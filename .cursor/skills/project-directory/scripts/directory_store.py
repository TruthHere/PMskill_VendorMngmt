#!/usr/bin/env python3
"""Project Directory store: JSON, contact parse, package match."""

from __future__ import annotations

import re
import sys
from email.utils import parseaddr
from pathlib import Path
from typing import Any

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_CURSOR = _SKILL_ROOT.parents[1]
_FOUNDATION = _CURSOR / "lib" / "project-foundation" / "scripts"
if str(_FOUNDATION) not in sys.path:
    sys.path.insert(0, str(_FOUNDATION))

from common import (  # noqa: E402
    PROJECT_JSON,
    load_json,
    load_tracker_packages,
    now_iso,
    project_archive_dir,
    save_json,
    sanitize_filename,
    system_file,
)
from pending_store import add_pending as store_add_pending  # noqa: E402

DIRECTORY_JSON = "directory.json"
XLSX_SUFFIX = "_项目通讯录.xlsx"

_QUOTE_SPLIT = re.compile(
    r"\n(?:-{2,}\s*)?(?:Original Message|转发的原始邮件|原始邮件|发件人\s*[:：]|From\s*:)",
    re.I,
)
_RECORD_START = re.compile(r"^(?:姓名|Name)(?:\s*/\s*[^\s:：]+)?\s*[:：]", re.I | re.M)
_PKG_LINE = re.compile(r"^(?:采购包|Package)\s*[:：]\s*(.+)$", re.I | re.M)
_SUP_LINE = re.compile(r"^(?:供应商|Supplier)\s*[:：]\s*(.+)$", re.I | re.M)
_PDIR = re.compile(r"\[PDIR\]|\[Project Directory\]|\[项目通讯录\]", re.I)


def directory_path(project_root: Path) -> Path:
    return system_file(project_root, DIRECTORY_JSON)


def xlsx_path_for(project_root: Path, project_name: str) -> Path:
    safe = sanitize_filename(project_name or "项目", 80) or "项目"
    return project_root.expanduser().resolve() / f"{safe}{XLSX_SUFFIX}"


def share_dir(project_root: Path) -> Path:
    path = project_archive_dir(project_root, create=True) / "05_项目通讯录"
    path.mkdir(parents=True, exist_ok=True)
    return path


def empty_store(project_name: str = "") -> dict[str, Any]:
    return {
        "version": 1,
        "project_name": project_name,
        "updated_at": now_iso(),
        "xlsx_path": "",
        "requests": [],
        "contacts": [],
    }


def load_store(project_root: Path) -> dict[str, Any]:
    data = load_json(directory_path(project_root), None)
    if not isinstance(data, dict):
        project = load_json(system_file(project_root, PROJECT_JSON), {}) or {}
        return empty_store(str(project.get("project_name") or ""))
    data.setdefault("version", 1)
    data.setdefault("requests", [])
    data.setdefault("contacts", [])
    return data


def save_store(project_root: Path, store: dict[str, Any]) -> Path:
    store["updated_at"] = now_iso()
    path = directory_path(project_root)
    save_json(path, store)
    return path


def split_emails(raw: str) -> list[str]:
    seen: list[str] = []
    for part in re.split(r"[;,\s]+", raw or ""):
        addr = part.strip().strip("<>").lower()
        if "@" in addr and addr not in seen:
            seen.append(addr)
    return seen


def project_meta(project_root: Path) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    project = load_json(system_file(root, PROJECT_JSON), {}) or {}
    return {
        "root": root,
        "project": project,
        "project_name": str(project.get("project_name") or root.name),
        "project_code": str(project.get("project_code") or ""),
        "pm": str(project.get("project_manager") or project.get("pm") or ""),
        "mailbox": project.get("mailbox") or {},
        "packages": load_tracker_packages(root),
    }


