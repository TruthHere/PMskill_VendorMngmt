"""Locate project-foundation and sibling skills without PYTHONPATH.

Canonical: ``.cursor/lib/project-foundation`` and ``.cursor/skills/<name>``.
WorkBuddy: those folders sit next to each other under ``~/.workbuddy/skills/``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HOME_SKILL_ROOTS = (
    Path.home() / ".workbuddy" / "skills",
    Path.home() / ".cursor" / "skills",
)


def prepend_sys_path(path: Path) -> None:
    """Put a directory at the front of sys.path (move it if it is already present)."""
    s = str(path)
    while s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)


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
    for root in _HOME_SKILL_ROOTS:
        cand = root / "project-foundation" / "scripts"
        if (cand / "common.py").is_file():
            return cand
    raise ImportError(
        "找不到项目基建库 project-foundation。"
        "真源应在 .cursor/lib/project-foundation；"
        "WorkBuddy 则与各 Skill 文件夹并列。"
    )


def skill_scripts(skill_name: str, anchor: Path | None = None) -> Path:
    start = (anchor or Path(__file__)).resolve()
    for p in [start, *start.parents]:
        for rel in (
            (skill_name, "scripts"),
            (".cursor", "skills", skill_name, "scripts"),
            ("skills", skill_name, "scripts"),
        ):
            cand = p.joinpath(*rel)
            if cand.is_dir() and any(cand.glob("*.py")):
                return cand
    for root in _HOME_SKILL_ROOTS:
        cand = root / skill_name / "scripts"
        if cand.is_dir() and any(cand.glob("*.py")):
            return cand
    raise ImportError(
        f"找不到技能 {skill_name} 的 scripts 目录。"
        "仓库里应在 .cursor/skills/ 下与其它技能并列；"
        "WorkBuddy 应在 ~/.workbuddy/skills/ 下并列。"
    )


def load_skill_module(skill_name: str, script_stem: str, anchor: Path | None = None):
    """Load a sibling skill script by file path.

    Uses a unique module name so a same-named file in the *current* script
    directory cannot shadow it (python render_card.py vs payment-sheet).
    """
    scripts = skill_scripts(skill_name, anchor)
    path = scripts / f"{script_stem}.py"
    if not path.is_file():
        raise ImportError(f"找不到 {skill_name}/scripts/{script_stem}.py（{path}）")
    prepend_sys_path(scripts)
    mod_name = f"_pm_{skill_name.replace('-', '_')}_{script_stem}"
    existing = sys.modules.get(mod_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod
