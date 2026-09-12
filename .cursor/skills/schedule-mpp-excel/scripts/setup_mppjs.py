#!/usr/bin/env python3
"""Ensure @byteink/mppjs native binary is installed under scripts/.mppjs/."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_MPPJS_DIR = _SCRIPTS / ".mppjs"
_PKG = "@byteink/mppjs"


def platform_sidecar_glob() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        os_name = "darwin"
    elif system == "linux":
        os_name = "linux"
    elif system in {"windows", "win32"}:
        os_name = "win32"
    else:
        os_name = system
    if machine in {"arm64", "aarch64"}:
        arch = "arm64"
    elif machine in {"x86_64", "amd64"}:
        arch = "x64"
    else:
        arch = machine
    return f"mppjs-{os_name}-{arch}"


def find_local_binary() -> Path | None:
    env = os.environ.get("MPPJS_BINARY", "").strip()
    if env and Path(env).is_file():
        return Path(env)

    vendor = _SCRIPTS / "vendor" / "mpxj-convert"
    if vendor.is_file():
        return vendor

    which = shutil.which("mpxj-convert")
    if which:
        return Path(which)

    # Skill-local npm install
    nm = _MPPJS_DIR / "node_modules" / "@byteink"
    if nm.is_dir():
        for p in nm.glob("mppjs-*/bin/mpxj-convert"):
            if p.is_file():
                return p
        for p in nm.glob("mppjs-*/bin/mpxj-convert.exe"):
            if p.is_file():
                return p

    return None


def _seed_vendor_from_existing() -> Path | None:
    """If user already has an mppjs install elsewhere, copy into skill vendor (one-time)."""
    vendor_dir = _SCRIPTS / "vendor"
    vendor_bin = vendor_dir / "mpxj-convert"
    if vendor_bin.is_file():
        return vendor_bin

    search_roots = [
        Path.home() / "Desktop" / "Test" / "_mpp_convert" / "node_modules" / "@byteink",
        Path.home() / "node_modules" / "@byteink",
        _SCRIPTS.parent / "node_modules" / "@byteink",
    ]
    src: Path | None = None
    for root in search_roots:
        if not root.is_dir():
            continue
        for p in root.glob("mppjs-*/bin/mpxj-convert"):
            if p.is_file():
                src = p
                break
        if src:
            break
    if src is None:
        return None

    vendor_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, vendor_bin)
    vendor_bin.chmod(vendor_bin.stat().st_mode | 0o111)
    return vendor_bin


def ensure_mppjs(*, timeout: int = 600) -> Path:
    """Return path to mpxj-convert; install under scripts/.mppjs if missing."""
    existing = find_local_binary()
    if existing is not None:
        return existing

    seeded = _seed_vendor_from_existing()
    if seeded is not None:
        print(f"已从本机现有安装复制 mppjs → {seeded}", file=sys.stderr)
        return seeded

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError(
            "未找到 mppjs 二进制，且本机没有 npm。\n"
            "请安装 Node.js ≥ 20 后重试，或设置 MPPJS_BINARY 指向 mpxj-convert。"
        )

    _MPPJS_DIR.mkdir(parents=True, exist_ok=True)
    pkg_json = _MPPJS_DIR / "package.json"
    if not pkg_json.exists():
        pkg_json.write_text('{"name":"schedule-mpp-excel-mppjs","private":true}\n', encoding="utf-8")

    print(f"正在安装 {_PKG} 到 {_MPPJS_DIR}（首次约需下载原生二进制，可能需数分钟）…", file=sys.stderr)
    proc = subprocess.run(
        [npm, "install", "--no-fund", "--no-audit", _PKG],
        cwd=str(_MPPJS_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"npm install {_PKG} 失败：\n{err}")

    found = find_local_binary()
    if found is None:
        raise RuntimeError(
            f"已安装 {_PKG}，但未找到平台二进制（期望 sidecar: {platform_sidecar_glob()}）。\n"
            f"请检查 {_MPPJS_DIR / 'node_modules' / '@byteink'}"
        )
    print(f"mppjs 就绪: {found}", file=sys.stderr)
    return found


def main() -> int:
    timeout = int(os.environ.get("MPPJS_SETUP_TIMEOUT", "600"))
    try:
        path = ensure_mppjs(timeout=timeout)
    except Exception as e:
        print(f"失败: {e}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
