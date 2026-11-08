"""RISK-3P-211..216: strict mock-only P65 governance result ingress."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_65_integrated_offline_audit as audit


class HostileKey:
    def __hash__(self):
        return 0x65001

    def __eq__(self, other):
        raise AssertionError("untrusted key comparison")


class HostileText(str):
    def __hash__(self):
        return 0x65002

    def __eq__(self, other):
        raise AssertionError("untrusted string comparison")


class HostileValue:
    def __eq__(self, other):
        raise AssertionError("untrusted value comparison")


class HostileDict(dict):
    def get(self, *args, **kwargs):
        raise AssertionError("untrusted subclass get")


class HostileList(list):
    def __eq__(self, other):
        raise AssertionError("untrusted subclass equality")


class GovernanceBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = dict(zip(audit.NAMES, audit._outputs()))

    def assert_denied(self, injected):
        result = audit.evaluate(injected=injected)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(result["automatic_main_merge_authorized"], False)
        self.assertIs(result["ea_or_order_execution_authorized"], False)
        self.assertIs(result["real_mt4_observation_authorized"], False)
        self.assertNotIn("CANARY_P65_PRIVATE", str(result))

    def row(self, name="existing_mock_quality"):
        return copy.deepcopy(self.baseline[name])

    def test_211_clean_synthetic_baseline_passes(self):
        self.assertEqual(audit.evaluate()["status"], "PASS_GOVERNANCE_DESIGN_ONLY")

    def test_211_wrong_root_type(self):
        self.assert_denied([])

    def test_211_root_dict_subclass(self):
        self.assert_denied(HostileDict({"existing_mock_quality": self.row()}))

    def test_212_untrusted_root_key(self):
        self.assert_denied({HostileKey(): "CANARY_P65_PRIVATE"})

    def test_212_root_str_subclass(self):
        self.assert_denied({HostileText("existing_mock_quality"): self.row()})

    def test_212_unknown_plain_root_key(self):
        self.assert_denied({"order_credentials": "CANARY_P65_PRIVATE"})

    def test_213_untrusted_child_key(self):
        row = self.row()
        row[HostileKey()] = True
        self.assert_denied({"existing_mock_quality": row})

    def test_213_child_str_subclass(self):
        row = self.row()
        row[HostileText("extra")] = True
        self.assert_denied({"existing_mock_quality": row})

    def test_213_child_dict_subclass(self):
        self.assert_denied({"existing_mock_quality": HostileDict(self.row())})

    def test_214_status_custom_eq(self):
        row = self.row()
        row["status"] = HostileValue()
        self.assert_denied({"existing_mock_quality": row})

    def test_214_runtime_custom_eq(self):
        row = self.row()
        row["runtime_go_no_go"] = HostileValue()
        self.assert_denied({"existing_mock_quality": row})

    def test_214_errors_list_subclass(self):
        row = self.row()
        row["errors"] = HostileList()
        self.assert_denied({"existing_mock_quality": row})

    def test_215_counter_boolean_alias(self):
        row = self.row()
        row["p05_passed"] = False
        self.assert_denied({"existing_mock_quality": row})

    def test_215_real_permission_numeric_alias(self):
        row = self.row()
        row["real_mt4_access_authorized"] = 0
        self.assert_denied({"existing_mock_quality": row})

    def test_216_extra_order_permission(self):
        row = self.row()
        row["order_authorized"] = True
        self.assert_denied({"existing_mock_quality": row})

    def test_216_injected_failure_does_not_mutate_baseline(self):
        baseline = copy.deepcopy(self.baseline)
        self.assert_denied({"existing_mock_quality": {"secret": "CANARY_P65_PRIVATE"}})
        self.assertEqual(self.baseline, baseline)


if __name__ == "__main__":
    unittest.main()
