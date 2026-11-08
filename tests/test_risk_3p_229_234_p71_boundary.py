"""RISK-3P-229..234 P71 composite mock gate input/exception regression.

No live orders, network, MT4, EA, human approvals, original archives or secrets.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts import risk_3p_71_offline_integrity_gate as gate

CANARY = "P71_FAKE_PRIVATE_CANARY_NOT_FOR_OUTPUT"


class UnsafeKey:
    def __hash__(self):
        return 0x71001

    def __eq__(self, other):
        raise AssertionError(CANARY)


class UnsafeText(str):
    def __hash__(self):
        return 0x71002

    def __eq__(self, other):
        raise AssertionError(CANARY)


class UnsafeValue:
    def __eq__(self, other):
        raise AssertionError(CANARY)


class UnsafeDict(dict):
    def get(self, *args, **kwargs):
        raise AssertionError(CANARY)


class UnsafeList(list):
    def __eq__(self, other):
        raise AssertionError(CANARY)


class P71BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = gate._outputs()

    def result(self, injected=None, *, outputs=None):
        rows = copy.deepcopy(self.baseline) if outputs is None else outputs
        with patch.object(gate, "_outputs", return_value=rows):
            return gate.evaluate(injected=injected)

    def assert_denied(self, outcome, code=None):
        self.assertEqual(outcome["status"], "FAIL_CLOSED", outcome)
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")
        self.assertIs(outcome["safety_hold_latched"], True)
        self.assertIs(outcome["real_mt4_observation_authorized"], False)
        self.assertIs(outcome["real_order_execution_authorized"], False)
        self.assertIs(outcome["main_auto_merge_authorized"], False)
        self.assertEqual(outcome["p05_passed"], 0)
        self.assertEqual(outcome["g1_real_verified"], 0)
        self.assertNotIn(CANARY, str(outcome))
        if code:
            self.assertIn(code, outcome["errors"])

    def test_229_normal_combined_offline_pass_no_go(self):
        outcome = self.result()
        self.assertEqual(outcome["status"], "PASS_OFFLINE_INTEGRITY_ONLY", outcome)
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")

    def test_229_root_must_be_builtin_dict(self):
        self.assert_denied(self.result(injected=[]), "P71_UNKNOWN_OR_PRIVATE_RESULT_NAME")

    def test_229_root_dict_subclass_denied(self):
        self.assert_denied(self.result(injected=UnsafeDict()), "P71_UNKNOWN_OR_PRIVATE_RESULT_NAME")

    def test_230_untrusted_root_key_not_compared(self):
        self.assert_denied(self.result(injected={UnsafeKey(): CANARY}), "P71_UNKNOWN_OR_PRIVATE_RESULT_NAME")

    def test_230_root_str_subclass_not_compared(self):
        self.assert_denied(self.result(injected={UnsafeText("invalid"): CANARY}), "P71_UNKNOWN_OR_PRIVATE_RESULT_NAME")

    def test_230_unknown_plain_key_denied(self):
        self.assert_denied(self.result(injected={"broker_password": CANARY}), "P71_UNKNOWN_OR_PRIVATE_RESULT_NAME")

    def test_231_untrusted_child_key_not_compared(self):
        row = copy.deepcopy(self.baseline[0])
        row[UnsafeKey()] = CANARY
        self.assert_denied(self.result(injected={gate.NAMES[0]: row}), "P71_CHILD_REPORT_MISSING_OR_INVALID:1")

    def test_231_child_str_subclass_not_compared(self):
        row = copy.deepcopy(self.baseline[0])
        row[UnsafeText("extra")] = CANARY
        self.assert_denied(self.result(injected={gate.NAMES[0]: row}), "P71_CHILD_REPORT_MISSING_OR_INVALID:1")

    def test_231_child_dict_subclass_denied(self):
        self.assert_denied(self.result(injected={gate.NAMES[0]: UnsafeDict(self.baseline[0])}),
                           "P71_CHILD_REPORT_MISSING_OR_INVALID:1")

    def test_232_untrusted_status_value_not_compared(self):
        row = copy.deepcopy(self.baseline[0])
        row["status"] = UnsafeValue()
        self.assert_denied(self.result(injected={gate.NAMES[0]: row}), "P71_CHILD_REPORT_MISSING_OR_INVALID:1")

    def test_232_untrusted_runtime_value_not_compared(self):
        row = copy.deepcopy(self.baseline[0])
        row["runtime_go_no_go"] = UnsafeValue()
        self.assert_denied(self.result(injected={gate.NAMES[0]: row}), "P71_CHILD_REPORT_MISSING_OR_INVALID:1")

    def test_232_untrusted_errors_list_not_compared(self):
        row = copy.deepcopy(self.baseline[0])
        row["errors"] = UnsafeList()
        self.assert_denied(self.result(injected={gate.NAMES[0]: row}), "P71_CHILD_REPORT_MISSING_OR_INVALID:1")

    def test_233_boolean_integer_counter_conflation_denied(self):
        row = copy.deepcopy(self.baseline[0])
        row["p05_passed"] = False
        self.assert_denied(self.result(injected={gate.NAMES[0]: row}), "P71_UNREVIEWED_CHILD_FIELD_OR_TYPE:1")

    def test_233_extra_order_authority_denied(self):
        row = copy.deepcopy(self.baseline[0])
        row["live_order_authorized"] = True
        self.assert_denied(self.result(injected={gate.NAMES[0]: row}), "P71_UNREVIEWED_CHILD_FIELD_OR_TYPE:1")

    def test_234_unknown_exception_returns_fixed_code(self):
        with patch.object(gate, "_outputs", side_effect=RuntimeError(CANARY)):
            self.assert_denied(gate.evaluate(), "P71_OFFLINE_EVALUATOR_FAILURE")

    def test_234_short_output_tuple_denied_without_partial_success(self):
        self.assert_denied(self.result(outputs=self.baseline[:6]),
                           "P71_INCOMPLETE_SEVEN_GATE_CHAIN")

    def test_234_failure_followed_by_clean_offline_call(self):
        with patch.object(gate, "_outputs", side_effect=RuntimeError(CANARY)):
            self.assert_denied(gate.evaluate(), "P71_OFFLINE_EVALUATOR_FAILURE")
        self.assertEqual(self.result()["status"], "PASS_OFFLINE_INTEGRITY_ONLY")


if __name__ == "__main__":
    unittest.main()
