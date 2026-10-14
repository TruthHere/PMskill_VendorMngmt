#!/usr/bin/env python3
"""Seed eval project roots for po-payment eval."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS.parent

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
    subprocess.run([sys.executable, str(SCRIPTS / script), *args], check=True, cwd=str(SCRIPTS))


def seed_po_project(root: Path) -> None:
    if root.exists():
        import shutil
        shutil.rmtree(root)
    run(
        "init_project.py",
        "--root", str(root),
        "--name", "Sample Project", "--code", "SAMPLE",
        "--type", "实验室",
        "--address", "上海市浦东新区张江路 100 号",
        "--client", "样例业主有限公司",
        "--pm", "张三", "--currency", "CNY 含税",
    )
    run(
        "update_tracker.py",
        "--project-root", str(root),
        "--action", "add-package",
        "--package-name", PKG_NAME,
        "--supplier", SUPPLIER,
        "--supplier-short", SUPPLIER_SHORT,
        "--contact-email", CONTACT_EMAIL,
        "--package-type", PKG_TYPE,
        "--milestone", "技术方案已确认",
    )
    pkg = package_dir(root)
    patch = json.dumps({"scope_summary": "楼宇自控系统供应与调试"}, ensure_ascii=False)
    run_render_card("--package-dir", str(pkg), "--patch", patch)


if __name__ == "__main__":
    seed_po_project(Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/eval-sample-po"))
