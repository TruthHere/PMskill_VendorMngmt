#!/usr/bin/env python3
"""Classify a PDF: text layer richness, page count, file size, scan likelihood."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

LARGE_MB = 30
MIN_CHARS = 80
MAX_MB = 200


def page_count(pdf_path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        return 0


def extract_text_native(pdf_path: Path) -> tuple[list[str], str]:
    pages: list[str] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        if any(p.strip() for p in pages):
            return pages, "pypdf"
    except Exception:
        pages = []

    try:
        import pdfplumber

        with pdfplumber.open(str(pdf_path)) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        if any(p.strip() for p in pages):
            return pages, "pdfplumber"
    except Exception:
        pages = []

    return pages, "none"


def classify(pdf_path: Path, min_chars: int = MIN_CHARS) -> dict:
    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_MB:
        return {
            "pdf": str(pdf_path),
            "classification": "oversized",
            "error": f"file exceeds {MAX_MB} MB limit",
            "size_mb": round(size_mb, 2),
        }

    pages, engine = extract_text_native(pdf_path)
    native_text = "\n".join(pages)
    native_chars = len(re.sub(r"\s+", "", native_text))
    is_scan = native_chars < min_chars
    total = page_count(pdf_path) or len(pages)

    if size_mb > LARGE_MB:
        classification = "large"
    elif is_scan:
        classification = "scan"
    else:
        classification = "text"

    return {
        "pdf": str(pdf_path),
        "classification": classification,
        "is_scan_likely": is_scan,
        "native_chars": native_chars,
        "engine_native": engine,
        "page_count": total,
        "size_mb": round(size_mb, 2),
        "recommended_route": "somark" if classification in ("scan", "large") else "local",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify PDF for read routing")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--min-chars", type=int, default=MIN_CHARS)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        print(json.dumps({"error": f"not found: {pdf_path}"}, ensure_ascii=False))
        sys.exit(1)

    result = classify(pdf_path, args.min_chars)
    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
    print(out)

    if result.get("classification") == "oversized":
        sys.exit(2)


if __name__ == "__main__":
    main()
