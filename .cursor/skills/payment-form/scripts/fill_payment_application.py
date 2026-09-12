#!/usr/bin/env python3
"""Fill Apple Payment Application xlsx from form response JSON.

Owned by payment-form. Writes Excel only; does not touch ledger or Tracker.
Patches the company template ZIP so Invoice layout stays 1:1.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from patch_apple_xlsx import patch_file

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "Apple_Payment_Application.xlsx"


def fill(response: dict, out_path: Path) -> Path:
    if not TEMPLATE.is_file():
        raise FileNotFoundError(TEMPLATE)
    return patch_file(TEMPLATE, response, out_path)


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
    fill(response, out_path)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
