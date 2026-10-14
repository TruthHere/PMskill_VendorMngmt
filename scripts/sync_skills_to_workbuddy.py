#!/usr/bin/env python3
"""Sync PMskills runtime skills + shared libs → ~/.workbuddy/skills (overwrite).

Use after editing skills/libs in this repo, before re-testing in WorkBuddy.
project-foundation is a library (not a Skill) but is still copied as a sibling
folder so scripts can find it.
"""

from __future__ import annotations

import argparse
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILLS_SRC = REPO / "skills"
LIB_SRC = REPO / "lib"
DEFAULT_DEST = Path.home() / ".workbuddy" / "skills"

RUNTIME_SKILLS = (
    "po-flow",
    "vendor-card",
    "mail-inbox",
    "critical-nodes",
    "mpp-to-excel",
    "read-pdf",
    "new-project",
    "payment-flow",
    "payment-sheet",
    "change-flow",
    "cashflow",
)
# skill-orchestration = 编排说明书（Rule 配套），不是 Skill
RUNTIME_LIBS = ("project-foundation", "skill-orchestration")

EXCLUDE_DIR_NAMES = {"__pycache__", "node_modules", "evals", "tests", ".git"}
EXCLUDE_FILE_NAMES = {".DS_Store", ".mailbox.secret", "mailbox-registry.json"}
EXCLUDE_GLOBS = (
    "*.pyc",
    "*.secret",
    "*.pyo",
    "smoke_*.py",
    "run_all_evals.py",
)


def skip(rel: Path) -> bool:
    if any(p in EXCLUDE_DIR_NAMES for p in rel.parts):
        return True
    if rel.name in EXCLUDE_FILE_NAMES:
        return True
    return any(fnmatch.fnmatch(rel.name, g) for g in EXCLUDE_GLOBS)


def copy_skill(src: Path, dest: Path) -> int:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    n = 0
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        if skip(rel):
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        n += 1
    return n


def ensure_openpyxl(python: str) -> None:
    try:
        subprocess.run(
            [python, "-c", "import openpyxl; print(openpyxl.__version__)"],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"openpyxl OK ({python})")
    except subprocess.CalledProcessError:
        print(f"Installing openpyxl into: {python}")
        subprocess.run(
            [python, "-m", "pip", "install", "openpyxl==3.1.5"],
            check=True,
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"WorkBuddy skills root (default: {DEFAULT_DEST})",
    )
    ap.add_argument(
        "--skills",
        nargs="*",
        default=list(RUNTIME_SKILLS),
        help="Skill folder names to sync (default: Skill1 runtime set)",
    )
    ap.add_argument(
        "--with-openpyxl",
        action="store_true",
        help="Ensure openpyxl is installed for the given --python",
    )
    ap.add_argument(
        "--python",
        default=sys.executable,
        help="Python used for --with-openpyxl check/install",
    )
    args = ap.parse_args()

    dest_root: Path = args.dest.expanduser().resolve()
    dest_root.mkdir(parents=True, exist_ok=True)

    for name in args.skills:
        src = SKILLS_SRC / name
        if not (src / "SKILL.md").is_file():
            print(f"SKIP missing skill: {src}", file=sys.stderr)
            continue
        n = copy_skill(src, dest_root / name)
        print(f"synced {name} ({n} files) → {dest_root / name}")

    for name in RUNTIME_LIBS:
        src = LIB_SRC / name
        # project-foundation has scripts; skill-orchestration is docs-only
        if not ((src / "scripts" / "common.py").is_file() or (src / "README.md").is_file()):
            print(f"SKIP missing lib: {src}", file=sys.stderr)
            continue
        n = copy_skill(src, dest_root / name)
        print(f"synced lib {name} ({n} files, not a Skill) → {dest_root / name}")

    if args.with_openpyxl:
        ensure_openpyxl(args.python)

    print("\nDone. Restart WorkBuddy (or start a new chat), then retest.")


if __name__ == "__main__":
    main()
