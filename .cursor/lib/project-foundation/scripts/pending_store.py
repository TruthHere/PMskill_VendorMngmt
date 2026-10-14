#!/usr/bin/env python3
"""项目 .skill/pending.json 的唯一写入口。

硬规则：
- 每条必须带 skill（是哪个 Skill 的）
- 每个 Skill 只能关自己的
- 进度待确认写在 schedule.json，禁止写进 pending.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from common import PENDING_JSON, load_json, now_iso, system_file

ALLOWED_PENDING_SKILLS = frozenset(
    {
        "mail-inbox",
        "new-project",
        "po-flow",
        "payment-flow",
        "change-flow",
        "cashflow",
    }
)

SCHEDULE_PENDING_SKILLS = frozenset(
    {
        "critical-nodes",
        "mpp-to-excel",
    }
)

FORBIDDEN_PENDING_SKILLS = {
    "critical-nodes": "进度的待确认必须写在 schedule.json 里，不能写进 pending.json。",
    "mpp-to-excel": "转进度表不写 pending.json；吃不准的节点交给 critical-nodes，写在 schedule.json。",
    "vendor-card": "卡片质量提醒只留在卡片顶栏，禁止写入 pending.json。",
    "payment-sheet": "请款申请页不写 pending.json。",
    "read-pdf": "读 PDF 不写 pending.json。",
}

SKILL_ALIASES = {
    "skill0": "new-project",
    "skill 0": "new-project",
    "sk-init": "new-project",
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
    "sk-mail": "mail-inbox",
}

SKILL_LABELS = {
    "mail-inbox": "邮件入口",
    "new-project": "Skill 0 项目初始化",
    "po-flow": "Skill 1 履约",
    "payment-flow": "Skill 2 请款",
    "change-flow": "Skill 3 变更",
    "cashflow": "现金流预测",
}

CLOSE_STATUSES = frozenset({"confirmed", "cancelled"})


class PendingStoreError(ValueError):
    """pending.json 归属 / 写入被硬拦。"""


def normalize_skill(skill: str | None) -> str:
    raw = str(skill or "").strip()
    if not raw:
        return ""
    return SKILL_ALIASES.get(raw.lower(), raw)


def skill_label(skill: str | None) -> str:
    key = normalize_skill(skill)
    return SKILL_LABELS.get(key, key or "未标明")


def pending_path(project_root: Path) -> Path:
    return system_file(project_root, PENDING_JSON)


def load_pending_doc(project_root: Path) -> dict[str, Any]:
    data = load_json(pending_path(project_root), {"items": []})
    if isinstance(data, list):
        return {"items": data}
    if not isinstance(data, dict):
        return {"items": []}
    data.setdefault("items", [])
    if not isinstance(data["items"], list):
        data["items"] = []
    return data


def _write_pending_doc(project_root: Path, data: dict[str, Any]) -> None:
    path = pending_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def ensure_pending_file(project_root: Path) -> Path:
    """建项时落下空 pending.json；已有文件不覆盖。"""
    path = pending_path(project_root)
    if not path.exists():
        _write_pending_doc(project_root, {"items": []})
    return path


def require_allowed_skill(skill: str | None) -> str:
    key = normalize_skill(skill)
    if not key:
        raise PendingStoreError("这条待确认没写是哪个 Skill 的，不能进 pending.json。")
    if key in SCHEDULE_PENDING_SKILLS or key in FORBIDDEN_PENDING_SKILLS:
        raise PendingStoreError(
            FORBIDDEN_PENDING_SKILLS.get(
                key,
                "进度的待确认必须写在 schedule.json 里，不能写进 pending.json。",
            )
        )
    if key not in ALLOWED_PENDING_SKILLS:
        allowed = "、".join(sorted(ALLOWED_PENDING_SKILLS))
        raise PendingStoreError(f"不认识的 Skill「{key}」，pending.json 只允许：{allowed}。")
    return key


def infer_legacy_skill(item: dict[str, Any]) -> str | None:
    """旧条目没有 skill 时，按 step/reason 猜归属。猜不出就返回 None（不能关）。"""
    stamped = normalize_skill(str(item.get("skill") or "").strip())
    if stamped:
        try:
            return require_allowed_skill(stamped)
        except PendingStoreError:
            return stamped if stamped in ALLOWED_PENDING_SKILLS else None

    step = str(item.get("step") or "").strip()
    reason = str(item.get("reason") or "").strip()

    if step in {"change_archive", "change_po"} or step.startswith("change."):
        return "change-flow"
    if reason in {
        "change_po_deferred",
        "change_id_unmatched",
        "change_row_missing",
        "change_handler_failed",
        "amount_unconfirmed",
    }:
        return "change-flow"
    if step in {"project_init", "stage0"} or reason.startswith("project_"):
        return "new-project"
    if step.startswith("payment_claim") or reason.startswith("payment_"):
        return "payment-flow"
    if reason in {"intent_low_confidence", "unknown_intent"} or step in {"unknown"}:
        return "mail-inbox"
    if reason in {
        "routed_to_skill0",
        "routed_to_skill3",
        "low_confidence",
        "unknown_step",
        "tax_rate_uncertain",
        "amount_mismatch_body_vs_quote",
        "quote_amount_unparsed",
        "contract_payment_needs_review",
        "package_not_found",
        "possible_thread_reply",
        "open_action_item",
    }:
        return "po-flow"
    if step.startswith("step") or step in {"步骤4"}:
        return "po-flow"
    if reason in {"package_unmatched", "out_of_order"}:
        return "change-flow"
    return None


def item_owner(item: dict[str, Any]) -> str | None:
    return infer_legacy_skill(item)


def _same_open_item(existing: dict[str, Any], item: dict[str, Any], skill: str) -> bool:
    if (existing.get("status") or "open") != "open":
        return False
    owner = item_owner(existing)
    if owner and owner != skill:
        return False
    reason = str(item.get("reason") or "").strip()
    if str(existing.get("reason") or "").strip() != reason:
        return False
    eml_path = str(item.get("eml_path") or "").strip()
    subject = " ".join(str(item.get("subject") or "").split())
    same_eml = eml_path and str(existing.get("eml_path") or "").strip() == eml_path
    same_subj = subject and " ".join(str(existing.get("subject") or "").split()) == subject
    return bool(same_eml or same_subj)


def add_pending(
    project_root: Path,
    item: dict[str, Any],
    *,
    skill: str | None = None,
) -> str:
    """追加一条待确认。skill 必填；同一封邮件同一原因同一 Skill 复用同一条。"""
    declared = skill or item.get("skill")
    if skill and item.get("skill"):
        item_skill = normalize_skill(str(item.get("skill")))
        arg_skill = normalize_skill(str(skill))
        if item_skill and arg_skill and item_skill != arg_skill:
            raise PendingStoreError(
                f"这条待确认写的是 {item_skill} 的，调用方却说自己是 {arg_skill}，对不上。"
            )
    owner = require_allowed_skill(declared)

    payload = {k: v for k, v in dict(item).items() if k not in {"pending_id", "created_at", "status"}}
    payload["skill"] = owner

    data = load_pending_doc(project_root)
    items: list[dict[str, Any]] = data["items"]
    for existing in items:
        if _same_open_item(existing, payload, owner):
            keep_id = existing.get("pending_id")
            keep_created = existing.get("created_at")
            existing.update(payload)
            existing["pending_id"] = keep_id
            existing["created_at"] = keep_created or now_iso()
            existing["status"] = "open"
            existing["skill"] = owner
            existing["updated_at"] = now_iso()
            _write_pending_doc(project_root, data)
            return str(existing.get("pending_id") or "")

    stamp = now_iso().replace(":", "").replace("+", "")[-12:]
    seq = sum(1 for x in items if str(x.get("pending_id") or "").startswith(f"p-{stamp}"))
    pending_id = f"p-{stamp}" if seq == 0 else f"p-{stamp}-{seq + 1}"
    items.append(
        {
            **payload,
            "pending_id": pending_id,
            "status": "open",
            "skill": owner,
            "created_at": now_iso(),
        }
    )
    _write_pending_doc(project_root, data)
    return pending_id


def close_pending(
    project_root: Path,
    pending_id: str,
    *,
    skill: str,
    status: str = "confirmed",
    note: str = "",
) -> dict[str, Any]:
    """只允许条目所属 Skill 关单。"""
    owner = require_allowed_skill(skill)
    want_status = str(status or "confirmed").strip() or "confirmed"
    if want_status not in CLOSE_STATUSES:
        raise PendingStoreError(f"关单状态只能是 confirmed 或 cancelled，不能是「{want_status}」。")
    pid = str(pending_id or "").strip()
    if not pid:
        raise PendingStoreError("关单必须带 pending_id。")

    data = load_pending_doc(project_root)
    found: dict[str, Any] | None = None
    for item in data["items"]:
        if str(item.get("pending_id") or "") == pid:
            found = item
            break
    if found is None:
        raise PendingStoreError(f"找不到待确认 {pid}。")

    item_skill = item_owner(found)
    if not item_skill:
        raise PendingStoreError(
            f"{pid} 是旧条目、看不出是哪个 Skill 的，不能关。请先由真正负责的 Skill 补上 skill 再关。"
        )
    if item_skill != owner:
        raise PendingStoreError(
            f"{pid} 属于 {skill_label(item_skill)}（{item_skill}），"
            f"{skill_label(owner)} 不能关别人的单。"
        )
    if found.get("status") not in (None, "", "open"):
        raise PendingStoreError(f"{pid} 已经是 {found.get('status')}，不必再关。")
    found["status"] = want_status
    found["skill"] = item_skill
    found["resolved_at"] = now_iso()
    found["resolved_by"] = owner
    if note:
        found["resolved_note"] = note
    _write_pending_doc(project_root, data)
    return dict(found)


def close_matching(
    project_root: Path,
    *,
    skill: str,
    match: Callable[[dict[str, Any]], bool],
    status: str = "confirmed",
) -> list[str]:
    """按条件关掉「属于本 Skill」的开放条目。别人的一律跳过，不报错也不改。"""
    owner = require_allowed_skill(skill)
    want_status = str(status or "confirmed").strip() or "confirmed"
    if want_status not in CLOSE_STATUSES:
        raise PendingStoreError(f"关单状态只能是 confirmed 或 cancelled，不能是「{want_status}」。")

    data = load_pending_doc(project_root)
    closed: list[str] = []
    changed = False
    for item in data["items"]:
        if (item.get("status") or "open") != "open":
            continue
        item_skill = item_owner(item)
        if item_skill != owner:
            continue
        if not match(item):
            continue
        item["status"] = want_status
        item["skill"] = owner
        item["resolved_at"] = now_iso()
        item["resolved_by"] = owner
        closed.append(str(item.get("pending_id") or ""))
        changed = True
    if changed:
        _write_pending_doc(project_root, data)
    return [pid for pid in closed if pid]


def open_items(project_root: Path, *, skill: str | None = None) -> list[dict[str, Any]]:
    owner = require_allowed_skill(skill) if skill else None
    out: list[dict[str, Any]] = []
    for item in load_pending_doc(project_root)["items"]:
        if (item.get("status") or "open") != "open":
            continue
        if owner and item_owner(item) != owner:
            continue
        out.append(item)
    return out


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pending.json 唯一写入口（必须声明 Skill）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="追加一条待确认")
    p_add.add_argument("--project-root", required=True)
    p_add.add_argument("--skill", required=True)
    p_add.add_argument("--item-json", required=True, help="条目 JSON 对象")

    p_close = sub.add_parser("close", help="关掉自己的一条待确认")
    p_close.add_argument("--project-root", required=True)
    p_close.add_argument("--skill", required=True)
    p_close.add_argument("--pending-id", required=True)
    p_close.add_argument("--status", default="confirmed", choices=sorted(CLOSE_STATUSES))
    p_close.add_argument("--note", default="")

    p_list = sub.add_parser("list", help="列出开放待确认")
    p_list.add_argument("--project-root", required=True)
    p_list.add_argument("--skill", default="")

    args = parser.parse_args(argv)
    root = Path(args.project_root).expanduser().resolve()

    if args.cmd == "add":
        item = json.loads(args.item_json)
        if not isinstance(item, dict):
            raise PendingStoreError("--item-json 必须是 JSON 对象。")
        pid = add_pending(root, item, skill=args.skill)
        print(json.dumps({"ok": True, "pending_id": pid, "skill": normalize_skill(args.skill)}, ensure_ascii=False))
        return 0
    if args.cmd == "close":
        item = close_pending(
            root,
            args.pending_id,
            skill=args.skill,
            status=args.status,
            note=args.note,
        )
        print(json.dumps({"ok": True, "item": item}, ensure_ascii=False))
        return 0
    items = open_items(root, skill=args.skill or None)
    print(json.dumps({"ok": True, "count": len(items), "items": items}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_cli())
    except PendingStoreError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2) from exc
