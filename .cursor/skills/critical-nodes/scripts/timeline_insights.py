"""Derive project-control insights for critical-nodes timeline HTML.

Inputs (from schedule.json):
  - critical_nodes[], pending[], packages[], milestones[] (optional)

No external API; all rules are documented inline for Skill presentation.md.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

NODE_LABELS: dict[str, str] = {
    "delivery": "到货",
    "site_access": "进场",
    "install_complete": "安装完成",
    "commissioning": "调试",
    "prelim_accept": "初步验收",
    "final_accept": "最终验收",
    "project_handover": "客户验收",
    "gc_milestone": "总包里程碑",
    "concept": "方案",
    "detail_deliverable": "成果交付",
    "deliverable_accept": "成果验收",
    "po_confirm": "下单确认",
}

# MVP 默认必推（node-taxonomy.md）
REQUIRED_BY_TYPE: dict[str, list[str]] = {
    "供应": ["delivery"],
    "供装": [
        "delivery",
        "site_access",
        "install_complete",
        "prelim_accept",
        "final_accept",
    ],
    "顾问": ["concept", "detail_deliverable", "deliverable_accept"],
    "总包": [],
}

_GC_PKG = frozenset({"总包", "GC", "gc"})
_HANDOVER_CODES = frozenset({"project_handover", "project_completion"})
_HANDOVER_RE = re.compile(
    r"客户验收|client\s*final\s*acceptance|final\s*acceptance|handover|移交",
    re.I,
)


def parse_iso_date(value: str) -> date | None:
    raw = (value or "").strip()[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _critical_list(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = schedule.get("critical_nodes")
    return nodes if isinstance(nodes, list) else []


def _packages_list(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    pkgs = schedule.get("packages")
    if isinstance(pkgs, list) and pkgs:
        return [p for p in pkgs if isinstance(p, dict)]
    # fallback: infer from critical_nodes
    seen: dict[str, str] = {}
    for n in _critical_list(schedule):
        pname = str(n.get("package_name") or "").strip()
        if not pname or pname == "_project":
            continue
        ptype = str(n.get("package_type") or "").strip()
        if pname not in seen:
            seen[pname] = ptype
    return [{"package_name": k, "package_type": v} for k, v in sorted(seen.items())]


def find_client_handover_date(schedule: dict[str, Any]) -> tuple[date | None, str]:
    """客户验收锚点：优先总包 project_handover，其次 milestones 关键词。"""
    critical = _critical_list(schedule)

    def _is_gc(n: dict[str, Any]) -> bool:
        pname = str(n.get("package_name") or "")
        ptype = str(n.get("package_type") or "")
        return pname in _GC_PKG or ptype == "总包"

    # 1) 总包 project_handover
    for n in critical:
        if not _is_gc(n):
            continue
        if str(n.get("node_code") or "") != "project_handover":
            continue
        d = parse_iso_date(str(n.get("window_end") or ""))
        if d:
            return d, "critical_nodes"

    # 2) 总包 gc_milestone + 验收语义
    for n in critical:
        if not _is_gc(n):
            continue
        if str(n.get("node_code") or "") != "gc_milestone":
            continue
        hay = " ".join(str(n.get(k) or "") for k in ("name", "name_zh", "basis"))
        if not _HANDOVER_RE.search(hay):
            continue
        d = parse_iso_date(str(n.get("window_end") or ""))
        if d:
            return d, "critical_nodes"

    # 3) milestones
    milestones = schedule.get("milestones")
    if isinstance(milestones, list):
        for m in milestones:
            if not isinstance(m, dict):
                continue
            name = str(m.get("name") or "")
            if not _HANDOVER_RE.search(name):
                continue
            d = parse_iso_date(str(m.get("date") or m.get("end_date") or ""))
            if d:
                return d, "milestones"
    return None, ""


def project_anchor_marks(
    schedule: dict[str, Any],
    *,
    axis_start: date,
    axis_end: date,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Vertical markers: today only（客户验收已在各包节点上，不再画总竖线）。"""
    ref = today or date.today()
    out: list[dict[str, Any]] = []

    if axis_start <= ref <= axis_end:
        out.append(
            {
                "kind": "today",
                "date": ref.isoformat(),
                "label": "今天",
                "source": "system",
            }
        )
    return out


def upcoming_critical_nodes(
    schedule: dict[str, Any],
    *,
    days: int = 30,
    from_date: date | None = None,
) -> list[dict[str, Any]]:
    """Nodes with window_end in [today, today+days]."""
    start = from_date or date.today()
    end = start + timedelta(days=days)
    items: list[dict[str, Any]] = []
    for n in _critical_list(schedule):
        d = parse_iso_date(str(n.get("window_end") or ""))
        if not d or d < start or d > end:
            continue
        pname = str(n.get("package_name") or "")
        if pname == "_project":
            continue
        code = str(n.get("node_code") or "")
        name = str(n.get("name_zh") or n.get("name") or code)
        items.append(
            {
                "package_name": pname,
                "package_type": str(n.get("package_type") or ""),
                "node_code": code,
                "name": name,
                "window_end": d.isoformat(),
                "source": str(n.get("source") or ""),
                "needs_confirm": bool(n.get("needs_confirm")),
            }
        )
    items.sort(key=lambda x: (x["window_end"], x["package_name"], x["node_code"]))
    return items


