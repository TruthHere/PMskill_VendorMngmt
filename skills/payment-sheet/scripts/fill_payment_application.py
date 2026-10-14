#!/usr/bin/env python3
"""Fill a project-adopted payment application xlsx from form response JSON.

Owned by payment-sheet. Writes Excel only; does not touch ledger or Tracker.
Patches the company template ZIP so layout stays 1:1.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from patch_insert_xlsx import patch_file as patch_insert_rows
from patch_xlsx import patch_file as patch_cells
from template_profile import DISABLED_NOTICE, resolve_assets

SKILL_ROOT = Path(__file__).resolve().parents[1]


def _project_root(package_dir: Path | None) -> Path | None:
    if package_dir is None:
        return None
    cur = package_dir.resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".skill").is_dir():
            return p
    return None


def fill(response: dict, out_path: Path, *, package_dir: Path | None = None) -> Path:
    root = _project_root(package_dir)
    template, profile, _ = resolve_assets(root)
    if template is None or not template.is_file() or profile is None:
        raise RuntimeError(DISABLED_NOTICE)
    engine = profile.get("engine") or "cells"
    if engine == "cells":
        return patch_cells(template, response, out_path, profile)
    return patch_insert_rows(template, response, out_path)


def default_out_name(response: dict, package_dir: Path | None = None) -> str:
    n = int(response.get("payment_no") or 1)
    pkg = response.get("work_package") or (package_dir.name if package_dir else "package")
    pkg = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", str(pkg))[:40]
    return f"PAYMENT_NO_{n}_{pkg}_{date.today().isoformat()}.xlsx"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--response", required=True, help="claim_response.json")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--package-dir", default="")
    args = ap.parse_args()

    response = json.loads(Path(args.response).expanduser().read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir).expanduser().resolve()
    package_dir = Path(args.package_dir).expanduser().resolve() if args.package_dir else None

    if package_dir and (package_dir / "card-data.json").is_file():
        card = json.loads((package_dir / "card-data.json").read_text(encoding="utf-8"))
        response.setdefault("vendor_name", card.get("supplier_name"))
        response.setdefault("work_package", card.get("package_name"))
        response.setdefault("project_name", card.get("project_name"))

    out_path = out_dir / default_out_name(response, package_dir)
    fill(response, out_path, package_dir=package_dir)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
