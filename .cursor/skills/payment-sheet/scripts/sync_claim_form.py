#!/usr/bin/env python3
"""Sync package-local 请款申请.html from card-data + Tracker 请款章节 + project.json.

Reads ledger only to seed Excel previous-claim lines. Does not estimate claim amounts.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
from _foundation import foundation_scripts, prepend_sys_path  # noqa: E402

prepend_sys_path(foundation_scripts(Path(__file__)))
prepend_sys_path(_SCRIPTS)

from common import confirmed_changes_total_excl_tax, find_package, load_tracker_packages  # noqa: E402
from template_profile import DISABLED_NOTICE, resolve_assets  # noqa: E402

TEMPLATE = SKILL_ROOT / "assets" / "claim-form.html"
DISABLED_TEMPLATE = SKILL_ROOT / "assets" / "claim-form-disabled.html"
JSZIP_JS = SKILL_ROOT / "assets" / "vendor" / "jszip.min.js"
FILL_INSERT_JS = SKILL_ROOT / "assets" / "fill-insert-xlsx.js"
FILL_GENERIC_JS = SKILL_ROOT / "assets" / "fill-xlsx.js"
CLAIM_FORM_NAME = "请款申请.html"
CLAIM_ASSETS_DIR = ".claim-assets"

# 填写页附件提醒（按节点；发票在客户批复请款后开，不读卡片 payment_attachments）
_EMPTY_FILES_HINT = "本节点无需随单附件。"
_ADVANCE_FILES_HINT = "预付款无需随单附件。客户批复请款后再开发票。"
_DELIVERY_FILES_HINT = "到货款请附到货签认单。勾选只提醒你别漏文件，不会生成附件包。客户批复请款后再开发票。"
_ACCEPT_FILES_HINT = "验收款请附验收确认单。勾选只提醒你别漏文件，不会生成附件包。客户批复请款后再开发票。"


def _vendor_fields_html(fields: list) -> str:
    if not fields:
        return (
            '<p class="section-hint">还没有对照客户模板的抬头字段。'
            "把客户请款单交给我认模板后，这里会出现要填的格子。</p>"
        )
    parts: list[str] = []
    for f in fields:
        key = str(f.get("key") or "").strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        label = html.escape(str(f.get("label") or key))
        en = str(f.get("label_en") or "").strip()
        en_html = f'<span class="en">{html.escape(en)}</span>' if en else ""
        req = '<span class="req">必填</span>' if f.get("required") else '<span class="opt">可空</span>'
        mode = str(f.get("inputmode") or "").strip()
        mode_attr = f' inputmode="{html.escape(mode)}"' if mode else ""
        ph = html.escape(str(f.get("placeholder") or ""))
        wrap = ' class="full"' if f.get("full") else ""
        if str(f.get("input") or "") == "textarea":
            rows = int(f.get("rows") or 3)
            field = (
                f'<textarea id="{key}" rows="{rows}" placeholder="{ph}"></textarea>'
            )
        else:
            field = (
                f'<input id="{key}" value="" autocomplete="off" placeholder="{ph}"{mode_attr}>'
            )
        parts.append(
            f"<div{wrap}>"
            f'<label class="field-label" for="{key}">{label} {en_html} {req}</label>'
            f"{field}"
            "</div>"
        )
    return "\n          ".join(parts)


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _node_attachment_hints(node_name: str) -> tuple[list[str], str]:
    name = node_name or ""
    if re.search(r"预付|advance", name, re.I):
        return [], _ADVANCE_FILES_HINT
    if re.search(r"到货|delivery", name, re.I):
        return ["到货签认单"], _DELIVERY_FILES_HINT
    if re.search(r"验收|accept|移交|handover", name, re.I):
        return ["验收确认单"], _ACCEPT_FILES_HINT
    return [], _EMPTY_FILES_HINT


def _project_root(package_dir: Path) -> Path | None:
    cur = package_dir.resolve()
    for p in [cur] + list(cur.parents):
        if (p / ".skill" / "project.json").is_file() or (p / ".skill").is_dir():
            if (p / ".skill").is_dir():
                return p
    return None


def _money(value) -> float | None:
    if value is None or value == "":
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)", str(value).replace(" ", "").replace("¥", "").replace("￥", ""))
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _fmt_money(v: float | None) -> str:
    if v is None:
        return ""
    text = f"{v:,.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _scale_to_incl(amount_excl, excl, incl) -> float | None:
    """Convert an 不含税 figure to 含税 using this package's Tracker ratio. No default rate."""
    if amount_excl is None:
        return None
    if excl is None or incl is None:
        return None
    try:
        excl_f = float(excl)
        incl_f = float(incl)
        amt = float(amount_excl)
    except (TypeError, ValueError):
        return None
    if excl_f <= 0:
        return None
    return round(amt * (incl_f / excl_f), 2)


