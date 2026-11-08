"""RISK-3P-205..210 P60 offline input boundary, never actual broker safety."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_60_offline_ingress_quality_gate as gate


class DangerousKey:
    def __hash__(self):
        return 0x79001

    def __eq__(self, other):
        raise AssertionError("untrusted key comparison")


class DangerousText(str):
    def __hash__(self):
        return 0x79002

    def __eq__(self, other):
        raise AssertionError("untrusted string subclass comparison")


class DangerousValue:
    def __eq__(self, other):
        raise AssertionError("untrusted value comparison")


class DictSubclass(dict):
    def get(self, *args, **kwargs):
        raise AssertionError("dict subclass used")


class ListSubclass(list):
    def __eq__(self, other):
        raise AssertionError("list subclass equality")


class P60BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = dict(zip(gate.NAMES, gate._outputs()))

    def assert_closed(self, injected):
        r = gate.evaluate(injected=injected)
        self.assertEqual(r["status"], "FAIL_CLOSED", r)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertIs(r["safety_hold_latched"], True)
        self.assertIs(r["real_mt4_access_authorized"], False)
        self.assertIs(r["real_order_or_ea_action_authorized"], False)
        self.assertNotIn("P60_CANARY_SECRET", str(r))

    def mock_row(self, name="fictional_ingress"):
        return copy.deepcopy(self.baseline[name])

    def test_205_normal_offline_snapshot_unchanged(self):
        self.assertEqual(gate.evaluate()["status"],
                         "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY")

    def test_205_unknown_plain_root_key_denied(self):
        self.assert_closed({"unknown_key": "P60_CANARY_SECRET"})

    def test_205_non_dict_injection_denied(self):
        self.assert_closed(["fictional_ingress"])

    def test_206_custom_root_key_never_compared(self):
        self.assert_closed({DangerousKey(): "P60_CANARY_SECRET"})

    def test_206_root_str_subclass_never_compared(self):
        self.assert_closed({DangerousText("fictional_ingress"): self.mock_row()})

    def test_206_dict_subclass_never_consulted(self):
        self.assert_closed(DictSubclass({"fictional_ingress": self.mock_row()}))

    def test_207_custom_child_key_never_compared(self):
        row = self.mock_row()
        row[DangerousKey()] = "P60_CANARY_SECRET"
        self.assert_closed({"fictional_ingress": row})

    def test_207_child_str_subclass_never_compared(self):
        row = self.mock_row()
        row[DangerousText("x")] = "P60_CANARY_SECRET"
        self.assert_closed({"fictional_ingress": row})

    def test_207_child_dict_subclass_denied(self):
        self.assert_closed({"fictional_ingress": DictSubclass(self.mock_row())})

    def test_208_custom_status_value_never_compared(self):
        row = self.mock_row()
        row["status"] = DangerousValue()
        self.assert_closed({"fictional_ingress": row})

    def test_208_custom_runtime_value_never_compared(self):
        row = self.mock_row()
        row["runtime_go_no_go"] = DangerousValue()
        self.assert_closed({"fictional_ingress": row})

    def test_208_custom_errors_list_never_compared(self):
        row = self.mock_row()
        row["errors"] = ListSubclass()
        self.assert_closed({"fictional_ingress": row})

    def test_209_bool_int_counter_confusion_denied(self):
        row = self.mock_row()
        row["p05_passed"] = False
        self.assert_closed({"fictional_ingress": row})

    def test_209_fake_permission_denied(self):
        row = self.mock_row()
        row["real_mt4_read_authorized"] = 0
        self.assert_closed({"fictional_ingress": row})

    def test_210_extra_synthetic_case_denied(self):
        self.assert_closed({"fictional_ingress": self.mock_row(),
                            "secret_order": "P60_CANARY_SECRET"})

    def test_210_failure_does_not_change_baseline(self):
        unchanged = copy.deepcopy(self.baseline)
        self.assert_closed({"fictional_ingress": {"bad": DangerousValue()}})
        self.assertEqual(self.baseline, unchanged)


if __name__ == "__main__":
    unittest.main()
