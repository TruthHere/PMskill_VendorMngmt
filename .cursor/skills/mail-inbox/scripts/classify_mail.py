#!/usr/bin/env python3
"""Classify a single mail into Skill 0/1/2/3 intents."""

from __future__ import annotations

import argparse
import email
import json
import re
from email.header import decode_header
from pathlib import Path
from typing import Any


def _safe_charset(charset: str | None) -> str:
    if not charset:
        return "utf-8"
    c = charset.strip().lower()
    if c in {"unknown-8bit", "unknown", "x-unknown", "8bit", "binary"}:
        return "utf-8"
    return charset


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, charset in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(_safe_charset(charset), errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


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
    joined = "\n".join(htmls)
    joined = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", joined)
    joined = re.sub(r"(?s)<[^>]+>", " ", joined)
    joined = re.sub(r"&nbsp;", " ", joined)
    joined = re.sub(r"\s+", " ", joined)
    return joined.strip()


def parse_subject_triple(subject: str) -> dict[str, str]:
    subject = re.sub(r"\s+", " ", subject.replace("\r", " ").replace("\n", " "))
    m = re.match(
        r"^\s*(?:FW:\s*|Fwd:\s*|RE:\s*)*([^·—\-]+)\s*[·•]\s*([^·—\-]+)\s*[·•]\s*([^—\-]+)",
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
    s = re.sub(r"\s+", " ", subject.replace("\r", " ").replace("\n", " ")).strip()
    s = re.sub(r"^(?:FW|Fwd|RE)\s*:\s*", "", s, flags=re.I)
    out: dict[str, str] = {}

    trailing_paren = None
    m_paren = re.search(r"[\(（]([^)）]+)[\)）]\s*$", s)
    if m_paren and re.search(r"\b(?:RFQ|RFP)\b", s, re.I):
        trailing_paren = m_paren.group(1).strip()
        s_noparen = s[: m_paren.start()].rstrip()
    else:
        s_noparen = s

    m = re.search(r"\b(?:RFQ|RFP)\b\s+for\s+(.+?)(?:\s+[—\-|]\s*|\s*$)", s_noparen, re.I)
    if m:
        pkg = m.group(1).strip()
        if not trailing_paren:
            pkg = re.sub(r"[\(（][^)）]*[\)）]\s*$", "", pkg).strip()
        out["package_name"] = pkg
    if trailing_paren:
        out["supplier_hint"] = trailing_paren

    # Payment Application No. N for {package} …
    if not out.get("package_name"):
        m_pay = re.search(
            r"(?:payment\s+application|请款)\s*(?:no\.?\s*\d+\s*)?for\s+([A-Za-z0-9][\w\- /]{0,40})",
            s,
            re.I,
        )
        if m_pay:
            pkg = m_pay.group(1).strip()
            pkg = re.sub(r"\s*[-—].*$", "", pkg).strip()
            if pkg:
                out["package_name"] = pkg
    return out


def infer_fields_from_body(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    m = re.search(
        r"raise\s*po\s+to\s+([A-Za-z][\w\- ]{1,40}?)\s+for\s+(.+?)(?:\s+contractor|\s+in\s+|\s*\.|$)",
        body,
        re.I,
    )
    if m:
        out["supplier_hint"] = m.group(1).strip()
        out["package_name"] = m.group(2).strip()
    return out


def collect_attachment_meta(msg: email.message.Message) -> list[dict[str, str]]:
    attachments: list[dict[str, str]] = []
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        name = decode_mime_header(filename).strip()
        lower = name.lower()
        kind = "other"
        if re.search(r"\.(xlsx|xlsm|xls|csv)$", lower):
            kind = "quote"
        elif re.search(r"\.(dwg|pdf)$", lower) and re.search(r"drawing|图|shop", lower, re.I):
            kind = "drawing"
        elif re.search(r"\.(mpp|xml|xlsx|xls|csv)$", lower) and re.search(r"schedule|plan|进度", lower, re.I):
            kind = "schedule"
        elif re.search(r"\.(pdf|docx?|xlsx?)$", lower) and re.search(r"contract|合同", lower, re.I):
            kind = "contract"
        attachments.append({"filename": name, "kind": kind})
    return attachments


def detect_fulfillment_step(subject: str, body: str) -> str:
    subject_n = re.sub(r"\s+", " ", subject.replace("\r", " ").replace("\n", " ")).strip()
    blob = f"{subject_n}\n{body}"
    blob_l = blob.lower()

    if re.search(
        r"\brfq\b|\brfp\b|request\s+for\s+(quot|propos)|询价|招标|采购邀请|"
        r"invitation\s+to\s+tender|\bitb\b|procurement.*\b(rfq|rfp)\b|\b(rfq|rfp)\b.*for\b",
        blob_l,
    ):
        return "fulfillment.rfp"
    if re.search(
        r"付款条件|付款指示|payment\s*terms|payment\s*instruction",
        blob,
        re.I,
    ):
        return "fulfillment.payment_terms"
    if re.search(
        r"顾问确认|技术确认|技术文件|tech(?:nical)?\s*confirm|approved\s*drawing",
        blob,
        re.I,
    ):
        return "fulfillment.tech_confirm"
    if re.search(
        r"raise\s*po|raise\s*procurement|发出\s*po|已发\s*po|purchase\s*order|\bpr\s*邮件\b|定标.*po",
        blob_l,
    ):
        return "fulfillment.raise_po"
    if re.search(r"\b合同\b|\bcontract\b", blob, re.I) and not re.search(r"\brfq\b|\brfp\b|询价|招标", blob_l):
        if re.search(r"合同|contract", subject_n, re.I):
            return "fulfillment.contract"
    return "unknown"


def extract_change_no(subject: str, body: str) -> str:
    blob = f"{subject}\n{body}"
    m = re.search(r"\b(COD|PMI|COT)\s*[- ]?(\d{2,5})\b", blob, re.I)
    if m:
        return f"{m.group(1).upper()}{m.group(2)}"
    return ""


def has_change_anchor(subject: str, body: str) -> bool:
    """变更专属锚点：有序号，或主题/正文明确点名 COD/PMI/COT/变更序号。

    缺锚点时，不得把履约「技术确认/图纸」抢进 Skill 3。
    """
    if extract_change_no(subject, body):
        return True
    blob = f"{subject}\n{body}"
    return bool(
        re.search(
            r"\b(?:COD|PMI|COT)\b|变更序号|变更洽商|Change\s*Order\s*Document|项目经理指令",
            blob,
            re.I,
        )
    )


def is_change_po_mail(subject: str, body: str = "") -> bool:
    """真 Change PO，不是采购 FAQ 里的 “If this PR is a change order…original PO”。"""
    blob = f"{subject}\n{body}"
    if re.search(r"change\s*po|变更\s*po|增补\s*po", blob, re.I):
        return True
    if re.search(r"(?:raise|issue|发出|下发)\s+change\s*order", blob, re.I):
        return True
    if re.search(r"change\s*order\s+(?:po|purchase\s*order)\b", blob, re.I):
        return True
    return False


def has_strong_cod_signal(subject: str, body: str) -> bool:
    """COD 要够硬：主题带 COD / 正文带序号或正式全称；随口提 COD process 不算。"""
    subject_n = re.sub(r"\s+", " ", subject.replace("\r", " ").replace("\n", " ")).strip()
    if re.search(r"\bCOD\b|Change\s*Order\s*Document|变更通知|变更确认", subject_n, re.I):
        return True
    if re.search(r"Change\s*Order\s*Document|变更通知|变更确认", body, re.I):
        return True
    if re.search(r"\bCOD\s*[- ]?\d{2,5}\b", body, re.I):
        return True
    return False


def detect_change_intent(subject: str, body: str) -> str:
    blob = f"{subject}\n{body}"
    if is_change_po_mail(subject, body):
        return "change.change_po"
    if re.search(r"\bPMI\b|Project\s*Manager\s*Instruction|项目经理指令", blob, re.I):
        return "change.pmi"
    if has_strong_cod_signal(subject, body):
        return "change.cod"
    if re.search(r"商务金额确认|cp\s*confirm|commercial\s*amount", blob, re.I):
        return "change.commercial_amount"
    # 以下与履约关键词重叠：无变更锚点则放行给 fulfillment.*
    if not has_change_anchor(subject, body):
        return ""
    if re.search(r"商务确认|commercial\s*confirm", blob, re.I):
        return "change.commercial"
    if re.search(r"顾问终版|技术确认|approved\s*drawing", blob, re.I):
        return "change.tech_confirm"
    if re.search(r"技术文件|图纸|submittal|shop\s*drawing", blob, re.I):
        return "change.tech_submit"
    return ""


def detect_payment_claim_intent(subject: str, body: str) -> str:
    """请款五步子意图；须先确认这是请款信。"""
    blob = f"{subject}\n{body}"
    if re.search(
        r"客户批复|业主批复|批复请款|同意支付|claim\s*approved|"
        r"payment\s*(?:application\s*)?approved|apple\s*approved|"
        r"certified\s+this\s+claim",
        blob,
        re.I,
    ):
        return "payment_claim.client_approved"
    if re.search(
        r"\bQS\b.*(?:confirm|confirmed|核对|确认金额)|"
        r"(?:工料测量|造价咨询).*(?:确认|核对)|"
        r"QS\s*confirm|确认金额如下|核对后金额",
        blob,
        re.I,
    ):
        return "payment_claim.qs_confirm"
    if re.search(
        r"已发(?:给)?客户|已提交客户|提交请款给(?:客户|甲方|apple)|"
        r"sent\s+to\s+(?:the\s+)?(?:client|apple|owner)",
        blob,
        re.I,
    ):
        return "payment_claim.client_sent"
    if re.search(
        r"已发(?:给)?QS|发给QS|请QS核对|sent\s+to\s+QS",
        blob,
        re.I,
    ):
        return "payment_claim.qs_sent"
    return "payment_claim.inbound"


def detect_payment_claim(subject: str, body: str) -> bool:
    blob = f"{subject}\n{body}"
    if re.search(
        r"payment\s*application|payment\s*claim|请款申请|请款单|progress\s*claim",
        blob,
        re.I,
    ):
        return True
    if re.search(r"payment\s*no\s*[:：#]?\s*\d+", blob, re.I):
        return True
    # 裸 invoice/发票太宽；须同时有请款语境
    if re.search(r"\binvoice\b|发票", blob, re.I) and re.search(
        r"请款|payment\s*(?:application|claim|request)|申请付款",
        blob,
        re.I,
    ):
        return True
    return False


def classify_intent(subject: str, body: str) -> str:
    if re.search(r"\[项目初始化\]|项目初始化", subject, re.I):
        return "project_init"
    change_intent = detect_change_intent(subject, body)
    if change_intent:
        return change_intent
    step = detect_fulfillment_step(subject, body)
    if step != "unknown":
        return step
    if detect_payment_claim(subject, body):
        return detect_payment_claim_intent(subject, body)
    return "unknown"


def route_to(intent: str) -> str | None:
    if intent == "project_init":
        return "project-init"
    if intent.startswith("fulfillment."):
        return "contract-fulfillment-struct"
    if intent.startswith("change."):
        return "change-archive"
    if intent.startswith("payment_claim."):
        return "payment-request"
    return None


def confidence_for(intent: str, hints: dict[str, str]) -> str:
    if intent == "unknown":
        return "low"
    if intent in {"project_init", "change.change_po"}:
        return "high"
    if intent.startswith("change.") and not hints.get("change_no"):
        return "medium"
    if intent.startswith("fulfillment.") and not hints.get("package_name"):
        return "medium"
    return "high"


def build_enrichment(body: str, attachments: list[dict[str, str]]) -> dict[str, bool]:
    kinds = {a["kind"] for a in attachments}
    return {
        "payment_terms": bool(
            re.search(r"付款条件|付款指示|请款条件|payment\s*terms|payment\s*milestone", body, re.I)
        ),
        "has_quote_attachment": "quote" in kinds,
        "has_drawing": "drawing" in kinds,
        "schedule_attachment": "schedule" in kinds,
    }


def classify_from_message(
    *,
    subject: str,
    body: str,
    eml_path: str = "",
    project_root: str = "",
    attachments: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    attachments = attachments or []
    triple = parse_subject_triple(subject)
    subj = infer_fields_from_subject(subject)
    body_fields = infer_fields_from_body(body)
    hints = {**triple, **subj, **body_fields}
    hints["subject"] = subject
    hints["change_no"] = extract_change_no(subject, body)

    intent = classify_intent(subject, body)
    confidence = confidence_for(intent, hints)
    enrichment = build_enrichment(body, attachments)

    pending = None
    if confidence == "low":
        pending = {
            "reason": "intent_low_confidence",
            "question": "邮件意图置信度低，需确认交给哪个 Skill。",
            "candidates": ["project-init", "contract-fulfillment-struct", "payment-request", "change-archive"],
        }

    route = route_to(intent)
    next_action = {
        "skill": route,
        "action": f"handle_{intent.replace('.', '_')}" if route else "pending_only",
        "note": "业务 Skill 消费本 JSON；mail-inbox 不改业务数据",
    }
    return {
        "ok": True,
        "eml_path": eml_path,
        "intent": intent,
        "route_to": route,
        "confidence": confidence,
        "project_root": project_root,
        "hints": hints,
        "enrichment": enrichment,
        "attachments": attachments,
        "pending": pending,
        "did": ["ingest", "classify"],
        "next": next_action,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", default="")
    ap.add_argument("--eml", default="")
    ap.add_argument("--subject", default="")
    ap.add_argument("--body", default="")
    args = ap.parse_args()

    subject = args.subject
    body = args.body
    attachments: list[dict[str, str]] = []
    eml_path = args.eml
    if args.eml:
        path = Path(args.eml).expanduser().resolve()
        msg = email.message_from_bytes(path.read_bytes())
        subject = decode_mime_header(msg.get("Subject"))
        body = get_body_text(msg)
        attachments = collect_attachment_meta(msg)
        eml_path = str(path)

    result = classify_from_message(
        subject=subject,
        body=body,
        eml_path=eml_path,
        project_root=args.project_root,
        attachments=attachments,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
