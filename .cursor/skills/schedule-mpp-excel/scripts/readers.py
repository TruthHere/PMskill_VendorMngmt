#!/usr/bin/env python3
"""Schedule task model + readers (csv/xlsx/xml/mpp)."""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass
class TaskRow:
    uid: str = ""
    task_id: int = 0
    name: str = ""
    outline_level: int = 1
    wbs: str = ""
    start: Optional[date] = None
    finish: Optional[date] = None
    duration: str = ""
    predecessors: str = ""
    percent_complete: float = 0.0
    resources: str = ""
    package: str = ""
    is_summary: bool = False
    is_milestone: bool = False
    is_critical: bool = False


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
_PACKAGE_HEADERS = {"采购包", "包名", "package", "package name", "package_name", "专业", "discipline"}
_ID_HEADERS = {"id", "任务id", "task id", "task_id", "uid"}
_OUTLINE_HEADERS = {"大纲级别", "大纲", "outline", "outline level", "outline_level", "wbs level"}
_WBS_HEADERS = {"wbs", "wbs编码", "wbs 编码", "wbs code"}
_DURATION_HEADERS = {"工期", "duration", "工期(天)"}
_PRED_HEADERS = {"前置任务", "前置", "predecessors", "predecessor", "preds"}
_PCT_HEADERS = {"完成百分比", "% complete", "percent complete", "%complete", "进度", "%完成"}
_RES_HEADERS = {"资源名称", "资源", "resource names", "resources", "resource"}
_SUMMARY_HEADERS = {"是否摘要", "摘要", "summary", "is_summary"}
_MILESTONE_HEADERS = {"是否里程碑", "里程碑标记", "milestone", "is_milestone"}
_CRITICAL_HEADERS = {"是否关键", "关键", "critical", "is_critical"}

# MSPDI LinkLag unit: tenths of a minute; 8h day → 4800 tenths = 1 working day
_LAG_TENTHS_PER_DAY = 4800


def _norm_header(h: Any) -> str:
    return re.sub(r"\s+", " ", str(h or "").strip().lower())


def parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    if "T" in s:
        s = s.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def duration_from_dates(start: Optional[date], finish: Optional[date], is_milestone: bool) -> str:
    """Calendar-span fallback: exclusive end semantics → (finish - start) days, not +1."""
    if is_milestone:
        return "0d"
    if not start or not finish:
        return ""
    days = (finish - start).days
    if days < 0:
        days = 0
    if days == 0 and start == finish:
        return "1d"
    return f"{days}d"


def parse_mspdi_duration(raw: str, is_milestone: bool) -> str:
    if is_milestone:
        return "0d"
    if not raw:
        return ""
    if raw.startswith("PT"):
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", raw)
        if m:
            hours = int(m.group(1) or 0)
            days = max(0, round(hours / 8)) if hours else 0
            return f"{days}d"
    return raw


def format_predecessor(task_id: Any, link: str = "FS", lag_days: float = 0.0) -> str:
    """Project-style: `3` / `3FS` / `3FS+2d` / `3SS-1d`."""
    tid = str(task_id)
    link = (link or "FS").upper()
    lag = float(lag_days or 0)
    # Whole days preferred
    if abs(lag - round(lag)) < 1e-6:
        lag_i = int(round(lag))
        lag_s = "" if lag_i == 0 else f"{lag_i:+d}d"
    else:
        lag_s = f"{lag:+.1f}d".replace(".0d", "d")

    if link == "FS" and not lag_s:
        return tid
    return f"{tid}{link}{lag_s}"


def lag_tenths_to_days(link_lag: str) -> float:
    try:
        tenths = float(link_lag or 0)
    except ValueError:
        return 0.0
    return tenths / _LAG_TENTHS_PER_DAY


def read_schedule(path: Path) -> list[TaskRow]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        return read_xlsx(path)
    if suffix == ".xml":
        return read_mspdi_xml(path)
    if suffix == ".mpp":
        return read_mpp(path)
    raise ValueError(f"不支持的输入格式: {suffix}（支持 .mpp / .xml / .xlsx / .csv）")


