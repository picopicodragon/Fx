"""RISK-3P-253..258: pinned public mock source inventory strict types.

Offline only. No MT4, EA, broker, orders or private source archive.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts import audit_risk_3p_67_source_index as p67

CANARY = "P67_SIM_PRIVATE_CANARY_NO_ECHO"


class HostileKey:
    def __hash__(self):
        return 670001

    def __eq__(self, other):
        raise AssertionError(CANARY)


class HostileText(str):
    def __eq__(self, other):
        raise AssertionError(CANARY)


class HostileDict(dict):
    def get(self, *args, **kwargs):
        raise AssertionError(CANARY)


class HostileValue:
    def __eq__(self, other):
        raise AssertionError(CANARY)


class P67PinnedTypeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {p: p67._read(p67.ROOT, p) for p in (p67.TRACE, p67.PINNED)}

    def denied(self, mutate, expected):
        docs = copy.deepcopy(self.docs)
        mutate(docs)
        result = p67.snapshot(injected=docs)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(expected, result["errors"], result)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(result["real_mt4_access_authorized"], False)
        self.assertIs(result["main_auto_merge_authorized"], False)
        self.assertEqual(result["p05_passed"], 0)
        self.assertEqual(result["g1_real_verified"], 0)
        self.assertNotIn(CANARY, str(result))

    def test_253_normal_exact_45_mock_sources(self):
        self.assertEqual(p67.audit(), [])
        r = p67.snapshot()
        self.assertEqual(r["status"], "PASS_PINNED_OFFLINE_INVENTORY_ONLY")
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_253_root_hostile_key_not_compared(self):
        self.denied(lambda d: d.update({HostileKey(): CANARY}),
                    "P67_SOURCE_INDEX_OR_TRACE_INVALID")

    def test_254_root_dict_subclass_not_consulted(self):
        d = HostileDict(copy.deepcopy(self.docs))
        result = p67.snapshot(injected=d)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P67_SOURCE_INDEX_OR_TRACE_INVALID", result["errors"])

    def test_254_pinned_hostile_key_not_compared(self):
        self.denied(lambda d: d[p67.PINNED].update({HostileKey(): CANARY}),
                    "P67_SOURCE_INDEX_OR_TRACE_INVALID")

    def test_254_trace_hostile_key_not_compared(self):
        self.denied(lambda d: d[p67.TRACE].update({HostileKey(): CANARY}),
                    "P67_SOURCE_INDEX_OR_TRACE_INVALID")

    def test_255_mapping_hostile_key_not_compared(self):
        self.denied(lambda d: d[p67.TRACE]["offline_synthetic_mappings"][0].update(
            {HostileKey(): CANARY}), "P67_TRACEABILITY_ROWS_NOT_OFFLINE")

    def test_255_mapping_dict_subclass_rejected(self):
        self.denied(lambda d: d[p67.TRACE]["offline_synthetic_mappings"].__setitem__(
            0, HostileDict(d[p67.TRACE]["offline_synthetic_mappings"][0])),
                    "P67_TRACEABILITY_ROWS_NOT_OFFLINE")

    def test_256_safety_hostile_key_not_compared(self):
        self.denied(lambda d: d[p67.PINNED]["safety"].update(
            {HostileKey(): CANARY}), "P67_REAL_PERMISSION_OR_MERGE_FORGED")

    def test_256_permission_boolean_integer_confusion_rejected(self):
        self.denied(lambda d: d[p67.PINNED]["safety"].update(
            production_approval_granted=0), "P67_REAL_PERMISSION_OR_MERGE_FORGED")

    def test_256_safety_custom_comparison_value_rejected(self):
        self.denied(lambda d: d[p67.PINNED]["safety"].update(
            runtime_go_no_go=HostileValue()), "P67_REAL_PERMISSION_OR_MERGE_FORGED")

    def test_257_scope_str_subclass_not_compared(self):
        self.denied(lambda d: d[p67.PINNED].update(
            scope=HostileText("RISK-3P-67-72")), "P67_PINNED_INDEX_SCOPE_CHANGED")

    def test_257_malformed_source_list_rejected(self):
        self.denied(lambda d: d[p67.PINNED].update(sources=[HostileValue()]),
                    "P67_EXPECTED_45_UNIQUE_SOURCE_NAMES")

    def test_258_unexpected_public_read_exception_fixed(self):
        with patch.object(p67, "_read", side_effect=RuntimeError(CANARY)):
            result = p67.snapshot()
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P67_PUBLIC_INDEX_READ_OR_SCHEMA_FAILURE", result["errors"])
        self.assertNotIn(CANARY, str(result))

    def test_258_failure_followed_by_clean_audit(self):
        self.denied(lambda d: d[p67.PINNED]["safety"].update(
            real_mt4_access_authorized=True), "P67_REAL_PERMISSION_OR_MERGE_FORGED")
        self.assertEqual(p67.snapshot()["status"], "PASS_PINNED_OFFLINE_INVENTORY_ONLY")


if __name__ == "__main__":
    unittest.main()
