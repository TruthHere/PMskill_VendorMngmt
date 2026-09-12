#!/usr/bin/env python3
"""Render critical_nodes timeline HTML (presentation.md §3)."""

from __future__ import annotations

import argparse
import html
import json
import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from cn_holidays import HolidayBand, holiday_bands_for_axis
from timeline_insights import (
    coverage_and_attention,
    node_needs_review,
    parse_basis,
    project_anchor_marks,
    timeline_kpis,
    upcoming_critical_nodes,
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# 轴上圆点内显示的简称（2–3 字）；完整名在悬停 tip
NODE_AXIS_SHORT: dict[str, str] = {
    "delivery": "到货",
    "site_access": "进场",
    "install_complete": "安装",
    "commissioning": "调试",
    "prelim_accept": "初验",
    "final_accept": "终验",
    "project_handover": "验收",
    "project_start": "开工",
    "project_completion": "竣工",
    "project_interface": "界面",
    "po_confirm": "下单",
    "fat": "厂验",
    "shipment": "发运",
    "warranty_start": "质保",
    "contract_sign": "签约",
    "concept": "方案",
    "detail_deliverable": "成果",
    "site_support": "配合",
    "deliverable_accept": "成果验",
}


def node_axis_label(n: dict[str, Any]) -> str:
    code = str(n.get("node_code") or "").strip()
    if code in NODE_AXIS_SHORT:
        return NODE_AXIS_SHORT[code]
    name_zh = str(n.get("name_zh") or "").strip()
    name = str(n.get("name") or "").strip()
    text = re.sub(r"[\sA-Za-z/].*", "", name_zh or name).strip()
    if not text:
        return "?"
    if "隔墙" in text:
        return "隔墙"
    if "吊顶" in text or "天花" in text:
        return "吊顶"
    if "许可" in text:
        return "许可"
    if "客户" in text and "验收" in text:
        return "验收"
    for suf in ("验收", "完成", "获得"):
        if text.endswith(suf) and len(text) > len(suf) + 1:
            text = text[: -len(suf)]
            break
    if len(text) <= 4:
        return text
    return text[:3]


def parse_iso_date(value: str) -> date | None:
    raw = (value or "").strip()[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _date_to_axis_pct(d: date, months: list[date]) -> float:
    """按「每月等宽列」换算位置，使 10/1 对齐十月列左缘（与月头标签一致）。"""
    if not months:
        return 0.0
    n = len(months)
    ms = date(d.year, d.month, 1)
    if d < months[0]:
        return 0.0
    if ms > months[-1]:
        return 100.0
    try:
        i = months.index(ms)
    except ValueError:
        # 轴外月份：夹到两端
        if ms < months[0]:
            return 0.0
        return 100.0
    dim = monthrange(d.year, d.month)[1]
    frac = (d.day - 1) / max(dim, 1)
    return (i + frac) / n * 100.0


def _holiday_layer_html(
    bands: list[HolidayBand],
    *,
    months: list[date],
    with_label: bool,
) -> str:
    if not bands or not months:
        return ""
    parts: list[str] = []
    for b in bands:
        left = _date_to_axis_pct(b.start, months)
        # 结束日含当天：落到该日结束后的边界
        end_exclusive = b.end + timedelta(days=1)
        right = _date_to_axis_pct(end_exclusive, months)
        if end_exclusive.month != b.end.month or end_exclusive.day == 1:
            # 跨月到下月 1 号 = 下月列左缘，已正确
            pass
        width = right - left
        if width <= 0:
            continue
        left = max(0.0, min(left, 100.0))
        width = max(0.6, min(width, 100.0 - left))
        short = {
            "spring": "春节",
            "labor": "五一",
            "national": "国庆",
        }.get(b.kind, b.name)
        full_name = {
            "spring": "春节停工",
            "labor": "五一长假",
            "national": "国庆长假",
        }.get(b.kind, b.name)
        tip = html.escape(
            json.dumps(
                {
                    "kind": "holiday",
                    "name": full_name,
                    "range": f"{b.start.isoformat()}～{b.end.isoformat()}",
                    "note": b.note,
                    "color": "#b44830" if b.kind == "spring" else "#9a5a28",
                },
                ensure_ascii=False,
            ),
            quote=True,
        )
        label = ""
        if with_label:
            label = (
                f'<span class="holiday-label">{html.escape(short)}</span>'
            )
        parts.append(
            f'<div class="holiday-band {html.escape(b.kind)}" style="left:{left:.3f}%;'
            f'width:{width:.3f}%" data-tip="{tip}" role="img" '
            f'aria-label="{html.escape(full_name)}">'
            f"{label}</div>"
        )
    if not parts:
        return ""
    return f'<div class="holiday-layer">{"".join(parts)}</div>'


def _anchor_layer_html(
    anchors: list[dict[str, Any]],
    *,
    months: list[date],
    with_label: bool,
) -> str:
    if not anchors or not months:
        return ""
    parts: list[str] = []
    for a in anchors:
        d = parse_iso_date(str(a.get("date") or ""))
        if not d:
            continue
        left = _date_to_axis_pct(d, months)
        kind = str(a.get("kind") or "anchor")
        label = str(a.get("label") or "")
        tip = html.escape(
            json.dumps(
                {
                    "kind": "anchor",
                    "anchor_kind": kind,
                    "name": label,
                    "range": str(a.get("date") or ""),
                    "note": str(a.get("source") or ""),
                },
                ensure_ascii=False,
            ),
            quote=True,
        )
        label_html = ""
        if with_label and label:
            label_html = (
                f'<span class="anchor-label">{html.escape(label)}</span>'
            )
        parts.append(
            f'<div class="anchor-mark {html.escape(kind)}" style="left:{left:.3f}%" '
            f'data-tip="{tip}" role="img" aria-label="{html.escape(label)}">'
            f"{label_html}</div>"
        )
    if not parts:
        return ""
    return f'<div class="anchor-layer">{"".join(parts)}</div>'


def _source_short(source: str) -> str:
    return {
        "explicit": "明示",
        "inferred": "倒推",
        "aligned": "对齐",
        "manual": "手工",
    }.get(source, source)


def _build_insights_html(
    upcoming: list[dict[str, Any]],
    attention: dict[str, Any],
    kpis: dict[str, int],
) -> str:
    n_pkg = kpis.get("packages", 0)
    n_up = kpis.get("upcoming_30d", 0)
    n_att = kpis.get("attention", 0)

    kpi = (
        f'<div class="kpi">'
        f'<span><strong>{n_pkg}</strong> 个采购包</span>'
    )
    if n_up:
        kpi += (
            f'<span>近 30 天内有 <strong>{n_up}</strong> 个重要节点</span>'
        )
    else:
        kpi += "<span>近 30 天内无重要节点</span>"
    kpi += "</div>"

    up_lines: list[str] = []
    for item in upcoming:
        src = _source_short(str(item.get("source") or ""))
        flag = " ?" if item.get("needs_confirm") else ""
        up_lines.append(
            "<li>"
            f'<span class="up-when">{html.escape(str(item.get("window_end") or ""))}</span> '
            f"{html.escape(str(item.get('package_name') or ''))} · "
            f"{html.escape(str(item.get('name') or ''))}"
            f'<span class="up-src">{html.escape(src)}{flag}</span>'
            "</li>"
        )
    if up_lines:
        upcoming_block = (
            '<section class="panel upcoming">'
            '<h2 class="panel-title">近 30 天内将完成</h2>'
            f'<ol class="panel-list">{"".join(up_lines)}</ol>'
            "</section>"
        )
    else:
        upcoming_block = ""

    att_parts: list[str] = []
    for row in attention.get("pending") or []:
        pkg = str(row.get("package_name") or "").strip()
        msg = str(row.get("message") or "").strip()
        prefix = f"{html.escape(pkg)} · " if pkg else ""
        att_parts.append(
            f'<li class="att-item">'
            f'<div class="att-head">{prefix}{html.escape(msg)}</div>'
            "</li>"
        )
    for row in attention.get("reviews") or []:
        pkg = html.escape(str(row.get("package_name") or ""))
        name = html.escape(str(row.get("name") or ""))
        src = html.escape(_source_short(str(row.get("source") or "")))
        when = html.escape(str(row.get("window_end") or ""))
        evidence = str(row.get("basis_evidence") or "").strip()
        how = str(row.get("basis_how") or "").strip()
        if not evidence and not how:
            how = str(row.get("basis") or "").strip() or "未写依据"
        basis_bits: list[str] = []
        if evidence:
            basis_bits.append(
                f'<div class="att-basis"><span class="att-k">依据</span>'
                f"{html.escape(evidence)}</div>"
            )
        if how:
            basis_bits.append(
                f'<div class="att-basis"><span class="att-k">定法</span>'
                f"{html.escape(how)}</div>"
            )
        risk = str(row.get("risks") or "").strip()
        risk_html = (
            f'<div class="att-risk">{html.escape(risk)}</div>' if risk else ""
        )
        cn_index = int(row.get("cn_index") if row.get("cn_index") is not None else -1)
        pkg_raw = str(row.get("package_name") or "")
        code_raw = str(row.get("node_code") or "")
        when_raw = str(row.get("window_end") or "")
        actions = (
            f'<div class="att-actions">'
            f'<button type="button" data-att-action="confirm">确认无误</button>'
            f'<button type="button" data-att-action="edit">改日期</button>'
            f'<button type="button" data-att-action="delete">删除</button>'
            f"</div>"
        )
        att_parts.append(
            f'<li class="att-item" data-cn-index="{cn_index}" '
            f'data-package-name="{html.escape(pkg_raw, quote=True)}" '
            f'data-node-code="{html.escape(code_raw, quote=True)}" '
            f'data-end="{html.escape(when_raw, quote=True)}">'
            f'<div class="att-head">{pkg} · {name}'
            f'<span class="up-src">{src} {when}</span></div>'
            f"{''.join(basis_bits)}"
            f"{risk_html}"
            f"{actions}"
            f"</li>"
        )

    if att_parts:
        attention_block = (
            f'<details class="attention-fold">'
            f'<summary>待确认 <span class="att-count">{n_att}</span></summary>'
            f'<ul class="panel-list att-review">{"".join(att_parts)}</ul>'
            f"</details>"
        )
    else:
        attention_block = ""

    return f'<div class="insights">{kpi}{upcoming_block}{attention_block}</div>'


def decade_label(iso_date: str) -> str:
    dt = parse_iso_date(iso_date)
    if not dt:
        return iso_date or ""
    if dt.day <= 10:
        decade = "上旬"
    elif dt.day <= 20:
        decade = "中旬"
    else:
        decade = "下旬"
    return f"{dt.year}年{dt.month}月{decade}"


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def _months_between(start: date, end: date) -> list[date]:
    cur = _month_start(start)
    last = _month_start(end)
    out: list[date] = []
    while cur <= last:
        out.append(cur)
        cur = _add_months(cur, 1)
    return out or [_month_start(start)]


def group_nodes(
    critical: list[dict[str, Any]],
    *,
    package_filter: str | None = None,
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    by_pkg: dict[str, list[dict[str, Any]]] = {}
    for n in critical:
        pname = str(n.get("package_name") or "_project")
        if package_filter and pname not in (package_filter, "_project"):
            continue
        by_pkg.setdefault(pname, []).append(n)

    rows: list[tuple[str, str, list[dict[str, Any]]]] = []
    # 总包行置顶（旧数据里的 _project 兼容为「项目锚点」）
    for key, label in (("_project", "项目锚点（旧）"),):
        if key in by_pkg:
            nodes = sorted(
                by_pkg[key],
                key=lambda n: (
                    n.get("window_end") or n.get("window_start") or "",
                    n.get("node_code") or "",
                ),
            )
            rows.append((label, key, nodes))

    # Prefer 总包 package name variants first
    gc_names = [k for k in by_pkg if k not in {"_project"} and (
        str(by_pkg[k][0].get("package_type") or "") == "总包" or k in {"总包", "GC", "gc"}
    )]
    for pname in sorted(gc_names):
        nodes = by_pkg[pname]
        ptype = str(nodes[0].get("package_type") or "")
        nodes = sorted(
            nodes,
            key=lambda n: (n.get("window_end") or n.get("window_start") or "", n.get("node_code") or ""),
        )
        title = f"{pname}（{ptype}）" if ptype else pname
        rows.append((title, pname, nodes))

    for pname in sorted(k for k in by_pkg if k != "_project" and k not in gc_names):
        nodes = by_pkg[pname]
        ptype = str(nodes[0].get("package_type") or "")
        nodes = sorted(
            nodes,
            key=lambda n: (n.get("window_end") or n.get("window_start") or "", n.get("node_code") or ""),
        )
        title = f"{pname}（{ptype}）" if ptype else pname
        rows.append((title, pname, nodes))
    return rows


_PKG_COLORS = (
    "#1e4d8c",  # gc / blue
    "#0d7377",  # teal
    "#c45d26",  # terracotta
    "#2f6b3a",  # green
    "#6b3fa0",  # purple
    "#b45309",  # amber
)


def _package_color(package_name: str, package_type: str, index: int) -> str:
    key = f"{package_name}|{package_type}".lower()
    if package_type == "总包" or package_name in {"总包", "GC", "_project"}:
        return "#1e4d8c"
    if "bms" in key:
        return "#0d7377"
    if "家具" in package_name or "furn" in key:
        return "#c45d26"
    if "配电" in package_name or "pdb" in key:
        return "#2f6b3a"
    return _PKG_COLORS[index % len(_PKG_COLORS)]


def render_timeline_html(
    schedule: dict[str, Any],
    *,
    project_name: str = "",
    package_filter: str | None = None,
    highlight_package: str | None = None,
) -> str:
    critical = schedule.get("critical_nodes") or []
    if not isinstance(critical, list):
        critical = []
    rows = group_nodes(critical, package_filter=package_filter)

    ends: list[date] = []
    for _, _, nodes in rows:
        for n in nodes:
            d = parse_iso_date(str(n.get("window_end") or ""))
            if d:
                ends.append(d)
    if not ends:
        today = date.today()
        ends = [today, today + timedelta(days=90)]

    axis_start = _month_start(min(ends))
    months = _months_between(axis_start, _add_months(_month_start(max(ends)), 0))
    # Ensure at least the month of max end is included fully
    if months[-1] < _month_start(max(ends)):
        months.append(_month_start(max(ends)))
    last_month = months[-1]
    axis_end_day = date(
        last_month.year, last_month.month, monthrange(last_month.year, last_month.month)[1]
    )
    total_days = max((axis_end_day - axis_start).days, 1)
    month_count = max(len(months), 1)
    month_w = 108
    label_w = 148
    track_w = month_w * month_count

    holiday_bands = holiday_bands_for_axis(axis_start, axis_end_day)
    holiday_header = _holiday_layer_html(
        holiday_bands, months=months, with_label=True
    )
    holiday_tracks = _holiday_layer_html(
        holiday_bands, months=months, with_label=False
    )

    anchors = project_anchor_marks(
        schedule, axis_start=axis_start, axis_end=axis_end_day
    )
    anchor_header = _anchor_layer_html(
        anchors, months=months, with_label=True
    )
    anchor_tracks = _anchor_layer_html(
        anchors, months=months, with_label=False
    )

    upcoming = upcoming_critical_nodes(schedule)
    attention = coverage_and_attention(schedule)
    kpis = timeline_kpis(schedule, upcoming=upcoming, attention=attention)
    insights_html = _build_insights_html(upcoming, attention, kpis)

    month_cells: list[str] = []
    for m in months:
        month_cells.append(
            '<div class="month">'
            f'<span class="y">{m.year}</span>'
            f"<span>{m.month}月</span>"
            '<span class="thirds"><i></i><i></i><i></i></span>'
            "</div>"
        )

    grid_rows: list[str] = []

    for row_i, (title, pname, nodes) in enumerate(rows):
        ptype = ""
        if nodes:
            ptype = str(nodes[0].get("package_type") or "")
        color = _package_color(pname, ptype, row_i)
        hl = " highlight" if highlight_package and pname == highlight_package else ""
        short = pname if pname != "_project" else "项目锚点"
        type_label = ptype if ptype and ptype not in {"_project"} else ""

        dots: list[str] = []
        for i, n in enumerate(nodes, start=1):
            end = str(n.get("window_end") or "")
            d = parse_iso_date(end)
            if not d:
                continue
            left = ((d - axis_start).days / total_days) * 100
            left = min(max(left, 0.8), 99.2)
            name_zh = str(n.get("name_zh") or "").strip()
            name = str(n.get("name") or n.get("node_code") or f"节点{i}")
            code = str(n.get("node_code") or "")
            decade = decade_label(end)
            source = str(n.get("source") or "")
            inferred = source == "inferred"
            source_label = {
                "explicit": "计划明示",
                "inferred": "倒推",
                "aligned": "对齐",
                "manual": "手工调整",
            }.get(source, source)
            basis = str(n.get("basis") or "").strip()
            parsed_basis = parse_basis(basis)
            needs_review = node_needs_review(n)
            display_name = name_zh or name
            axis_label = node_axis_label(n)
            # Index into schedule.critical_nodes for edits
            cn_index = -1
            for ci, cn in enumerate(critical):
                if cn is n or (
                    isinstance(cn, dict)
                    and cn.get("package_name") == n.get("package_name")
                    and cn.get("node_code") == n.get("node_code")
                    and cn.get("window_end") == n.get("window_end")
                    and cn.get("name") == n.get("name")
                ):
                    cn_index = ci
                    break
            tip_data = html.escape(
                json.dumps(
                    {
                        "ordinal": i,
                        "package": title,
                        "package_name": pname,
                        "package_type": ptype,
                        "name": display_name,
                        "name_full": name,
                        "axis_label": axis_label,
                        "node_code": code,
                        "decade": decade,
                        "end": end,
                        "source": source_label,
                        "needs_confirm": bool(n.get("needs_confirm")),
                        "needs_review": needs_review,
                        "basis": basis,
                        "basis_evidence": parsed_basis.get("evidence") or "",
                        "basis_how": parsed_basis.get("how") or "",
                        "color": color,
                        "cn_index": cn_index,
                    },
                    ensure_ascii=False,
                ),
                quote=True,
            )
            cls = "node"
            if needs_review:
                cls += " needs-review"
            elif inferred:
                cls += " inferred"
            if source == "manual":
                cls += " manual"
            dots.append(
                f'<button type="button" class="{cls}" style="left:{left:.3f}%;'
                f'--node:{color}" data-tip="{tip_data}" data-cn-index="{cn_index}" '
                f'data-package="{html.escape(pname, quote=True)}" '
                f'aria-label="{html.escape(display_name, quote=True)}">'
                f'<span class="node-text">{html.escape(axis_label)}</span></button>'
            )

        type_bit = (
            f'<span class="pkg-type">{html.escape(type_label)}</span>'
            if type_label
            else ""
        )
        grid_rows.append(
            f'<div class="pkg-label sticky-cell{hl}" data-package-name="'
            f'{html.escape(pname, quote=True)}" data-package-type="'
            f'{html.escape(ptype, quote=True)}">'
            f"<strong>{html.escape(short)}</strong>{type_bit}"
            f"</div>"
            f'<div class="track{hl}" data-package-name="'
            f'{html.escape(pname, quote=True)}" style="width:{track_w}px">'
            f"{holiday_tracks}"
            f"{anchor_tracks}"
            f'{"".join(dots)}</div>'
        )

    analyzed = html.escape(str(schedule.get("analyzed_at") or ""))
    source_file = html.escape(str(schedule.get("source_file") or ""))
    title_text = project_name or "项目"
    eyebrow = html.escape(title_text)
    filter_note = (
        f" · 聚焦 {html.escape(package_filter)}" if package_filter else ""
    )
    schedule_embed = json.dumps(schedule, ensure_ascii=False).replace("</", "<\\/")
    axis_short_embed = json.dumps(NODE_AXIS_SHORT, ensure_ascii=False)
    axis_meta = html.escape(
        json.dumps(
            {
                "axis_start": axis_start.isoformat(),
                "total_days": total_days,
                "track_w": track_w,
            },
            ensure_ascii=False,
        ),
        quote=True,
    )

    if not rows:
        board_body = '<div class="empty">暂无关键节点</div>'
        detail_html = ""
    else:
        board_body = (
            f'<div class="scroller"><div class="grid" style="'
            f"--months:{month_count};--track-w:{track_w}px;--label-w:{label_w}px;"
            f"--month-w:{month_w}px\">"
            f'<div class="head-label sticky-cell">采购包</div>'
            f'<div class="months-wrap" style="width:{track_w}px">'
            f"{holiday_header}"
            f"{anchor_header}"
            f'<div class="months">{"".join(month_cells)}</div>'
            f"</div>"
            f'{"".join(grid_rows)}'
            f"</div></div>"
        )
        detail_html = ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title_text)} · 项目采购包关键节点汇总</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap" rel="stylesheet"/>
<style>
:root {{
  --ink: #1a2332;
  --muted: #6b7785;
  --line: #e2e8ef;
  --paper: #f6f8fa;
  --card: #ffffff;
  --sticky-bg: #fafbfc;
  --inferred: #9a8570;
  --rail: #eef2f6;
  --row-h: 44px;
  --holiday-spring: rgba(120, 90, 70, 0.14);
  --holiday-labor: rgba(200, 110, 40, 0.18);
  --today: #c43c2c;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: "Instrument Sans", system-ui, sans-serif;
  color: var(--ink);
  background: var(--paper);
  min-height: 100vh;
  padding: 32px 20px 48px;
  line-height: 1.45;
}}
.wrap {{ max-width: 1100px; margin: 0 auto; }}
header {{ margin-bottom: 18px; }}
header .eyebrow {{
  font-size: 13px; color: var(--muted); font-weight: 500; margin-bottom: 6px;
}}
header h1 {{
  font-family: Newsreader, Georgia, serif;
  font-weight: 500;
  font-size: clamp(1.35rem, 2.5vw, 1.75rem);
  letter-spacing: -0.01em;
  text-wrap: balance;
}}
.legend {{
  display: flex; flex-wrap: wrap; gap: 10px 18px; margin-top: 12px;
  font-size: 12px; color: var(--muted); font-weight: 500;
}}
.legend span {{ display: inline-flex; align-items: center; gap: 7px; }}
.swatch {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.swatch.ring {{ background: transparent; border: 1px dashed var(--inferred); }}
.swatch.hollow {{
  background: #fff; border: 1.5px solid var(--inferred); box-shadow: none;
}}
.swatch.band {{ width: 16px; height: 10px; border-radius: 1px; display: inline-block; }}
.swatch.band.spring {{
  background:
    repeating-linear-gradient(-45deg, rgba(120, 90, 70, 0.22) 0 2px, transparent 2px 5px),
    rgba(120, 90, 70, 0.08);
  box-shadow: inset 0 0 0 1px rgba(120, 90, 70, 0.28);
}}
.swatch.band.labor,
.swatch.band.national {{
  background: var(--holiday-labor);
  box-shadow: inset 0 0 0 1px rgba(180, 90, 30, 0.35);
}}
.anchor-swatch {{ width: 0; height: 12px; display: inline-block; }}
.anchor-swatch.today {{ border-left: 2px dashed var(--today); }}
.months-wrap {{
  position: relative; height: 44px; border-bottom: 1px solid var(--line);
  background: var(--card);
}}
.holiday-layer {{ position: absolute; inset: 0; pointer-events: none; z-index: 1; }}
.holiday-band {{
  position: absolute; top: 0; bottom: 0; pointer-events: auto; cursor: default; min-width: 8px;
}}
.holiday-band::after {{ content: ""; position: absolute; inset: 0 -6px; }}
.holiday-band.spring {{
  background:
    repeating-linear-gradient(-45deg, rgba(120, 90, 70, 0.16) 0 2px, transparent 2px 5px),
    rgba(120, 90, 70, 0.06);
}}
.holiday-band.labor,
.holiday-band.national {{ background: var(--holiday-labor); }}
.holiday-label {{
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  writing-mode: vertical-rl; text-orientation: upright;
  font-size: 10px; font-weight: 500; letter-spacing: 0.08em;
  color: rgba(107, 119, 133, 0.9); line-height: 1.05;
  white-space: nowrap; pointer-events: none;
}}
.holiday-band.labor .holiday-label,
.holiday-band.national .holiday-label {{ color: #9a5a28; }}
.holiday-band.spring .holiday-label {{ color: #6e5848; }}
.anchor-layer {{ position: absolute; inset: 0; pointer-events: none; z-index: 3; }}
.anchor-mark {{
  position: absolute; top: 0; bottom: 0; width: 0; margin-left: -1px; pointer-events: auto;
}}
.anchor-mark.today {{ border-left: 2px dashed var(--today); opacity: 0.95; }}
.anchor-label {{
  position: absolute; top: 12px; left: 5px;
  font-size: 9px; font-weight: 600; white-space: nowrap; pointer-events: none;
}}
.anchor-mark.today .anchor-label {{ color: var(--today); top: 2px; }}
.insights {{ display: grid; gap: 12px; margin-bottom: 14px; }}
.kpi {{
  display: flex; flex-wrap: wrap; gap: 12px 18px;
  font-size: 12px; color: var(--muted);
}}
.kpi strong {{ color: var(--ink); font-weight: 600; }}
.panel {{ font-size: 12px; color: var(--muted); }}
.panel-title {{
  font-size: 11px; font-weight: 550; color: var(--ink); margin-bottom: 6px;
}}
.panel-list {{ margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; }}
.panel-list li {{ line-height: 1.4; }}
.up-when {{ color: var(--ink); font-variant-numeric: tabular-nums; }}
.up-src {{ margin-left: 6px; font-size: 11px; opacity: 0.85; }}
.attention-fold {{
  border: 1px solid var(--line); border-radius: 8px; background: var(--card); padding: 0;
}}
.attention-fold > summary {{
  cursor: pointer; list-style: none; padding: 10px 12px;
  font-size: 12px; font-weight: 550; color: var(--ink);
  display: flex; align-items: center; gap: 8px; user-select: none;
}}
.attention-fold > summary::-webkit-details-marker {{ display: none; }}
.attention-fold > summary::before {{ content: "▸"; color: var(--muted); font-size: 11px; }}
.attention-fold[open] > summary::before {{ content: "▾"; }}
.att-count {{
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px;
  background: #f3ebe4; color: #8a5a40; font-size: 11px; font-weight: 600;
}}
.attention-fold .att-review {{
  padding: 10px 0 12px; gap: 10px;
  border-top: 1px solid var(--rail); margin: 0 12px;
}}
.att-item {{ display: grid; gap: 4px; }}
.att-head {{ color: var(--ink); font-weight: 550; }}
.att-basis {{ color: var(--muted); font-size: 11px; line-height: 1.45; }}
.att-k {{
  display: inline-block; min-width: 2em; margin-right: 6px;
  color: var(--ink); font-weight: 550; opacity: 0.72;
}}
.att-risk {{ color: #8a5a40; font-size: 11px; }}
.att-actions {{
  display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px;
}}
.att-actions button {{
  font: inherit; font-size: 11px; font-weight: 500;
  padding: 3px 8px; border-radius: 5px;
  border: 1px solid var(--line); background: transparent;
  color: var(--muted); cursor: pointer;
}}
.att-actions button[data-att-action="confirm"] {{
  color: var(--ink); border-color: #c5ced8;
}}
.att-actions button:hover {{ border-color: #b0bac6; color: var(--ink); }}
.board {{
  border-radius: 8px; background: var(--card);
  border: 1px solid var(--line); box-shadow: none; overflow: hidden;
}}
.scroller {{
  overflow-x: auto; overflow-y: hidden;
  -webkit-overflow-scrolling: touch; scrollbar-gutter: stable;
}}
.grid {{
  display: grid;
  grid-template-columns: var(--label-w) var(--track-w);
  width: calc(var(--label-w) + var(--track-w));
  min-width: 100%;
}}
.sticky-cell {{
  position: sticky; left: 0; z-index: 5;
  background: var(--sticky-bg);
  border-right: 1px solid var(--line);
  box-shadow: 4px 0 8px -8px rgba(26, 35, 50, 0.12);
}}
.head-label {{
  height: 44px; display: flex; align-items: flex-end;
  padding: 0 12px 10px; font-size: 11px; font-weight: 500; color: var(--muted);
}}
.months {{
  display: grid; grid-template-columns: repeat(var(--months), var(--month-w));
  height: 44px; position: relative; z-index: 2; background: transparent;
}}
.month {{
  display: flex; flex-direction: column; align-items: center;
  justify-content: flex-end; padding-bottom: 8px;
  font-size: 11px; font-weight: 500; color: var(--muted);
  border-left: 1px solid var(--rail); position: relative;
}}
.month .y {{ font-size: 9px; font-weight: 400; opacity: 0.65; }}
.month .thirds {{
  position: absolute; left: 0; right: 0; bottom: 0; height: 4px;
  display: grid; grid-template-columns: 1fr 1fr 1fr;
}}
.month .thirds i {{ border-left: 1px dashed rgba(213, 221, 230, 0.7); }}
.month .thirds i:first-child {{ border-left: 0; }}
.pkg-label {{
  height: var(--row-h); display: flex; align-items: center; gap: 6px;
  padding: 0 12px; border-top: 1px solid var(--rail);
}}
.pkg-label.highlight, .track.highlight {{ background: #f8fafc; }}
.pkg-label strong {{ font-size: 13px; font-weight: 550; }}
.pkg-type {{ font-size: 10px; color: var(--muted); font-weight: 500; }}
.track {{
  position: relative; height: var(--row-h); border-top: 1px solid var(--rail);
  background: repeating-linear-gradient(
    90deg, transparent 0, transparent calc(var(--month-w) - 1px),
    var(--rail) calc(var(--month-w) - 1px), var(--rail) var(--month-w)
  );
}}
.track::before {{
  content: ""; position: absolute; left: 0; right: 0; top: 50%;
  height: 1px; background: var(--line); transform: translateY(-50%); z-index: 0;
}}
.node {{
  position: absolute; top: 50%; transform: translate(-50%, -50%);
  z-index: 2; min-width: 28px; max-width: 52px; height: 20px;
  padding: 0 5px; border-radius: 10px;
  border: 1.5px solid #fff; background: var(--node, #0d7377);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 600; color: #fff;
  cursor: default; outline: none; touch-action: none; line-height: 1;
}}
body.editing .node {{ cursor: grab; }}
body.editing .node.dragging, body.editing .node:active {{ cursor: grabbing; }}
.node-text {{
  display: block; max-width: 44px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
  pointer-events: none; letter-spacing: -0.02em;
}}
.node.manual {{ box-shadow: 0 0 0 1px #3d5a80, 0 1px 3px rgba(0,0,0,0.1); }}
.node.inferred {{ box-shadow: 0 0 0 1px var(--inferred), 0 1px 3px rgba(0,0,0,0.08); }}
.node.needs-review {{
  background: #fff;
  color: var(--node, #0d7377);
  border: 1.5px solid var(--node, #0d7377);
  box-shadow: none;
}}
.node.needs-review .node-text {{ color: var(--node, #0d7377); }}
.node:hover, .node:focus-visible, .node.active {{
  transform: translate(-50%, -50%) scale(1.04); z-index: 3;
}}
.toolbar {{
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  margin: 0 0 10px; padding: 0;
}}
.toolbar button {{
  font: inherit; font-size: 12px; font-weight: 500; padding: 5px 10px;
  border-radius: 6px; border: 1px solid var(--line); background: transparent;
  color: var(--muted); cursor: pointer;
}}
.toolbar button.primary {{
  background: var(--ink); color: #fff; border-color: var(--ink);
}}
.toolbar button:disabled {{ opacity: 0.35; cursor: not-allowed; }}
.toolbar .save-status {{
  font-size: 11px; color: var(--muted); font-weight: 500; margin-left: 2px;
}}
.toolbar .save-status.ok {{ color: #2f6b4f; }}
.toolbar .save-status.err {{ color: #8a4040; }}
.toolbar .dirty[hidden], .toolbar .edit-only[hidden] {{ display: none !important; }}
.modal-backdrop {{
  display: none; position: fixed; inset: 0; z-index: 60;
  background: rgba(26,35,50,0.35); align-items: center; justify-content: center; padding: 20px;
}}
.modal-backdrop.show {{ display: flex; }}
.modal {{
  background: #fff; border-radius: 14px; padding: 18px 20px; width: min(420px, 100%);
  box-shadow: 0 20px 50px -24px rgba(0,0,0,0.45);
}}
.modal h3 {{ font-size: 16px; margin-bottom: 12px; }}
.modal label {{ display: block; font-size: 12px; color: var(--muted); margin: 10px 0 4px; }}
.modal select, .modal input {{
  width: 100%; font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--line);
}}
.modal .actions {{ display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }}
.node span {{ pointer-events: none; }}
.tip-panel {{
  display: none; position: fixed; z-index: 50;
  max-width: min(320px, calc(100vw - 24px));
  padding: 10px 12px; border-radius: 6px;
  background: var(--card); color: var(--ink);
  border: 1px solid var(--line);
  box-shadow: 0 4px 16px rgba(26, 35, 50, 0.08);
  font-size: 12px; line-height: 1.45; pointer-events: none;
}}
.tip-panel.show {{ display: block; }}
.tip-panel .tip-title {{ font-weight: 550; margin: 0 0 4px; font-size: 13px; }}
.tip-panel .tip-meta {{ color: var(--muted); margin: 0; font-size: 11px; }}
.tip-panel .tip-flag {{
  display: inline-block; margin-top: 6px; padding: 1px 6px;
  border-radius: 4px; background: var(--rail);
  color: var(--muted); font-size: 10px; font-weight: 500;
}}
.tip-accent {{
  width: 6px; height: 6px; border-radius: 50%; display: inline-block;
  margin-right: 5px; vertical-align: middle;
}}
.empty {{ padding: 24px 16px; color: var(--muted); font-size: 0.875rem; }}
footer {{ margin-top: 16px; font-size: 11px; color: var(--muted); }}
footer code {{ font-size: 10px; background: transparent; padding: 0; border-radius: 0; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="eyebrow">{eyebrow}{filter_note}</div>
    <h1>项目采购包关键节点汇总</h1>
    <div class="legend">
      <span><i class="swatch hollow"></i>待确认</span>
      <span><i class="swatch band spring"></i>春节停工</span>
      <span><i class="swatch band labor"></i>五一 / 国庆</span>
      <span><i class="anchor-swatch today"></i>今天</span>
    </div>
  </header>
  {insights_html}
  <div class="toolbar" id="edit-toolbar">
    <button type="button" id="btn-edit">编辑</button>
    <button type="button" class="primary edit-only" id="btn-save" hidden>保存全部修改</button>
    <button type="button" class="edit-only" id="btn-add" hidden>添加</button>
    <button type="button" class="edit-only" id="btn-del" hidden disabled>删除</button>
    <button type="button" class="edit-only" id="btn-done" hidden>完成</button>
    <span class="dirty" id="dirty-flag" hidden>未保存</span>
    <span class="save-status" id="save-status" hidden></span>
  </div>
  <div class="board" id="timeline-board" data-axis="{axis_meta}">{board_body}</div>
  <footer>
    {analyzed or "—"} · <code>{source_file or "—"}</code>
  </footer>
</div>
<div id="tip-panel" class="tip-panel" role="tooltip" hidden></div>
<div class="modal-backdrop" id="add-modal" hidden>
  <div class="modal" role="dialog" aria-labelledby="add-title">
    <h3 id="add-title">添加关键节点</h3>
    <label for="add-pkg">采购包</label>
    <select id="add-pkg"></select>
    <label for="add-code">节点类型</label>
    <select id="add-code">
      <option value="delivery">到货</option>
      <option value="site_access">进场</option>
      <option value="install_complete">安装完成</option>
      <option value="commissioning">调试</option>
      <option value="prelim_accept">初步验收</option>
      <option value="final_accept">最终验收</option>
      <option value="gc_milestone">总包里程碑</option>
      <option value="project_handover">移交/客户验收</option>
    </select>
    <label for="add-name">名称</label>
    <input id="add-name" type="text" placeholder="名称"/>
    <div class="actions">
      <button type="button" id="add-cancel">取消</button>
      <button type="button" class="primary" id="add-ok">添加</button>
    </div>
  </div>
</div>
<script type="application/json" id="schedule-data">{schedule_embed}</script>
<script type="application/json" id="node-axis-short">{axis_short_embed}</script>
<script>
(function () {{
  var NODE_SHORT = {{}};
  try {{
    NODE_SHORT = JSON.parse(document.getElementById("node-axis-short").textContent || "{{}}");
  }} catch (e) {{}}
  function axisLabel(code, name) {{
    if (NODE_SHORT[code]) return NODE_SHORT[code];
    var text = String(name || "").replace(/[\\sA-Za-z/].*$/, "").trim();
    if (!text) return "?";
    if (text.indexOf("隔墙") >= 0) return "隔墙";
    if (text.indexOf("吊顶") >= 0 || text.indexOf("天花") >= 0) return "吊顶";
    if (text.indexOf("许可") >= 0) return "许可";
    if (text.indexOf("客户") >= 0 && text.indexOf("验收") >= 0) return "验收";
    var suffixes = ["验收", "完成", "获得"];
    for (var si = 0; si < suffixes.length; si++) {{
      var suf = suffixes[si];
      if (text.slice(-suf.length) === suf && text.length > suf.length + 1) {{
        text = text.slice(0, -suf.length);
        break;
      }}
    }}
    if (text.length <= 4) return text;
    return text.slice(0, 3);
  }}
  var panel = document.getElementById("tip-panel");
  var pinned = null;
  var selected = null;
  var dirty = false;
  var dirtyHintShown = false;
  var dragging = null;
  var editing = false;
  var schedule = {{}};
  try {{
    schedule = JSON.parse(document.getElementById("schedule-data").textContent || "{{}}");
  }} catch (e) {{ schedule = {{ critical_nodes: [] }}; }}
  if (!Array.isArray(schedule.critical_nodes)) schedule.critical_nodes = [];

  var board = document.getElementById("timeline-board");
  var axis = {{ axis_start: null, total_days: 1, track_w: 800 }};
  try {{ axis = JSON.parse(board.getAttribute("data-axis") || "{{}}"); }} catch (e) {{}}

  function updateToolbarVisibility() {{
    var editBtn = document.getElementById("btn-edit");
    if (editBtn) editBtn.hidden = editing;
    document.querySelectorAll(".edit-only").forEach(function (el) {{
      // 有未保存修改时，「保存」始终可见，方便改完多个包再一次性保存
      if (el.id === "btn-save") {{
        el.hidden = !(editing || dirty);
        return;
      }}
      el.hidden = !editing;
    }});
  }}
  function setEditing(on) {{
    editing = !!on;
    document.body.classList.toggle("editing", editing);
    updateToolbarVisibility();
    if (!editing) {{
      selected = null;
      var del = document.getElementById("btn-del");
      if (del) del.disabled = true;
      hide(true);
    }}
  }}

  function escapeHtml(s) {{
    return String(s || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }}
  function decadeLabel(iso) {{
    var m = String(iso || "").match(/^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})/);
    if (!m) return iso || "";
    var day = parseInt(m[3], 10);
    var d = day <= 10 ? "上旬" : day <= 20 ? "中旬" : "下旬";
    return parseInt(m[1], 10) + "年" + parseInt(m[2], 10) + "月" + d;
  }}
  function setDirty(v) {{
    dirty = !!v;
    var dirtyEl = document.getElementById("dirty-flag");
    if (dirtyEl) {{
      dirtyEl.hidden = !dirty;
      if (dirty) dirtyEl.textContent = "有未保存的修改";
    }}
    updateToolbarVisibility();
    if (dirty && !dirtyHintShown) {{
      dirtyHintShown = true;
      setSaveStatus("可继续改其它包，全部改完再点一次「保存全部修改」", "ok");
      setTimeout(function () {{
        var st = document.getElementById("save-status");
        if (st && st.textContent.indexOf("全部改完") >= 0) setSaveStatus("", "");
      }}, 5000);
    }}
    if (!dirty) dirtyHintShown = false;
  }}
  function renderTip(data) {{
    if (!panel || !data) return;
    if (data.kind === "holiday") {{
      var accentH = data.color
        ? '<i class="tip-accent" style="background:' + escapeHtml(data.color) + '"></i>'
        : "";
      panel.innerHTML =
        '<div class="tip-title">' + accentH + escapeHtml(data.name || "停工/长假") + "</div>" +
        '<div class="tip-meta">' + escapeHtml(data.range || "") + "</div>";
      return;
    }}
    if (data.kind === "anchor") {{
      panel.innerHTML =
        '<div class="tip-title">' + escapeHtml(data.name || "锚点") + "</div>" +
        '<div class="tip-meta">' + escapeHtml(data.range || "") + "</div>";
      return;
    }}
    var accent = data.color
      ? '<i class="tip-accent" style="background:' + escapeHtml(data.color) + '"></i>'
      : "";
    var flag = (data.needs_review || data.needs_confirm)
      ? '<div class="tip-flag">待确认</div>' : "";
    var basisBits = "";
    if (data.basis_evidence) {{
      basisBits += '<div class="tip-meta"><strong>依据</strong> '
        + escapeHtml(data.basis_evidence) + "</div>";
    }}
    if (data.basis_how) {{
      basisBits += '<div class="tip-meta"><strong>定法</strong> '
        + escapeHtml(data.basis_how) + "</div>";
    }} else if (data.basis && !data.basis_evidence) {{
      basisBits += '<div class="tip-meta">' + escapeHtml(data.basis) + "</div>";
    }}
    panel.innerHTML =
      '<div class="tip-title">' + accent + escapeHtml(data.name || "节点") + "</div>" +
      '<div class="tip-meta">' + escapeHtml(data.package || "") +
      " · " + escapeHtml(data.decade || data.end || "") +
      (data.source ? " · " + escapeHtml(data.source) : "") +
      "</div>" + flag + basisBits;
  }}
  function placePanel(el) {{
    if (!panel) return;
    panel.hidden = false; panel.classList.add("show");
    var rect = el.getBoundingClientRect();
    var tw = panel.offsetWidth || 300, th = panel.offsetHeight || 120;
    var left = Math.max(12, Math.min(rect.left + rect.width / 2 - tw / 2, window.innerWidth - tw - 12));
    var top = rect.top - th - 10;
    if (top < 8) top = rect.bottom + 10;
    panel.style.left = left + "px"; panel.style.top = top + "px";
  }}
  function showHoliday(el) {{
    var raw = el.getAttribute("data-tip"); if (!raw) return;
    var data; try {{ data = JSON.parse(raw); }} catch (e) {{ return; }}
    renderTip(data); placePanel(el);
  }}
  function showFor(el, pin) {{
    var raw = el.getAttribute("data-tip"); if (!raw) return;
    var data; try {{ data = JSON.parse(raw); }} catch (e) {{ return; }}
    document.querySelectorAll(".node.active").forEach(function (d) {{ d.classList.remove("active"); }});
    el.classList.add("active"); selected = el;
    var del = document.getElementById("btn-del");
    if (del) del.disabled = !(editing);
    renderTip(data); placePanel(el);
    if (pin) pinned = el;
  }}
  function hide(force) {{
    if (pinned && !force) return;
    pinned = null;
    if (!force && selected) return;
    document.querySelectorAll(".node.active").forEach(function (d) {{ d.classList.remove("active"); }});
    if (force) {{ selected = null; var del = document.getElementById("btn-del"); if (del) del.disabled = true; }}
    if (!panel) return; panel.classList.remove("show"); panel.hidden = true;
  }}
  function parseIso(s) {{
    var m = String(s || "").match(/^(\\d{{4}})-(\\d{{2}})-(\\d{{2}})/);
    if (!m) return null;
    return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  }}
  function fmtIso(d) {{
    return d.getUTCFullYear() + "-" + String(d.getUTCMonth() + 1).padStart(2, "0") + "-" +
      String(d.getUTCDate()).padStart(2, "0");
  }}
  function xToDate(clientX, track) {{
    var rect = track.getBoundingClientRect();
    var x = Math.min(Math.max(clientX - rect.left, 0), rect.width);
    var start = parseIso(axis.axis_start);
    if (!start) return null;
    var days = Math.round((x / rect.width) * (axis.total_days || 1));
    var d = new Date(start.getTime());
    d.setUTCDate(d.getUTCDate() + days);
    return fmtIso(d);
  }}
  function updateNodeDom(el, iso) {{
    var tip; try {{ tip = JSON.parse(el.getAttribute("data-tip") || "{{}}"); }} catch (e) {{ return; }}
    tip.end = iso;
    tip.decade = decadeLabel(iso);
    tip.source = "手工调整";
    tip.needs_confirm = false;
    tip.needs_review = false;
    tip.basis = "PM 在时间线上调整为 " + iso;
    tip.basis_evidence = "";
    tip.basis_how = "PM 在时间线上调整为 " + iso;
    el.setAttribute("data-tip", JSON.stringify(tip));
    el.classList.add("manual");
    el.classList.remove("inferred");
    el.classList.remove("needs-review");
    var start = parseIso(axis.axis_start);
    var end = parseIso(iso);
    if (start && end) {{
      var left = ((end - start) / 86400000) / (axis.total_days || 1) * 100;
      left = Math.min(Math.max(left, 0.8), 99.2);
      el.style.left = left.toFixed(3) + "%";
    }}
    if (selected === el) renderTip(tip);
  }}
  function applyDateToSchedule(cnIndex, iso) {{
    var n = schedule.critical_nodes[cnIndex];
    if (!n) return;
    n.window_end = iso;
    if (!n.window_start || n.window_start > iso) n.window_start = iso;
    n.source = "manual";
    n.confidence = 1;
    n.needs_confirm = false;
    n.pm_confirmed = true;
    n.basis = "PM 在时间线上调整为 " + iso;
    setDirty(true);
    document.querySelectorAll(".att-item").forEach(function (li) {{
      if (li.getAttribute("data-package-name") === String(n.package_name || "") &&
          li.getAttribute("data-node-code") === String(n.node_code || "")) {{
        li.remove();
      }}
    }});
    updateAttCount();
  }}
  function refreshCnIndices() {{
    document.querySelectorAll(".node").forEach(function (el) {{
      var tip; try {{ tip = JSON.parse(el.getAttribute("data-tip") || "{{}}"); }} catch (e) {{ return; }}
      var found = -1;
      for (var i = 0; i < schedule.critical_nodes.length; i++) {{
        var n = schedule.critical_nodes[i];
        if (n.package_name === tip.package_name && n.node_code === tip.node_code &&
            (n.window_end === tip.end || n.name === tip.name_full || n.name_zh === tip.name)) {{
          found = i; break;
        }}
      }}
      el.setAttribute("data-cn-index", String(found));
      tip.cn_index = found;
      el.setAttribute("data-tip", JSON.stringify(tip));
    }});
    document.querySelectorAll(".att-item").forEach(function (li) {{
      var pkg = li.getAttribute("data-package-name") || "";
      var code = li.getAttribute("data-node-code") || "";
      var end = li.getAttribute("data-end") || "";
      var found = -1;
      for (var i = 0; i < schedule.critical_nodes.length; i++) {{
        var n = schedule.critical_nodes[i];
        if (String(n.package_name || "") === pkg && String(n.node_code || "") === code &&
            String(n.window_end || "").slice(0, 10) === end.slice(0, 10)) {{
          found = i; break;
        }}
      }}
      li.setAttribute("data-cn-index", String(found));
    }});
  }}
  function updateAttCount() {{
    var items = document.querySelectorAll(".att-item");
    var countEl = document.querySelector(".att-count");
    if (countEl) countEl.textContent = String(items.length);
    if (!items.length) {{
      var fold = document.querySelector(".attention-fold");
      if (fold) fold.remove();
    }}
  }}
  function removeAttItemForNode(cnIndex, pkg, code, end) {{
    var li = null;
    if (cnIndex >= 0) {{
      li = document.querySelector('.att-item[data-cn-index="' + cnIndex + '"]');
    }}
    if (!li && pkg) {{
      document.querySelectorAll(".att-item").forEach(function (el) {{
        if (el.getAttribute("data-package-name") === pkg &&
            el.getAttribute("data-node-code") === code &&
            el.getAttribute("data-end") === end) li = el;
      }});
    }}
    if (li) li.remove();
    updateAttCount();
  }}
  function findNodeElByIndex(cnIndex) {{
    return document.querySelector('.node[data-cn-index="' + cnIndex + '"]');
  }}
  function confirmReview(cnIndex) {{
    var n = schedule.critical_nodes[cnIndex];
    if (!n) return;
    n.pm_confirmed = true;
    n.needs_confirm = false;
    var el = findNodeElByIndex(cnIndex);
    if (el) {{
      el.classList.remove("needs-review");
      var tip; try {{ tip = JSON.parse(el.getAttribute("data-tip") || "{{}}"); }} catch (e) {{ tip = {{}}; }}
      tip.needs_review = false;
      tip.needs_confirm = false;
      el.setAttribute("data-tip", JSON.stringify(tip));
      if (selected === el) renderTip(tip);
    }}
    removeAttItemForNode(
      cnIndex,
      String(n.package_name || ""),
      String(n.node_code || ""),
      String(n.window_end || "").slice(0, 10)
    );
    setDirty(true);
  }}
  function editReview(cnIndex) {{
    setEditing(true);
    var el = findNodeElByIndex(cnIndex);
    if (!el) return;
    el.scrollIntoView({{ behavior: "smooth", block: "center", inline: "center" }});
    showFor(el, true);
  }}
  function deleteReview(cnIndex) {{
    if (cnIndex < 0 || !schedule.critical_nodes[cnIndex]) return;
    if (!confirm("删除该关键节点？")) return;
    var n = schedule.critical_nodes[cnIndex];
    var pkg = String(n.package_name || "");
    var code = String(n.node_code || "");
    var end = String(n.window_end || "").slice(0, 10);
    var el = findNodeElByIndex(cnIndex);
    schedule.critical_nodes.splice(cnIndex, 1);
    if (el) el.remove();
    if (selected === el) {{ selected = null; hide(true); }}
    removeAttItemForNode(cnIndex, pkg, code, end);
    refreshCnIndices();
    setDirty(true);
  }}
  document.querySelector(".insights") && document.querySelector(".insights").addEventListener("click", function (ev) {{
    var btn = ev.target.closest("[data-att-action]");
    if (!btn) return;
    ev.preventDefault();
    ev.stopPropagation();
    var li = btn.closest(".att-item");
    if (!li) return;
    var idx = parseInt(li.getAttribute("data-cn-index") || "-1", 10);
    var action = btn.getAttribute("data-att-action");
    if (action === "confirm") confirmReview(idx);
    else if (action === "edit") editReview(idx);
    else if (action === "delete") deleteReview(idx);
  }});
  function bindNode(el) {{
    el.addEventListener("mouseenter", function () {{
      if (dragging || (pinned && pinned !== el)) return;
      showFor(el, false);
    }});
    el.addEventListener("mouseleave", function () {{ if (!pinned && !dragging) hide(false); }});
    el.addEventListener("pointerdown", function (ev) {{
      if (!editing) {{
        showFor(el, true);
        return;
      }}
      if (ev.button !== 0) return;
      ev.preventDefault();
      ev.stopPropagation();
      showFor(el, true);
      dragging = {{
        el: el,
        track: el.parentElement,
        moved: false,
        startX: ev.clientX
      }};
      el.classList.add("dragging");
      el.setPointerCapture(ev.pointerId);
    }});
    el.addEventListener("pointermove", function (ev) {{
      if (!dragging || dragging.el !== el) return;
      if (Math.abs(ev.clientX - dragging.startX) > 3) dragging.moved = true;
      var iso = xToDate(ev.clientX, dragging.track);
      if (iso) updateNodeDom(el, iso);
    }});
    el.addEventListener("pointerup", function (ev) {{
      if (!dragging || dragging.el !== el) return;
      el.classList.remove("dragging");
      var iso = xToDate(ev.clientX, dragging.track);
      var idx = parseInt(el.getAttribute("data-cn-index") || "-1", 10);
      if (iso && dragging.moved && idx >= 0) {{
        updateNodeDom(el, iso);
        applyDateToSchedule(idx, iso);
      }}
      dragging = null;
      try {{ el.releasePointerCapture(ev.pointerId); }} catch (e) {{}}
    }});
  }}
  document.querySelectorAll(".node").forEach(bindNode);
  document.querySelectorAll(".holiday-band[data-tip]").forEach(function (el) {{
    el.addEventListener("mouseenter", function () {{
      if (dragging || pinned) return;
      showHoliday(el);
    }});
    el.addEventListener("mouseleave", function () {{
      if (pinned || dragging) return;
      if (selected && selected.classList && selected.classList.contains("node")) {{
        showFor(selected, false);
      }} else {{
        hide(true);
      }}
    }});
    el.addEventListener("click", function (ev) {{
      ev.stopPropagation();
      showHoliday(el);
    }});
  }});
  document.querySelectorAll(".anchor-mark[data-tip]").forEach(function (el) {{
    el.addEventListener("mouseenter", function () {{
      if (dragging || pinned) return;
      showHoliday(el);
    }});
    el.addEventListener("mouseleave", function () {{
      if (pinned || dragging) return;
      if (selected && selected.classList && selected.classList.contains("node")) {{
        showFor(selected, false);
      }} else {{
        hide(true);
      }}
    }});
  }});
  document.addEventListener("click", function () {{ if (!dragging) hide(true); }});

  document.getElementById("btn-edit").addEventListener("click", function () {{
    setEditing(true);
  }});
  document.getElementById("btn-done").addEventListener("click", function () {{
    if (dirty) {{
      var go = confirm(
        "有未保存的修改。\\n\\n要现在一次性保存吗？\\n（改了多个包也只需保存一次）"
      );
      setEditing(false);
      if (go) {{
        if (window.TIMELINE_LIVE_SAVE) saveToProject();
        else saveLocal();
      }} else {{
        setSaveStatus("修改还在本页，记得点「保存全部修改」再覆盖文件", "");
      }}
      return;
    }}
    setEditing(false);
  }});
  window.addEventListener("beforeunload", function (ev) {{
    if (!dirty) return;
    ev.preventDefault();
    ev.returnValue = "";
  }});
  function setSaveStatus(msg, kind) {{
    var el = document.getElementById("save-status");
    if (!el) return;
    if (!msg) {{ el.hidden = true; el.textContent = ""; el.className = "save-status"; return; }}
    el.hidden = false;
    el.textContent = msg;
    el.className = "save-status" + (kind ? " " + kind : "");
  }}
  function syncScheduleEmbed() {{
    var el = document.getElementById("schedule-data");
    if (el) el.textContent = JSON.stringify(schedule, null, 2);
  }}
  function triggerDownload(filename, text, mime) {{
    var blob = new Blob([text], {{ type: mime || "application/octet-stream" }});
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(function () {{ URL.revokeObjectURL(a.href); }}, 1500);
  }}
  function buildHtmlSnapshot() {{
    hide(true);
    setEditing(false);
    syncScheduleEmbed();
    var root = document.documentElement.cloneNode(true);
    root.querySelectorAll("script").forEach(function (s) {{
      if ((s.textContent || "").indexOf("TIMELINE_LIVE_SAVE") >= 0) s.remove();
    }});
    var dirtyEl = root.querySelector("#dirty-flag");
    if (dirtyEl) dirtyEl.setAttribute("hidden", "");
    var st = root.querySelector("#save-status");
    if (st) {{ st.setAttribute("hidden", ""); st.textContent = ""; }}
    return "<!DOCTYPE html>\\n" + root.outerHTML;
  }}
  function saveByDownload() {{
    var html = buildHtmlSnapshot();
    triggerDownload("关键节点时间线.html", html, "text/html;charset=utf-8");
    setTimeout(function () {{
      triggerDownload(
        "schedule.json",
        JSON.stringify(schedule, null, 2),
        "application/json"
      );
    }}, 400);
    setDirty(false);
    setSaveStatus(
      "已下载：用「关键节点时间线.html」覆盖原文件；把 schedule.json 放进项目 .skill 文件夹。下次直接双击 HTML 即可",
      "ok"
    );
  }}
  async function saveByFilePicker() {{
    if (!window.showSaveFilePicker) return false;
    try {{
      var htmlHandle = await window.showSaveFilePicker({{
        suggestedName: "关键节点时间线.html",
        types: [{{ description: "HTML", accept: {{ "text/html": [".html"] }} }}]
      }});
      var html = buildHtmlSnapshot();
      var w = await htmlHandle.createWritable();
      await w.write(html);
      await w.close();
      try {{
        var jsonHandle = await window.showSaveFilePicker({{
          suggestedName: "schedule.json",
          types: [{{ description: "JSON", accept: {{ "application/json": [".json"] }} }}]
        }});
        var w2 = await jsonHandle.createWritable();
        await w2.write(JSON.stringify(schedule, null, 2));
        await w2.close();
      }} catch (e2) {{
        triggerDownload(
          "schedule.json",
          JSON.stringify(schedule, null, 2),
          "application/json"
        );
      }}
      setDirty(false);
      setSaveStatus("已保存。下次打开该 HTML 就是现在这样", "ok");
      return true;
    }} catch (e) {{
      if (e && e.name === "AbortError") {{
        setSaveStatus("已取消保存", "");
        return true;
      }}
      return false;
    }}
  }}
  function saveLocal() {{
    setSaveStatus("正在保存…", "");
    saveByFilePicker().then(function (done) {{
      if (!done) saveByDownload();
    }});
  }}
  function saveToProject() {{
    setSaveStatus("正在保存…", "");
    fetch("/api/save", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(schedule)
    }}).then(function (r) {{
      return r.json().then(function (data) {{ return {{ ok: r.ok, data: data }}; }});
    }}).then(function (res) {{
      if (res.ok && res.data && res.data.ok) {{
        setDirty(false);
        setSaveStatus("已保存到项目，下次打开就是这样", "ok");
      }} else {{
        var err = (res.data && (res.data.error || res.data.hint)) || "保存失败";
        setSaveStatus(String(err), "err");
        saveLocal();
      }}
    }}).catch(function () {{
      saveLocal();
    }});
  }}
  document.getElementById("btn-save").addEventListener("click", function () {{
    if (window.TIMELINE_LIVE_SAVE) saveToProject();
    else saveLocal();
  }});

  document.getElementById("btn-del").addEventListener("click", function () {{
    if (!selected) return;
    var idx = parseInt(selected.getAttribute("data-cn-index") || "-1", 10);
    if (idx < 0) return;
    deleteReview(idx);
  }});

  var modal = document.getElementById("add-modal");
  function openAdd() {{
    var sel = document.getElementById("add-pkg");
    sel.innerHTML = "";
    var seen = {{}};
    document.querySelectorAll(".pkg-label[data-package-name]").forEach(function (el) {{
      var name = el.getAttribute("data-package-name");
      if (!name || seen[name]) return;
      seen[name] = true;
      var opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name + "（" + (el.getAttribute("data-package-type") || "") + "）";
      opt.dataset.type = el.getAttribute("data-package-type") || "";
      sel.appendChild(opt);
    }});
    modal.hidden = false; modal.classList.add("show");
  }}
  function closeAdd() {{ modal.classList.remove("show"); modal.hidden = true; }}
  document.getElementById("btn-add").addEventListener("click", openAdd);
  document.getElementById("add-cancel").addEventListener("click", closeAdd);
  document.getElementById("add-ok").addEventListener("click", function () {{
    var pkgSel = document.getElementById("add-pkg");
    var pkg = pkgSel.value;
    var ptype = pkgSel.options[pkgSel.selectedIndex]
      ? (pkgSel.options[pkgSel.selectedIndex].dataset.type || "")
      : "";
    var code = document.getElementById("add-code").value;
    var name = (document.getElementById("add-name").value || "").trim() || code;
    var mid = parseIso(axis.axis_start);
    if (mid) mid = new Date(mid.getTime() + Math.floor((axis.total_days || 1) / 2) * 86400000);
    var iso = mid ? fmtIso(mid) : (axis.axis_start || "");
    var node = {{
      node_code: code,
      name: name,
      name_zh: name,
      name_en: code,
      window_start: iso,
      window_end: iso,
      source: "manual",
      confidence: 1,
      basis: "PM 在时间线上新增",
      package_name: pkg,
      package_type: ptype || (pkg === "总包" ? "总包" : "供装"),
      risks: []
    }};
    schedule.critical_nodes.push(node);
    setDirty(true);
    closeAdd();
    var track = null;
    document.querySelectorAll(".track[data-package-name]").forEach(function (t) {{
      if (t.getAttribute("data-package-name") === pkg) track = t;
    }});
    if (track) {{
      var idx = schedule.critical_nodes.length - 1;
      var color = getComputedStyle(document.documentElement).getPropertyValue("--ink") || "#1e4d8c";
      var existing = track.querySelector(".node");
      if (existing) color = getComputedStyle(existing).getPropertyValue("--node") || color;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "node manual";
      btn.style.setProperty("--node", color.trim() || "#1e4d8c");
      var start = parseIso(axis.axis_start);
      var end = parseIso(iso);
      var left = 50;
      if (start && end) left = Math.min(Math.max(((end - start) / 86400000) / (axis.total_days || 1) * 100, 0.8), 99.2);
      btn.style.left = left.toFixed(3) + "%";
      var axLabel = axisLabel(code, name);
      var tip = {{
        ordinal: track.querySelectorAll(".node").length + 1,
        package: pkg,
        package_name: pkg,
        package_type: ptype,
        name: name,
        name_full: name,
        axis_label: axLabel,
        node_code: code,
        decade: decadeLabel(iso),
        end: iso,
        source: "手工调整",
        needs_confirm: false,
        basis: "PM 在时间线上新增",
        color: color.trim() || "#1e4d8c",
        cn_index: idx
      }};
      btn.setAttribute("data-tip", JSON.stringify(tip));
      btn.setAttribute("data-cn-index", String(idx));
      btn.setAttribute("data-package", pkg);
      btn.innerHTML = '<span class="node-text">' + escapeHtml(axLabel) + "</span>";
      track.appendChild(btn);
      bindNode(btn);
      showFor(btn, true);
    }}
  }});
}})();
</script>
</body>
</html>
"""


def default_timeline_paths(project_root: Path) -> tuple[Path, Path]:
    root = project_root.expanduser().resolve()
    human = root / "项目档案" / "00_进度计划" / "关键节点时间线.html"
    skill = root / ".skill" / "critical_nodes_timeline.html"
    return human, skill


def write_timeline(
    project_root: Path,
    *,
    schedule_path: Path | None = None,
    package_filter: str | None = None,
    package_dir: Path | None = None,
    project_name: str = "",
    highlight_package: str | None = None,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    sched_path = schedule_path or (root / ".skill" / "schedule.json")
    schedule = load_json(sched_path)
    if not project_name:
        proj = load_json(root / ".skill" / "project.json")
        project_name = str(proj.get("project_name") or root.name)

    html_text = render_timeline_html(
        schedule,
        project_name=project_name,
        package_filter=package_filter,
        highlight_package=highlight_package or package_filter,
    )

    written: list[str] = []
    human, skill = default_timeline_paths(root)
    # Full project timeline always when no package filter
    if not package_filter:
        for path in (human, skill):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html_text, encoding="utf-8")
            written.append(str(path))
    else:
        # Filtered view for one package
        if package_dir is None:
            package_dir = root
        out = Path(package_dir).expanduser().resolve() / "关键节点时间线.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_text, encoding="utf-8")
        written.append(str(out))

    return {
        "schedule_json": str(sched_path),
        "written": written,
        "package_filter": package_filter,
        "node_count": len(schedule.get("critical_nodes") or []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render critical_nodes timeline HTML from .skill/schedule.json"
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--schedule-json", default=None)
    parser.add_argument(
        "--package",
        default=None,
        help="Only include this package (+ project-level); write into --package-dir",
    )
    parser.add_argument(
        "--package-dir",
        default=None,
        help="Output dir for filtered timeline (default: project root)",
    )
    parser.add_argument("--project-name", default="")
    args = parser.parse_args(argv)

    try:
        result = write_timeline(
            Path(args.project_root),
            schedule_path=Path(args.schedule_json) if args.schedule_json else None,
            package_filter=args.package,
            package_dir=Path(args.package_dir) if args.package_dir else None,
            project_name=args.project_name,
            highlight_package=args.package,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
