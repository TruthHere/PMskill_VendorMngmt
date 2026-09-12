#!/usr/bin/env python3
"""Fingerprints of ledgers the cashflow workbook depends on."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

CST = timezone(timedelta(hours=8))
_PKG_DIR = re.compile(r"^\d+_")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _mtime_iso(path: Path) -> str:
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=CST)
    return ts.strftime("%Y-%m-%d %H:%M")


def fingerprint(kind: str, label: str, path: Path, project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    path = path.expanduser().resolve()
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = path.name
    if not path.is_file():
        return {
            "kind": kind,
            "label": label,
            "path": str(path),
            "rel": rel,
            "missing": True,
            "mtime": "",
            "sha256": "",
        }
    return {
        "kind": kind,
        "label": label,
        "path": str(path),
        "rel": rel,
        "missing": False,
        "mtime": _mtime_iso(path),
        "sha256": _sha256(path),
    }


def collect_forecast_sources(project_root: Path) -> list[dict[str, Any]]:
    from common import resolve_change_log_path, resolve_tracker_path

    root = project_root.expanduser().resolve()
    out: list[dict[str, Any]] = []

    tracker = resolve_tracker_path(root)
    if tracker:
        out.append(fingerprint("tracker", "采购包 Tracker（CSV）", tracker, root))
        xlsx = tracker.with_suffix(".xlsx")
        if xlsx.is_file():
            out.append(fingerprint("tracker_xlsx", "采购包 Tracker（Excel）", xlsx, root))

    change_log = resolve_change_log_path(root)
    if change_log:
        out.append(fingerprint("change_log", "变更台账 Change Log", change_log, root))

    out.append(
        fingerprint("schedule", "进度关键节点", root / ".skill" / "schedule.json", root)
    )
    overrides = root / ".skill" / "cashflow_overrides.json"
    if overrides.is_file():
        out.append(fingerprint("overrides", "现金流人工覆盖", overrides, root))

    for pkg_dir in sorted(p for p in root.iterdir() if p.is_dir() and _PKG_DIR.match(p.name)):
        card = pkg_dir / "card-data.json"
        if card.is_file():
            out.append(
                fingerprint("card_data", f"{pkg_dir.name} 履约卡片数据", card, root)
            )
    return out


def compare_sources(
    snapshot: list[dict[str, Any]], current: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return rows that changed or went missing/appeared."""
    by_rel = {str(s.get("rel") or ""): s for s in snapshot if s.get("rel")}
    cur_by_rel = {str(s.get("rel") or ""): s for s in current if s.get("rel")}
    changes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel, old in by_rel.items():
        seen.add(rel)
        new = cur_by_rel.get(rel)
        if not new:
            changes.append({**old, "status": "removed", "detail": "文件不见了"})
            continue
        if old.get("missing") and not new.get("missing"):
            changes.append({**new, "status": "added", "detail": "新出现"})
            continue
        if new.get("missing") and not old.get("missing"):
            changes.append({**new, "status": "removed", "detail": "文件不见了"})
            continue
        if (old.get("sha256") or "") != (new.get("sha256") or ""):
            changes.append(
                {
                    **new,
                    "status": "updated",
                    "detail": f"有改动（生成时 {old.get('mtime') or '—'}）",
                }
            )
    for rel, new in cur_by_rel.items():
        if rel in seen:
            continue
        if new.get("missing"):
            continue
        changes.append({**new, "status": "added", "detail": "新出现"})
    return changes
