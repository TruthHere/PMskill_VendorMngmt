#!/usr/bin/env python3
"""Resolve SoMark API key for pdf-read — portable across Cursor, WorkBuddy, CLI."""

from __future__ import annotations

import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent


def _read_secret_file(path: Path) -> str:
    if not path.exists():
        return ""
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return ""
    # Allow plain key or KEY=value (e.g. SOMARK_API_KEY=sk-...)
    if "=" in raw and not raw.startswith("sk-"):
        _, _, value = raw.partition("=")
        return value.strip().strip("'\"")
    return raw


def resolve_somark_api_key(project_root: Path | None = None) -> str:
    """
    Lookup order (first hit wins):
      1. SOMARK_API_KEY env
      2. <project_root>/.somark.secret
      3. pdf-read skill /.somark.secret
      4. ~/.pmskills/somark.secret
    """
    env_key = os.environ.get("SOMARK_API_KEY", "").strip()
    if env_key:
        return env_key

    candidates: list[Path] = []
    if project_root is not None:
        candidates.append(project_root.expanduser().resolve() / ".somark.secret")
    candidates.extend(
        [
            SKILL_ROOT / ".somark.secret",
            Path.home() / ".pmskills" / "somark.secret",
        ]
    )

    for path in candidates:
        try:
            key = _read_secret_file(path)
            if key:
                return key
        except OSError:
            continue
    return ""


def somark_env(project_root: Path | None = None) -> dict[str, str]:
    """Return os.environ copy with SOMARK_API_KEY set when resolved."""
    env = os.environ.copy()
    key = resolve_somark_api_key(project_root)
    if key:
        env["SOMARK_API_KEY"] = key
    return env


def key_source_hint(project_root: Path | None = None) -> str:
    """Human-readable hint for setup docs / error messages."""
    if os.environ.get("SOMARK_API_KEY", "").strip():
        return "SOMARK_API_KEY (environment)"
    if project_root and (project_root / ".somark.secret").exists():
        return str(project_root / ".somark.secret")
    if (SKILL_ROOT / ".somark.secret").exists():
        return str(SKILL_ROOT / ".somark.secret")
    home = Path.home() / ".pmskills" / "somark.secret"
    if home.exists():
        return str(home)
    return "not configured"
