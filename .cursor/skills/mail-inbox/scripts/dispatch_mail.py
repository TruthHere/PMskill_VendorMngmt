#!/usr/bin/env python3
"""Classify then dispatch one .eml (or Outlook .msg) to Skill 0/1/2/3 handlers."""

from __future__ import annotations

import argparse
import email
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SKILLS = _SCRIPTS.parents[1]
_FC_SCRIPTS = _SKILLS / "po-flow" / "scripts"
_PR_SCRIPTS = _SKILLS / "payment-flow" / "scripts"
_CA_SCRIPTS = _SKILLS / "change-flow" / "scripts"
_PI_SCRIPTS = _SKILLS / "new-project" / "scripts"
_FOUNDATION = _SKILLS.parent / "lib" / "project-foundation" / "scripts"

for path in (_SCRIPTS, _FOUNDATION, _FC_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from classify_mail import (  # noqa: E402
    classify_from_message,
    collect_attachment_meta,
    decode_mime_header,
    get_body_text,
)
from common import load_tracker_packages  # noqa: E402
from msg_to_eml import load_mail, stage_msg_as_eml  # noqa: E402
from pending_store import add_pending  # noqa: E402
from process_email import (  # noqa: E402
    find_package_fuzzy,
    process_eml_file,
    slug_package_name,
)


def dispatch_project_init(
    project_root: Path | None,
    eml_path: Path,
    classification: dict[str, Any],
    *,
    subject: str,
) -> dict[str, Any]:
    route_path = None
    if project_root is not None:
        route_path = (
            project_root.expanduser().resolve()
            / ".skill"
            / "inbox"
            / "processed"
            / f"{eml_path.stem}.route.json"
        )
        route_path.parent.mkdir(parents=True, exist_ok=True)
        route_path.write_text(json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")

    script = _PI_SCRIPTS / "handle_init_email.py"
    cmd = [sys.executable, str(script), "--eml", str(eml_path)]
    if project_root is not None:
        cmd.extend(["--project-root", str(project_root.expanduser().resolve())])
    if route_path is not None:
        cmd.extend(["--route-json", str(route_path)])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        note = (proc.stderr or proc.stdout or "new-project handler failed").strip()[:500]
        if project_root is None:
            return {
                "intent": "project_init",
                "route_to": "new-project",
                "reason": "project_init_handler_failed",
                "note": note,
                "auto": False,
            }
        pid = add_pending(
            project_root.expanduser().resolve(),
            {
                "step": "project_init",
                "fields": classification.get("hints") or {},
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "project_init_handler_failed",
                "note": note,
            },
            skill="new-project",
        )
        return {
            "intent": "project_init",
            "route_to": "new-project",
            "pending_id": pid,
            "reason": "project_init_handler_failed",
            "auto": False,
        }

    payload = (proc.stdout or "").strip()
    return json.loads(payload) if payload else {"ok": True, "intent": "project_init", "auto": True}


def classify_eml(
    project_root: Path | None,
    eml_path: Path,
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    eml_path = eml_path.expanduser().resolve()
    msg = load_mail(eml_path)
    subject = decode_mime_header(msg.get("Subject"))
    body = get_body_text(msg)
    attachments = collect_attachment_meta(msg)
    if attachment_paths:
        saved = {Path(p).name.lower() for p in attachment_paths}
        for item in attachments:
            if item.get("filename", "").lower() in saved:
                item["path"] = next(
                    p for p in attachment_paths if Path(p).name.lower() == item["filename"].lower()
                )
    return classify_from_message(
        subject=subject,
        body=body,
        eml_path=str(eml_path),
        project_root=str(project_root) if project_root else "",
        attachments=attachments,
    )


def write_classification_pending(
    project_root: Path,
    eml_path: Path,
    subject: str,
    classification: dict[str, Any],
) -> str:
    pending = classification.get("pending") or {}
    pid = add_pending(
        project_root,
        {
            "step": classification.get("intent") or "unknown",
            "fields": classification.get("hints") or {},
            "subject": subject,
            "eml_path": str(eml_path),
            "reason": pending.get("reason") or "intent_low_confidence",
            "note": pending.get("question") or "邮件意图置信度低，需人工确认路由。",
            "candidates": pending.get("candidates"),
        },
        skill="mail-inbox",
    )
    return pid


def resolve_package_dir(project_root: Path, hints: dict[str, str]) -> Path | None:
    package_name = (hints.get("package_name") or "").strip()
    if not package_name:
        return None
    if re.search(r"[A-Za-z]", package_name):
        package_name = slug_package_name(package_name)
    else:
        package_name = re.sub(r"[（(].*$", "", package_name).strip()
    packages = load_tracker_packages(project_root)
    pkg = find_package_fuzzy(packages, package_name)
    if not pkg:
        return None
    project_root = project_root.expanduser().resolve()
    folder = Path(str(pkg.get("folder_path") or ""))
    if not folder.is_absolute():
        folder = (project_root / folder).resolve()
    else:
        folder = folder.expanduser().resolve()
        try:
            folder.relative_to(project_root)
        except ValueError:
            # Absolute path from another copy/sample — remap by directory name under this project
            candidate = project_root / folder.name
            if candidate.is_dir():
                folder = candidate.resolve()
    if not folder.is_dir():
        candidate = project_root / folder.name
        if candidate.is_dir():
            folder = candidate.resolve()
    return folder if folder.is_dir() else None


INTENT_TO_STATUS = {
    "payment_claim.inbound": "vendor_received",
    "payment_claim.qs_sent": "qs_sent",
    "payment_claim.qs_confirm": "qs_confirmed",
    "payment_claim.client_sent": "client_sent",
    "payment_claim.client_approved": "certified",
}


def dispatch_payment_claim(
    project_root: Path,
    eml_path: Path,
    classification: dict[str, Any],
    *,
    subject: str,
) -> dict[str, Any]:
    intent = str(classification.get("intent") or "payment_claim.inbound")
    status = INTENT_TO_STATUS.get(intent, "vendor_received")
    hints = classification.get("hints") or {}
    pkg_dir = resolve_package_dir(project_root, hints)
    if not pkg_dir:
        pid = add_pending(
            project_root,
            {
                "step": intent,
                "fields": hints,
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "package_ambiguous",
                "note": "请款邮件已分类，但无法唯一匹配采购包目录。",
            },
            skill="payment-flow",
        )
        return {
            "intent": intent,
            "route_to": "payment-flow",
            "pending_id": pid,
            "reason": "package_ambiguous",
            "auto": False,
        }

    script = _PR_SCRIPTS / "record_payment_email.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--package-dir",
            str(pkg_dir),
            "--eml",
            str(eml_path),
            "--status",
            status,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 4:
        payload = {}
        try:
            payload = json.loads((proc.stdout or "").strip() or "{}")
        except json.JSONDecodeError:
            payload = {}
        pid = add_pending(
            project_root,
            {
                "step": intent,
                "fields": {
                    **hints,
                    "package_dir": str(pkg_dir),
                    "target_status": status,
                    "current_status": payload.get("current_status"),
                    "payment_no": payload.get("payment_no"),
                },
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "payment_claim_out_of_order",
                "note": (
                    "请款阶段跳步：当前是"
                    f"{payload.get('current_label') or '尚未建行'}，"
                    f"来件想进「{payload.get('target_label') or status}」。需人工确认或先补前面步骤。"
                ),
            },
            skill="payment-flow",
        )
        return {
            "intent": intent,
            "route_to": "payment-flow",
            "ok": False,
            "auto": False,
            "pending_id": pid,
            "reason": "payment_claim_out_of_order",
            "recorded": False,
            "parsed": payload,
        }
    if proc.returncode != 0:
        pid = add_pending(
            project_root,
            {
                "step": intent,
                "fields": {**hints, "package_dir": str(pkg_dir), "target_status": status},
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "payment_claim_parse_failed",
                "note": (proc.stderr or proc.stdout or "record_payment_email failed").strip()[:500],
            },
            skill="payment-flow",
        )
        return {
            "intent": intent,
            "route_to": "payment-flow",
            "pending_id": pid,
            "reason": "payment_claim_parse_failed",
            "auto": False,
        }

    payload = (proc.stdout or "").strip()
    parsed = json.loads(payload) if payload else {}
    return {
        "intent": intent,
        "route_to": "payment-flow",
        "ok": True,
        "auto": True,
        "recorded": bool(parsed.get("recorded")),
        "status": status,
        "parsed": {
            "payment_no": parsed.get("payment_no"),
            "node": parsed.get("node"),
            "amount_excl_tax": parsed.get("amount_excl_tax"),
            "package_dir": str(pkg_dir),
            "status": status,
        },
        "did": list(parsed.get("did") or ["payment-flow.record_payment"]),
    }


def dispatch_change(
    project_root: Path,
    eml_path: Path,
    classification: dict[str, Any],
    *,
    subject: str,
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    intent = classification.get("intent") or ""
    route_path = project_root / ".skill" / "inbox" / "processed" / f"{eml_path.stem}.route.json"
    route_path.parent.mkdir(parents=True, exist_ok=True)
    route_path.write_text(json.dumps(classification, ensure_ascii=False, indent=2), encoding="utf-8")

    script = _CA_SCRIPTS / "handle_change_email.py"
    cmd = [
        sys.executable,
        str(script),
        "--project-root",
        str(project_root),
        "--eml",
        str(eml_path),
        "--route-json",
        str(route_path),
    ]
    for att in attachment_paths or []:
        cmd.extend(["--attachment", str(att)])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        hints = classification.get("hints") or {}
        pid = add_pending(
            project_root,
            {
                "step": intent,
                "fields": hints,
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "change_handler_failed",
                "note": (proc.stderr or proc.stdout or "change handler failed").strip()[:500],
            },
            skill="change-flow",
        )
        return {
            "intent": intent,
            "route_to": "change-flow",
            "pending_id": pid,
            "reason": "change_handler_failed",
            "auto": False,
        }

    payload = (proc.stdout or "").strip()
    return json.loads(payload) if payload else {"ok": True, "intent": intent, "auto": True}


def dispatch_eml_file(
    project_root: Path | None,
    eml_path: Path,
    attachment_paths: list[str] | None = None,
) -> dict[str, Any]:
    eml_path = eml_path.expanduser().resolve()
    if eml_path.suffix.lower() == ".msg":
        eml_path = stage_msg_as_eml(eml_path)

    classification = classify_eml(project_root, eml_path, attachment_paths)
    msg = email.message_from_bytes(eml_path.read_bytes())
    subject = decode_mime_header(msg.get("Subject"))

    result: dict[str, Any] = {
        "ok": True,
        "eml_path": str(eml_path),
        "classification": classification,
        "intent": classification.get("intent"),
        "route_to": classification.get("route_to"),
        "confidence": classification.get("confidence"),
        "did": list(classification.get("did") or []) + ["dispatch"],
    }

    if classification.get("pending"):
        if project_root is None:
            result["handler_result"] = {
                "reason": "missing_project",
                "auto": False,
                "note": "低置信度邮件需要 project_root 才能写入 pending。",
            }
            return result
        pid = write_classification_pending(project_root.expanduser().resolve(), eml_path, subject, classification)
        result["handler_result"] = {
            "pending_id": pid,
            "reason": classification["pending"].get("reason"),
            "auto": False,
        }
        return result

    route = classification.get("route_to")
    if route == "new-project":
        handler = dispatch_project_init(
            project_root,
            eml_path,
            classification,
            subject=subject,
        )
    elif route == "po-flow":
        handler = process_eml_file(
            project_root,
            eml_path,
            attachment_paths=attachment_paths,
            classification=classification,
        )
    elif route == "payment-flow":
        if project_root is None:
            raise ValueError("project_root required for payment_claim mail")
        handler = dispatch_payment_claim(
            project_root.expanduser().resolve(),
            eml_path,
            classification,
            subject=subject,
        )
    elif route == "change-flow":
        if project_root is None:
            raise ValueError("project_root required for change mail")
        handler = dispatch_change(
            project_root.expanduser().resolve(),
            eml_path,
            classification,
            subject=subject,
            attachment_paths=attachment_paths,
        )
    else:
        if project_root is None:
            result["handler_result"] = {"reason": "unknown_intent", "auto": False}
            return result
        pid = add_pending(
            project_root.expanduser().resolve(),
            {
                "step": classification.get("intent") or "unknown",
                "fields": classification.get("hints") or {},
                "subject": subject,
                "eml_path": str(eml_path),
                "reason": "unknown_intent",
            },
            skill="mail-inbox",
        )
        handler = {"pending_id": pid, "reason": "unknown_intent", "auto": False}

    result["handler_result"] = handler
    result["auto"] = bool(handler.get("auto"))
    if handler.get("pending_id"):
        result["pending_id"] = handler["pending_id"]
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", default="")
    ap.add_argument("--eml", required=True)
    ap.add_argument("--attachment", action="append", default=[])
    ap.add_argument("--classify-only", action="store_true")
    args = ap.parse_args()

    root = Path(args.project_root).expanduser().resolve() if args.project_root else None
    eml = Path(args.eml).expanduser().resolve()

    if args.classify_only:
        out = classify_eml(root, eml, args.attachment or None)
    else:
        out = dispatch_eml_file(
            root,
            eml,
            attachment_paths=args.attachment or None,
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
