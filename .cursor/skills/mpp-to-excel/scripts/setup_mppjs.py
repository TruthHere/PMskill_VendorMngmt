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

# Official @byteink/mppjs optional sidecars (npm). Others need Java+mpxj or XML.
_SUPPORTED_SIDECARS = frozenset(
    {
        "darwin-arm64",
        "linux-x64",
        "linux-arm64",
        "win32-x64",
    }
)


def platform_parts() -> tuple[str, str]:
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
    return os_name, arch


def platform_sidecar_glob() -> str:
    os_name, arch = platform_parts()
    return f"mppjs-{os_name}-{arch}"


def platform_tag() -> str:
    os_name, arch = platform_parts()
    return f"{os_name}-{arch}"


def is_supported_platform() -> bool:
    return platform_tag() in _SUPPORTED_SIDECARS


def _binary_names() -> list[str]:
    """Prefer .exe on Windows; keep bare name for PATH/vendor compatibility."""
    if platform.system().lower() in {"windows", "win32"}:
        return ["mpxj-convert.exe", "mpxj-convert"]
    return ["mpxj-convert"]


def _chmod_executable(path: Path) -> None:
    if platform.system().lower() in {"windows", "win32"}:
        return
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except OSError:
        pass


def _sidecar_bin(nm_root: Path, sidecar_dir_name: str) -> Path | None:
    base = nm_root / sidecar_dir_name / "bin"
    if not base.is_dir():
        return None
    for name in _binary_names():
        p = base / name
        if p.is_file():
            return p
    return None


def _find_platform_matched(nm_root: Path) -> Path | None:
    return _sidecar_bin(nm_root, platform_sidecar_glob())


def _find_any_sidecar(nm_root: Path) -> Path | None:
    """Last resort: any installed sidecar (may be wrong OS — caller should warn)."""
    for name in _binary_names():
        for p in nm_root.glob(f"mppjs-*/bin/{name}"):
            if p.is_file():
                return p
    return None


def _binary_matches_platform(path: Path) -> bool:
    """Best-effort: skip vendor/.mppjs binaries copied from another OS/arch."""
    tag = platform_tag()
    system = platform.system().lower()
    name = path.name.lower()

    if system in {"windows", "win32"}:
        # Mac/Linux ELF/Mach-O copied over will not be .exe
        return name.endswith(".exe") or tag.startswith("win32")

    # Unix: use `file` when available
    file_cmd = shutil.which("file")
    if not file_cmd:
        return True
    try:
        proc = subprocess.run(
            [file_cmd, "-b", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        desc = (proc.stdout or "").lower()
    except (OSError, subprocess.TimeoutExpired):
        return True

    if system == "darwin":
        if "mach-o" not in desc:
            return False
        if "arm64" in tag:
            return "arm64" in desc or "aarch64" in desc
        if "x64" in tag:
            return "x86_64" in desc or "x86-64" in desc
        return True

    if system == "linux":
        if "elf" not in desc:
            return False
        if "arm64" in tag:
            return "aarch64" in desc or "arm64" in desc
        if "x64" in tag:
            return "x86-64" in desc or "x86_64" in desc or "amd64" in desc
        return True

    return True


def find_local_binary() -> Path | None:
    """Resolve mpxj-convert for *this* OS/arch. Prefer platform-matched npm sidecar."""
    env = os.environ.get("MPPJS_BINARY", "").strip()
    if env and Path(env).is_file():
        return Path(env)

    nm = _MPPJS_DIR / "node_modules" / "@byteink"
    if nm.is_dir():
        matched = _find_platform_matched(nm)
        if matched is not None:
            return matched

    for name in _binary_names():
        vendor = _SCRIPTS / "vendor" / name
        if vendor.is_file():
            if _binary_matches_platform(vendor):
                return vendor
            print(
                f"警告: 跳过与本机平台不符的 vendor 二进制: {vendor} "
                f"（期望 {platform_sidecar_glob()}）。将尝试重新安装。",
                file=sys.stderr,
            )

    for cmd in ("mpxj-convert", "mpxj-convert.exe"):
        which = shutil.which(cmd)
        if which:
            p = Path(which)
            if _binary_matches_platform(p):
                return p

    # Wrong-platform leftover under .mppjs (e.g. copied from another machine)
    if nm.is_dir():
        other = _find_any_sidecar(nm)
        if other is not None and _binary_matches_platform(other):
            # Matched by file(1) but not by folder name — still usable
            return other
        if other is not None:
            print(
                f"警告: .mppjs 里的二进制与本机不符（期望 {platform_sidecar_glob()}）。"
                f"建议删除 {_MPPJS_DIR} 后重跑 setup_mppjs.py。",
                file=sys.stderr,
            )

    return None


def _seed_vendor_from_existing() -> Path | None:
    """If user already has a *matching* mppjs install elsewhere, copy into skill vendor."""
    vendor_dir = _SCRIPTS / "vendor"
    for name in _binary_names():
        vendor_bin = vendor_dir / name
        if vendor_bin.is_file():
            return vendor_bin

    want = platform_sidecar_glob()
    search_roots = [
        Path.home() / "Desktop" / "Test" / "_mpp_convert" / "node_modules" / "@byteink",
        Path.home() / "node_modules" / "@byteink",
        _SCRIPTS.parent / "node_modules" / "@byteink",
    ]
    src: Path | None = None
    for root in search_roots:
        if not root.is_dir():
            continue
        src = _sidecar_bin(root, want)
        if src is not None:
            break
    if src is None:
        return None

    vendor_dir.mkdir(parents=True, exist_ok=True)
    # Keep a stable vendor name without .exe on Unix; on Windows prefer .exe
    dest_name = "mpxj-convert.exe" if src.name.endswith(".exe") else "mpxj-convert"
    vendor_bin = vendor_dir / dest_name
    shutil.copy2(src, vendor_bin)
    _chmod_executable(vendor_bin)
    return vendor_bin


def ensure_mppjs(*, timeout: int = 600) -> Path:
    """Return path to mpxj-convert; install under scripts/.mppjs if missing."""
    existing = find_local_binary()
    if existing is not None:
        return existing

    if not is_supported_platform():
        raise RuntimeError(
            f"当前平台 {platform_tag()} 没有官方 mppjs 原生包。\n"
            f"已支持：{', '.join(sorted(_SUPPORTED_SIDECARS))}。\n"
            "请改用：① Project 另存为 XML 再喂本 Skill；或 ② 安装 Java 17+ 与 pip 包 mpxj。"
        )

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
        pkg_json.write_text('{"name":"mpp-to-excel-mppjs","private":true}\n', encoding="utf-8")

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
