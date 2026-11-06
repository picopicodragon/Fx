"""Fictional two-source G1 witness coherency cannot certify real contracts."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_50_synthetic_dual_witness as mod


class FictionalDualWitnessTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.fixture()

    def fail(self, mutate, code):
        x = copy.deepcopy(self.data)
        mutate(x)
        result = mod.evaluate(x)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(code, result["errors"], result)
        self.assertEqual(result["actual_broker_fields_verified"], 0)
        self.assertFalse(result["actual_source_independence_verified"])
        self.assertFalse(result["real_mt4_read_authorized"])
        self.assertFalse(result["human_approval_verified"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_mock_two_witnesses_cover_fifteen_fields_without_real_evidence(self):
        state = mod.evaluate(self.data)
        self.assertEqual(state["status"], "PASS_TWO_FAKE_WITNESSES_ONLY")
        self.assertEqual(state["fictitious_fields"], 15)
        self.assertEqual(state["actual_broker_fields_verified"], 0)
        self.assertEqual(state["p05_passed"], 0)

    def test_independent_origin_claim_or_account_scope_refused(self):
        self.fail(lambda x: x["second_witness"].update(
            source_kind="REAL_BROKER_SERVER"), "P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")
        self.fail(lambda x: x["second_witness"].update(
            account_alias="SIM_SECOND_ACCOUNT"), "P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")
        self.fail(lambda x: x["second_witness"].update(
            fake_utc="2026-11-06T00:00:00Z"), "P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")

    def test_every_field_conflict_refused_even_if_primary_is_well_formed(self):
        for i in range(15):
            with self.subTest(index=i):
                self.fail(lambda x, n=i: x["second_witness"]["rows"][n].update(
                    synthetic_decimal="99.99"),
                    "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:" + str(i + 1))

    def test_unit_and_pair_substitution_refused(self):
        self.fail(lambda x: x["second_witness"]["rows"][4].update(
            unit="POINTS_PER_TICK"), "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:5")
        self.fail(lambda x: x["second_witness"]["rows"][9].update(
            pair="GBP/USD"), "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:10")

    def test_reused_or_cross_field_source_tokens_refused(self):
        self.fail(lambda x: x["second_witness"]["rows"][1].update(
            source_token="SIM_WITNESS_01"),
            "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:2")
        self.fail(lambda x: x["second_witness"]["rows"][11].update(
            field="lot_step"), "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:12")

    def test_missing_rows_and_private_data_columns_refused(self):
        self.fail(lambda x: x["second_witness"]["rows"].pop(),
                  "P50_FIFTEEN_WITNESS_ROWS_REQUIRED")
        self.fail(lambda x: x["second_witness"]["rows"][0].update(
            account_password="CANARY_50"),
            "P50_WITNESS_ROW_SECRET_OR_MISSING:1")

    def test_primary_baseline_must_be_validated_separately(self):
        self.fail(lambda x: x["primary"]["rows"][0].update(
            synthetic_value_decimal="0"),
            "P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID")
        self.fail(lambda x: x["primary"].update(
            order_authorized=True),
            "P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID")

    def test_real_permission_or_p05_signature_spoof_refused(self):
        for key, original in mod.SAFETY.items():
            with self.subTest(key=key):
                new = (not original if type(original) is bool
                       else (1 if type(original) is int else "GO"))
                self.fail(lambda x, k=key, v=new:
                          x["safety"].update({k: v}),
                          "P50_FORGED_REAL_EVIDENCE_OR_PERMISSION")

    def test_unknown_or_sensitive_envelope_fields_refused(self):
        self.fail(lambda x: x.update(account_id="CANARY_50"),
                  "P50_INVALID_OR_EXTRA_PACKAGE_FIELDS")
        self.fail(lambda x: x["second_witness"].update(
            actual_broker_log="CANARY_50"),
            "P50_SECOND_WITNESS_STRUCTURE_INVALID")

    def test_untrusted_root_inputs_do_not_echo_secret(self):
        for inp in (None, [], "", {}, 1, {"password": "CANARY_50"}):
            result = mod.evaluate(inp)
            self.assertEqual(result["status"], "FAIL_CLOSED")
            self.assertNotIn("CANARY_50", str(result))


if __name__ == "__main__":
    unittest.main()
