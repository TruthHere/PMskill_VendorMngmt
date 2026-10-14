#!/usr/bin/env python3
"""IMAP poll: fetch unread mail, save .eml + attachments, then dispatch."""

from __future__ import annotations

import argparse
import email
import imaplib
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILLS = SCRIPTS.parents[1]
FULFILLMENT_SCRIPTS = SKILLS / "po-flow" / "scripts"
for path in (SCRIPTS, FULFILLMENT_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from classify_mail import decode_mime_header  # noqa: E402
from common import (  # noqa: E402
    MAILBOX_STATE_JSON,
    PROJECT_JSON,
    ensure_inbox_dirs,
    load_json,
    now_iso,
    read_mailbox_password,
    save_json,
    system_file,
)
from dispatch_mail import dispatch_eml_file  # noqa: E402


def safe_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[\\/:*?"<>|\s]+', "_", text.strip())
    return (text[:max_len] or "mail").strip("_")


def connect_imap(host: str, port: int, username: str, password: str) -> imaplib.IMAP4_SSL:
    """Connect and login. NetEase 163 requires IMAP ID while AUTH before SELECT."""
    imaplib.Commands["ID"] = ("AUTH",)

    client = imaplib.IMAP4_SSL(host, port)
    typ, data = client.login(username, password)
    if typ != "OK":
        raise RuntimeError(f"IMAP login failed: {typ} {data}")

    try:
        typ, data = client._simple_command(
            "ID",
            '("name" "PMskills" "version" "1.0" "vendor" "pmskills")',
        )
        client._untagged_response(typ, data, "ID")
    except Exception as exc:
        raise RuntimeError(f"IMAP ID failed (required for 163): {exc}") from exc

    return client


def select_inbox(client: imaplib.IMAP4_SSL) -> None:
    typ, data = client.select("INBOX")
    if typ == "OK":
        return
    for name in ("Inbox", "INBOX", "&g0l6P3ux-"):
        typ, data = client.select(name)
        if typ == "OK":
            return
    raise RuntimeError(f"SELECT inbox failed: {typ} {data}")


def poll_project(
    project_root: Path,
    *,
    mark_seen: bool = True,
    process: bool = True,
) -> dict:
    project_root = project_root.expanduser().resolve()
    project = load_json(system_file(project_root, PROJECT_JSON))
    if not project:
        raise FileNotFoundError(f"{PROJECT_JSON} missing in {project_root}")

    mailbox = project.get("mailbox") or {}
    address = mailbox.get("address") or ""
    host = mailbox.get("imap_host") or "imap.163.com"
    port = int(mailbox.get("imap_port") or 993)
    username = mailbox.get("username") or address
    if not address:
        raise ValueError("project.json has no mailbox.address")

    password = read_mailbox_password(project_root, project.get("project_code", ""))
    if not password:
        raise ValueError(
            "Mailbox password not found. Set PMSKILLS_MAIL_PASS or write .mailbox.secret"
        )

    ensure_inbox_dirs(project_root)
    inbox = system_file(project_root, "inbox")
    state_path = system_file(project_root, MAILBOX_STATE_JSON)
    state = load_json(state_path, {"processed_uids": [], "processed_msg_ids": []})
    processed = set(str(u) for u in state.get("processed_uids", []))
    # Keep agent-mail ids when IMAP poll rewrites state
    processed_msg_ids = list(state.get("processed_msg_ids") or [])

    client = connect_imap(host, port, username, password)
    select_inbox(client)
    typ, data = client.search(None, "UNSEEN")
    if typ != "OK":
        client.logout()
        raise RuntimeError(f"IMAP search failed: {typ} {data}")

    uids = data[0].split() if data and data[0] else []
    results = []

    for uid in uids:
        uid_s = uid.decode() if isinstance(uid, bytes) else str(uid)
        if uid_s in processed:
            continue

        typ, msg_data = client.fetch(uid, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1]
        if not isinstance(raw, (bytes, bytearray)):
            continue

        msg = email.message_from_bytes(raw)
        subject = decode_mime_header(msg.get("Subject"))
        stamp = now_iso().replace(":", "").replace("+", "")
        base = f"{stamp}_{safe_filename(subject)}_{uid_s}"
        eml_path = inbox / "raw" / f"{base}.eml"
        eml_path.write_bytes(raw)

        att_dir = inbox / "attachments" / base
        att_dir.mkdir(parents=True, exist_ok=True)
        saved_atts: list[str] = []
        for part in msg.walk():
            disposition = str(part.get("Content-Disposition") or "")
            filename = part.get_filename()
            if filename or "attachment" in disposition.lower():
                fname = decode_mime_header(filename) or "attachment.bin"
                fname = safe_filename(fname, 120)
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                out = att_dir / fname
                out.write_bytes(payload)
                saved_atts.append(str(out))

        item = {
            "uid": uid_s,
            "eml_path": str(eml_path),
            "subject": subject,
            "attachments": saved_atts,
            "fetched_at": now_iso(),
        }

        if process:
            try:
                proc = dispatch_eml_file(
                    project_root,
                    eml_path,
                    attachment_paths=saved_atts,
                )
                item["process"] = proc
                save_json(inbox / "processed" / f"{base}.json", {**item, **proc})
            except Exception as exc:
                item["error"] = str(exc)
                save_json(inbox / "failed" / f"{base}.json", item)
        else:
            save_json(inbox / "processed" / f"{base}.fetched.json", item)

        processed.add(uid_s)
        if mark_seen:
            client.store(uid, "+FLAGS", "\\Seen")
        results.append(item)

    state["processed_uids"] = sorted(processed)
    state["processed_msg_ids"] = processed_msg_ids
    state["last_poll_at"] = now_iso()
    save_json(state_path, state)
    client.logout()
    return {"fetched": len(results), "items": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll project mailbox for unread mail")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--no-process", action="store_true", help="Only fetch, do not process")
    parser.add_argument("--keep-unseen", action="store_true", help="Do not mark as Seen")
    args = parser.parse_args()
    try:
        result = poll_project(
            Path(args.project_root),
            mark_seen=not args.keep_unseen,
            process=not args.no_process,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
