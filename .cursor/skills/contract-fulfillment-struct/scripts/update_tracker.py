#!/usr/bin/env python3
"""Update tracker.csv: add package, update fields, status transitions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    CARD_DATA_FILENAME,
    CARD_FILENAME,
    PROJECT_JSON,
    default_card_data,
    find_package,
    first_pending_payment_node,
    load_json,
    load_tracker_packages,
    merge_contact_emails,
    now_iso,
    package_folder_name,
    resolve_milestone_key,
    resolve_tracker_path,
    save_json,
    save_tracker_packages,
    stamp_milestone,
    subdirs_for_type,
    system_file,
)
from sync_schedule_timeline import sync_schedule_timeline_after_package


def add_package(
    project_root: Path,
    *,
    package_name: str,
    supplier_name: str,
    supplier_short: str,
    contact_email: str,
    package_type: str,
    milestone: str | None = None,
    status: str | None = None,  # legacy alias → milestone
    amount_excl_tax: str = "",
    amount_incl_tax: str = "",
    delivery_summary: str = "",
    milestone_at: str | None = None,
    sync_timeline: bool = True,
) -> dict:
    project_root = project_root.expanduser().resolve()
    project = load_json(system_file(project_root, PROJECT_JSON))
    if not project:
        raise FileNotFoundError(f"{PROJECT_JSON} not found in {project_root}. Run stage 0 first.")

    packages = load_tracker_packages(project_root)
    if find_package(packages, package_name):
        raise ValueError(f"Package already exists: {package_name}")

    seq = len(packages) + 1
    folder_name = package_folder_name(seq, package_name, supplier_short)
    package_dir = project_root / folder_name
    package_dir.mkdir(parents=True, exist_ok=True)
    for sub in subdirs_for_type(package_type):
        (package_dir / sub).mkdir(exist_ok=True)

    card_path = package_dir / CARD_FILENAME
    card_data_path = package_dir / CARD_DATA_FILENAME
    card_data = default_card_data(
        package_name=package_name,
        supplier_name=supplier_name,
        package_type=package_type,
        project_name=project.get("project_name", ""),
    )
    card_data["contact_email"] = contact_email
    save_json(card_data_path, card_data)

    pkg: dict = {
        "package_name": package_name,
        "supplier_name": supplier_name,
        "supplier_short": supplier_short,
        "contact_email": contact_email,
        "package_type": package_type,
        "amount_excl_tax": amount_excl_tax,
        "amount_incl_tax": amount_incl_tax,
        "delivery_summary": delivery_summary,
        "claimed_amount_excl_tax": "",
        "remaining_claim_amount_excl_tax": "",
        "next_payment_node": "",
        "payment_progress": "无在办",
        "ts_rfp_issued": "",
        "ts_tech_confirmed": "",
        "ts_quote_confirmed": "",
        "ts_po_issued": "",
        "ts_settled": "",
        "amount_remark": "",
        "seq": "",
        "card_path": str(card_path),
        "folder_path": str(package_dir),
    }
    effective_milestone = milestone or status
    if effective_milestone:
        stamp_milestone(pkg, effective_milestone, milestone_at or now_iso())
    packages.append(pkg)
    save_tracker_packages(project_root, packages)

    if sync_timeline:
        timeline = sync_schedule_timeline_after_package(
            project_root,
            package_name=package_name,
            package_dir=package_dir,
        )
        pkg["schedule_timeline"] = timeline

    return pkg


def update_package(
    project_root: Path,
    *,
    package_name: str,
    milestone: str | None = None,
    status: str | None = None,  # legacy alias → milestone
    amount_excl_tax: str | None = None,
    amount_incl_tax: str | None = None,
    total_amount: str | None = None,  # legacy alias → amount_excl_tax
    delivery_summary: str | None = None,
    contact_email: str | None = None,
    supplier_name: str | None = None,
    next_payment_node: str | None = None,
    claimed_amount_excl_tax: str | None = None,
    remaining_claim_amount_excl_tax: str | None = None,
    payment_progress: str | None = None,
    milestone_at: str | None = None,
    merge_contacts: bool = True,
) -> dict:
    project_root = project_root.expanduser().resolve()
    packages = load_tracker_packages(project_root)
    if not resolve_tracker_path(project_root) and not packages:
        raise FileNotFoundError(f"Tracker CSV not found in {project_root}")

    pkg = find_package(packages, package_name)
    if not pkg:
        raise ValueError(f"Package not found: {package_name}")

    if total_amount is not None and amount_excl_tax is None:
        amount_excl_tax = total_amount

    if contact_email is not None:
        if merge_contacts:
            pkg["contact_email"] = merge_contact_emails(
                pkg.get("contact_email", ""), contact_email
            )
        else:
            pkg["contact_email"] = contact_email

    updates = {
        "amount_excl_tax": amount_excl_tax,
        "amount_incl_tax": amount_incl_tax,
        "delivery_summary": delivery_summary,
        "supplier_name": supplier_name,
        "next_payment_node": next_payment_node,
        "claimed_amount_excl_tax": claimed_amount_excl_tax,
        "remaining_claim_amount_excl_tax": remaining_claim_amount_excl_tax,
        "payment_progress": payment_progress,
    }
    for key, value in updates.items():
        if value is not None:
            pkg[key] = value

    effective_milestone = milestone or status
    if effective_milestone:
        stamp_milestone(pkg, effective_milestone, milestone_at or now_iso())

    save_tracker_packages(project_root, packages)
    return pkg


def sync_next_payment_from_card(project_root: Path, package_name: str) -> None:
    packages = load_tracker_packages(project_root)
    pkg = find_package(packages, package_name)
    if not pkg:
        return
    card_data = load_json(Path(pkg["folder_path"]) / CARD_DATA_FILENAME, {})
    node = first_pending_payment_node(card_data.get("payment_nodes", []))
    if node:
        update_package(project_root, package_name=package_name, next_payment_node=node)


def main() -> None:
    parser = argparse.ArgumentParser(description="Update tracker.csv")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--action", choices=["add-package", "update"], required=True)

    parser.add_argument("--package-name")
    parser.add_argument("--supplier-short")
    parser.add_argument("--contact-email", default=None)
    parser.add_argument("--package-type", choices=["供应", "供装", "顾问", "总包"])
    parser.add_argument("--status", default=None, help="Legacy; maps to --milestone")
    parser.add_argument(
        "--milestone",
        default=None,
        help="Milestone to stamp: ts_rfp_issued | RFP 发出 | 待技术确认 (legacy) etc.",
    )
    parser.add_argument("--total-amount", default=None, help="Legacy; maps to 金额不含税")
    parser.add_argument("--amount-excl-tax", default=None)
    parser.add_argument("--amount-incl-tax", default=None)
    parser.add_argument("--delivery-summary", default=None)
    parser.add_argument("--next-payment-node", default=None)
    parser.add_argument("--claimed-amount-excl-tax", default=None)
    parser.add_argument("--remaining-claim-amount-excl-tax", default=None)
    parser.add_argument("--payment-progress", default=None)
    parser.add_argument("--supplier", default=None)
    parser.add_argument("--sync-payment-node", action="store_true")
    parser.add_argument("--milestone-at", default=None, help="ISO time for status stamp")
    parser.add_argument(
        "--no-sync-timeline",
        action="store_true",
        help="Skip schedule-critical-nodes analyze + timeline HTML after add-package",
    )

    args = parser.parse_args()
    root = Path(args.project_root)

    if args.action == "add-package":
        effective_milestone = args.milestone or args.status
        if not all([args.package_name, args.supplier, args.supplier_short, args.package_type]):
            parser.error("add-package requires --package-name, --supplier, --supplier-short, --package-type")
        if effective_milestone and not resolve_milestone_key(effective_milestone):
            parser.error(f"Unknown milestone/status: {effective_milestone}")
        result = add_package(
            root,
            package_name=args.package_name,
            supplier_name=args.supplier,
            supplier_short=args.supplier_short,
            contact_email=args.contact_email or "",
            package_type=args.package_type,
            milestone=effective_milestone,
            amount_excl_tax=args.amount_excl_tax or args.total_amount or "",
            amount_incl_tax=args.amount_incl_tax or "",
            milestone_at=args.milestone_at,
            sync_timeline=not args.no_sync_timeline,
        )
    else:
        if not args.package_name:
            parser.error("update requires --package-name")
        effective_milestone = args.milestone or args.status
        if effective_milestone and not resolve_milestone_key(effective_milestone):
            parser.error(f"Unknown milestone/status: {effective_milestone}")
        result = update_package(
            root,
            package_name=args.package_name,
            milestone=effective_milestone,
            amount_excl_tax=args.amount_excl_tax,
            amount_incl_tax=args.amount_incl_tax,
            total_amount=args.total_amount,
            delivery_summary=args.delivery_summary,
            contact_email=args.contact_email,
            supplier_name=args.supplier,
            next_payment_node=args.next_payment_node,
            claimed_amount_excl_tax=args.claimed_amount_excl_tax,
            remaining_claim_amount_excl_tax=args.remaining_claim_amount_excl_tax,
            payment_progress=args.payment_progress,
            milestone_at=args.milestone_at,
        )
        if args.sync_payment_node:
            sync_next_payment_from_card(root, args.package_name)
            result = find_package(load_tracker_packages(root), args.package_name)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
