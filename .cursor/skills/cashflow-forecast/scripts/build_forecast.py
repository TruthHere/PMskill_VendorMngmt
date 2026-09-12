#!/usr/bin/env python3
"""Build supplier cash-out forecast (Skill 4). Read-only aggregation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
_CURSOR = _SKILL_ROOT.parents[1]
_FOUNDATION = _CURSOR / "lib" / "project-foundation" / "scripts"
_PAYMENT = _CURSOR / "skills" / "payment-request" / "scripts"
for _p in (_SCRIPTS, _FOUNDATION, _PAYMENT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from common import load_json, load_tracker_packages, parse_amount_with_tax, confirmed_changes_total_excl_tax  # noqa: E402
from forecast_sources import collect_forecast_sources  # noqa: E402
from payment_status import completed_nodes_before  # noqa: E402
from write_forecast_xlsx import write_forecast_xlsx  # noqa: E402

_PCT = re.compile(r"([\d.]+)\s*%")
_PKG_DIR = re.compile(r"^\d+_")
_PO_LAG = re.compile(
    r"(?:PO|合同|订单).{0,12}?(?:签发|生效|签署).{0,8}?(\d+)\s*(?:个)?日",
    re.I,
)


def _parse_ymd(s: str | None) -> date | None:
    if not s:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(s))
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _parse_pct(raw: str | None) -> float | None:
    if not raw:
        return None
    m = _PCT.search(str(raw))
    if not m:
        return None
    return float(m.group(1))


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)


def _iter_months(start: date, end: date) -> list[str]:
    cur = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    out: list[str] = []
    while cur <= last:
        out.append(_month_key(cur))
        cur = _add_months(cur, 1)
    return out


def _format_terms(nodes: list[dict]) -> str:
    parts: list[str] = []
    for node in nodes:
        name = str(node.get("name") or "").split("/")[0].strip()
        pct = str(node.get("pct") or "").strip()
        if name and pct:
            parts.append(f"{name} {pct}")
        elif name:
            parts.append(name)
    return "；".join(parts)


def _project_bound_dates(project: dict[str, Any], project_root: Path) -> list[date]:
    dates: list[date] = []
    for key in ("start_date", "project_start", "end_date", "project_end"):
        d = _parse_ymd(str(project.get(key) or ""))
        if d:
            dates.append(d)
    sched = load_json(project_root / ".skill" / "schedule.json", {}) or {}
    for n in sched.get("critical_nodes") or []:
        if not isinstance(n, dict):
            continue
        for key in ("window_start", "window_end"):
            d = _parse_ymd(n.get(key))
            if d:
                dates.append(d)
    for m in sched.get("milestones") or []:
        if not isinstance(m, dict):
            continue
        d = _parse_ymd(str(m.get("date") or m.get("end_date") or ""))
        if d:
            dates.append(d)
    return dates


def _find_package_dirs(project_root: Path) -> list[Path]:
    return sorted(
        p for p in project_root.iterdir() if p.is_dir() and _PKG_DIR.match(p.name)
    )


def _tracker_by_name(packages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for pkg in packages:
        name = str(pkg.get("package_name") or "").strip()
        if name:
            out[name] = pkg
    return out


def _float_amount(text: str | None) -> float | None:
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    if re.fullmatch(r"-?[\d.]+", s):
        return float(s)
    parsed = parse_amount_with_tax(s)
    for key in ("amount_excl_tax", "amount", "value"):
        v = parsed.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    nums = re.findall(r"[\d,]+\.?\d*", s.replace(",", ""))
    if nums:
        try:
            return float(nums[0])
        except ValueError:
            return None
    return None


def _schedule_ends(project_root: Path, package_name: str) -> dict[str, date]:
    sched = load_json(project_root / ".skill" / "schedule.json", {}) or {}
    out: dict[str, date] = {}
    for n in sched.get("critical_nodes") or []:
        if not isinstance(n, dict):
            continue
        if (n.get("package_name") or "").strip() != package_name:
            continue
        end = _parse_ymd(n.get("window_end"))
        if not end:
            continue
        for key in filter(
            None, [n.get("name"), n.get("name_zh"), n.get("name_en"), n.get("node_code")]
        ):
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
        "预付",
        "到货",
        "安装",
        "验收",
        "调试",
        "尾款",
        "质保",
        "进度",
        "advance",
        "delivery",
        "install",
        "accept",
        "commission",
        "retention",
    ):
        if token.lower() in low:
            for k, v in ends.items():
                if token.lower() in k:
                    return v
    return None


def _infer_from_condition(condition: str, po_date: date | None) -> date | None:
    if not condition or not po_date:
        return None
    m = _PO_LAG.search(condition)
    if m:
        return po_date + timedelta(days=int(m.group(1)))
    if re.search(r"PO|合同|订单", condition, re.I) and re.search(
        r"生效|签发|签署", condition
    ):
        return po_date
    return None


def _claim_for_node(claims: list[dict], node_name: str, payment_no: int) -> dict | None:
    for c in claims or []:
        if int(c.get("payment_no") or 0) == payment_no:
            return c
    for c in claims or []:
        n = str(c.get("node") or "").strip()
        if n == node_name:
            return c
        primary = node_name.split("/")[0].strip()
        if primary and primary in n:
            return c
    return None


@dataclass
class ForecastConfig:
    as_of: date
    horizon_months: int
    payment_lag_days: int
    tax_basis: str = "excl_tax"
    tail_months: int = 1


@dataclass
class BuildState:
    line_items: list[dict[str, Any]] = field(default_factory=list)
    pending: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


def _load_overrides(project_root: Path) -> dict[str, Any]:
    return load_json(project_root / ".skill" / "cashflow_overrides.json", {}) or {}


def _override_map(overrides_doc: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in overrides_doc.get("overrides") or []:
        if not isinstance(row, dict):
            continue
        pkg = str(row.get("package") or "").strip()
        try:
            no = int(row.get("payment_no"))
        except (TypeError, ValueError):
            continue
        if pkg and no:
            out[(pkg, no)] = row
    return out


def _resolve_dates(
    *,
    package_name: str,
    payment_no: int,
    node: dict[str, Any],
    ends: dict[str, date],
    po_date: date | None,
    override_row: dict[str, Any] | None,
    claim: dict | None,
    payment_lag_days: int,
) -> tuple[date | None, date | None, str, str]:
    """Return anchor_date, cash_out_date, date_source, date_confidence."""
    node_name = str(node.get("name") or "").strip()

    if override_row:
        out = _parse_ymd(override_row.get("forecast_date"))
        if out:
            return out, out, "override", "high"

    # 已请完节点：不再有 ledger 批复日；用窗口日当出账锚点（已发生）
    if claim is True:
        end = _match_end(node_name, ends)
        if end:
            return end, end, "tracker_paid", "medium"

    milestone = _parse_ymd(node.get("milestone"))
    if milestone:
        cash = milestone + timedelta(days=payment_lag_days)
        return milestone, cash, "milestone", "high"

    end = _match_end(node_name, ends)
    if end:
        return end, end + timedelta(days=payment_lag_days), "window_end", "high"

    sw = _parse_ymd(str(node.get("schedule_window") or ""))
    if not sw:
        m = re.search(r"≤\s*(\d{4}-\d{2}-\d{2})", str(node.get("schedule_window") or ""))
        if m:
            sw = _parse_ymd(m.group(1))
    if sw:
        return sw, sw + timedelta(days=payment_lag_days), "schedule_window", "medium"

    inferred = _infer_from_condition(str(node.get("condition") or ""), po_date)
    if inferred:
        return inferred, inferred + timedelta(days=payment_lag_days), "condition_infer", "medium"

    return None, None, "pending", "pending"


def _pct_sum(nodes: list[dict]) -> float | None:
    if not nodes:
        return None
    total = 0.0
    for node in nodes:
        p = _parse_pct(str(node.get("pct") or ""))
        if p is None:
            return None
        total += p
    return total


def build_forecast(project_root: Path, cfg: ForecastConfig) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    project = load_json(project_root / ".skill" / "project.json", {}) or {}
    currency = str(project.get("currency") or "CNY")
    overrides_doc = _load_overrides(project_root)
    lag = int(
        (overrides_doc.get("assumptions") or {}).get("payment_lag_days") or cfg.payment_lag_days
    )
    override_lookup = _override_map(overrides_doc)

    tracker_rows = load_tracker_packages(project_root)
    tracker_map = _tracker_by_name(tracker_rows)
    state = BuildState()
    calendar_dates = _project_bound_dates(project, project_root)

    contract_total = 0.0
    changes_total = 0.0
    paid_total = 0.0
    packages_out: list[dict[str, Any]] = []

    for pkg_dir in _find_package_dirs(project_root):
        card = load_json(pkg_dir / "card-data.json", {}) or {}
        if not isinstance(card, dict):
            continue
        package_name = str(card.get("package_name") or "").strip()
        supplier = str(card.get("supplier_name") or "").strip()
        nodes = list(card.get("payment_nodes") or [])
        changes_sum = confirmed_changes_total_excl_tax(project_root, package_name)
        changes_total += changes_sum

        tracker = tracker_map.get(package_name, {})
        base = _float_amount(tracker.get("amount_excl_tax"))
        if base is None:
            base = _float_amount(card.get("total_amount"))
        if base is not None:
            contract_total += base
        for key in ("ts_rfp_issued", "ts_po_issued"):
            d = _parse_ymd(str(tracker.get(key) or "")[:10])
            if d:
                calendar_dates.append(d)

        po_date = _parse_ymd(str(tracker.get("ts_po_issued") or "")[:10])
        next_node = str(tracker.get("next_payment_node") or "").strip()
        occupied = completed_nodes_before(card if isinstance(card, dict) else {}, next_node)
        po_number = (
            str(card.get("po_number") or "").strip()
            or str(card.get("contract_or_quote_no") or "").strip()
        )

        ends = _schedule_ends(project_root, package_name)
        parts = pkg_dir.name.split("_", 2)
        if len(parts) >= 2:
            ends.update(_schedule_ends(project_root, parts[1]))

        pct_total = _pct_sum(nodes)
        if pct_total is not None and abs(pct_total - 100.0) > 1.0:
            state.warnings.append(
                {
                    "code": "payment_pct_sum_not_100",
                    "package": package_name,
                    "message": f"{package_name} 付款节点比例合计 {pct_total:.1f}%（偏离 100%）",
                }
            )

        last_index = len(nodes)
        month_map: dict[str, dict[str, float]] = {}
        pending_pkg = 0.0

        for index, node in enumerate(nodes, start=1):
            if not isinstance(node, dict):
                continue
            node_name = str(node.get("name") or "").strip()
            pct = _parse_pct(str(node.get("pct") or ""))

            expected: float | None = None
            includes_change = False
            if base is not None and pct is not None:
                expected = round(base * pct / 100.0, 2)
                if index == last_index and changes_sum:
                    expected = round(expected + changes_sum, 2)
                    includes_change = True
            else:
                state.pending.append(
                    {
                        "package": package_name,
                        "payment_no": index,
                        "node": node_name,
                        "reason": "amount_missing",
                        "message": "缺合同基数或节点比例，无法算金额",
                    }
                )

            actual_amount: float | None = None
            primary = node_name.split("/")[0].strip()
            is_actual = bool(
                node_name in occupied
                or (primary and any(primary in c for c in occupied))
            )
            if is_actual:
                actual_amount = expected
                if actual_amount is not None:
                    paid_total += actual_amount

            override_row = override_lookup.get((package_name, index))
            planned_anchor, planned_cash, date_source, confidence = _resolve_dates(
                package_name=package_name,
                payment_no=index,
                node=node,
                ends=ends,
                po_date=po_date,
                override_row=override_row,
                claim=is_actual,
                payment_lag_days=lag,
            )
            actual_date = planned_anchor if is_actual else None
            if planned_cash:
                calendar_dates.append(planned_cash)
            if actual_date:
                calendar_dates.append(actual_date)

            if is_actual:
                status = "actual"
            elif planned_cash is not None and expected is not None:
                status = "forecast"
            else:
                status = "pending"
                if expected is not None:
                    pending_pkg += expected
                    state.pending.append(
                        {
                            "package": package_name,
                            "payment_no": index,
                            "node": node_name,
                            "amount_excl_tax": expected,
                            "reason": "date_pending",
                            "message": f"{package_name} · {node_name} 有金额但无可靠出账日",
                        }
                    )

            planned_month = _month_key(planned_cash) if planned_cash else None
            actual_month = _month_key(actual_date) if actual_date else None
            if planned_month and expected:
                bucket = month_map.setdefault(planned_month, {"expected": 0.0, "actual": 0.0})
                bucket["expected"] += float(expected)
            if actual_month and actual_amount:
                bucket = month_map.setdefault(actual_month, {"expected": 0.0, "actual": 0.0})
                bucket["actual"] += float(actual_amount)

            item = {
                "package": package_name,
                "supplier": supplier,
                "package_dir": pkg_dir.name,
                "payment_no": index,
                "node": node_name,
                "status": status,
                "expected_amount_excl_tax": expected,
                "actual_amount_excl_tax": actual_amount,
                "includes_change_amount": includes_change,
                "anchor_date": planned_anchor.isoformat() if planned_anchor else None,
                "planned_cash_out_date": planned_cash.isoformat() if planned_cash else None,
                "planned_cash_out_month": planned_month,
                "actual_date": actual_date.isoformat() if actual_date else None,
                "actual_month": actual_month,
                "date_confidence": confidence,
                "date_source": "tracker_paid" if is_actual and actual_date else date_source,
                "pct": node.get("pct"),
            }
            if override_row and override_row.get("note"):
                item["note"] = override_row.get("note")
            state.line_items.append(item)

        packages_out.append(
            {
                "seq": str(tracker.get("seq") or pkg_dir.name.split("_", 1)[0]),
                "package": package_name,
                "supplier": supplier,
                "package_dir": pkg_dir.name,
                "amount_excl_tax": base,
                "changes_excl_tax": round(changes_sum, 2),
                "po_number": po_number,
                "payment_terms": _format_terms(nodes),
                "pending_excl_tax": round(pending_pkg, 2),
                "months": {
                    k: {"expected": round(v["expected"], 2), "actual": round(v["actual"], 2)}
                    for k, v in month_map.items()
                },
            }
        )

    if calendar_dates:
        cal_start = min(calendar_dates).replace(day=1)
        cal_end = _add_months(max(calendar_dates).replace(day=1), cfg.tail_months)
    else:
        cal_start = cfg.as_of.replace(day=1)
        cal_end = _add_months(cal_start, cfg.horizon_months)
    months_axis = _iter_months(cal_start, cal_end)

    forecast_remaining = 0.0
    pending_amount = 0.0
    monthly_map: dict[str, dict[str, float]] = {
        m: {"expected": 0.0, "actual": 0.0} for m in months_axis
    }
    for item in state.line_items:
        expected = item.get("expected_amount_excl_tax")
        actual = item.get("actual_amount_excl_tax")
        st = item.get("status")
        if st == "forecast" and expected:
            forecast_remaining += float(expected)
        elif st == "pending" and expected:
            pending_amount += float(expected)
        planned_month = item.get("planned_cash_out_month")
        actual_month = item.get("actual_month")
        if planned_month and expected and planned_month in monthly_map:
            monthly_map[planned_month]["expected"] += float(expected)
        if actual_month and actual and actual_month in monthly_map:
            monthly_map[actual_month]["actual"] += float(actual)

    monthly_rows = [
        {
            "month": month,
            "expected": round(monthly_map[month]["expected"], 2),
            "actual": round(monthly_map[month]["actual"], 2),
        }
        for month in months_axis
    ]

    expected_max = contract_total + changes_total
    if expected_max > 0 and (paid_total + forecast_remaining + pending_amount) > expected_max * 1.01:
        state.warnings.append(
            {
                "code": "forecast_exceeds_contract",
                "message": "预测待付+已付超过合同+已确认变更（>1% 容差），请核对基数或节点比例",
            }
        )

    return {
        "as_of": cfg.as_of.isoformat(),
        "currency": currency,
        "tax_basis": cfg.tax_basis,
        "payment_lag_days": lag,
        "horizon_months": cfg.horizon_months,
        "tail_months": cfg.tail_months,
        "summary": {
            "contract_base_excl_tax": round(contract_total, 2),
            "changes_confirmed_excl_tax": round(changes_total, 2),
            "paid_to_date_excl_tax": round(paid_total, 2),
            "forecast_remaining_excl_tax": round(forecast_remaining, 2),
            "pending_amount_excl_tax": round(pending_amount, 2),
        },
        "calendar": {
            "start_month": months_axis[0] if months_axis else None,
            "end_month": months_axis[-1] if months_axis else None,
            "months": months_axis,
        },
        "packages": packages_out,
        "monthly": monthly_rows,
        "line_items": state.line_items,
        "pending": state.pending,
        "warnings": state.warnings,
        "sources": collect_forecast_sources(project_root),
    }


def write_outputs(project_root: Path, doc: dict[str, Any]) -> list[Path]:
    project_root = project_root.expanduser().resolve()
    project = load_json(project_root / ".skill" / "project.json", {}) or {}
    project_name = str(project.get("project_name") or project_root.name)

    written: list[Path] = []

    json_path = project_root / ".skill" / "cashflow_forecast.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    written.append(json_path)

    from check_sources import write_check_command

    cmd_path = write_check_command(project_root, sys.executable)
    written.append(cmd_path)

    xlsx_path = project_root / f"{project_name}_现金流预测.xlsx"
    write_forecast_xlsx(xlsx_path, doc, project_name, check_command=cmd_path)
    written.append(xlsx_path)

    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--horizon-months", type=int, default=18)
    ap.add_argument("--tail-months", type=int, default=1, help="项目结束后再留几个月")
    ap.add_argument("--payment-lag-days", type=int, default=30)
    ap.add_argument("--tax-basis", default="excl_tax", choices=["excl_tax", "incl_tax"])
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    root = Path(args.project_root).expanduser().resolve()
    as_of = _parse_ymd(args.as_of) or date.today()
    cfg = ForecastConfig(
        as_of=as_of,
        horizon_months=args.horizon_months,
        payment_lag_days=args.payment_lag_days,
        tax_basis=args.tax_basis,
        tail_months=args.tail_months,
    )
    doc = build_forecast(root, cfg)
    text = json.dumps(doc, ensure_ascii=False, indent=2)
    print(text)
    if args.write:
        paths = write_outputs(root, doc)
        for p in paths:
            print(f"Wrote {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
