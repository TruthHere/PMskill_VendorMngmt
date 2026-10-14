#!/usr/bin/env python3
"""从已读出的合同/报价正文抽付款节点候选（启发式，须 PM 确认）。

不读 PDF。PDF 正文由 read-pdf/scripts/read_pdf.py 产出后再交给本脚本。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PAYMENT_HINTS = (
    "付款",
    "预付款",
    "进度款",
    "保留金",
    "尾款",
    "payment",
    "advance",
    "retention",
    "合同金额",
    "误期",
)


def heuristic_payment_nodes(text: str) -> list[dict]:
    """Lightweight candidates for LLM / PM confirmation — not legal truth."""
    nodes: list[dict] = []
    patterns = [
        (r"预付款[^\n%]{0,40}?(\d{1,3})\s*%", "预付款"),
        (r"保留金[^\n%]{0,40}?(\d{1,3})\s*%", "保留金"),
        (r"Advance\s*Payment[^\n%]{0,40}?(\d{1,3})\s*%", "预付款", re.I),
        (r"Retention[^\n%]{0,40}?(\d{1,3})\s*%", "保留金", re.I),
    ]
    seen = set()
    for item in patterns:
        if len(item) == 3:
            pat, name, flags = item
        else:
            pat, name = item
            flags = 0
        m = re.search(pat, text, flags)
        if m and name not in seen:
            seen.add(name)
            nodes.append(
                {
                    "name": name,
                    "pct": f"{m.group(1)}%",
                    "condition": "待核对合同原文",
                    "source": "合同提取",
                }
            )

    for m in re.finditer(r"累计[^\d]{0,6}(\d{1,3})\s*%", text):
        pct = f"累计至{m.group(1)}%"
        key = f"进度款-{pct}"
        if key not in seen:
            seen.add(key)
            nodes.append(
                {
                    "name": "进度款",
                    "pct": pct,
                    "condition": "达到附件进度节点后申请",
                    "source": "合同提取",
                }
            )
    return nodes


def extract_amount(text: str) -> str | None:
    m = re.search(
        r"(?:合同金额|合同总价|Contract\s*Amount)[^\n]{0,40}?(?:RMB|¥|CNY)?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.I,
    )
    if m:
        return m.group(1).replace(",", "")
    m = re.search(r"RMB\s*([\d,]+(?:\.\d+)?)", text)
    return m.group(1).replace(",", "") if m else None


def payment_hint_pages(text: str) -> list[int]:
    pages: list[int] = []
    current = None
    for line in text.splitlines():
        m = re.match(r"^--- page (\d+) ---$", line.strip())
        if m:
            current = int(m.group(1))
            continue
        if current is None:
            continue
        if any(h.lower() in line.lower() for h in PAYMENT_HINTS):
            if current not in pages:
                pages.append(current)
    return pages


def build_analysis_result(
    combined: str,
    *,
    source: str = "unknown",
    pdf: str | None = None,
    page_count: int | None = None,
    is_scan_likely: bool | None = None,
) -> dict:
    """Contract heuristics on pre-read text (from read-pdf JSON)."""
    return {
        "contract_amount_guess": extract_amount(combined),
        "payment_nodes": heuristic_payment_nodes(combined),
        "payment_hint_pages": payment_hint_pages(combined),
        "text_excerpt": combined[:12000],
        "source": source,
        "pdf": pdf,
        "page_count": page_count,
        "is_scan_likely": is_scan_likely,
        "notes": [
            "payment_nodes 为启发式候选，须 PM 确认后写入卡片",
            "总包滚动进度款核验归 Skill 2",
            "正文来自 read-pdf，本脚本不读 PDF",
        ],
    }


def load_text_from_read_json(path: Path) -> tuple[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("error"):
        raise ValueError(f"read-pdf failed: {data['error']}")
    text = data.get("text") or data.get("markdown") or ""
    meta = {
        "source": data.get("source", "unknown"),
        "pdf": data.get("pdf"),
        "page_count": data.get("page_count"),
        "is_scan_likely": data.get("is_scan_likely"),
    }
    return text, meta


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract payment-node candidates from read-pdf JSON or plain text"
    )
    parser.add_argument(
        "--read-json",
        default="",
        help="read-pdf/scripts/read_pdf.py 产出的 JSON",
    )
    parser.add_argument(
        "--text",
        default="",
        help="直接喂正文（调试用；正式路径用 --read-json）",
    )
    parser.add_argument("--out", default="", help="Optional JSON output path")
    args = parser.parse_args()

    if args.read_json:
        json_path = Path(args.read_json).expanduser().resolve()
        if not json_path.exists():
            print(json.dumps({"error": f"not found: {json_path}"}, ensure_ascii=False))
            sys.exit(1)
        try:
            combined, meta = load_text_from_read_json(json_path)
        except (json.JSONDecodeError, ValueError) as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            sys.exit(1)
        result = build_analysis_result(combined, **meta)
    elif args.text:
        text_path = Path(args.text).expanduser().resolve()
        if text_path.is_file():
            combined = text_path.read_text(encoding="utf-8", errors="replace")
        else:
            combined = args.text
        result = build_analysis_result(combined, source="text")
    else:
        print(
            json.dumps(
                {
                    "error": "need --read-json (read-pdf output) or --text",
                    "hint": "先跑 read-pdf/scripts/read_pdf.py，再把 JSON 交给本脚本",
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
