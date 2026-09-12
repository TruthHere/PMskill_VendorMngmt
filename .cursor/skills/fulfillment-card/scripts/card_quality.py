#!/usr/bin/env python3
"""Assess fulfillment card-data quality. Soft warnings — never block render."""

from __future__ import annotations

import re
from typing import Any

_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")
_HAS_LATIN = re.compile(r"[A-Za-z]")
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# 总包「施工进度 N」占位，无具体里程碑
_VAGUE_GC_PROGRESS = re.compile(
    r"^(附件\s*B\s*)?施工进度\s*\d+\s*$|^(进度|progress)\s*\d+\s*$",
    re.I,
)

# Stable codes — used by grader / callers
CODE_SUPPLIER_EMPTY = "supplier_name_empty"
CODE_PACKAGE_EMPTY = "package_name_empty"
CODE_AMOUNT_TAX = "total_amount_tax_unclear"
CODE_NODES_EMPTY = "payment_nodes_empty"
CODE_NODE_BILINGUAL = "payment_node_not_bilingual"
CODE_PCT_SUM = "payment_pct_sum_not_100"
CODE_PCT_UNPARSEABLE = "payment_pct_unparseable"
CODE_NODE_NAME_EMPTY = "payment_node_name_empty"
CODE_CONTACT_EMAIL = "contact_email_unclear"
CODE_ACCEPTANCE_EMPTY = "acceptance_items_empty"
CODE_SCOPE_EMPTY = "scope_summary_empty"
CODE_DELIVERY_UNCLEAR = "delivery_schedule_unclear"
CODE_CONTRACT_NO_EMPTY = "contract_or_quote_no_empty"
CODE_CONTRACT_DATE_EMPTY = "contract_or_quote_date_empty"
CODE_GC_PROGRESS_VAGUE = "gc_progress_milestone_vague"
CODE_NODE_CONDITION_EMPTY = "payment_node_condition_empty"


def _blank(value: object) -> bool:
    text = str(value or "").strip()
    return (not text) or text in {"—", "-", "待补充", "待定", "TBD", "n/a", "N/A"}


def is_bilingual_name(name: str) -> bool:
    text = (name or "").strip()
    if not text:
        return False
    if "/" in text:
        left, _, right = text.partition("/")
        return bool(left.strip() and right.strip())
    return bool(_HAS_CJK.search(text) and _HAS_LATIN.search(text))


def amount_has_tax_mark(amount: str) -> bool:
    text = (amount or "").lower()
    markers = (
        "含税",
        "不含税",
        "incl",
        "vat",
        "before vat",
        "after vat",
        "tax incl",
        "tax excl",
    )
    return any(m in text for m in markers)


def parse_pct_sum(nodes: list[dict[str, Any]]) -> tuple[float | None, bool]:
    """Return (sum, all_parseable). sum is None if no nodes."""
    if not nodes:
        return None, True
    total = 0.0
    for node in nodes:
        raw = str(node.get("pct") or "")
        match = _PCT.search(raw)
        if not match:
            return None, False
        total += float(match.group(1))
    return total, True


def is_gc_package(card_data: dict[str, Any]) -> bool:
    package_type = str(card_data.get("package_type", "")).strip()
    package_type_label = str(card_data.get("package_type_label", "")).strip()
    return package_type == "总包" or package_type_label == "总包"


def _warn(code: str, field: str, message: str) -> dict[str, str]:
    return {"code": code, "field": field, "message": message}


