#!/usr/bin/env python3
"""Build a RFC822 .eml from agent-mail (or compatible) JSON.

Does not call MCP. WorkBuddy / Agent fetches mail via MCP, writes JSON (+ attachments),
then this script (or ingest_agent_mail.py) turns it into .eml for dispatch_mail.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, parseaddr
from pathlib import Path
from typing import Any


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                addr = item.get("address") or item.get("email") or item.get("addr") or ""
                name = item.get("name") or item.get("display_name") or ""
                if addr and name:
                    out.append(formataddr((str(name), str(addr))))
                elif addr:
                    out.append(str(addr))
            else:
                s = str(item).strip()
                if s:
                    out.append(s)
        return out
    return [str(value).strip()] if str(value).strip() else []


def _first_address(value: Any) -> str:
    items = _as_list(value)
    return items[0] if items else "unknown@localhost"


def message_id_of(payload: dict[str, Any]) -> str:
    for key in ("message_id", "msg_id", "id"):
        raw = payload.get(key)
        if raw:
            return str(raw).strip()
    return ""


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept common agent-mail / hand-written field aliases."""
    body = payload.get("body")
    if body is None:
        body = payload.get("body_text") or payload.get("text") or payload.get("content") or ""
    body_format = str(payload.get("body_format") or payload.get("content_type") or "text").lower()
    if "html" in body_format:
        body_format = "html"
    else:
        body_format = "text"

    attachments: list[dict[str, str]] = []
    for item in payload.get("attachments") or []:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or item.get("name") or "").strip()
        path = str(item.get("path") or item.get("local_path") or item.get("file") or "").strip()
        if filename or path:
            attachments.append({"filename": filename or Path(path).name, "path": path})

    return {
        "message_id": message_id_of(payload),
        "subject": str(payload.get("subject") or "(no subject)"),
        "from": _first_address(payload.get("from") or payload.get("from_address") or payload.get("sender")),
        "to": _as_list(payload.get("to") or payload.get("to_address")),
        "cc": _as_list(payload.get("cc") or payload.get("cc_address")),
        "date": payload.get("date") or payload.get("sent_at") or payload.get("received_at") or "",
        "body": str(body),
        "body_format": body_format,
        "attachments": attachments,
        "in_reply_to": str(payload.get("in_reply_to") or payload.get("In-Reply-To") or "").strip(),
        "references": str(payload.get("references") or payload.get("References") or "").strip(),
        "rfc_message_id": str(payload.get("rfc_message_id") or payload.get("Message-ID") or "").strip(),
    }


def _parse_date_header(value: Any) -> str | None:
    if not value:
        return None
    if hasattr(value, "tzinfo"):
        try:
            return format_datetime(value)  # type: ignore[arg-type]
        except Exception:
            return str(value)
    text = str(value).strip()
    if not text:
        return None
    # Already looks like an email date header
    if re.search(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", text):
        return text
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(text)
        return format_datetime(dt)
    except Exception:
        pass
    try:
        from datetime import datetime

        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                raw = text.replace("Z", "+0000")
                if fmt.endswith("%z") and re.search(r"[+-]\d{2}:\d{2}$", raw):
                    raw = raw[:-3] + raw[-2:]
                dt = datetime.strptime(raw, fmt)
                return format_datetime(dt)
            except ValueError:
                continue
    except Exception:
        pass
    return text


def build_eml_bytes(payload: dict[str, Any], *, attachment_root: Path | None = None) -> bytes:
    norm = normalize_payload(payload)
    msg = EmailMessage()
    msg["Subject"] = norm["subject"]
    msg["From"] = norm["from"]
    if norm["to"]:
        msg["To"] = ", ".join(norm["to"])
    if norm["cc"]:
        msg["Cc"] = ", ".join(norm["cc"])
    date_hdr = _parse_date_header(norm["date"])
    if date_hdr:
        msg["Date"] = date_hdr
    if norm["rfc_message_id"]:
        mid = norm["rfc_message_id"]
        if not mid.startswith("<"):
            mid = f"<{mid}>"
        msg["Message-ID"] = mid
    elif norm["message_id"]:
        # Synthetic but stable for threading within our pipeline
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", norm["message_id"])
        msg["Message-ID"] = f"<{safe}@agent-mail.local>"
    if norm["in_reply_to"]:
        msg["In-Reply-To"] = norm["in_reply_to"]
    if norm["references"]:
        msg["References"] = norm["references"]

    body = norm["body"] or ""
    if norm["body_format"] == "html":
        msg.set_content("HTML message; see HTML part.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    for att in norm["attachments"]:
        path_s = att.get("path") or ""
        if not path_s:
            continue
        path = Path(path_s).expanduser()
        if not path.is_file() and attachment_root is not None:
            cand = (attachment_root / path_s).expanduser()
            if cand.is_file():
                path = cand
            elif not path.is_absolute():
                cand2 = (attachment_root / path.name).expanduser()
                if cand2.is_file():
                    path = cand2
        if not path.is_file():
            raise FileNotFoundError(f"attachment not found: {path_s}")
        filename = att.get("filename") or path.name
        ctype, _ = mimetypes.guess_type(filename)
        if not ctype:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    return msg.as_bytes()


def write_eml(
    payload: dict[str, Any],
    out_path: Path,
    *,
    attachment_root: Path | None = None,
) -> Path:
    out_path = out_path.expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(build_eml_bytes(payload, attachment_root=attachment_root))
    return out_path


def load_message_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"message JSON must be an object: {path}")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--message-json", required=True, help="Path to agent-mail style JSON")
    ap.add_argument("--out", required=True, help="Output .eml path")
    ap.add_argument(
        "--attachment-root",
        default="",
        help="Optional base dir to resolve relative attachment paths",
    )
    args = ap.parse_args()
    payload = load_message_json(Path(args.message_json))
    root = Path(args.attachment_root).expanduser().resolve() if args.attachment_root else None
    path = write_eml(payload, Path(args.out), attachment_root=root)
    print(json.dumps({"ok": True, "eml_path": str(path), "message_id": message_id_of(payload)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