def _payment_terms(nodes: list) -> str:
    parts = []
    for node in nodes:
        name = str(node.get("name") or "").strip()
        if not name:
            continue
        pct = str(node.get("pct") or "").strip()
        cond = str(node.get("condition") or "").strip()
        chunk = name
        if pct:
            chunk += f" {pct}"
        if cond:
            chunk += f"（{cond}）"
        parts.append(chunk)
    return "；".join(parts)


def _vat_pct_from_amounts(excl, incl) -> int | float | None:
    """Package VAT % from Tracker 金额含税 / 金额不含税. No project-wide default."""
    if excl is None or incl is None:
        return None
    try:
        excl_f = float(excl)
        incl_f = float(incl)
    except (TypeError, ValueError):
        return None
    if excl_f <= 0:
        return None
    rate = (incl_f / excl_f - 1.0) * 100.0
    if rate < -0.05:
        return None
    nearest = round(rate)
    if abs(rate - nearest) <= 0.2:
        return int(nearest)
    return round(rate, 1)


def _ledger_completed(package_dir: Path) -> list[dict]:
    """既往请款行：不再读 payment_ledger；仅用 Tracker「已请金额」合成一行。"""
    return []


def _variations_total(package_dir: Path, card: dict) -> float:
    root = _project_root(package_dir)
    name = str(card.get("package_name") or "").strip()
    if root is None or not name:
        return 0.0
    return confirmed_changes_total_excl_tax(root, name)


def _tracker_row(package_dir: Path, card: dict) -> dict:
    root = _project_root(package_dir)
    if root is None:
        return {}
    try:
        packages = load_tracker_packages(root)
    except Exception:
        return {}
    name = str(card.get("package_name") or "").strip()
    if name:
        found = find_package(packages, name)
        if found:
            return found
    folder = str(package_dir.resolve())
    for pkg in packages:
        if str(pkg.get("folder_path") or "").rstrip("/") == folder:
            return pkg
    return {}


