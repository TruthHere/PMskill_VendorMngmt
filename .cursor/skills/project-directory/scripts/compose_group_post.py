#!/usr/bin/env python3
"""Compose a WeCom group post + fill-in page for Project Directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from directory_store import (  # noqa: E402
    load_store,
    project_meta,
    save_store,
    share_dir,
    upsert_request,
)
from common import now_iso  # noqa: E402
from write_directory_xlsx import write_directory_xlsx  # noqa: E402

_FORM_TEMPLATE = _SKILL_ROOT / "assets" / "fill-form.html"

GROUP_TEMPLATE = """【项目通讯录 / Project Directory】{project}

请各位供应商在本群回复贵司本项目对接人（姓名、Title、手机、邮箱）。
直接回群即可，不必发邮件。

也可以打开群文件里的「填写页.html」，填完点「复制回群」再粘贴过来。

采购包：
{package_lines}

回复请用下面格式（可复制；一位对接人一块，可多块）：

[PDIR]
采购包：（例如 BMS）
供应商：

---
姓名 / Name：
Title：
手机 / Mobile：
邮箱 / Email：
---

谢谢。
{pm_name}
"""


def _package_lines(packages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for pkg in packages:
        seq = str(pkg.get("seq") or "").strip()
        name = str(pkg.get("package_name") or "").strip()
        if not name:
            continue
        supplier = str(pkg.get("supplier_short") or pkg.get("supplier_name") or "").strip()
        prefix = f"{seq} " if seq else ""
        tail = f" · {supplier}" if supplier else ""
        lines.append(f"- {prefix}{name}{tail}")
    return "\n".join(lines) if lines else "- （Tracker 里还没有采购包，先写上贵司包名）"


def _write_fill_form(path: Path, meta: dict[str, Any]) -> Path:
    packages = []
    for pkg in meta["packages"]:
        name = str(pkg.get("package_name") or "").strip()
        if not name:
            continue
        packages.append(
            {
                "seq": pkg.get("seq") or "",
                "package_name": name,
                "supplier_name": pkg.get("supplier_name") or "",
                "supplier_short": pkg.get("supplier_short") or "",
            }
        )
    html = _FORM_TEMPLATE.read_text(encoding="utf-8")
    pm = str(meta.get("pm") or "").strip()
    pm_line = f"有问题找 {pm}。" if pm else ""
    html = (
        html.replace("__PROJECT_NAME__", str(meta["project_name"]))
        .replace("__PM_LINE__", pm_line)
        .replace("__PACKAGES_JSON__", json.dumps(packages, ensure_ascii=False))
    )
    path.write_text(html, encoding="utf-8")
    return path


def compose_group_post(
    project_root: Path,
    *,
    mark_posted: bool = False,
    write_xlsx: bool = True,
) -> dict[str, Any]:
    meta = project_meta(project_root)
    store = load_store(meta["root"])
    store["project_name"] = meta["project_name"]
    dest = share_dir(meta["root"])
    message = GROUP_TEMPLATE.format(
        project=meta["project_name"],
        package_lines=_package_lines(meta["packages"]),
        pm_name=meta["pm"] or "项目经理",
    ).strip() + "\n"
    msg_path = dest / "群消息.txt"
    form_path = dest / "填写页.html"
    msg_path.write_text(message, encoding="utf-8")
    _write_fill_form(form_path, meta)

    status = "posted" if mark_posted else "ready"
    stamp_key = "posted_at" if mark_posted else "ready_at"
    stamp = now_iso()
    for pkg in meta["packages"]:
        name = str(pkg.get("package_name") or "").strip()
        if not name:
            continue
        existing = next((r for r in store["requests"] if r.get("package_name") == name), {})
        if existing.get("status") == "replied":
            continue
        upsert_request(
            store,
            {
                **existing,
                "package_name": name,
                "supplier_name": pkg.get("supplier_name") or existing.get("supplier_name") or "",
                "supplier_short": pkg.get("supplier_short") or existing.get("supplier_short") or "",
                "seq": pkg.get("seq") or existing.get("seq") or "",
                "status": status,
                stamp_key: stamp,
                "posted_at": stamp if mark_posted else existing.get("posted_at") or "",
                "channel": "wecom_group",
                "group_message_path": str(msg_path),
                "fill_form_path": str(form_path),
                "error": "",
            },
        )

    store["channel"] = "wecom_group"
    store["group_message_path"] = str(msg_path)
    store["fill_form_path"] = str(form_path)
    save_store(meta["root"], store)
    xlsx = str(write_directory_xlsx(meta["root"], store)) if write_xlsx else ""
    return {
        "ok": True,
        "auto": True,
        "did": ["directory.compose"],
        "channel": "wecom_group",
        "group_message": message,
        "group_message_path": str(msg_path),
        "fill_form_path": str(form_path),
        "xlsx_path": xlsx,
        "status": status,
        "packages": [str(p.get("package_name") or "") for p in meta["packages"] if p.get("package_name")],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--mark-posted", action="store_true", help="PM already sent the group message")
    args = ap.parse_args()
    out = compose_group_post(Path(args.project_root), mark_posted=args.mark_posted)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
