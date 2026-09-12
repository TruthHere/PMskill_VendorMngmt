#!/usr/bin/env python3
"""对话路径用错 Skill 必须拒写。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from common import (
    PROJECT_JSON,
    load_tracker_packages,
    save_json,
    save_tracker_packages,
    system_dir,
)
from write_guard import (
    WriteGuardError,
    assert_card_data_write,
    assert_change_log_write,
    assert_solo_output_allowed,
    assert_tracker_write,
    skill_from_path,
)


def _seed_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="write-guard-"))
    (root / ".skill").mkdir()
    save_json(
        system_dir(root) / PROJECT_JSON,
        {"project_name": "GateProj", "project_code": "GATE"},
    )
    save_tracker_packages(
        root,
        [
            {
                "package_name": "BMS",
                "supplier_name": "Schneider",
                "supplier_short": "Schneider",
                "package_type": "供装",
                "amount_excl_tax": "1000000.00",
                "amount_incl_tax": "1090000.00",
                "claimed_amount_excl_tax": "0",
                "remaining_claim_amount_excl_tax": "1000000.00",
                "next_payment_node": "到货 / Delivery",
                "payment_progress": "无在办",
            }
        ],
    )
    return root


class WriteGuardTests(unittest.TestCase):
    def test_fulfillment_cannot_write_change_log(self) -> None:
        with self.assertRaises(WriteGuardError) as ctx:
            assert_change_log_write(skill="contract-fulfillment-struct")
        self.assertIn("变更台账", str(ctx.exception))
        self.assertIn("Skill 3", str(ctx.exception))

    def test_change_cannot_write_tracker(self) -> None:
        root = _seed_project()
        packages = load_tracker_packages(root)
        with self.assertRaises(WriteGuardError) as ctx:
            assert_tracker_write(root, packages, skill="change-archive")
        self.assertIn("采购包总表", str(ctx.exception))

    def test_payment_cannot_write_contract_amount(self) -> None:
        root = _seed_project()
        packages = load_tracker_packages(root)
        packages[0]["amount_excl_tax"] = "1.00"
        with self.assertRaises(WriteGuardError) as ctx:
            assert_tracker_write(root, packages, skill="payment-request")
        self.assertIn("合同额", str(ctx.exception))

    def test_payment_cannot_write_change_log(self) -> None:
        with self.assertRaises(WriteGuardError) as ctx:
            assert_change_log_write(skill="payment-request")
        self.assertIn("变更台账", str(ctx.exception))

    def test_pdf_cannot_write_card_data(self) -> None:
        with self.assertRaises(WriteGuardError) as ctx:
            assert_card_data_write(skill="pdf-read")
        self.assertIn("履约卡片", str(ctx.exception))
        with self.assertRaises(WriteGuardError) as ctx2:
            assert_solo_output_allowed("card-data.json", skill="pdf-read")
        self.assertIn("card-data.json", str(ctx2.exception))

    def test_mpp_cannot_write_tracker_file(self) -> None:
        with self.assertRaises(WriteGuardError) as ctx:
            assert_solo_output_allowed(
                "Demo_procurement_packages_status_tracker.csv",
                skill="schedule-mpp-excel",
            )
        self.assertIn("不能把输出写成", str(ctx.exception))

    def test_payment_may_write_progress_only(self) -> None:
        root = _seed_project()
        packages = load_tracker_packages(root)
        packages[0]["payment_progress"] = "供应商请款已收到 · 到货 / Delivery"
        assert_tracker_write(root, packages, skill="payment-request")

    def test_fulfillment_may_write_amount(self) -> None:
        root = _seed_project()
        packages = load_tracker_packages(root)
        packages[0]["amount_excl_tax"] = "1100000.00"
        assert_tracker_write(root, packages, skill="contract-fulfillment-struct")

    def test_fulfillment_cannot_write_claimed(self) -> None:
        root = _seed_project()
        packages = load_tracker_packages(root)
        packages[0]["claimed_amount_excl_tax"] = "500.00"
        with self.assertRaises(WriteGuardError):
            assert_tracker_write(root, packages, skill="contract-fulfillment-struct")

    def test_skill_from_path(self) -> None:
        path = Path("/x/.cursor/skills/change-archive/scripts/handle_change_email.py")
        self.assertEqual(skill_from_path(path), "change-archive")


if __name__ == "__main__":
    unittest.main()
