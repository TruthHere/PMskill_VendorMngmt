#!/usr/bin/env python3
"""Resolve the payment-sheet Excel template + profile for a project.

No project template → not enabled. Never fall back to any bundled sample workbook.
"""

from __future__ import annotations

import json
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]

DISABLED_NOTICE = "还没有请款单模板，请款单生成尚未启用。把客户标准请款单（.xlsx）给我认模板之后才能出填写页。"


def find_project_root(start: Path | None) -> Path | None:
    if start is None:
        return None
    cur = start.expanduser().resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".skill").is_dir():
            return p
    return None


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def default_profile() -> dict:
    return {"id": "cells", "engine": "cells", "title": "请款单", "writes": [], "form": {"user_fields": []}}


def resolve_assets(project_root: Path | None) -> tuple[Path | None, dict | None, Path | None]:
    """Return (xlsx_path, profile, profile_path). All None if this project has no template."""
    if project_root is None:
        return None, None, None
    root = project_root.expanduser().resolve()
    folder = root / ".skill" / "payment-sheet"
    xlsx = folder / "template.xlsx"
    profile_path = folder / "template-profile.json"
    project = load_json(root / ".skill" / "project.json")
    cfg = project.get("payment_form") if isinstance(project.get("payment_form"), dict) else {}
    if cfg.get("template"):
        cand = (root / str(cfg["template"])).resolve()
        if cand.is_file():
            xlsx = cand
    if cfg.get("profile"):
        cand_p = (root / str(cfg["profile"])).resolve()
        if cand_p.is_file():
            profile_path = cand_p
    if not xlsx.is_file():
        return None, None, None
    if profile_path.is_file():
        profile = load_json(profile_path)
        engine = str(profile.get("engine") or "").strip()
        if not engine:
            profile["engine"] = "cells"
        elif engine != "cells":
            profile["engine"] = "insert_rows"
        return xlsx, profile, profile_path
    stub = {
        "id": "project-draft",
        "engine": "cells",
        "title": "请款单",
        "status": "draft",
        "form": {"user_fields": []},
        "writes": [],
        "notes": "已有模板文件，但还没有对照表。请先跑认模板步骤补 template-profile.json。",
    }
    return xlsx, stub, None


def payment_form_enabled(project_root: Path | None) -> bool:
    xlsx, _profile, _ = resolve_assets(project_root)
    return bool(xlsx and xlsx.is_file())
