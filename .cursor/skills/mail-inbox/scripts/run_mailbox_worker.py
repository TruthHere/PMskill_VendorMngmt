#!/usr/bin/env python3
"""Background worker: poll all registered projects on an interval."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILLS = SCRIPTS.parents[1]
FULFILLMENT_SCRIPTS = SKILLS / "po-flow" / "scripts"
for path in (SCRIPTS, FULFILLMENT_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from common import load_json, registry_path  # noqa: E402

_POLL_SPEC = importlib.util.spec_from_file_location(
    "mail_inbox_poll_mailbox",
    SCRIPTS / "poll_mailbox.py",
)
if _POLL_SPEC is None or _POLL_SPEC.loader is None:
    raise RuntimeError("failed to load mail-inbox poll_mailbox.py")
_POLL_MODULE = importlib.util.module_from_spec(_POLL_SPEC)
_POLL_SPEC.loader.exec_module(_POLL_MODULE)
poll_project = _POLL_MODULE.poll_project


def list_projects() -> list[dict]:
    data = load_json(registry_path(), {"projects": []})
    return data.get("projects") or []


def run_once() -> dict:
    projects = list_projects()
    summary = {"projects": [], "errors": []}
    for project in projects:
        root = Path(project["root"])
        if not root.exists():
            summary["errors"].append({"root": str(root), "error": "missing"})
            continue
        try:
            result = poll_project(root)
            summary["projects"].append(
                {"root": str(root), "code": project.get("code"), **result}
            )
        except Exception as exc:
            summary["errors"].append({"root": str(root), "error": str(exc)})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Mailbox worker for mail-inbox")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between polls")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()

    if args.once:
        print(json.dumps(run_once(), ensure_ascii=False, indent=2))
        return

    print(f"Mailbox worker started. registry={registry_path()} interval={args.interval}s")
    while True:
        summary = run_once()
        fetched = sum(p.get("fetched", 0) for p in summary.get("projects", []))
        print(
            json.dumps(
                {
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "fetched": fetched,
                    "summary": summary,
                },
                ensure_ascii=False,
            )
        )
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
