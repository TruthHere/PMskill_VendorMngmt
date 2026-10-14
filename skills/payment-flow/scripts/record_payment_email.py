#!/usr/bin/env python3
"""Parse a supplier / QS / client payment mail and advance the claim stage.

Default stage = vendor_received（供应商来请款，写入过程，不占节点）。
客户批复请传 --status certified。
"""

from __future__ import annotations

import argparse
import email
import json
import re
import subprocess
import sys
from email.header import decode_header
from pathlib import Path


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def get_body_text(msg: email.message.Message) -> str:
    texts: list[str] = []
    htmls: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")
            if part.get_content_type() == "text/plain":
                texts.append(decoded)
            elif part.get_content_type() == "text/html":
                htmls.append(decoded)
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            texts.append(decoded)
        elif isinstance(payload, str):
            texts.append(payload)
    if texts:
        return "\n".join(texts)
    joined = "\n".join(htmls)
    joined = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", joined)
    joined = re.sub(r"(?s)<[^>]+>", " ", joined)
    joined = re.sub(r"\s+", " ", joined)
    return joined.strip()


def infer_payment_no(subject: str, body: str) -> int | None:
    blob = f"{subject}\n{body}"
    m = re.search(r"(?:PAYMENT\s*NO|PAYMENT\s*#|请款(?:编号|单号)?)\s*[:：#]?\s*(\d{1,4})", blob, re.I)
    return int(m.group(1)) if m else None


def infer_claim_node(subject: str, body: str, card: dict) -> str:
    blob = f"{subject}\n{body}"
    for node in card.get("payment_nodes") or []:
        name = str(node.get("name") or "").strip()
        if name and re.search(re.escape(name), blob, re.I):
            return name
    if re.search(r"delivery|到货", blob, re.I):
        return "到货 / Delivery"
    if re.search(r"advance|预付", blob, re.I):
        return "预付款 / Advance"
    if re.search(r"acceptance|验收", blob, re.I):
        return "验收 / Acceptance"
    return ""


def infer_amount_excl_tax(subject: str, body: str) -> float | None:
    blob = f"{subject}\n{body}"
    m = re.search(r"(?:RMB|CNY|¥)\s*([\d,]+(?:\.\d+)?)", blob, re.I)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(
        r"(?:amount(?:\s*\(?\s*excl(?:uding)?\.?\s*tax\s*\)?)?|金额(?:不含税)?)\s*[:：]?\s*(?:RMB|CNY|¥)?\s*([\d,]+(?:\.\d+)?)",
        blob,
        re.I,
    )
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package-dir", required=True)
    ap.add_argument("--eml", required=True)
    ap.add_argument(
        "--status",
        default="vendor_received",
        help="五步状态；默认 vendor_received。客户批复用 certified",
    )
    ap.add_argument(
        "--allow-skip",
        action="store_true",
        help="补录历史时允许跳步",
    )
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    pkg = Path(args.package_dir).expanduser().resolve()
    eml = Path(args.eml).expanduser().resolve()
    msg = email.message_from_bytes(eml.read_bytes())
    subject = decode_mime_header(msg.get("Subject"))
    body = get_body_text(msg)

    card_path = pkg / "card-data.json"
    if not card_path.is_file():
        raise SystemExit(f"missing card-data.json: {card_path}")
    card = json.loads(card_path.read_text(encoding="utf-8"))

    payment_no = infer_payment_no(subject, body)
    node = infer_claim_node(subject, body, card)
    amount_excl_tax = infer_amount_excl_tax(subject, body)

    if not payment_no:
        raise SystemExit("cannot infer payment_no from email")
    if not node:
        raise SystemExit("cannot infer claim node from email")
    if amount_excl_tax is None:
        raise SystemExit("cannot infer amount_excl_tax from email")

    parsed = {
        "ok": True,
        "package_dir": str(pkg),
        "eml_path": str(eml),
        "payment_no": payment_no,
        "node": node,
        "amount_excl_tax": amount_excl_tax,
        "subject": subject,
        "status": args.status,
        "did": ["payment-flow.record_payment_email.parse"],
    }

    record_payment = Path(__file__).resolve().parent / "record_payment.py"
    cmd = [
        sys.executable,
        str(record_payment),
        "--package-dir",
        str(pkg),
        "--payment-no",
        str(payment_no),
        "--node",
        node,
        "--amount-excl-tax",
        str(amount_excl_tax),
        "--status",
        args.status,
        "--source",
        "email",
        "--source-eml",
        str(eml),
        "--notes",
        args.notes or subject,
    ]
    if args.allow_skip:
        cmd.append("--allow-skip")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 4:
        skip = {}
        err = (proc.stderr or "").strip()
        try:
            skip = json.loads(err.splitlines()[-1]) if err else {}
        except json.JSONDecodeError:
            skip = {"ok": False, "reason": "out_of_order", "note": err[:500]}
        print(json.dumps({**parsed, **skip, "recorded": False}, ensure_ascii=False, indent=2))
        return 4
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout or "record_payment failed")

    out_lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    result = {
        **parsed,
        "recorded": True,
        "needs_pm_confirm": False,
        "did": [
            "payment-flow.record_payment_email.parse",
            "payment-flow.record_payment",
        ],
        "outputs": out_lines,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
