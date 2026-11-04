"""RISK-3P-02: migration register tests. Offline and no broker state changes."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import audit_risk_3p_02_migration as mod


ROOT = Path(__file__).resolve().parents[1]


class RiskThreePairMigrationTests(unittest.TestCase):
    def setUp(self):
        self.document = mod.load(ROOT)

    def assert_rejected(self, changes: dict, expected: str):
        data = copy.deepcopy(self.document)
        data.update(changes)
        errors = mod.audit(ROOT, data)
        self.assertIn(expected, errors)

    def test_source_derived_register_and_safety_hold(self):
        self.assertEqual(mod.audit(ROOT), [])
        self.assertEqual(self.document["target_pairs"],
                         ["USD/JPY", "EUR/JPY", "EUR/USD"])
        self.assertEqual(self.document["historical_q3_pairs"],
                         ["USD/JPY", "EUR/JPY", "GBP/USD", "AUD/USD"])
        self.assertEqual(self.document["status"], "INVENTORIED_NOT_MIGRATED")
        self.assertEqual(self.document["runtime_go_no_go"], "NO_GO")
        self.assertEqual(self.document["phase_1"], "BLOCKED")
        self.assertIs(self.document["safety_hold_latched"], True)
        self.assertIsNone(self.document["verified_values"])

    def test_rejects_trade_scope_change_and_missing_eurusd(self):
        for pairs in (["USD/JPY", "EUR/JPY", "GBP/USD"],
                      ["USD/JPY", "EUR/JPY"],
                      ["USD/JPY", "EUR/JPY", "EUR/USD", "AUD/USD"]):
            with self.subTest(pairs=pairs):
                self.assert_rejected({"target_pairs": pairs},
                                     "TARGET_PAIRS_NOT_3P")

    def test_historical_q3_is_never_rewritten(self):
        self.assert_rejected(
            {"historical_q3_pairs": ["USD/JPY", "EUR/JPY", "EUR/USD"]},
            "HISTORICAL_Q3_CHANGED")

    def test_no_synthetic_or_inventory_can_become_approval(self):
        for field, value in (
            ("implementation_authorized", True),
            ("production_authorized", True),
            ("broker_connection_authorized", True),
            ("stop_release_authorized", True),
            ("runtime_go_no_go", "GO"),
            ("phase_1", "ACCEPTED"),
            ("safety_hold_latched", False),
            ("verified_values", {"EUR/USD": "invented"}),
        ):
            with self.subTest(field=field):
                self.assert_rejected({field: value},
                                     "SAFETY_STATE_PROMOTED")
        self.assert_rejected({"status": "MIGRATED"},
                             "FALSE_MIGRATION_ACCEPTANCE")

    def test_3_by_5_is_proposed_and_g1_4_by_5_still_blocked(self):
        self.assert_rejected({"target_g1_attribute_count": 20},
                             "G1_SCOPE_COUNTS_CHANGED")
        self.assert_rejected({"target_g1_status": "VERIFIED"},
                             "FALSE_MIGRATION_ACCEPTANCE")
        self.assertEqual(self.document["target_g1_attribute_count"], 15)
        self.assertEqual(self.document["historical_g1_attribute_count"], 20)

    def test_legacy_code_cannot_disappear_from_inventory(self):
        x = self.document["legacy_code_paths"][0]
        adjusted = [p for p in self.document["legacy_code_paths"] if p != x]
        payload = copy.deepcopy(self.document)
        payload["legacy_code_paths"] = adjusted
        self.assertIn("UNREGISTERED_LEGACY_4P_CODE:" + x,
                      mod.audit(ROOT, payload))

    def test_misclassified_legacy_source_is_rejected(self):
        payload = copy.deepcopy(self.document)
        first = payload["legacy_code_paths"][0]
        record = next(x for x in payload["inventory"] if x["path"] == first)
        record["category"] = "CURRENT_3P_SYNTHETIC"
        self.assertIn("LEGACY_CODE_MISCLASSIFIED:" + first,
                      mod.audit(ROOT, payload))

    def test_duplicate_inventory_file_is_rejected(self):
        payload = copy.deepcopy(self.document)
        payload["inventory"].append(copy.deepcopy(payload["inventory"][0]))
        self.assertIn("INVENTORY_DUPLICATE_OR_UNSAFE_PATH",
                      mod.audit(ROOT, payload))

    def test_inventory_files_are_known_in_repository(self):
        paths = {x["path"] for x in self.document["inventory"]}
        self.assertGreaterEqual(len(paths), 25)
        self.assertIn("specs/p0_01_d5_25_gap_verification_matrix.json", paths)
        self.assertIn("scripts/mt4_manual_symbol_v2.py", paths)
        self.assertIn("scripts/phase1_three_pair_synthetic_risk.py", paths)
        self.assertIn("mt4/read_only/P0_01_ManualSymbolSnapshot_ReadOnly.mq4",
                      paths)
        self.assertIn("specs/p0_01_rakuten_mt4_public_contract_evidence.json", paths)

    def test_no_hidden_four_pair_approval_by_reading_migration_only(self):
        from scripts.phase1_three_pair_synthetic_risk import PAIRS
        self.assertEqual(PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))
        formal = json.loads(
            (ROOT / "specs/p0_01_d5_25_gap_verification_matrix.json")
            .read_text(encoding="utf-8"))
        self.assertEqual(formal["phase_1"], "BLOCKED")
        self.assertEqual(formal["runtime_go_no_go"], "NO_GO")
        self.assertEqual(formal["gaps"][0]["id"], "G1")
        self.assertIs(formal["gaps"][0]["real_world_verified"], False)


if __name__ == "__main__":
    unittest.main()
