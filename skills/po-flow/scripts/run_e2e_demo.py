#!/usr/bin/env python3
"""Run end-to-end MVP demo: stage 0 through step 4 for Sample Project."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
SAMPLES_ROOT = SKILL_ROOT / "samples"
INPUT_DIR = SAMPLES_ROOT / "input"
PROJECT_DIR = SAMPLES_ROOT / "Sample-Project"

from eval_fixtures import (
    CONTACT_EMAIL,
    PKG_NAME,
    PKG_TYPE,
    SUPPLIER,
    SUPPLIER_SHORT,
    package_dir,
    run_render_card,
)


def run(script: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(SCRIPTS))


def main() -> None:
    if PROJECT_DIR.exists():
        import shutil
        shutil.rmtree(PROJECT_DIR)

    run(
        "init_project.py",
        "--root", str(PROJECT_DIR),
        "--name", "Sample Project",
        "--code", "SAMPLE",
        "--type", "实验室",
        "--address", "上海市浦东新区张江路 100 号",
        "--client", "样例业主有限公司",
        "--pm", "张三",
        "--currency", "CNY 含税",
    )

    run(
        "archive_file.py",
        "--project-root", str(PROJECT_DIR),
        "--source", str(INPUT_DIR / "project_schedule.csv"),
        "--dest-subdir", "项目档案/00_进度计划",
        "--file-type", "进度计划",
        "--package-name", "项目级",
        "--description", "总进度计划",
    )

    run(
        "import_schedule_csv.py",
        "--project-root", str(PROJECT_DIR),
        "--source", str(INPUT_DIR / "project_schedule.csv"),
    )

    run(
        "update_tracker.py",
        "--project-root", str(PROJECT_DIR),
        "--action", "add-package",
        "--package-name", PKG_NAME,
        "--supplier", SUPPLIER,
        "--supplier-short", SUPPLIER_SHORT,
        "--contact-email", CONTACT_EMAIL,
        "--package-type", PKG_TYPE,
        "--milestone", "RFP 发出",
    )
    pkg_dir = package_dir(PROJECT_DIR)

    run(
        "archive_file.py",
        "--package-dir", str(pkg_dir),
        "--source", str(INPUT_DIR / "rfp_body.txt"),
        "--dest-subdir", "07_往来文件",
        "--file-type", "RFP",
        "--package-name", PKG_NAME,
        "--description", "RFP正文",
        "--date", "20260701",
    )
    run(
        "archive_file.py",
        "--package-dir", str(pkg_dir),
        "--source", str(INPUT_DIR / "tech_spec.pdf.txt"),
        "--dest-subdir", "02_图纸",
        "--file-type", "技术图",
        "--package-name", PKG_NAME,
        "--description", "技术要求",
        "--date", "20260701",
    )
    patch1 = json.dumps({
        "scope_summary": "楼宇自控系统供应，含 DDC 控制器与现场调试",
        "acceptance_items": ["点位核对：按 I/O 清单逐项确认"],
        "data_sources": "RFP 邮件 2026-07-01",
    }, ensure_ascii=False)
    run_render_card("--package-dir", str(pkg_dir), "--patch", patch1)

    run(
        "archive_file.py",
        "--package-dir", str(pkg_dir),
        "--source", str(INPUT_DIR / "tech_confirmed.pdf.txt"),
        "--dest-subdir", "02_图纸",
        "--file-type", "技术图",
        "--package-name", PKG_NAME,
        "--description", "顾问确认图",
        "--version", "v终版",
        "--date", "20260710",
    )
    run(
        "update_tracker.py",
        "--project-root", str(PROJECT_DIR),
        "--action", "update",
        "--package-name", PKG_NAME,
        "--milestone", "技术方案已确认",
    )
    patch2 = json.dumps({
        "scope_summary": "楼宇自控系统；顾问确认 FX-160 控制器",
        "acceptance_items": [
            "点位核对：按 I/O 清单逐项确认",
            "通讯测试：BACnet IP 联调通过",
        ],
        "data_sources": "RFP 邮件 2026-07-01；顾问确认技术文件 2026-07-10",
    }, ensure_ascii=False)
    run_render_card("--package-dir", str(pkg_dir), "--patch", patch2)

    run(
        "archive_file.py",
        "--package-dir", str(pkg_dir),
        "--source", str(INPUT_DIR / "final_quote.pdf.txt"),
        "--dest-subdir", "01_合同报价",
        "--file-type", "报价单",
        "--package-name", PKG_NAME,
        "--description", "最终报价",
        "--version", "v终版",
        "--date", "20260715",
    )
    run(
        "update_tracker.py",
        "--project-root", str(PROJECT_DIR),
        "--action", "update",
        "--package-name", PKG_NAME,
        "--milestone", "PO 已发起",
        "--total-amount", "¥1,280,000 CNY 含税",
        "--delivery-summary", "2026-09-30 前全部到货",
    )
    patch3 = json.dumps({
        "total_amount": "¥1,280,000 CNY 含税",
        "delivery_schedule": "2026-09-30 前全部到货",
        "data_sources": "RFP 2026-07-01；顾问确认 2026-07-10；Raise PO 2026-07-15",
    }, ensure_ascii=False)
    run_render_card("--package-dir", str(pkg_dir), "--patch", patch3)

    patch4 = json.dumps({
        "payment_nodes": [
            {"name": "预付款", "pct": "30%", "condition": "PO 签发后 7 日内", "source": "邮件指示"},
            {"name": "到货验收", "pct": "60%", "condition": "全部到货并验收合格后", "source": "邮件指示"},
            {"name": "尾款", "pct": "10%", "condition": "质保期满无质量问题后", "source": "邮件指示"},
        ],
        "data_sources": "RFP 2026-07-01；顾问确认 2026-07-10；Raise PO 2026-07-15；付款指示邮件 2026-07-20",
    }, ensure_ascii=False)
    run_render_card("--package-dir", str(pkg_dir), "--patch", patch4)
    run(
        "update_tracker.py",
        "--project-root", str(PROJECT_DIR),
        "--action", "update",
        "--package-name", PKG_NAME,
        "--sync-payment-node",
    )

    sys.path.insert(0, str(SCRIPTS))
    from _foundation import foundation_scripts

    sys.path.insert(0, str(foundation_scripts(SCRIPTS)))
    from pending_store import add_pending, close_pending

    pid = add_pending(
        PROJECT_DIR,
        {
            "step": "步骤4",
            "project_code": "SAMPLE",
            "package_name": PKG_NAME,
            "fields": {"payment_source": "邮件指示"},
            "archive_plan": [],
            "reason": "demo_payment_source",
        },
        skill="po-flow",
    )
    close_pending(PROJECT_DIR, pid, skill="po-flow")

    print("\nE2E demo complete:", PROJECT_DIR)
    from common import load_tracker_packages
    print("Tracker packages:", len(load_tracker_packages(PROJECT_DIR)))


if __name__ == "__main__":
    main()