def build_context(package_dir: Path) -> dict:
    package_dir = package_dir.expanduser().resolve()
    card = _load_json(package_dir / "card-data.json")
    root = _project_root(package_dir)
    project = _load_json(root / ".skill" / "project.json") if root else {}
    tracker = _tracker_row(package_dir, card)
    xlsx_path, profile, _profile_path = resolve_assets(root)
    if xlsx_path is None or profile is None:
        raise RuntimeError(DISABLED_NOTICE)

    nodes = list(card.get("payment_nodes") or [])
    form_cfg = profile.get("form") if isinstance(profile.get("form"), dict) else {}
    amount_tax = str(profile.get("amount_tax") or form_cfg.get("amount_tax") or "excl").strip().lower()
    if amount_tax in ("incl", "incl_tax", "含税"):
        amount_tax = "incl"
    else:
        amount_tax = "excl"
    base = _money(tracker.get("amount_excl_tax"))
    incl = _money(tracker.get("amount_incl_tax"))
    claimed_amount = _money(tracker.get("claimed_amount_excl_tax"))
    claimed_incl = _scale_to_incl(claimed_amount, base, incl)
    previous_claims = _ledger_completed(package_dir)
    prev_amt = claimed_incl if amount_tax == "incl" else claimed_amount
    if not previous_claims and prev_amt:
        previous_claims = [
            {"payment_no": 0, "name": "Previously certified", "amount": prev_amt}
        ]
    variations_to_date = _variations_total(package_dir, card)
    vat = _vat_pct_from_amounts(base, incl)
    payment_terms = _payment_terms(nodes)

    overview_lines = []
    overview_rows = []
    boot_nodes = []
    options = []
    first_node = None
    for i, node in enumerate(nodes, 1):
        name = str(node.get("name") or "").strip()
        if not name:
            continue
        pct = node.get("pct") or ""
        node_payment_no = int(node.get("payment_no") or i)
        checklist, files_hint = _node_attachment_hints(name)
        overview_lines.append(f"{node_payment_no}. {name}  {pct}".rstrip())
        row_cls = "is-current" if first_node is None else ""
        overview_rows.append(
            f"<tr class=\"{row_cls}\">"
            f"<td class=\"col-no\">NO.{node_payment_no}</td>"
            f"<td>{html.escape(name)}</td>"
            f"<td class=\"col-pct\">{html.escape(str(pct))}</td>"
            "</tr>"
        )
        boot_nodes.append(
            {
                "name": name,
                "pct": pct,
                "checklist": checklist,
                "files_hint": files_hint,
                "payment_no": node_payment_no,
            }
        )
        sel = " selected" if first_node is None else ""
        options.append(
            f'<option value="{html.escape(name, quote=True)}"{sel}>{html.escape(name)}</option>'
        )
        if first_node is None:
            first_node = boot_nodes[-1]

    payment_no = int((first_node or {}).get("payment_no") or 1)
    tax_label = "含税" if amount_tax == "incl" else "不含税"
    amount_hint = f"本次请款金额须为{tax_label}，由供应商按合同自行填写。以客户请款单模板上的口径为准。"
    attachment_mode = str(form_cfg.get("attachment_mode") or "checklist")
    files_hint = (
        "每行一项，会写进付款证书「请款支持文件」。不同采购包可以写不一样的附件。"
        if attachment_mode == "lines"
        else ((first_node or {}).get("files_hint") or _EMPTY_FILES_HINT)
    )
    checklist_items = (first_node or {}).get("checklist") or []
    if checklist_items:
        checklist_html = "".join(
            f"<li><label><input type=\"checkbox\"> {html.escape(t)}</label></li>"
            for t in checklist_items
        )
    else:
        checklist_html = "<li class=\"checklist-empty\">本节点无需随单附件。</li>"

    user_fields = list(form_cfg.get("user_fields") or [])
    engine = profile.get("engine") or "cells"
    form_title = str(profile.get("title") or "请款单")
    form_title_en = str(profile.get("title_en") or "Payment Application")
    vendor_section_title = str(profile.get("vendor_section_title") or "请款单抬头（供应商填）")
    download_label = str(profile.get("download_label") or "下载请款单（Excel）")
    show_variations = form_cfg.get("show_includes_variations", True)
    contract_display = incl if amount_tax == "incl" else base

    boot = {
        "project_name": card.get("project_name") or project.get("project_name") or "",
        "division": project.get("division") or "",
        "division_code": project.get("division_code") or "",
        "billing_entity": project.get("billing_entity") or "",
        "vendor_name": card.get("supplier_name") or "",
        "work_package": card.get("package_name") or package_dir.name,
        "contract_value_excl_tax": base,
        "contract_value_incl_tax": incl,
        "claimed_amount_excl_tax": claimed_amount,
        "claimed_amount_incl_tax": claimed_incl,
        "payment_terms": payment_terms,
        "variations_to_date": variations_to_date,
        "period_count": len(boot_nodes),
        "previous_claims": previous_claims,
        "vat_note_pct": vat,
        "nodes": boot_nodes,
        "amount_hint": amount_hint,
        "amount_tax": amount_tax,
        "attachment_mode": attachment_mode,
        "engine": engine,
        "form_title": form_title,
        "download_filename": str(profile.get("download_filename") or ""),
        "user_fields": user_fields,
    }
    if (profile.get("engine") or "cells") == "cells":
        boot["profile"] = profile

    nodes_overview_html = (
        "".join(overview_rows)
        or "<tr class=\"data-table-empty\"><td colspan=\"3\">暂无付款节点</td></tr>"
    )
    dash = "—"
    if vat is None:
        vat_note_line = "本包税率未从含税/不含税算出"
        vat_note_display = dash
    else:
        vat_note_line = f"VAT {vat}%"
        vat_note_display = str(vat)
    return {
        "package_name": html.escape(str(card.get("package_name") or package_dir.name)),
        "supplier_name": html.escape(str(card.get("supplier_name") or "")),
        "project_name": html.escape(str(boot["project_name"]) or dash),
        "division": html.escape(str(boot["division"] or dash)),
        "billing_entity": html.escape(str(boot["billing_entity"] or dash)),
        "payment_no": str(payment_no),
        "contract_value_excl_tax": html.escape(_fmt_money(contract_display) or dash),
        "contract_amount_label": html.escape(f"合同金额（{tax_label}）"),
        "amount_field_label": html.escape(f"本次金额（{tax_label}）"),
        "claim_section_hint": html.escape(f"选节点、自己填{tax_label}金额。系统不代算，避免和合同对不上。"),
        "facts_amount_note": html.escape(f"金额按{tax_label}填写"),
        "type_badge": html.escape(form_title),
        "files_section_title": html.escape("请款支持文件" if attachment_mode == "lines" else "随单附件（提醒）"),
        "files_checklist_class": "is-hidden" if attachment_mode == "lines" else "",
        "files_lines_class": "" if attachment_mode == "lines" else "is-hidden",
        "vat_note_pct": vat_note_display,
        "vat_note_line": html.escape(vat_note_line),
        "nodes_overview": html.escape("\n".join(overview_lines)),
        "nodes_overview_html": nodes_overview_html,
        "node_options_html": "\n".join(options) or '<option value="">（无付款节点）</option>',
        "suggested_amount": "",
        "amount_hint": html.escape(amount_hint),
        "files_hint": html.escape(files_hint),
        "vendor_ref": "",
        "contact_name": "",
        "contact_mobile": "",
        "office_phone": "",
        "office_address": "",
        "checklist_html": checklist_html,
        "form_title": html.escape(form_title),
        "form_title_en": html.escape(form_title_en),
        "vendor_section_title": html.escape(vendor_section_title),
        "download_label": html.escape(download_label),
        "vendor_fields_html": _vendor_fields_html(user_fields),
        "variations_flag_class": "" if show_variations else "is-hidden",
        "boot_json": json.dumps(boot, ensure_ascii=False),
        "xlsx_template_b64": "",
    }


