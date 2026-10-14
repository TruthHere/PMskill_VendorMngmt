#!/usr/bin/env python3
"""对话路径写权限：用错 Skill 直接拒写。

邮件分发已经按 0/1/2/3 切开。这里拦的是对话里直接跑脚本：
履约改不了变更台账；变更改不了 Tracker / 请款栏；
请款改不了合同额 / 变更台账；单独转 MPP、读 PDF 改不了履约数据。
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

SKILL_ALIASES = {
    "skill0": "new-project",
    "skill 0": "new-project",
    "sk-init": "new-project",
    "new-project-workspace": "new-project",
    "skill1": "po-flow",
    "skill 1": "po-flow",
    "sk-fulfill": "po-flow",
    "skill2": "payment-flow",
    "skill 2": "payment-flow",
    "sk-pay": "payment-flow",
    "skill3": "change-flow",
    "skill 3": "change-flow",
    "sk-change": "change-flow",
    "skill4": "cashflow",
    "skill 4": "cashflow",
    "sk-cash": "cashflow",
}

KNOWN_SKILLS = frozenset(
    {
        "mail-inbox",
        "new-project",
        "po-flow",
        "payment-flow",
        "change-flow",
        "cashflow",
        "vendor-card",
        "payment-sheet",
        "mpp-to-excel",
        "critical-nodes",
        "read-pdf",
        "project-foundation",
        "skill-orchestration",
    }
)

# 邮局只分发；基建库 / 编排说明书不是业务 Skill。写权限看它们后面真正办事的那个。
SKIP_AS_WRITER = frozenset({"mail-inbox", "project-foundation", "skill-orchestration"})

SKILL_LABELS = {
    "mail-inbox": "邮件入口",
    "new-project": "Skill 0 项目初始化",
    "po-flow": "Skill 1 履约",
    "payment-flow": "Skill 2 请款",
    "change-flow": "Skill 3 变更",
    "cashflow": "现金流预测",
    "vendor-card": "履约卡片",
    "payment-sheet": "请款申请页",
    "mpp-to-excel": "进度转 Excel",
    "critical-nodes": "进度关键节点",
    "read-pdf": "读 PDF",
    "project-foundation": "项目基建库",
}

TRACKER_PAYMENT_KEYS = frozenset(
    {
        "claimed_amount_excl_tax",
        "remaining_claim_amount_excl_tax",
        "next_payment_node",
        "payment_progress",
    }
)
TRACKER_AMOUNT_KEYS = frozenset({"amount_excl_tax", "amount_incl_tax", "amount_remark"})
TRACKER_SKILL1_PAYMENT_KEYS = frozenset({"next_payment_node"})  # 改付款节点后同步「下一笔」
SOLO_NO_FULFILL_SKILLS = frozenset({"mpp-to-excel", "read-pdf"})

_CARD_DATA = "card-data.json"
_CARD_HTML = "履约条件卡片.html"
_PENDING = "pending.json"
_TRACKER_SUFFIX = "_procurement_packages_status_tracker.csv"
_TRACKER_XLSX_SUFFIX = "_Status Tracker.xlsx"
_TRACKER_CSV_SKILL = "status_tracker.csv"


class WriteGuardError(PermissionError):
    """用错 Skill，拒写。"""


def normalize_skill(skill: str | None) -> str:
    raw = str(skill or "").strip()
    if not raw:
        return ""
    return SKILL_ALIASES.get(raw.lower(), raw)


def skill_label(skill: str | None) -> str:
    key = normalize_skill(skill)
    return SKILL_LABELS.get(key, key or "未知")


def skill_from_path(path: Path | str) -> str | None:
    parts = Path(path).resolve().parts
    if "project-foundation" in parts:
        return "project-foundation"
    if "skills" in parts:
        idx = parts.index("skills")
        if idx + 1 < len(parts):
            name = normalize_skill(parts[idx + 1])
            if name in KNOWN_SKILLS:
                return name
    return None


def infer_caller_skill() -> str:
    """调用栈里最外层的业务 Skill（跳过邮局分发和基建库）。"""
    found: list[str] = []
    for frame in reversed(inspect.stack()):
        name = skill_from_path(frame.filename)
        if name and (not found or found[-1] != name):
            found.append(name)
    business = [s for s in found if s not in SKIP_AS_WRITER]
    if business:
        return business[0]
    return found[0] if found else ""


def _resolve_skill(skill: str | None) -> str:
    return normalize_skill(skill) or infer_caller_skill()


def _refuse(skill: str, message: str) -> None:
    who = skill_label(skill) if skill else "未知调用方"
    raise WriteGuardError(f"{who}不能这么写。{message}")


def assert_change_log_write(*, skill: str | None = None) -> None:
    owner = _resolve_skill(skill)
    if owner == "change-flow":
        return
    if owner == "po-flow":
        _refuse(owner, "变更台账归 Skill 3（change-flow）。请走变更脚本，不要用履约改 Change Log。")
    if owner == "payment-flow":
        _refuse(owner, "变更台账归 Skill 3。请款只改进度/已请金额，不能改变更台账。")
    if owner in SOLO_NO_FULFILL_SKILLS:
        _refuse(owner, "单独转进度 / 读 PDF 只出自己的文件，不能改变更台账。")
    _refuse(owner or "未知", "只有 Skill 3（change-flow）能写 Change Log。")


def assert_card_data_write(*, skill: str | None = None) -> None:
    owner = _resolve_skill(skill)
    if owner in {"po-flow", "vendor-card", "project-foundation"}:
        return
    if owner == "change-flow":
        _refuse(owner, "变更不写履约卡片。金额以 Change Log 为准。")
    if owner == "payment-flow":
        _refuse(owner, "请款不改合同卡片。请改 Tracker 请款栏。")
    if owner in SOLO_NO_FULFILL_SKILLS:
        _refuse(owner, "单独转进度 / 读 PDF 不能改履约卡片。把正文或进度表交给人，履约数据留给履约 Skill。")
    _refuse(owner or "未知", "履约卡片数据只能由 Skill 1 或履约卡片渲染脚本写。")


def assert_solo_output_allowed(path: Path | str, *, skill: str | None = None) -> None:
    owner = _resolve_skill(skill)
    if owner not in SOLO_NO_FULFILL_SKILLS:
        return
    target = Path(path)
    name = target.name
    if (
        name in {_CARD_DATA, _CARD_HTML, _PENDING}
        or name.endswith(_TRACKER_SUFFIX)
        or name.endswith(_TRACKER_XLSX_SUFFIX)
        or name in {"tracker.csv", _TRACKER_CSV_SKILL, "status_tracker.csv"}
        or name.endswith("_change_log.csv")
        or name.endswith("_Change Log.xlsx")
        or name == "change_log.csv"
        or name == "schedule.json"
    ):
        _refuse(
            owner,
            f"不能把输出写成「{name}」。单独转表 / 读 PDF 只写进度 Excel/CSV 或 PDF 正文，不要改履约数据。",
        )


def _pkg_key(pkg: dict[str, Any]) -> str:
    return str(pkg.get("package_name") or "").strip()


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _changed_keys(old: dict[str, Any], new: dict[str, Any]) -> set[str]:
    keys = set(old) | set(new)
    return {k for k in keys if _norm(old.get(k)) != _norm(new.get(k))}


def assert_tracker_write(
    project_root: Path,
    packages: list[dict[str, Any]],
    *,
    skill: str | None = None,
) -> None:
    owner = _resolve_skill(skill)
    if owner in {"project-foundation", "new-project"}:
        if owner == "new-project" and any(_pkg_key(p) for p in packages):
            _refuse(owner, "Skill 0 只建空总表。建采购包请用 Skill 1 履约。")
        return
    if owner == "change-flow":
        _refuse(owner, "采购包总表和请款栏都不归变更。改包身份用履约，改进度用请款。")
    if owner in SOLO_NO_FULFILL_SKILLS:
        _refuse(owner, "单独转进度 / 读 PDF 不能改 Tracker。")
    if owner not in {"po-flow", "payment-flow"}:
        _refuse(owner or "未知", "Tracker 只能由 Skill 1 履约或 Skill 2 请款来写。")

    from common import load_tracker_packages

    existing = { _pkg_key(p): p for p in load_tracker_packages(project_root) if _pkg_key(p) }
    incoming = { _pkg_key(p): p for p in packages if _pkg_key(p) }

    added = set(incoming) - set(existing)
    removed = set(existing) - set(incoming)
    if (added or removed) and owner == "payment-flow":
        _refuse(owner, "请款不能新建/删采购包，也不能改合同额。建包和合同额归履约。")

    for name in set(incoming) & set(existing):
        changed = _changed_keys(existing[name], incoming[name])
        if not changed:
            continue
        amount_hits = changed & TRACKER_AMOUNT_KEYS
        payment_hits = changed & TRACKER_PAYMENT_KEYS
        other = changed - TRACKER_AMOUNT_KEYS - TRACKER_PAYMENT_KEYS
        if owner == "payment-flow":
            if amount_hits:
                _refuse(owner, "请款不能改合同额（不含税/含税）。合同金额归履约；变更金额归变更台账。")
            if other:
                _refuse(owner, "请款只能改请款四栏（已请/待请/下一节点/请款进度），不能改包身份或里程碑。")
        elif owner == "po-flow":
            forbidden_pay = payment_hits - TRACKER_SKILL1_PAYMENT_KEYS
            if forbidden_pay:
                _refuse(owner, "履约不能改请款进度/已请金额。那四栏归 Skill 2。")


def assert_path_write(path: Path | str, *, skill: str | None = None) -> None:
    """save_json 等通用写入：认出履约卡片 / 待确认后再分流。"""
    target = Path(path)
    name = target.name
    if name == _CARD_DATA:
        assert_card_data_write(skill=skill)
    elif name.endswith("_change_log.csv") or name == "change_log.csv" or name.endswith("_Change Log.xlsx"):
        assert_change_log_write(skill=skill)
    elif (
        name.endswith(_TRACKER_SUFFIX)
        or name.endswith(_TRACKER_XLSX_SUFFIX)
        or name in {"tracker.csv", _TRACKER_CSV_SKILL}
    ):
        _refuse(_resolve_skill(skill), "Tracker 必须走 save_tracker_packages，好按列检查是谁在写。")
    else:
        assert_solo_output_allowed(target, skill=skill)
