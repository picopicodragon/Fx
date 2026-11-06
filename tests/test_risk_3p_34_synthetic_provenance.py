"""Negative/fault injection tests for in-memory-only P34 synthetic G1 contract."""
from __future__ import annotations

import copy
import unittest

from scripts import validate_risk_3p_34_synthetic_provenance as mod


class SyntheticProvenanceContractTests(unittest.TestCase):
    def setUp(self):
        self.package = mod.make_synthetic_fixture()

    def reject(self, mutate, expected):
        package = copy.deepcopy(self.package)
        mutate(package)
        output = mod.check_synthetic_package(package)
        self.assertEqual(output["status"], "FAIL_CLOSED", output)
        self.assertIn(expected, output["errors"], output)
        self.assertEqual(output["real_broker_values_verified"], 0)
        self.assertEqual(output["p05_passed"], 0)
        self.assertFalse(output["real_mt4_read_authorized"])
        self.assertFalse(output["order_authorized"])
        self.assertEqual(output["runtime_go_no_go"], "NO_GO")
        self.assertTrue(output["safety_hold_latched"])

    def test_baseline_fixture_never_claims_real_evidence(self):
        self.assertEqual(len(self.package["rows"]), 15)
        self.assertEqual([r["pair"] for r in self.package["rows"]][::5],
                         list(mod.PAIRS))
        self.assertEqual([r["field"] for r in self.package["rows"][:5]],
                         list(mod.FIELDS))
        result = mod.check_synthetic_package(self.package)
        self.assertEqual(result["status"], "PASS_SYNTHETIC_CONTRACT_ONLY")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["synthetic_rows_expected"], 15)
        self.assertEqual(result["real_broker_values_verified"], 0)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_no_real_claims_or_safety_permission_can_be_enabled(self):
        for key, value in (
            ("p05_status", "PASSED"), ("runtime_go_no_go", "GO"),
            ("safety_hold_latched", False),
            ("broker_evidence_verified", True), ("mt4_read_authorized", True),
            ("order_authorized", True)):
            with self.subTest(key=key):
                self.reject(lambda p, k=key, v=value: p.update({k: v}),
                            "P34_SAFETY_PERMISSION_FALSELY_PROMOTED")

    def test_unsupported_scope_or_real_data_classification_rejected(self):
        for key, value in (
            ("classification", "REAL_BROKER_EVIDENCE"),
            ("target_pairs", ["USD/JPY", "GBP/USD", "EUR/USD"]),
            ("target_fields", ["min_lot"]), ("schema_version", True)):
            with self.subTest(key=key):
                self.reject(lambda p, k=key, v=value: p.update({k: v}),
                            "P34_SCOPE_OR_CLASSIFICATION_DRIFT")
        self.reject(lambda p: p.update(account_id="SENSITIVE"),
                    "P34_PACKAGE_SHAPE_OR_UNKNOWN_FIELDS")

    def test_non_decimal_or_invalid_numeric_values_rejected(self):
        for value in (0.1, 1, "-1", "0", "0.00", "NaN", "Infinity", "1e9",
                      "00.1", "1,000", " ", "", None, "7.77 USD"):
            with self.subTest(value=value):
                self.reject(
                    lambda p, v=value:
                    p["rows"][0].update(synthetic_value_decimal=v),
                    "P34_UNITS_VALUE_OR_FAKE_TIME_INVALID:1")

    def test_unit_contract_enforced_without_tick_point_or_currency_proxy(self):
        for idx, unit in (
            (0, "UNITS"), (1, "LOT_STEP"), (2, "USD"),
            (3, "QUOTE_CCY_PER_POINT"), (4, "POINTS_PER_TICK")):
            with self.subTest(row=idx, unit=unit):
                self.reject(lambda p, n=idx, u=unit:
                            p["rows"][n].update(unit=u),
                            "P34_UNITS_VALUE_OR_FAKE_TIME_INVALID:"
                            + str(idx + 1))

    def test_stale_invalid_or_real_world_time_and_terminal_name_rejected(self):
        for timestamp in ("2026-11-06T00:00:00Z", "SIM_2026-13-01T00:00:00Z",
                          "SIM_2000-01-01T00:00:00+09:00",
                          "SIM_2000-01-01T99:00:00Z"):
            with self.subTest(timestamp=timestamp):
                self.reject(lambda p, v=timestamp:
                            p["rows"][0].update(synthetic_timestamp_utc=v),
                            "P34_UNITS_VALUE_OR_FAKE_TIME_INVALID:1")
        self.reject(lambda p: p["rows"][0].update(
            synthetic_terminal_symbol_alias="USDJPY"),
            "P34_UNITS_VALUE_OR_FAKE_TIME_INVALID:1")
        self.reject(lambda p: p["rows"][0].update(
            synthetic_terminal_symbol_alias="SIM_EURUSD"),
            "P34_UNITS_VALUE_OR_FAKE_TIME_INVALID:1")

    def test_primary_and_independent_fictitious_sources_cannot_collide(self):
        self.reject(lambda p: p["rows"][0].update(
            independent_source=copy.deepcopy(p["rows"][0]["primary_source"])),
            "P34_SYNTHETIC_SOURCES_NOT_INDEPENDENT:1")
        self.reject(lambda p: p["rows"][0]["primary_source"].update(
            kind="BROKER_API"),
            "P34_SYNTHETIC_SOURCES_NOT_INDEPENDENT:1")
        self.reject(lambda p: p["rows"][0]["primary_source"].update(
            token="C:\\Users\\Secret"),
            "P34_SYNTHETIC_SOURCES_NOT_INDEPENDENT:1")
        self.reject(lambda p: p["rows"][0]["primary_source"].update(
            account_number="INTERNAL"),
            "P34_SYNTHETIC_SOURCES_NOT_INDEPENDENT:1")

    def test_no_reordering_missing_rows_or_unapproved_private_data_columns(self):
        self.reject(lambda p: p["rows"].pop(),
                    "P34_EXACTLY_15_ROWS_REQUIRED")
        self.reject(lambda p: p["rows"].reverse(),
                    "P34_PAIR_FIELD_OR_STATUS_MISMATCH:1")
        self.reject(lambda p: p["rows"][0].update(status="VERIFIED"),
                    "P34_PAIR_FIELD_OR_STATUS_MISMATCH:1")
        self.reject(lambda p: p["rows"][0].update(
            account_number="SENSITIVE"),
            "P34_ROW_SHAPE_OR_SECRET_FIELD:1")

    def test_untrusted_payload_never_echoes_secret_or_crashes(self):
        for bad in (None, [], "", 100, {"secret": "PASSWORD"}):
            with self.subTest(kind=type(bad).__name__):
                output = mod.check_synthetic_package(bad)
                self.assertEqual(output["status"], "FAIL_CLOSED")
                self.assertNotIn("PASSWORD", str(output))
                self.assertEqual(output["runtime_go_no_go"], "NO_GO")
        self.reject(lambda p: p.update(secret_key="TOPSECRET"),
                    "P34_PACKAGE_SHAPE_OR_UNKNOWN_FIELDS")
        result = mod.check_synthetic_package({
            "secret": "RAW_PRIVATE_KEY_MUST_NOT_APPEAR"})
        self.assertNotIn("RAW_PRIVATE_KEY_MUST_NOT_APPEAR", str(result))


if __name__ == "__main__":
    unittest.main()