def _prepare_claim_assets(package_dir: Path) -> str:
    """Copy fill helpers next to the form; return the project/client template as base64."""
    root = _project_root(package_dir)
    xlsx_path, _profile, _ = resolve_assets(root)
    if xlsx_path is None or not xlsx_path.is_file():
        raise FileNotFoundError(DISABLED_NOTICE)
    if not JSZIP_JS.is_file():
        raise FileNotFoundError(f"missing JSZip vendor: {JSZIP_JS}")
    if not FILL_INSERT_JS.is_file():
        raise FileNotFoundError(f"missing fill helper: {FILL_INSERT_JS}")
    if not FILL_GENERIC_JS.is_file():
        raise FileNotFoundError(f"missing generic fill helper: {FILL_GENERIC_JS}")
    assets = package_dir / CLAIM_ASSETS_DIR
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(JSZIP_JS, assets / "jszip.min.js")
    shutil.copy2(FILL_INSERT_JS, assets / "fill-insert-xlsx.js")
    shutil.copy2(FILL_GENERIC_JS, assets / "fill-xlsx.js")
    shutil.copy2(xlsx_path, assets / "template.xlsx")
    for stale_name in ("xlsx.full.min.js", "fill-apple-xlsx.js"):
        stale = assets / stale_name
        if stale.is_file():
            stale.unlink()
    return base64.b64encode(xlsx_path.read_bytes()).decode("ascii")


def _write_disabled_form(package_dir: Path) -> Path:
    card = _load_json(package_dir / "card-data.json")
    name = html.escape(str(card.get("package_name") or package_dir.name))
    out = DISABLED_TEMPLATE.read_text(encoding="utf-8").replace("{{package_name}}", name)
    dest = package_dir / CLAIM_FORM_NAME
    dest.write_text(out, encoding="utf-8")
    return dest


def sync_claim_form(package_dir: Path, *, template_path: Path | None = None) -> Path:
    package_dir = package_dir.expanduser().resolve()
    root = _project_root(package_dir)
    xlsx, _profile, _ = resolve_assets(root)
    if xlsx is None:
        return _write_disabled_form(package_dir)
    template = (template_path or TEMPLATE).read_text(encoding="utf-8")
    ctx = build_context(package_dir)
    ctx["xlsx_template_b64"] = _prepare_claim_assets(package_dir)
    out = template
    for key, value in ctx.items():
        out = out.replace("{{" + key + "}}", value)
    if "{{" in out:
        # leave unknown placeholders empty-ish
        out = re.sub(r"\{\{[^}]+\}\}", "", out)
    dest = package_dir / CLAIM_FORM_NAME
    dest.write_text(out, encoding="utf-8")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package-dir", required=True)
    ap.add_argument("--template", default=None)
    args = ap.parse_args()
    path = sync_claim_form(
        Path(args.package_dir),
        template_path=Path(args.template) if args.template else None,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