def strip_quoted(body: str) -> str:
    text = _QUOTE_SPLIT.split(body or "", maxsplit=1)[0]
    lines: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith(">"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


_LABEL_LIKE = re.compile(
    r"^(?:姓名|Name|Title|职称|职位|职务|头衔|手机号?|电话|Mobile|Tel|Phone|邮箱|E-?mail)"
    r"(?:[ \t]*/[ \t]*\S+)?[ \t]*[:：]?[ \t]*$",
    re.I,
)


def _field(blob: str, aliases: str) -> str:
    m = re.search(
        rf"(?m)^(?:{aliases})(?:[ \t]*/[ \t]*[^\s:：]+)?[ \t]*[:：][ \t]*(.*?)\s*$",
        blob,
        re.I,
    )
    if not m:
        return ""
    value = m.group(1).strip()
    value = re.sub(r"\s{2,}", " ", value)
    if not value or value in {"-", "—", "/", "无", "n/a", "N/A"}:
        return ""
    if _LABEL_LIKE.match(value):
        return ""
    return value


def parse_contact_blocks(body: str) -> list[dict[str, str]]:
    text = strip_quoted(body)
    if not text:
        return []
    starts = list(_RECORD_START.finditer(text))
    chunks: list[str]
    if len(starts) >= 2:
        chunks = []
        for i, match in enumerate(starts):
            end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
            chunks.append(text[match.start() : end])
    else:
        chunks = [c.strip() for c in re.split(r"\n\s*-{3,}\s*\n", text) if c.strip()]
        if len(chunks) <= 1:
            chunks = [text]

    contacts: list[dict[str, str]] = []
    for chunk in chunks:
        name = _field(chunk, r"姓名|Name")
        title = _field(chunk, r"Title|职称|职位|职务|头衔")
        phone = _field(chunk, r"手机号?|电话|Mobile|Tel|Phone")
        email = _field(chunk, r"邮箱|E-?mail")
        if email:
            _n, addr = parseaddr(email)
            email = (addr or email).strip().lower()
            if "@" not in email:
                email = ""
        phone = re.sub(r"[\s\-]+", "", phone)
        if not name and not email:
            continue
        contacts.append(
            {
                "name": name,
                "title": title,
                "phone": phone,
                "email": email,
            }
        )
    return contacts


def extract_package_hints(subject: str, body: str) -> dict[str, str]:
    text = strip_quoted(body)
    hints: dict[str, str] = {}
    m = _PKG_LINE.search(text)
    if m:
        hints["package_name"] = m.group(1).strip()
    m = _SUP_LINE.search(text)
    if m:
        hints["supplier_hint"] = m.group(1).strip()
    subj = re.sub(r"\s+", " ", (subject or "").replace("\r", " ").replace("\n", " "))
    subj = re.sub(r"^(?:FW|Fwd|RE|回复|答复)\s*[:：]\s*", "", subj, flags=re.I)
    triple = re.match(
        r"^\s*([^·—\-]+)\s*[·•]\s*([^·—\-]+)\s*[·•]\s*([^—\-]+)",
        subj,
    )
    if triple:
        hints.setdefault("project_code", triple.group(1).strip())
        hints.setdefault("package_name", triple.group(2).strip())
        supplier = re.sub(r"\s*[—\-].*$", "", triple.group(3)).strip()
        hints.setdefault("supplier_hint", supplier)
    return hints


def split_pdir_sections(body: str) -> list[str]:
    text = strip_quoted(body or "")
    if not text:
        return []
    parts = re.split(r"(?=\[PDIR\]|\[Project Directory\]|\[项目通讯录\])", text, flags=re.I)
    sections = [p.strip() for p in parts if p.strip() and _PDIR.search(p)]
    if sections:
        return sections
    if _RECORD_START.search(text) or _PKG_LINE.search(text):
        return [text]
    return []


def is_directory_text(text: str) -> bool:
    blob = text or ""
    if _PDIR.search(blob):
        return True
    if _RECORD_START.search(blob) and _field(blob, r"手机号?|电话|Mobile|邮箱|E-?mail"):
        return True
    return False


def match_package(
    packages: list[dict[str, Any]],
    *,
    package_name: str = "",
    supplier_hint: str = "",
    from_addr: str = "",
) -> dict[str, Any] | None:
    name = (package_name or "").strip()
    supplier = (supplier_hint or "").strip()
    addr = (from_addr or "").strip().lower()

    def _norm(s: str) -> str:
        return re.sub(r"\s+", "", s).lower()

    if name:
        exact = [p for p in packages if _norm(p.get("package_name") or "") == _norm(name)]
        if len(exact) == 1:
            return exact[0]
        fuzzy = [
            p
            for p in packages
            if _norm(name) in _norm(p.get("package_name") or "")
            or _norm(p.get("package_name") or "") in _norm(name)
        ]
        if len(fuzzy) == 1:
            return fuzzy[0]
        if supplier and fuzzy:
            by_sup = [
                p
                for p in fuzzy
                if _norm(supplier) in _norm(p.get("supplier_short") or "")
                or _norm(supplier) in _norm(p.get("supplier_name") or "")
            ]
            if len(by_sup) == 1:
                return by_sup[0]

    if addr:
        hits = []
        for pkg in packages:
            emails = split_emails(str(pkg.get("contact_email") or ""))
            if addr in emails:
                hits.append(pkg)
        if len(hits) == 1:
            return hits[0]
    return None


def upsert_request(store: dict[str, Any], request: dict[str, Any]) -> None:
    key = str(request.get("package_name") or "")
    for i, item in enumerate(store["requests"]):
        if str(item.get("package_name") or "") == key:
            merged = {**item, **request}
            store["requests"][i] = merged
            return
    store["requests"].append(request)


def upsert_contacts(store: dict[str, Any], package_name: str, contacts: list[dict[str, Any]]) -> int:
    existing = [
        c for c in store["contacts"] if str(c.get("package_name") or "") != package_name
    ]
    current = [
        c for c in store["contacts"] if str(c.get("package_name") or "") == package_name
    ]
    by_email = {(c.get("email") or "").lower(): c for c in current if c.get("email")}
    by_name = {(c.get("name") or "").strip().lower(): c for c in current if c.get("name")}
    wrote = 0
    for person in contacts:
        email = (person.get("email") or "").lower()
        name_key = (person.get("name") or "").strip().lower()
        target = None
        if email and email in by_email:
            target = by_email[email]
        elif name_key and name_key in by_name:
            target = by_name[name_key]
        if target is None:
            row = dict(person)
            current.append(row)
            if email:
                by_email[email] = row
            if name_key:
                by_name[name_key] = row
            wrote += 1
        else:
            for field in ("name", "title", "phone", "email", "supplier_name", "seq", "source"):
                if person.get(field):
                    target[field] = person[field]
            target["updated_at"] = person.get("updated_at") or now_iso()
            wrote += 1
    store["contacts"] = existing + current
    return wrote


def request_for(store: dict[str, Any], package_name: str) -> dict[str, Any] | None:
    for item in store.get("requests") or []:
        if str(item.get("package_name") or "") == package_name:
            return item
    return None


def status_label(status: str) -> str:
    return {
        "ready": "待发群消息",
        "posted": "已发群待回",
        "replied": "已收录",
        "missing_email": "待发群消息",
        "draft": "待发群消息",
        "sent": "已发群待回",
        "failed": "待发群消息",
    }.get(status, status or "待发群消息")


def add_directory_pending(project_root: Path, item: dict[str, Any]) -> str:
    return store_add_pending(project_root, item, skill="project-directory")
