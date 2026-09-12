#!/usr/bin/env python3
"""Check whether cashflow source ledgers changed; optionally rebuild the workbook."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS.parent
_CURSOR = _SKILL_ROOT.parents[1]
_FOUNDATION = _CURSOR / "lib" / "project-foundation" / "scripts"
for _p in (_SCRIPTS, _FOUNDATION):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from forecast_sources import collect_forecast_sources, compare_sources  # noqa: E402


def _load_snapshot(project_root: Path) -> list[dict]:
    path = project_root / ".skill" / "cashflow_forecast.json"
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    sources = doc.get("sources")
    return list(sources) if isinstance(sources, list) else []


def _notify(title: str, message: str) -> None:
    text = message.replace("\\", "\\\\").replace('"', "“")
    head = title.replace("\\", "\\\\").replace('"', "“")
    script = (
        f'display dialog "{text}" with title "{head}" '
        f'buttons {{"好"}} default button 1'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except OSError:
        print(f"{title}\n{message}")


def _human_report(changes: list[dict]) -> str:
    if not changes:
        return "台账没有新变化，这张现金流表还是新的。"
    lines = ["发现台账有更新："]
    for row in changes:
        label = row.get("label") or row.get("rel") or "文件"
        detail = row.get("detail") or row.get("status")
        lines.append(f"· {label} — {detail}")
    return "\n".join(lines)


def check(project_root: Path) -> dict:
    project_root = project_root.expanduser().resolve()
    snapshot = _load_snapshot(project_root)
    current = collect_forecast_sources(project_root)
    if not snapshot:
        return {
            "fresh": False,
            "reason": "no_snapshot",
            "changes": [{"label": "尚无快照", "detail": "还没生成过现金流表", "status": "added"}],
            "current": current,
        }
    changes = compare_sources(snapshot, current)
    return {
        "fresh": not changes,
        "reason": "ok" if not changes else "stale",
        "changes": changes,
        "current": current,
    }


def write_check_command(project_root: Path, python_bin: str) -> Path:
    project_root = project_root.expanduser().resolve()
    dest = project_root / "检查现金流台账.command"
    script = _SCRIPTS / "check_sources.py"
    body = f"""#!/bin/bash
cd {json.dumps(str(project_root))}
{json.dumps(python_bin)} {json.dumps(str(script))} \\
  --project-root {json.dumps(str(project_root))} \\
  --rebuild --notify
"""
    dest.write_text(body, encoding="utf-8")
    dest.chmod(dest.stat().st_mode | 0o111)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--rebuild", action="store_true", help="有更新则重算 Excel")
    ap.add_argument("--notify", action="store_true", help="用系统弹窗告诉结果")
    args = ap.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    result = check(root)
    report = _human_report(result["changes"])
    rebuilt = False
    rebuild_error = ""

    if args.rebuild and not result["fresh"]:
        from build_forecast import ForecastConfig, _parse_ymd, build_forecast, write_outputs
        from datetime import date

        try:
            doc = build_forecast(
                root,
                ForecastConfig(
                    as_of=date.today(),
                    horizon_months=18,
                    payment_lag_days=30,
                ),
            )
            write_outputs(root, doc)
            rebuilt = True
            report += "\n\n已按最新台账重算现金流表。请关掉旧表后重新打开 Excel。"
        except PermissionError:
            rebuild_error = "没法覆盖 Excel：请先关掉已打开的现金流表，再点一次。"
            report += "\n\n" + rebuild_error
        except Exception as exc:  # noqa: BLE001
            rebuild_error = str(exc)
            report += f"\n\n重算失败：{exc}"

    print(json.dumps({**result, "rebuilt": rebuilt, "report": report}, ensure_ascii=False, indent=2))
    if args.notify:
        title = "现金流 · 台账无更新" if result["fresh"] else "现金流 · 台账有更新"
        _notify(title, report)
    if rebuild_error and not rebuilt:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
