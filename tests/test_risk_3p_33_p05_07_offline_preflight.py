"""Offline P05-07 G1 provenance checks. Never access MT4 or private folders."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_33_p05_07_offline_preflight as mod


class OfflineP0507PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._load(mod.ROOT, name) for name in mod.PATHS}

    def reject(self, filename, mutate, expected):
        data = copy.deepcopy(self.docs)
        mutate(data[filename])
        errors = mod.audit(injected=data)
        self.assertIn(expected, errors, errors)
        self.assertEqual(mod.snapshot(injected=data)["runtime_go_no_go"], "NO_GO")
        self.assertEqual(mod.snapshot(injected=data)["status"], "FAIL_CLOSED")

    def test_baseline_is_three_pairs_fifteen_empty_fields_and_no_go(self):
        self.assertEqual(mod.audit(), [])
        ledger = self.docs[mod.LEDGER]
        self.assertEqual(len(ledger["g1_entries"]), 15)
        self.assertEqual(ledger["target_pairs"], list(mod.PAIRS))
        self.assertEqual(ledger["required_fields"], list(mod.FIELDS))
        self.assertTrue(all(r["value"] is None for r in
                            ledger["g1_entries"]))
        state = mod.snapshot()
        self.assertEqual(state["status"], "PASS_OFFLINE_SCHEMA_ONLY")
        self.assertTrue(state["owner_storage_accepted_for_offline_planning_only"])
        self.assertEqual(state["real_g1_fields_verified"], 0)
        self.assertEqual(state["p05_passed"], 0)
        self.assertFalse(state["actual_mt4_read_authorized"])
        self.assertFalse(state["real_broker_evidence_collected"])
        self.assertTrue(state["safety_hold_latched"])
        self.assertEqual(state["runtime_go_no_go"], "NO_GO")

    def test_filled_or_fabricated_g1_value_or_evidence_is_rejected(self):
        for key, value in (
            ("value", "0.01"), ("unit", "lot"),
            ("terminal_symbol", "USDJPY"), ("observed_at_utc",
                                            "2026-11-06T00:00:00Z"),
            ("primary_source_ref", "invented-broker-evidence"),
            ("independent_source_ref", "fabricated-reference"),
            ("reviewer_ref", "made-up-owner-approval")):
            with self.subTest(key=key):
                self.reject(mod.LEDGER,
                            lambda d, k=key, v=value:
                            d["g1_entries"][0].update({k: v}),
                            "P05_07_UNVERIFIED_ROW_FILLED_OR_MISLABELED:1")

    def test_reordered_duplicate_or_missing_rows_fail_closed(self):
        self.reject(mod.LEDGER,
                    lambda d: d["g1_entries"].pop(),
                    "P05_07_G1_15_UNVERIFIED_ROWS_REQUIRED")
        self.reject(mod.LEDGER,
                    lambda d: d["g1_entries"][0].update(pair="GBP/USD"),
                    "P05_07_UNVERIFIED_ROW_FILLED_OR_MISLABELED:1")
        self.reject(mod.LEDGER,
                    lambda d: d["g1_entries"][0].update(status="VERIFIED"),
                    "P05_07_UNVERIFIED_ROW_FILLED_OR_MISLABELED:1")
        self.reject(mod.LEDGER,
                    lambda d: d["g1_entries"][0].update(
                        account_number="FORBIDDEN_SENSITIVE_FIELD"),
                    "P05_07_UNVERIFIED_ROW_FILLED_OR_MISLABELED:1")

    def test_safety_and_owner_scope_cannot_be_promoted(self):
        for key, value in (
            ("p05_passed_checks", 1),
            ("independently_verified_g1_items", 15),
            ("p05_actual_terminal_session_authorized", True),
            ("p05_real_mt4_data_collection_authorized", True),
            ("order_execution_authorized", True),
            ("cloud_or_github_private_evidence_upload_authorized", True),
            ("safety_hold_latched", False),
            ("runtime_go_no_go", "GO")):
            with self.subTest(key=key):
                self.reject(mod.LEDGER,
                            lambda d, k=key, v=value:
                            d["safety"].update({k: v}),
                            "P05_07_G1_OR_MT4_AUTHORIZATION_FALSELY_GRANTED")
        self.reject(mod.LEDGER, lambda d: d.update(required_items=20),
                    "P05_07_G1_3X5_SCOPE_DRIFT")
        self.reject(mod.SCOPE,
                    lambda d: d.update(real_verified_field_count=1),
                    "P05_07_OWNER_SCOPE_MISTAKEN_FOR_EVIDENCE")
        self.reject(mod.PROTOCOL, lambda d: d.update(
            owner_approved_real_read=True),
            "P05_07_READONLY_PROTOCOL_BROKER_PERMISSION_DRIFT")

    def test_storage_acceptance_is_not_p05_access_signoff(self):
        self.reject(mod.P05,
                    lambda d: d["p05_checks"][5]
                    ["owner_accepted_storage_security_scope"].update(
                        accepted_for="REAL_TERMINAL_OBSERVATION"),
                    "P05_07_STORAGE_ACCEPTANCE_NOT_MT4_SIGNOFF")
        self.reject(mod.P05, lambda d: d.update(p05_passed_checks=1),
                    "P05_07_P05_NOT_INDEPENDENTLY_CLEARED")
        self.reject(mod.P05, lambda d: d.update(
            p06_observation_authorized=True),
            "P05_07_P05_NOT_INDEPENDENTLY_CLEARED")

    def test_blank_mt4_template_cannot_be_filled_or_contain_secrets(self):
        self.reject(mod.TEMPLATE,
                    lambda d: d["symbols"][0]["properties"].update(
                        min_lot="0.01"),
                    "P05_07_BROKER_PROPERTIES_NOT_BLANK:1")
        self.reject(mod.TEMPLATE,
                    lambda d: d["symbols"][1]["observation"].update(
                        terminal_symbol="EURJPY"),
                    "P05_07_OBSERVATION_NOT_BLANK:2")
        self.reject(mod.TEMPLATE,
                    lambda d: d["symbols"][2]["display_properties"]
                    .update(margin_currency="USD"),
                    "P05_07_DISPLAY_DATA_NOT_BLANK:3")
        self.reject(mod.TEMPLATE,
                    lambda d: d["symbols"][0]["display_properties"]
                    ["trading_hours_display"].update(monday="06:00"),
                    "P05_07_HOURS_NOT_BLANK:1")
        self.reject(mod.TEMPLATE,
                    lambda d: d["symbols"][0].update(
                        private_path="PERSONAL_WINDOWS_FOLDER"),
                    "P05_07_TEMPLATE_SYMBOL_DRIFT:1")
        self.reject(mod.TEMPLATE,
                    lambda d: d["symbols"][0].update(symbol="GBP/USD"),
                    "P05_07_TEMPLATE_SYMBOL_DRIFT:1")

    def test_malformed_documents_fail_closed_without_leaking_contents(self):
        injected = copy.deepcopy(self.docs)
        injected[mod.LEDGER] = []
        errors = mod.audit(injected=injected)
        self.assertEqual(errors, ["P05_07_INVALID_OFFLINE_DOCUMENT"])
        injected = copy.deepcopy(self.docs)
        injected.pop(mod.TEMPLATE)
        errors = mod.audit(injected=injected)
        self.assertIn("P05_07_MALFORMED_OR_MISSING_OFFLINE_INPUT", errors)
        self.assertNotIn("PRIVATE_WINDOWS_FOLDER", str(errors))

    def test_ledger_has_no_real_broker_evidence_or_raw_account_fields(self):
        ledger = self.docs[mod.LEDGER]
        forbidden = ("account_number", "login_id", "password",
                     "api_key", "secret", "private_path")
        for item in ledger["g1_entries"]:
            for word in forbidden:
                self.assertNotIn(word, item)
            self.assertTrue(all(item[k] is None for k in
                                mod.ROW_KEYS
                                if k not in ("pair", "field", "status")))


if __name__ == "__main__":
    unittest.main()
