#!/usr/bin/env python3
"""Scan packages: only the next pending payment node approaching window_end.

真相读 Tracker「下一付款节点」+「请款进度」；不再读 payment_ledger.json。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from payment_status import (  # noqa: E402
    NO_ACTIVE_PROGRESS,
    completed_nodes_before,
    parse_progress,
    resolve_next_pending,
)


def _today() -> date:
    return date.today()


def _parse_ymd(s: str | None) -> date | None:
    if not s:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(s))
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _load_json(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _skill1_scripts() -> Path:
    return Path(__file__).resolve().parents[2] / "contract-fulfillment-struct" / "scripts"


def _load_packages(project_root: Path) -> list[dict]:
    sys.path.insert(0, str(_skill1_scripts()))
    from common import load_tracker_packages  # type: ignore

    return load_tracker_packages(project_root)


def _package_dir(project_root: Path, row: dict) -> Path | None:
    folder = Path(str(row.get("folder_path") or ""))
    if not folder.is_absolute():
        folder = (project_root / folder).resolve()
    else:
        folder = folder.expanduser().resolve()
    if folder.is_dir():
        return folder
    name = folder.name
    if name:
        cand = project_root / name
        if cand.is_dir():
            return cand
    return None


def _schedule_ends(project_root: Path, package_name: str) -> dict[str, date]:
    sched = _load_json(project_root / ".skill" / "schedule.json") or {}
    out: dict[str, date] = {}
    for n in sched.get("critical_nodes") or []:
        if (n.get("package_name") or "") != package_name:
            continue
        end = _parse_ymd(n.get("window_end"))
        if not end:
            continue
        for key in filter(None, [n.get("name"), n.get("name_zh"), n.get("name_en"), n.get("node_code")]):
            out[str(key).lower()] = end
    return out


def _match_end(node_name: str, ends: dict[str, date]) -> date | None:
    low = node_name.lower()
    if low in ends:
        return ends[low]
    for k, v in ends.items():
        if k in low or low in k:
            return v
    for token in (
        "预付", "到货", "安装", "验收", "调试", "尾款", "质保", "进度",
        "advance", "delivery", "install", "accept", "commission", "retention",
    ):
        if token.lower() in low:
            for k, v in ends.items():
                if token.lower() in k:
                    return v
    return None


def _urgency(window_end: date, today: date) -> str:
    if today > window_end:
        return "overdue"
    if today == window_end:
        return "due_today"
    return "due_soon"


def scan(project_root: Path, lead_days: int) -> dict:
    today = _today()
    horizon = today + timedelta(days=lead_days)
    items = []
    for row in _load_packages(project_root):
        package_name = str(row.get("package_name") or "").strip()
        if not package_name:
            continue
        pkg_dir = _package_dir(project_root, row)
        if not pkg_dir:
            continue
        card = _load_json(pkg_dir / "card-data.json") or {}
        stage, progress_node = parse_progress(row.get("payment_progress"))
        node = resolve_next_pending(card, row)
        if progress_node and stage:
            node = progress_node
        if not node:
            continue

        ends = _schedule_ends(project_root, package_name)
        parts = pkg_dir.name.split("_", 2)
        if len(parts) >= 2:
            ends.update(_schedule_ends(project_root, parts[1]))

        end = _match_end(node, ends)
        if not end:
            # card schedule_window fallback
            for n in card.get("payment_nodes") or []:
                if str(n.get("name") or "").strip() == node:
                    end = _parse_ymd(str(n.get("schedule_window") or ""))
                    break
        if not end or end > horizon:
            continue

        nodes = list(card.get("payment_nodes") or [])
        index = 1
        pct = None
        for i, n in enumerate(nodes, 1):
            if str(n.get("name") or "").strip() == node:
                index = int(n.get("payment_no") or i)
                pct = n.get("pct")
                break

        items.append(
            {
                "package_name": package_name,
                "supplier_name": row.get("supplier_name") or card.get("supplier_name") or "",
                "package_dir": pkg_dir.name,
                "node": node,
                "pct": pct,
                "window_end": end.isoformat(),
                "urgency": _urgency(end, today),
                "next_payment_no": index,
                "payment_progress": row.get("payment_progress") or NO_ACTIVE_PROGRESS,
                "is_next_pending_only": True,
                "completed_nodes": sorted(completed_nodes_before(card, node)),
                "form_hint": "打开同包 请款申请.html；发给客户前用 payment-form",
            }
        )
    items.sort(key=lambda x: (x["window_end"], x["package_dir"]))
    return {
        "scanned_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "lead_days": lead_days,
        "policy": "next_pending_only",
        "truth": "tracker",
        "items": items,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--lead-days", type=int, default=14)
    ap.add_argument("--write", action="store_true", help="Write .skill/payment_due.json")
    args = ap.parse_args()
    root = Path(args.project_root).expanduser().resolve()
    result = scan(root, args.lead_days)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.write:
        out = root / ".skill" / "payment_due.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
