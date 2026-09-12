#!/usr/bin/env python3
"""Generate payment application xlsx from claim_response.json.

Owned by payment-form. Writes the company Excel only — does not touch ledger / Tracker.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fill_payment_application import default_out_name, fill


def generate_payment_application(
    response: dict,
    out_dir: Path,
    *,
    package_dir: Path | None = None,
    filename: str = "",
) -> Path:
    out_dir = out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if filename:
        xlsx_path = out_dir / filename
    else:
        xlsx_path = out_dir / default_out_name(response, package_dir)
    fill(response, xlsx_path)
    return xlsx_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response", required=True, help="claim_response.json")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--package-dir", default="", help="Optional; only used for default filename")
    parser.add_argument("--filename", default="", help="Optional xlsx filename")
    args = parser.parse_args()

    response = json.loads(Path(args.response).expanduser().read_text(encoding="utf-8"))
    package_dir = Path(args.package_dir).expanduser().resolve() if args.package_dir else None
    xlsx_path = generate_payment_application(
        response,
        Path(args.out_dir),
        package_dir=package_dir,
        filename=args.filename,
    )
    print(f"xlsx={xlsx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