def _rows_from_mapping(rows: Iterable[dict[str, Any]]) -> list[TaskRow]:
    out: list[TaskRow] = []
    for i, raw in enumerate(rows, start=1):
        mapped = {_norm_header(k): v for k, v in raw.items()}

        def get(aliases: set[str], default: Any = "") -> Any:
            for a in aliases:
                if a in mapped and mapped[a] not in (None, ""):
                    return mapped[a]
            return default

        name = str(get(_NAME_HEADERS, "")).strip()
        if not name:
            continue
        start = parse_date(get(_START_HEADERS))
        finish = parse_date(get(_END_HEADERS))
        if start is None and finish is not None:
            start = finish
        if finish is None and start is not None:
            finish = start

        outline_raw = get(_OUTLINE_HEADERS, 1)
        try:
            outline = int(float(str(outline_raw)))
        except (TypeError, ValueError):
            outline = 1

        pct_raw = get(_PCT_HEADERS, 0)
        try:
            pct = float(str(pct_raw).replace("%", "").strip() or 0)
        except ValueError:
            pct = 0.0

        summary_raw = str(get(_SUMMARY_HEADERS, "")).strip().lower()
        milestone_raw = str(get(_MILESTONE_HEADERS, "")).strip().lower()
        critical_raw = str(get(_CRITICAL_HEADERS, "")).strip().lower()
        is_summary = summary_raw in {"1", "true", "yes", "y", "是", "摘要"}
        is_milestone = milestone_raw in {"1", "true", "yes", "y", "是", "里程碑"}
        is_critical = critical_raw in {"1", "true", "yes", "y", "是", "关键"}

        tid_raw = get(_ID_HEADERS, i)
        try:
            tid = int(float(str(tid_raw)))
        except (TypeError, ValueError):
            tid = i

        duration = str(get(_DURATION_HEADERS, "")).strip() or duration_from_dates(start, finish, is_milestone)
        wbs = str(get(_WBS_HEADERS, "")).strip()

        out.append(
            TaskRow(
                uid=str(tid),
                task_id=tid,
                name=name.lstrip(),
                outline_level=max(1, outline),
                wbs=wbs,
                start=start,
                finish=finish,
                duration=duration,
                predecessors=str(get(_PRED_HEADERS, "")).strip(),
                percent_complete=pct,
                resources=str(get(_RES_HEADERS, "")).strip(),
                package=str(get(_PACKAGE_HEADERS, "")).strip(),
                is_summary=is_summary,
                is_milestone=is_milestone,
                is_critical=is_critical,
            )
        )
    return out


