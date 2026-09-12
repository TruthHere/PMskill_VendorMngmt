#!/usr/bin/env python3
"""Parse project schedule CSV and sync to .skill/schedule.json."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from common import (
    PROJECT_JSON,
    SCHEDULE_JSON,
    load_json,
    now_iso,
    project_archive_dir,
    save_json,
    system_file,
)

_NAME_HEADERS = {
    "里程碑",
    "节点",
    "节点名称",
    "任务名称",
    "任务",
    "活动",
    "activity",
    "task",
    "task name",
    "task_name",
    "name",
    "milestone",
    "milestone name",
    "description",
    "wbs",
    "wbs name",
}
_START_HEADERS = {
    "开始",
    "开始日期",
    "start",
    "start date",
    "start_date",
    "计划开始",
    "基准开始",
    "日期",
    "date",
    "基准日期",
}
_END_HEADERS = {
    "结束",
    "结束日期",
    "finish",
    "finish date",
    "finish_date",
    "计划完成",
    "完成日期",
    "end",
    "end date",
    "end_date",
    "计划结束",
}
_PACKAGE_HEADERS = {
    "采购包",
    "包名",
    "package",
    "package name",
    "package_name",
    "专业",
    "discipline",
    "trade",
}

_DATE_PATTERNS = (
    ("%Y-%m-%d", r"^\d{4}-\d{2}-\d{2}$"),
    ("%Y/%m/%d", r"^\d{4}/\d{1,2}/\d{1,2}$"),
    ("%Y.%m.%d", r"^\d{4}\.\d{1,2}\.\d{1,2}$"),
    ("%Y%m%d", r"^\d{8}$"),
)


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _header_key(header: str) -> str | None:
    norm = _normalize_header(header)
    if not norm:
        return None
    if norm in _NAME_HEADERS:
        return "name"
    if norm in _START_HEADERS:
        return "start"
    if norm in _END_HEADERS:
        return "end"
    if norm in _PACKAGE_HEADERS:
        return "package"
    return None


def parse_date_cell(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    for fmt, pattern in _DATE_PATTERNS:
        if re.match(pattern, text):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    match = re.search(r"\d{4}/\d{1,2}/\d{1,2}", text)
    if match:
        try:
            parts = match.group(0).split("/")
            return datetime(int(parts[0]), int(parts[1]), int(parts[2])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _compose_name(base_name: str, package_name: str) -> str:
    base = (base_name or "").strip()
    package = (package_name or "").strip()
    if not base:
        return ""
    if not package:
        return base
    if package.lower() in base.lower():
        return base
    return f"{package} {base}"


def parse_schedule_csv(path: Path) -> list[dict[str, str]]:
    path = path.expanduser().resolve()
    raw = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        return []

    mapping: dict[str, str] = {}
    for header in reader.fieldnames:
        key = _header_key(header)
        if key and key not in mapping:
            mapping[key] = header

    if "name" not in mapping:
        raise ValueError(
            f"Schedule CSV missing milestone name column. "
            f"Expected one of: {', '.join(sorted(_NAME_HEADERS))}. "
            f"Found headers: {reader.fieldnames}"
        )
    if "start" not in mapping and "end" not in mapping:
        raise ValueError(
            f"Schedule CSV missing date column. "
            f"Expected start/finish headers such as 开始日期 / 结束日期 / date. "
            f"Found headers: {reader.fieldnames}"
        )

    milestones: list[dict[str, str]] = []
    for row in reader:
        if not row:
            continue
        name = str(row.get(mapping["name"], "") or "").strip()
        if not name or name.startswith("#"):
            continue
        package = str(row.get(mapping.get("package", ""), "") or "").strip() if mapping.get("package") else ""
        name = _compose_name(name, package)

        start = parse_date_cell(str(row.get(mapping.get("start", ""), "") or "")) if mapping.get("start") else ""
        end = parse_date_cell(str(row.get(mapping.get("end", ""), "") or "")) if mapping.get("end") else ""
        if not start and end:
            start = end
        if start and not end:
            end = start
        if not start:
            continue

        item: dict[str, str] = {"name": name, "date": start}
        if end and end != start:
            item["end_date"] = end
        if package:
            item["package"] = package
        milestones.append(item)
    return milestones


def resolve_schedule_csv_path(project_root: Path) -> Path | None:
    root = project_root.expanduser().resolve()
    project = load_json(system_file(root, PROJECT_JSON), {}) or {}

    configured = str(project.get("schedule_csv") or "").strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = root / configured
        if path.is_file():
            return path.resolve()

    archive = project_archive_dir(root) / "00_进度计划"
    if not archive.is_dir():
        return None

    csv_files = sorted(archive.glob("*.csv"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not csv_files:
        return None
    if len(csv_files) == 1:
        return csv_files[0].resolve()

    preferred: list[Path] = []
    for pattern in ("*进度*", "*schedule*", "*project*", "*Project*"):
        preferred.extend(archive.glob(f"{pattern}.csv"))
    if preferred:
        return sorted(preferred, key=lambda item: item.stat().st_mtime, reverse=True)[0].resolve()
    return csv_files[0].resolve()


def import_project_schedule_csv(
    project_root: Path,
    source: Path | None = None,
    *,
    register: bool = True,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    csv_path = source.expanduser().resolve() if source else resolve_schedule_csv_path(root)
    if csv_path is None or not csv_path.is_file():
        raise FileNotFoundError(
            f"No schedule CSV found for project {root}. "
            "Place a CSV under 项目档案/00_进度计划/ or pass --source."
        )

    milestones = parse_schedule_csv(csv_path)
    if not milestones:
        raise ValueError(f"No milestones parsed from schedule CSV: {csv_path}")

    if csv_path.is_relative_to(root):
        rel_path = str(csv_path.relative_to(root))
    else:
        rel_path = str(csv_path)
    schedule_doc = {
        "milestones": milestones,
        "source_csv": rel_path,
        "imported_at": now_iso(),
        "note": "Auto-imported from project schedule CSV",
    }
    save_json(system_file(root, SCHEDULE_JSON), schedule_doc)

    if register:
        project = load_json(system_file(root, PROJECT_JSON), {}) or {}
        project["schedule_csv"] = rel_path
        save_json(system_file(root, PROJECT_JSON), project)

    return {
        "project_root": str(root),
        "schedule_csv": str(csv_path),
        "milestone_count": len(milestones),
        "milestones": milestones,
    }


def load_schedule_milestones(project_root: Path) -> list[dict[str, str]]:
    root = project_root.expanduser().resolve()
    csv_path = resolve_schedule_csv_path(root)
    if csv_path and csv_path.is_file():
        try:
            milestones = parse_schedule_csv(csv_path)
            if milestones:
                return milestones
        except (OSError, ValueError, csv.Error):
            pass

    data = load_json(system_file(root, SCHEDULE_JSON), {})
    milestones = data.get("milestones") if isinstance(data, dict) else []
    result: list[dict[str, str]] = []
    for item in milestones or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        date = str(item.get("date") or item.get("start") or "").strip()
        end_date = str(item.get("end_date") or item.get("end") or "").strip()
        if name and date:
            row = {"name": name, "date": date, "end_date": end_date}
            package = str(item.get("package") or "").strip()
            if package:
                row["package"] = package
            result.append(row)
    return result
