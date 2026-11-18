"""Pinned legacy governance baselines never changed by final-paper sprint."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class FinalPaperGovernanceExtensionTests(unittest.TestCase):
    def test_old_45_source_offline_inventory_stays_frozen(self):
        base=json.loads((ROOT/"specs/traceability.json").read_text())
        self.assertEqual(len(base["offline_synthetic_mappings"]),45)
        extension=json.loads((ROOT/"specs"/
            "final_paper_q109_traceability_extension_20261118.json").read_text())
        self.assertTrue(extension["base_registry_pinned_and_unchanged"])
        self.assertFalse(extension["activation_authorized"])
        seen=set()
        for record in extension["registered_sources"]:
            self.assertFalse(record["production_authorized"])
            self.assertTrue(record["spec_ids"])
            self.assertTrue(record["tests"])
            self.assertNotIn(record["source"],seen)
            seen.add(record["source"])
            self.assertTrue((ROOT/record["source"]).is_file(),
                            record["source"])
            for test in record["tests"]:
                self.assertTrue((ROOT/test).is_file(),test)
        self.assertIn("research/final_paper_runtime.py",seen)
        self.assertIn("research/final_paper_bls_event_archive.py",seen)

    def test_q110_module_phase_approval_still_missing(self):
        original=json.loads((ROOT/"specs/acceptance_registry.json").read_text())
        self.assertEqual(len(original["modules"]),1)
        ext=json.loads((ROOT/"specs"/
            "final_paper_q110_acceptance_extension_20261118.json").read_text())
        self.assertTrue(ext["base_registry_frozen_and_unchanged"])
        self.assertFalse(ext["human_approved_module"])
        self.assertFalse(ext["human_approved_phase"])
        self.assertFalse(ext["virtual_reentry_authorized"])
        self.assertFalse(ext["broker_orders_authorized"])
        self.assertFalse(ext["paid_ai_extension_authorized"])
        self.assertEqual(len(ext["tasks"]),5)
        self.assertEqual(ext["modules"][0]["status"],"BLOCKED")
        self.assertIsNone(ext["modules"][0]["approval"])
        self.assertEqual(ext["phases"][0]["status"],"BLOCKED")
        self.assertIsNone(ext["phases"][0]["approval"])
        for task in ext["tasks"]:
            self.assertIsNone(task["approval"])


if __name__=="__main__":
    unittest.main()
