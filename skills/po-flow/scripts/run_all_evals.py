#!/usr/bin/env python3
"""Run Skill 1 MVP evals via real process_email (.eml), grade strictly, build review page."""

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
INPUT = SKILL_ROOT / "samples" / "input"
REPO_ROOT = SKILL_ROOT.parent.parent
WORKSPACE = REPO_ROOT / "po-flow-workspace" / "iteration-2"
EVALS_JSON = SKILL_ROOT / "evals" / "evals.json"
SKILL_CREATOR = Path.home() / ".cursor" / "skills" / "skill-creator"

from eval_fixtures import (  # noqa: E402
    CONTACT_EMAIL,
    PKG_NAME,
    PKG_TYPE,
    SUPPLIER,
    SUPPLIER_SHORT,
    package_dir,
)


def run(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(SCRIPTS / script), *args], check=True, cwd=str(SCRIPTS))


def write_eml(path: Path, subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = "pm@example.com"
    msg["To"] = "ai@example.com"
    msg["Date"] = "Sat, 1 Aug 2026 10:00:00 +0800"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(msg.as_bytes())


def write_route(path: Path, intent: str) -> None:
    path.write_text(
        json.dumps({"intent": intent, "confidence": 0.95}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def process_email(
    project_root: Path,
    eml: Path,
    *,
    intent: str | None = None,
    attachment: Path | None = None,
) -> dict:
    cmd = [
        sys.executable,
        str(SCRIPTS / "process_email.py"),
        "--eml",
        str(eml),
        "--project-root",
        str(project_root),
    ]
    route: Path | None = None
    if intent:
        route = project_root / f"_route_{eml.stem}.json"
        write_route(route, intent)
        cmd.extend(["--route-json", str(route)])
    if attachment:
        cmd.extend(["--attachment", str(attachment)])
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    if proc.returncode != 0:
        raise RuntimeError(
            f"process_email failed ({proc.returncode}): {proc.stderr or proc.stdout}"
        )
    raw = (proc.stdout or "").strip()
    data = json.loads(raw) if raw else {}
    data["_elapsed_ms"] = elapsed_ms
    return data


def seed_empty_project(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    run(
        "init_project.py",
        "--root",
        str(root),
        "--name",
        "Sample Project",
        "--code",
        "SAMPLE",
        "--type",
        "实验室",
        "--address",
        "上海市浦东新区张江路 100 号",
        "--client",
        "样例业主有限公司",
        "--pm",
        "张三",
        "--currency",
        "CNY 含税",
    )


def seed_package_tech_confirmed(root: Path) -> None:
    seed_empty_project(root)
    run(
        "update_tracker.py",
        "--project-root",
        str(root),
        "--action",
        "add-package",
        "--package-name",
        PKG_NAME,
        "--supplier",
        SUPPLIER,
        "--supplier-short",
        SUPPLIER_SHORT,
        "--contact-email",
        CONTACT_EMAIL,
        "--package-type",
        PKG_TYPE,
        "--milestone",
        "技术方案已确认",
    )


def save_result(root: Path, data: dict) -> None:
    (root / "process_result.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "eval_type.txt").write_text(data.get("_eval_type", "") + "\n", encoding="utf-8")


def grade(output_dir: Path, eval_type: str) -> None:
    (output_dir / "eval_type.txt").write_text(eval_type + "\n", encoding="utf-8")
    run("grade_run.py", str(output_dir), "--eval-type", eval_type)


def write_metadata(eval_dir: Path, eval_id: int, name: str, prompt: str, assertions: list) -> None:
    eval_dir.mkdir(parents=True, exist_ok=True)
    (eval_dir / "eval_metadata.json").write_text(
        json.dumps(
            {
                "eval_id": eval_id,
                "eval_name": name,
                "prompt": prompt,
                "assertions": assertions,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


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
    write_metadata(eval_dir, eval_id, name, prompt, assertions)
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
        (run_dir / "timing.json").write_text(
            json.dumps(timing, indent=2) + "\n", encoding="utf-8"
        )


def timing_from_ms(ms: int, tokens: int = 0) -> dict:
    return {
        "total_tokens": tokens,
        "duration_ms": ms,
        "total_duration_seconds": round(ms / 1000, 3),
    }


# --- with_skill runs (real process_email) ---


def run_with_skill_misroute(out: Path) -> dict:
    seed_empty_project(out)
    eml = out / "_mail" / "init.eml"
    write_eml(
        eml,
        "[项目初始化] Sample Project - SAMPLE",
        "项目名称：Sample Project\n项目编号：SAMPLE\n项目类型：实验室\n",
    )
    data = process_email(out, eml, intent="project_init")
    data["_eval_type"] = "misroute_init"
    save_result(out, data)
    return timing_from_ms(int(data.get("_elapsed_ms") or 0))


def run_with_skill_rfp(out: Path) -> dict:
    seed_empty_project(out)
    body = (INPUT / "rfp_body.txt").read_text(encoding="utf-8")
    # strip subject line if present as first line
    lines = body.strip().splitlines()
    if lines and "RFP" in lines[0] and "项目" not in lines[0]:
        subject = lines[0].strip()
        body = "\n".join(lines[1:]).strip() + "\n"
    else:
        subject = "SAMPLE · BMS · BOSCH — RFP"
    eml = out / "_mail" / "rfp.eml"
    write_eml(eml, subject, body)
    data = process_email(out, eml, intent="fulfillment.rfp")
    data["_eval_type"] = "rfp"
    save_result(out, data)
    return timing_from_ms(int(data.get("_elapsed_ms") or 0))


def run_with_skill_po(out: Path) -> dict:
    seed_package_tech_confirmed(out)
    quote = INPUT / "final_quote.pdf.txt"
    po_body = (
        "项目：SAMPLE\n"
        "采购包：BMS\n"
        "供应商：BOSCH Building Technologies\n"
        "对接人邮箱：procurement@bosch-build.example.com\n"
        "金额含税：¥1,280,000\n"
        "交期：2026-09-30\n"
        "Raise PO\n"
    )
    eml_po = out / "_mail" / "raise_po.eml"
    write_eml(eml_po, "SAMPLE · BMS · BOSCH — Raise PO", po_body)
    # copy quote beside as attachment file
    att = out / "_mail" / "final_quote.pdf.txt"
    shutil.copy2(quote, att)
    t0 = time.perf_counter()
    data_po = process_email(
        out, eml_po, intent="fulfillment.raise_po", attachment=att
    )
    pay_body = (
        "项目：SAMPLE\n"
        "采购包：BMS\n"
        "供应商：BOSCH Building Technologies\n"
        "付款指示：\n"
        "1. 预付款 30%，PO 签发后 7 日内\n"
        "2. 到货验收 60%，全部到货并验收合格后\n"
        "3. 尾款 10%，质保期满无质量问题后\n"
    )
    eml_pay = out / "_mail" / "payment.eml"
    write_eml(eml_pay, "SAMPLE · BMS · BOSCH — 付款指示", pay_body)
    data_pay = process_email(out, eml_pay, intent="fulfillment.payment_terms")
    elapsed = int((time.perf_counter() - t0) * 1000)
    merged = {
        "raise_po": data_po,
        "payment": data_pay,
        "reason": data_pay.get("reason") or data_po.get("reason") or "",
        "step": data_pay.get("step") or data_po.get("step"),
        "payment_nodes": data_pay.get("payment_nodes") or data_po.get("payment_nodes"),
        "_eval_type": "po",
        "_elapsed_ms": elapsed,
    }
    save_result(out, merged)
    return timing_from_ms(elapsed)


# --- without_skill baselines (naive, should fail strict checks) ---


def run_without_skill_misroute(out: Path) -> dict:
    t0 = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    (out / "notes.md").write_text(
        "# 已收到项目初始化邮件，当作新项目记下了。\n", encoding="utf-8"
    )
    (out / "process_result.json").write_text(
        json.dumps({"step": "stage0", "auto": True, "note": "naive init"}, indent=2) + "\n",
        encoding="utf-8",
    )
    return timing_from_ms(int((time.perf_counter() - t0) * 1000))


def run_without_skill_rfp(out: Path) -> dict:
    t0 = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    pkg = out / "01_BMS_BOSCH"
    pkg.mkdir(exist_ok=True)
    (pkg / "rfp.txt").write_text(f"RFP for {PKG_NAME}\n", encoding="utf-8")
    (out / "tracker.csv").write_text(
        "采购包名称,供应商名称,状态\nBMS,BOSCH,new\n",
        encoding="utf-8-sig",
    )
    return timing_from_ms(int((time.perf_counter() - t0) * 1000))


def run_without_skill_po(out: Path) -> dict:
    t0 = time.perf_counter()
    out.mkdir(parents=True, exist_ok=True)
    pkg = out / PKG_NAME
    pkg.mkdir(exist_ok=True)
    (pkg / "po_summary.txt").write_text("PO issued, 1.28M, pay 30/60/10\n", encoding="utf-8")
    (out / "tracker.csv").write_text(
        "采购包名称,状态,总金额\nBMS,PO,1280000\n",
        encoding="utf-8-sig",
    )
    return timing_from_ms(int((time.perf_counter() - t0) * 1000))


def load_evals() -> list[dict]:
    data = json.loads(EVALS_JSON.read_text(encoding="utf-8"))
    return list(data.get("evals") or [])


RUNNERS = {
    "misroute-init": (run_with_skill_misroute, run_without_skill_misroute, "misroute_init"),
    "rfp-forward": (run_with_skill_rfp, run_without_skill_rfp, "rfp"),
    "po-payment": (run_with_skill_po, run_without_skill_po, "po"),
}


def aggregate_and_review() -> None:
    if not SKILL_CREATOR.is_dir():
        print("Skip benchmark viewer: skill-creator not found at", SKILL_CREATOR)
        # still write a local review
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "render_eval_review.py"),
                str(WORKSPACE),
                str(WORKSPACE / "review.html"),
            ],
            check=False,
            cwd=str(SCRIPTS),
        )
        return
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.aggregate_benchmark",
                str(WORKSPACE),
                "--skill-name",
                "po-flow",
                "--skill-path",
                str(SKILL_ROOT),
            ],
            check=True,
            cwd=str(SKILL_CREATOR),
        )
    except subprocess.CalledProcessError as exc:
        print("aggregate_benchmark failed:", exc)
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
        if ws.exists():
            shutil.rmtree(ws)
        if wo.exists():
            shutil.rmtree(wo)

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

    aggregate_and_review()
    print("Eval workspace ready:", WORKSPACE)


if __name__ == "__main__":
    main()
