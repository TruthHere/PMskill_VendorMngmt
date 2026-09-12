#!/usr/bin/env python3
"""Grade fulfillment-card outputs against format + quality assertions.

See evals/GRADING_RULES.md for the human-readable rulebook.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from render_card import (  # noqa: E402
    is_gc_package,
    validate_rendered_card,
)

_SKILL1_SCRIPTS = SKILL_ROOT.parent / "contract-fulfillment-struct" / "scripts"
if str(_SKILL1_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL1_SCRIPTS))
from _foundation import foundation_scripts  # noqa: E402

_FOUNDATION = foundation_scripts(Path(__file__))
if str(_FOUNDATION) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION))

from common import CARD_DATA_FILENAME, CARD_FILENAME, load_json  # noqa: E402

FORMAT_ASSERTIONS = {
    "card HTML exists",
    "card-data.json exists",
    "card-title is supplier_name",
    "package-name appears in subtitle",
    "payment nodes render as payment-table",
    "card has no change section",
    "data_sources live in footer-meta",
    "claim link points to 请款申请.html",
    "no unresolved template placeholders",
    "validate_rendered_card passes",
    "GC shows 约束条款 section",
    "non-GC hides 约束条款 section",
    "payment_attachments appear in table",
    "empty payment_nodes show 待补充 row",
}

QUALITY_ASSERTIONS = {
    "supplier_name is non-empty",
    "payment node names are bilingual",
    "payment pct sum is about 100%",
    "total_amount marks 含税 or 不含税",
    "each payment node has attachments after enrich",
    "schedule_window column when windows present",
    "change item rows match card-data",
    # Soft gate: render OK, but must surface reminders
    "quality_ok is true",
    "no quality warnings when data is good",
    "quality_ok is false when data is poor",
    "quality warnings recorded when data is poor",
    "quality banner visible when warnings present",
    "quality banner sits above card header",
}

_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")
_HAS_LATIN = re.compile(r"[A-Za-z]")
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def tier_for(text: str) -> str:
    if text in QUALITY_ASSERTIONS:
        return "quality"
    return "format"


def find_package_dir(output_root: Path) -> Path | None:
    output_root = output_root.expanduser().resolve()
    direct = output_root / CARD_DATA_FILENAME
    if direct.is_file():
        return output_root
    candidates = sorted(
        p
        for p in output_root.rglob(CARD_DATA_FILENAME)
        if p.is_file() and p.parent.is_dir()
    )
    if candidates:
        return candidates[0].parent
    # naive without_skill may only have HTML
    html_only = sorted(output_root.rglob(CARD_FILENAME))
    if html_only:
        return html_only[0].parent
    return None


def is_bilingual_name(name: str) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    if "/" in text:
        left, _, right = text.partition("/")
        return bool(left.strip() and right.strip())
    return bool(_HAS_CJK.search(text) and _HAS_LATIN.search(text))


def parse_pct_sum(nodes: list[dict]) -> float | None:
    if not nodes:
        return None
    total = 0.0
    for node in nodes:
        raw = str(node.get("pct") or "")
        match = _PCT.search(raw)
        if not match:
            return None
        total += float(match.group(1))
    return total


def amount_has_tax_mark(amount: str) -> bool:
    text = (amount or "").lower()
    markers = ("含税", "不含税", "incl", "vat", "before vat", "after vat", "tax incl", "tax excl")
    return any(m in text for m in markers)


def grade_package(
    package_dir: Path | None,
    assertions: list[str],
) -> dict:
    expectations: list[dict] = []
    passed = 0

    def check(text: str, ok: bool, evidence: str) -> None:
        nonlocal passed
        if text not in assertions:
            return
        expectations.append(
            {
                "text": text,
                "passed": bool(ok),
                "evidence": evidence,
                "tier": tier_for(text),
            }
        )
        if ok:
            passed += 1

    card_data: dict = {}
    html = ""
    pkg = package_dir

    if pkg is None:
        for text in assertions:
            check(text, False, "package dir missing")
        return _result(expectations, passed, assertions)

    card_data_path = pkg / CARD_DATA_FILENAME
    card_html_path = pkg / CARD_FILENAME
    card_data = load_json(card_data_path, {}) if card_data_path.is_file() else {}
    html = card_html_path.read_text(encoding="utf-8") if card_html_path.is_file() else ""

    supplier = str(card_data.get("supplier_name") or "").strip()
    package = str(card_data.get("package_name") or "").strip()
    nodes = list(card_data.get("payment_nodes") or [])

    check("card HTML exists", card_html_path.is_file() and bool(html.strip()), str(card_html_path))
    check("card-data.json exists", card_data_path.is_file(), str(card_data_path))

    check(
        "card-title is supplier_name",
        bool(supplier) and f'<h1 class="card-title">{_esc(supplier)}</h1>' in html,
        f"supplier={supplier or 'empty'}",
    )
    check(
        "package-name appears in subtitle",
        bool(package) and f'class="package-name">{_esc(package)}</span>' in html,
        f"package={package or 'empty'}",
    )
    check(
        "payment nodes render as payment-table",
        'class="data-table payment-table"' in html,
        "found" if "payment-table" in html else "missing",
    )
    check(
        "card has no change section",
        "变更内容" not in html and "change-table" not in html,
        "found change UI" if ("变更内容" in html or "change-table" in html) else "clean",
    )
    check(
        "data_sources live in footer-meta",
        'class="footer-meta"' in html and "数据来源" in html,
        "found" if "footer-meta" in html else "missing",
    )
    # Claim link: real cards always point to sibling claim form; naive may omit.
    check(
        "claim link points to 请款申请.html",
        'href="请款申请.html"' in html and "发起请款" in html,
        "found" if "请款申请.html" in html else "missing",
    )
    check(
        "no unresolved template placeholders",
        "{{" not in html,
        "clean" if "{{" not in html else "has {{",
    )

    if card_html_path.is_file() and card_data:
        errors = validate_rendered_card(html, card_data)
        check(
            "validate_rendered_card passes",
            not errors,
            "ok" if not errors else "; ".join(errors[:3]),
        )
    else:
        check("validate_rendered_card passes", False, "missing html or card-data")

    is_gc = is_gc_package(card_data) if card_data else False
    has_constraint = "约束条款" in html
    check(
        "GC shows 约束条款 section",
        is_gc and has_constraint,
        f"is_gc={is_gc} has_section={has_constraint}",
    )
    check(
        "non-GC hides 约束条款 section",
        (not is_gc) and (not has_constraint),
        f"is_gc={is_gc} has_section={has_constraint}",
    )

    # Attachments: if any node declares/enrich has attachments, they should appear in HTML.
    attachment_texts = [
        str(n.get("payment_attachments") or "").strip()
        for n in nodes
        if str(n.get("payment_attachments") or "").strip()
    ]
    if attachment_texts:
        ok_att = all(_esc(t) in html or t in html for t in attachment_texts)
        check(
            "payment_attachments appear in table",
            ok_att,
            f"nodes_with_attachments={len(attachment_texts)}",
        )
    else:
        check(
            "payment_attachments appear in table",
            False,
            "no payment_attachments in card-data after render",
        )

    check(
        "empty payment_nodes show 待补充 row",
        (not nodes) and ("待补充" in html) and ("payment-table" in html),
        f"nodes={len(nodes)}",
    )

    # --- quality (data) + soft warning gate ---
    warnings = card_data.get("quality_warnings")
    if not isinstance(warnings, list):
        warnings = []
    q_ok = card_data.get("quality_ok")
    has_banner = (
        'class="quality-banner"' in html
        or "数据不够清晰" in html
        or "数据质量提醒" in html
    )
    # Banner should sit above the card header when warnings exist (ignore CSS rules)
    banner_before_header = False
    marker = 'class="quality-banner"'
    header_marker = 'class="card-header"'
    if has_banner and marker in html and header_marker in html:
        banner_before_header = html.find(marker) < html.find(header_marker)

    check("quality_ok is true", q_ok is True and len(warnings) == 0, f"quality_ok={q_ok} n={len(warnings)}")
    check(
        "no quality warnings when data is good",
        q_ok is True and len(warnings) == 0 and not has_banner,
        f"warnings={len(warnings)} banner={has_banner}",
    )
    check(
        "quality_ok is false when data is poor",
        q_ok is False and len(warnings) > 0,
        f"quality_ok={q_ok} n={len(warnings)}",
    )
    check(
        "quality warnings recorded when data is poor",
        len(warnings) > 0 and all(str(w.get("message") or "").strip() for w in warnings),
        f"n={len(warnings)} codes={[w.get('code') for w in warnings[:6]]}",
    )
    check(
        "quality banner visible when warnings present",
        len(warnings) > 0 and has_banner,
        f"warnings={len(warnings)} banner={has_banner}",
    )
    check(
        "quality banner sits above card header",
        len(warnings) > 0 and banner_before_header,
        f"before_header={banner_before_header}",
    )

    check("supplier_name is non-empty", bool(supplier), supplier or "empty")

    if nodes:
        bilingual_ok = all(is_bilingual_name(str(n.get("name") or "")) for n in nodes)
        check(
            "payment node names are bilingual",
            bilingual_ok,
            ", ".join(str(n.get("name") or "") for n in nodes)[:160],
        )
        pct_sum = parse_pct_sum(nodes)
        check(
            "payment pct sum is about 100%",
            pct_sum is not None and abs(pct_sum - 100.0) <= 1.0,
            f"sum={pct_sum}",
        )
        all_att = all(str(n.get("payment_attachments") or "").strip() for n in nodes)
        check(
            "each payment node has attachments after enrich",
            all_att,
            "ok" if all_att else "some nodes missing attachments",
        )
    else:
        check("payment node names are bilingual", False, "no payment_nodes")
        check("payment pct sum is about 100%", False, "no payment_nodes")
        check("each payment node has attachments after enrich", False, "no payment_nodes")

    amount = str(card_data.get("total_amount") or "")
    check(
        "total_amount marks 含税 or 不含税",
        amount_has_tax_mark(amount),
        amount or "empty",
    )

    has_windows = any(str(n.get("schedule_window") or "").strip() for n in nodes)
    check(
        "schedule_window column when windows present",
        (not has_windows) or ("计划时间区间" in html),
        f"has_windows={has_windows}",
    )

    # Only return expectations for requested assertions (order preserved)
    by_text = {e["text"]: e for e in expectations}
    ordered = []
    for text in assertions:
        if text in by_text:
            ordered.append(by_text[text])
        else:
            ordered.append(
                {
                    "text": text,
                    "passed": False,
                    "evidence": "assertion not implemented in grade_card",
                    "tier": tier_for(text),
                }
            )
    passed = sum(1 for e in ordered if e["passed"])
    return _result(ordered, passed, assertions)


def _esc(value: str) -> str:
    import html as html_lib

    return html_lib.escape(str(value or ""), quote=False)


def _result(expectations: list[dict], passed: int, assertions: list[str]) -> dict:
    format_items = [e for e in expectations if e.get("tier") == "format"]
    quality_items = [e for e in expectations if e.get("tier") == "quality"]
    return {
        "expectations": expectations,
        "passed": passed,
        "total": len(assertions),
        "pass_rate": round(passed / len(assertions), 4) if assertions else 0.0,
        "format": {
            "passed": sum(1 for e in format_items if e["passed"]),
            "total": len(format_items),
            "pass_rate": round(
                sum(1 for e in format_items if e["passed"]) / len(format_items), 4
            )
            if format_items
            else None,
        },
        "quality": {
            "passed": sum(1 for e in quality_items if e["passed"]),
            "total": len(quality_items),
            "pass_rate": round(
                sum(1 for e in quality_items if e["passed"]) / len(quality_items), 4
            )
            if quality_items
            else None,
        },
    }


def grade_run(output_root: Path, assertions: list[str]) -> dict:
    pkg = find_package_dir(output_root)
    result = grade_package(pkg, assertions)
    out = output_root.expanduser().resolve()
    grading_path = out / "grading.json"
    grading_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade fulfillment-card eval output")
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--assertions-json",
        default="",
        help="JSON array of assertion strings; default = all known assertions",
    )
    args = parser.parse_args()
    if args.assertions_json:
        assertions = json.loads(Path(args.assertions_json).read_text(encoding="utf-8"))
    else:
        assertions = sorted(FORMAT_ASSERTIONS | QUALITY_ASSERTIONS)
    result = grade_run(Path(args.output_root), assertions)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
