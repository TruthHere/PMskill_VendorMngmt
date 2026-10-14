#!/usr/bin/env python3
"""请款五步状态机（Skill 2）——真相在采购包 Tracker，不另开 ledger。

Tracker 请款章节：
  已请金额 / 待请款金额 / 下一付款节点 / 请款进度
请款进度：人话当前步（如「已发QS核对 · 到货 / Delivery」）；无在办写「无在办」。
真正完成 = 客户批复（certified）才计入已请、才推进下一笔。
"""

from __future__ import annotations

# 正向五步（只前进；跳级须 --allow-skip 补录）
PIPELINE: tuple[str, ...] = (
    "vendor_received",
    "qs_sent",
    "qs_confirmed",
    "client_sent",
    "certified",
)

STATUS_LABELS: dict[str, str] = {
    "vendor_received": "供应商请款已收到",
    "qs_sent": "已发QS核对",
    "qs_confirmed": "QS已确认金额",
    "client_sent": "已发客户请款",
    "certified": "客户已批复",
    "returned": "已退回",
    "rejected": "已驳回",
}

LABEL_TO_STATUS: dict[str, str] = {v: k for k, v in STATUS_LABELS.items()}

# 旧口径兼容
ALIASES: dict[str, str] = {
    "draft": "vendor_received",
    "submitted": "client_sent",
}

ALL_STATUSES = frozenset(PIPELINE) | {"returned", "rejected"} | set(ALIASES)

DEFAULT_OPEN_STATUS = "vendor_received"
DEFAULT_COMPLETED_STATUS = "certified"

# Tracker「请款进度」无在办
NO_ACTIVE_PROGRESS = "无在办"


def normalize_status(status: str | None) -> str:
    raw = (status or "").strip()
    if not raw:
        return ""
    return ALIASES.get(raw, raw)


def status_label(status: str | None) -> str:
    n = normalize_status(status)
    return STATUS_LABELS.get(n, n or "")


def is_completed(status: str | None) -> bool:
    return normalize_status(status) == "certified"


def pipeline_index(status: str | None) -> int | None:
    n = normalize_status(status)
    if n not in PIPELINE:
        return None
    return PIPELINE.index(n)


def would_skip(current: str | None, target: str | None) -> bool:
    """目标是否跳过了合法下一步。补录请用 --allow-skip。"""
    target_n = normalize_status(target)
    if target_n in {"returned", "rejected"}:
        return False
    if target_n not in PIPELINE:
        return True
    current_n = normalize_status(current)
    if not current_n:
        return target_n != "vendor_received"
    if current_n in {"returned", "rejected"}:
        return target_n not in {"vendor_received", "qs_sent"}
    ci = pipeline_index(current_n)
    ti = pipeline_index(target_n)
    if ci is None or ti is None:
        return True
    if ti < ci:
        return True
    return ti > ci + 1


def format_progress(status: str | None, node: str | None) -> str:
    """写入 Tracker「请款进度」。"""
    n = normalize_status(status)
    if not n or n == "certified":
        # 批复完成由调用方改「无在办」；此处兜底
        return NO_ACTIVE_PROGRESS
    if n in {"returned", "rejected"}:
        label = status_label(n)
        node_s = (node or "").strip()
        return f"{label} · {node_s}" if node_s else label
    label = status_label(n) or n
    node_s = (node or "").strip()
    if label and node_s:
        return f"{label} · {node_s}"
    return label or NO_ACTIVE_PROGRESS


def parse_progress(progress: str | None) -> tuple[str | None, str]:
    """从 Tracker「请款进度」解析 (status_code|None, node)。无在办 → (None, "")."""
    raw = (progress or "").strip()
    if not raw or raw == NO_ACTIVE_PROGRESS:
        return None, ""
    label, _, node = raw.partition("·")
    label = label.strip()
    node = node.strip()
    status = LABEL_TO_STATUS.get(label) or normalize_status(label)
    if status not in ALL_STATUSES and status not in PIPELINE:
        # 整串碰巧是旧码
        status = normalize_status(raw) or None
        if status and status in ALL_STATUSES:
            return status, node
        return None, node
    return status, node


def payment_nodes_list(card: dict) -> list[dict]:
    return list(card.get("payment_nodes") or [])


def node_names_in_order(card: dict) -> list[str]:
    out: list[str] = []
    for node in payment_nodes_list(card):
        name = str(node.get("name") or "").strip()
        if name:
            out.append(name)
    return out


def _node_match(a: str, b: str) -> bool:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    ap, bp = a.split("/")[0].strip(), b.split("/")[0].strip()
    return bool(ap and bp and (ap in b or bp in a))


def completed_nodes_before(card: dict, next_node: str) -> set[str]:
    """下一笔待请之前的节点视为已客户批复（已请完）。"""
    names = node_names_in_order(card)
    if not next_node.strip():
        return set(names)
    done: set[str] = set()
    for name in names:
        if _node_match(name, next_node):
            break
        done.add(name)
    return done


def next_node_after(card: dict, current_node: str) -> str:
    names = node_names_in_order(card)
    for i, name in enumerate(names):
        if _node_match(name, current_node):
            if i + 1 < len(names):
                return names[i + 1]
            return ""
    # 当前节点不在卡片上：退回第一未知名
    return names[0] if names else ""


def resolve_next_pending(card: dict, tracker_row: dict) -> str:
    """下一笔待请节点名：优先 Tracker；空则卡片第一个节点。"""
    nxt = str(tracker_row.get("next_payment_node") or "").strip()
    if nxt:
        return nxt
    names = node_names_in_order(card)
    return names[0] if names else ""


def payment_no_for_node(card: dict, node: str) -> int:
    for i, name in enumerate(node_names_in_order(card), 1):
        if _node_match(name, node):
            return i
    return 0