def assess_card_quality(card_data: dict[str, Any]) -> list[dict[str, str]]:
    """Return list of {code, message, field}. Empty = quality OK."""
    warnings: list[dict[str, str]] = []

    if _blank(card_data.get("supplier_name")):
        warnings.append(
            _warn(
                CODE_SUPPLIER_EMPTY,
                "supplier_name",
                "供应商名称不够清晰：页眉主标题会空白，请补全供应商全称。",
            )
        )

    if _blank(card_data.get("package_name")):
        warnings.append(
            _warn(
                CODE_PACKAGE_EMPTY,
                "package_name",
                "采购包名称不够清晰：副标题无法识别采购包。",
            )
        )

    if _blank(card_data.get("contract_or_quote_no")):
        warnings.append(
            _warn(
                CODE_CONTRACT_NO_EMPTY,
                "contract_or_quote_no",
                "合同/报价单编号未填：有合同填合同号，无合同填报价单号。",
            )
        )

    if _blank(card_data.get("contract_or_quote_date")):
        warnings.append(
            _warn(
                CODE_CONTRACT_DATE_EMPTY,
                "contract_or_quote_date",
                "签约/报价日期未填：影响质保期起算核对，请补日期。",
            )
        )

    email = str(card_data.get("contact_email") or "").strip()
    if _blank(email):
        warnings.append(
            _warn(
                CODE_CONTACT_EMAIL,
                "contact_email",
                "对接人邮箱未填：请款与往来缺联系人。",
            )
        )
    else:
        # Allow multiple emails separated by ; or ,
        parts = [p.strip() for p in re.split(r"[;,]", email) if p.strip()]
        if not parts or any(not _EMAIL.match(p) for p in parts):
            warnings.append(
                _warn(
                    CODE_CONTACT_EMAIL,
                    "contact_email",
                    f"对接人邮箱格式不够清晰（当前：{email}），请核对。",
                )
            )

    amount = str(card_data.get("total_amount") or "").strip()
    if amount and not _blank(amount) and not amount_has_tax_mark(amount):
        warnings.append(
            _warn(
                CODE_AMOUNT_TAX,
                "total_amount",
                f"总金额未标明含税/不含税（当前：{amount}），请核对后补注。",
            )
        )
    elif _blank(amount):
        warnings.append(
            _warn(
                CODE_AMOUNT_TAX,
                "total_amount",
                "总金额不够清晰：请从报价/合同补全并标注含税或不含税。",
            )
        )

    if _blank(card_data.get("scope_summary")):
        warnings.append(
            _warn(
                CODE_SCOPE_EMPTY,
                "scope_summary",
                "供应/服务范围未填：卡片缺少工作内容摘要。",
            )
        )

    delivery = str(card_data.get("delivery_schedule") or "").strip()
    if _blank(delivery):
        warnings.append(
            _warn(
                CODE_DELIVERY_UNCLEAR,
                "delivery_schedule",
                "交期/服务周期不够清晰：请填写到货或完工节点（勿只写「待定」）。",
            )
        )

    acceptance = list(card_data.get("acceptance_items") or [])
    real_acceptance = [
        str(item).strip()
        for item in acceptance
        if str(item).strip() and str(item).strip() not in {"待补充", "—", "-"}
    ]
    if not real_acceptance:
        warnings.append(
            _warn(
                CODE_ACCEPTANCE_EMPTY,
                "acceptance_items",
                "验收标准为空：请补充可勾选的验收要点。",
            )
        )

    nodes = list(card_data.get("payment_nodes") or [])
    if not nodes:
        warnings.append(
            _warn(
                CODE_NODES_EMPTY,
                "payment_nodes",
                "付款节点为空：卡片仅显示「待补充」，请写入合同或邮件中的付款里程碑。",
            )
        )
    else:
        for index, node in enumerate(nodes):
            name = str(node.get("name") or "").strip()
            if not name:
                warnings.append(
                    _warn(
                        CODE_NODE_NAME_EMPTY,
                        f"payment_nodes[{index}].name",
                        f"第 {index + 1} 个付款节点名称不够清晰（空）。",
                    )
                )
            elif not is_bilingual_name(name):
                warnings.append(
                    _warn(
                        CODE_NODE_BILINGUAL,
                        f"payment_nodes[{index}].name",
                        f"付款节点「{name}」建议中英对照（例：预付款 / Advance）。",
                    )
                )

            condition = str(node.get("condition") or "").strip()
            milestone = str(node.get("milestone") or "").strip()
            if _blank(condition) and _blank(milestone):
                warnings.append(
                    _warn(
                        CODE_NODE_CONDITION_EMPTY,
                        f"payment_nodes[{index}].condition",
                        f"付款节点「{name or f'#{index+1}'}」触发条件不够清晰。",
                    )
                )

            if is_gc_package(card_data):
                for probe in (condition, milestone, name):
                    if probe and _VAGUE_GC_PROGRESS.match(probe.strip()):
                        warnings.append(
                            _warn(
                                CODE_GC_PROGRESS_VAGUE,
                                f"payment_nodes[{index}]",
                                f"总包节点「{name or probe}」仍是「施工进度 N」占位，"
                                "请从附件 B 写入具体里程碑目标。",
                            )
                        )
                        break

        pct_sum, all_parseable = parse_pct_sum(nodes)
        if not all_parseable:
            warnings.append(
                _warn(
                    CODE_PCT_UNPARSEABLE,
                    "payment_nodes.pct",
                    "部分付款比例无法解析为百分比，请写成如 30% 的格式。",
                )
            )
        elif pct_sum is not None and abs(pct_sum - 100.0) > 1.0:
            warnings.append(
                _warn(
                    CODE_PCT_SUM,
                    "payment_nodes.pct",
                    f"付款比例合计为 {pct_sum:g}%，不是约 100%，请核对节点是否齐全或比例是否有误。",
                )
            )

    return warnings


def quality_ok(warnings: list[dict[str, str]]) -> bool:
    return len(warnings) == 0
