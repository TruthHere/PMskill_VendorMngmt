#!/usr/bin/env python3
"""Parse .eml for fulfillment steps 1–4; call existing scripts or write pending.

project_init → Skill 0; change.* → Skill 3 (via mail-inbox). This module only
consumes fulfillment.*; misroutes write pending with routed_to_skill0/3.
"""

from __future__ import annotations

import argparse
import email
import json
import re
import sys
from email.header import decode_header
from pathlib import Path
from typing import Any

from archive_file import archive_file
from common import (
    PROJECT_JSON,
    extract_amounts_from_quote_file,
    is_quotation_attachment,
    load_json,
    load_tracker_packages,
    merge_contact_emails,
    now_iso,
    parse_amount_with_tax,
    system_file,
)
from pending_store import add_pending as store_add_pending
from update_tracker import add_package, update_package, sync_next_payment_from_card

_FC_SCRIPTS = Path(__file__).resolve().parents[1].parent / "fulfillment-card" / "scripts"
_MAIL_SCRIPTS = Path(__file__).resolve().parents[1].parent / "mail-inbox" / "scripts"
for _p in (_FC_SCRIPTS, _MAIL_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from classify_mail import (  # noqa: E402
    classify_from_message,
    collect_attachment_meta,
    # 仅作「绕过邮局直扔进来」时的拒收兜底；分类/防误伤真源在 mail-inbox，勿在本 Skill 另写一套
    is_change_po_mail,
)
from render_card import patch_and_render  # noqa: E402


def render_package_card(pkg_dir: Path, patch: dict) -> dict:
    """Write card-data patch via fulfillment-card (card HTML + 请款申请.html)."""
    return patch_and_render(pkg_dir, patch)

TYPE_MAP = {
    "纯供应": "供应",
    "供应": "供应",
    "供装": "供装",
    "供应+安装": "供装",
    "顾问": "顾问",
    "总包": "总包",
}


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def email_event_time(msg: email.message.Message) -> str:
    """Prefer email Date header (CST ISO); fallback to now."""
    from email.utils import parsedate_to_datetime

    raw = msg.get("Date")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                from common import CST

                dt = dt.replace(tzinfo=CST)
            from common import CST

            return dt.astimezone(CST).isoformat(timespec="seconds")
        except Exception:
            pass
    return now_iso()


def archive_eml_correspondence(
    eml_path: Path,
    pkg_dir: Path,
    package_name: str,
    *,
    description: str = "往来邮件",
) -> Path | None:
    """Every AI-mailbox mail that maps to a package → 07_往来文件/*.eml"""
    if not eml_path.exists():
        return None
    return archive_file(
        source=eml_path,
        dest_dir=pkg_dir / "07_往来文件",
        package_name=package_name,
        file_type="邮件",
        description=description[:10] or "往来邮件",
        version="v1",
    )


def archive_quote_attachments(
    attachment_paths: list[str] | None,
    pkg_dir: Path,
    package_name: str,
    *,
    file_type: str = "报价单",
    description: str = "最终报价",
) -> tuple[list[str], list[Path]]:
    """Only store quotation-related files under 01_合同报价; skip signature images.
    Returns (skipped_names, archived_paths)."""
    kept: list[Path] = []
    skipped: list[str] = []
    for att in attachment_paths or []:
        p = Path(att)
        if is_quotation_attachment(p):
            target = archive_file(
                source=p,
                dest_dir=pkg_dir / "01_合同报价",
                package_name=package_name,
                file_type=file_type,
                description=description,
                version="v终版",
            )
            kept.append(Path(target))
        else:
            skipped.append(p.name)
    return skipped, kept


def _amount_number(text: str) -> float | None:
    """Parse display amount like ¥83,381.16 → float; None if empty/unparseable."""
    if not (text or "").strip():
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)", str(text).replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _amounts_conflict(a: str, b: str, *, tol: float = 0.02) -> bool:
    """True when both sides have a number and they differ beyond tol (absolute)."""
    na, nb = _amount_number(a), _amount_number(b)
    if na is None or nb is None:
        return False
    return abs(na - nb) > tol


def merge_amount_fields(
    email_info: dict[str, Any],
    quote_paths: list[Path],
) -> dict[str, Any]:
    """Attachment quote is authority; body only fills gaps. Flag body↔quote conflicts.

    Returns also:
      amount_source: quote | body | mixed
      body_quote_mismatch: bool
      quote_unparsed: quote files present but extractor got nothing
    """
    body_excl = (email_info.get("amount_excl_tax") or "").strip()
    body_incl = (email_info.get("amount_incl_tax") or "").strip()
    quote_excl = ""
    quote_incl = ""
    quote_source = ""
    quote_paths = [Path(p) for p in quote_paths if p]
    tried_quote = False

    for qp in quote_paths:
        tried_quote = True
        try:
            q = extract_amounts_from_quote_file(qp)
        except Exception:
            continue
        if q.get("amount_excl_tax"):
            quote_excl = q["amount_excl_tax"]
            quote_source = q.get("source") or str(qp)
        if q.get("amount_incl_tax"):
            quote_incl = q["amount_incl_tax"]
            quote_source = q.get("source") or str(qp)
        if quote_excl and quote_incl:
            break

    quote_unparsed = bool(quote_paths) and not (quote_excl or quote_incl)
    mismatch = False
    if quote_excl or quote_incl:
        if quote_excl and body_excl and _amounts_conflict(quote_excl, body_excl):
            mismatch = True
        if quote_incl and body_incl and _amounts_conflict(quote_incl, body_incl):
            mismatch = True
        # One-sided body vs the other side of quote (e.g. body only excl, quote both)
        if body_excl and not body_incl and quote_incl and _amounts_conflict(body_excl, quote_excl or ""):
            mismatch = True
        if body_incl and not body_excl and quote_excl and _amounts_conflict(body_incl, quote_incl or ""):
            mismatch = True

    # Authority: quote wins; body only fills empty sides
    excl = quote_excl or body_excl
    incl = quote_incl or body_incl
    if quote_excl and quote_incl:
        source = "quote"
    elif quote_excl or quote_incl:
        source = "mixed" if (body_excl or body_incl) else "quote"
    elif body_excl or body_incl:
        source = "body"
    else:
        source = ""

    tax_uncertain = bool(email_info.get("tax_uncertain")) and not (excl and incl)
    if excl and incl:
        tax_uncertain = False
    elif excl or incl:
        tax_uncertain = True

    return {
        "amount_excl_tax": excl,
        "amount_incl_tax": incl,
        "tax_uncertain": tax_uncertain,
        "quote_source": quote_source,
        "amount_source": source,
        "body_quote_mismatch": mismatch,
        "quote_unparsed": quote_unparsed,
        "body_amount_excl_tax": body_excl,
        "body_amount_incl_tax": body_incl,
        "tried_quote": tried_quote,
    }


