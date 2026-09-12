#!/usr/bin/env python3
"""Save IMAP auth code to {project}/.mailbox.secret (Agent/dialog friendly; no terminal echo needed)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import write_mailbox_secret


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument(
        "--secret",
        default="",
        help="IMAP auth code (163 授权码). Prefer dialog paste → Agent runs this once.",
    )
    ap.add_argument(
        "--stdin",
        action="store_true",
        help="Read secret from stdin (one line) instead of --secret",
    )
    args = ap.parse_args()

    secret = sys.stdin.read() if args.stdin else args.secret
    path = write_mailbox_secret(Path(args.project_root), secret)
    # Never print the secret back
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(path),
                "note": "wrote .mailbox.secret (chmod 600); not stored in project.json",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
