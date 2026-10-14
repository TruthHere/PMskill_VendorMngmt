#!/usr/bin/env python3
"""Stage 0: Initialize project directory, project.json, tracker.csv, pending.json, inbox."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    MAILBOX_STATE_JSON,
    PROJECT_JSON,
    SCHEDULE_JSON,
    drop_mail_dir,
    ensure_inbox_dirs,
    load_json,
    now_iso,
    project_archive_dir,
    project_json_path,
    register_project,
    resolve_tracker_path,
    save_json,
    save_tracker_packages,
    system_dir,
    tracker_basename,
    write_mailbox_secret,
    write_project_background_md,
)
from pending_store import ensure_pending_file


def init_project(
    root: Path,
    *,
    name: str,
    code: str,
    project_type: str,
    address: str,
    client: str,
    pm: str,
    currency: str,
    mailbox_address: str = "",
    mailbox_imap_host: str = "imap.163.com",
    mailbox_imap_port: int = 993,
    mailbox_username: str = "",
) -> dict:
    root = root.expanduser().resolve()
    if not str(currency or "").strip():
        raise ValueError("currency_required")
    if project_json_path(root).is_file():
        raise FileExistsError("already_initialized")
    archive_dir = project_archive_dir(root, create=True) / "00_进度计划"
    archive_dir.mkdir(parents=True, exist_ok=True)
    sys_dir = system_dir(root, create=True)
    ensure_inbox_dirs(root)
    drop = drop_mail_dir(root, create=True)

    username = mailbox_username or mailbox_address
    project = {
        "project_name": name,
        "project_code": code,
        "project_type": project_type,
        "address": address,
        "client_name": client,
        "project_manager": pm,
        "currency_tax": currency,
        "root_path": str(root),
        "initialized_at": now_iso(),
    }
    if mailbox_address:
        project["mailbox"] = {
            "address": mailbox_address,
            "imap_host": mailbox_imap_host,
            "imap_port": mailbox_imap_port,
            "username": username,
        }
    save_json(sys_dir / PROJECT_JSON, project)

    save_tracker_packages(root, [])
    project = load_json(sys_dir / PROJECT_JSON, project)

    schedule = load_json(sys_dir / SCHEDULE_JSON, {"milestones": [], "note": "MVP: 手填关键里程碑"})
    save_json(sys_dir / SCHEDULE_JSON, schedule)

    ensure_pending_file(root)

    if not (sys_dir / MAILBOX_STATE_JSON).exists():
        save_json(sys_dir / MAILBOX_STATE_JSON, {"processed_uids": [], "processed_msg_ids": []})

    write_project_background_md(root, project)

    register_project(root, code)

    orchestration_rule = ""
    try:
        from install_orchestration_rule import install_orchestration_rule

        orchestration_rule = str(install_orchestration_rule(root))
    except Exception as exc:  # noqa: BLE001 — 建项不因 Rule 失败而整单失败
        orchestration_rule = f"FAILED: {exc}"

    tracker_name = str(project.get("tracker_xlsx") or "") or (
        resolve_tracker_path(root).name if resolve_tracker_path(root) else tracker_basename(project)
    )
    out = {
        "ok": True,
        "project": project,
        "tracker": str(resolve_tracker_path(root) or root / tracker_basename(project)),
        "root": str(root),
        "drop_mail": str(drop),
        "visible": [
            "项目背景.md",
            tracker_name,
            "项目档案/00_进度计划/",
            "待处理邮件/",
        ],
    }
    if orchestration_rule:
        out["orchestration_rule"] = orchestration_rule
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize project (stage 0 · project-foundation library)")
    parser.add_argument("--root", required=True, help="Local project root folder path")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--code", required=True, help="Project code")
    parser.add_argument("--type", required=True, dest="project_type", help="Project type")
    parser.add_argument("--address", required=True, help="Project address")
    parser.add_argument("--client", required=True, help="Client name")
    parser.add_argument("--pm", required=True, help="Project manager")
    parser.add_argument(
        "--currency",
        required=True,
        help="Currency and tax, e.g. 人民币 含税. No default; ask the user first.",
    )
    parser.add_argument("--mailbox-address", default="", help="Project IMAP mailbox address")
    parser.add_argument("--mailbox-imap-host", default="imap.163.com")
    parser.add_argument("--mailbox-imap-port", type=int, default=993)
    parser.add_argument("--mailbox-username", default="", help="Defaults to mailbox address")
    parser.add_argument(
        "--mailbox-secret",
        default="",
        help="Optional IMAP auth code; writes {root}/.mailbox.secret (never into project.json)",
    )
    parser.add_argument(
        "--schedule-csv",
        default="",
        help="Optional project schedule CSV; imports milestones automatically",
    )
    args = parser.parse_args()

    root = Path(args.root)
    if project_json_path(root).is_file():
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "already_initialized",
                    "root": str(root.expanduser().resolve()),
                    "note": "这个文件夹已经是建过的项目。先问是接着用，还是换一个空文件夹。不要覆盖。",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    if not str(args.currency or "").strip():
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "currency_required",
                    "note": "还没问清币种和是否含税，不能建。",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    result = init_project(
        root,
        name=args.name,
        code=args.code,
        project_type=args.project_type,
        address=args.address,
        client=args.client,
        pm=args.pm,
        currency=args.currency,
        mailbox_address=args.mailbox_address,
        mailbox_imap_host=args.mailbox_imap_host,
        mailbox_imap_port=args.mailbox_imap_port,
        mailbox_username=args.mailbox_username,
    )
    if args.mailbox_secret.strip():
        secret_path = write_mailbox_secret(root, args.mailbox_secret)
        result["mailbox_secret_path"] = str(secret_path)
    if args.schedule_csv:
        from schedule_csv import import_project_schedule_csv

        schedule_result = import_project_schedule_csv(
            root,
            Path(args.schedule_csv),
        )
        result["schedule"] = schedule_result
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
