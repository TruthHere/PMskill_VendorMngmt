#!/usr/bin/env python3
"""Backward-compat shim → project-foundation. Do not add logic here."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from _foundation import foundation_scripts

_FOUNDATION_SCRIPTS = foundation_scripts(Path(__file__))
_TARGET = _FOUNDATION_SCRIPTS / "common.py"

if str(_FOUNDATION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION_SCRIPTS))

# Replace this shim in sys.modules so sibling foundation imports share one `common`.
_spec = importlib.util.spec_from_file_location("common", _TARGET)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load project-foundation common from {_TARGET}")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["common"] = _mod
_spec.loader.exec_module(_mod)
globals().update({k: v for k, v in vars(_mod).items() if k != "__name__"})
