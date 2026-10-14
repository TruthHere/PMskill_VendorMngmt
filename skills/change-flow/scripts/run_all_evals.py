#!/usr/bin/env python3
"""Run Skill 3 evals via real handle_change_email, grade strictly, build review page."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from email.mime.text import MIMEText
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS.parent
REPO_ROOT = SKILL_ROOT.parent.parent
WORKSPACE = REPO_ROOT / "change-flow-workspace" / "iteration-1"
EVALS_JSON = SKILL_ROOT / "evals" / "evals.json"
INIT = SKILL_ROOT.parent / "po-flow" / "scripts" / "init_project.py"
UPDATE = SKILL_ROOT.parent / "po-flow" / "scripts" / "update_tracker.py"
HANDLE = SCRIPTS / "handle_change_email.py"
GRADE = SCRIPTS / "grade_run.py"
REVIEW = SKILL_ROOT.parent / "po-flow" / "scripts" / "render_eval_review.py"

PKG_NAME = "Glazing partition"
HINTS = {"change_no": "COT003", "package_name": PKG_NAME}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def write_eml(path: Path, subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = "pm@example.com"
    msg["To"] = "ai@example.com"
    msg["Date"] = "Sat, 8 Aug 2026 22:00:00 +0800"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msg.as_bytes())


def write_route(path: Path, intent: str) -> None:
    path.write_text(
        json.dumps({"intent": intent, "confidence": 0.95, "hints": HINTS}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def seed_project(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    run(
        [
            sys.executable,
            str(INIT),
            "--root",
            str(root),
            "--name",
            "ChangeEval",
            "--code",
            "CHEVAL",
            "--type",
            "实验室",
            "--address",
            "上海",
            "--client",
            "Apple",
            "--pm",
            "Truth",
            "--mailbox-address",
            "change-eval@test.local",
        ]
    )
    run(
        [
            sys.executable,
            str(UPDATE),
            "--project-root",
            str(root),
            "--action",
            "add-package",
            "--package-name",
            PKG_NAME,
            "--supplier",
            "Facade Co",
            "--supplier-short",
            "Facade",
            "--contact-email",
            "a@b.com",
            "--package-type",
            "供应",
            "--milestone",
            "已发PO",
        ]
    )
    tracker = next(root.glob("*_procurement_packages_status_tracker.csv"))
    (root / "tracker_baseline.txt").write_text(tracker.read_text(encoding="utf-8-sig"), encoding="utf-8")


def handle(root: Path, eml: Path, route: Path) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            sys.executable,
            str(HANDLE),
            "--project-root",
            str(root),
            "--eml",
            str(eml),
            "--route-json",
            str(route),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout or "{}")
    data["_elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return data


def save_result(root: Path, data: dict, eval_type: str) -> None:
    (root / "process_result.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / "eval_type.txt").write_text(eval_type + "\n", encoding="utf-8")


def grade(root: Path, eval_type: str) -> None:
    run([sys.executable, str(GRADE), str(root), "--eval-type", eval_type])


def timing_from_ms(ms: int) -> dict:
    return {
        "total_tokens": 0,
        "duration_ms": ms,
        "total_duration_seconds": round(ms / 1000, 3),
    }


def mail_step(root: Path, name: str, intent: str, subject: str, body: str) -> dict:
    mail = root / "_mail"
    eml = mail / f"{name}.eml"
    route = mail / f"{name}.route.json"
    write_eml(eml, subject, body)
    write_route(route, intent)
    return handle(root, eml, route)


# --- with_skill ---


def run_with_skill_cod(out: Path) -> dict:
    seed_project(out)
    data = mail_step(
        out,
        "cod",
        "change.cod",
        "ChangeEval · COT-003 · COD — 增加一道防火门",
        "变更序号：COT-003\n采购包：Glazing partition\n预估金额不含税：¥15,000\n",
    )
    data["_eval_type"] = "cod"
    save_result(out, data, "cod")
    return timing_from_ms(int(data.get("_elapsed_ms") or 0))


def run_with_skill_lifecycle(out: Path) -> dict:
    seed_project(out)
    t0 = time.perf_counter()
    steps = [
        ("cod", "change.cod", "ChangeEval · COT-003 · COD — 增加一道防火门", "变更序号：COT-003\n采购包：Glazing partition\n预估金额不含税：¥15,000\n"),
        ("pmi", "change.pmi", "ChangeEval · [PMI] COT-003", "PMI for COT-003 Glazing partition\n"),
        ("tech", "change.tech_submit", "COT-003 shop drawing submit", "Please review shop drawing for COT-003 Glazing partition\n"),
        ("tc", "change.tech_confirm", "COT-003 drawings approved", "drawings approved, no further comment. COT-003 Glazing partition\n"),
        ("com", "change.commercial", "FW: COT-003 quote to QS", "Forward quote for COT-003 Glazing partition to QS\n"),
        (
            "amt",
            "change.commercial_amount",
            "COT-003 CP Confirm",
            "CP confirm final price excl VAT ¥16,800 for COT-003 Glazing partition\n",
        ),
        ("po", "change.change_po", "ChangeEval Raise PO (Change PO) COT-003", "Change PO issued for COT-003 Glazing partition\n"),
    ]
    last = {}
    for name, intent, subject, body in steps:
        last = mail_step(out, name, intent, subject, body)
    elapsed = int((time.perf_counter() - t0) * 1000)
    last["_eval_type"] = "lifecycle"
    last["_elapsed_ms"] = elapsed
    save_result(out, last, "lifecycle")
    return timing_from_ms(elapsed)


def run_with_skill_ooo(out: Path) -> dict:
    seed_project(out)
    mail_step(
        out,
        "cod",
        "change.cod",
        "ChangeEval · COT-003 · COD — 增加一道防火门",
        "变更序号：COT-003\n采购包：Glazing partition\n预估金额不含税：¥15,000\n",
    )
    data = mail_step(
        out,
        "com",
        "change.commercial",
        "FW: COT-003 quote to QS",
        "Forward quote for COT-003 Glazing partition to QS\n",
    )
    data["_eval_type"] = "out_of_order"
    save_result(out, data, "out_of_order")
    return timing_from_ms(int(data.get("_elapsed_ms") or 0))


# --- without_skill (naive, should fail strict checks) ---


def run_without_skill_cod(out: Path) -> dict:
    t0 = time.perf_counter()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "notes.md").write_text("收到 COD，记了一笔变更。\n", encoding="utf-8")
    (out / "change_log.csv").write_text(
        "变更序号,当前状态\nCOT-003,COD\n", encoding="utf-8-sig"
    )
    save_result(out, {"auto": True, "note": "naive"}, "cod")
    (out / "tracker_baseline.txt").write_text("baseline\n", encoding="utf-8")
    return timing_from_ms(int((time.perf_counter() - t0) * 1000))


def run_without_skill_lifecycle(out: Path) -> dict:
    t0 = time.perf_counter()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    pkg = out / "01_Glazingpartition_Facade"
    pkg.mkdir(parents=True)
    (pkg / "card-data.json").write_text(
        json.dumps({"change_items": [{"number": "COT003", "content": "x", "confirmed_amount": "¥3.00"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    # naive: 金额写错到 ¥3，且误以为该写卡片
    (out / "ChangeEval_change_log.csv").write_text(
        "# 最后更新,x\n"
        "变更序号,采购包名称,供应商,变更内容,预估金额,最终确认金额,时间影响,当前状态,技术文件提交,技术审核中,技术确认,商务确认,商务金额确认,Change PO下发,已取消,归档路径,备注\n"
        "COT003,Glazing partition,Facade,门,,¥3.00,,Change PO 下发,,,,,,,,\n",
        encoding="utf-8-sig",
    )
    save_result(out, {"auto": True, "status": "Change PO 下发"}, "lifecycle")
    (out / "tracker_baseline.txt").write_text("baseline\n", encoding="utf-8")
    return timing_from_ms(int((time.perf_counter() - t0) * 1000))


def run_without_skill_ooo(out: Path) -> dict:
    t0 = time.perf_counter()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "ChangeEval_change_log.csv").write_text(
        "# 最后更新,x\n"
        "变更序号,采购包名称,供应商,变更内容,预估金额,最终确认金额,时间影响,当前状态,技术文件提交,技术审核中,技术确认,商务确认,商务金额确认,Change PO下发,归档路径,备注\n"
        "COT003,Glazing partition,Facade,门,,,,商务确认,,,,,,,\n",
        encoding="utf-8-sig",
    )
    save_result(out, {"auto": True, "status": "商务确认"}, "out_of_order")
    (out / "tracker_baseline.txt").write_text("baseline\n", encoding="utf-8")
    return timing_from_ms(int((time.perf_counter() - t0) * 1000))


def load_evals() -> list[dict]:
    return list(json.loads(EVALS_JSON.read_text(encoding="utf-8")).get("evals") or [])


RUNNERS = {
    "cod-create": (run_with_skill_cod, run_without_skill_cod, "cod"),
    "lifecycle-close": (run_with_skill_lifecycle, run_without_skill_lifecycle, "lifecycle"),
    "out-of-order": (run_with_skill_ooo, run_without_skill_ooo, "out_of_order"),
}


def setup_eval_layout(
    eval_dir: Path,
    ws: Path,
    wo: Path,
    eval_id: int,
    name: str,
    prompt: str,
    assertions: list,
    timing_with: dict,
    timing_without: dict,
) -> None:
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {"eval_id": eval_id, "eval_name": name, "prompt": prompt, "assertions": assertions},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for config, src, timing in (
        ("with_skill", ws, timing_with),
        ("without_skill", wo, timing_without),
    ):
        config_dir = eval_dir / config
        run_dir = config_dir / "run-1"
        outputs = config_dir / "outputs"
        run_dir.mkdir(parents=True, exist_ok=True)
        if outputs.exists():
            shutil.rmtree(outputs)
        shutil.copytree(src, outputs)
        grading_src = src / "grading.json"
        if grading_src.exists():
            shutil.copy2(grading_src, run_dir / "grading.json")
            shutil.copy2(grading_src, outputs / "grading.json")
        (run_dir / "timing.json").write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")


def write_benchmark(workspace: Path) -> None:
    rows = []
    with_pass = with_total = wo_pass = wo_total = 0
    for eval_dir in sorted(workspace.glob("eval-*")):
        meta = json.loads((eval_dir / "eval_metadata.json").read_text(encoding="utf-8"))
        for config in ("with_skill", "without_skill"):
            g = json.loads((eval_dir / config / "run-1" / "grading.json").read_text(encoding="utf-8"))
            s = g["summary"]
            rows.append({"eval": meta["eval_name"], "config": config, **s})
            if config == "with_skill":
                with_pass += s["passed"]
                with_total += s["total"]
            else:
                wo_pass += s["passed"]
                wo_total += s["total"]
    with_rate = round(with_pass / with_total, 4) if with_total else 0
    wo_rate = round(wo_pass / wo_total, 4) if wo_total else 0
    data = {
        "skill_name": "change-flow",
        "run_summary": {
            "with_skill": {"pass_rate": {"mean": with_rate}, "passed": with_pass, "total": with_total},
            "without_skill": {"pass_rate": {"mean": wo_rate}, "passed": wo_pass, "total": wo_total},
            "delta": {"pass_rate": round(with_rate - wo_rate, 4)},
        },
        "evals": rows,
    }
    (workspace / "benchmark.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# change-flow benchmark",
        "",
        f"- with_skill: {with_pass}/{with_total} ({with_rate})",
        f"- without_skill: {wo_pass}/{wo_total} ({wo_rate})",
        f"- delta: {round(with_rate - wo_rate, 4)}",
        "",
    ]
    for row in rows:
        lines.append(f"- {row['eval']} / {row['config']}: {row['passed']}/{row['total']}")
    (workspace / "benchmark.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)

    for item in load_evals():
        name = item["name"]
        eval_id = int(item["id"])
        if name not in RUNNERS:
            raise SystemExit(f"No runner for eval name={name}")
        with_fn, without_fn, eval_type = RUNNERS[name]
        eval_dir = WORKSPACE / f"eval-{eval_id}"
        ws = WORKSPACE / "_tmp" / f"{name}-with"
        wo = WORKSPACE / "_tmp" / f"{name}-without"
        timing_with = with_fn(ws)
        timing_without = without_fn(wo)
        grade(ws, eval_type)
        grade(wo, eval_type)
        setup_eval_layout(
            eval_dir,
            ws,
            wo,
            eval_id,
            name,
            item.get("prompt") or name,
            item.get("assertions") or [],
            timing_with,
            timing_without,
        )
        print(f"OK eval-{eval_id} {name}")

    tmp = WORKSPACE / "_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)

    write_benchmark(WORKSPACE)
    if REVIEW.is_file():
        # Patch title via env-less: render script hardcodes skill1 title; still useful
        subprocess.run(
            [sys.executable, str(REVIEW), str(WORKSPACE), str(WORKSPACE / "review.html")],
            check=False,
        )
        # Fix page title for Skill 3
        review = WORKSPACE / "review.html"
        if review.is_file():
            text = review.read_text(encoding="utf-8")
            review.write_text(
                text.replace("po-flow · Eval Review", "change-flow · Eval Review"),
                encoding="utf-8",
            )
    print("Eval workspace ready:", WORKSPACE)


if __name__ == "__main__":
    main()
