#!/usr/bin/env python3
"""推进请款五步：只写采购包 Tracker；03_请款记录只归档附件。

默认推进为「供应商请款已收到」。客户批复（certified）才计入已请金额并切下一笔。
跳级默认拒绝；补录历史用 --allow-skip。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from payment_status import (  # noqa: E402
    ALL_STATUSES,
    DEFAULT_OPEN_STATUS,
    NO_ACTIVE_PROGRESS,
    format_progress,
    is_completed,
    next_node_after,
    normalize_status,
    parse_progress,
    payment_no_for_node,
    resolve_next_pending,
    status_label,
    would_skip,
)

EXIT_OUT_OF_ORDER = 4


def _now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def _project_root(package_dir: Path) -> Path | None:
    for p in [package_dir] + list(package_dir.parents):
        if (p / ".skill").is_dir():
            return p
    return None


def _money(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").replace("¥", "").replace("￥", "").strip())
    except ValueError:
        return None


def _fmt_amount(value: float) -> str:
    return f"{value:.2f}"


def _load_card(package_dir: Path) -> dict:
    path = package_dir / "card-data.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _skill1_scripts() -> Path:
    return Path(__file__).resolve().parents[2] / "contract-fulfillment-struct" / "scripts"


def _load_tracker_row(project_root: Path, package_name: str) -> dict:
    sys.path.insert(0, str(_skill1_scripts()))
    from common import find_package, load_tracker_packages  # type: ignore

    return find_package(load_tracker_packages(project_root), package_name) or {}


def _update_tracker(
    project_root: Path,
    package_name: str,
    *,
    next_payment_node: str,
    payment_progress: str,
    claimed_amount_excl_tax: str | None = None,
    remaining_claim_amount_excl_tax: str | None = None,
) -> None:
    sys.path.insert(0, str(_skill1_scripts()))
    from update_tracker import update_package  # type: ignore

    kwargs: dict = {
        "next_payment_node": next_payment_node,
        "payment_progress": payment_progress,
    }
    if claimed_amount_excl_tax is not None:
        kwargs["claimed_amount_excl_tax"] = claimed_amount_excl_tax
    if remaining_claim_amount_excl_tax is not None:
        kwargs["remaining_claim_amount_excl_tax"] = remaining_claim_amount_excl_tax
    update_package(project_root, package_name=package_name, **kwargs)


def _archive_file(package_dir: Path, src: Path, stem_tag: str) -> Path | None:
    if not src.is_file():
        return None
    out_dir = package_dir / "03_请款记录"
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{_now_stamp()}_{stem_tag}_{src.name}"
    shutil.copy2(src, dest)
    return dest


def _load_response(path: str | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package-dir", required=True)
    ap.add_argument("--response", default="", help="claim_response.json（可选，归档到 03_请款记录）")
    ap.add_argument("--payment-no", type=int, default=None)
    ap.add_argument("--node", default=None)
    ap.add_argument("--amount-excl-tax", type=float, default=None)
    ap.add_argument("--currency", default="CNY")
    ap.add_argument(
        "--status",
        default=DEFAULT_OPEN_STATUS,
        choices=sorted(ALL_STATUSES),
        help="五步之一；默认 vendor_received。客户批复用 certified",
    )
    ap.add_argument("--allow-skip", action="store_true", help="补录历史时允许跳步")
    ap.add_argument("--source", default="manual")
    ap.add_argument("--source-eml", default="", help="往来邮件路径，复制进 03_请款记录")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    response = _load_response(args.response)
    node = (args.node or response.get("claim_node") or "").strip()
    amount_excl_tax = (
        args.amount_excl_tax
        if args.amount_excl_tax is not None
        else response.get("claim_amount_excl_tax")
    )
    target = normalize_status(args.status)
    pkg = Path(args.package_dir).expanduser().resolve()
    card = _load_card(pkg)
    package_name = str(card.get("package_name") or "").strip()
    if not package_name:
        raise SystemExit("card-data.json missing package_name")

    project_root = _project_root(pkg)
    if not project_root:
        raise SystemExit(f"cannot find project root (.skill) above {pkg}")

    tracker = _load_tracker_row(project_root, package_name)
    current_status, progress_node = parse_progress(tracker.get("payment_progress"))
    pending_node = resolve_next_pending(card, tracker)

    if not node:
        node = progress_node or pending_node
    if not node:
        raise SystemExit("missing --node / response.claim_node / Tracker 下一付款节点")

    if current_status is None and target != "vendor_received" and not args.allow_skip:
        payload = {
            "ok": False,
            "reason": "out_of_order",
            "current_status": None,
            "current_label": NO_ACTIVE_PROGRESS,
            "target_status": target,
            "target_label": status_label(target),
            "note": "无在办时须先记「供应商请款已收到」",
        }
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return EXIT_OUT_OF_ORDER

    if would_skip(current_status, target) and not args.allow_skip:
        payload = {
            "ok": False,
            "reason": "out_of_order",
            "current_status": current_status,
            "current_label": status_label(current_status) if current_status else NO_ACTIVE_PROGRESS,
            "target_status": target,
            "target_label": status_label(target),
            "node": node,
        }
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return EXIT_OUT_OF_ORDER

    payment_no = (
        args.payment_no
        or int(response.get("payment_no") or 0)
        or payment_no_for_node(card, node)
    )

    if is_completed(target) and amount_excl_tax is None:
        raise SystemExit("客户批复需要 --amount-excl-tax（或 response.claim_amount_excl_tax）")
    amt = float(amount_excl_tax) if amount_excl_tax is not None else None

    claimed = _money(tracker.get("claimed_amount_excl_tax")) or 0.0
    excl = _money(tracker.get("amount_excl_tax"))
    next_out = node

    if is_completed(target):
        claimed = claimed + float(amt or 0)
        next_out = next_node_after(card, node)
        progress = NO_ACTIVE_PROGRESS
        remaining = _fmt_amount(excl - claimed) if excl is not None else ""
        _update_tracker(
            project_root,
            package_name,
            next_payment_node=next_out,
            payment_progress=progress,
            claimed_amount_excl_tax=_fmt_amount(claimed),
            remaining_claim_amount_excl_tax=remaining,
        )
    elif target in {"returned", "rejected"}:
        progress = format_progress(target, node)
        _update_tracker(
            project_root,
            package_name,
            next_payment_node=node,
            payment_progress=progress,
        )
    else:
        progress = format_progress(target, node)
        _update_tracker(
            project_root,
            package_name,
            next_payment_node=node,
            payment_progress=progress,
        )

    archived: list[str] = []
    if args.source_eml:
        p = _archive_file(
            pkg, Path(args.source_eml).expanduser().resolve(), f"PAY{payment_no}_{target}"
        )
        if p:
            archived.append(str(p))
    if args.response:
        p = _archive_file(
            pkg, Path(args.response).expanduser().resolve(), f"PAY{payment_no}_response"
        )
        if p:
            archived.append(str(p))

    legacy = pkg / "03_请款记录" / "payment_ledger.json"
    print(f"package={package_name}")
    print(f"payment_no={payment_no}")
    print(f"node={node}")
    print(f"status={target}")
    print(f"status_label={status_label(target)}")
    print(f"payment_progress={progress}")
    print(f"next_payment_node={next_out}")
    if is_completed(target):
        print(f"claimed_amount_excl_tax={_fmt_amount(claimed)}")
    if archived:
        print("archived=" + ";".join(archived))
    if legacy.is_file():
        print("legacy_payment_ledger_ignored=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
