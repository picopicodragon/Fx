"""P0-01 D4-3: end-to-end offline safety boundary regression tests.

All fixtures are synthetic; no terminal, credentials, files or broker observations.
"""
import copy
import unittest
from unittest.mock import patch

from scripts.p0_01_offline_five_field_mock import (
    PAIRS, FIELDS, PASS as SYNTHETIC_PASS, REVIEW, INCOMPLETE,
    report_safe_status_codes_only,
)
from scripts.p0_01_offline_provenance_guard import (
    EXPECTED_UNITS, PENDING as CANDIDATE_PENDING, check_candidate,
)
from scripts.p0_01_offline_approval_gate import (
    deny_all, invariant_holds, PENDING,
)

REFERENCE = "2026-10-28T01:00:00+00:00"


def synthetic():
    return [{"symbol": pair, "properties": {
        "min_lot": "0.1", "lot_step": "0.01", "point_quote": "0.001",
        "tick_size_points": "1", "tick_value_deposit_currency": "10",
    }} for pair in PAIRS]


def candidate():
    return {
        "origin": "MANUAL_UNVERIFIED",
        "observed_at": "2026-10-28T00:00:00+00:00",
        "evidence_kind": "MANUAL_SCREEN_NOTE_UNVERIFIED",
        "account_currency": "JPY",
        "contract_basis_confirmed": False,
        "symbols": [
            {"symbol": row["symbol"], "properties": dict(row["properties"]),
             "units": dict(EXPECTED_UNITS)}
            for row in synthetic()
        ],
    }


class OfflinePipelineIntegrationTests(unittest.TestCase):
    def assert_denied(self, response):
        self.assertTrue(invariant_holds(response))
        self.assertIs(response["broker_verified"], False)
        self.assertIs(response["production_usable"], False)
        self.assertIs(response["orders_generated"], False)
        self.assertIs(response["terminal_execution_approved"], False)
        self.assertIs(response["forward_trading_enabled"], False)
        self.assertEqual(response["phase_1"], "BLOCKED")

    def test_all_valid_synthetic_remains_unverified_across_pipeline(self):
        rows = synthetic()
        self.assertEqual(report_safe_status_codes_only(rows)["status"], SYNTHETIC_PASS)
        result = deny_all("SYNTHETIC", rows)
        self.assertEqual(result["status"], PENDING)
        self.assert_denied(result)

    def test_manual_candidate_remains_pending_even_if_complete(self):
        data = candidate()
        self.assertEqual(check_candidate(data, REFERENCE)["status"], CANDIDATE_PENDING)
        result = deny_all("MANUAL_CANDIDATE", data, REFERENCE)
        self.assertEqual(result["status"], PENDING)
        self.assert_denied(result)

    def test_cross_stage_masquerading_is_rejected(self):
        for stage, payload in (("MANUAL_CANDIDATE", synthetic()),
                               ("SYNTHETIC", candidate()),
                               ("BROKER_VERIFIED", candidate()),
                               ("LIVE", synthetic())):
            with self.subTest(stage=stage):
                result = deny_all(stage, payload, REFERENCE)
                self.assertEqual(result["status"], REVIEW)
                self.assert_denied(result)

    def test_all_twenty_missing_properties_are_not_authorized(self):
        for index in range(len(PAIRS)):
            for field in FIELDS:
                with self.subTest(index=index, field=field):
                    rows = synthetic()
                    rows[index]["properties"][field] = None
                    self.assertEqual(report_safe_status_codes_only(rows)["status"], INCOMPLETE)
                    self.assert_denied(deny_all("SYNTHETIC", rows))

    def test_invalid_unit_and_timestamp_fail_closed(self):
        for changed in ("unit", "future", "naive", "stale"):
            data = candidate()
            if changed == "unit":
                data["symbols"][0]["units"]["point_quote"] = "points_per_tick"
            elif changed == "future":
                data["observed_at"] = "2026-10-29T01:00:00+00:00"
            elif changed == "naive":
                data["observed_at"] = "2026-10-28T00:00:00"
            else:
                data["observed_at"] = "2026-10-20T00:00:00+00:00"
            with self.subTest(changed=changed):
                result = deny_all("MANUAL_CANDIDATE", data, REFERENCE)
                self.assertEqual(result["status"], REVIEW)
                self.assert_denied(result)

    def test_fake_approval_field_or_contract_claim_fails(self):
        data = candidate()
        data["forward_trading_enabled"] = True
        self.assertEqual(deny_all("MANUAL_CANDIDATE", data, REFERENCE)["status"], REVIEW)
        data = candidate()
        data["contract_basis_confirmed"] = True
        self.assertEqual(deny_all("MANUAL_CANDIDATE", data, REFERENCE)["status"], REVIEW)

    def test_no_input_mutation_or_raw_value_in_response(self):
        rows = synthetic()
        original = copy.deepcopy(rows)
        self.assert_denied(deny_all("SYNTHETIC", rows))
        self.assertEqual(rows, original)
        rows[0]["properties"]["min_lot"] = "PRIVATE_UNIQUE_SENTINEL"
        response = deny_all("SYNTHETIC", rows)
        self.assertNotIn("PRIVATE_UNIQUE_SENTINEL", repr(response))
        self.assert_denied(response)

    def test_exception_in_downstream_checker_denies(self):
        with patch("scripts.p0_01_offline_approval_gate.check_candidate",
                   side_effect=RuntimeError("PRIVATE_EXCEPTION")):
            response = deny_all("MANUAL_CANDIDATE", candidate(), REFERENCE)
            self.assertEqual(response["status"], REVIEW)
            self.assertNotIn("PRIVATE_EXCEPTION", repr(response))
            self.assert_denied(response)

    def test_mutating_final_report_fails_invariant(self):
        response = deny_all("SYNTHETIC", synthetic())
        for field in ("broker_verified", "production_usable", "orders_generated",
                      "terminal_execution_approved", "forward_trading_enabled"):
            modified = dict(response, **{field: True})
            self.assertFalse(invariant_holds(modified))

    def test_unexpected_inputs_never_grant_authority(self):
        for value in (None, True, 2, "PRIVATE_BAD", [], {}, object()):
            with self.subTest(input_type=type(value).__name__):
                self.assert_denied(deny_all(value, value, value))
                self.assert_denied(deny_all("SYNTHETIC", value))
                self.assert_denied(deny_all("MANUAL_CANDIDATE", value, value))


if __name__ == "__main__":
    unittest.main()
