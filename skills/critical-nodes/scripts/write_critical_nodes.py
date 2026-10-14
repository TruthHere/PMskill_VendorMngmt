#!/usr/bin/env python3
"""Validate Agent-produced critical_nodes and write .skill/schedule.json.

Primary path for critical-nodes (agent-led). Does not invent nodes
from keyword dictionaries — that is the agent's job.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Reuse parsers / labels from analyze_schedule (milestones only; no inference).
from analyze_schedule import (  # noqa: E402
    NODE_LABELS,
    NODE_ORDER,
    _decade_label,
    _display_name,
    load_json,
    load_packages_from_tracker,
    load_packages_json,
    find_tracker,
    milestones_for_skill1,
    parse_schedule_file,
    render_markdown,
    resolve_schedule_source,
    save_json,
    _render_timeline_files,
)

REQUIRED_NODE_FIELDS = (
    "node_code",
    "name",
    "window_start",
    "window_end",
    "source",
    "confidence",
    "basis",
    "package_name",
    "package_type",
)

VALID_SOURCES = {"explicit", "inferred", "aligned", "manual"}
VALID_PACKAGE_TYPES = {"供应", "供装", "顾问", "总包"}
KNOWN_CODES = set(NODE_LABELS.keys())
GC_PACKAGE_NAMES = frozenset({"总包", "GC", "gc"})
LEGACY_PROJECT_NAMES = frozenset({"_project"})


def _is_gc_package(name: str) -> bool:
    return str(name or "").strip() in GC_PACKAGE_NAMES | LEGACY_PROJECT_NAMES


def scrub_stale_init_pending(
    pending: list[Any],
    *,
    packages: list[dict[str, str]],
) -> list[Any]:
    """Drop init-era pending once Tracker/packages already have real packages."""
    real = [
        p
        for p in packages
        if isinstance(p, dict)
        and str(p.get("package_name") or "").strip()
        and not _is_gc_package(str(p.get("package_name") or ""))
    ]
    if not real:
        return list(pending) if isinstance(pending, list) else []

    out: list[Any] = []
    for item in pending or []:
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
            msg = str(item.get("message") or item.get("reason") or "")
            if code == "missing_anchor":
                continue
            if "尚无采购包" in msg or "尚无采购包清单" in msg:
                continue
            out.append(item)
        elif isinstance(item, str):
            if "尚无采购包" in item:
                continue
            out.append(item)
        else:
            out.append(item)
    return out


def merge_critical_nodes(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    merge_packages: list[str],
) -> list[dict[str, Any]]:
    """Keep nodes outside merge_packages; replace those packages from incoming.

    Preserves 总包 / legacy `_project` unless merge_packages explicitly names them.
    """
    targets = {str(p).strip() for p in merge_packages if str(p).strip()}
    if not targets:
        return list(incoming)

    # Treat 总包 and _project as the same merge target bucket when either is named
    if targets & (GC_PACKAGE_NAMES | LEGACY_PROJECT_NAMES):
        targets |= GC_PACKAGE_NAMES | LEGACY_PROJECT_NAMES

    rewrite_gc = bool(targets & (GC_PACKAGE_NAMES | LEGACY_PROJECT_NAMES))

    kept: list[dict[str, Any]] = []
    for n in existing:
        pname = str(n.get("package_name") or "").strip()
        if not rewrite_gc and _is_gc_package(pname):
            kept.append(n)
            continue
        if pname not in targets:
            kept.append(n)

    added = [
        n for n in incoming if str(n.get("package_name") or "").strip() in targets
    ]
    return kept + added


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _is_ymd(value: Any) -> bool:
    text = str(value or "").strip()
    if len(text) < 10:
        return False
    try:
        datetime.strptime(text[:10], "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _load_nodes_payload(path: Path | None, raw: str | None) -> dict[str, Any]:
    if path is not None:
        data = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    elif raw is not None:
        data = json.loads(raw)
    else:
        raise ValueError("Provide --nodes-json or --nodes-json-text")

    if isinstance(data, list):
        return {"critical_nodes": data}
    if isinstance(data, dict):
        return data
    raise ValueError("nodes JSON must be an array or an object")


def normalize_node(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fill display names; return (node, field errors)."""
    errors: list[str] = []
    node = dict(raw)
    code = str(node.get("node_code") or "").strip()
    if not code:
        errors.append("missing node_code")
    elif code not in KNOWN_CODES:
        errors.append(f"unknown node_code: {code}")

    if code and code in NODE_LABELS:
        zh, en = NODE_LABELS[code]
        node.setdefault("name_zh", zh)
        node.setdefault("name_en", en)
        if not str(node.get("name") or "").strip():
            node["name"] = _display_name(code)

    # 新写入禁止 package_name=_project → 归一成「总包」
    pname = str(node.get("package_name") or "").strip()
    ptype = str(node.get("package_type") or "").strip()
    if pname == "_project" or ptype == "_project":
        node["package_name"] = "总包"
        node["package_type"] = "总包"
        pname = "总包"
        ptype = "总包"

    for field in REQUIRED_NODE_FIELDS:
        if field == "name" and str(node.get("name") or "").strip():
            continue
        if node.get(field) in (None, ""):
            errors.append(f"missing {field}")

    source = str(node.get("source") or "").strip()
    if source and source not in VALID_SOURCES:
        errors.append(f"invalid source: {source}")

    ptype = str(node.get("package_type") or "").strip()
    if ptype and ptype not in VALID_PACKAGE_TYPES:
        errors.append(f"invalid package_type: {ptype}")

    for dkey in ("window_start", "window_end"):
        if node.get(dkey) and not _is_ymd(node.get(dkey)):
            errors.append(f"bad date {dkey}={node.get(dkey)!r}")

    try:
        conf = float(node.get("confidence"))
        node["confidence"] = round(conf, 2)
        if conf < 0 or conf > 1:
            errors.append(f"confidence out of range: {conf}")
    except (TypeError, ValueError):
        errors.append(f"bad confidence: {node.get('confidence')!r}")

    if not isinstance(node.get("risks", []), list):
        errors.append("risks must be a list")
    node.setdefault("risks", [])

    return node, errors


