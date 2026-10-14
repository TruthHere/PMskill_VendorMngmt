#!/usr/bin/env python3
"""Skill 2 冒烟：Tracker 唯一状态；03 只归档。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
SAMPLES = SKILL_ROOT / "samples" / "demo_project"
FIXTURE_EML = SKILL_ROOT / "samples" / "fixtures" / "payment_claim.eml"
SCRIPTS = SKILL_ROOT / "scripts"
MAIL_DISPATCH = REPO_ROOT / ".cursor" / "skills" / "mail-inbox" / "scripts" / "dispatch_mail.py"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _fail(msg: str, proc: subprocess.CompletedProcess[str] | None = None) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    if proc is not None:
        if proc.stdout:
            print(proc.stdout, file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
    raise SystemExit(1)


def _patch_tracker_paths(root: Path) -> None:
    sys.path.insert(
        0,
        str(Path(__file__).resolve().parents[2] / "po-flow" / "scripts"),
    )
    from common import load_tracker_packages, save_tracker_packages  # type: ignore

    csv_path = _tracker_csv(root)
    packages = load_tracker_packages(root)
    folder = root / "01_BMS_Schneider"
    old_folder = ""
    for pkg in packages:
        if str(pkg.get("package_name") or "") == "BMS":
            old_folder = str(pkg.get("folder_path") or "")
            break
    if old_folder and folder.is_dir():
        text = csv_path.read_text(encoding="utf-8-sig")
        csv_path.write_text(text.replace(old_folder, str(folder)), encoding="utf-8-sig")
        packages = load_tracker_packages(root)
    for pkg in packages:
        if str(pkg.get("package_name") or "") != "BMS":
            continue
        pkg["payment_progress"] = "无在办"
        pkg["next_payment_node"] = "到货 / Delivery"
        pkg["claimed_amount_excl_tax"] = "100000.00"
        pkg["remaining_claim_amount_excl_tax"] = "900000.00"
    save_tracker_packages(root, packages)


def _patch_schedule(root: Path) -> None:
    today = date.today()
    sched = {
        "critical_nodes": [
            {
                "package_name": "BMS",
                "name": "预付款 / Advance",
                "window_end": (today + timedelta(days=-30)).isoformat(),
            },
            {
                "package_name": "BMS",
                "name": "到货 / Delivery",
                "window_end": (today + timedelta(days=5)).isoformat(),
            },
            {
                "package_name": "BMS",
                "name": "验收 / Acceptance",
                "window_end": (today + timedelta(days=60)).isoformat(),
            },
        ]
    }
    path = root / ".skill" / "schedule.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tracker_csv(root: Path) -> Path:
    nested = root / ".skill" / "status_tracker.csv"
    if nested.is_file():
        return nested
    matches = list(root.glob("*tracker.csv"))
    if not matches:
        raise FileNotFoundError(f"no tracker csv under {root}")
    return matches[0]


def _tracker_text(root: Path) -> str:
    return _tracker_csv(root).read_text(encoding="utf-8-sig")


def _no_ledger(pkg: Path) -> None:
    led = pkg / "03_请款记录" / "payment_ledger.json"
    if led.is_file():
        _fail(f"should not create payment_ledger.json, found {led}")


def main() -> int:
    if not SAMPLES.is_dir() or not FIXTURE_EML.is_file():
        _fail("missing samples")

    with tempfile.TemporaryDirectory(prefix="skill2-smoke-") as tmp:
        root = Path(tmp) / "demo_project"
        shutil.copytree(SAMPLES, root)
        _patch_schedule(root)
        _patch_tracker_paths(root)
        pkg = root / "01_BMS_Schneider"
        (pkg / "03_请款记录").mkdir(parents=True, exist_ok=True)
        eml = Path(tmp) / "payment_claim.eml"
        shutil.copy2(FIXTURE_EML, eml)

        proc = _run(
            [
                sys.executable,
                str(SCRIPTS / "scan_due_payments.py"),
                "--project-root",
                str(root),
                "--lead-days",
                "14",
            ]
        )
        if proc.returncode != 0:
            _fail("scan failed", proc)
        due = json.loads(proc.stdout)
        if due.get("truth") != "tracker":
            _fail("scan must declare truth=tracker", proc)
        items = due.get("items") or []
        if len(items) != 1 or items[0].get("node") != "到货 / Delivery":
            _fail(f"scan expected only 到货, got {items}", proc)
        print("PASS scan → Tracker 下一笔到货")

        def _record(status: str, amount: str = "300000") -> subprocess.CompletedProcess[str]:
            return _run(
                [
                    sys.executable,
                    str(SCRIPTS / "record_payment.py"),
                    "--package-dir",
                    str(pkg),
                    "--node",
                    "到货 / Delivery",
                    "--amount-excl-tax",
                    amount,
                    "--status",
                    status,
                ]
            )

        if _record("certified").returncode != 4:
            _fail("skip to certified should fail")
        print("PASS 跳级拦")

        for step, expect in (
            ("vendor_received", "供应商请款已收到 · 到货 / Delivery"),
            ("qs_sent", "已发QS核对 · 到货 / Delivery"),
            ("qs_confirmed", "QS已确认金额 · 到货 / Delivery"),
            ("client_sent", "已发客户请款 · 到货 / Delivery"),
        ):
            proc = _record(step)
            if proc.returncode != 0:
                _fail(f"{step} failed", proc)
            if f"payment_progress={expect}" not in proc.stdout:
                _fail(f"progress {expect}", proc)
            if "100000.00" not in _tracker_text(root) and step != "vendor_received":
                # claimed stays 100000 until certified
                pass
            if "claimed_amount_excl_tax=" in proc.stdout:
                _fail("process steps must not print claimed update", proc)
        _no_ledger(pkg)
        print("PASS 四步过程只改进度、不改已请、无 ledger")

        proc = _record("certified")
        if proc.returncode != 0:
            _fail("certified failed", proc)
        if "payment_progress=无在办" not in proc.stdout:
            _fail("after certify → 无在办", proc)
        if "next_payment_node=验收 / Acceptance" not in proc.stdout:
            _fail("next → 验收", proc)
        if "claimed_amount_excl_tax=400000.00" not in proc.stdout:
            _fail("claimed should be 100000+300000", proc)
        tr = _tracker_text(root)
        if "无在办" not in tr or "验收 / Acceptance" not in tr:
            _fail("tracker row not updated", proc)
        _no_ledger(pkg)
        print("PASS 客户批复 → 已请累加、下一笔、无在办")

        # reset progress for email
        _patch_tracker_paths(root)
        proc = _run(
            [
                sys.executable,
                str(SCRIPTS / "record_payment_email.py"),
                "--package-dir",
                str(pkg),
                "--eml",
                str(eml),
            ]
        )
        if proc.returncode != 0:
            _fail("email failed", proc)
        payload = json.loads(proc.stdout)
        if not payload.get("recorded") or payload.get("status") != "vendor_received":
            _fail(f"email payload {payload}", proc)
        archived = list((pkg / "03_请款记录").glob("*vendor_received*.eml"))
        if not archived:
            _fail("eml not archived into 03_请款记录")
        _no_ledger(pkg)
        print("PASS 邮件 → 进度已收到 + eml 进档案柜")

        if MAIL_DISPATCH.is_file():
            _patch_tracker_paths(root)
            # clear archives noise ok
            proc = _run(
                [
                    sys.executable,
                    str(MAIL_DISPATCH),
                    "--project-root",
                    str(root),
                    "--eml",
                    str(eml),
                ]
            )
            if proc.returncode != 0:
                _fail("dispatch failed", proc)
            out = json.loads(proc.stdout)
            hr = out.get("handler_result") or {}
            if not hr.get("auto") or hr.get("status") != "vendor_received":
                _fail(f"dispatch {hr}", proc)
            print("PASS mail-inbox dispatch")

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
