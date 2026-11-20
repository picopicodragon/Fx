"""New paper Q109/Q110 evidence extends, never edits, frozen registries."""
from __future__ import annotations
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class FinalPaper20261120GovernanceTests(unittest.TestCase):
    def test_q109_extension_safety_tests_resolve_without_merging_base(self):
        inventory=json.loads((ROOT/"specs/traceability.json").read_text("utf-8"))
        self.assertEqual(len(inventory["offline_synthetic_mappings"]),45)
        path=ROOT/"specs/final_paper_q109_traceability_extension_20261120.json"
        spec=json.loads(path.read_text("utf-8"))
        self.assertTrue(spec["legacy_registries_intentionally_unchanged"])
        self.assertFalse(spec["live_virtual_entry_authorized"])
        self.assertFalse(spec["paid_ai_renewal_authorized"])
        seen=set()
        for item in spec["registered_sources"]:
            self.assertNotIn(item["source"],seen)
            seen.add(item["source"])
            self.assertFalse(item["production_authorized"])
            self.assertTrue((ROOT/item["source"]).is_file())
            for test in item["tests"]:
                self.assertTrue((ROOT/test).is_file())
        self.assertIn("research/final_paper_e2e_replay.py",seen)
        self.assertIn("research/final_paper_completed_decision.py",seen)

    def test_q110_offline_vs_live_acceptance_never_confused(self):
        path=ROOT/"specs/final_paper_q110_acceptance_extension_20261120.json"
        spec=json.loads(path.read_text("utf-8"))
        self.assertTrue(spec["operator_approved_communication_release_scope_only"])
        self.assertFalse(spec["live_communication_latch_cleared"])
        for name in ("live_new_virtual_entry_authorized",
                     "added_paid_calls_authorized",
                     "demo_orders_authorized",
                     "real_orders_authorized","main_merge_authorized"):
            self.assertFalse(spec[name])
        self.assertEqual(len(spec["tasks"]),5)
        self.assertTrue(all(t["operator_approval"] is None
                            for t in spec["tasks"]))
        self.assertTrue(all("BLOCKED" in t["status"]
                            or "NOT_LIVE_ACCEPTED" in t["status"]
                            for t in spec["tasks"]))


if __name__=="__main__":
    unittest.main()
