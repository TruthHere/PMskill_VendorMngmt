#!/usr/bin/env python3
"""Deprecated CLI wrapper → payment-sheet/scripts/sync_claim_form.py.

Also re-exports sync_claim_form() so `python render_card.py` cannot pick up
this file as the real module (same filename, script dir wins sys.path).
"""

from __future__ import annotations

import sys
from pathlib import Path

from _foundation import load_skill_module

_REAL = load_skill_module("payment-sheet", "sync_claim_form", Path(__file__))
sync_claim_form = _REAL.sync_claim_form


def main() -> int:
    print(
        "warn: use payment-sheet/scripts/sync_claim_form.py "
        "(vendor-card wrapper)",
        file=sys.stderr,
    )
    return int(_REAL.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
