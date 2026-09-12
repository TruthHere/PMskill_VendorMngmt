#!/usr/bin/env python3
"""CLI: MPP / Project XML / xlsx / csv → Project-view Excel + structured CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as script from any cwd
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from gantt_xlsx import write_project_view  # noqa: E402
from readers import read_schedule, resolve_gantt_unit  # noqa: E402
from structured_export import write_structured_csv, write_structured_xlsx  # noqa: E402

_FOUNDATION = Path(__file__).resolve().parents[3] / "lib" / "project-foundation" / "scripts"
if str(_FOUNDATION) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION))
from write_guard import assert_solo_output_allowed  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Convert schedule to Project-view Excel + structured CSV")
    p.add_argument("--source", required=True, help="输入 .mpp / .xml / .xlsx / .csv")
    p.add_argument("--out-dir", default="", help="输出目录（默认：源文件同目录）")
    p.add_argument("--gantt-unit", choices=["day", "week"], default="week")
    p.add_argument("--project-name", default="", help="写入表头的项目名")
    p.add_argument("--no-structured-xlsx", action="store_true", help="不写 *_schedule_structured.xlsx")
    p.add_argument("--stem", default="", help="输出文件名前缀（默认用源文件 stem）")
    args = p.parse_args(argv)

    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        print(f"找不到源文件: {source}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else source.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.stem.strip() or source.stem

    try:
        tasks = read_schedule(source)
    except Exception as e:
        print(f"读取失败: {e}", file=sys.stderr)
        return 2

    if not tasks:
        print("未解析到任何任务行", file=sys.stderr)
        return 3

    gantt_unit = resolve_gantt_unit(tasks, args.gantt_unit)
    if gantt_unit != args.gantt_unit:
        print(f"提示: 跨度较长，甘特粒度由 {args.gantt_unit} 改为 {gantt_unit}")

    view_path = out_dir / f"{stem}_project_view.xlsx"
    csv_path = out_dir / f"{stem}_schedule.csv"
    xlsx_path = out_dir / f"{stem}_schedule_structured.xlsx"
    for dest in (view_path, csv_path, xlsx_path):
        assert_solo_output_allowed(dest)

    write_project_view(
        tasks,
        view_path,
        source_name=source.name,
        project_name=args.project_name,
        gantt_unit=gantt_unit,
    )
    write_structured_csv(tasks, csv_path)
    if not args.no_structured_xlsx:
        write_structured_xlsx(tasks, xlsx_path)

    dated = [t for t in tasks if t.start or t.finish]
    print(f"任务行: {len(tasks)}（含日期 {len(dated)}）")
    print(f"Project 视图: {view_path}")
    print(f"机读 CSV:     {csv_path}")
    if not args.no_structured_xlsx:
        print(f"机读 xlsx:    {xlsx_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