def _nodes_by_package(critical: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for n in critical:
        pname = str(n.get("package_name") or "").strip()
        if not pname or pname == "_project":
            continue
        out.setdefault(pname, []).append(n)
    return out


def parse_basis(basis: str) -> dict[str, str]:
    """Split basis into 依据 / 定法. Accepts `依据：…｜定法：…` or plain text."""
    text = (basis or "").strip()
    if not text:
        return {"evidence": "", "how": ""}
    evidence = ""
    how = ""
    # Prefer explicit markers
    if "｜" in text or "|" in text:
        parts = re.split(r"\s*[｜|]\s*", text)
        for part in parts:
            p = part.strip()
            if p.startswith("依据：") or p.startswith("依据:"):
                evidence = re.sub(r"^依据[:：]\s*", "", p).strip()
            elif p.startswith("定法：") or p.startswith("定法:"):
                how = re.sub(r"^定法[:：]\s*", "", p).strip()
            elif not evidence and not how:
                # bare first segment → treat as evidence if second looks like 定法
                pass
        if len(parts) == 2 and not evidence and not how:
            a, b = parts[0].strip(), parts[1].strip()
            if a.startswith("依据") or b.startswith("定法"):
                evidence = re.sub(r"^依据[:：]\s*", "", a).strip()
                how = re.sub(r"^定法[:：]\s*", "", b).strip()
            else:
                evidence, how = a, b
    if not evidence and not how:
        m_ev = re.search(r"依据[:：]\s*(.+?)(?=定法[:：]|$)", text, re.S)
        m_how = re.search(r"定法[:：]\s*(.+)$", text, re.S)
        if m_ev:
            evidence = m_ev.group(1).strip().rstrip("｜|；; ").strip()
        if m_how:
            how = m_how.group(1).strip()
    if not evidence and not how:
        # Legacy free text → show entirely under 定法 so PM still sees it
        how = text
    return {"evidence": evidence, "how": how}


def node_needs_review(n: dict[str, Any]) -> bool:
    """Whether this node should appear in 待确认 and render as hollow."""
    if n.get("pm_confirmed"):
        return False
    if n.get("needs_confirm"):
        return True
    source = str(n.get("source") or "")
    return source in {"inferred", "aligned"}


def _node_review_row(n: dict[str, Any], *, cn_index: int = -1) -> dict[str, Any]:
    code = str(n.get("node_code") or "")
    name = str(n.get("name_zh") or n.get("name") or NODE_LABELS.get(code, code))
    risks = n.get("risks")
    risk_text = ""
    if isinstance(risks, list):
        risk_text = "；".join(str(r).strip() for r in risks if str(r).strip())
    parsed = parse_basis(str(n.get("basis") or ""))
    return {
        "package_name": str(n.get("package_name") or ""),
        "name": name,
        "node_code": code,
        "source": str(n.get("source") or ""),
        "window_end": str(n.get("window_end") or "")[:10],
        "basis": str(n.get("basis") or "").strip(),
        "basis_evidence": parsed["evidence"],
        "basis_how": parsed["how"],
        "risks": risk_text,
        "needs_confirm": bool(n.get("needs_confirm")),
        "cn_index": cn_index,
    }


def coverage_and_attention(schedule: dict[str, Any]) -> dict[str, Any]:
    """倒推/对齐且尚未 PM 确认的节点 + pending。"""
    critical = _critical_list(schedule)

    pending_rows: list[dict[str, str]] = []
    raw_pending = schedule.get("pending")
    if isinstance(raw_pending, list):
        for p in raw_pending:
            if isinstance(p, dict):
                msg = str(p.get("message") or p.get("reason") or "").strip()
                if not msg:
                    continue
                pending_rows.append(
                    {
                        "kind": "pending",
                        "package_name": str(p.get("package_name") or ""),
                        "message": msg,
                    }
                )
            elif isinstance(p, str) and p.strip():
                pending_rows.append(
                    {"kind": "pending", "package_name": "", "message": p.strip()}
                )

    reviews: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for ci, n in enumerate(critical):
        if not isinstance(n, dict):
            continue
        if str(n.get("package_name") or "") == "_project":
            continue
        if not node_needs_review(n):
            continue
        row = _node_review_row(n, cn_index=ci)
        key = (row["package_name"], row["node_code"], row["window_end"])
        if key in seen:
            continue
        seen.add(key)
        reviews.append(row)

    reviews.sort(
        key=lambda r: (
            r.get("window_end") or "",
            r.get("package_name") or "",
            r.get("node_code") or "",
        )
    )

    return {
        "pending": pending_rows,
        "reviews": reviews,
        "gaps": [],
        "has_attention": bool(pending_rows or reviews),
    }


def timeline_kpis(
    schedule: dict[str, Any],
    *,
    upcoming: list[dict[str, Any]] | None = None,
    attention: dict[str, Any] | None = None,
) -> dict[str, int]:
    critical = _critical_list(schedule)
    packages = _packages_list(schedule)
    up = upcoming if upcoming is not None else upcoming_critical_nodes(schedule)
    att = attention if attention is not None else coverage_and_attention(schedule)
    return {
        "packages": len([p for p in packages if str(p.get("package_name") or "") != "_project"]),
        "nodes": len([n for n in critical if str(n.get("package_name") or "") != "_project"]),
        "upcoming_30d": len(up),
        "attention": len(att.get("pending") or []) + len(att.get("reviews") or []),
    }