def annotate_order_risks(nodes: list[dict[str, Any]]) -> None:
    """Soft checks on window_end order (completion-point semantics)."""
    by_pkg: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        by_pkg.setdefault(str(n.get("package_name") or ""), []).append(n)

    handover_end = ""
    for gkey in ("总包", "_project", "GC", "gc"):
        for n in by_pkg.get(gkey, []):
            if n.get("node_code") in {"project_handover", "project_completion"}:
                end = str(n.get("window_end") or "")
                if end and (not handover_end or end > handover_end):
                    if n.get("node_code") == "project_handover":
                        handover_end = end
                    elif not handover_end:
                        handover_end = end
        for n in by_pkg.get(gkey, []):
            if n.get("node_code") == "project_handover":
                handover_end = str(n.get("window_end") or handover_end)
                break

    for pname, group in by_pkg.items():
        if _is_gc_package(pname):
            continue
        ordered = sorted(
            group, key=lambda n: NODE_ORDER.get(str(n.get("node_code")), 999)
        )
        for i in range(1, len(ordered)):
            prev, cur = ordered[i - 1], ordered[i]
            # gc_milestone 是总包事件锚点，不与 taxonomy 顺序强绑
            if prev.get("node_code") == "gc_milestone" or cur.get("node_code") == "gc_milestone":
                continue
            pe = str(prev.get("window_end") or "")
            ce = str(cur.get("window_end") or "")
            if pe and ce and ce < pe:
                msg = (
                    f"完成日顺序冲突：{cur.get('node_code')} {ce} "
                    f"早于 {prev.get('node_code')} {pe}"
                )
                risks = list(cur.get("risks") or [])
                if msg not in risks:
                    risks.append(msg)
                cur["risks"] = risks

        delivery = next((n for n in group if n.get("node_code") == "delivery"), None)
        install = next(
            (n for n in group if n.get("node_code") == "install_complete"), None
        )
        if (
            delivery
            and install
            and str(delivery.get("window_end") or "")
            > str(install.get("window_end") or "")
        ):
            msg = (
                f"到货完成晚于安装完成："
                f"delivery {delivery.get('window_end')} > "
                f"install_complete {install.get('window_end')}"
            )
            risks = list(delivery.get("risks") or [])
            if msg not in risks:
                risks.append(msg)
            delivery["risks"] = risks

        if handover_end:
            for n in group:
                if n.get("node_code") in {
                    "final_accept",
                    "prelim_accept",
                    "deliverable_accept",
                } and str(n.get("window_end") or "") > handover_end:
                    msg = (
                        f"验收完成晚于项目移交/竣工："
                        f"{n.get('node_code')} {n.get('window_end')} > {handover_end}"
                    )
                    risks = list(n.get("risks") or [])
                    if msg not in risks:
                        risks.append(msg)
                    n["risks"] = risks


