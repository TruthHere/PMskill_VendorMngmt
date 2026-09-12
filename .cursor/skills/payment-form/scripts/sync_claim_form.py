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
_CURSOR = SKILL_ROOT.parents[1]
_FOUNDATION = _CURSOR / "lib" / "project-foundation" / "scripts"
if str(_FOUNDATION) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION))

from common import confirmed_changes_total_excl_tax, find_package, load_tracker_packages  # noqa: E402

TEMPLATE = SKILL_ROOT / "assets" / "claim-form.html"
XLSX_TEMPLATE = SKILL_ROOT / "assets" / "Apple_Payment_Application.xlsx"
JSZIP_JS = SKILL_ROOT / "assets" / "vendor" / "jszip.min.js"
FILL_JS = SKILL_ROOT / "assets" / "fill-apple-xlsx.js"
CLAIM_FORM_NAME = "请款申请.html"
CLAIM_ASSETS_DIR = ".claim-assets"

# 苹果请款页附件提醒（按节点；发票在客户批复请款后开，不读卡片 payment_attachments）
_EMPTY_FILES_HINT = "本节点无需随单附件。"
_ADVANCE_FILES_HINT = "预付款无需随单附件。客户批复请款后再开发票。"
_DELIVERY_FILES_HINT = "到货款请附到货签认单。勾选只提醒你别漏文件，不会生成附件包。客户批复请款后再开发票。"
_ACCEPT_FILES_HINT = "验收款请附验收确认单。勾选只提醒你别漏文件，不会生成附件包。客户批复请款后再开发票。"


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _apple_attachments(node_name: str) -> tuple[list[str], str]:
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

    nodes = list(card.get("payment_nodes") or [])
    base = _money(tracker.get("amount_excl_tax"))
    claimed_amount = _money(tracker.get("claimed_amount_excl_tax"))
    previous_claims = _ledger_completed(package_dir)
    if not previous_claims and claimed_amount:
        previous_claims = [
            {"payment_no": 0, "name": "Previously certified", "amount": claimed_amount}
        ]
    variations_to_date = _variations_total(package_dir, card)
    vat = _vat_pct_from_amounts(base, _money(tracker.get("amount_incl_tax")))

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
        checklist, files_hint = _apple_attachments(name)
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
    amount_hint = "本次请款金额须为不含税，由供应商按合同自行填写。"
    files_hint = (first_node or {}).get("files_hint") or _EMPTY_FILES_HINT
    checklist_items = (first_node or {}).get("checklist") or []
    if checklist_items:
        checklist_html = "".join(
            f"<li><label><input type=\"checkbox\"> {html.escape(t)}</label></li>"
            for t in checklist_items
        )
    else:
        checklist_html = "<li class=\"checklist-empty\">本节点无需随单附件。</li>"

    boot = {
        "project_name": card.get("project_name") or project.get("project_name") or "",
        "division": project.get("division") or "",
        "division_code": project.get("division_code") or "",
        "billing_entity": project.get("billing_entity") or "",
        "vendor_name": card.get("supplier_name") or "",
        "work_package": card.get("package_name") or package_dir.name,
        "contract_value_excl_tax": base,
        "claimed_amount_excl_tax": claimed_amount,
        "variations_to_date": variations_to_date,
        "period_count": len(boot_nodes),
        "previous_claims": previous_claims,
        "vat_note_pct": vat,
        "nodes": boot_nodes,
        "amount_hint": amount_hint,
    }

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
        "contract_value_excl_tax": html.escape(_fmt_money(base) or dash),
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
        "boot_json": json.dumps(boot, ensure_ascii=False),
        "xlsx_template_b64": "",
    }


def _prepare_claim_assets(package_dir: Path) -> str:
    """Copy fill helpers next to the form; return Apple template as base64 for offline fill."""
    if not XLSX_TEMPLATE.is_file():
        raise FileNotFoundError(f"missing Apple template: {XLSX_TEMPLATE}")
    if not JSZIP_JS.is_file():
        raise FileNotFoundError(f"missing JSZip vendor: {JSZIP_JS}")
    if not FILL_JS.is_file():
        raise FileNotFoundError(f"missing fill helper: {FILL_JS}")
    assets = package_dir / CLAIM_ASSETS_DIR
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(JSZIP_JS, assets / "jszip.min.js")
    shutil.copy2(FILL_JS, assets / "fill-apple-xlsx.js")
    shutil.copy2(XLSX_TEMPLATE, assets / "Apple_Payment_Application.xlsx")
    stale = assets / "xlsx.full.min.js"
    if stale.is_file():
        stale.unlink()
    return base64.b64encode(XLSX_TEMPLATE.read_bytes()).decode("ascii")


def sync_claim_form(package_dir: Path, *, template_path: Path | None = None) -> Path:
    package_dir = package_dir.expanduser().resolve()
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
