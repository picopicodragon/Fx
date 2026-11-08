"""Fictional two-source G1 witness coherency cannot certify real contracts."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts import risk_3p_50_synthetic_dual_witness as mod


class FictionalDualWitnessTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.fixture()

    def reject(self, mutate, code):
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
        self.reject(lambda x: x["second_witness"].update(
            source_kind="REAL_BROKER_SERVER"), "P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")
        self.reject(lambda x: x["second_witness"].update(
            account_alias="SIM_SECOND_ACCOUNT"), "P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")
        self.reject(lambda x: x["second_witness"].update(
            fake_utc="2026-11-06T00:00:00Z"), "P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")

    def test_every_field_conflict_refused_even_if_primary_is_well_formed(self):
        for i in range(15):
            with self.subTest(index=i):
                self.reject(lambda x, n=i: x["second_witness"]["rows"][n].update(
                    synthetic_decimal="99.99"),
                    "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:" + str(i + 1))

    def test_unit_and_pair_substitution_refused(self):
        self.reject(lambda x: x["second_witness"]["rows"][4].update(
            unit="POINTS_PER_TICK"), "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:5")
        self.reject(lambda x: x["second_witness"]["rows"][9].update(
            pair="GBP/USD"), "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:10")

    def test_reused_or_cross_field_source_tokens_refused(self):
        self.reject(lambda x: x["second_witness"]["rows"][1].update(
            source_token="SIM_WITNESS_01"),
            "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:2")
        self.reject(lambda x: x["second_witness"]["rows"][11].update(
            field="point_quote"), "P50_SOURCE_VALUE_OR_UNIT_CONFLICT:12")

    def test_missing_rows_and_private_data_columns_refused(self):
        self.reject(lambda x: x["second_witness"]["rows"].pop(),
                  "P50_FIFTEEN_WITNESS_ROWS_REQUIRED")
        self.reject(lambda x: x["second_witness"]["rows"][0].update(
            account_password="CANARY_50"),
            "P50_WITNESS_ROW_SECRET_OR_MISSING:1")

    def test_primary_baseline_must_be_validated_separately(self):
        self.reject(lambda x: x["primary"]["rows"][0].update(
            synthetic_value_decimal="0"),
            "P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID")
        self.reject(lambda x: x["primary"].update(
            order_authorized=True),
            "P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID")

    def test_real_permission_or_p05_signature_spoof_refused(self):
        for key, original in mod.SAFETY.items():
            with self.subTest(key=key):
                new = (not original if type(original) is bool
                       else (1 if type(original) is int else "GO"))
                self.reject(lambda x, k=key, v=new:
                          x["safety"].update({k: v}),
                          "P50_FORGED_REAL_EVIDENCE_OR_PERMISSION")

    def test_unknown_or_sensitive_envelope_fields_refused(self):
        self.reject(lambda x: x.update(account_id="CANARY_50"),
                  "P50_INVALID_OR_EXTRA_PACKAGE_FIELDS")
        self.reject(lambda x: x["second_witness"].update(
            actual_broker_log="CANARY_50"),
            "P50_SECOND_WITNESS_STRUCTURE_INVALID")

    def test_untrusted_root_inputs_do_not_echo_secret(self):
        for inp in (None, [], "", {}, 1, {"password": "CANARY_50"}):
            result = mod.evaluate(inp)
            self.assertEqual(result["status"], "FAIL_CLOSED")
            self.assertNotIn("CANARY_50", str(result))


    def test_fake_safety_false_to_zero_is_not_equivalent(self):
        for key, value in mod.SAFETY.items():
            if type(value) is bool and not value:
                with self.subTest(key=key):
                    self.reject(lambda d,k=key: d["safety"].update({k:0}),
                                "P50_FORGED_REAL_EVIDENCE_OR_PERMISSION")

    def test_fake_safety_int_zero_to_false_is_not_equivalent(self):
        for key, value in mod.SAFETY.items():
            if type(value) is int and value == 0:
                with self.subTest(key=key):
                    self.reject(lambda d,k=key: d["safety"].update({k:False}),
                                "P50_FORGED_REAL_EVIDENCE_OR_PERMISSION")

    def test_root_poison_key_never_computed_after_dict_creation(self):
        class Key:
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash("classification")
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_157")
        d = copy.deepcopy(self.data)
        d.pop("classification")
        d[Key()] = "SIM_TWO_WITNESSES_NOT_REAL_EVIDENCE"
        Key.calls = 0
        state = mod.evaluate(d)
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertIn("P50_INVALID_OR_EXTRA_PACKAGE_FIELDS", state["errors"])
        self.assertEqual(Key.calls, 0)

    def test_second_witness_poison_key_never_rehashed(self):
        class Key:
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash("fake_utc")
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_157")
        d = copy.deepcopy(self.data)
        witness = d["second_witness"]
        val = witness.pop("fake_utc")
        witness[Key()] = val
        Key.calls = 0
        state = mod.evaluate(d)
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertIn("P50_SECOND_WITNESS_STRUCTURE_INVALID", state["errors"])
        self.assertEqual(Key.calls, 0)

    def test_primary_evaluator_exception_fails_closed_without_canary(self):
        from unittest.mock import patch
        with patch.object(mod.base, "check_synthetic_package",
                          side_effect=RuntimeError("PRIVATE_CANARY_157")):
            state = mod.evaluate(copy.deepcopy(self.data))
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertIn("P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID", state["errors"])
        self.assertNotIn("PRIVATE_CANARY_157", str(state))

    def test_primary_evaluator_non_dict_result_is_rejected(self):
        from unittest.mock import patch
        with patch.object(mod.base, "check_synthetic_package",
                          return_value=["PASS_SYNTHETIC_CONTRACT_ONLY"]):
            state = mod.evaluate(copy.deepcopy(self.data))
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertIn("P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID", state["errors"])

    def test_witness_field_poison_comparator_not_called(self):
        class Value:
            calls = 0
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_157")
            def __ne__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_157")
        d = copy.deepcopy(self.data)
        d["second_witness"]["rows"][0]["pair"] = Value()
        state = mod.evaluate(d)
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertIn("P50_SOURCE_VALUE_OR_UNIT_CONFLICT:1", state["errors"])
        self.assertEqual(Value.calls, 0)

    def test_second_witness_scope_object_is_not_compared(self):
        class Value:
            calls = 0
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_157")
        d = copy.deepcopy(self.data)
        d["second_witness"]["account_alias"] = Value()
        state = mod.evaluate(d)
        self.assertEqual(state["status"], "FAIL_CLOSED")
        self.assertIn("P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID", state["errors"])
        self.assertEqual(Value.calls, 0)


    def _forged_primary(self, report):
        with patch.object(mod.base, "check_synthetic_package",
                          return_value=report):
            result = mod.evaluate(copy.deepcopy(self.data))
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID",
                      result["errors"])
        self.assertEqual(result["actual_broker_fields_verified"], 0)
        self.assertFalse(result["actual_source_independence_verified"])
        self.assertFalse(result["real_mt4_read_authorized"])
        self.assertFalse(result["orders_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])
        self.assertNotIn("PRIVATE_CANARY_175", str(result))

    def test_actual_upstream_validator_matches_complete_fixed_schema(self):
        parent = mod.base.check_synthetic_package(self.data["primary"])
        self.assertEqual(parent, mod.EXPECTED_PRIMARY_REPORT)
        self.assertTrue(mod._safe_primary_report(parent))
        accepted = mod.evaluate(self.data)
        self.assertEqual(accepted["status"], "PASS_TWO_FAKE_WITNESSES_ONLY")
        self.assertFalse(accepted["orders_authorized"])

    def test_forged_primary_access_true_cannot_produce_witness_pass(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["real_mt4_read_authorized"] = True
        self._forged_primary(fake)

    def test_forged_primary_order_authorization_true_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["order_authorized"] = True
        self._forged_primary(fake)

    def test_forged_primary_extra_permission_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["live_order_authorized"] = True
        self._forged_primary(fake)

    def test_forged_primary_broker_evidence_count_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["real_broker_values_verified"] = 15
        self._forged_primary(fake)

    def test_forged_primary_passed_p05_count_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["p05_passed"] = 1
        self._forged_primary(fake)

    def test_forged_primary_coverage_count_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["synthetic_rows_expected"] = 14
        self._forged_primary(fake)

    def test_forged_primary_no_go_changed_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["runtime_go_no_go"] = "GO"
        self._forged_primary(fake)

    def test_forged_primary_latch_false_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["safety_hold_latched"] = False
        self._forged_primary(fake)

    def test_forged_primary_bool_int_type_spoof_rejected(self):
        for key, known in mod.EXPECTED_PRIMARY_REPORT.items():
            if type(known) is bool:
                with self.subTest(field=key):
                    fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
                    fake[key] = int(known)
                    self._forged_primary(fake)
            elif type(known) is int:
                with self.subTest(field=key):
                    fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
                    fake[key] = bool(known)
                    self._forged_primary(fake)

    def test_forged_primary_nonempty_error_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["errors"] = ["PRIVATE_CANARY_175"]
        self._forged_primary(fake)

    def test_forged_primary_error_field_missing_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        del fake["errors"]
        self._forged_primary(fake)

    def test_forged_primary_errors_string_instead_of_list_rejected(self):
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["errors"] = ""
        self._forged_primary(fake)

    def test_forged_primary_status_only_is_insufficient(self):
        fake = {"status": "PASS_SYNTHETIC_CONTRACT_ONLY"}
        self._forged_primary(fake)

    def test_forged_primary_dict_subclass_rejected_without_custom_items(self):
        class Rogue(dict):
            calls = 0
            def items(self):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_175")
        fake = Rogue(mod.EXPECTED_PRIMARY_REPORT)
        self._forged_primary(fake)
        self.assertEqual(Rogue.calls, 0)

    def test_forged_primary_comparator_not_executed(self):
        class Poison:
            calls = 0
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_175")
            def __ne__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_175")
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake["runtime_go_no_go"] = Poison()
        self._forged_primary(fake)
        self.assertEqual(Poison.calls, 0)

    def test_forged_primary_unknown_object_key_not_rehashed(self):
        class Key:
            calls = 0
            def __hash__(self):
                type(self).calls += 1
                return hash("UNKNOWN_PRIVATE_CANARY_175")
            def __eq__(self, other):
                type(self).calls += 1
                raise RuntimeError("PRIVATE_CANARY_175")
        fake = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake[Key()] = False
        Key.calls = 0
        self._forged_primary(fake)
        self.assertEqual(Key.calls, 0)

    def test_forged_primary_malformed_result_does_not_echo_secret(self):
        for value in (None, [], "PRIVATE_CANARY_175", 1, False):
            with self.subTest(value=repr(value)):
                self._forged_primary(value)

    def test_strict_primary_report_unchanged_after_forgery_attempts(self):
        before = copy.deepcopy(mod.EXPECTED_PRIMARY_REPORT)
        fake = copy.deepcopy(before)
        fake["errors"].append("PRIVATE_CANARY_175")
        self._forged_primary(fake)
        self.assertEqual(mod.EXPECTED_PRIMARY_REPORT, before)
        self.assertTrue(mod._safe_primary_report(
            mod.base.check_synthetic_package(self.data["primary"])))


if __name__ == "__main__":
    unittest.main()
