"""RISK-3P-199..204: P61 untrusted keys and value types fail closed.

All records are fictional; no network, MT4, EA, broker or orders.
"""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_61_strict_offline_result_contract as strict


class ExplosiveKey:
    def __hash__(self):
        return 0x7FEE11

    def __eq__(self, other):
        raise AssertionError("P61 must not compare untrusted keys")


class ExplosiveText(str):
    def __hash__(self):
        return 0x7FEE12

    def __eq__(self, other):
        raise AssertionError("P61 must not compare str subclasses")


class ExplosiveValue:
    def __eq__(self, other):
        raise AssertionError("P61 must not compare untrusted values")


class DictSubclass(dict):
    def keys(self):
        raise AssertionError("P61 must reject dict subclasses")


class ListSubclass(list):
    def __iter__(self):
        raise AssertionError("P61 must reject list subclasses")


class StrictP61AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.records = copy.deepcopy(strict.EXPECTED)

    def assert_denied(self, records):
        result = strict.snapshot(records)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(result["real_mt4_read_authorized"], False)
        self.assertIs(result["real_order_execution_authorized"], False)
        self.assertIs(result["actual_broker_evidence_authenticated"], False)
        self.assertNotIn("CANARY_P61_SECRET", str(result))

    def test_199_original_offline_contract_remains_valid(self):
        self.assertEqual(strict.snapshot(self.records)["status"],
                         "PASS_EXACT_OFFLINE_RESULTS_ONLY")

    def test_199_wrong_root_type_denied(self):
        self.assert_denied([self.records])

    def test_199_root_dict_subclass_denied(self):
        self.assert_denied(DictSubclass(self.records))

    def test_200_untrusted_root_object_key_not_compared(self):
        self.records[ExplosiveKey()] = "CANARY_P61_SECRET"
        self.assert_denied(self.records)

    def test_200_untrusted_root_str_subclass_not_compared(self):
        self.records[ExplosiveText("forged")] = "CANARY_P61_SECRET"
        self.assert_denied(self.records)

    def test_200_unknown_root_plain_key_denied(self):
        self.records["order_authorized"] = True
        self.assert_denied(self.records)

    def test_201_untrusted_child_object_key_not_compared(self):
        self.records["fake_clocks"][ExplosiveKey()] = True
        self.assert_denied(self.records)

    def test_201_untrusted_child_str_subclass_not_compared(self):
        self.records["safe_diagnostics"][ExplosiveText("extra")] = True
        self.assert_denied(self.records)

    def test_201_child_dict_subclass_denied(self):
        self.records["fictional_ingress"] = DictSubclass(
            self.records["fictional_ingress"])
        self.assert_denied(self.records)

    def test_202_untrusted_child_comparison_value_denied(self):
        self.records["unsigned_future_handoff"]["status"] = ExplosiveValue()
        self.assert_denied(self.records)

    def test_202_boolean_integer_conflation_denied(self):
        self.records["safe_diagnostics"]["p05_passed"] = False
        self.assert_denied(self.records)

    def test_202_boolean_integer_conflation_on_permission_denied(self):
        self.records["safe_diagnostics"]["real_mt4_read_authorized"] = 0
        self.assert_denied(self.records)

    def test_203_errors_list_subclass_denied(self):
        self.records["fake_clocks"]["errors"] = ListSubclass()
        self.assert_denied(self.records)

    def test_203_unknown_inner_permission_field_denied(self):
        self.records["fictional_ingress"]["enable_live_orders"] = True
        self.assert_denied(self.records)

    def test_204_untrusted_report_class_denied_without_comparison(self):
        self.assertEqual(strict.check(ExplosiveText("fake_clocks"), {}),
                         ["P61_UNKNOWN_REPORT_CLASS"])

    def test_204_bad_record_rejected_without_secret_echo(self):
        self.assertEqual(strict.check("fake_clocks", {
            "private_token": "CANARY_P61_SECRET"}),
            ["P61_UNKNOWN_FIELD_TYPE_OR_VALUE_DRIFT:3"])


if __name__ == "__main__":
    unittest.main()
