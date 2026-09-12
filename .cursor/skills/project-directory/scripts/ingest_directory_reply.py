#!/usr/bin/env python3
"""Ingest Project Directory replies from group chat paste or fill-form JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from directory_store import (  # noqa: E402
    add_directory_pending,
    extract_package_hints,
    load_store,
    match_package,
    now_iso,
    parse_contact_blocks,
    project_meta,
    request_for,
    save_store,
    split_pdir_sections,
    upsert_contacts,
    upsert_request,
)
from write_directory_xlsx import write_directory_xlsx  # noqa: E402


def _contacts_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and payload.get("contacts"):
        return [
            {
                "package_name": str(payload.get("package_name") or ""),
                "supplier_name": str(payload.get("supplier_name") or payload.get("supplier_hint") or ""),
                "name": str(c.get("name") or ""),
                "title": str(c.get("title") or ""),
                "phone": str(c.get("phone") or ""),
                "email": str(c.get("email") or "").lower(),
            }
            for c in payload.get("contacts") or []
            if isinstance(c, dict)
        ]
    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            rows.extend(_contacts_from_payload(item))
        return rows
    return []


def _apply_rows(
    *,
    meta: dict[str, Any],
    store: dict[str, Any],
    package_name: str,
    supplier_hint: str,
    people: list[dict[str, str]],
    source: str,
) -> dict[str, Any]:
    pkg = match_package(
        meta["packages"],
        package_name=package_name,
        supplier_hint=supplier_hint,
    )
    if pkg is None and len(meta["packages"]) == 1:
        pkg = meta["packages"][0]
    if pkg is None:
        pid = add_directory_pending(
            meta["root"],
            {
                "step": "directory.reply",
                "fields": {"package_name": package_name, "supplier_hint": supplier_hint},
                "reason": "package_ambiguous",
                "note": "群回复对不上采购包。告诉我是哪一家。",
            },
        )
        return {
            "ok": False,
            "pending_id": pid,
            "reason": "package_ambiguous",
            "package_name": package_name,
        }

    usable = [c for c in people if c.get("name") or c.get("email")]
    if not usable:
        pid = add_directory_pending(
            meta["root"],
            {
                "step": "directory.reply",
                "fields": {"package_name": pkg.get("package_name")},
                "reason": "directory_parse_failed",
                "note": "这段回复里没有抽出姓名/邮箱。让对方按模板再回一条，或把信息贴给我。",
            },
        )
        return {
            "ok": False,
            "pending_id": pid,
            "reason": "directory_parse_failed",
            "package_name": pkg.get("package_name"),
        }

    now = now_iso()
    rows = []
    for person in usable:
        rows.append(
            {
                "package_name": pkg.get("package_name") or "",
                "supplier_name": pkg.get("supplier_name") or pkg.get("supplier_short") or "",
                "seq": pkg.get("seq") or "",
                "name": person.get("name") or "",
                "title": person.get("title") or "",
                "phone": person.get("phone") or "",
                "email": person.get("email") or "",
                "source": source,
                "updated_at": now,
            }
        )
    wrote = upsert_contacts(store, str(pkg.get("package_name") or ""), rows)
    existing = request_for(store, str(pkg.get("package_name") or "")) or {}
    upsert_request(
        store,
        {
            **existing,
            "package_name": pkg.get("package_name") or "",
            "supplier_name": pkg.get("supplier_name") or existing.get("supplier_name") or "",
            "supplier_short": pkg.get("supplier_short") or existing.get("supplier_short") or "",
            "seq": pkg.get("seq") or existing.get("seq") or "",
            "status": "replied",
            "replied_at": now,
            "channel": "wecom_group",
            "error": "",
        },
    )
    return {
        "ok": True,
        "package_name": pkg.get("package_name"),
        "contacts_written": wrote,
        "contacts": rows,
    }


def ingest_directory_reply(
    project_root: Path,
    *,
    text: str = "",
    json_payload: Any = None,
    source: str = "group",
) -> dict[str, Any]:
    meta = project_meta(project_root)
    store = load_store(meta["root"])
    store["project_name"] = meta["project_name"]
    results: list[dict[str, Any]] = []

    if json_payload is not None:
        grouped: dict[str, list[dict[str, str]]] = {}
        supplier_by_pkg: dict[str, str] = {}
        for row in _contacts_from_payload(json_payload):
            key = str(row.get("package_name") or "")
            grouped.setdefault(key, []).append(
                {
                    "name": row.get("name") or "",
                    "title": row.get("title") or "",
                    "phone": row.get("phone") or "",
                    "email": row.get("email") or "",
                }
            )
            if row.get("supplier_name"):
                supplier_by_pkg[key] = str(row.get("supplier_name") or "")
        if not grouped:
            pid = add_directory_pending(
                meta["root"],
                {
                    "step": "directory.reply",
                    "reason": "directory_parse_failed",
                    "note": "填写页回执是空的。",
                },
            )
            return {"ok": False, "auto": False, "pending_id": pid, "reason": "directory_parse_failed"}
        for pkg_name, people in grouped.items():
            results.append(
                _apply_rows(
                    meta=meta,
                    store=store,
                    package_name=pkg_name,
                    supplier_hint=supplier_by_pkg.get(pkg_name, ""),
                    people=people,
                    source="fill_form",
                )
            )
    else:
        sections = split_pdir_sections(text)
        if not sections:
            pid = add_directory_pending(
                meta["root"],
                {
                    "step": "directory.reply",
                    "reason": "directory_parse_failed",
                    "note": "这段群消息里没有通讯录格式。把对方按模板回的那几条贴给我。",
                },
            )
            return {"ok": False, "auto": False, "pending_id": pid, "reason": "directory_parse_failed"}
        for section in sections:
            hints = extract_package_hints("", section)
            results.append(
                _apply_rows(
                    meta=meta,
                    store=store,
                    package_name=hints.get("package_name") or "",
                    supplier_hint=hints.get("supplier_hint") or "",
                    people=parse_contact_blocks(section),
                    source=source,
                )
            )

    save_store(meta["root"], store)
    xlsx = str(write_directory_xlsx(meta["root"], store))
    ok_n = sum(1 for r in results if r.get("ok"))
    pending = [r.get("pending_id") for r in results if r.get("pending_id")]
    wrote = sum(int(r.get("contacts_written") or 0) for r in results if r.get("ok"))
    return {
        "ok": ok_n > 0,
        "auto": ok_n > 0 and not pending,
        "did": ["directory.ingest"],
        "channel": "wecom_group",
        "xlsx_path": xlsx,
        "contacts_written": wrote,
        "pending_ids": pending,
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--text-file", default="")
    ap.add_argument("--json-file", default="")
    args = ap.parse_args()
    payload = None
    text = args.text
    if args.text_file:
        text = Path(args.text_file).expanduser().resolve().read_text(encoding="utf-8")
    if args.json_file:
        payload = json.loads(Path(args.json_file).expanduser().resolve().read_text(encoding="utf-8"))
    if not text and payload is None:
        raise SystemExit("需要 --text / --text-file / --json-file 其中之一")
    out = ingest_directory_reply(
        Path(args.project_root),
        text=text,
        json_payload=payload,
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