def validate_nodes(
    nodes: list[Any], *, strict: bool = True
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(nodes, list):
        return [], ["critical_nodes must be a list"]
    out: list[dict[str, Any]] = []
    errors: list[str] = []
    for i, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            errors.append(f"critical_nodes[{i}] not an object")
            continue
        node, errs = normalize_node(raw)
        for e in errs:
            errors.append(f"critical_nodes[{i}] ({raw.get('node_code')}): {e}")
        out.append(node)
    annotate_order_risks(out)
    out.sort(
        key=lambda n: (
            not _is_gc_package(str(n.get("package_name") or "")),
            str(n.get("package_name") or ""),
            NODE_ORDER.get(str(n.get("node_code")), 999),
            str(n.get("window_start") or ""),
        )
    )
    if strict and errors:
        return out, errors
    return out, errors


def run(
    project_root: Path,
    payload: dict[str, Any],
    *,
    source: Path | None = None,
    packages: list[dict[str, str]] | None = None,
    write_md: bool = False,
    write_timeline: bool = False,
    timeline_package: str | None = None,
    timeline_package_dir: Path | None = None,
    merge_packages: list[str] | None = None,
    validate_only: bool = False,
    strict: bool = True,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    raw_nodes = payload.get("critical_nodes")
    if raw_nodes is None:
        raise ValueError("payload missing critical_nodes")

    nodes, errors = validate_nodes(raw_nodes, strict=False)
    if strict and errors:
        return {
            "ok": False,
            "errors": errors,
            "critical_node_count": len(nodes),
        }

    pending = payload.get("pending")
    if pending is None:
        pending = []
    if not isinstance(pending, list):
        raise ValueError("pending must be a list")

    pkg_list = packages
    if pkg_list is None and isinstance(payload.get("packages"), list):
        pkg_list = [
            {
                "package_name": str(p.get("package_name") or p.get("name") or ""),
                "package_type": str(p.get("package_type") or p.get("type") or "供应"),
            }
            for p in payload["packages"]
            if isinstance(p, dict) and (p.get("package_name") or p.get("name"))
        ]
    if pkg_list is None:
        pkg_list = []

    milestones_raw: list[dict[str, str]] | None = None
    source_rel = payload.get("source_file")
    if source is not None or (source_rel and not payload.get("milestones")):
        try:
            src = resolve_schedule_source(
                root, Path(source) if source else Path(str(source_rel))
            )
            milestones_raw = parse_schedule_file(src)
            if src.is_relative_to(root):
                source_rel = str(src.relative_to(root))
            else:
                source_rel = str(src)
        except (OSError, ValueError) as exc:
            if source is not None:
                raise
            # keep existing milestones if optional source_file stale
            source_rel = source_rel or ""
            milestones_raw = None
            pending = list(pending) + [
                {
                    "code": "source_unreadable",
                    "message": f"未能刷新 milestones：{exc}",
                }
            ]
    elif isinstance(payload.get("milestones"), list):
        milestones_raw = None  # use payload milestones as-is below

    if validate_only:
        return {
            "ok": True,
            "errors": errors,
            "warnings": errors,
            "critical_node_count": len(nodes),
            "pending_count": len(pending),
            "inferred_count": sum(1 for n in nodes if n.get("source") == "inferred"),
            "explicit_count": sum(1 for n in nodes if n.get("source") == "explicit"),
            "sample_decades": [
                {
                    "package_name": n.get("package_name"),
                    "node_code": n.get("node_code"),
                    "window_end": n.get("window_end"),
                    "decade": _decade_label(str(n.get("window_end") or "")),
                }
                for n in nodes[:5]
            ],
        }

    skill_dir = root / ".skill"
    schedule_path = skill_dir / "schedule.json"
    existing = load_json(schedule_path)
    doc: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}

    if milestones_raw is not None:
        doc["milestones"] = milestones_for_skill1(milestones_raw)
    elif isinstance(payload.get("milestones"), list):
        doc["milestones"] = payload["milestones"]
    # else keep existing milestones

    existing_nodes = [
        n for n in (doc.get("critical_nodes") or []) if isinstance(n, dict)
    ]
    merge_list = [str(p).strip() for p in (merge_packages or []) if str(p).strip()]
    if merge_list:
        nodes = merge_critical_nodes(existing_nodes, nodes, merge_packages=merge_list)
        nodes, merge_errs = validate_nodes(nodes, strict=False)
        errors = list(errors) + merge_errs
        if strict and merge_errs:
            return {
                "ok": False,
                "errors": errors,
                "critical_node_count": len(nodes),
                "merge_packages": merge_list,
            }

    # Prefer Tracker/pkg_list; else keep existing packages snapshot for scrub
    packages_for_scrub = pkg_list or [
        p
        for p in (doc.get("packages") or [])
        if isinstance(p, dict)
    ]
    if not packages_for_scrub:
        # Infer from nodes already on disk + incoming
        names = {
            str(n.get("package_name") or "").strip()
            for n in (existing_nodes + nodes)
            if str(n.get("package_name") or "").strip()
        }
        packages_for_scrub = [
            {"package_name": n, "package_type": "供装"}
            for n in sorted(names)
            if n and not _is_gc_package(n)
        ]

    # Merge pending with existing when doing package merge (don't wipe other pending)
    if merge_list and payload.get("pending") is None:
        pending = list(doc.get("pending") or [])
    elif merge_list and isinstance(payload.get("pending"), list):
        # Keep existing pending not about target packages, plus incoming
        keep_pending: list[Any] = []
        for item in doc.get("pending") or []:
            if isinstance(item, dict):
                ctx_pkg = str(
                    (item.get("context") or {}).get("package_name")
                    if isinstance(item.get("context"), dict)
                    else item.get("package_name")
                    or ""
                ).strip()
                if ctx_pkg and ctx_pkg in merge_list:
                    continue
            keep_pending.append(item)
        pending = keep_pending + list(pending)

    pending = scrub_stale_init_pending(pending, packages=packages_for_scrub)

    doc["critical_nodes"] = nodes
    doc["pending"] = pending  # 进度自己的 pending，留在 schedule.json；禁止写入项目 pending.json
    if pkg_list:
        # Merge package list snapshot
        by_name = {
            str(p.get("package_name") or ""): p
            for p in (doc.get("packages") or [])
            if isinstance(p, dict) and p.get("package_name")
        }
        for p in pkg_list:
            by_name[str(p.get("package_name") or "")] = p
        doc["packages"] = list(by_name.values())
    if source_rel:
        doc["source_file"] = source_rel
    doc["analyzed_at"] = now_iso()
    doc["note"] = "critical_nodes from critical-nodes (agent-led)"
    doc["analysis_mode"] = "agent"
    if merge_list:
        doc["last_merge_packages"] = merge_list
    save_json(schedule_path, doc)

    md_path = None
    if write_md:
        md_path = skill_dir / "critical_nodes.md"
        md_path.write_text(
            render_markdown(
                analyzed_at=doc["analyzed_at"],
                source_file=str(doc.get("source_file") or ""),
                critical=nodes,
                pending=pending,
            ),
            encoding="utf-8",
        )

    timeline_info = None
    if write_timeline:
        timeline_info = _render_timeline_files(
            root,
            package_name=timeline_package or (merge_list[0] if merge_list else None),
            package_dir=timeline_package_dir,  # ignored by renderer
        )

    return {
        "ok": True,
        "errors": errors,
        "project_root": str(root),
        "schedule_json": str(schedule_path),
        "critical_nodes_md": str(md_path) if md_path else None,
        "timeline": timeline_info,
        "critical_node_count": len(nodes),
        "pending_count": len(pending),
        "inferred_count": sum(1 for n in nodes if n.get("source") == "inferred"),
        "explicit_count": sum(1 for n in nodes if n.get("source") == "explicit"),
        "analysis_mode": "agent",
        "merge_packages": merge_list or None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate + write agent-produced critical_nodes → schedule.json"
    )
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--nodes-json",
        default=None,
        help="Path to JSON (array of nodes, or object with critical_nodes)",
    )
    parser.add_argument(
        "--nodes-json-text",
        default=None,
        help="Inline JSON string (same shapes as --nodes-json)",
    )
    parser.add_argument("--source", default=None, help="csv/xlsx to refresh milestones")
    parser.add_argument("--packages-json", default=None)
    parser.add_argument("--tracker", default=None)
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--write-timeline", action="store_true")
    parser.add_argument(
        "--timeline-package",
        default=None,
        help="Highlight this package on the project timeline (does not write package-dir HTML)",
    )
    parser.add_argument(
        "--timeline-package-dir",
        default=None,
        help="Deprecated/ignored: per-package timeline HTML is forbidden",
    )
    parser.add_argument(
        "--merge-package",
        action="append",
        default=None,
        dest="merge_packages",
        help=(
            "Merge mode: keep existing nodes for other packages (always keep 总包 unless "
            "listed here); only replace/append nodes for this package. Repeatable."
        ),
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate only; do not write schedule.json",
    )
    parser.add_argument(
        "--allow-invalid",
        action="store_true",
        help="Write even if field errors exist (still reported)",
    )
    args = parser.parse_args(argv)

    if not args.nodes_json and not args.nodes_json_text:
        print("ERROR: need --nodes-json or --nodes-json-text", file=sys.stderr)
        return 2

    try:
        payload = _load_nodes_payload(
            Path(args.nodes_json) if args.nodes_json else None,
            args.nodes_json_text,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    root = Path(args.project_root).expanduser().resolve()
    packages: list[dict[str, str]] | None = None
    if args.packages_json:
        packages = load_packages_json(args.packages_json)
    else:
        tracker = (
            Path(args.tracker).expanduser().resolve()
            if args.tracker
            else find_tracker(root)
        )
        if tracker and tracker.is_file():
            packages = load_packages_from_tracker(tracker)

    pkg_dir = (
        Path(args.timeline_package_dir).expanduser().resolve()
        if args.timeline_package_dir
        else None
    )
    try:
        result = run(
            root,
            payload,
            source=Path(args.source) if args.source else None,
            packages=packages,
            write_md=args.write_md,
            write_timeline=args.write_timeline,
            timeline_package=args.timeline_package,
            timeline_package_dir=pkg_dir,
            merge_packages=args.merge_packages,
            validate_only=args.validate_only,
            strict=not args.allow_invalid,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
