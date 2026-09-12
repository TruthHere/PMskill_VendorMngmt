#!/usr/bin/env python3
"""Import project schedule CSV into .skill/schedule.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schedule_csv import import_project_schedule_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Import project schedule CSV")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    parser.add_argument(
        "--source",
        default="",
        help="Schedule CSV path. Default: auto-detect under 项目档案/00_进度计划/",
    )
    args = parser.parse_args()

    source = Path(args.source) if args.source else None
    result = import_project_schedule_csv(Path(args.project_root), source)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
