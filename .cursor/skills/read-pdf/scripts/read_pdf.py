#!/usr/bin/env python3
"""Orchestrate PDF reading: classify → route (local / SoMark) → unified JSON output."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
_FOUNDATION = SCRIPT_DIR.parents[2] / "lib" / "project-foundation" / "scripts"
if str(_FOUNDATION) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION))

sys.path.insert(0, str(SCRIPT_DIR))
from classify_pdf import classify, extract_text_native  # noqa: E402
from somark_config import resolve_somark_api_key, somark_env, key_source_hint  # noqa: E402
from write_guard import assert_solo_output_allowed  # noqa: E402

# SoMark 同步解析长文档可能截断正文；超过阈值强制 --async --wait
SOMARK_ASYNC_MIN_PAGES = 30
SOMARK_ASYNC_SCAN_MIN_PAGES = 20


def somark_use_async(info: dict) -> bool:
    """Return True when SoMark should use async mode to avoid truncated output."""
    if info.get("classification") == "large":
        return True
    pages = int(info.get("page_count") or 0)
    if pages >= SOMARK_ASYNC_MIN_PAGES:
        return True
    if info.get("is_scan_likely") and pages >= SOMARK_ASYNC_SCAN_MIN_PAGES:
        return True
    return False


def run_local_extract(pdf_path: Path) -> dict:
    pages, engine = extract_text_native(pdf_path)
    text = "\n".join(f"--- page {i} ---\n{t}" for i, t in enumerate(pages, start=1))
    return {
        "source": "local",
        "engine": engine,
        "text": text,
        "markdown": text,
        "page_count": len(pages),
    }


def run_somark(pdf_path: Path, async_mode: bool, project_root: Path | None = None) -> dict:
    api_key = resolve_somark_api_key(project_root)
    if not api_key:
        raise RuntimeError(
            "SoMark API key not found. Set SOMARK_API_KEY or create one of:\n"
            f"  - {SKILL_ROOT / '.somark.secret'}\n"
            f"  - {Path.home() / '.pmskills' / 'somark.secret'}\n"
            "See references/somark-setup.md · Key: https://somark.cn/workbench/apikey"
        )
    somark = shutil.which("somark")
    if not somark:
        raise RuntimeError("somark CLI not found. Install: pip install somark")

    with tempfile.TemporaryDirectory(prefix="read-pdf-somark-") as tmp:
        out_dir = Path(tmp)
        cmd = [
            somark,
            "parse",
            str(pdf_path),
            "--formats",
            "md",
            "--out",
            str(out_dir),
        ]
        if async_mode:
            cmd.extend(["--async", "--wait"])

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=somark_env(project_root),
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "somark parse failed")

        md_files = sorted(out_dir.glob("*.md"))
        if not md_files:
            md_files = sorted(out_dir.rglob("*.md"))
        if not md_files:
            raise RuntimeError(f"somark produced no markdown in {out_dir}")

        markdown = md_files[0].read_text(encoding="utf-8", errors="replace")
        return {
            "source": "somark",
            "engine": "somark",
            "text": markdown,
            "markdown": markdown,
            "somark_output": str(md_files[0]),
            "somark_key_source": key_source_hint(project_root),
            "somark_async": async_mode,
        }


def read_pdf(pdf_path: Path, project_root: Path | None = None) -> dict:
    info = classify(pdf_path)
    if info.get("classification") == "oversized":
        return info

    classification = info["classification"]
    route = info["recommended_route"]

    try:
        if route == "local":
            result = run_local_extract(pdf_path)
            result["classification"] = classification
            result["is_scan_likely"] = info["is_scan_likely"]
            result["pdf"] = str(pdf_path)
        else:
            use_async = somark_use_async(info)
            result = run_somark(pdf_path, async_mode=use_async, project_root=project_root)
            result["classification"] = classification
            result["is_scan_likely"] = info["is_scan_likely"]
            result["pdf"] = str(pdf_path)
            result["page_count"] = info.get("page_count")
    except RuntimeError as e:
        # local empty → try somark fallback
        if route == "local" and resolve_somark_api_key(project_root):
            use_async = somark_use_async(info)
            result = run_somark(pdf_path, async_mode=use_async, project_root=project_root)
            result["classification"] = "scan"
            result["is_scan_likely"] = True
            result["pdf"] = str(pdf_path)
            result["fallback_from"] = "local_failed"
            result["fallback_reason"] = str(e)
        else:
            return {
                "pdf": str(pdf_path),
                "classification": classification,
                "error": str(e),
                "is_scan_likely": info["is_scan_likely"],
                "recommended_fallback": "优先页识图 + 人手填（扫描件需配置 SoMark，见 somark-setup.md）",
            }

    result.setdefault("pdf", str(pdf_path))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Read PDF via classify → route pipeline")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--project-root",
        default="",
        help="Optional project root for .somark.secret lookup",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else None
    if not pdf_path.exists():
        print(json.dumps({"error": f"not found: {pdf_path}"}, ensure_ascii=False))
        sys.exit(1)

    result = read_pdf(pdf_path, project_root=project_root)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        assert_solo_output_allowed(out_path)
        out_path.write_text(out + "\n", encoding="utf-8")
    print(out)

    if result.get("error"):
        sys.exit(2)


if __name__ == "__main__":
    main()
