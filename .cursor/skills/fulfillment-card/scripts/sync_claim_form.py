#!/usr/bin/env python3
"""Deprecated wrapper → payment-form/scripts/sync_claim_form.py"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[2] / "payment-form" / "scripts" / "sync_claim_form.py"


def main() -> int:
    print(
        "warn: use .cursor/skills/payment-form/scripts/sync_claim_form.py "
        "(fulfillment-card wrapper)",
        file=sys.stderr,
    )
    sys.argv[0] = str(TARGET)
    runpy.run_path(str(TARGET), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
