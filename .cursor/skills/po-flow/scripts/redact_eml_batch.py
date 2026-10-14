#!/usr/bin/env python3
"""
Batch-redact .eml files for Skill testing.

Focus: Subject / From / To / Cc, text bodies, text-like attachments,
nested .eml. PDF binaries are replaced with a tiny placeholder PDF
(content cannot be safely rewritten in-place). Signature blocks are
not specially targeted — use mapping if you need them gone.

Usage:
  python3 redact_eml_batch.py \\
    --mapping tests/redact/mapping.json \\
    --input tests/redact/raw \\
    --output tests/redact/output

  # or point at any folder of .eml
  python3 redact_eml_batch.py --mapping ... --input ~/Desktop/eml-raw --output ...
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from email import policy
from email.generator import BytesGenerator
from email.message import EmailMessage, Message
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS.parent
DEFAULT_MAPPING = SKILL_ROOT / "tests" / "redact" / "mapping.json"

# Minimal valid PDF (~placeholder for quotation/spec binaries)
_PLACEHOLDER_PDF = b"""%PDF-1.1
1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj
2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj
3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj
4 0 obj<< /Length 68 >>stream
BT /F1 12 Tf 72 720 Td (REDACTED quotation / attachment placeholder) Tj ET
endstream
endobj
5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000384 00000 n 
trailer<< /Size 6 /Root 1 0 R >>
startxref
456
%%EOF
"""

_TEXT_ATTACHMENT_SUFFIXES = {".txt", ".csv", ".md", ".html", ".htm", ".xml", ".json", ".eml"}
_PDF_SUFFIXES = {".pdf"}


def load_mapping(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("mapping must be a JSON object")
    return data


def build_replacement_pairs(mapping: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for section in ("replacements", "emails", "suppliers", "projects"):
        block = mapping.get(section) or {}
        if isinstance(block, dict):
            for old, new in block.items():
                old_s = str(old)
                new_s = str(new)
                if old_s and old_s != new_s:
                    pairs.append((old_s, new_s))
    # longest first so "Grace.He@jll.cn" wins over "jll.cn"
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def apply_text(text: str, pairs: list[tuple[str, str]], regexes: list[tuple[str, str]]) -> str:
    out = text
    # Regex first so full URL tokens are wiped before domain-only string maps.
    for pattern, repl in regexes:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    for old, new in pairs:
        if not old:
            continue
        out = re.sub(re.escape(old), lambda _m, n=new: n, out, flags=re.IGNORECASE)
    return out


def _set_payload_bytes(part: Message, data: bytes, *, maintype: str, subtype: str) -> None:
    from email import encoders

    # Clear before rewrite — Outlook parts often already have CTE/type set.
    for key in ("Content-Transfer-Encoding", "Content-Type"):
        while key in part:
            del part[key]
    part.set_payload(data)
    part.add_header("Content-Type", f"{maintype}/{subtype}")
    encoders.encode_base64(part)


def redact_message(msg: Message, mapping: dict[str, Any], *, depth: int = 0) -> Message:
    if depth > 5:
        return msg

    pairs = build_replacement_pairs(mapping)
    regexes: list[tuple[str, str]] = []
    for item in mapping.get("regex") or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            regexes.append((str(item[0]), str(item[1])))

    # Headers
    for header in ("Subject", "From", "To", "Cc", "Bcc", "Reply-To"):
        if msg.get(header):
            value = apply_text(str(msg.get(header)), pairs, regexes)
            msg.replace_header(header, value)

    prefix = str(mapping.get("subject_prefix") or "").strip()
    if prefix and msg.get("Subject"):
        subj = str(msg.get("Subject"))
        if not subj.startswith(prefix):
            msg.replace_header("Subject", f"{prefix} {subj}")

    if mapping.get("from_addr") and msg.get("From"):
        msg.replace_header("From", str(mapping["from_addr"]))
    if mapping.get("to_addr") and msg.get("To"):
        msg.replace_header("To", str(mapping["to_addr"]))
    if "cc_addr" in mapping and msg.get("Cc") is not None:
        cc = mapping.get("cc_addr")
        if cc:
            msg.replace_header("Cc", str(cc))
        else:
            del msg["Cc"]

    # Drop noisy / leaky headers (best-effort)
    drop_prefixes = tuple(mapping.get("drop_header_prefixes") or ("Received", "X-MS-", "Thread-"))
    for key in list(msg.keys()):
        if any(key.startswith(p) for p in drop_prefixes):
            del msg[key]

    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            _redact_part(part, pairs, regexes, mapping, depth)
    else:
        _redact_part(msg, pairs, regexes, mapping, depth)

    return msg


def _redact_part(
    part: Message,
    pairs: list[tuple[str, str]],
    regexes: list[tuple[str, str]],
    mapping: dict[str, Any],
    depth: int,
) -> None:
    ctype = part.get_content_type()
    fname = part.get_filename() or ""
    fname_lower = fname.lower()
    disp = str(part.get("Content-Disposition") or "").lower()

    # Filename
    if fname:
        new_name = apply_text(fname, pairs, regexes)
        if new_name != fname:
            # rebuild Content-Disposition
            for key in ("Content-Disposition",):
                if key in part:
                    del part[key]
            part.add_header("Content-Disposition", "attachment", filename=new_name)
            fname = new_name
            fname_lower = fname.lower()

    is_attachment = "attachment" in disp or bool(fname)

    # Nested .eml
    if fname_lower.endswith(".eml") or ctype in {"message/rfc822", "application/octet-stream"} and fname_lower.endswith(".eml"):
        raw = part.get_payload(decode=True) or b""
        try:
            nested = BytesParser(policy=policy.default).parsebytes(raw)
            redact_message(nested, mapping, depth=depth + 1)
            buf = BytesIO()
            BytesGenerator(buf, policy=policy.default).flatten(nested)
            _set_payload_bytes(part, buf.getvalue(), maintype="application", subtype="octet-stream")
        except Exception:
            pass
        return

    # PDF → placeholder
    if fname_lower.endswith(".pdf") or ctype == "application/pdf":
        if mapping.get("replace_pdf", True):
            _set_payload_bytes(part, _PLACEHOLDER_PDF, maintype="application", subtype="pdf")
        return

    # Text bodies / text attachments
    if ctype in ("text/plain", "text/html") or any(fname_lower.endswith(s) for s in _TEXT_ATTACHMENT_SUFFIXES):
        try:
            if ctype.startswith("text/") and not is_attachment:
                # Prefer get_content for bodies
                try:
                    text = part.get_content()
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                if not isinstance(text, str):
                    text = str(text)
                new_text = apply_text(text, pairs, regexes)
                subtype = "html" if ctype == "text/html" else "plain"
                charset = part.get_content_charset() or "utf-8"
                part.set_content(new_text, subtype=subtype, charset=charset)
            else:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
                new_text = apply_text(text, pairs, regexes)
                _set_payload_bytes(
                    part,
                    new_text.encode(charset, errors="replace"),
                    maintype="text",
                    subtype="plain" if not fname_lower.endswith((".html", ".htm")) else "html",
                )
        except Exception:
            return
        return

    # Images / other binaries: leave bytes; filename already rewritten if mapped


def safe_filename(name: str, fallback: str = "redacted.eml") -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
    name = re.sub(r"\s+", " ", name)
    if not name.lower().endswith(".eml"):
        name = f"{name}.eml"
    return name[:180] if name else fallback


def redact_eml_file(src: Path, dst: Path, mapping: dict[str, Any]) -> Path:
    raw = src.read_bytes()
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    redact_message(msg, mapping)
    # Prefer redacted subject as output filename when writing into a directory batch.
    if dst.suffix.lower() == ".eml" and mapping.get("rename_from_subject", True):
        subj = str(msg.get("Subject") or "").strip()
        if subj:
            dst = dst.with_name(safe_filename(subj))
    dst.parent.mkdir(parents=True, exist_ok=True)
    buf = BytesIO()
    BytesGenerator(buf, policy=policy.default).flatten(msg)
    dst.write_bytes(buf.getvalue())
    return dst


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch redact .eml for Skill testing")
    parser.add_argument("--mapping", default=str(DEFAULT_MAPPING), help="Path to mapping.json")
    parser.add_argument("--input", required=True, help="Input .eml file or directory")
    parser.add_argument("--output", required=True, help="Output directory for redacted .eml")
    parser.add_argument("--dry-run", action="store_true", help="List files only")
    args = parser.parse_args()

    mapping_path = Path(args.mapping).expanduser()
    if not mapping_path.is_file():
        print(f"Mapping not found: {mapping_path}", file=sys.stderr)
        print("Copy mapping.example.json → mapping.json and edit.", file=sys.stderr)
        sys.exit(1)

    mapping = load_mapping(mapping_path)
    src = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()

    files = [src] if src.is_file() else sorted(src.glob("*.eml"))
    if not files:
        print(f"No .eml under {src}", file=sys.stderr)
        sys.exit(1)

    print(f"mapping: {mapping_path}")
    print(f"files:   {len(files)}")
    for path in files:
        dest = out_dir / path.name
        print(f"  {path.name}")
        if args.dry_run:
            continue
        written = redact_eml_file(path, dest, mapping)
        print(f"    → {written.name}")
    if not args.dry_run:
        print(f"done → {out_dir}")


if __name__ == "__main__":
    main()
