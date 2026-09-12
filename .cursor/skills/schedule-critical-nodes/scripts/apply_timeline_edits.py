#!/usr/bin/env python3
"""Apply PM timeline edits (downloaded schedule.json) back to the project.

Writes .skill/schedule.json and re-renders timeline HTML.
Does not refresh fulfillment cards by default (cards are one-shot for vendors).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
SKILLS_ROOT = SCRIPTS.parent.parent
FC_RENDER = SKILLS_ROOT / "fulfillment-card" / "scripts" / "render_card.py"

sys.path.insert(0, str(SCRIPTS))
from write_critical_nodes import run as write_nodes  # noqa: E402
from render_timeline import write_timeline  # noqa: E402


def _load_edited(path: Path) -> dict[str, Any]:
    data = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("edited JSON must be an object (full schedule.json)")
    if "critical_nodes" not in data:
        raise ValueError("edited JSON missing critical_nodes")
    return data


def _package_dirs(project_root: Path) -> list[Path]:
    root = project_root.expanduser().resolve()
    out: list[Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if (child / "card-data.json").is_file():
            out.append(child)
    return out


def _refresh_cards(project_root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if not FC_RENDER.is_file():
        return [{"ok": False, "error": "render_card.py missing"}]
    for pkg_dir in _package_dirs(project_root):
        cmd = [
            sys.executable,
            str(FC_RENDER),
            "--package-dir",
            str(pkg_dir),
            "--patch",
            "{}",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(FC_RENDER.parent),
        )
        entry: dict[str, Any] = {
            "package_dir": str(pkg_dir),
            "ok": proc.returncode == 0,
        }
        if proc.returncode == 0:
            try:
                entry["render"] = json.loads(proc.stdout.strip() or "{}")
            except json.JSONDecodeError:
                entry["raw"] = (proc.stdout or "")[:400]
        else:
            entry["error"] = (proc.stderr or proc.stdout or "")[:500]
        results.append(entry)
    return results


def apply_payload(
    project_root: Path,
    payload: dict[str, Any],
    *,
    refresh_cards: bool = False,
) -> dict[str, Any]:
    """Write edited schedule dict → schedule.json + timeline HTML."""
    root = project_root.expanduser().resolve()
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object (full schedule.json)")
    if "critical_nodes" not in payload:
        raise ValueError("payload missing critical_nodes")

    write_result = write_nodes(
        root,
        payload,
        source=None,
        packages=payload.get("packages")
        if isinstance(payload.get("packages"), list)
        else None,
        write_md=True,
        write_timeline=False,
        validate_only=False,
        strict=True,
    )
    if not write_result.get("ok"):
        return {"ok": False, "write": write_result}

    # Preserve milestones from edited file if write didn't refresh them
    schedule_path = root / ".skill" / "schedule.json"
    if schedule_path.is_file() and isinstance(payload.get("milestones"), list):
        doc = json.loads(schedule_path.read_text(encoding="utf-8"))
        if not doc.get("milestones"):
            doc["milestones"] = payload["milestones"]
            schedule_path.write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    timeline = write_timeline(root)
    cards: list[dict[str, Any]] | None = None
    if refresh_cards:
        cards = _refresh_cards(root)

    return {
        "ok": True,
        "write": write_result,
        "timeline": timeline,
        "cards_refreshed": cards,
        "card_count": len(cards or []),
        "hint": (
            "已写回 schedule.json、重渲时间线"
            + ("，并重渲履约卡片" if refresh_cards else "")
        ),
    }


def apply_edits(
    project_root: Path,
    edited_json: Path,
    *,
    refresh_cards: bool = False,
) -> dict[str, Any]:
    return apply_payload(
        project_root,
        _load_edited(edited_json),
        refresh_cards=refresh_cards,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply timeline-edited schedule.json → project (schedule + timeline)"
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--edited-json",
        required=True,
        help="Downloaded schedule.json from the editable timeline",
    )
    parser.add_argument(
        "--refresh-cards",
        action="store_true",
        help="Also re-render fulfillment cards that already have card-data.json (optional)",
    )
    args = parser.parse_args(argv)
    try:
        result = apply_edits(
            Path(args.project_root),
            Path(args.edited_json),
            refresh_cards=args.refresh_cards,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
