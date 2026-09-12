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
    ensure_inbox_dirs,
    load_json,
    now_iso,
    project_archive_dir,
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
    archive_dir = project_archive_dir(root, create=True) / "00_进度计划"
    archive_dir.mkdir(parents=True, exist_ok=True)
    sys_dir = system_dir(root, create=True)
    ensure_inbox_dirs(root)

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

    return {
        "project": project,
        "tracker": str(resolve_tracker_path(root) or root / tracker_basename(project)),
        "root": str(root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize project (stage 0 · project-foundation library)")
    parser.add_argument("--root", required=True, help="Local project root folder path")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--code", required=True, help="Project code")
    parser.add_argument("--type", required=True, dest="project_type", help="Project type")
    parser.add_argument("--address", required=True, help="Project address")
    parser.add_argument("--client", required=True, help="Client name")
    parser.add_argument("--pm", required=True, help="Project manager")
    parser.add_argument("--currency", default="CNY 含税", help="Currency and tax note")
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


if __name__ == "__main__":
    main()
