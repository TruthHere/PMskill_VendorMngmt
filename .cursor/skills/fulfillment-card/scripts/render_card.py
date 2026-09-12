#!/usr/bin/env python3
"""Render or incrementally update fulfillment card HTML from card-data.json."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_ROOT = SKILL_ROOT.parent
_SKILL1_SCRIPTS = _SKILLS_ROOT / "contract-fulfillment-struct" / "scripts"
if str(_SKILL1_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SKILL1_SCRIPTS))
from _foundation import foundation_scripts  # noqa: E402

_FOUNDATION_SCRIPTS = foundation_scripts(Path(__file__))
if str(_FOUNDATION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION_SCRIPTS))

from common import (  # noqa: E402
    CARD_DATA_FILENAME,
    CARD_FILENAME,
    deep_merge,
    enrich_payment_nodes,
    load_critical_nodes,
    load_json,
    load_project_schedule,
    resolve_project_root_from_package,
    save_json,
)
from card_quality import assess_card_quality, quality_ok  # noqa: E402

DEFAULT_TEMPLATE = SKILL_ROOT / "assets" / "fulfillment-card.html"

# Canonical template markers — see references/card-template.md
_TEMPLATE_REQUIRED_SNIPPETS = (
    '<h1 class="card-title">{{supplier_name}}</h1>',
    'class="package-name">{{package_name}}',
    'class="footer-meta"',
    "{{payment_nodes_html}}",
    "{{quality_banner_html}}",
)
_TEMPLATE_FORBIDDEN_SNIPPETS = (
    '<h1 class="card-title">{{package_name}}</h1>',
    '<p class="card-sub">{{supplier_name}}</p>',
    "{{payment_flow_class}}",
)


def validate_template(template_path: Path) -> list[str]:
    text = template_path.read_text(encoding="utf-8")
    errors: list[str] = []
    for snippet in _TEMPLATE_REQUIRED_SNIPPETS:
        if snippet not in text:
            errors.append(f"template missing required marker: {snippet!r}")
    for snippet in _TEMPLATE_FORBIDDEN_SNIPPETS:
        if snippet in text:
            errors.append(f"template uses forbidden legacy marker: {snippet!r}")
    return errors


def validate_rendered_card(html_out: str, card_data: dict) -> list[str]:
    """Ensure rendered HTML matches mandatory card format."""
    errors: list[str] = []
    supplier = escape_text(card_data.get("supplier_name", ""))
    package = escape_text(card_data.get("package_name", ""))

    if "{{" in html_out:
        errors.append("unresolved template placeholders in output")

    if supplier and f'<h1 class="card-title">{supplier}</h1>' not in html_out:
        errors.append("card-title must be supplier_name (not package_name)")

    if package and f'class="package-name">{package}</span>' not in html_out:
        errors.append("package_name must appear in subtitle package-name span")

    if package and supplier and f'<h1 class="card-title">{package}</h1>' in html_out:
        errors.append("legacy header: package_name used as card-title")

    if 'class="footer-meta"' not in html_out:
        errors.append("missing footer-meta (data_sources must be in footer)")

    if 'class="data-table payment-table"' not in html_out:
        errors.append("payment nodes must render as payment-table")

    if "变更内容" in html_out or "change-table" in html_out:
        errors.append("履约卡片不应再展示变更内容（变更只在 Change Log）")

    nodes = card_data.get("payment_nodes") or []
    if nodes:
        for node in nodes:
            attachments = str(node.get("payment_attachments") or "").strip()
            if attachments and escape_text(attachments) not in html_out:
                errors.append(
                    f"payment_attachments missing in table for node {node.get('name', '')!r}"
                )
                break

    is_gc = is_gc_package(card_data)
    has_constraint = "约束条款" in html_out
    if is_gc and not has_constraint:
        errors.append("总包卡片缺少约束条款章节")
    if not is_gc and has_constraint:
        errors.append("非总包卡片不应出现约束条款章节")

    warnings = card_data.get("quality_warnings")
    if isinstance(warnings, list) and warnings:
        if 'class="quality-banner"' not in html_out and "数据不够清晰" not in html_out:
            errors.append("quality_warnings 非空但卡片缺少数据质量提醒横幅")
    if card_data.get("quality_ok") is True and (
        'class="quality-banner"' in html_out or "数据不够清晰" in html_out
    ):
        errors.append("quality_ok 为 true 但卡片仍显示数据质量提醒")

    return errors


def escape_text(value: str) -> str:
    return html.escape(str(value or ""), quote=False)


def _cell_multiline(value: str) -> str:
    text = escape_text(value).replace("\n", "<br>")
    return text or "—"


def _payment_enrichment_kwargs(
    package_dir: Path | None,
    card_data: dict,
) -> dict:
    schedule_milestones: list[dict[str, str]] = []
    critical_nodes: list[dict] = []
    if package_dir is not None:
        project_root = resolve_project_root_from_package(package_dir)
        if project_root is not None:
            schedule_milestones = load_project_schedule(project_root)
            critical_nodes = load_critical_nodes(project_root)
    return {
        "package_type": str(card_data.get("package_type", "")).strip(),
        "schedule_milestones": schedule_milestones,
        "critical_nodes": critical_nodes,
        "package_name": str(card_data.get("package_name", "")).strip(),
        "delivery_schedule": str(card_data.get("delivery_schedule", "")).strip(),
    }


def render_payment_nodes_table(
    nodes: list[dict],
    *,
    package_type: str = "",
    schedule_milestones: list[dict[str, str]] | None = None,
    package_name: str = "",
    delivery_schedule: str = "",
    critical_nodes: list[dict] | None = None,
    enriched_nodes: list[dict] | None = None,
) -> str:
    if enriched_nodes is not None:
        enriched = enriched_nodes
    else:
        enriched = enrich_payment_nodes(
            nodes,
            package_type=package_type,
            schedule_milestones=schedule_milestones,
            package_name=package_name,
            delivery_schedule=delivery_schedule,
            critical_nodes=critical_nodes,
        )
    show_schedule = (
        bool(schedule_milestones)
        or bool(critical_nodes)
        or any(str(node.get("schedule_window") or "").strip() for node in enriched)
    )
    schedule_header = "<th>计划时间区间</th>" if show_schedule else ""
    colspan = "5" if show_schedule else "4"

    if not enriched:
        return (
            '<table class="data-table payment-table">'
            "<thead><tr>"
            f"<th>节点</th><th>比例</th><th>触发条件</th>{schedule_header}<th>请款附件</th>"
            "</tr></thead>"
            f'<tbody><tr class="data-table-empty">'
            f'<td colspan="{colspan}">待补充</td></tr></tbody></table>'
        )

    rows = []
    for node in enriched:
        name = escape_text(node.get("name", ""))
        pct = escape_text(node.get("pct", ""))
        condition = str(node.get("condition", "")).strip()
        milestone = str(node.get("milestone", "")).strip()
        source = str(node.get("source", "")).strip()
        if milestone:
            condition = f"{condition}\n里程碑：{milestone}" if condition else f"里程碑：{milestone}"
        if source:
            condition = f"{condition}\n来源：{source}" if condition else f"来源：{source}"
        schedule_window = escape_text(str(node.get("schedule_window") or "").strip()) or "—"
        attachments = str(node.get("payment_attachments", "")).strip()
        schedule_cell = f"<td>{schedule_window}</td>" if show_schedule else ""
        rows.append(
            "<tr>"
            f"<td>{name or '—'}</td>"
            f'<td class="col-pct">{pct or "—"}</td>'
            f"<td>{_cell_multiline(condition)}</td>"
            f"{schedule_cell}"
            f"<td>{_cell_multiline(attachments)}</td>"
            "</tr>"
        )

    return (
        '<table class="data-table payment-table">'
        "<thead><tr>"
        f"<th>节点</th><th>比例</th><th>触发条件</th>{schedule_header}<th>请款附件</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def normalize_change_item(item: object) -> dict[str, str]:
    """Legacy helper kept for old card-data; 变更已迁至 Change Log，渲染不再使用。"""
    if isinstance(item, str):
        return {"number": "", "content": item, "confirmed_amount": ""}
    if isinstance(item, dict):
        return {
            "number": str(
                item.get("number")
                or item.get("cot_no")
                or item.get("change_no")
                or item.get("title")
                or ""
            ).strip(),
            "content": str(item.get("content") or item.get("detail") or "").strip(),
            "confirmed_amount": str(
                item.get("confirmed_amount") or item.get("amount") or ""
            ).strip(),
        }
    return {"number": "", "content": str(item), "confirmed_amount": ""}


def render_change_items_table(items: list) -> str:
    """变更不再写入履约卡片；占位恒为空。"""
    return ""


def render_acceptance_items(items: list) -> str:
    if not items:
        return (
            '<div class="acc-item">'
            '<span class="acc-check" aria-hidden="true">✓</span>'
            "<span>待补充</span></div>"
        )
    parts = []
    for item in items:
        parts.append(
            '<div class="acc-item">'
            '<span class="acc-check" aria-hidden="true">✓</span>'
            f"<span>{escape_text(item)}</span></div>"
        )
    return "\n        ".join(parts)


def is_gc_package(card_data: dict) -> bool:
    package_type = str(card_data.get("package_type", "")).strip()
    package_type_label = str(card_data.get("package_type_label", "")).strip()
    return package_type == "总包" or package_type_label == "总包"


def _render_constraint_clauses(value: str) -> str:
    text = str(value or "").strip()
    if not text or text == "—":
        return '<div class="constraint-box empty">—</div>'
    return f'<div class="constraint-box">{escape_text(text)}</div>'


def render_constraint_section(card_data: dict) -> str:
    if not is_gc_package(card_data):
        return ""
    return (
        '<section class="section">\n'
        '        <div class="section-head">\n'
        '          <span class="section-dot constraint"></span>\n'
        '          <h2 class="section-title">约束条款</h2>\n'
        "        </div>\n"
        f"        {_render_constraint_clauses(card_data.get('constraint_clauses', ''))}\n"
        "      </section>"
    )


def render_quality_banner(warnings: list[dict]) -> str:
    """Top-of-card reminder when data quality is poor. Empty string when OK.

    Reminder lives only on the card — do not push these into pending.json.
    """
    if not warnings:
        return ""
    items = []
    for warning in warnings:
        message = escape_text(str(warning.get("message") or warning.get("code") or ""))
        field = escape_text(str(warning.get("field") or "").strip())
        label = f'<span class="quality-field">{field}</span> ' if field else ""
        items.append(f"<li>{label}{message}</li>")
    count = len(warnings)
    return (
        '<div class="quality-banner" role="status" aria-live="polite" data-quality="warn">'
        '<div class="quality-banner-title">'
        '<span class="quality-banner-icon" aria-hidden="true">!</span>'
        f"<span>数据不够清晰（{count} 项）</span>"
        "</div>"
        "<p>卡片已生成，可先查阅。下列字段请核对修正后重新渲染（提醒仅在本卡片顶部）。</p>"
        f"<ul>{''.join(items)}</ul>"
        "</div>"
    )


def render_card_html(
    card_data: dict,
    template_path: Path,
    *,
    package_dir: Path | None = None,
    quality_warnings: list[dict] | None = None,
) -> str:
    template = template_path.read_text(encoding="utf-8")
    enrichment = _payment_enrichment_kwargs(package_dir, card_data)
    nodes = enrich_payment_nodes(
        card_data.get("payment_nodes", []),
        **enrichment,
    )
    card_data = {**card_data, "payment_nodes": nodes}
    warnings = (
        list(quality_warnings)
        if quality_warnings is not None
        else assess_card_quality(card_data)
    )

    replacements = {
        "{{package_type_label}}": escape_text(card_data.get("package_type_label", "")),
        "{{package_name}}": escape_text(card_data.get("package_name", "")),
        "{{supplier_name}}": escape_text(card_data.get("supplier_name", "")),
        "{{project_name}}": escape_text(card_data.get("project_name", "")),
        "{{contact_email}}": escape_text(card_data.get("contact_email", "")) or "—",
        "{{total_amount}}": escape_text(card_data.get("total_amount", "")) or "—",
        "{{contract_or_quote_no}}": escape_text(
            card_data.get("contract_or_quote_no", "")
        )
        or "—",
        "{{contract_or_quote_date}}": escape_text(
            card_data.get("contract_or_quote_date", "")
        )
        or "—",
        "{{scope_summary}}": escape_text(card_data.get("scope_summary", "")) or "—",
        "{{delivery_schedule}}": escape_text(card_data.get("delivery_schedule", "")) or "—",
        "{{quality_banner_html}}": render_quality_banner(warnings),
        "{{payment_nodes_html}}": render_payment_nodes_table(
            nodes,
            enriched_nodes=nodes,
            **enrichment,
        ),
        "{{change_items_html}}": render_change_items_table(
            card_data.get("change_items", [])
        ),
        "{{acceptance_items_html}}": render_acceptance_items(
            card_data.get("acceptance_items", [])
        ),
        "{{constraint_section_html}}": render_constraint_section(card_data),
        "{{data_sources}}": escape_text(card_data.get("data_sources", "")) or "—",
    }
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def patch_and_render(
    package_dir: Path,
    patch: dict,
    *,
    template_path: Path | None = None,
) -> dict:
    package_dir = package_dir.expanduser().resolve()
    card_data_path = package_dir / CARD_DATA_FILENAME
    card_path = package_dir / CARD_FILENAME
    template = template_path or DEFAULT_TEMPLATE

    template_errors = validate_template(template)
    if template_errors:
        raise RuntimeError(
            "fulfillment card template invalid:\n- "
            + "\n- ".join(template_errors)
            + f"\nSee {SKILL_ROOT / 'references/card-template.md'}"
        )

    existing = load_json(card_data_path, {})
    merged = deep_merge(existing, patch)
    enrichment = _payment_enrichment_kwargs(package_dir, merged)
    if merged.get("payment_nodes"):
        merged["payment_nodes"] = enrich_payment_nodes(
            merged["payment_nodes"],
            **enrichment,
        )
    # Soft quality gate: always render, but record + surface warnings
    warnings = assess_card_quality(merged)
    merged["quality_warnings"] = warnings
    merged["quality_ok"] = quality_ok(warnings)
    save_json(card_data_path, merged)

    html_out = render_card_html(
        merged,
        template,
        package_dir=package_dir,
        quality_warnings=warnings,
    )
    render_errors = validate_rendered_card(html_out, merged)
    if render_errors:
        raise RuntimeError(
            "fulfillment card render failed format check:\n- "
            + "\n- ".join(render_errors)
            + f"\nSee {SKILL_ROOT / 'references/card-template.md'}"
        )

    card_path.write_text(html_out, encoding="utf-8")

    # 请款申请页归 payment-form；渲卡片后自动刷页（编排表 A，禁止再手跑一遍）
    import sys

    _pf_scripts = SKILL_ROOT.parent / "payment-form" / "scripts"
    if str(_pf_scripts) not in sys.path:
        sys.path.insert(0, str(_pf_scripts))
    from sync_claim_form import sync_claim_form  # payment-form

    claim_path = sync_claim_form(package_dir)
    did = ["fulfillment-card.render", "payment-form.sync"]

    return {
        "card_data_path": str(card_data_path),
        "card_path": str(card_path),
        "card_data": merged,
        "format_valid": True,
        "quality_ok": merged["quality_ok"],
        "quality_warnings": warnings,
        "claim_form_path": str(claim_path),
        "needs_claim_sync": False,
        "did": did,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render fulfillment card HTML")
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--patch", default="{}", help="JSON patch to merge into card-data.json")
    parser.add_argument("--template", default=None, help="Optional template path")
    args = parser.parse_args()

    patch = json.loads(args.patch)
    template = Path(args.template) if args.template else None
    result = patch_and_render(Path(args.package_dir), patch, template_path=template)
    print(
        json.dumps(
            {
                "card_path": result["card_path"],
                "card_data_path": result["card_data_path"],
                "claim_form_path": result.get("claim_form_path"),
                "needs_claim_sync": result.get("needs_claim_sync", False),
                "quality_ok": result.get("quality_ok"),
                "quality_warnings": result.get("quality_warnings") or [],
                "did": result.get("did") or [],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
