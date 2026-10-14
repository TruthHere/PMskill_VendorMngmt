#!/usr/bin/env python3
"""Sync timeline after a procurement package is added (agent-led safe).

Default: re-render the single project timeline from existing schedule.json
critical_nodes (human path + .skill copy). Does NOT write into 采购包目录.
Does NOT re-run dictionary analyze (would overwrite Agent reasoning).

Optional --draft-analyze: only when critical_nodes empty and a schedule source
exists; output is a draft that Agent must review — never treat as final merge.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent


def analyze_script() -> Path:
    return SCRIPTS / "analyze_schedule.py"


def render_timeline_script() -> Path:
    return SCRIPTS / "render_timeline.py"


def has_schedule_source(project_root: Path) -> bool:
    """True if progress files or an existing schedule.json with milestones exist."""
    root = project_root.expanduser().resolve()
    schedule_json = root / ".skill" / "schedule.json"
    if schedule_json.is_file():
        try:
            data = json.loads(schedule_json.read_text(encoding="utf-8"))
            if data.get("milestones") or data.get("critical_nodes") or data.get("source_file"):
                return True
        except json.JSONDecodeError:
            pass
    plan_dir = root / "项目档案" / "00_进度计划"
    if plan_dir.is_dir():
        for p in plan_dir.iterdir():
            if p.suffix.lower() in {".csv", ".xlsx", ".xlsm"} and p.is_file():
                return True
    return False


def load_schedule(project_root: Path) -> dict[str, Any]:
    path = project_root / ".skill" / "schedule.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _render_only(
    project_root: Path,
    *,
    package_name: str = "",
) -> dict[str, Any]:
    script = render_timeline_script()
    if not script.is_file():
        return {"ok": False, "error": "render_timeline_missing"}

    cmd = [
        sys.executable,
        str(script),
        "--project-root",
        str(project_root),
    ]
    if package_name:
        # Highlight only; still writes full project timeline (no package-dir file)
        cmd.extend(["--package", package_name])

    proc = subprocess.run(
        cmd, capture_output=True, text=True, check=False, cwd=str(script.parent)
    )
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or proc.stdout or "").strip()[:500]}

    return {
        "ok": True,
        "mode": "render_existing",
        "project_timeline": proc.stdout.strip(),
        "note": (
            "Rewrote 项目档案/00_进度计划/关键节点时间线.html + .skill/critical_nodes_timeline.html only. "
            "Does not write under 采购包目录."
        ),
    }


def _draft_analyze(project_root: Path) -> dict[str, Any]:
    script = analyze_script()
    if not script.is_file():
        return {"ok": False, "skipped": "analyze_schedule_missing", "path": str(script)}

    cmd = [
        sys.executable,
        str(script),
        "--project-root",
        str(project_root),
        "--write-md",
        "--write-timeline",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(script.parent),
        )
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()[
                :800
            ],
        }

    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"raw": proc.stdout.strip()[:800]}

    return {
        "ok": True,
        "mode": "draft_analyze",
        "note": (
            "Dictionary draft only — Agent must review; "
            "do NOT use as final overwrite of existing 总包 nodes. "
            "Prefer write_critical_nodes.py --merge-package after Agent inference."
        ),
        "analyze": payload,
    }


def sync_schedule_timeline_after_package(
    project_root: Path,
    *,
    package_name: str,
    package_dir: Path | None = None,
    draft_analyze: bool = False,
) -> dict[str, Any]:
    """
    Soft-fail sync after add-package.

    Prefer rendering existing agent critical_nodes onto the single project timeline.
    package_dir is accepted for API compatibility but never used for output.
    """
    root = project_root.expanduser().resolve()
    if not has_schedule_source(root):
        return {
            "ok": False,
            "skipped": "no_schedule_source",
            "hint": "阶段 0 / critical-nodes 产出进度基座后再录入采购包，将自动生成时间线",
        }

    schedule = load_schedule(root)
    nodes = schedule.get("critical_nodes") or []
    has_nodes = isinstance(nodes, list) and len(nodes) > 0

    ignored_dir = str(package_dir) if package_dir else None

    if has_nodes:
        result = _render_only(root, package_name=package_name)
        if result.get("ok"):
            result["critical_node_count"] = len(nodes)
            result["analysis_mode"] = schedule.get("analysis_mode") or "existing"
            result["package_name"] = package_name
            if ignored_dir:
                result["package_dir_ignored"] = ignored_dir
        return result

    if draft_analyze:
        out = _draft_analyze(root)
        if ignored_dir:
            out["package_dir_ignored"] = ignored_dir
        return out

    return {
        "ok": False,
        "skipped": "no_critical_nodes",
        "hint": (
            "尚无 critical_nodes。请按 critical-nodes（Agent 主导）只推该包节点，"
            "经 write_critical_nodes.py --merge-package 落盘并 --write-timeline；"
            "禁止用 analyze_schedule 字典草稿当定稿整盘覆盖。"
        ),
        "package_name": package_name,
        "package_dir_ignored": ignored_dir,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync project timeline after package add (no package-dir HTML)"
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--package-name", required=True)
    parser.add_argument(
        "--package-dir",
        default=None,
        help="Ignored (API compat). Timeline is never written into 采购包目录.",
    )
    parser.add_argument(
        "--draft-analyze",
        action="store_true",
        help="If critical_nodes empty, run analyze_schedule as draft (Agent must review)",
    )
    args = parser.parse_args()
    result = sync_schedule_timeline_after_package(
        Path(args.project_root),
        package_name=args.package_name,
        package_dir=Path(args.package_dir) if args.package_dir else None,
        draft_analyze=args.draft_analyze,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") or result.get("skipped") else 1)


if __name__ == "__main__":
    main()
