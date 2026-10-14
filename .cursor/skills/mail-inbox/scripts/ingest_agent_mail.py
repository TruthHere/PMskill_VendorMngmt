#!/usr/bin/env python3
"""Ingest agent-mail JSON drop → .eml → dispatch_mail; track processed_msg_ids.

WorkBuddy / Agent responsibility (MCP): ListMessages / GetMessage / download attachments,
write JSON under `.skill/inbox/agent_mail/` (and attachment files).

This script (mail-inbox): JSON → RFC822 .eml → classify/dispatch → update mailbox_state.
IMAP poll_mailbox.py remains for source=imap projects.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
SKILLS = SCRIPTS.parents[1]
FULFILLMENT_SCRIPTS = SKILLS / "po-flow" / "scripts"
for path in (SCRIPTS, FULFILLMENT_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_eml_from_agent_mail import (  # noqa: E402
    load_message_json,
    message_id_of,
    normalize_payload,
    write_eml,
)
from common import (  # noqa: E402
    MAILBOX_STATE_JSON,
    PROJECT_JSON,
    ensure_inbox_dirs,
    load_json,
    now_iso,
    save_json,
    system_file,
)
from dispatch_mail import dispatch_eml_file  # noqa: E402


def safe_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/:*?"<>|\s]+', "_", (text or "").strip())
    return (text[:max_len] or "mail").strip("_")


def load_state(project_root: Path) -> dict[str, Any]:
    state = load_json(
        system_file(project_root, MAILBOX_STATE_JSON),
        {"processed_uids": [], "processed_msg_ids": []},
    ) or {}
    state.setdefault("processed_uids", [])
    state.setdefault("processed_msg_ids", [])
    return state


def save_state(project_root: Path, state: dict[str, Any]) -> None:
    state["last_ingest_at"] = now_iso()
    save_json(system_file(project_root, MAILBOX_STATE_JSON), state)


def collect_json_paths(project_root: Path, explicit: list[str]) -> list[Path]:
    if explicit:
        return [Path(p).expanduser().resolve() for p in explicit]
    drop = system_file(project_root, "inbox") / "agent_mail"
    drop.mkdir(parents=True, exist_ok=True)
    return sorted(drop.glob("*.json"))


def resolve_attachment_paths(
    payload: dict[str, Any],
    *,
    json_path: Path,
    extra_attachments: list[str],
) -> dict[str, Any]:
    """Return a copy of payload with attachment paths filled/merged."""
    data = dict(payload)
    atts = list(data.get("attachments") or [])
    if not isinstance(atts, list):
        atts = []
    # Merge CLI --attachment paths not already listed
    known = {str(a.get("path") or "") for a in atts if isinstance(a, dict)}
    for path_s in extra_attachments:
        p = Path(path_s).expanduser().resolve()
        if str(p) not in known:
            atts.append({"filename": p.name, "path": str(p)})
    # Resolve relative paths next to the JSON file
    fixed: list[dict[str, Any]] = []
    for item in atts:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        path_s = str(item.get("path") or item.get("local_path") or "").strip()
        if path_s:
            path = Path(path_s).expanduser()
            if not path.is_file():
                cand = (json_path.parent / path_s).resolve()
                if cand.is_file():
                    path = cand
                elif not path.is_absolute():
                    cand2 = (json_path.parent / path.name).resolve()
                    if cand2.is_file():
                        path = cand2
            item["path"] = str(path)
        fixed.append(item)
    data["attachments"] = fixed
    return data


def ingest_one(
    project_root: Path,
    json_path: Path,
    *,
    force: bool = False,
    classify_only: bool = False,
    process: bool = True,
    extra_attachments: list[str] | None = None,
) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    json_path = json_path.expanduser().resolve()
    ensure_inbox_dirs(project_root)

    payload = load_message_json(json_path)
    payload = resolve_attachment_paths(
        payload,
        json_path=json_path,
        extra_attachments=extra_attachments or [],
    )
    norm = normalize_payload(payload)
    msg_id = norm["message_id"] or f"file_{json_path.stem}"

    state = load_state(project_root)
    processed = {str(x) for x in state.get("processed_msg_ids") or []}
    if msg_id in processed and not force:
        return {
            "ok": True,
            "skipped": True,
            "reason": "already_processed",
            "message_id": msg_id,
            "json_path": str(json_path),
        }

    stamp = now_iso().replace(":", "").replace("+", "")
    base = f"{stamp}_{safe_filename(norm['subject'])}_{safe_filename(msg_id, 40)}"
    inbox = system_file(project_root, "inbox")
    eml_path = inbox / "raw" / f"{base}.eml"
    write_eml(payload, eml_path, attachment_root=json_path.parent)

    # Copy referenced attachments into inbox/attachments/<base>/ for traceability
    att_dir = inbox / "attachments" / base
    att_dir.mkdir(parents=True, exist_ok=True)
    saved_atts: list[str] = []
    for item in norm["attachments"]:
        src_s = item.get("path") or ""
        if not src_s:
            continue
        src = Path(src_s)
        # re-resolve after write_eml may have used relative paths from payload
        if not src.is_file():
            for a in payload.get("attachments") or []:
                if isinstance(a, dict) and (a.get("filename") == item.get("filename") or a.get("path")):
                    cand = Path(str(a.get("path") or ""))
                    if cand.is_file():
                        src = cand
                        break
        if not src.is_file():
            continue
        dest = att_dir / (item.get("filename") or src.name)
        dest.write_bytes(src.read_bytes())
        saved_atts.append(str(dest))

    # Persist normalized drop copy next to processed outputs
    drop_copy = inbox / "agent_mail" / f"{safe_filename(msg_id, 60)}.json"
    if json_path.resolve() != drop_copy.resolve():
        drop_copy.parent.mkdir(parents=True, exist_ok=True)
        drop_copy.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    item: dict[str, Any] = {
        "ok": True,
        "message_id": msg_id,
        "json_path": str(json_path),
        "eml_path": str(eml_path),
        "attachments": saved_atts,
        "subject": norm["subject"],
        "ingested_at": now_iso(),
        "source": "agent_mail",
    }

    if not process:
        save_json(inbox / "processed" / f"{base}.fetched.json", item)
        processed.add(msg_id)
        state["processed_msg_ids"] = sorted(processed)
        save_state(project_root, state)
        item["fetched_only"] = True
        return item

    try:
        if classify_only:
            from dispatch_mail import classify_eml

            proc = classify_eml(project_root, eml_path, saved_atts or None)
        else:
            proc = dispatch_eml_file(project_root, eml_path, attachment_paths=saved_atts or None)
        item["process"] = proc
        save_json(inbox / "processed" / f"{base}.json", {**item, **(proc if isinstance(proc, dict) else {})})
    except Exception as exc:
        item["ok"] = False
        item["error"] = str(exc)
        save_json(inbox / "failed" / f"{base}.json", item)
        # Still mark processed to avoid tight retry loops; use --force to retry
        processed.add(msg_id)
        state["processed_msg_ids"] = sorted(processed)
        save_state(project_root, state)
        return item

    processed.add(msg_id)
    state["processed_msg_ids"] = sorted(processed)
    save_state(project_root, state)
    return item


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument(
        "--message-json",
        action="append",
        default=[],
        help="One JSON file (repeatable). Default: all *.json under .skill/inbox/agent_mail/",
    )
    ap.add_argument("--attachment", action="append", default=[], help="Extra attachment path")
    ap.add_argument("--force", action="store_true", help="Reprocess even if message_id seen")
    ap.add_argument("--classify-only", action="store_true")
    ap.add_argument("--no-process", action="store_true", help="Only build .eml, do not dispatch")
    args = ap.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    if not system_file(root, PROJECT_JSON).is_file():
        print(json.dumps({"ok": False, "error": f"missing {PROJECT_JSON} in {root}"}, ensure_ascii=False))
        return 1

    # Optional hint in project.json — does not block ingest
    project = load_json(system_file(root, PROJECT_JSON), {}) or {}
    mailbox = project.get("mailbox") or {}
    source = str(mailbox.get("source") or "").strip().lower()

    paths = collect_json_paths(root, args.message_json)
    results = []
    for jp in paths:
        results.append(
            ingest_one(
                root,
                jp,
                force=args.force,
                classify_only=args.classify_only,
                process=not args.no_process,
                extra_attachments=args.attachment or [],
            )
        )

    out = {
        "ok": True,
        "project_root": str(root),
        "mailbox_source_hint": source or "unspecified",
        "processed": len([r for r in results if not r.get("skipped")]),
        "skipped": len([r for r in results if r.get("skipped")]),
        "results": results,
        "did": ["ingest_agent_mail"],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if all(r.get("ok", True) for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