def extract_header_addresses(msg: email.message.Message, *headers: str) -> list[str]:
    from email.utils import getaddresses

    pairs = getaddresses([msg.get(h) or "" for h in headers])
    return [addr.strip() for _, addr in pairs if addr and "@" in addr]


def supplier_domain_tokens(supplier_name: str) -> list[str]:
    if not supplier_name or supplier_name == "待确认":
        return []
    tokens = re.findall(r"[A-Za-z0-9]{3,}", supplier_name.lower())
    # Modular Space → modularspace; Lantro → lantro
    joined = re.sub(r"[^a-z0-9]", "", supplier_name.lower())
    out = list(tokens)
    if len(joined) >= 4:
        out.append(joined)
    return out


def collect_supplier_contact_emails(
    msg: email.message.Message,
    body: str,
    supplier_name: str,
) -> str:
    """Keep To/Cc/From addresses whose domain matches supplier name tokens."""
    tokens = supplier_domain_tokens(supplier_name)
    candidates = extract_header_addresses(msg, "From", "To", "Cc", "CC", "Reply-To")
    candidates += re.findall(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", body, flags=re.I
    )
    kept: list[str] = []
    for addr in candidates:
        addr_l = addr.lower().strip().strip("<>")
        domain = addr_l.split("@")[-1]
        if tokens:
            if any(t in domain or t in addr_l for t in tokens):
                kept.append(addr_l)
        # always keep explicit vendor domains seen with supplier in local-part? skip if no tokens
    if not kept and tokens:
        # fallback: any address with token in local or domain from Cc/To only
        for addr in extract_header_addresses(msg, "To", "Cc", "CC"):
            addr_l = addr.lower()
            if any(t in addr_l for t in tokens):
                kept.append(addr_l)
    return merge_contact_emails(*kept)


def get_body_text(msg: email.message.Message) -> str:
    texts: list[str] = []
    htmls: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain":
                texts.append(decoded)
            elif ctype == "text/html":
                htmls.append(decoded)
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                htmls.append(decoded)
            else:
                texts.append(decoded)
        elif isinstance(payload, str):
            texts.append(payload)
    if texts:
        return "\n".join(texts)
    # Fallback: strip rough HTML tags
    joined = "\n".join(htmls)
    joined = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", joined)
    joined = re.sub(r"(?s)<[^>]+>", " ", joined)
    joined = re.sub(r"&nbsp;", " ", joined)
    joined = re.sub(r"\s+", " ", joined)
    return joined.strip()


def intent_to_step(intent: str) -> str:
    return {
        "fulfillment.rfp": "step1",
        "fulfillment.tech_confirm": "step2",
        "fulfillment.raise_po": "step3",
        "fulfillment.payment_terms": "step4_payment",
        "fulfillment.contract": "step4_contract",
    }.get(intent, "unknown")


def extract_field(body: str, labels: list[str]) -> str:
    for label in labels:
        m = re.search(rf"{re.escape(label)}\s*[：:]\s*(.+)", body)
        if m:
            return m.group(1).strip().split("\n")[0].strip()
    return ""


def parse_subject_triple(subject: str) -> dict[str, str]:
    # Optional structured form: SAMPLE · BMS · BOSCH — RFP
    subject = re.sub(r"\s+", " ", subject.replace("\r", " ").replace("\n", " "))
    m = re.match(
        r"^\s*(?:FW:\s*|RE:\s*)*([^·—\-]+)\s*[·•]\s*([^·—\-]+)\s*[·•]\s*([^—\-]+)",
        subject,
        re.I,
    )
    if not m:
        return {}
    return {
        "project_code": m.group(1).strip(),
        "package_name": m.group(2).strip(),
        "supplier_hint": re.sub(r"\s*[—\-].*$", "", m.group(3)).strip(),
    }


