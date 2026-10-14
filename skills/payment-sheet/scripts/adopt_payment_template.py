#!/usr/bin/env python3
"""Adopt a client's payment application xlsx into a project.

Copies the file into `{project}/.skill/payment-sheet/template.xlsx`,
writes an inspect dump, optionally installs a confirmed profile,
and points project.json at them.

Does not invent a mapping. Agent drafts template-profile.json after reading
the inspect dump, then re-runs with --profile once the user confirms.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from xlsx_inspect import inspect_markdown, inspect_xlsx, require_xlsx  # noqa: E402


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def adopt(
    xlsx: Path,
    project_root: Path,
    *,
    profile_path: Path | None = None,
    title: str = "",
) -> dict:
    project_root = project_root.expanduser().resolve()
    xlsx = xlsx.expanduser().resolve()
    if not xlsx.is_file():
        raise FileNotFoundError(xlsx)
    require_xlsx(xlsx)
    dest_dir = project_root / ".skill" / "payment-sheet"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_xlsx = dest_dir / "template.xlsx"
    shutil.copy2(xlsx, dest_xlsx)

    dest_profile = dest_dir / "template-profile.json"
    if profile_path and profile_path.expanduser().is_file():
        shutil.copy2(profile_path.expanduser().resolve(), dest_profile)
        profile = _load_json(dest_profile)
        status = "profile_installed"
    elif dest_profile.is_file():
        profile = _load_json(dest_profile)
        status = "profile_kept"
    else:
        profile = {
            "id": "project",
            "engine": "cells",
            "title": title or "请款单",
            "title_en": "Payment Application",
            "download_label": "下载请款单（Excel）",
            "vendor_section_title": "请款单抬头（供应商填）",
            "drop_sheets": [],
            "form": {"show_includes_variations": True, "user_fields": []},
            "writes": [],
            "status": "draft",
            "notes": "草稿：对照 template-inspect.md 填 writes / user_fields 后，再让用户确认。",
        }
        if title:
            profile["title"] = title
        dest_profile.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        status = "draft_profile"

    clear_addrs = [str(a) for a in (profile.get("clear_on_adopt") or []) if a]
    if clear_addrs:
        from patch_xlsx import clear_cells_keep_layout

        clear_cells_keep_layout(
            dest_xlsx,
            clear_addrs,
            sheet_name=str(profile.get("invoice_sheet") or ""),
        )

    inspected = inspect_xlsx(dest_xlsx)
    inspect_json = dest_dir / "template-inspect.json"
    inspect_md = dest_dir / "template-inspect.md"
    inspect_json.write_text(json.dumps(inspected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    inspect_md.write_text(inspect_markdown(inspected), encoding="utf-8")

    project_json = project_root / ".skill" / "project.json"
    project = _load_json(project_json)
    project["payment_form"] = {
        "template": ".skill/payment-sheet/template.xlsx",
        "profile": ".skill/payment-sheet/template-profile.json",
    }
    if project_json.parent.is_dir():
        project_json.write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "status": status,
        "template": str(dest_xlsx),
        "profile": str(dest_profile),
        "inspect_md": str(inspect_md),
        "inspect_json": str(inspect_json),
        "title": profile.get("title") or title,
        "engine": profile.get("engine") or "cells",
        "sheet_names": [s.get("name") for s in inspected.get("sheets") or []],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xlsx", required=True, help="客户标准请款单（仅 .xlsx）")
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--profile", default="", help="已确认的 template-profile.json；没有则写草稿")
    ap.add_argument("--title", default="", help="填写页标题，如「XX 请款单」")
    args = ap.parse_args()
    info = adopt(
        Path(args.xlsx),
        Path(args.project_root),
        profile_path=Path(args.profile) if args.profile else None,
        title=args.title,
    )
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
