#!/usr/bin/env python3
"""Shared eval/demo fixture constants (fictional BMS package — not real suppliers)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG_NAME = "BMS"
SUPPLIER = "BOSCH Building Technologies"
SUPPLIER_SHORT = "BOSCH"
CONTACT_EMAIL = "procurement@bosch-build.example.com"
PKG_TYPE = "供应"

_SCRIPTS = Path(__file__).resolve().parent
_FC_SCRIPTS = _SCRIPTS.parent.parent / "fulfillment-card" / "scripts"


def package_dir(project_root: Path) -> Path:
    """Resolve package folder from tracker; fallback to canonical naming."""
    from common import load_tracker_packages, package_folder_name

    packages = load_tracker_packages(project_root)
    for pkg in packages:
        folder = (pkg.get("folder_path") or "").strip()
        if folder:
            return Path(folder)
    return project_root / package_folder_name(1, PKG_NAME, SUPPLIER_SHORT)


def run_render_card(*args: str) -> None:
    """Run fulfillment-card render (includes 请款申请.html)."""
    cmd = [sys.executable, str(_FC_SCRIPTS / "render_card.py"), *args]
    print(">", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(_FC_SCRIPTS))