def infer_fields_from_subject(subject: str) -> dict[str, str]:
    """Heuristic extraction when structured subject is absent."""
    s = re.sub(r"\s+", " ", subject.replace("\r", " ").replace("\n", " ")).strip()
    s = re.sub(r"^(?:FW|Fwd|RE)\s*:\s*", "", s, flags=re.I)
    out: dict[str, str] = {}

    # Trailing "(Vendor Name)" on RFQ/RFP subjects is often the supplier, not a room note.
    # Support ASCII () and fullwidth （）.
    trailing_paren = None
    m_paren = re.search(r"[\(（]([^)）]+)[\)）]\s*$", s)
    if m_paren and re.search(r"\b(?:RFQ|RFP)\b", s, re.I):
        trailing_paren = m_paren.group(1).strip()
        s_noparen = s[: m_paren.start()].rstrip()
    else:
        s_noparen = s

    # "RFQ for rubber floor & carpet" / "RFP for xxx"
    m = re.search(
        r"\b(?:RFQ|RFP)\b\s+for\s+(.+?)(?:\s+[—\-|]\s*|\s*$)",
        s_noparen,
        re.I,
    )
    if m:
        pkg = m.group(1).strip()
        # Only strip paren if we already captured it as supplier candidate
        if not trailing_paren:
            pkg = re.sub(r"[\(（][^)）]*[\)）]\s*$", "", pkg).strip()
        out["package_name"] = pkg
        out["package_hint_raw"] = pkg

    if trailing_paren:
        # Normalize display: Modular space → Modular Space
        vendor = " ".join(w.capitalize() if w.islower() else w for w in trailing_paren.split())
        out["supplier_hint"] = vendor

    # [Raise PO] ..._IT cabling_Lantro
    # [Raise PO] ... Ph5_BMS（change PO）_Schneider
    # [Raise PO] ..._Power distribution box (change PO)_Schneider (公司中文名)
    m = re.search(
        r"(?:Raise\s*PO|Raise\s*Procurement).+?_"
        r"([^_]+?)"
        r"(?:[\(（][^)）]*[\)）])?"
        r"_([A-Za-z][\w\- ]{1,40}?)"
        r"(?:\s*[\(（].*)?\s*$",
        s,
        re.I,
    )
    if m:
        out.setdefault("package_name", m.group(1).replace("_", " ").strip())
        out.setdefault("supplier_hint", m.group(2).strip())
    else:
        m = re.search(
            r"(?:Raise\s*PO|Raise\s*Procurement)[^\n]*?(?:Refresh|Project)[_\s\-]+(.+?)_([A-Za-z][\w\- ]{1,40})\s*$",
            s,
            re.I,
        )
        if m:
            out.setdefault("package_name", m.group(1).replace("_", " ").strip())
            out.setdefault("supplier_hint", m.group(2).strip())

    # Project-ish token before " - Procurement" / "Refresh"
    m = re.search(
        r"^([A-Za-z0-9][A-Za-z0-9 _/-]{1,40}?)\s*[-–—]\s*(?:Procurement|Refresh|Project)",
        s,
        re.I,
    )
    if m:
        out["project_hint"] = m.group(1).strip()

    return out


def infer_fields_from_body(body: str) -> dict[str, str]:
    """Pull package / supplier / amount / delivery from free-text Raise PO / RFQ bodies."""
    out: dict[str, str] = {}
    # raise PO to Lantro for IT cabling
    m = re.search(
        r"raise\s*PO\s+to\s+([A-Za-z][\w\- ]{1,40}?)\s+for\s+(.+?)(?:\s+contractor|\s+in\s+|\s*\.|$)",
        body,
        re.I,
    )
    if m:
        out["supplier_hint"] = m.group(1).strip()
        out["package_name"] = m.group(2).strip()

    m = re.search(
        r"(?:Approved\s+total\s+amount|total\s+(?:of\s+this\s+PR|amount)|总金额)\s*[:：]?\s*"
        r"(?:Reply:\s*)?(RMB|CNY|USD|¥)?\s*([\d,]+(?:\.\d+)?)\s*([^\n]*)",
        body,
        re.I,
    )
    if m:
        cur = (m.group(1) or "RMB").upper()
        amt = m.group(2)
        note = (m.group(3) or "").strip()
        # Prefer line right after "Approved total amount"
        out["total_amount"] = f"{cur} {amt} {note}".strip()

    # Cleaner: dedicated line RMB 83,381.16(excl.9% VAT)
    m = re.search(r"\b(RMB|CNY|USD)\s*([\d,]+(?:\.\d+)?)\s*(\([^)]+\))?", body, re.I)
    if m and "total_amount" not in out:
        out["total_amount"] = f"{m.group(1).upper()} {m.group(2)}{(m.group(3) or '')}".strip()
    elif m and re.search(r"Approved\s+total", body, re.I):
        out["total_amount"] = f"{m.group(1).upper()} {m.group(2)}{(m.group(3) or '')}".strip()

    m = re.search(
        r"(?:delivered|installed|performed|交期|服务期限)[^\n]{0,80}?"
        r"(?:from\s+)?(end of \w+ \d{4})\s+to\s+(end of \w+ \d{4})",
        body,
        re.I,
    )
    if m:
        out["delivery"] = f"{m.group(1)} – {m.group(2)}"
    else:
        m = re.search(
            r"The service will start from\s+(.+?)\s+to\s+(.+?)\.",
            body,
            re.I,
        )
        if m:
            out["delivery"] = f"{m.group(1).strip()} – {m.group(2).strip()}"

    # contact from vendor domain in To: line near Lantro
    m = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]*lantro[A-Z0-9.-]*)", body, re.I)
    if m:
        out["contact_email"] = m.group(1)

    if re.search(r"contractor|installation|安装|供装|cabling", body, re.I):
        out["package_type_hint"] = "供装"

    return out


def package_name_key(name: str) -> str:
    """Normalize for comparison: lowercase, drop separators, keep letters/digits/CJK."""
    text = (name or "").lower().replace("_", "-")
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text, flags=re.UNICODE)


