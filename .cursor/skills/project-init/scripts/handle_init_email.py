#!/usr/bin/env python3
"""Skill 0 handler: project_init mail → confirm existing project / pending for manual init.

Does NOT silently create a half-baked project from email. New projects must go through
the project-foundation library init_project.py with PM-provided params (or Agent running that CLI).
"""

from __future__ import annotations

import argparse
import email
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
SKILLS = SCRIPTS.parents[1]
FULFILLMENT_SCRIPTS = SKILLS / "contract-fulfillment-struct" / "scripts"
MAIL_INBOX_SCRIPTS = SKILLS / "mail-inbox" / "scripts"

if str(FULFILLMENT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(FULFILLMENT_SCRIPTS))
from _foundation import foundation_scripts  # noqa: E402

FOUNDATION_SCRIPTS = foundation_scripts(Path(__file__))

for path in (SCRIPTS, FOUNDATION_SCRIPTS, FULFILLMENT_SCRIPTS, MAIL_INBOX_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from classify_mail import decode_mime_header, get_body_text  # noqa: E402
from common import (  # noqa: E402
    PROJECT_JSON,
    load_json,
    now_iso,
    save_json,
    system_file,
)
from pending_store import add_pending as store_add_pending  # noqa: E402
from process_email import extract_field  # noqa: E402


def add_pending(project_root: Path, item: dict[str, Any]) -> str:
    return store_add_pending(project_root, item, skill="project-init")


def _extract_init_fields(subject: str, body: str) -> dict[str, str]:
    return {
        "project_name": extract_field(body, ["项目名称"]) or "",
        "project_code": extract_field(body, ["项目编号"]) or "",
        "project_type": extract_field(body, ["项目类型"]) or "",
        "address": extract_field(body, ["项目地址"]) or "",
        "client": extract_field(body, ["甲方名称", "甲方"]) or "",
        "pm": extract_field(body, ["项目经理"]) or "",
        "currency": extract_field(body, ["币种/含税", "币种"]) or "",
        "root": extract_field(body, ["本地根文件夹路径", "本地根路径", "根文件夹路径"]) or "",
        "mailbox_address": extract_field(body, ["专用邮箱", "Skill邮箱", "邮箱"])
        or _mailbox_from_subject(subject),
    }


def _mailbox_from_subject(subject: str) -> str:
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", subject or "")
    return m.group(0) if m else ""


def _project_exists(project_root: Path) -> bool:
    return system_file(project_root, PROJECT_JSON).is_file()


def _maybe_update_mailbox(project_root: Path, mailbox_address: str) -> bool:
    """If email carries a mailbox and project lacks one (or differs), write it back."""
    mailbox_address = (mailbox_address or "").strip()
    if not mailbox_address or "@" not in mailbox_address:
        return False
    path = system_file(project_root, PROJECT_JSON)
    project = load_json(path, {}) or {}
    existing = ((project.get("mailbox") or {}).get("address") or "").strip()
    if existing == mailbox_address:
        return False
    project["mailbox"] = {
        "address": mailbox_address,
        "imap_host": ((project.get("mailbox") or {}).get("imap_host") or "imap.163.com"),
        "imap_port": int((project.get("mailbox") or {}).get("imap_port") or 993),
        "username": mailbox_address,
    }
    project["mailbox_updated_at"] = now_iso()
    save_json(path, project)
    return True


def handle_init_email(
    project_root: Path | None,
    eml_path: Path,
    *,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eml_path = eml_path.expanduser().resolve()
    msg = email.message_from_bytes(eml_path.read_bytes())
    subject = decode_mime_header(msg.get("Subject"))
    body = get_body_text(msg)
    fields = _extract_init_fields(subject, body)
    if classification and classification.get("hints"):
        for k, v in (classification.get("hints") or {}).items():
            if v and not fields.get(k):
                fields[k] = str(v)

    result: dict[str, Any] = {
        "ok": True,
        "intent": "project_init",
        "route_to": "project-init",
        "eml_path": str(eml_path),
        "subject": subject,
        "fields": fields,
        "auto": False,
    }

    root: Path | None = None
    if project_root is not None:
        root = project_root.expanduser().resolve()
    elif fields.get("root"):
        root = Path(fields["root"]).expanduser().resolve()

    if root is None:
        result["reason"] = "project_init_needs_root"
        result["note"] = (
            "收到项目初始化意图，但缺少 project_root / 正文「本地根文件夹路径」。"
            "请 PM 提供路径后运行 Skill 0 / `.cursor/lib/project-foundation/scripts/init_project.py`，"
            "勿在邮件路径静默建半残项目。"
        )
        return result

    if not _project_exists(root):
        root.mkdir(parents=True, exist_ok=True)
        pid = add_pending(
            root,
            {
                "step": "project_init",
                "fields": fields,
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "project_not_initialized",
                "note": (
                    "邮件识别为项目初始化，但目标目录尚无 .skill/project.json。"
                    "请用 Skill 0（调用基建库 `init_project.py`）补齐档案后再收信；"
                    "本 handler 不会静默建项目。"
                ),
            },
        )
        result["project_root"] = str(root)
        result["pending_id"] = pid
        result["reason"] = "project_not_initialized"
        return result

    # Existing project: confirm + optional mailbox bind refresh
    updated = _maybe_update_mailbox(root, fields.get("mailbox_address") or "")
    project = load_json(system_file(root, PROJECT_JSON), {}) or {}
    missing = [
        label
        for key, label in (
            ("project_name", "项目名称"),
            ("project_code", "项目编号"),
        )
        if not str(project.get(key) or "").strip()
    ]
    if missing:
        pid = add_pending(
            root,
            {
                "step": "project_init",
                "fields": fields,
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "project_archive_incomplete",
                "note": f"项目已有 project.json，但缺：{', '.join(missing)}。请 PM 补全。",
            },
        )
        result["project_root"] = str(root)
        result["pending_id"] = pid
        result["reason"] = "project_archive_incomplete"
        return result

    result["auto"] = True
    result["project_root"] = str(root)
    result["did"] = ["confirm_existing_project"] + (["update_mailbox"] if updated else [])
    result["note"] = (
        "项目已初始化；已确认档案。"
        + (" 已回写专用邮箱绑定。" if updated else "")
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", default="")
    ap.add_argument("--eml", required=True)
    ap.add_argument("--route-json", default="")
    args = ap.parse_args()

    root = Path(args.project_root).expanduser().resolve() if args.project_root else None
    classification = None
    if args.route_json:
        classification = json.loads(Path(args.route_json).expanduser().resolve().read_text(encoding="utf-8"))

    out = handle_init_email(root, Path(args.eml), classification=classification)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
