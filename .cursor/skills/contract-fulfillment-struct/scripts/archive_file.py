#!/usr/bin/env python3
"""Archive files with standard naming into package or project subfolders."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from common import CST, sanitize_segment


def archive_file(
    *,
    source: Path,
    dest_dir: Path,
    package_name: str,
    file_type: str,
    description: str,
    version: str = "v1",
    date: str | None = None,
) -> Path:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    dest_dir = dest_dir.expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    date_str = date or datetime.now(CST).strftime("%Y%m%d")
    ext = source.suffix or ""
    filename = (
        f"{sanitize_segment(package_name, 30)}_"
        f"{sanitize_segment(file_type, 10)}_"
        f"{date_str}_"
        f"{sanitize_segment(version, 8)}_"
        f"{sanitize_segment(description, 10)}"
        f"{ext}"
    )
    target = dest_dir / filename
    shutil.copy2(source, target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive file with standard naming")
    parser.add_argument("--source", required=True, help="Source file path")
    parser.add_argument("--file-type", required=True, help="File type label")
    parser.add_argument("--package-name", required=True, help="Package name for filename")
    parser.add_argument("--description", required=True, help="Brief description (<=10 chars)")
    parser.add_argument("--version", default="v1", help="Version tag")
    parser.add_argument("--date", default=None, help="Date YYYYMMDD")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--package-dir", help="Package folder; use with --dest-subdir")
    group.add_argument("--project-root", help="Project root; use with --dest-subdir")

    parser.add_argument(
        "--dest-subdir",
        required=True,
        help="Subfolder relative to package-dir or project-root, e.g. 02_图纸 or _项目档案/00_进度计划",
    )
    args = parser.parse_args()

    if args.package_dir:
        dest = Path(args.package_dir) / args.dest_subdir
    else:
        dest = Path(args.project_root) / args.dest_subdir

    target = archive_file(
        source=Path(args.source),
        dest_dir=dest,
        package_name=args.package_name,
        file_type=args.file_type,
        description=args.description,
        version=args.version,
        date=args.date,
    )
    print(json.dumps({"archived_to": str(target)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
