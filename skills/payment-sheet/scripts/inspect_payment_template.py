#!/usr/bin/env python3
"""CLI: inspect a client payment application xlsx (sheets / labels / formulas)."""

from __future__ import annotations

import argparse
from pathlib import Path

from xlsx_inspect import inspect_markdown, inspect_xlsx
import json


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-md", default="")
    args = ap.parse_args()
    data = inspect_xlsx(Path(args.xlsx))
    if args.out_json:
        Path(args.out_json).expanduser().write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.out_md:
        Path(args.out_md).expanduser().write_text(inspect_markdown(data), encoding="utf-8")
    if not args.out_json and not args.out_md:
        print(inspect_markdown(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
