#!/usr/bin/env python3
"""Read an xlsx enough to list sheets, labels, formulas, and empty styled cells.

Stdlib only. Used before drafting a payment-sheet template profile.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

_CELL_REF = re.compile(r"^([A-Z]+)(\d+)$")

XLSX_ONLY = (
    "请款单模板目前只收 Excel 工作簿（.xlsx）。"
    "老格式 .xls、Word（.doc/.docx）先不接，请换成 .xlsx 再给我。"
)


def require_xlsx(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path.suffix.lower() != ".xlsx":
        raise ValueError(XLSX_ONLY)
    if not zipfile.is_zipfile(path):
        raise ValueError(
            "这个文件虽然叫 .xlsx，但不是新格式 Excel。"
            "请换成真正的 Excel 工作簿（.xlsx）再给我。"
        )
    return path


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _col_row(addr: str) -> tuple[str, int] | None:
    m = _CELL_REF.match(addr or "")
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _col_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def _col_name(idx: int) -> str:
    out = []
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        out.append(chr(65 + rem))
    return "".join(reversed(out))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    name = "xl/sharedStrings.xml"
    if name not in z.namelist():
        return []
    root = ET.fromstring(z.read(name))
    out: list[str] = []
    for si in root:
        if _local(si.tag) != "si":
            continue
        texts = ["".join(t.text or "" for t in el.iter() if _local(el.tag) == "t") for el in si.iter()]
        # join unique walk: prefer direct t nodes in document order
        parts: list[str] = []
        for el in si.iter():
            if _local(el.tag) == "t" and el.text:
                parts.append(el.text)
            elif _local(el.tag) == "t" and el.text is None:
                parts.append("")
        out.append("".join(parts))
    return out


def _cell_value(c: ET.Element, shared: list[str]) -> tuple[str, str]:
    """Return (kind, text) kind in value|formula|empty|shared."""
    ctype = c.attrib.get("t") or ""
    formula = ""
    value = ""
    inline = ""
    for child in list(c):
        loc = _local(child.tag)
        if loc == "f":
            formula = "".join(child.itertext())
        elif loc == "v":
            value = "".join(child.itertext())
        elif loc == "is":
            inline = "".join(t.text or "" for t in child.iter() if _local(t.tag) == "t")
    if formula:
        return "formula", formula
    if ctype == "s" and value.isdigit() and int(value) < len(shared):
        return "value", shared[int(value)]
    if ctype == "inlineStr" or inline:
        return "value", inline
    if value != "":
        return "value", value
    return "empty", ""


def inspect_xlsx(path: Path, *, max_cells: int = 600) -> dict:
    path = require_xlsx(path)
    with zipfile.ZipFile(path) as z:
        names = [n.replace("\\", "/") for n in z.namelist()]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {}
        for rel in rels_root:
            rid_to_target[rel.attrib.get("Id")] = rel.attrib.get("Target")

        sheets = []
        for sh in wb.iter():
            if _local(sh.tag) != "sheet":
                continue
            rid = sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id") or sh.attrib.get("id")
            target = rid_to_target.get(rid) or ""
            target = target.replace("\\", "/")
            if target.startswith("/"):
                part = target.lstrip("/")
            else:
                part = "xl/" + target.lstrip("/")
            sheets.append(
                {
                    "name": sh.attrib.get("name") or "",
                    "state": sh.attrib.get("state") or "visible",
                    "rid": rid,
                    "part": part,
                    "in_zip": part in names,
                }
            )

        shared = _shared_strings(z)
        for sheet in sheets:
            part = sheet["part"]
            if part not in names:
                sheet["cells"] = []
                sheet["formulas"] = []
                sheet["empty_styled"] = []
                continue
            root = ET.fromstring(z.read(part))
            cells = []
            formulas = []
            empty_styled = []
            by_addr: dict[str, dict] = {}
            for el in root.iter():
                if _local(el.tag) != "c":
                    continue
                addr = el.attrib.get("r") or ""
                if not addr:
                    continue
                kind, text = _cell_value(el, shared)
                rec = {
                    "cell": addr,
                    "kind": kind,
                    "text": text.strip() if isinstance(text, str) else text,
                    "style": el.attrib.get("s") or "",
                }
                by_addr[addr] = rec
                if kind == "formula":
                    formulas.append(rec)
                elif kind == "value" and rec["text"]:
                    cells.append(rec)
                elif kind == "empty" and rec["style"]:
                    empty_styled.append(rec)

            # Guess fill target: empty styled cell to the right or below a label.
            guesses = []
            label_index = {}
            for rec in cells:
                cr = _col_row(rec["cell"])
                if cr:
                    label_index[cr] = rec["text"]
            for rec in empty_styled:
                cr = _col_row(rec["cell"])
                if not cr:
                    continue
                col, row = cr
                ci = _col_index(col)
                left = label_index.get((_col_name(ci - 1), row)) if ci > 1 else None
                above = label_index.get((col, row - 1)) if row > 1 else None
                label = left or above
                if not label:
                    continue
                guesses.append(
                    {
                        "cell": rec["cell"],
                        "label": label,
                        "label_at": "left" if left else "above",
                    }
                )

            sheet["cells"] = cells[:max_cells]
            sheet["formulas"] = formulas
            sheet["empty_styled_count"] = len(empty_styled)
            sheet["fill_guesses"] = guesses[:120]
            sheet["truncated"] = len(cells) > max_cells

    return {
        "file": str(path),
        "sheets": sheets,
    }


def inspect_markdown(data: dict) -> str:
    lines = [f"# 请款单模板体检", "", f"文件：`{data.get('file')}`", ""]
    for sheet in data.get("sheets") or []:
        lines.append(f"## 表 `{sheet.get('name')}`（{sheet.get('state')}）")
        lines.append("")
        if sheet.get("formulas"):
            lines.append("公式：")
            for rec in sheet["formulas"][:40]:
                lines.append(f"- `{rec['cell']}` = `{rec['text']}`")
            lines.append("")
        lines.append("有字的格子（节选）：")
        for rec in (sheet.get("cells") or [])[:80]:
            text = rec["text"].replace("\n", " / ")
            if len(text) > 80:
                text = text[:77] + "…"
            lines.append(f"- `{rec['cell']}` {text}")
        lines.append("")
        if sheet.get("fill_guesses"):
            lines.append("疑似要填的空格（旁边有标签）：")
            for g in sheet["fill_guesses"][:60]:
                lines.append(f"- `{g['cell']}` ← {g['label_at']}「{g['label']}」")
            lines.append("")
    lines.append("下一步：按这些格子起草 `template-profile.json`，用白话给用户对一遍「网页填什么 → Excel 哪一格」。")
    return "\n".join(lines) + "\n"


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-md", default="")
    args = ap.parse_args()
    data = inspect_xlsx(Path(args.xlsx))
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out_json:
        Path(args.out_json).expanduser().write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.out_md:
        Path(args.out_md).expanduser().write_text(inspect_markdown(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
