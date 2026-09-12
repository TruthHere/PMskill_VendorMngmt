#!/usr/bin/env python3
"""Handle a routed change mail and update Change Log conservatively."""

from __future__ import annotations

import argparse
import csv
import email
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
SKILLS = SCRIPTS.parents[1]
FULFILLMENT_SCRIPTS = SKILLS / "contract-fulfillment-struct" / "scripts"
MAIL_INBOX_SCRIPTS = SKILLS / "mail-inbox" / "scripts"
FOUNDATION_SCRIPTS = SKILLS.parent / "lib" / "project-foundation" / "scripts"
for path in (SCRIPTS, FOUNDATION_SCRIPTS, FULFILLMENT_SCRIPTS, MAIL_INBOX_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from archive_file import archive_file  # noqa: E402
from classify_mail import decode_mime_header, get_body_text  # noqa: E402
from common import (  # noqa: E402
    CST,
    PROJECT_JSON,
    format_currency_amount,
    load_json,
    load_tracker_packages,
    now_iso,
    parse_amount_with_tax,
    system_file,
)
from pending_store import add_pending as store_add_pending, close_matching  # noqa: E402


def add_pending(project_root: Path, item: dict[str, Any]) -> str:
    return store_add_pending(project_root, item, skill="change-archive")

TEMPLATE = SCRIPTS.parent / "assets" / "change_log.template.csv"

STATUS_TO_LABEL = {
    "change.cod": "COD 已发出",
    "change.pmi": "PMI 已发出",
    "change.tech_submit": "技术审核中",
    "change.tech_confirm": "技术确认",
    "change.commercial": "商务确认",
    "change.commercial_amount": "商务金额确认",
    "change.change_po": "Change PO 下发",
}
STATUS_ORDER = {
    "COD 已发出": 1,
    "PMI 已发出": 2,
    "技术审核中": 3,
    "技术确认": 4,
    "商务确认": 5,
    "商务金额确认": 6,
    "Change PO 下发": 7,
    # 已取消：终态侧枝，不参与 1→7 前进序；见 is_cancelled()
}
MILESTONE_FIELD_BY_INTENT = {
    "change.cod": ["COD已发出"],
    "change.pmi": ["PMI已发出"],
    "change.tech_submit": ["技术文件提交", "技术审核中"],
    "change.tech_confirm": ["技术确认"],
    "change.commercial": ["商务确认"],
    "change.commercial_amount": ["商务金额确认"],
    "change.change_po": ["Change PO下发"],
}
# 与采购包 Tracker 同语义：每列一个节点，单元格有值=已达成（首次锁定）
MILESTONE_COLUMNS = [
    "COD已发出",
    "PMI已发出",
    "技术文件提交",
    "技术审核中",
    "技术确认",
    "商务确认",
    "商务金额确认",
    "Change PO下发",
    "已取消",
]
CANCELLED_STATUS = "已取消"
DRAWING_HINT_RE = re.compile(r"drawing|图|shop|submittal|送审", re.I)


def template_fieldnames() -> list[str]:
    raw = TEMPLATE.read_text(encoding="utf-8-sig").splitlines()
    for line in raw:
        if line.startswith("#") or not line.strip():
            continue
        return next(csv.reader([line]))
    return []


def merge_fieldnames(existing: list[str] | None) -> list[str]:
    """Upgrade old Change Log headers (e.g. missing COD已发出/PMI已发出)."""
    base = template_fieldnames()
    have = list(existing or [])
    if not have:
        return base
    # Keep unknown custom columns at the end (before 备注 if possible)
    extras = [c for c in have if c and c not in base]
    if not extras:
        return base
    out = list(base)
    if "备注" in out:
        idx = out.index("备注")
        for col in extras:
            out.insert(idx, col)
            idx += 1
    else:
        out.extend(extras)
    return out


def resolve_change_log_path(project_root: Path) -> Path:
    project = load_json(system_file(project_root, PROJECT_JSON), {}) or {}
    project_name = str(project.get("project_name") or "").strip()
    if not project_name:
        raise FileNotFoundError(f"missing project_name in {PROJECT_JSON}")
    return project_root / f"{project_name}_change_log.csv"


def ensure_change_log(project_root: Path) -> Path:
    from write_guard import assert_change_log_write

    assert_change_log_write()
    path = resolve_change_log_path(project_root)
    if not path.exists():
        path.write_text(TEMPLATE.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
    return path


def load_change_log(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    raw = path.read_text(encoding="utf-8-sig")
    lines = raw.splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    reader = csv.DictReader(lines)
    rows = [{k: (v or "") for k, v in row.items() if k} for row in reader if row and any(row.values())]
    fieldnames = merge_fieldnames(list(reader.fieldnames or []))
    for row in rows:
        for name in fieldnames:
            row.setdefault(name, "")
    return rows, fieldnames


def save_change_log(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    from write_guard import assert_change_log_write

    assert_change_log_write()
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = merge_fieldnames(fieldnames)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        f.write(f"# 最后更新,{now_iso()}\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def event_stamp(eml_path: Path | None = None, fallback: str | None = None) -> str:
    """Prefer email Date for milestone stamp; else now."""
    if eml_path and eml_path.is_file():
        try:
            from email.utils import parsedate_to_datetime

            msg = email.message_from_bytes(eml_path.read_bytes())
            raw = msg.get("Date") or ""
            if raw:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=CST)
                return dt.astimezone(CST).isoformat(timespec="seconds")
        except Exception:
            pass
    return fallback or now_iso()


def stamp_milestones(row: dict[str, str], intent: str, *, stamp: str) -> None:
    for field in MILESTONE_FIELD_BY_INTENT.get(intent) or []:
        if not str(row.get(field) or "").strip():
            row[field] = stamp


def package_name_key(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (text or "").lower())


def package_key_variants(name: str) -> set[str]:
    """Tolerate English singular/plural drift: GC work ↔ GC works."""
    key = package_name_key(name)
    out = {key} if key else set()
    if not key:
        return out
    if key.endswith("ies") and len(key) > 4:
        out.add(key[:-3] + "y")
    elif key.endswith("s") and len(key) > 3 and not key.endswith(("ss", "us", "is")):
        out.add(key[:-1])
    else:
        out.add(key + "s")
    return {k for k in out if k}


def blob_mentions_package(blob: str, name: str) -> bool:
    if not name:
        return False
    if re.search(re.escape(name), blob, re.I):
        return True
    blob_key = package_name_key(blob)
    for key in package_key_variants(name):
        if key and key in blob_key:
            return True
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if len(parts) >= 2:
        head = r"\s+".join(re.escape(p) for p in parts[:-1])
        last = parts[-1]
        stem = re.escape(last[:-1] if last.lower().endswith("s") and len(last) > 3 else last)
        if re.search(rf"\b{head}\s+{stem}s?\b", blob, re.I):
            return True
    return False


def infer_change_no(subject: str, body: str, hints: dict[str, Any]) -> str:
    hinted = str(hints.get("change_no") or "").strip()
    if hinted:
        return hinted.replace("-", "").replace(" ", "")
    blob = f"{subject}\n{body}"
    m = re.search(r"\b(COD|COT|PMI)\s*[- ]?([A-Z0-9]{2,10})\b", blob, re.I)
    if not m:
        return ""
    return f"{m.group(1).upper()}{m.group(2).upper()}"


def infer_package(
    packages: list[dict[str, str]],
    subject: str,
    body: str,
    hints: dict[str, Any],
    *,
    eml_path: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, str] | None:
    hinted = str(hints.get("package_name") or "").strip()
    if hinted:
        key = package_name_key(hinted)
        for pkg in packages:
            if package_name_key(pkg.get("package_name") or "") == key:
                return pkg
            if blob_mentions_package(hinted, str(pkg.get("package_name") or "")):
                return pkg
    blob = f"{subject}\n{body}"
    matches: list[dict[str, str]] = []
    for pkg in packages:
        name = str(pkg.get("package_name") or "").strip()
        if not name:
            continue
        if blob_mentions_package(blob, name):
            matches.append(pkg)
            continue
        # supplier name as weak secondary signal
        supplier = str(pkg.get("supplier_name") or pkg.get("supplier_short") or "").strip()
        if supplier and re.search(re.escape(supplier), blob, re.I):
            matches.append(pkg)
    # de-dupe while preserving order
    dedup: list[dict[str, str]] = []
    seen: set[str] = set()
    for pkg in matches:
        name = str(pkg.get("package_name") or "")
        if name in seen:
            continue
        seen.add(name)
        dedup.append(pkg)
    matches = dedup
    if len(matches) == 1:
        return matches[0]
    if eml_path is not None:
        eml_resolved = eml_path.expanduser().resolve()
        for pkg in packages:
            folder = str(pkg.get("folder_path") or "").strip()
            if not folder:
                continue
            folder_path = Path(folder).expanduser()
            if project_root is not None and not folder_path.is_absolute():
                folder_path = project_root / folder_path
            if folder_path.suffix.lower() in {".html", ".htm", ".json"}:
                folder_path = folder_path.parent
            try:
                eml_resolved.relative_to(folder_path.resolve())
                return pkg
            except ValueError:
                if folder_path.name and folder_path.name in eml_resolved.parts:
                    return pkg
                continue
    return None


def infer_supplier(pkg: dict[str, str]) -> str:
    return str(pkg.get("supplier_name") or pkg.get("supplier_short") or "").strip()


def package_dir_from_pkg(project_root: Path, pkg: dict[str, str]) -> Path:
    raw = str(pkg.get("folder_path") or "").strip()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project_root / path
    if path.suffix.lower() in {".html", ".htm", ".json"}:
        path = path.parent
    return path.resolve()


def normalize_change_no(text: str) -> str:
    return re.sub(r"[\s\-_/]+", "", (text or "").upper())


def project_title_aliases(project_root: Path | None) -> list[str]:
    """Project name/code variants to strip from change titles."""
    if project_root is None:
        return []
    try:
        project = load_json(system_file(project_root, PROJECT_JSON), {}) or {}
    except Exception:
        return []
    aliases: list[str] = []
    for key in ("project_name", "project_code"):
        raw = str(project.get(key) or "").strip()
        if not raw:
            continue
        aliases.append(raw)
        # drop leading brand token: "Apple SARL Ph5" → "SARL Ph5"
        parts = raw.split()
        if len(parts) >= 2 and parts[0].lower() in {"apple", "client", "owner"}:
            aliases.append(" ".join(parts[1:]))
    # longest first so "Apple SARL Ph5" wins over "SARL Ph5"
    return sorted({a for a in aliases if a}, key=len, reverse=True)


def extract_change_title(
    subject: str,
    change_no: str,
    *,
    body: str = "",
    project_root: Path | None = None,
) -> str:
    # Prefer body phrasing: "Hereby issue the COD076 for <title>."
    if body:
        m = re.search(
            r"(?:hereby\s+)?(?:issue|issued)\s+(?:the\s+)?(?:COD|COT|PMI)\s*[- ]?[A-Z0-9]*\d[A-Z0-9]*\s+for\s+(.+?)(?:\.|$)",
            body,
            re.I | re.S,
        )
        if m:
            candidate = re.sub(r"\s+", " ", m.group(1)).strip(" \t.-_·•—–")
            # stop at next sentence marker / blank intent
            candidate = re.split(r"(?:This email|Thank you|Thanks\b)", candidate, maxsplit=1, flags=re.I)[0]
            candidate = candidate.strip(" \t.-_·•—–")
            if 8 <= len(candidate) <= 120:
                return candidate[:120]

    title = re.sub(r"^(?:FW|FWD|RE)\s*:\s*", "", subject.strip(), flags=re.I)
    # normalize whitespace / soft line wraps in subjects
    title = re.sub(r"\s+", " ", title.replace("\r", " ").replace("\n", " "))

    for alias in project_title_aliases(project_root):
        title = re.sub(re.escape(alias), " ", title, flags=re.I)

    if change_no:
        title = re.sub(re.escape(change_no), " ", title, flags=re.I)
        title = re.sub(re.escape(normalize_change_no(change_no)), " ", title, flags=re.I)
    # 序号段必须含数字，避免把「COD COT-009」误切成「COD + COT」
    title = re.sub(r"\b(?:COD|COT|PMI)\s*[- ]?[A-Z0-9]*\d[A-Z0-9]*\b", " ", title, flags=re.I)
    title = re.sub(r"\[(?:COD|PMI|Change PO)[^\]]*\]", " ", title, flags=re.I)
    title = re.sub(r"\((?:Change PO|变更 ?PO|增补 ?PO)[^)]+\)", " ", title, flags=re.I)
    title = re.sub(r"\b(?:COD|PMI|Change\s*PO)\b", " ", title, flags=re.I)
    # collapse leftover separators from stripped tokens: " - - " / "· ·"
    title = re.sub(r"[\s]*[-_·•—–|/]+[\s]*", " - ", title)
    title = re.sub(r"(?:\s*-\s*){2,}", " - ", title)
    title = re.sub(r"\s+", " ", title).strip(" -_·•\t—–|/.")
    return title[:120]


def relative_archive_dir(project_root: Path, package_dir: Path) -> str:
    return str((package_dir / "04_变更洽商").resolve().relative_to(project_root.resolve())) + "/"


def stage_tag(intent: str) -> str:
    return {
        "change.cod": "COD",
        "change.pmi": "PMI",
        "change.tech_submit": "TECH",
        "change.tech_confirm": "TC",
        "change.commercial": "QUOTE",
        "change.commercial_amount": "CP",
        "change.change_po": "CHPO",
    }.get(intent, "CHANGE")


def archive_change_mail(
    project_root: Path,
    package_dir: Path,
    package_name: str,
    eml_path: Path,
    attachment_paths: list[str] | None,
    *,
    change_no: str,
    intent: str,
) -> dict[str, list[str]]:
    # version 放阶段码，description 放变更序号，避免 sanitize 截断后各阶段文件名撞车
    stage = stage_tag(intent)
    desc = change_no or "UNKNOWN"
    eml_targets = [
        archive_file(
            source=eml_path,
            dest_dir=package_dir / "07_往来文件",
            package_name=package_name,
            file_type="邮件",
            description=desc,
            version=stage,
        ),
        archive_file(
            source=eml_path,
            dest_dir=package_dir / "04_变更洽商",
            package_name=package_name,
            file_type="变更",
            description=desc,
            version=stage,
        ),
    ]

    archived: dict[str, list[str]] = {
        "eml": [str(p) for p in eml_targets],
        "attachments_04": [],
        "attachments_02": [],
    }
    for att in attachment_paths or []:
        source = Path(att)
        if not source.is_file():
            continue
        target_04 = archive_file(
            source=source,
            dest_dir=package_dir / "04_变更洽商",
            package_name=package_name,
            file_type="变更",
            description=desc,
            version=stage,
        )
        archived["attachments_04"].append(str(target_04))
        if DRAWING_HINT_RE.search(source.name):
            target_02 = archive_file(
                source=source,
                dest_dir=package_dir / "02_图纸",
                package_name=package_name,
                file_type="图纸",
                description=desc,
                version=stage,
            )
            archived["attachments_02"].append(str(target_02))
    return archived


def locate_row(rows: list[dict[str, str]], change_no: str, package_name: str) -> dict[str, str] | None:
    key = normalize_change_no(change_no)
    for row in rows:
        if (
            normalize_change_no(str(row.get("变更序号") or "")) == key
            and str(row.get("采购包名称") or "").strip() == package_name
        ):
            return row
    return None


def can_advance(row: dict[str, str], new_status: str) -> bool:
    if is_cancelled(row):
        return False
    current = str(row.get("当前状态") or "").strip()
    return STATUS_ORDER.get(new_status, 0) >= STATUS_ORDER.get(current, 0)


def would_skip(row: dict[str, str], new_status: str) -> bool:
    """True if advancing would jump more than one status step."""
    if is_cancelled(row):
        return True
    current = str(row.get("当前状态") or "").strip()
    cur = STATUS_ORDER.get(current, 0)
    new = STATUS_ORDER.get(new_status, 0)
    return new > cur + 1


def is_cancelled(row: dict[str, str] | None) -> bool:
    """已取消：当前状态或「已取消」里程碑列任一有值即视为终态（含 PM 手改）。"""
    if not row:
        return False
    if str(row.get("当前状态") or "").strip() == CANCELLED_STATUS:
        return True
    return bool(str(row.get("已取消") or "").strip())


def ensure_row(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    *,
    change_no: str,
    package_name: str,
    supplier: str,
    title: str,
    archive_path: str,
) -> dict[str, str]:
    row = locate_row(rows, change_no, package_name)
    if row:
        return row
    row = {name: "" for name in fieldnames}
    row["变更序号"] = change_no
    row["采购包名称"] = package_name
    row["供应商"] = supplier
    row["变更内容"] = title
    row["归档路径"] = archive_path
    row["备注"] = "不改采购包 Tracker"
    rows.append(row)
    return row


_AMOUNT_HINT_RE = re.compile(
    r"CP\s*confirm|final\s*price|最终金额|确认报价|commercial\s*amount|"
    r"预估金额|estimate(?:d)?\s*(?:amount|cost|price)?|forecast(?:ed)?|"
    r"financial\s*value|cost\s*impact|不含税|excl\.?\s*VAT",
    re.I,
)
_CURRENCY_AMOUNT_RE = re.compile(
    r"(?:RMB|CNY|USD|¥|￥)\s*[\d,]+(?:\.\d+)?|[\d,]{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{2}",
    re.I,
)


def _line_has_real_money(line: str, change_no: str = "") -> bool:
    """Reject lines whose only digits are the change number (e.g. COT-003)."""
    if not _CURRENCY_AMOUNT_RE.search(line):
        return False
    parsed = parse_amount_with_tax(line)
    raw_amt = str(parsed.get("amount_excl_tax") or parsed.get("amount_incl_tax") or "")
    m = re.search(r"([\d,]+(?:\.\d+)?)", raw_amt.replace(" ", ""))
    if not m:
        return False
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return False
    # Tiny integers that match change-no trailing digits are almost never real change amounts
    key = normalize_change_no(change_no)
    trailing = re.search(r"(\d+)$", key)
    if trailing and num == float(trailing.group(1)) and num < 1000:
        return False
    if num < 1:
        return False
    return True


def extract_amount_line(subject: str, body: str, *, change_no: str = "", prefer_hints: bool = True) -> str:
    """Pick a line that both looks like an amount context and contains real money."""
    lines = [ln.strip() for ln in f"{subject}\n{body}".splitlines() if ln.strip()]
    hinted = [ln for ln in lines if _AMOUNT_HINT_RE.search(ln)]
    ordered = (hinted + [ln for ln in lines if ln not in hinted]) if prefer_hints else lines
    for line in ordered:
        if _line_has_real_money(line, change_no):
            return line
    return ""


def extract_excl_amount(subject: str, body: str, *, change_no: str = "") -> tuple[str, bool]:
    line = extract_amount_line(subject, body, change_no=change_no, prefer_hints=True)
    if not line:
        return "", True
    parsed = parse_amount_with_tax(line)
    raw = line.lower()
    explicit_excl = bool(re.search(r"excl|不含税|未税|before\s*vat", raw, re.I))
    explicit_incl = bool(re.search(r"incl|含税|include\.?\s*vat", raw, re.I))
    if parsed.get("amount_excl_tax") and (explicit_excl or not explicit_incl):
        return str(parsed["amount_excl_tax"]), bool(parsed.get("tax_uncertain"))
    if parsed.get("amount_incl_tax") and not parsed.get("amount_excl_tax"):
        return "", True
    return "", True


def extract_estimate_amount(subject: str, body: str, *, change_no: str = "") -> str:
    """COD 预估金额（不含税）；抽不到则空串，不瞎填。"""
    # Prefer estimate/forecast context; allow amount on the following line
    lines = [ln.strip() for ln in f"{subject}\n{body}".splitlines()]
    for i, candidate in enumerate(lines):
        if not re.search(r"预估|estimate|forecast|financial\s*value|cost\s*impact", candidate, re.I):
            continue
        window = " ".join(x for x in lines[i : i + 3] if x.strip())
        if _line_has_real_money(window, change_no):
            amount, _u = extract_excl_amount(window, "", change_no=change_no)
            if amount:
                return amount
            parsed = parse_amount_with_tax(window)
            if parsed.get("amount_excl_tax") and _line_has_real_money(
                str(parsed.get("amount_excl_tax")), change_no
            ):
                return str(parsed["amount_excl_tax"])
    line = extract_amount_line(subject, body, change_no=change_no, prefer_hints=True)
    if not line:
        return ""
    amount, _uncertain = extract_excl_amount(line, "", change_no=change_no)
    if amount:
        return amount
    parsed = parse_amount_with_tax(line)
    return str(parsed.get("amount_excl_tax") or "")


def extract_time_impact(subject: str, body: str) -> str:
    blob = f"{subject}\n{body}"
    m = re.search(
        r"Schedule\s*Impact[^\n]*\n+\s*[・\-–*]?\s*(No schedule impact|[^\n]{3,120})",
        blob,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()[:120]
    m = re.search(r"(No schedule impact|无进度影响|不影响工期)", blob, re.I)
    return m.group(1).strip() if m else ""


def close_change_po_pending(project_root: Path, change_no: str, package_name: str, eml_path: Path) -> None:
    def _match(item: dict[str, Any]) -> bool:
        if str(item.get("reason") or "") != "change_po_deferred":
            return False
        fields = item.get("fields") or {}
        matches_eml = str(item.get("eml_path") or "") == str(eml_path)
        matches_change = change_no and normalize_change_no(str(fields.get("change_no") or "")) == normalize_change_no(
            change_no
        )
        matches_pkg = package_name and str(fields.get("package_name") or "") == package_name
        return bool(matches_eml or matches_change or matches_pkg)

    close_matching(project_root, skill="change-archive", match=_match)


def require_prior(row: dict[str, str], expected: str) -> bool:
    return STATUS_ORDER.get(str(row.get("当前状态") or "").strip(), 0) >= STATUS_ORDER.get(expected, 0)


def handle_change_mail(
    *,
    project_root: Path,
    eml_path: Path,
    subject: str,
    body: str,
    classification: dict[str, Any],
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    intent = str(classification.get("intent") or "")
    hints = classification.get("hints") or {}
    packages = load_tracker_packages(project_root)
    package = infer_package(
        packages,
        subject,
        body,
        hints,
        eml_path=eml_path,
        project_root=project_root,
    )
    change_no = infer_change_no(subject, body, hints)

    if not change_no:
        pid = add_pending(
            project_root,
            {
                "step": "change_archive",
                "fields": hints,
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "change_id_unmatched",
                "note": "无法从邮件中识别变更序号。",
            },
        )
        return {"auto": False, "pending_id": pid, "reason": "change_id_unmatched", "intent": intent}

    if not package:
        pid = add_pending(
            project_root,
            {
                "step": "change_archive",
                "fields": {**hints, "change_no": change_no},
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "package_unmatched",
                "note": "变更序号已识别，但无法唯一匹配采购包。",
            },
        )
        return {"auto": False, "pending_id": pid, "reason": "package_unmatched", "intent": intent}

    package_name = str(package.get("package_name") or "")
    package_dir = package_dir_from_pkg(project_root, package)
    supplier = infer_supplier(package)

    archived = archive_change_mail(
        project_root,
        package_dir,
        package_name,
        eml_path,
        attachment_paths,
        change_no=change_no,
        intent=intent,
    )
    change_log = ensure_change_log(project_root)
    rows, fieldnames = load_change_log(change_log)
    row = locate_row(rows, change_no, package_name)

    if intent != "change.cod" and row is None:
        pid = add_pending(
            project_root,
            {
                "step": "change_archive",
                "fields": {"change_no": change_no, "package_name": package_name},
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "change_row_missing",
                "note": "该阶段邮件已识别，但 Change Log 里还没有对应 COD 建行。",
            },
        )
        return {"auto": False, "pending_id": pid, "reason": "change_row_missing", "intent": intent}

    title = extract_change_title(subject, change_no, body=body, project_root=project_root)

    if row is None:
        row = ensure_row(
            rows,
            fieldnames,
            change_no=change_no,
            package_name=package_name,
            supplier=supplier,
            title=title,
            archive_path=relative_archive_dir(project_root, package_dir),
        )

    if not row.get("供应商"):
        row["供应商"] = supplier
    if not row.get("变更内容"):
        row["变更内容"] = title
    row["归档路径"] = relative_archive_dir(project_root, package_dir)

    # PM 可手改 Change Log；已取消后 Skill 3 只归档往来，不再改状态/金额/卡片
    if is_cancelled(row):
        save_change_log(change_log, rows, fieldnames)
        return {
            "ok": True,
            "auto": False,
            "intent": intent,
            "change_no": change_no,
            "package_name": package_name,
            "status": CANCELLED_STATUS,
            "reason": "change_cancelled",
            "change_log": str(change_log),
            "archived": archived,
            "note": "变更已取消（含手改）。邮件已归档，不推进状态。",
            "did": ["change-archive.handle_change_email.archive_only"],
        }

    stamp = event_stamp(eml_path)

    if intent == "change.cod":
        row["当前状态"] = "COD 已发出"
        stamp_milestones(row, intent, stamp=stamp)
        estimate = extract_estimate_amount(subject, body, change_no=change_no)
        if estimate and not str(row.get("预估金额") or "").strip():
            row["预估金额"] = estimate
        time_impact = extract_time_impact(subject, body)
        if time_impact and not str(row.get("时间影响") or "").strip():
            row["时间影响"] = time_impact
    elif intent == "change.pmi":
        if not require_prior(row, "COD 已发出"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "PMI 先于 COD 建行到达，需人工确认是否补录 COD。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        if can_advance(row, "PMI 已发出"):
            row["当前状态"] = "PMI 已发出"
        stamp_milestones(row, intent, stamp=stamp)
    elif intent == "change.tech_submit":
        if would_skip(row, "技术审核中"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "技术文件提交跳级（尚缺 PMI 等前置状态），需人工确认。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        if can_advance(row, "技术审核中"):
            row["当前状态"] = "技术审核中"
        stamp_milestones(row, intent, stamp=stamp)
    elif intent == "change.tech_confirm":
        if would_skip(row, "技术确认"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "技术确认跳级（尚缺技术审核中等前置），需人工确认。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        if can_advance(row, "技术确认"):
            row["当前状态"] = "技术确认"
        stamp_milestones(row, intent, stamp=stamp)
    elif intent == "change.commercial":
        if not row.get("技术确认"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "技术确认尚未落账，不自动推进到商务确认。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        if would_skip(row, "商务确认"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "商务确认跳级，需人工确认前置状态。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        if can_advance(row, "商务确认"):
            row["当前状态"] = "商务确认"
        stamp_milestones(row, intent, stamp=stamp)
    elif intent == "change.commercial_amount":
        if not row.get("技术确认"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "技术确认尚未落账，不自动推进到商务金额确认。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        if would_skip(row, "商务金额确认"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "商务金额确认跳级（通常应先有商务确认），需人工确认。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        amount_excl, uncertain = extract_excl_amount(subject, body, change_no=change_no)
        if not amount_excl:
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "amount_unconfirmed",
                    "note": "无法确认不含税最终金额，未自动写入商务金额确认。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "amount_unconfirmed", "intent": intent}
        if can_advance(row, "商务金额确认"):
            row["当前状态"] = "商务金额确认"
        row["最终确认金额"] = amount_excl
        stamp_milestones(row, intent, stamp=stamp)
        if uncertain:
            note = str(row.get("备注") or "")
            extra = "金额来源邮件，税侧未展开"
            if extra not in note:
                row["备注"] = f"{note}；{extra}" if note else extra
        # 最终金额只写 Change Log；现金流/请款页直接读台账，不写履约卡片
    elif intent == "change.change_po":
        if not require_prior(row, "商务金额确认"):
            pid = add_pending(
                project_root,
                {
                    "step": "change_archive",
                    "fields": {"change_no": change_no, "package_name": package_name},
                    "subject": subject,
                    "eml_path": str(eml_path),
                    "reason": "out_of_order",
                    "note": "变更尚未到商务金额确认，不自动闭环 Change PO。",
                },
            )
            return {"auto": False, "pending_id": pid, "reason": "out_of_order", "intent": intent}
        if can_advance(row, "Change PO 下发"):
            row["当前状态"] = "Change PO 下发"
        stamp_milestones(row, intent, stamp=stamp)
        close_change_po_pending(project_root, change_no, package_name, eml_path)

    save_change_log(change_log, rows, fieldnames)
    return {
        "ok": True,
        "auto": True,
        "intent": intent,
        "change_no": change_no,
        "package_name": package_name,
        "status": row.get("当前状态") or "",
        "change_log": str(change_log),
        "archived": archived,
        "did": ["change-archive.handle_change_email"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--eml", required=True)
    ap.add_argument("--attachment", action="append", default=[])
    ap.add_argument("--route-json", default="")
    args = ap.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    eml_path = Path(args.eml).expanduser().resolve()
    msg = email.message_from_bytes(eml_path.read_bytes())
    subject = decode_mime_header(msg.get("Subject"))
    body = get_body_text(msg)
    classification = (
        json.loads(Path(args.route_json).expanduser().read_text(encoding="utf-8"))
        if args.route_json
        else {}
    )

    result = handle_change_mail(
        project_root=project_root,
        eml_path=eml_path,
        subject=subject,
        body=body,
        classification=classification,
        attachment_paths=args.attachment,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
