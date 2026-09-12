"""Locate the project-foundation library (not a Skill).

Canonical: ``.cursor/lib/project-foundation``.
WorkBuddy: sibling ``project-foundation/`` next to the skills (no SKILL.md).
"""

from __future__ import annotations

from pathlib import Path


def foundation_scripts(anchor: Path | None = None) -> Path:
    start = (anchor or Path(__file__)).resolve()
    for p in [start, *start.parents]:
        for rel in (
            ("lib", "project-foundation", "scripts"),
            (".cursor", "lib", "project-foundation", "scripts"),
            ("project-foundation", "scripts"),
        ):
            cand = p.joinpath(*rel)
            if (cand / "common.py").is_file():
                return cand
    raise ImportError(
        "找不到项目基建库 project-foundation。"
        "真源应在 .cursor/lib/project-foundation；"
        "WorkBuddy 则与各 Skill 文件夹并列。"
    )