def read_csv(path: Path) -> list[TaskRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV 无表头: {path}")
        return _rows_from_mapping(reader)


def _is_project_view_workbook(path: Path, sheet_title: str, first_row: tuple[Any, ...]) -> bool:
    """Detect human-facing Project View output; it must not be re-used as input."""
    name = path.name.lower()
    if name.endswith("_project_view.xlsx") or name.endswith("_project_view.xlsm"):
        return True
    if sheet_title == "Project View":
        return True
    first = " ".join(str(c or "") for c in first_row).strip()
    if first.startswith("项目:") and "甘特:" in first:
        return True
    return False


def read_xlsx(path: Path) -> list[TaskRow]:
    try:
        from openpyxl import load_workbook
    except ImportError as e:
        raise RuntimeError("需要 openpyxl：pip3 install openpyxl") from e

    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration as e:
        wb.close()
        raise ValueError(f"空工作簿: {path}") from e

    if _is_project_view_workbook(path, ws.title or "", tuple(header_row or ())):
        wb.close()
        raise ValueError(
            f"拒绝读取人看版 Project View：{path.name}\n"
            "请改用机读输出 `*_schedule.csv` / `*_schedule_structured.xlsx`，"
            "或原始 .mpp / Project XML / 任务表。\n"
            "说明：人看版第 1 行是元数据、甘特色块是静态填充，改日期也不会更新甘特；"
            "需要更新时请重新运行 convert_schedule.py。"
        )

    headers = [str(h or "").strip() for h in header_row]
    dict_rows = []
    for row in rows_iter:
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue
        dict_rows.append({headers[i]: row[i] if i < len(row) else None for i in range(len(headers))})
    wb.close()
    return _rows_from_mapping(dict_rows)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def read_mspdi_xml(path: Path) -> list[TaskRow]:
    tree = ET.parse(path)
    root = tree.getroot()

    resources: dict[str, str] = {}
    for el in root.iter():
        if _local(el.tag) != "Resource":
            continue
        rid, name = "", ""
        for child in el:
            ln = _local(child.tag)
            if ln == "UID":
                rid = (child.text or "").strip()
            elif ln == "Name":
                name = (child.text or "").strip()
        if rid and name:
            resources[rid] = name

    assigns: dict[str, list[str]] = {}
    for el in root.iter():
        if _local(el.tag) != "Assignment":
            continue
        tid, rid = "", ""
        for child in el:
            ln = _local(child.tag)
            if ln == "TaskUID":
                tid = (child.text or "").strip()
            elif ln == "ResourceUID":
                rid = (child.text or "").strip()
        if tid and rid and rid in resources and resources[rid]:
            assigns.setdefault(tid, []).append(resources[rid])

    tasks: list[TaskRow] = []
    # pred_buf[uid] = list of (pred_uid, link_type, lag_days)
    pred_buf: dict[str, list[tuple[str, str, float]]] = {}

    for el in root.iter():
        if _local(el.tag) != "Task":
            continue
        data: dict[str, str] = {}
        preds: list[tuple[str, str, float]] = []
        for child in el:
            ln = _local(child.tag)
            if ln == "PredecessorLink":
                puid, ptype, plag = "", "1", "0"
                for p in child:
                    pln = _local(p.tag)
                    if pln == "PredecessorUID":
                        puid = (p.text or "").strip()
                    elif pln == "Type":
                        ptype = (p.text or "1").strip()
                    elif pln == "LinkLag":
                        plag = (p.text or "0").strip()
                type_map = {"0": "FF", "1": "FS", "2": "SF", "3": "SS"}
                if puid:
                    preds.append((puid, type_map.get(ptype, "FS"), lag_tenths_to_days(plag)))
            else:
                data[ln] = (child.text or "").strip()

        name = data.get("Name", "").strip()
        if not name:
            continue
        uid = data.get("UID", "")
        if uid == "0" or data.get("ID") == "0":
            continue
        try:
            tid = int(float(data.get("ID") or data.get("UID") or 0))
        except ValueError:
            tid = len(tasks) + 1
        if tid == 0:
            continue

        start = parse_date(data.get("Start"))
        finish = parse_date(data.get("Finish"))
        try:
            outline = int(float(data.get("OutlineLevel") or 1))
        except ValueError:
            outline = 1
        if outline < 1:
            outline = 1
        try:
            pct = float(data.get("PercentComplete") or 0)
        except ValueError:
            pct = 0.0
        is_summary = data.get("Summary", "0") in {"1", "true", "True"}
        is_milestone = data.get("Milestone", "0") in {"1", "true", "True"}
        is_critical = data.get("Critical", "0") in {"1", "true", "True"}

        duration = parse_mspdi_duration(data.get("Duration", ""), is_milestone)
        if not duration:
            duration = duration_from_dates(start, finish, is_milestone)

        res_names = [n for n in assigns.get(uid, []) if n]
        row = TaskRow(
            uid=uid or str(tid),
            task_id=tid,
            name=name,
            outline_level=max(1, outline),
            wbs=data.get("WBS", "").strip(),
            start=start,
            finish=finish,
            duration=duration,
            predecessors="",
            percent_complete=pct,
            resources=", ".join(res_names),
            is_summary=is_summary,
            is_milestone=is_milestone,
            is_critical=is_critical,
        )
        tasks.append(row)
        if preds:
            pred_buf[row.uid] = preds

    uid_to_id = {t.uid: t.task_id for t in tasks}
    for t in tasks:
        rendered = []
        for puid, link, lag in pred_buf.get(t.uid, []):
            pid = uid_to_id.get(puid, puid)
            rendered.append(format_predecessor(pid, link, lag))
        t.predecessors = ",".join(rendered)

    return tasks


def read_mpp(path: Path) -> list[TaskRow]:
    """Prefer mppjs (no JVM) → MSPDI XML; fall back to mpxj+Java."""
    xml_path = _mpp_to_xml_via_mppjs(path)
    if xml_path is not None:
        try:
            return read_mspdi_xml(xml_path)
        finally:
            if xml_path.name.endswith(".mppjs.tmp.xml") and xml_path.exists():
                try:
                    xml_path.unlink()
                except OSError:
                    pass

    return _read_mpp_via_mpxj(path)


def _mppjs_timeout_seconds() -> int:
    import os

    raw = os.environ.get("MPPJS_TIMEOUT", "600").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 600


def _mpp_to_xml_via_mppjs(path: Path) -> Optional[Path]:
    import os
    import shutil
    import subprocess

    out = path.with_suffix(".mppjs.tmp.xml")
    timeout = _mppjs_timeout_seconds()
    candidates: list[list[str]] = []

    # 1) Prefer already-resolved local binary (env / vendor / skill .mppjs / PATH)
    try:
        from setup_mppjs import ensure_mppjs, find_local_binary

        local = find_local_binary()
        if local is None:
            # First-time: install into scripts/.mppjs (may take minutes once)
            local = ensure_mppjs(timeout=timeout)
        candidates.append([str(local), str(path), str(out)])
    except Exception as e:
        _MPPJS_LAST_ERROR[0] = str(e)

    # 2) Last resort: npx (slow; longer timeout)
    npx = shutil.which("npx")
    if npx:
        candidates.append([npx, "--yes", "@byteink/mppjs", str(path), str(out)])

    if not candidates:
        return None

    last_err = _MPPJS_LAST_ERROR[0]
    for cmd in candidates:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            last_err = str(e)
            continue
        if proc.returncode == 0 and out.is_file() and out.stat().st_size > 0:
            return out
        last_err = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
    if last_err:
        _MPPJS_LAST_ERROR[0] = last_err
    return None


_MPPJS_LAST_ERROR: list[str] = [""]


def _read_mpp_via_mpxj(path: Path) -> list[TaskRow]:
    try:
        from mpxj.reader import UniversalProjectReader
    except ImportError as e:
        hint = _MPPJS_LAST_ERROR[0]
        extra = f"\n（mppjs 尝试失败: {hint}）" if hint else ""
        raise RuntimeError(
            "无法直读 .mpp。本 Skill 依赖 mppjs 原生二进制（无需 Java）。\n"
            "请先运行一次：\n"
            "  python3 .cursor/skills/schedule-mpp-excel/scripts/setup_mppjs.py\n"
            "或设置 MPPJS_BINARY 指向 mpxj-convert；或安装 Node.js ≥ 20 后重试"
            "（脚本会自动 npm install 到 scripts/.mppjs/）。\n"
            "备选：pip3 install mpxj + Java 17+。" + extra
        ) from e

    import shutil
    import subprocess

    java = shutil.which("java")
    if not java:
        raise RuntimeError(
            "mppjs 不可用，且未找到 Java（mpxj 兜底需要 Java 17+）。\n"
            "请运行：python3 .cursor/skills/schedule-mpp-excel/scripts/setup_mppjs.py"
        )
    try:
        subprocess.run([java, "-version"], capture_output=True, check=False)
    except OSError as e:
        raise RuntimeError(
            "Java 无法执行。请运行 setup_mppjs.py 安装 mppjs（推荐，无需 Java）。"
        ) from e

    project = UniversalProjectReader().read(str(path))
    tasks: list[TaskRow] = []

    for t in project.getTasks():
        if t is None:
            continue
        name = str(t.getName() or "").strip()
        if not name:
            continue
        try:
            tid = int(t.getID() or 0)
        except Exception:
            tid = len(tasks) + 1
        if tid == 0:
            continue
        try:
            outline = int(t.getOutlineLevel() or 1)
        except Exception:
            outline = 1

        start = _mpxj_date(t.getStart())
        finish = _mpxj_date(t.getFinish())
        try:
            pct = float(t.getPercentageComplete() or 0)
        except Exception:
            pct = 0.0
        try:
            is_summary = bool(t.getSummary())
        except Exception:
            is_summary = False
        try:
            is_milestone = bool(t.getMilestone())
        except Exception:
            is_milestone = False
        try:
            is_critical = bool(t.getCritical())
        except Exception:
            is_critical = False

        duration = ""
        try:
            d = t.getDuration()
            if d is not None:
                duration = f"{int(round(float(d.getDuration())))}d"
        except Exception:
            duration = ""
        if not duration:
            duration = duration_from_dates(start, finish, is_milestone)

        preds = []
        try:
            for rel in t.getPredecessors() or []:
                pt = rel.getTargetTask()
                pid = pt.getID() if pt is not None else None
                if pid is None:
                    continue
                link = str(rel.getType() or "FS")
                lag_days = 0.0
                try:
                    lag = rel.getLag()
                    if lag is not None:
                        lag_days = float(lag.getDuration())
                except Exception:
                    lag_days = 0.0
                preds.append(format_predecessor(int(pid), link, lag_days))
        except Exception:
            pass

        rnames = []
        try:
            for a in t.getResourceAssignments() or []:
                r = a.getResource()
                if r is not None and r.getName():
                    rnames.append(str(r.getName()))
        except Exception:
            pass

        try:
            uid = str(t.getUniqueID())
        except Exception:
            uid = str(tid)
        if uid == "0":
            continue

        wbs = ""
        try:
            wbs = str(t.getWBS() or "")
        except Exception:
            wbs = ""

        tasks.append(
            TaskRow(
                uid=uid,
                task_id=tid,
                name=name,
                outline_level=max(1, outline),
                wbs=wbs,
                start=start,
                finish=finish,
                duration=duration,
                predecessors=",".join(preds),
                percent_complete=pct,
                resources=", ".join(rnames),
                is_summary=is_summary,
                is_milestone=is_milestone,
                is_critical=is_critical,
            )
        )
    return tasks


def _mpxj_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    try:
        if hasattr(value, "getYear") and hasattr(value, "getMonthValue"):
            return date(int(value.getYear()), int(value.getMonthValue()), int(value.getDayOfMonth()))
        if hasattr(value, "getTime"):
            from datetime import timezone

            millis = int(value.getTime())
            return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc).date()
    except Exception:
        pass
    return parse_date(str(value))