def slug_package_name(name: str) -> str:
    """Folder-friendly package id; keep readable English/Chinese."""
    name = name.strip()
    # Drop trailing vendor paren if still glued onto package text
    name = re.sub(r"[\(（][^)）]+[\)）]\s*$", "", name).strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "", name)
    name = re.sub(r"[&]+", " and ", name)
    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"[^\w\u4e00-\u9fff\-]+", "", name, flags=re.UNICODE)
    name = re.sub(r"-{2,}", "-", name)
    return (name[:40] or "package").strip("-")


def find_package_fuzzy(packages: list[dict], package_name: str) -> dict | None:
    target = package_name_key(package_name)
    if not target:
        return None
    # Exact normalized key
    for pkg in packages:
        name = package_name_key(pkg.get("package_name") or "")
        if name and name == target:
            return pkg
    # Containment for near-duplicates (glazingpartitionjeb vs glazingpartition)
    for pkg in packages:
        name = package_name_key(pkg.get("package_name") or "")
        if not name:
            continue
        if target in name or name in target:
            # Avoid tiny accidental matches
            if min(len(target), len(name)) >= 6:
                return pkg
    return None


# CN key → (中文名, English name)
_PAYMENT_NAME_BI = {
    "预付款": ("预付款", "Advance"),
    "到货": ("到货", "Delivery"),
    "到货验收": ("到货验收", "Delivery acceptance"),
    "安装完成": ("安装完成", "Installation completion"),
    "尾款": ("尾款", "Final payment"),
    "验收": ("验收", "Acceptance"),
    "竣工验收": ("竣工验收", "Final acceptance"),
    "付款": ("付款", "Payment"),
}

# EN condition fragment → CN gloss
_COND_EN_TO_CN = (
    (r"upon\s+material\s+deliver\w*", "材料到货"),
    (r"material\s+deliver\w*", "材料到货"),
    (r"upon\s+deliver\w*", "到货"),
    (r"install(?:ation)?\s*complet\w*", "安装完成"),
    (r"final\s*accept\w*", "最终验收"),
    (r"accept\w*", "验收"),
    (r"prepayment|advance\s*payment|deposit", "预付"),
)


def _bilingual(cn: str, en: str) -> str:
    cn = (cn or "").strip()
    en = (en or "").strip()
    if cn and en and cn.lower() != en.lower():
        return f"{cn} / {en}"
    return cn or en


def _payment_name_pair(cond: str) -> tuple[str, str]:
    c = cond.lower()
    if re.search(r"prepayment|advance|deposit|预付", c):
        return _PAYMENT_NAME_BI["预付款"]
    if re.search(r"install(?:ation)?\s*complet|安装完成", c):
        return _PAYMENT_NAME_BI["安装完成"]
    if re.search(r"material\s*deliver|upon\s+deliver|到货", c):
        return _PAYMENT_NAME_BI["到货"]
    if re.search(r"final\s*accept|竣工|终验|尾款|retention", c):
        return _PAYMENT_NAME_BI["尾款"]
    if re.search(r"accept|验收", c):
        return _PAYMENT_NAME_BI["验收"]
    short = cond.strip()[:24] or "付款"
    return short, short


def _condition_bilingual(cond: str, scope: str = "") -> str:
    cond = (cond or "").strip()
    cn_gloss = ""
    for pat, gloss in _COND_EN_TO_CN:
        if re.search(pat, cond, re.I):
            cn_gloss = gloss
            break
    # Already mostly Chinese
    if re.search(r"[\u4e00-\u9fff]", cond) and not re.search(r"[A-Za-z]{3,}", cond):
        bi = cond
    else:
        bi = _bilingual(cn_gloss, cond) if cn_gloss else cond
    if scope:
        return f"{scope} · {bi}"
    return bi


def _node(name_cn: str, name_en: str, pct: str, condition: str) -> dict[str, str]:
    return {
        "name": _bilingual(name_cn, name_en),
        "pct": pct if pct.endswith("%") else f"{pct}%",
        "condition": condition,
        "source": "邮件指示 / Email instruction",
    }


def parse_payment_nodes(body: str) -> list[dict[str, str]]:
    """Parse payment milestones from any mail body (CN or EN). Output names/conditions in 中+英."""
    nodes: list[dict[str, str]] = []
    for m in re.finditer(
        r"(\d+)[\.、]\s*(预付款|到货验收|尾款|到货|安装完成|竣工验收)[^\d%]*?(\d+)\s*%[，,]?\s*(.*)",
        body,
    ):
        key = m.group(2)
        cn, en = _PAYMENT_NAME_BI.get(key, (key, key))
        cond_raw = (m.group(4) or "").strip().rstrip("。；;")
        nodes.append(_node(cn, en, f"{m.group(3)}%", _condition_bilingual(cond_raw)))
    if nodes:
        return nodes

    for name in ("预付款", "到货验收", "到货", "尾款", "安装完成"):
        m = re.search(rf"{name}\s*(\d+)\s*%", body)
        if m:
            cn, en = _PAYMENT_NAME_BI[name]
            nodes.append(_node(cn, en, f"{m.group(1)}%", ""))
    if nodes:
        return nodes

    scope = ""
    for raw in body.splitlines():
        line = raw.strip().rstrip(";")
        if not line:
            continue
        if re.search(r"请款条件|付款条件|付款指示|payment\s*terms|payment\s*milestone", line, re.I):
            continue
        m_scope = re.match(r"^([A-Za-z][\w\s/&]+?)\s*[-–—]\s*$", line)
        if m_scope and "%" not in line:
            scope = m_scope.group(1).strip()
            continue
        m = re.match(r"^(\d+)\s*%\s+(.+)$", line, re.I)
        if not m:
            m = re.match(r"^(\d+)\s*%\s*[·\-–—,]?\s*(.+)$", line, re.I)
        if m:
            cond = m.group(2).strip()
            cn, en = _payment_name_pair(cond)
            nodes.append(_node(cn, en, f"{m.group(1)}%", _condition_bilingual(cond, scope)))
    return nodes


