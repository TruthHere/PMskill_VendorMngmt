#!/usr/bin/env python3
"""Grade contract-fulfillment-struct eval outputs (strict, per eval type)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import (
    PROJECT_JSON,
    load_json,
    load_tracker_packages,
    resolve_tracker_path,
    system_file,
)
from eval_fixtures import PKG_NAME, SUPPLIER

_FC_SCRIPTS = Path(__file__).resolve().parents[1].parent / "fulfillment-card" / "scripts"
if str(_FC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_FC_SCRIPTS))
from render_card import validate_rendered_card  # noqa: E402

EVAL_TYPES = ("rfp", "po", "misroute_init", "misroute_change")


def po_reached(pkg: dict) -> bool:
    return bool((pkg.get("ts_po_issued") or "").strip()) or pkg.get("status") == "已发PO"


def rfp_reached(pkg: dict) -> bool:
    return bool((pkg.get("ts_rfp_issued") or "").strip()) or pkg.get("status") in {
        "待技术确认",
        "待报价确认",
        "已发PO",
        "已结算",
    }


def find_pkg_dir(output_root: Path, packages: list[dict]) -> Path | None:
    if packages:
        folder = (packages[0].get("folder_path") or "").strip()
        if folder and Path(folder).is_dir():
            return Path(folder)
        short = packages[0].get("supplier_short") or ""
        cand = output_root / f"01_{PKG_NAME}_{short}".rstrip("_")
        if cand.is_dir():
            return cand
    candidates = sorted(
        p for p in output_root.glob("01_*") if p.is_dir() and (p / "card-data.json").exists()
    )
    return candidates[0] if candidates else None


def load_process_result(output_root: Path) -> dict:
    for name in ("process_result.json", "result.json"):
        path = output_root / name
        if path.is_file():
            return load_json(path, {})
    return {}


def check_card_invocation(check, pkg_dir: Path | None) -> None:
    """Skill 1 must call fulfillment-card (data → card HTML + claim form), not hand-write HTML."""
    if not pkg_dir or not pkg_dir.is_dir():
        check("card-data.json exists (Skill 1 → fulfillment-card input)", False, "package dir missing")
        check("card HTML passes fulfillment-card template validation", False, "package dir missing")
        check("card HTML has payment-table (template fingerprint)", False, "package dir missing")
        check("请款申请.html exists (produced by payment-form via fulfillment-card)", False, "package dir missing")
        check("请款申请.html looks like claim-form template", False, "package dir missing")
        check("card has 发起请款 link to 请款申请.html", False, "package dir missing")
        check("card-data supplier_name filled by Skill 1", False, "package dir missing")
        return

    card_data_path = pkg_dir / "card-data.json"
    card_html_path = pkg_dir / "履约条件卡片.html"
    claim_path = pkg_dir / "请款申请.html"

    check(
        "card-data.json exists (Skill 1 → fulfillment-card input)",
        card_data_path.is_file(),
        str(card_data_path) if card_data_path.is_file() else "missing",
    )

    card_data = load_json(card_data_path, {}) if card_data_path.is_file() else {}
    html = card_html_path.read_text(encoding="utf-8") if card_html_path.is_file() else ""
    if card_html_path.is_file() and card_data:
        errors = validate_rendered_card(html, card_data)
        check(
            "card HTML passes fulfillment-card template validation",
            not errors,
            "ok" if not errors else "; ".join(errors[:3]),
        )
    else:
        check(
            "card HTML passes fulfillment-card template validation",
            False,
            "missing card HTML or card-data",
        )

    check(
        "card HTML has payment-table (template fingerprint)",
        'class="data-table payment-table"' in html,
        "found" if 'class="data-table payment-table"' in html else "missing payment-table",
    )

    claim_html = claim_path.read_text(encoding="utf-8") if claim_path.is_file() else ""
    check(
        "请款申请.html exists (produced by payment-form via fulfillment-card)",
        claim_path.is_file(),
        str(claim_path) if claim_path.is_file() else "missing",
    )
    # sync_claim_form template markers — hand-written stubs usually lack these
    claim_ok = (
        claim_path.is_file()
        and ('id="boot"' in claim_html or "getElementById(\"boot\")" in claim_html)
        and ("请款" in claim_html)
    )
    check(
        "请款申请.html looks like claim-form template",
        claim_ok,
        "template markers ok" if claim_ok else "missing id=boot / 请款 markers",
    )
    check(
        "card has 发起请款 link to 请款申请.html",
        'href="请款申请.html"' in html and "发起请款" in html,
        "found" if ('href="请款申请.html"' in html) else "missing claim link",
    )

    supplier = (card_data.get("supplier_name") or "").strip()
    check(
        "card-data supplier_name filled by Skill 1",
        bool(supplier) and (supplier == SUPPLIER or "BOSCH" in supplier),
        supplier or "empty",
    )


def check_process_pipeline(check, output_root: Path, result: dict, eval_type: str) -> None:
    """Require Skill 1 process_email-style pipeline evidence — not hand-waved notes."""
    pr_path = output_root / "process_result.json"
    check(
        "process_result.json exists (pipeline evidence)",
        pr_path.is_file(),
        str(pr_path) if pr_path.is_file() else "missing — likely hand-rolled without process_email",
    )
    if not result:
        check("process_result is non-empty JSON", False, "empty")
        return
    check("process_result is non-empty JSON", True, "ok")

    if eval_type == "misroute_init":
        check(
            "process_result came from mail classification path",
            bool(result.get("from_classification"))
            or str(result.get("intent") or "") == "project_init",
            f"from_classification={result.get('from_classification')} intent={result.get('intent')}",
        )
        return

    if eval_type == "rfp":
        check(
            "process_result intent is fulfillment.rfp",
            result.get("intent") == "fulfillment.rfp",
            f"intent={result.get('intent')}",
        )
        check(
            "process_result step is step1 and auto=true",
            result.get("step") == "step1" and bool(result.get("auto")),
            f"step={result.get('step')} auto={result.get('auto')}",
        )
        return

    if eval_type == "po":
        raise_po = result.get("raise_po") if isinstance(result.get("raise_po"), dict) else {}
        payment = result.get("payment") if isinstance(result.get("payment"), dict) else {}
        # Also accept flat process_result from a single combined run
        flat_ok = result.get("step") in {"step3", "step4_payment"} and bool(result.get("auto"))
        raise_ok = bool(raise_po.get("auto")) and raise_po.get("step") == "step3"
        pay_ok = bool(payment.get("auto")) and (
            payment.get("step") == "step4_payment"
            or int(payment.get("payment_nodes") or 0) >= 3
            or int(result.get("payment_nodes") or 0) >= 3
        )
        check(
            "process_result records Raise PO via pipeline (step3 auto)",
            raise_ok or flat_ok,
            f"raise_po.step={raise_po.get('step')} auto={raise_po.get('auto')} flat_step={result.get('step')}",
        )
        check(
            "process_result records payment terms via pipeline",
            pay_ok or (flat_ok and int(result.get("payment_nodes") or 0) >= 3),
            f"payment.step={payment.get('step')} payment_nodes={payment.get('payment_nodes') or result.get('payment_nodes')}",
        )


def detect_eval_type(output_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    marker = output_root / "eval_type.txt"
    if marker.is_file():
        return marker.read_text(encoding="utf-8").strip()
    name = output_root.name.lower()
    for key in EVAL_TYPES:
        if key.replace("_", "-") in name or key in name:
            return key
    if "rfp" in name:
        return "rfp"
    if "po" in name or "payment" in name:
        return "po"
    if "init" in name or "misroute" in name:
        return "misroute_init"
    raise SystemExit(f"Cannot detect eval type for {output_root}; pass --eval-type")


def grade_run(output_root: Path, eval_type: str) -> dict:
    expectations: list[dict] = []
    passed_count = 0
    output_root = output_root.expanduser().resolve()

    def check(text: str, ok: bool, evidence: str) -> None:
        nonlocal passed_count
        expectations.append({"text": text, "passed": bool(ok), "evidence": evidence})
        if ok:
            passed_count += 1

    project_json = system_file(output_root, PROJECT_JSON)
    tracker_csv = resolve_tracker_path(output_root)
    # Only count the standard procurement tracker name (not a random tracker.csv)
    tracker_ok = bool(
        tracker_csv
        and tracker_csv.is_file()
        and "procurement_packages_status_tracker" in tracker_csv.name
    )
    packages = load_tracker_packages(output_root) if tracker_ok else []
    pkg_dir = find_pkg_dir(output_root, packages)
    result = load_process_result(output_root)

    # Pipeline / process checks first — these discriminate Skill vs hand-rolled
    check_process_pipeline(check, output_root, result, eval_type)

    if eval_type == "misroute_init":
        reason = str(result.get("reason") or "")
        note = str(result.get("note") or "")
        check(
            "process_result reason is routed_to_skill0",
            reason == "routed_to_skill0",
            f"reason={reason or 'missing'}",
        )
        check(
            "note tells user to use Skill 0 / project-init",
            reason == "routed_to_skill0"
            and (
                "Skill 0" in note
                or "project-init" in note
                or "init_project" in note
                or "run_init" in note
            ),
            (note[:120] if note else "missing note"),
        )
        check(
            "no procurement package created by this mail",
            len(packages) == 0,
            f"packages={len(packages)}",
        )
        check(
            "no 01_* package folder created",
            not any(output_root.glob("01_*")),
            ",".join(p.name for p in output_root.glob("01_*")) or "none",
        )

    elif eval_type == "misroute_change":
        reason = str(result.get("reason") or "")
        check(
            "process_result reason is routed_to_skill3",
            reason == "routed_to_skill3",
            f"reason={reason or 'missing'}",
        )
        check(
            "Change PO / change intent not auto-archived by Skill 1",
            reason == "routed_to_skill3",
            f"step={result.get('step')} reason={reason}",
        )

    elif eval_type == "rfp":
        check(
            "project.json exists",
            project_json.is_file(),
            str(project_json) if project_json.is_file() else "missing",
        )
        check(
            "standard tracker CSV exists",
            tracker_ok,
            str(tracker_csv) if tracker_ok else (str(tracker_csv) if tracker_csv else "missing"),
        )
        check(
            "tracker has exactly one package",
            len(packages) == 1,
            f"count={len(packages)}",
        )
        if packages:
            check(
                "milestone RFP 发出 is set",
                rfp_reached(packages[0]),
                f"RFP 发出={packages[0].get('ts_rfp_issued', '')}",
            )
            check(
                "package name is BMS",
                (packages[0].get("package_name") or "") == PKG_NAME,
                packages[0].get("package_name", ""),
            )
        else:
            check("milestone RFP 发出 is set", False, "no package")
            check("package name is BMS", False, "no package")

        if pkg_dir and pkg_dir.is_dir():
            subdirs = [d.name for d in pkg_dir.iterdir() if d.is_dir()]
            has_all = all(
                any(s.startswith(prefix) for s in subdirs)
                for prefix in ["01_", "02_", "03_", "04_", "05_", "06_", "07_"]
            )
            check("package has 01~07 subfolders", has_all, ", ".join(subdirs) or "none")
            card = pkg_dir / "履约条件卡片.html"
            check("履约条件卡片.html exists", card.is_file(), str(card))
            mail_dir = pkg_dir / "07_往来文件"
            emls = list(mail_dir.glob("*.eml")) if mail_dir.is_dir() else []
            check("RFP .eml archived under 07_往来文件", bool(emls), f"count={len(emls)}")
        else:
            check("package has 01~07 subfolders", False, "package dir missing")
            check("履约条件卡片.html exists", False, "package dir missing")
            check("RFP .eml archived under 07_往来文件", False, "package dir missing")

        check_card_invocation(check, pkg_dir)

    elif eval_type == "po":
        check(
            "project.json exists",
            project_json.is_file(),
            str(project_json) if project_json.is_file() else "missing",
        )
        check(
            "tracker has a package",
            len(packages) >= 1,
            f"count={len(packages)}",
        )
        if packages:
            check(
                "milestone PO 已发起 is set",
                po_reached(packages[0]),
                f"PO 已发起={packages[0].get('ts_po_issued', '')}",
            )
            next_node = (packages[0].get("next_payment_node") or "").strip()
            check(
                "next_payment_node is populated",
                bool(next_node),
                next_node or "empty",
            )
        else:
            check("milestone PO 已发起 is set", False, "no package")
            check("next_payment_node is populated", False, "no package")

        if pkg_dir and pkg_dir.is_dir():
            card = pkg_dir / "履约条件卡片.html"
            check("履约条件卡片.html exists", card.is_file(), str(card))
            html = card.read_text(encoding="utf-8") if card.is_file() else ""
            check(
                "card HTML mentions 预付款",
                "预付款" in html,
                "found" if "预付款" in html else "not found",
            )
            check(
                "card HTML mentions 30%",
                "30%" in html,
                "found" if "30%" in html else "not found",
            )
            card_data = pkg_dir / "card-data.json"
            nodes = []
            if card_data.is_file():
                nodes = load_json(card_data, {}).get("payment_nodes") or []
            check(
                "card-data payment_nodes has 3 entries",
                len(nodes) == 3,
                f"count={len(nodes)}",
            )
            total_amt = ""
            if card_data.is_file():
                total_amt = str(load_json(card_data, {}).get("total_amount") or "").strip()
            tracker_incl = ""
            if packages:
                tracker_incl = (
                    packages[0].get("amount_incl_tax")
                    or packages[0].get("金额含税")
                    or ""
                ).strip()
            has_amt = bool(total_amt) or bool(tracker_incl) or ("1,280,000" in html) or ("1280000" in html)
            check(
                "PO amount written to tracker or card (含税)",
                has_amt,
                f"card={total_amt or 'empty'} tracker={tracker_incl or 'empty'}",
            )
        else:
            check("履约条件卡片.html exists", False, "package dir missing")
            check("card HTML mentions 预付款", False, "package dir missing")
            check("card HTML mentions 30%", False, "package dir missing")
            check("card-data payment_nodes has 3 entries", False, "package dir missing")
            check("PO amount written to tracker or card (含税)", False, "package dir missing")

        check_card_invocation(check, pkg_dir)

    else:
        raise SystemExit(f"Unknown eval type: {eval_type}")

    total = len(expectations)
    return {
        "eval_type": eval_type,
        "expectations": expectations,
        "summary": {
            "passed": passed_count,
            "total": total,
            "pass_rate": round(passed_count / total, 4) if total else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--eval-type", choices=EVAL_TYPES, default=None)
    args = parser.parse_args()
    eval_type = detect_eval_type(args.output_root, args.eval_type)
    result = grade_run(args.output_root, eval_type)
    out = args.output_root / "grading.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
