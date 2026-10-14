#!/usr/bin/env python3
"""Write PM Skills orchestration short-rule into a project (CodeBuddy / WorkBuddy).

Target (project-scoped, never user-global):
  {project_root}/.codebuddy/rules/pm-skill-orchestration/RULE.mdc

True source: sibling lib ``skill-orchestration/ALWAYS.md``.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

RULE_DIR_NAME = "pm-skill-orchestration"
RULE_FILE_NAME = "RULE.mdc"


def _always_path() -> Path:
    # …/lib/project-foundation/scripts → …/lib/skill-orchestration/ALWAYS.md
    # WorkBuddy flat: …/skills/project-foundation/scripts → …/skills/skill-orchestration/ALWAYS.md
    here = Path(__file__).resolve()
    lib_or_skills = here.parents[2]
    candidate = lib_or_skills / "skill-orchestration" / "ALWAYS.md"
    if candidate.is_file():
        return candidate
    # Fallback: walk up looking for skill-orchestration/ALWAYS.md
    for parent in here.parents:
        hit = parent / "skill-orchestration" / "ALWAYS.md"
        if hit.is_file():
            return hit
    raise FileNotFoundError(
        "找不到 skill-orchestration/ALWAYS.md（应与 project-foundation 并列）"
    )


def install_orchestration_rule(project_root: Path) -> Path:
    """Copy ALWAYS.md → project .codebuddy/rules/…/RULE.mdc. Returns written path."""
    root = project_root.expanduser().resolve()
    src = _always_path()
    dest_dir = root / ".codebuddy" / "rules" / RULE_DIR_NAME
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / RULE_FILE_NAME
    shutil.copy2(src, dest)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True, type=Path)
    args = ap.parse_args()
    path = install_orchestration_rule(args.project_root)
    print(path)


if __name__ == "__main__":
    main()
