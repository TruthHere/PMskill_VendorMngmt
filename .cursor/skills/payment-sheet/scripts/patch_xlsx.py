#!/usr/bin/env python3
"""Fill a payment xlsx from a template-profile (engine=cells).

Keeps layout by ZIP-patching cell values. Drops sheets listed in profile.drop_sheets.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from patch_insert_xlsx import (
    _as_money,
    _previous_lines,
    clear_cell,
    set_number_cell,
    set_text_cell,
)
from template_profile import default_profile

_NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _sheet_parts(workbook_xml: str, rels_xml: str) -> list[dict]:
    wb = ET.fromstring(workbook_xml.encode("utf-8") if isinstance(workbook_xml, str) else workbook_xml)
    rels = ET.fromstring(rels_xml.encode("utf-8") if isinstance(rels_xml, str) else rels_xml)
    rid_to_target = {rel.attrib.get("Id"): rel.attrib.get("Target") for rel in rels}
    out = []
    for sh in wb.iter():
        if _local(sh.tag) != "sheet":
            continue
        rid = sh.attrib.get(_NS_R + "id") or sh.attrib.get("id")
        target = (rid_to_target.get(rid) or "").replace("\\", "/")
        part = target[1:] if target.startswith("/") else "xl/" + target.lstrip("/")
        out.append({"name": sh.attrib.get("name") or "", "rid": rid, "part": part, "target": target})
    return out


def _drop_workbook_sheet(xml: str, sheet_name: str) -> str:
    return re.sub(
        rf'<sheet name="{re.escape(sheet_name)}"[^/]*/>',
        "",
        xml,
        count=1,
    )


def _drop_rel(xml: str, rid: str) -> str:
    return re.sub(rf'<Relationship Id="{re.escape(rid)}"[^/]*/>', "", xml, count=1)


def _drop_ctype(xml: str, part: str) -> str:
    part_attr = part if part.startswith("/") else "/" + part
    return re.sub(
        rf'<Override PartName="{re.escape(part_attr)}"[^/]*/>',
        "",
        xml,
        count=1,
    )


def _insert_cell(sheet: str, addr: str, inner: str, extra_attrs: str = "") -> str:
    m = re.match(r"^([A-Z]+)(\d+)$", addr)
    if not m:
        raise ValueError(f"bad cell {addr}")
    row = m.group(2)
    row_pat = re.compile(rf'(<row r="{row}"[^>]*>)(.*?)(</row>)', re.DOTALL)
    hit = row_pat.search(sheet)
    if not hit:
        raise ValueError(f"template missing row {row} for {addr}")
    body = hit.group(2)
    if re.search(rf'<c r="{re.escape(addr)}"', body):
        return set_text_cell(sheet, addr, "")  # exists; caller should use set_*
    cell = f'<c r="{addr}"{extra_attrs}>{inner}</c>'
    return sheet[: hit.start()] + hit.group(1) + body + cell + hit.group(3) + sheet[hit.end() :]


def _write_cell(sheet: str, addr: str, kind: str, value) -> str:
    from patch_insert_xlsx import _xml_text

    def try_set(fn):
        try:
            return fn()
        except ValueError:
            return None

    if value is None or (isinstance(value, str) and value.strip() == ""):
        out = try_set(lambda: clear_cell(sheet, addr))
        return out if out is not None else sheet

    if kind in ("number", "money"):
        num = _as_money(value) if kind == "money" else value
        if num is None and kind == "money":
            out = try_set(lambda: clear_cell(sheet, addr))
            return out if out is not None else sheet
        out = try_set(lambda: set_number_cell(sheet, addr, num if kind == "money" else value))
        if out is not None:
            return out
        raw = str(int(num) if isinstance(num, float) and num.is_integer() else num)
        inner = f"<v>{raw}</v>"
        return _insert_cell(sheet, addr, inner)

    if kind == "auto":
        code = str(value).strip()
        if re.fullmatch(r"-?\d+(\.\d+)?", code):
            return _write_cell(sheet, addr, "number", float(code) if "." in code else int(code))
        return _write_cell(sheet, addr, "text", code)

    text = str(value)
    out = try_set(lambda: set_text_cell(sheet, addr, text))
    if out is not None:
        return out
    inner = f'<is><t xml:space="preserve">{_xml_text(text)}</t></is>'
    return _insert_cell(sheet, addr, inner, extra_attrs=' t="inlineStr"')


def _payload_value(response: dict, spec: dict):
    key = spec.get("from")
    raw = response.get(key)
    fmt = spec.get("format")
    if raw is None or raw == "":
        return None
    if fmt:
        return str(fmt).replace("{value}", str(raw))
    return raw


def apply_profile_sheet(sheet: str, response: dict, profile: dict) -> str:
    for spec in profile.get("writes") or []:
        addr = spec.get("cell")
        if not addr:
            continue
        kind = spec.get("type") or "text"
        val = _payload_value(response, spec)
        sheet = _write_cell(sheet, addr, kind, val)

    vat = profile.get("vat") or {}
    pct = response.get(vat.get("from") or "vat_note_pct")
    fmt = vat.get("format") or "(CNY exclude {value}% VAT)"
    for addr in vat.get("cells") or []:
        if pct is None or pct == "":
            try:
                sheet = clear_cell(sheet, addr)
            except ValueError:
                pass
        else:
            sheet = _write_cell(sheet, addr, "text", str(fmt).replace("{value}", str(pct)))

    # Optional single-cell previous total if mapped
    prev_cell = (profile.get("previously_certified") or {}).get("cell")
    if prev_cell:
        prev_sum = sum(amt for _, amt in _previous_lines(response))
        sheet = _write_cell(sheet, prev_cell, "money", prev_sum)

    claim = profile.get("claim_amount") or {}
    if claim.get("name_cell"):
        sheet = _write_cell(sheet, claim["name_cell"], "text", response.get("claim_node"))
    claim_amt = _claim_money(response, profile)
    amount_cells = []
    if claim.get("amount_cell"):
        amount_cells.append(claim["amount_cell"])
    for addr in claim.get("amount_cells") or []:
        if addr and addr not in amount_cells:
            amount_cells.append(addr)
    for addr in amount_cells:
        sheet = _write_cell(sheet, addr, "money", claim_amt)

    lines = list(response.get("support_file_lines") or [])
    for i, addr in enumerate(profile.get("support_file_cells") or []):
        text = str(lines[i]).strip() if i < len(lines) else ""
        sheet = _write_cell(sheet, addr, "text", text or None)

    totals = profile.get("running_totals") or {}
    prev_sum = sum(amt for _, amt in _previous_lines(response))
    certified = prev_sum + (claim_amt or 0) if totals.get("includes_this_claim") else prev_sum
    if totals.get("certified_to_date_cell"):
        sheet = _write_cell(sheet, totals["certified_to_date_cell"], "money", certified)
    if totals.get("remaining_cell"):
        contract = _as_money(response.get(totals.get("contract_from") or "contract_value_excl_tax"))
        remain = None if contract is None else contract - certified
        sheet = _write_cell(sheet, totals["remaining_cell"], "money", remain)
    return sheet


def _amount_tax(profile: dict) -> str:
    form = profile.get("form") if isinstance(profile.get("form"), dict) else {}
    raw = str(profile.get("amount_tax") or form.get("amount_tax") or "excl").strip().lower()
    if raw in ("incl", "incl_tax", "含税"):
        return "incl"
    return "excl"


def _claim_money(response: dict, profile: dict):
    if _amount_tax(profile) == "incl":
        return _as_money(response.get("claim_amount_incl_tax") if response.get("claim_amount_incl_tax") is not None else response.get("claim_amount"))
    return _as_money(response.get("claim_amount_excl_tax") if response.get("claim_amount_excl_tax") is not None else response.get("claim_amount"))


def patch_workbook_bytes(src: bytes, response: dict, profile: dict | None = None) -> bytes:
    profile = profile or default_profile()
    drop_names = set(profile.get("drop_sheets") or [])
    invoice_name = profile.get("invoice_sheet") or ""

    src_buf = io.BytesIO(src)
    with zipfile.ZipFile(src_buf, "r") as zin:
        workbook = zin.read("xl/workbook.xml").decode("utf-8")
        rels = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        parts = _sheet_parts(workbook, rels)
        drop_parts = set()
        drop_rids = set()
        invoice_part = None
        for sh in parts:
            if sh["name"] in drop_names:
                drop_parts.add(sh["part"])
                drop_rids.add(sh["rid"])
                workbook = _drop_workbook_sheet(workbook, sh["name"])
                rels = _drop_rel(rels, sh["rid"])
            if invoice_name and sh["name"] == invoice_name:
                invoice_part = sh["part"]
        if invoice_part is None:
            visible = [sh for sh in parts if sh["name"] not in drop_names]
            invoice_part = visible[0]["part"] if visible else "xl/worksheets/sheet1.xml"

        skip = set(drop_parts)
        for part in drop_parts:
            parent = str(Path(part).parent).replace("\\", "/")
            skip.add(f"{parent}/_rels/{Path(part).name}.rels")
        out_buf = io.BytesIO()
        with zipfile.ZipFile(out_buf, "w") as zout:
            ctypes = zin.read("[Content_Types].xml").decode("utf-8")
            for part in drop_parts:
                ctypes = _drop_ctype(ctypes, part)
            for info in zin.infolist():
                name = info.filename.replace("\\", "/")
                if name in skip:
                    continue
                data = zin.read(info.filename)
                if name == "xl/workbook.xml":
                    data = workbook.encode("utf-8")
                elif name == "xl/_rels/workbook.xml.rels":
                    data = rels.encode("utf-8")
                elif name == "[Content_Types].xml":
                    data = ctypes.encode("utf-8")
                elif name == invoice_part:
                    sheet = apply_profile_sheet(data.decode("utf-8"), response, profile)
                    data = sheet.encode("utf-8")
                zout.writestr(info, data)
        return out_buf.getvalue()


def patch_file(template: Path, response: dict, out_path: Path, profile: dict | None = None) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(patch_workbook_bytes(template.read_bytes(), response, profile))
    return out_path


def clear_cells_keep_layout(xlsx: Path, addrs: list[str], *, sheet_name: str = "") -> Path:
    """Blank listed cells in-place. Pictures / wrap / merges stay. ZIP-patch only."""
    xlsx = xlsx.expanduser().resolve()
    addrs = [a for a in addrs if a]
    if not addrs or not xlsx.is_file():
        return xlsx
    src = xlsx.read_bytes()
    buf = io.BytesIO(src)
    out = io.BytesIO()
    with zipfile.ZipFile(buf, "r") as zin:
        workbook = zin.read("xl/workbook.xml").decode("utf-8")
        rels = zin.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        parts = _sheet_parts(workbook, rels)
        invoice_part = None
        if sheet_name:
            for sh in parts:
                if sh["name"] == sheet_name:
                    invoice_part = sh["part"]
                    break
        if invoice_part is None:
            invoice_part = parts[0]["part"] if parts else "xl/worksheets/sheet1.xml"
        with zipfile.ZipFile(out, "w") as zout:
            for info in zin.infolist():
                name = info.filename.replace("\\", "/")
                data = zin.read(info.filename)
                if name == invoice_part:
                    sheet = data.decode("utf-8")
                    for addr in addrs:
                        try:
                            sheet = clear_cell(sheet, addr)
                        except ValueError:
                            pass
                    data = sheet.encode("utf-8")
                zout.writestr(info, data)
    xlsx.write_bytes(out.getvalue())
    return xlsx
