#!/usr/bin/env python3
"""Turn an Outlook .msg into the .eml the rest of the pipeline already reads.

People drop either a standard .eml or an Outlook .msg into 待处理邮件.
Downstream classify / archive only understands .eml, so .msg is converted
here, once, before any ledger is touched.
"""

from __future__ import annotations

import email
import re
from email.message import EmailMessage, Message
from pathlib import Path

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_HEADER_LINE = re.compile(r"(?im)^(from|subject|date|mime-version|received):")


class MsgUnreadable(Exception):
    """The drop file could not be turned into a mail. Message is for the user."""


def looks_like_rfc822(data: bytes) -> bool:
    sample = data[:8192].lstrip(b"\xef\xbb\xbf")
    if sample.startswith(_OLE_MAGIC) or b"\x00" in sample[:512]:
        return False
    head = sample.decode("utf-8", errors="ignore")
    return _HEADER_LINE.search(head) is not None


def _fill_missing_headers(email_msg: EmailMessage, outlook) -> None:
    """Outlook sometimes keeps the subject only in the message fields, not the header block."""
    pairs = (
        ("Subject", getattr(outlook, "subject", None)),
        ("From", getattr(outlook, "sender", None)),
        ("To", getattr(outlook, "to", None)),
        ("Cc", getattr(outlook, "cc", None)),
        ("Message-ID", getattr(outlook, "messageId", None)),
    )
    for name, value in pairs:
        text = str(value or "").strip()
        if text and not str(email_msg.get(name) or "").strip():
            email_msg[name] = text
    if not str(email_msg.get("Date") or "").strip():
        sent = getattr(outlook, "date", None)
        if sent is not None:
            email_msg["Date"] = email.utils.format_datetime(sent)


def _clean_filenames(email_msg: EmailMessage) -> None:
    """Outlook stores a trailing NUL on filenames. A NUL breaks the archive name."""
    for part in email_msg.walk():
        filename = part.get_filename()
        if not filename or "\x00" not in filename:
            continue
        clean = filename.replace("\x00", "").strip() or "attachment"
        disposition = part.get_content_disposition() or "attachment"
        if "Content-Disposition" in part:
            del part["Content-Disposition"]
        part.add_header("Content-Disposition", disposition, filename=clean)


def msg_to_eml_bytes(path: Path) -> bytes:
    path = path.expanduser().resolve()
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MsgUnreadable(f"这封读不了，留在待处理里了：{exc}") from exc
    if looks_like_rfc822(data):
        return data
    if not data.startswith(_OLE_MAGIC):
        raise MsgUnreadable("这不是 Outlook 的 .msg，也不是标准邮件，留在待处理里了。")
    try:
        import extract_msg
    except ImportError as exc:
        raise MsgUnreadable(
            "这封是 Outlook 的 .msg，但这台电脑还没装读取它的组件，所以留在待处理里了。"
        ) from exc
    try:
        outlook = extract_msg.openMsg(str(path))
    except Exception as exc:  # noqa: BLE001 — 坏信、加密信都留在夹里
        raise MsgUnreadable(f"这封 Outlook 邮件读不了，留在待处理里了：{exc}") from exc
    try:
        try:
            email_msg = outlook.asEmailMessage()
        except Exception as exc:  # noqa: BLE001
            raise MsgUnreadable(f"这封 Outlook 邮件转不成标准邮件，留在待处理里了：{exc}") from exc
        _fill_missing_headers(email_msg, outlook)
        _clean_filenames(email_msg)
        return email_msg.as_bytes(policy=email.policy.SMTP)
    finally:
        outlook.close()


def read_mail_bytes(path: Path) -> bytes:
    path = path.expanduser().resolve()
    if path.suffix.lower() == ".msg":
        return msg_to_eml_bytes(path)
    return path.read_bytes()


def load_mail(path: Path) -> Message:
    return email.message_from_bytes(read_mail_bytes(path))


def staged_eml_path(msg_path: Path) -> Path:
    drop = msg_path.parent
    names = [f"{msg_path.stem}.eml", f"{msg_path.stem}.from-msg.eml"]
    names.extend(f"{msg_path.stem}.from-msg-{n}.eml" for n in range(2, 50))
    for name in names:
        candidate = drop / name
        if not candidate.exists():
            return candidate
    raise MsgUnreadable("旁边已经有太多同名邮件，这封 .msg 先留在待处理里了。")


def stage_msg_as_eml(path: Path) -> Path:
    """Write a sibling .eml and remove the .msg. Returns the .eml path.

    .eml inputs are returned unchanged. The .msg is removed only after the
    .eml is on disk, so a failed convert leaves the original in the drop folder.
    """
    path = path.expanduser().resolve()
    if path.suffix.lower() != ".msg":
        return path
    raw = msg_to_eml_bytes(path)
    dest = staged_eml_path(path)
    dest.write_bytes(raw)
    path.unlink()
    return dest
