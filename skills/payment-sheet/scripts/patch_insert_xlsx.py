#!/usr/bin/env python3
"""Patch a payment xlsx in-place (ZIP XML) when previous-claim rows must be inserted.

Keeps Invoice layout/styles/merges/print settings. Drops the extra schedule sheet if present.
Does not rewrite the workbook with openpyxl/SheetJS.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

SKIP_SHEET2 = {
    "xl/worksheets/sheet2.xml",
    "xl/worksheets/_rels/sheet2.xml.rels",
    "xl/printerSettings/printerSettings2.bin",
}

# Keep Excel formulas on these cells; only feed their inputs.
FORMULA_CELLS = frozenset({"I29", "I31", "Q39", "Q45"})


def _xml_text(value: str) -> str:
    return xml_escape("" if value is None else str(value), {"'": "&apos;", '"': "&quot;"})


def _keep_style(attrs: str) -> str:
    m = re.search(r'\bs="(\d+)"', attrs or "")
    return f' s="{m.group(1)}"' if m else ""


def _replace_cell(sheet: str, addr: str, inner: str, extra_attrs: str = "") -> str:
    pat = re.compile(
        rf'(<c r="{re.escape(addr)}")([^>]*?)(?:/>|>.*?</c>)',
        re.DOTALL,
    )

    def repl(m: re.Match) -> str:
        style = _keep_style(m.group(2))
        return f'{m.group(1)}{style}{extra_attrs}>{inner}</c>'

    out, n = pat.subn(repl, sheet, count=1)
    if n != 1:
        raise ValueError(f"template missing cell {addr}")
    return out


def set_text_cell(sheet: str, addr: str, value: str) -> str:
    text = _xml_text(value)
    inner = f'<is><t xml:space="preserve">{text}</t></is>'
    return _replace_cell(sheet, addr, inner, extra_attrs=' t="inlineStr"')


def set_number_cell(sheet: str, addr: str, value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        raw = str(int(value))
    elif isinstance(value, float):
        raw = format(value, ".10g")
    else:
        raw = str(value)
    return _replace_cell(sheet, addr, f"<v>{raw}</v>")


def clear_cell(sheet: str, addr: str) -> str:
    pat = re.compile(
        rf'(<c r="{re.escape(addr)}")([^>]*?)(?:/>|>.*?</c>)',
        re.DOTALL,
    )

    def repl(m: re.Match) -> str:
        return f'{m.group(1)}{_keep_style(m.group(2))}/>'

    out, n = pat.subn(repl, sheet, count=1)
    if n != 1:
        raise ValueError(f"template missing cell {addr}")
    return out


def _strip_sheet2_workbook(xml: str) -> str:
    xml = re.sub(
        r'<sheet name="Advance Payment Schedule"[^/]*/>',
        "",
        xml,
        count=1,
    )
    return xml


def _strip_sheet2_rels(xml: str) -> str:
    return re.sub(
        r'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>',
        "",
        xml,
        count=1,
    )


def _strip_sheet2_ctypes(xml: str) -> str:
    return re.sub(
        r'<Override PartName="/xl/worksheets/sheet2.xml"[^/]*/>',
        "",
        xml,
        count=1,
    )


def _strip_sheet2_calc(xml: str) -> str:
    return re.sub(r'<c r="[^"]+" i="4"[^/]*/>', "", xml)


def _as_money(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("¥", "").replace("CNY", "").replace("RMB", "").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _previous_lines(response: dict) -> list[tuple[str, float]]:
    current_no = int(response.get("payment_no") or 1)
    lines: list[tuple[str, float]] = []
    for c in response.get("previous_claims") or []:
        amt = _as_money(c.get("amount") if isinstance(c, dict) else None)
        if amt is None:
            continue
        pn = int((c.get("payment_no") or 0) if isinstance(c, dict) else 0)
        if pn and pn >= current_no:
            continue
        if not pn and current_no <= 1:
            continue
        name = str((c.get("name") if isinstance(c, dict) else "") or "Previously certified").strip()
        lines.append((name, amt))
    return lines


def _shift_row_num(n: int, from_row: int, delta: int) -> int:
    return n + delta if n >= from_row else n


def _shift_sheet(xml: str, from_row: int, delta: int) -> str:
    if delta <= 0:
        return xml

    def row_tag(m: re.Match) -> str:
        return f'<row r="{_shift_row_num(int(m.group(1)), from_row, delta)}"'

    xml = re.sub(r'<row r="(\d+)"', row_tag, xml)

    def cell_r(m: re.Match) -> str:
        return f'<c r="{m.group(1)}{_shift_row_num(int(m.group(2)), from_row, delta)}"'

    xml = re.sub(r'<c r="([A-Z]+)(\d+)"', cell_r, xml)

    def merge(m: re.Match) -> str:
        return (
            f'<mergeCell ref="{m.group(1)}{_shift_row_num(int(m.group(2)), from_row, delta)}'
            f':{m.group(3)}{_shift_row_num(int(m.group(4)), from_row, delta)}"'
        )

    xml = re.sub(r'<mergeCell ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"', merge, xml)

    def f_block(m: re.Match) -> str:
        inner = re.sub(
            r"([A-Z]+)(\d+)",
            lambda mm: f"{mm.group(1)}{_shift_row_num(int(mm.group(2)), from_row, delta)}",
            m.group(1),
        )
        return f"<f>{inner}</f>"

    xml = re.sub(r"<f>([^<]*)</f>", f_block, xml)

    def dim(m: re.Match) -> str:
        return (
            f'<dimension ref="{m.group(1)}{m.group(2)}:'
            f'{m.group(3)}{_shift_row_num(int(m.group(4)), from_row, delta)}"'
        )

    xml = re.sub(r'<dimension ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"', dim, xml)
    return xml


def _shift_calc(xml: str, from_row: int, delta: int) -> str:
    if delta <= 0:
        return xml

    def cell(m: re.Match) -> str:
        n = _shift_row_num(int(m.group(2)), from_row, delta)
        return f'<c r="{m.group(1)}{n}"'

    return re.sub(r'<c r="([A-Z]+)(\d+)"', cell, xml)


def _retarget_row(row_xml: str, old_r: int, new_r: int) -> str:
    row_xml = re.sub(rf'<row r="{old_r}"', f'<row r="{new_r}"', row_xml, count=1)
    return re.sub(
        rf' r="([A-Z]+){old_r}"',
        lambda m: f' r="{m.group(1)}{new_r}"',
        row_xml,
    )


def _insert_previous_rows(sheet: str, extra: int) -> str:
    if extra <= 0:
        return sheet
    m = re.search(r'<row r="36"[^>]*>.*?</row>', sheet, re.DOTALL)
    if not m:
        raise ValueError("template missing row 36")
    template = m.group(0)
    sheet = _shift_sheet(sheet, 37, extra)
    extras = "".join(_retarget_row(template, 36, 37 + i) for i in range(extra))
    anchor = re.search(r'<row r="36"[^>]*>.*?</row>', sheet, re.DOTALL)
    if not anchor:
        raise ValueError("row 36 missing after shift")
    return sheet[: anchor.end()] + extras + sheet[anchor.end() :]


def _ensure_merge(sheet: str, ref: str) -> str:
    if re.search(rf'<mergeCell ref="{re.escape(ref)}"/>', sheet):
        return sheet
    m = re.search(r'<mergeCells count="(\d+)">', sheet)
    if not m:
        raise ValueError("template missing mergeCells")
    n = int(m.group(1)) + 1
    sheet = sheet[: m.start()] + f'<mergeCells count="{n}">' + sheet[m.end() :]
    return sheet.replace("</mergeCells>", f'<mergeCell ref="{ref}"/></mergeCells>', 1)


def apply_payload(sheet: str, response: dict) -> tuple[str, int]:
    payment_no = int(response.get("payment_no") or 1)
    sheet = set_text_cell(sheet, "B1", f"PAYMENT NO: {payment_no}")
    sheet = set_number_cell(sheet, "Q19", payment_no)

    period = response.get("period_count")
    try:
        period_n = int(period) if period not in (None, "") else None
    except (TypeError, ValueError):
        period_n = None
    if period_n:
        sheet = set_number_cell(sheet, "P23", period_n)

    def text(addr: str, key: str) -> None:
        nonlocal sheet
        val = response.get(key)
        if val is None or str(val).strip() == "":
            sheet = clear_cell(sheet, addr)
        else:
            sheet = set_text_cell(sheet, addr, str(val).strip())

    text("C2", "project_name")
    text("C3", "division")
    text("C4", "vendor_name")
    text("C11", "vendor_name")
    text("C5", "work_package")
    text("C6", "vendor_ref")
    text("C7", "po_number")
    text("C12", "contact_name")
    text("C13", "contact_mobile")
    text("C14", "office_phone")
    text("K12", "office_address")
    text("C19", "billing_entity")
    text("B22", "nodes_overview")

    vat = response.get("vat_note_pct")
    if vat is None or vat == "":
        sheet = clear_cell(sheet, "D8")
        sheet = clear_cell(sheet, "D9")
    else:
        note = f"(CNY exclude {vat}% VAT)"
        sheet = set_text_cell(sheet, "D8", note)
        sheet = set_text_cell(sheet, "D9", note)

    code = str(response.get("division_code") or "").strip()
    if not code:
        sheet = clear_cell(sheet, "B19")
    elif re.fullmatch(r"-?\d+(\.\d+)?", code):
        sheet = set_number_cell(sheet, "B19", float(code) if "." in code else int(code))
    else:
        sheet = set_text_cell(sheet, "B19", code)

    po_val = _as_money(response.get("po_value_excl_tax"))
    contract_val = _as_money(response.get("contract_value_excl_tax"))
    if po_val is None:
        po_val = contract_val
    if contract_val is None:
        contract_val = po_val
    if po_val is None:
        sheet = clear_cell(sheet, "C8")
    else:
        sheet = set_number_cell(sheet, "C8", po_val)
    if contract_val is None:
        sheet = clear_cell(sheet, "C9")
    else:
        sheet = set_number_cell(sheet, "C9", contract_val)

    variations = _as_money(response.get("variations_to_date"))
    sheet = set_number_cell(sheet, "I30", 0.0 if variations is None else variations)

    prev_lines = _previous_lines(response)
    extra = max(0, len(prev_lines) - 1)
    sheet = _insert_previous_rows(sheet, extra)
    current_row = 37 + extra
    prev_sum = 0.0
    for i, (name, amt) in enumerate(prev_lines):
        row = 36 + i
        sheet = set_text_cell(sheet, f"B{row}", name)
        sheet = set_number_cell(sheet, f"Q{row}", amt)
        prev_sum += amt

    claim_name = str(response.get("claim_node") or "").strip()
    claim_amt = _as_money(response.get("claim_amount_excl_tax"))
    if claim_name:
        sheet = set_text_cell(sheet, f"B{current_row}", claim_name)
    else:
        sheet = clear_cell(sheet, f"B{current_row}")
    if claim_amt is None:
        sheet = clear_cell(sheet, f"Q{current_row}")
    else:
        sheet = set_number_cell(sheet, f"Q{current_row}", claim_amt)

    sheet = set_number_cell(sheet, f"Q{41 + extra}", prev_sum)
    for i in range(len(prev_lines)):
        sheet = _ensure_merge(sheet, f"B{36 + i}:M{36 + i}")
    return sheet, extra


def patch_workbook_bytes(src: bytes, response: dict) -> bytes:
    extra = max(0, len(_previous_lines(response)) - 1)
    src_buf = io.BytesIO(src)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(src_buf, "r") as zin, zipfile.ZipFile(out_buf, "w") as zout:
        for info in zin.infolist():
            name = info.filename.replace("\\", "/")
            if name in SKIP_SHEET2:
                continue
            data = zin.read(info.filename)
            if name == "xl/worksheets/sheet1.xml":
                sheet, _extra = apply_payload(data.decode("utf-8"), response)
                data = sheet.encode("utf-8")
            elif name == "xl/workbook.xml":
                data = _strip_sheet2_workbook(data.decode("utf-8")).encode("utf-8")
            elif name == "xl/_rels/workbook.xml.rels":
                data = _strip_sheet2_rels(data.decode("utf-8")).encode("utf-8")
            elif name == "[Content_Types].xml":
                data = _strip_sheet2_ctypes(data.decode("utf-8")).encode("utf-8")
            elif name == "xl/calcChain.xml":
                calc = _strip_sheet2_calc(data.decode("utf-8"))
                calc = _shift_calc(calc, 37, extra)
                data = calc.encode("utf-8")
            zout.writestr(info, data)
    return out_buf.getvalue()


def patch_file(template: Path, response: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(patch_workbook_bytes(template.read_bytes(), response))
    return out_path