def apply_payment_from_body(
    project_root: Path,
    pkg_dir: Path,
    package_name: str,
    body: str,
    subject: str,
    result: dict[str, Any],
    *,
    extra_patch: dict[str, Any] | None = None,
) -> bool:
    """Whenever payment text appears in any related mail, write card payment section (CN+EN)."""
    nodes = parse_payment_nodes(body)
    if not nodes:
        return False
    patch: dict[str, Any] = {
        "payment_nodes": nodes,
        "data_sources": (
            f"邮件 {subject.strip()[:80]}；"
            f"付款条件随邮件写入 / Payment terms captured from email"
        ),
    }
    if extra_patch:
        # Keep caller data_sources if provided; still note payment capture
        ds = extra_patch.get("data_sources")
        if ds:
            patch["data_sources"] = (
                f"{ds}；付款条件随邮件写入 / Payment terms captured from email"
            )
        for k, v in extra_patch.items():
            if k == "data_sources":
                continue
            if v is not None and v != "":
                patch[k] = v
    render_package_card(pkg_dir, patch)
    sync_next_payment_from_card(project_root, package_name)
    result["payment_nodes"] = len(nodes)
    return True


def add_pending(project_root: Path, item: dict[str, Any], *, skill: str = "contract-fulfillment-struct") -> str:
    """Skill 1 写 pending.json。其它 Skill 必须直接调 pending_store 并声明自己的 skill。"""
    return store_add_pending(project_root, item, skill=skill)


def confidence_ok(step: str, fields: dict[str, str]) -> bool:
    if step == "step1":
        # Supplier may be unknown on first RFQ forward; package + type is enough to open the package
        return bool(fields.get("package_name") and fields.get("package_type"))
    if step in ("step2", "step3", "step4_contract", "step4_payment"):
        return bool(fields.get("package_name"))
    return False


