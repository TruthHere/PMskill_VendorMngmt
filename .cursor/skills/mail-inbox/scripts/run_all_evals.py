#!/usr/bin/env python3
"""Run mail-inbox classify evals, grade, build review page."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS.parent
REPO_ROOT = SKILL_ROOT.parent.parent.parent
WORKSPACE = REPO_ROOT / "mail-inbox-workspace" / "iteration-1"
EVALS_JSON = SKILL_ROOT / "evals" / "evals.json"
GRADE = SCRIPTS / "grade_run.py"
REVIEW = SKILL_ROOT.parent / "po-flow" / "scripts" / "render_eval_review.py"

sys.path.insert(0, str(SCRIPTS))
from classify_mail import classify_from_message  # noqa: E402


def load_evals() -> list[dict[str, Any]]:
    data = json.loads(EVALS_JSON.read_text(encoding="utf-8"))
    return list(data.get("evals") or [])


def naive_classify(subject: str, body: str) -> dict[str, Any]:
    """故意复现旧坑：FAQ / 技术确认 / 随口 COD / 裸 invoice。"""
    blob = f"{subject}\n{body}"
    blob_l = blob.lower()
    intent = "unknown"
    if re.search(r"\[项目初始化\]|项目初始化", subject, re.I):
        intent = "project_init"
    elif re.search(r"change\s*order.*\bpo\b|change\s*po", blob, re.I):
        intent = "change.change_po"
    elif re.search(r"\bPMI\b", blob, re.I):
        intent = "change.pmi"
    elif re.search(r"\bCOD\b", blob, re.I):
        intent = "change.cod"
    elif re.search(r"技术确认|approved\s*drawing|技术文件|submittal", blob, re.I):
        intent = "change.tech_confirm"
    elif re.search(r"\brfq\b|\brfp\b", blob_l):
        intent = "fulfillment.rfp"
    elif re.search(r"raise\s*po", blob_l):
        intent = "fulfillment.raise_po"
    elif re.search(r"payment\s*application|invoice|请款", blob, re.I):
        intent = "payment_claim.inbound"

    route = {
        "project_init": "new-project",
        "fulfillment.rfp": "po-flow",
        "fulfillment.raise_po": "po-flow",
        "change.change_po": "change-flow",
        "change.pmi": "change-flow",
        "change.cod": "change-flow",
        "change.tech_confirm": "change-flow",
        "payment_claim.inbound": "payment-flow",
    }.get(intent)

    return {
        "ok": True,
        "intent": intent,
        "route_to": route,
        "confidence": "low" if intent == "unknown" else "high",
        "hints": {"subject": subject, "change_no": "", "package_name": ""},
        "enrichment": {"payment_terms": "payment terms" in blob_l},
        "attachments": [],
        "pending": None,
        "did": ["naive_classify"],
        "next": {"skill": route, "action": "naive"},
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_one(eval_item: dict[str, Any], config: str, out_dir: Path) -> tuple[dict[str, Any], int]:
    subject = eval_item.get("subject") or ""
    body = eval_item.get("body") or ""
    expected = eval_item.get("expected") or {}
    t0 = time.perf_counter()
    if config == "with_skill":
        result = classify_from_message(subject=subject, body=body)
    else:
        result = naive_classify(subject, body)
    elapsed = int((time.perf_counter() - t0) * 1000)
    run_dir = out_dir / config / "run-1"
    write_json(run_dir / "result.json", result)
    write_json(run_dir / "expected.json", expected)
    proc = subprocess.run(
        [sys.executable, str(GRADE), str(run_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    grading = json.loads((run_dir / "grading.json").read_text(encoding="utf-8"))
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr or proc.stdout or "grade_run failed")
    return grading, elapsed


def main() -> int:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)

    evals = load_evals()
    with_pass = with_total = wo_pass = wo_total = 0
    timing_with: list[int] = []
    timing_wo: list[int] = []

    for item in evals:
        name = item.get("name") or f"eval-{item.get('id')}"
        eval_dir = WORKSPACE / f"eval-{item.get('id')}-{name}"
        eval_dir.mkdir(parents=True)
        write_json(
            eval_dir / "eval_metadata.json",
            {
                "eval_id": item.get("id"),
                "eval_name": name,
                "prompt": item.get("prompt") or "",
            },
        )
        for config in ("with_skill", "without_skill"):
            grading, elapsed = run_one(item, config, eval_dir)
            s = grading.get("summary") or {}
            if config == "with_skill":
                with_pass += int(s.get("passed") or 0)
                with_total += int(s.get("total") or 0)
                timing_with.append(elapsed)
            else:
                wo_pass += int(s.get("passed") or 0)
                wo_total += int(s.get("total") or 0)
                timing_wo.append(elapsed)

    with_rate = (with_pass / with_total) if with_total else 0.0
    wo_rate = (wo_pass / wo_total) if wo_total else 0.0
    benchmark = {
        "skill": "mail-inbox",
        "run_summary": {
            "with_skill": {
                "pass_rate": {"mean": with_rate},
                "passed": with_pass,
                "total": with_total,
                "latency_ms": {"mean": sum(timing_with) / len(timing_with) if timing_with else 0},
            },
            "without_skill": {
                "pass_rate": {"mean": wo_rate},
                "passed": wo_pass,
                "total": wo_total,
                "latency_ms": {"mean": sum(timing_wo) / len(timing_wo) if timing_wo else 0},
            },
            "delta": {"pass_rate": f"{(with_rate - wo_rate) * 100:.1f} pp"},
        },
    }
    write_json(WORKSPACE / "benchmark.json", benchmark)

    lines = [
        "# mail-inbox eval summary",
        "",
        f"- with_skill: {with_pass}/{with_total} ({with_rate:.0%})",
        f"- without_skill: {wo_pass}/{wo_total} ({wo_rate:.0%})",
        f"- delta: {benchmark['run_summary']['delta']['pass_rate']}",
        "",
    ]
    (WORKSPACE / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    review = WORKSPACE / "review.html"
    subprocess.run(
        [sys.executable, str(REVIEW), str(WORKSPACE), str(review)],
        check=True,
    )
    # Retitle page for this skill
    html = review.read_text(encoding="utf-8")
    html = html.replace(
        "po-flow · Eval Review",
        "mail-inbox · Eval Review",
    )
    review.write_text(html, encoding="utf-8")

    print(json.dumps(benchmark["run_summary"], ensure_ascii=False, indent=2))
    print(f"review: {review}")
    return 0 if with_pass == with_total else 1


if __name__ == "__main__":
    raise SystemExit(main())
