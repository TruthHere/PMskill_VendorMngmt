#!/usr/bin/env python3
"""Skill 0 thin CLI → project-foundation library init_project."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def _foundation_scripts() -> Path:
    for p in Path(__file__).resolve().parents:
        for rel in (
            ("lib", "project-foundation", "scripts"),
            (".cursor", "lib", "project-foundation", "scripts"),
            ("project-foundation", "scripts"),
        ):
            cand = p.joinpath(*rel)
            if (cand / "common.py").is_file():
                return cand
    raise ImportError("找不到项目基建库 project-foundation")


_FOUNDATION_SCRIPTS = _foundation_scripts()
_TARGET = _FOUNDATION_SCRIPTS / "init_project.py"

if str(_FOUNDATION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION_SCRIPTS))

if __name__ == "__main__":
    sys.argv[0] = str(_TARGET)
    runpy.run_path(str(_TARGET), run_name="__main__")
