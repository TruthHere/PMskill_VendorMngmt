#!/usr/bin/env python3
"""Scan a project's 待处理邮件 folder and dispatch .eml or Outlook .msg files.

User path for this release: people save whole messages into
{project}/待处理邮件, then ask the agent to run this script.
Does not poll a mailbox. Does not create 已处理邮件.
"""

from __future__ import annotations

import argparse
import email
import json
import sys
from email.message import Message
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SKILLS = _SCRIPTS.parents[1]
_FOUNDATION = _SKILLS.parent / "lib" / "project-foundation" / "scripts"
_FC_SCRIPTS = _SKILLS / "po-flow" / "scripts"

for path in (_SCRIPTS, _FOUNDATION, _FC_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from classify_mail import decode_mime_header  # noqa: E402
from common import drop_mail_dir, project_json_path  # noqa: E402
from dispatch_mail import classify_eml, dispatch_eml_file  # noqa: E402
from msg_to_eml import MsgUnreadable, stage_msg_as_eml  # noqa: E402
from process_email import looks_like_reply_subject  # noqa: E402

_SKIP_PARTS = {".skill", ".git", "__pycache__", "node_modules"}


def _load(path: Path) -> Message:
    return email.message_from_bytes(path.read_bytes())


def message_key(msg: Message) -> str:
    mid = decode_mime_header(msg.get("Message-ID")).strip().lower().strip("<>").strip()
    if mid:
        return "mid:" + mid
    subject = decode_mime_header(msg.get("Subject")).strip().lower()
    sent = decode_mime_header(msg.get("Date")).strip().lower()
    sender = decode_mime_header(msg.get("From")).strip().lower()
    return "meta:" + "|".join((subject, sent, sender))


def _subject(msg: Message) -> str:
    return decode_mime_header(msg.get("Subject")).strip()


def _index_archived(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    if not root.is_dir():
        return found
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".eml":
            continue
        if any(part in _SKIP_PARTS or part == "待处理邮件" for part in path.parts):
            continue
        try:
            key = message_key(_load(path))
        except OSError:
            continue
        found.setdefault(key, path.relative_to(root).as_posix())
    return found


def _item(
    *,
    file_name: str,
    status: str,
    note: str,
    subject: str = "",
    intent: str = "",
    archive: str = "",
    reason: str = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "file": file_name,
        "status": status,
        "note": note,
    }
    if subject:
        row["subject"] = subject
    if intent:
        row["intent"] = intent
    if archive:
        row["archive"] = archive
    if reason:
        row["reason"] = reason
    return row


def _handler_note(handler: dict[str, Any]) -> str:
    note = str(handler.get("note") or "").strip()
    reason = str(handler.get("reason") or "").strip()
    if note:
        return note
    if reason:
        return reason
    return "这封没办完，原件还在待处理邮件里。"


def _stage_outlook_msgs(drop: Path) -> list[dict[str, Any]]:
    """Turn each .msg into a sibling .eml before the normal scan.

    A failed convert stays as .msg and is reported here. The main scan skips
    .msg so the same file is not also called "not an email".
    """
    staged: list[dict[str, Any]] = []
    if not drop.is_dir():
        return staged
    for path in sorted(drop.iterdir(), key=lambda item: item.name.lower()):
        if path.name.startswith(".") or not path.is_file() or path.suffix.lower() != ".msg":
            continue
        try:
            stage_msg_as_eml(path)
        except MsgUnreadable as exc:
            staged.append(
                _item(
                    file_name=path.name,
                    status="left",
                    reason="msg_unreadable",
                    note=str(exc),
                )
            )
    return staged


def process_drop_folder(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    if not project_json_path(root).is_file():
        return {
            "ok": False,
            "reason": "project_not_initialized",
            "root": str(root),
            "note": "这个文件夹还不是项目。先在对话里新建项目。",
            "items": [],
        }

    drop = drop_mail_dir(root, create=True)
    archived = _index_archived(root)
    items: list[dict[str, Any]] = _stage_outlook_msgs(drop)

    entries = sorted(drop.iterdir(), key=lambda p: p.name.lower())
    for path in entries:
        if path.name.startswith("."):
            continue
        if path.is_dir():
            items.append(
                _item(
                    file_name=path.name + "/",
                    status="left",
                    reason="not_eml",
                    note="这是文件夹，不是整封邮件，留在待处理里了。",
                )
            )
            continue
        if path.suffix.lower() == ".msg":
            continue
        if path.suffix.lower() != ".eml":
            items.append(
                _item(
                    file_name=path.name,
                    status="left",
                    reason="not_eml",
                    note="这不是整封邮件。请另存成 .eml，或 Outlook 的 .msg。这件留在待处理里了。",
                )
            )
            continue

        try:
            msg = _load(path)
        except OSError as exc:
            items.append(
                _item(
                    file_name=path.name,
                    status="left",
                    reason="unreadable",
                    note=f"这封读不了，留在待处理里了：{exc}",
                )
            )
            continue

        subject = _subject(msg)
        key = message_key(msg)
        existing = archived.get(key)
        if existing and existing != path.relative_to(root).as_posix():
            path.unlink()
            items.append(
                _item(
                    file_name=path.name,
                    status="skipped_duplicate",
                    subject=subject,
                    archive=existing,
                    reason="already_archived",
                    note=f"这封已经归档在 {existing}，没有再办一遍。待处理里的原件已拿走。",
                )
            )
            continue

        try:
            classification = classify_eml(root, path)
        except Exception as exc:  # noqa: BLE001 — 一封坏信不能挡住后面的
            items.append(
                _item(
                    file_name=path.name,
                    status="left",
                    subject=subject,
                    reason="classify_failed",
                    note=f"没看懂这封，留在待处理里了：{exc}",
                )
            )
            continue

        intent = str(classification.get("intent") or "")
        if classification.get("route_to") == "new-project" or intent == "project_init":
            items.append(
                _item(
                    file_name=path.name,
                    status="left",
                    subject=subject,
                    intent=intent or "project_init",
                    reason="project_init_use_chat",
                    note="建项不走这个文件夹。请在对话里说新建项目。这封还留在待处理里。",
                )
            )
            continue

        if looks_like_reply_subject(subject):
            items.append(
                _item(
                    file_name=path.name,
                    status="needs_you",
                    subject=subject,
                    intent=intent,
                    reason="thread_reply",
                    note="这封是回信。先看正文最新一段再决定它在办什么，不要跟着引用里的旧字办。原件还在待处理里。",
                )
            )
            continue

        if classification.get("pending") or str(classification.get("confidence") or "") != "high":
            pending = classification.get("pending") or {}
            question = str(pending.get("question") or pending.get("reason") or "看不准这封在办什么")
            items.append(
                _item(
                    file_name=path.name,
                    status="needs_you",
                    subject=subject,
                    intent=intent,
                    reason=str(pending.get("reason") or "low_confidence"),
                    note=f"{question}。原件还在待处理里，台账没动。",
                )
            )
            continue

        try:
            result = dispatch_eml_file(root, path)
        except Exception as exc:  # noqa: BLE001
            items.append(
                _item(
                    file_name=path.name,
                    status="left",
                    subject=subject,
                    intent=intent,
                    reason="dispatch_failed",
                    note=f"没办成，原件还在待处理里：{exc}",
                )
            )
            continue

        handler = result.get("handler_result") or {}
        archived = _index_archived(root)
        archive_path = archived.get(key, "")
        if archive_path:
            path.unlink(missing_ok=True)
            if handler.get("auto") and not handler.get("pending_id"):
                items.append(
                    _item(
                        file_name=path.name,
                        status="done",
                        subject=subject,
                        intent=str(result.get("intent") or intent),
                        archive=archive_path,
                        note=f"已归档到 {archive_path}。待处理里的原件已拿走。",
                    )
                )
            else:
                items.append(
                    _item(
                        file_name=path.name,
                        status="archived_needs_you",
                        subject=subject,
                        intent=str(result.get("intent") or intent),
                        archive=archive_path,
                        reason=str(handler.get("reason") or ""),
                        note=(
                            f"文件已归档到 {archive_path}，待处理里的原件已拿走。"
                            f"这件事还要你拍板：{_handler_note(handler)}"
                        ),
                    )
                )
            continue

        items.append(
            _item(
                file_name=path.name,
                status="left",
                subject=subject,
                intent=str(result.get("intent") or intent),
                reason=str(handler.get("reason") or "not_archived"),
                note=_handler_note(handler),
            )
        )

    return {
        "ok": True,
        "project_root": str(root),
        "drop_mail": str(drop),
        "items": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    args = ap.parse_args()
    out = process_drop_folder(Path(args.project_root))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
