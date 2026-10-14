#!/usr/bin/env python3
"""Run vendor-card evals: render fixtures vs naive HTML, grade, write review."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS.parent
REPO_ROOT = SKILL_ROOT.parent.parent.parent
EVALS_JSON = SKILL_ROOT / "evals" / "evals.json"
WORKSPACE = REPO_ROOT / "vendor-card-workspace" / "iteration-3"
FIXTURES = SKILL_ROOT / "evals" / "fixtures"

sys.path.insert(0, str(SCRIPTS))
from grade_card import grade_run  # noqa: E402
from render_card import patch_and_render  # noqa: E402


def load_evals() -> list[dict]:
    data = json.loads(EVALS_JSON.read_text(encoding="utf-8"))
    return list(data.get("evals") or [])


def fixture_path(item: dict) -> Path:
    files = item.get("files") or []
    if not files:
        raise SystemExit(f"eval {item.get('name')} missing files")
    path = SKILL_ROOT / files[0]
    if not path.is_file():
        raise SystemExit(f"fixture missing: {path}")
    return path


def run_with_skill(out: Path, fixture: Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    data = json.loads(fixture.read_text(encoding="utf-8"))
    (out / "card-data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    t0 = time.perf_counter()
    result = patch_and_render(out, {})
    ms = int((time.perf_counter() - t0) * 1000)
    (out / "render_result.json").write_text(
        json.dumps(
            {
                "card_path": result.get("card_path"),
                "needs_claim_sync": result.get("needs_claim_sync"),
                "format_valid": result.get("format_valid"),
                "quality_ok": result.get("quality_ok"),
                "quality_warnings": result.get("quality_warnings") or [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "total_tokens": 0,
        "duration_ms": ms,
        "total_duration_seconds": round(ms / 1000, 3),
    }


def run_without_skill(out: Path, fixture: Path) -> dict:
    """Naive baseline: package-as-title HTML blob, no tables / footer meta."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    data = json.loads(fixture.read_text(encoding="utf-8"))
    t0 = time.perf_counter()
    pkg = str(data.get("package_name") or "Package")
    supplier = str(data.get("supplier_name") or "Unknown")
    # Intentionally wrong header (package as h1) — historical failure mode
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{pkg}</title></head>
<body>
<h1 class="card-title">{pkg}</h1>
<p>{supplier}</p>
<p>付款：见正文笔记</p>
<ul>
{(chr(10).join(f"<li>{n.get('name')} {n.get('pct')}</li>" for n in (data.get('payment_nodes') or [])))}
</ul>
<p>数据来源：随便写在正文里</p>
</body></html>
"""
    (out / "履约条件卡片.html").write_text(html, encoding="utf-8")
    # Keep card-data so grader can still inspect content quality vs HTML mismatch
    (out / "card-data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "notes.md").write_text(
        "naive card: package_name used as title, no payment-table.\n", encoding="utf-8"
    )
    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "total_tokens": 0,
        "duration_ms": ms,
        "total_duration_seconds": round(ms / 1000, 3),
    }


def setup_eval_layout(
    eval_dir: Path,
    with_out: Path,
    without_out: Path,
    eval_id: int,
    name: str,
    prompt: str,
    assertions: list[str],
    timing_with: dict,
    timing_without: dict,
    eval_kind: str,
) -> None:
    if eval_dir.exists():
        shutil.rmtree(eval_dir)
    for label, src, timing in (
        ("with_skill", with_out, timing_with),
        ("without_skill", without_out, timing_without),
    ):
        outputs = eval_dir / label / "outputs"
        run1 = eval_dir / label / "run-1"
        outputs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, outputs)
        run1.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / "grading.json", run1 / "grading.json")
        shutil.copy2(src / "grading.json", outputs / "grading.json")
        (run1 / "timing.json").write_text(
            json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": eval_id,
                "eval_name": name,
                "eval_kind": eval_kind,
                "prompt": prompt,
                "assertions": assertions,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_benchmark(evals_meta: list[dict]) -> None:
    def rate(items: list[dict], key: str) -> float | None:
        vals = [x[key] for x in items if x.get(key) is not None]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 4)

    standard = [e for e in evals_meta if e.get("eval_kind") != "diagnostic"]
    diagnostic = [e for e in evals_meta if e.get("eval_kind") == "diagnostic"]

    summary = {
        "skill_name": "vendor-card",
        "iteration": 3,
        "standard_evals": {
            "with_skill_pass_rate": rate(standard, "with_pass"),
            "without_skill_pass_rate": rate(standard, "without_pass"),
            "with_skill_format_pass_rate": rate(standard, "with_format"),
            "with_skill_quality_pass_rate": rate(standard, "with_quality"),
            "without_skill_format_pass_rate": rate(standard, "without_format"),
            "count": len(standard),
        },
        "diagnostic_evals": {
            "with_skill_pass_rate": rate(diagnostic, "with_pass"),
            "with_skill_format_pass_rate": rate(diagnostic, "with_format"),
            "with_skill_quality_pass_rate": rate(diagnostic, "with_quality"),
            "note": "quality-gap：期望仍出卡 + quality_ok=false + 提醒横幅",
            "count": len(diagnostic),
        },
        "evals": evals_meta,
    }
    (WORKSPACE / "benchmark.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    std = summary["standard_evals"]
    diag = summary["diagnostic_evals"]
    lines = [
        "# vendor-card · iteration-3 benchmark",
        "",
        "## 达标题（eval 0–4）",
        f"- with_skill 总分：{std['with_skill_pass_rate']}",
        f"- without_skill 总分：{std['without_skill_pass_rate']}",
        f"- with_skill **format**：{std['with_skill_format_pass_rate']}",
        f"- with_skill **quality**：{std['with_skill_quality_pass_rate']}",
        "",
        "## 诊断题（quality-gap）",
        f"- with_skill 总分：{diag['with_skill_pass_rate']}",
        f"- format：{diag['with_skill_format_pass_rate']}（期望仍出卡）",
        f"- quality：{diag['with_skill_quality_pass_rate']}（期望提醒到位）",
        "",
        "规则见 `.cursor/skills/vendor-card/evals/GRADING_RULES.md`",
        "",
    ]
    (WORKSPACE / "benchmark.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)

    meta_rows: list[dict] = []
    for item in load_evals():
        name = item["name"]
        eval_id = int(item["id"])
        assertions = list(item.get("assertions") or [])
        eval_kind = str(item.get("eval_kind") or "standard")
        fixture = fixture_path(item)

        eval_dir = WORKSPACE / f"eval-{eval_id}"
        ws = WORKSPACE / "_tmp" / f"{name}-with"
        wo = WORKSPACE / "_tmp" / f"{name}-without"

        timing_with = run_with_skill(ws, fixture)
        timing_without = run_without_skill(wo, fixture)

        # Placeholder grading.json so layout copy succeeds; re-grade on final paths below.
        for root in (ws, wo):
            (root / "grading.json").write_text("{}\n", encoding="utf-8")

        setup_eval_layout(
            eval_dir,
            ws,
            wo,
            eval_id,
            name,
            item.get("prompt") or name,
            assertions,
            timing_with,
            timing_without,
            eval_kind,
        )

        with_outputs = eval_dir / "with_skill" / "outputs"
        without_outputs = eval_dir / "without_skill" / "outputs"
        g_with = grade_run(with_outputs, assertions)
        g_without = grade_run(without_outputs, assertions)
        # Mirror into run-1 for review tooling
        for label, grading in (
            ("with_skill", g_with),
            ("without_skill", g_without),
        ):
            run1 = eval_dir / label / "run-1" / "grading.json"
            run1.write_text(
                json.dumps(grading, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        meta_rows.append(
            {
                "eval_id": eval_id,
                "name": name,
                "eval_kind": eval_kind,
                "with_pass": g_with["pass_rate"],
                "without_pass": g_without["pass_rate"],
                "with_format": (g_with.get("format") or {}).get("pass_rate"),
                "with_quality": (g_with.get("quality") or {}).get("pass_rate"),
                "without_format": (g_without.get("format") or {}).get("pass_rate"),
                "without_quality": (g_without.get("quality") or {}).get("pass_rate"),
            }
        )
        print(
            f"OK eval-{eval_id} {name} "
            f"with={g_with['passed']}/{g_with['total']} "
            f"without={g_without['passed']}/{g_without['total']}"
        )

    tmp = WORKSPACE / "_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)

    write_benchmark(meta_rows)
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "render_eval_review.py"),
            str(WORKSPACE),
            str(WORKSPACE / "review.html"),
        ],
        check=True,
        cwd=str(SCRIPTS),
    )
    print("Eval workspace ready:", WORKSPACE)


if __name__ == "__main__":
    main()
