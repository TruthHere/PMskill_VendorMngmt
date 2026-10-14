#!/usr/bin/env python3
"""Backward-compat shim → critical-nodes. Do not add logic here."""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

_TARGET = (
    Path(__file__).resolve().parents[1].parent
    / "critical-nodes"
    / "scripts"
    / "sync_schedule_timeline.py"
)
_SCRIPTS = _TARGET.parent

if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

if __name__ == "__main__":
    sys.argv[0] = str(_TARGET)
    runpy.run_path(str(_TARGET), run_name="__main__")
else:
    _spec = importlib.util.spec_from_file_location("sync_schedule_timeline", _TARGET)
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Cannot load sync_schedule_timeline from {_TARGET}")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["sync_schedule_timeline"] = _mod
    _spec.loader.exec_module(_mod)
    globals().update({k: v for k, v in vars(_mod).items() if k != "__name__"})