def timeline_bounds(tasks: list[TaskRow], unit: str) -> tuple[date, date]:
    """Tight bounds: align to unit edges with at most half-unit padding."""
    starts = [t.start for t in tasks if t.start]
    finishes = [t.finish for t in tasks if t.finish]
    if not starts and not finishes:
        today = date.today()
        return today, today + timedelta(days=28)
    lo = min(starts + finishes)
    hi = max(starts + finishes)
    if unit == "day":
        return lo, hi
    # week: snap to Monday / Sunday covering the range (no extra ±1 week)
    lo = lo - timedelta(days=lo.weekday())
    hi = hi + timedelta(days=(6 - hi.weekday()))
    return lo, hi


def iter_timeline(start: date, end: date, unit: str) -> list[date]:
    out: list[date] = []
    cur = start
    step = timedelta(days=1 if unit == "day" else 7)
    while cur <= end:
        out.append(cur)
        cur = cur + step
    return out


def resolve_gantt_unit(tasks: list[TaskRow], requested: str) -> str:
    """Force week when span > ~4 months to avoid day-mode column explosion."""
    if requested == "week":
        return "week"
    starts = [t.start for t in tasks if t.start]
    finishes = [t.finish for t in tasks if t.finish]
    if not starts and not finishes:
        return requested
    span = (max(starts + finishes) - min(starts + finishes)).days
    if span > 120:  # ~4 months
        return "week"
    return requested
