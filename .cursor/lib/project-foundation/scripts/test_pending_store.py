#!/usr/bin/env python3
"""Hard-gate tests: pending.json 必须带 skill；只能关自己的；进度禁止混入。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import PENDING_JSON, save_json, system_dir
from pending_store import (
    PendingStoreError,
    add_pending,
    close_matching,
    close_pending,
    ensure_pending_file,
    load_pending_doc,
)


def _root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="pending-gate-"))
    (tmp / ".skill").mkdir(parents=True)
    ensure_pending_file(tmp)
    return tmp


class PendingStoreTests(unittest.TestCase):
    def test_add_requires_skill(self) -> None:
        root = _root()
        with self.assertRaises(PendingStoreError):
            add_pending(root, {"reason": "x", "subject": "s"})

    def test_schedule_skill_cannot_write_pending_json(self) -> None:
        root = _root()
        with self.assertRaises(PendingStoreError) as ctx:
            add_pending(
                root,
                {"reason": "unmapped_task", "note": "进度吃不准"},
                skill="critical-nodes",
            )
        self.assertIn("schedule.json", str(ctx.exception))
        self.assertEqual(load_pending_doc(root)["items"], [])

    def test_direct_save_json_blocked(self) -> None:
        root = _root()
        path = system_dir(root) / PENDING_JSON
        with self.assertRaises(PermissionError):
            save_json(path, {"items": [{"reason": "sneak"}]})

    def test_stamps_skill_and_owner_can_close(self) -> None:
        root = _root()
        pid = add_pending(
            root,
            {"reason": "tax_rate_uncertain", "subject": "Raise PO", "eml_path": "/tmp/a.eml"},
            skill="po-flow",
        )
        item = load_pending_doc(root)["items"][0]
        self.assertEqual(item["skill"], "po-flow")
        self.assertEqual(item["pending_id"], pid)
        closed = close_pending(root, pid, skill="po-flow")
        self.assertEqual(closed["status"], "confirmed")
        self.assertEqual(closed["resolved_by"], "po-flow")

    def test_other_skill_cannot_close(self) -> None:
        root = _root()
        pid = add_pending(
            root,
            {"reason": "out_of_order", "subject": "商务确认", "step": "change_archive"},
            skill="change-flow",
        )
        with self.assertRaises(PendingStoreError) as ctx:
            close_pending(root, pid, skill="payment-flow")
        self.assertIn("不能关别人的单", str(ctx.exception))
        self.assertEqual(load_pending_doc(root)["items"][0]["status"], "open")

    def test_close_matching_skips_others(self) -> None:
        root = _root()
        mine = add_pending(
            root,
            {"reason": "change_po_deferred", "fields": {"change_no": "COD076"}, "subject": "a"},
            skill="change-flow",
        )
        add_pending(
            root,
            {"reason": "change_po_deferred", "fields": {"change_no": "COD076"}, "subject": "b"},
            skill="po-flow",
        )
        closed = close_matching(
            root,
            skill="change-flow",
            match=lambda it: str(it.get("reason") or "") == "change_po_deferred",
        )
        self.assertEqual(closed, [mine])
        items = {it["pending_id"]: it for it in load_pending_doc(root)["items"]}
        self.assertEqual(items[mine]["status"], "confirmed")
        other = next(i for i in items.values() if i["pending_id"] != mine)
        self.assertEqual(other["status"], "open")
        self.assertEqual(other["skill"], "po-flow")

    def test_legacy_item_inferred_owner(self) -> None:
        root = _root()
        path = system_dir(root) / PENDING_JSON
        path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "pending_id": "p-old",
                            "status": "open",
                            "step": "change_archive",
                            "reason": "out_of_order",
                            "subject": "乱序",
                        }
                    ]
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        close_pending(root, "p-old", skill="change-flow")
        item = load_pending_doc(root)["items"][0]
        self.assertEqual(item["status"], "confirmed")
        self.assertEqual(item["skill"], "change-flow")
        with self.assertRaises(PendingStoreError) as ctx:
            close_pending(root, "p-old", skill="po-flow")
        self.assertIn("不能关别人的单", str(ctx.exception))

    def test_card_skill_forbidden(self) -> None:
        root = _root()
        with self.assertRaises(PendingStoreError):
            add_pending(root, {"reason": "quality"}, skill="vendor-card")


if __name__ == "__main__":
    unittest.main()