def process_eml_file(
    project_root: Path | None,
    eml_path: Path,
    attachment_paths: list[str] | None = None,
    *,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eml_path = eml_path.expanduser().resolve()
    raw = eml_path.read_bytes()
    msg = email.message_from_bytes(raw)
    subject = decode_mime_header(msg.get("Subject"))
    body = get_body_text(msg)
    intent = str((classification or {}).get("intent") or "")
    if not classification:
        classification = classify_from_message(
            subject=subject,
            body=body,
            eml_path=str(eml_path),
            project_root=str(project_root) if project_root else "",
            attachments=collect_attachment_meta(msg),
        )
        intent = str(classification.get("intent") or "")
    step = intent_to_step(intent)
    subj_bits = parse_subject_triple(subject)
    inferred = infer_fields_from_subject(subject)
    body_bits = infer_fields_from_body(body)

    result: dict[str, Any] = {
        "eml_path": str(eml_path),
        "subject": subject,
        "step": step,
        "auto": False,
    }
    if intent:
        result["intent"] = intent
    result["from_classification"] = True

    # Skill 1 only handles fulfillment.*; redirect misroutes
    if intent == "project_init" or step == "stage0":
        note = (
            "项目初始化已迁出 Skill 1。请经 mail-inbox 分发到 Skill 0 "
            "`project-init/scripts/handle_init_email.py`，或运行基建库 `init_project.py`（Skill 0）。"
        )
        if project_root is not None:
            project_root = project_root.expanduser().resolve()
            pid = add_pending(
                project_root,
                {
                    "step": "project_init",
                    "fields": {
                        "package_name": inferred.get("package_name") or "",
                        "subject": subject,
                    },
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "routed_to_skill0",
                    "note": note,
                },
            )
            result["pending_id"] = pid
        result["step"] = "stage0"
        result["reason"] = "routed_to_skill0"
        result["note"] = note
        return result

    # 兜底拒收：正常路径应由 mail-inbox 分到 Skill 3；此处发现变更/Change PO 则推开，不在 Skill 1 办件
    if intent.startswith("change.") or is_change_po_mail(subject, body):
        note = (
            "变更 / Change PO 已迁出 Skill 1。请经 mail-inbox 分发到 Skill 3 "
            "`change-archive/scripts/handle_change_email.py`；本 Skill 不再写 change_po_deferred。"
            "（本分支仅为绕过邮局时的拒收兜底，不是第二套分类器。）"
        )
        if project_root is None:
            raise ValueError("project_root required for change mail redirect")
        project_root = project_root.expanduser().resolve()
        pid = add_pending(
            project_root,
            {
                "step": intent or "change.change_po",
                "fields": {
                    "package_name": inferred.get("package_name") or body_bits.get("package_name") or "",
                    "supplier_name": inferred.get("supplier_hint") or body_bits.get("supplier_hint") or "",
                    "subject": subject,
                },
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "routed_to_skill3",
                "note": note,
            },
        )
        result["step"] = "change_po"
        result["pending_id"] = pid
        result["reason"] = "routed_to_skill3"
        result["note"] = note
        return result

    # Fulfillment steps need existing project
    if project_root is None:
        raise ValueError("project_root required for fulfillment mail")
    project_root = project_root.expanduser().resolve()
    project = load_json(system_file(project_root, PROJECT_JSON)) or {}

    package_name = (
        extract_field(body, ["采购包", "采购包名称"])
        or subj_bits.get("package_name", "")
        or inferred.get("package_name", "")
        or body_bits.get("package_name", "")
    )
    # Prefer slug for English descriptive names (folder-safe); keep Chinese as-is if short
    if package_name and re.search(r"[A-Za-z]", package_name):
        package_name = slug_package_name(package_name)
    else:
        package_name = re.sub(r"[（(].*$", "", package_name).strip()

    supplier_name = (
        extract_field(body, ["供应商", "供应商名称"])
        or subj_bits.get("supplier_hint", "")
        or inferred.get("supplier_hint", "")
        or body_bits.get("supplier_hint", "")
    )
    supplier_name = re.sub(r"\s*[—\-].*$", "", supplier_name).strip()
    if not supplier_name and step == "step1":
        # First RFQ forward often has no supplier line yet
        supplier_name = "待确认"

    contact = extract_field(body, ["对接人邮箱"]) or body_bits.get("contact_email", "")
    supplier_contacts = collect_supplier_contact_emails(msg, body, supplier_name)
    contact = merge_contact_emails(contact, supplier_contacts)
    if not contact:
        m = re.search(r"对接人[^\n]{0,20}([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", body, re.I)
        contact = m.group(1) if m else ""

    type_raw = (
        extract_field(body, ["类型", "采购包类型"])
        or body_bits.get("package_type_hint", "")
    )
    package_type = TYPE_MAP.get(type_raw, type_raw or "供应")
    if package_type not in ("供应", "供装", "顾问", "总包"):
        package_type = "供应"

    # Prefer explicit 含税/不含税 labels — bare「金额」不会匹配「金额含税：…」
    amount_incl_raw = extract_field(body, ["金额含税", "含税金额"])
    amount_excl_raw = extract_field(body, ["金额不含税", "不含税金额"])
    amount_raw = (
        extract_field(body, ["最终金额", "总金额", "金额"])
        or body_bits.get("total_amount", "")
        or amount_incl_raw
        or amount_excl_raw
    )
    amount_info: dict[str, Any] = {
        "amount_excl_tax": "",
        "amount_incl_tax": "",
        "tax_uncertain": False,
        "raw": amount_raw,
    }
    if amount_excl_raw:
        parsed_excl = parse_amount_with_tax(f"{amount_excl_raw} 不含税")
        amount_info["amount_excl_tax"] = parsed_excl.get("amount_excl_tax") or ""
        if parsed_excl.get("amount_incl_tax"):
            amount_info["amount_incl_tax"] = parsed_excl["amount_incl_tax"]
        amount_info["tax_uncertain"] = bool(parsed_excl.get("tax_uncertain"))
    if amount_incl_raw:
        parsed_incl = parse_amount_with_tax(f"{amount_incl_raw} 含税")
        amount_info["amount_incl_tax"] = parsed_incl.get("amount_incl_tax") or ""
        if parsed_incl.get("amount_excl_tax") and not amount_info["amount_excl_tax"]:
            amount_info["amount_excl_tax"] = parsed_incl["amount_excl_tax"]
        amount_info["tax_uncertain"] = bool(parsed_incl.get("tax_uncertain")) or bool(
            amount_info.get("tax_uncertain")
        )
    if amount_raw and not (amount_info["amount_excl_tax"] or amount_info["amount_incl_tax"]):
        amount_info = parse_amount_with_tax(amount_raw)
    if amount_info.get("amount_excl_tax") and amount_info.get("amount_incl_tax"):
        amount_info["tax_uncertain"] = False
    elif amount_info.get("amount_excl_tax") or amount_info.get("amount_incl_tax"):
        amount_info["tax_uncertain"] = True
    event_at = email_event_time(msg)

    fields = {
        "package_name": package_name,
        "supplier_name": supplier_name,
        "contact_email": contact,
        "package_type": package_type,
        "project_code": subj_bits.get("project_code")
        or project.get("project_code", "")
        or inferred.get("project_hint", ""),
        "project_hint": inferred.get("project_hint", ""),
        "total_amount": amount_raw,
        "amount_excl_tax": amount_info.get("amount_excl_tax", ""),
        "amount_incl_tax": amount_info.get("amount_incl_tax", ""),
        "tax_uncertain": bool(amount_info.get("tax_uncertain")),
        "delivery": extract_field(body, ["交期"]) or body_bits.get("delivery", ""),
        "scope_summary": extract_field(
            body, ["范围", "服务范围", "工作范围", "Scope", "Description of work", "服务内容"]
        )
        or inferred.get("package_hint_raw", "")
        or body_bits.get("package_name", ""),
        "event_at": event_at,
    }
    result["fields"] = fields

    if step == "unknown" or not confidence_ok(step, fields):
        pid = add_pending(project_root, {
            "step": step,
            "fields": fields,
            "subject": subject,
            "eml_path": str(eml_path),
            "reason": "low_confidence" if step != "unknown" else "unknown_step",
        })
        result["pending_id"] = pid
        result["reason"] = result["fields"] and ("low_confidence" if step != "unknown" else "unknown_step")
        return result

    packages = load_tracker_packages(project_root)
    supplier_short = (supplier_name[:6] if supplier_name and supplier_name != "待确认" else "待确认")

    if step == "step1":
        existing = find_package_fuzzy(packages, package_name)
        if existing:
            pkg_dir = Path(existing["folder_path"])
            archive_eml_correspondence(eml_path, pkg_dir, existing["package_name"], description="RFP邮件")
            update_package(
                project_root,
                package_name=existing["package_name"],
                contact_email=contact,
                supplier_name=supplier_name or None,
                milestone_at=event_at,
            )
            apply_payment_from_body(
                project_root,
                pkg_dir,
                existing["package_name"],
                body,
                subject,
                result,
                extra_patch={
                    "supplier_name": supplier_name or existing.get("supplier_name") or "",
                    "contact_email": contact,
                },
            )
            result["auto"] = True
            result["note"] = "package_already_exists"
            result["package"] = existing
            return result
        add_package(
            project_root,
            package_name=package_name,
            supplier_name=supplier_name,
            supplier_short=supplier_short,
            contact_email=contact,
            package_type=package_type,
            milestone="ts_rfp_issued",
            milestone_at=event_at,
        )
        packages = load_tracker_packages(project_root)
        pkg = find_package_fuzzy(packages, package_name)
        if not pkg:
            raise RuntimeError(f"package not found after add-package: {package_name}")
        package_name = pkg["package_name"]
        pkg_dir = Path(pkg["folder_path"])
        archive_eml_correspondence(eml_path, pkg_dir, package_name, description="RFP邮件")
        # RFP drawings/docs only — skip signature images in 02
        for att in attachment_paths or []:
            p = Path(att)
            ext = p.suffix.lower()
            if ext in {".gif"} or (
                ext in {".png", ".jpg", ".jpeg"}
                and re.match(r"image\d+", p.stem, re.I)
            ):
                continue
            archive_file(
                source=p,
                dest_dir=pkg_dir / "02_图纸",
                package_name=package_name,
                file_type="附件",
                description="邮件附件",
            )
        wrote_pay = apply_payment_from_body(
            project_root,
            pkg_dir,
            package_name,
            body,
            subject,
            result,
            extra_patch={
                "scope_summary": fields.get("scope_summary") or "",
                "contact_email": contact,
                "supplier_name": supplier_name,
                "data_sources": f"邮件 {subject.strip()[:80]}",
            },
        )
        if not wrote_pay:
            render_package_card(pkg_dir, {
                "scope_summary": fields.get("scope_summary") or "",
                "data_sources": f"邮件 {subject.strip()[:80]}",
                "contact_email": contact,
                "supplier_name": supplier_name,
            })
        result["auto"] = True
        result["package_name"] = package_name
        return result

    # Locate package for later steps; Raise PO may arrive before RFQ — bootstrap package
    pkg = find_package_fuzzy(packages, package_name)
    if not pkg and step in ("step2", "step3", "step4_contract", "step4_payment"):
        if package_name and supplier_name:
            add_package(
                project_root,
                package_name=package_name,
                supplier_name=supplier_name,
                supplier_short=supplier_short,
                contact_email=contact,
                package_type=package_type,
                amount_excl_tax=fields.get("amount_excl_tax") or "",
                amount_incl_tax=fields.get("amount_incl_tax") or "",
                delivery_summary=fields.get("delivery") or "",
                milestone_at=event_at,
            )
            packages = load_tracker_packages(project_root)
            pkg = find_package_fuzzy(packages, package_name)
            result["note"] = "package_bootstrapped_from_later_step"
    if not pkg:
        pid = add_pending(project_root, {
            "step": step,
            "fields": fields,
            "subject": subject,
            "eml_path": str(eml_path),
            "reason": "package_not_found",
        })
        result["pending_id"] = pid
        return result

    # Prefer canonical tracker name so later updates hit the same row
    package_name = pkg["package_name"]
    fields["package_name"] = package_name
    pkg_dir = Path(pkg["folder_path"])
    archive_eml_correspondence(eml_path, pkg_dir, package_name, description={
        "step2": "技术确认",
        "step3": "RaisePO",
        "step4_payment": "付款指示",
        "step4_contract": "合同邮件",
    }.get(step, "往来邮件"))

    if step == "step2":
        for att in attachment_paths or []:
            p = Path(att)
            if p.suffix.lower() == ".gif" or re.match(r"image\d+", p.stem, re.I):
                continue
            archive_file(
                source=p,
                dest_dir=pkg_dir / "02_图纸",
                package_name=package_name,
                file_type="技术图",
                description="顾问确认",
                version="v终版",
            )
        update_package(
            project_root,
            package_name=package_name,
            milestone="ts_tech_confirmed",
            contact_email=contact,
            milestone_at=event_at,
        )
        wrote_pay = apply_payment_from_body(
            project_root, pkg_dir, package_name, body, subject, result,
            extra_patch={"data_sources": f"顾问确认 {subject}", "contact_email": contact},
        )
        if not wrote_pay:
            render_package_card(pkg_dir, {"data_sources": f"顾问确认 {subject}", "contact_email": contact})
        result["auto"] = True
        return result

    if step == "step3":
        skipped, archived_quotes = archive_quote_attachments(
            attachment_paths, pkg_dir, package_name,
            file_type="报价单", description="最终报价",
        )
        if skipped:
            result["skipped_attachments"] = skipped
        # Also scan already-on-disk quotes under 01_合同报价
        quote_dir = pkg_dir / "01_合同报价"
        on_disk = [
            p for p in quote_dir.glob("*")
            if p.is_file() and p.suffix.lower() in {".xls", ".xlsx", ".xlsm", ".csv", ".pdf"}
        ] if quote_dir.exists() else []
        amount_merged = merge_amount_fields(amount_info, list(archived_quotes) + on_disk)
        fields["amount_excl_tax"] = amount_merged["amount_excl_tax"]
        fields["amount_incl_tax"] = amount_merged["amount_incl_tax"]
        fields["tax_uncertain"] = amount_merged["tax_uncertain"]
        if amount_merged.get("quote_source"):
            result["quote_amount_source"] = amount_merged["quote_source"]
        result["amount_source"] = amount_merged.get("amount_source") or ""
        if amount_merged.get("body_quote_mismatch"):
            result["body_quote_mismatch"] = True
        if amount_merged.get("quote_unparsed"):
            result["quote_unparsed"] = True

        upd_kw: dict[str, Any] = {
            "milestone": "ts_po_issued",
            "delivery_summary": fields.get("delivery") or "",
            "contact_email": contact,
            "milestone_at": event_at,
        }
        if fields.get("amount_excl_tax"):
            upd_kw["amount_excl_tax"] = fields["amount_excl_tax"]
        if fields.get("amount_incl_tax"):
            upd_kw["amount_incl_tax"] = fields["amount_incl_tax"]
        update_package(project_root, package_name=package_name, **upd_kw)
        display_amt = fields.get("amount_incl_tax") or fields.get("amount_excl_tax") or ""
        src_note = amount_merged.get("amount_source") or ""
        step3_patch = {
            "total_amount": display_amt,
            "delivery_schedule": fields.get("delivery") or "",
            "contact_email": contact,
            "scope_summary": fields.get("scope_summary") or "",
            "data_sources": f"Raise PO {subject}"
            + (f" · 金额来源={src_note}" if src_note else ""),
        }
        wrote_pay = apply_payment_from_body(
            project_root, pkg_dir, package_name, body, subject, result,
            extra_patch=step3_patch,
        )
        if not wrote_pay:
            render_package_card(pkg_dir, step3_patch)

        # Pendings: mismatch / quote unparsed / tax incomplete (one pending_id = last written)
        if amount_merged.get("body_quote_mismatch"):
            pid = add_pending(
                project_root,
                {
                    "step": step,
                    "fields": {
                        **fields,
                        "body_excl": amount_merged.get("body_amount_excl_tax") or "",
                        "body_incl": amount_merged.get("body_amount_incl_tax") or "",
                        "used_excl": fields.get("amount_excl_tax") or "",
                        "used_incl": fields.get("amount_incl_tax") or "",
                        "quote_source": amount_merged.get("quote_source") or "",
                        "amount_source": amount_merged.get("amount_source") or "",
                    },
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "amount_mismatch_body_vs_quote",
                    "note": (
                        "报价附件金额与邮件正文不一致——已按附件写入 Tracker；请人工核对。"
                        " / Quote attachment ≠ email body; Tracker used attachment. Please confirm."
                    ),
                },
            )
            result["pending_id"] = pid
        elif amount_merged.get("quote_unparsed"):
            pid = add_pending(
                project_root,
                {
                    "step": step,
                    "fields": fields,
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "quote_amount_unparsed",
                    "note": (
                        "有报价附件但脚本未能抽出金额"
                        + ("——暂用正文金额，请打开附件确认。" if (amount_raw or fields.get("amount_excl_tax")) else "——请打开附件读出含税/不含税。")
                        + " / Quote file present but unparsed; confirm amounts from attachment."
                    ),
                },
            )
            result["pending_id"] = pid
        elif fields.get("tax_uncertain") and (amount_raw or fields.get("amount_excl_tax")):
            pid = add_pending(project_root, {
                "step": step,
                "fields": fields,
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "tax_rate_uncertain",
                "note": "已写入金额，但含税/不含税不完整——请确认税率或另一侧金额"
                " / Amount saved but tax incl/excl incomplete — confirm VAT rate",
            })
            result["pending_id"] = pid
            result["tax_uncertain"] = True
        result["auto"] = True
        return result

    if step == "step4_payment":
        update_package(
            project_root,
            package_name=package_name,
            contact_email=contact,
            milestone_at=event_at,
        )
        if not apply_payment_from_body(
            project_root, pkg_dir, package_name, body, subject, result,
            extra_patch={"data_sources": f"付款指示 / Payment instruction {subject}"},
        ):
            pid = add_pending(project_root, {
                "step": step,
                "fields": fields,
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "payment_nodes_unparsed",
            })
            result["pending_id"] = pid
            return result
        result["auto"] = True
        return result

    if step == "step4_contract":
        skipped, _archived = archive_quote_attachments(
            attachment_paths, pkg_dir, package_name,
            file_type="合同", description="合同",
        )
        if skipped:
            result["skipped_attachments"] = skipped
        update_package(
            project_root,
            package_name=package_name,
            contact_email=contact,
            milestone_at=event_at,
        )
        apply_payment_from_body(
            project_root, pkg_dir, package_name, body, subject, result,
            extra_patch={"data_sources": f"合同邮件 / Contract email {subject}"},
        )
        pid = add_pending(project_root, {
            "step": step,
            "fields": fields,
            "subject": subject,
            "eml_path": str(eml_path),
            "reason": "contract_payment_needs_review",
            "note": "合同已归档；付款节点请 Agent/PM 确认后写入卡片"
            " / Contract archived; confirm payment nodes if not already captured from body",
        })
        result["pending_id"] = pid
        result["archived"] = True
        return result

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Process one .eml file")
    parser.add_argument("--eml", required=True)
    parser.add_argument("--project-root", default="", help="Required for fulfillment mail")
    parser.add_argument("--attachment", action="append", default=[])
    parser.add_argument(
        "--route-json",
        default="",
        help="Pre-classification JSON from mail-inbox classify_mail / dispatch_mail",
    )
    args = parser.parse_args()
    root = Path(args.project_root) if args.project_root else None
    classification = None
    if args.route_json:
        classification = json.loads(Path(args.route_json).expanduser().read_text(encoding="utf-8"))
    try:
        result = process_eml_file(
            root,
            Path(args.eml),
            attachment_paths=args.attachment,
            classification=classification,
        )
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
