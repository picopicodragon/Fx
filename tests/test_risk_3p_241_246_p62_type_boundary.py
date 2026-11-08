"""RISK-3P-241..246: P62 Q109 mock traceability keys fail closed."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from scripts import audit_risk_3p_62_offline_traceability_graph as p62

CANARY = "P62_SIMULATED_SECRET_DO_NOT_ECHO"


class HostileKey:
    def __hash__(self):
        return 620001

    def __eq__(self, other):
        raise AssertionError(CANARY)


class HostileStr(str):
    def __hash__(self):
        return 620002

    def __eq__(self, other):
        raise AssertionError(CANARY)


class HostileDict(dict):
    def get(self, *args, **kwargs):
        raise AssertionError(CANARY)


class P62TypeBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((p62.ROOT / p62.TRACE).read_text(encoding="utf-8"))

    def assert_denied(self, altered, expected=None):
        result = p62.snapshot(data=altered)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(result["real_mt4_read_authorized"], False)
        self.assertIs(result["order_execution_authorized"], False)
        if expected is not None:
            self.assertIn(expected, result["errors"])
        self.assertNotIn(CANARY, str(result))

    def test_241_existing_manifest_remains_mock_only_pass(self):
        result = p62.snapshot()
        self.assertEqual(result["status"], "PASS_OFFLINE_Q109_LINKS_ONLY", result)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_241_manifest_dict_subclass_rejected(self):
        self.assert_denied(HostileDict(self.manifest),
                           "P62_INVALID_TRACEABILITY_MANIFEST")

    def test_242_root_custom_key_not_compared(self):
        manifest = copy.deepcopy(self.manifest)
        manifest[HostileKey()] = CANARY
        self.assert_denied(manifest, "P62_INVALID_TRACEABILITY_MANIFEST")

    def test_242_root_str_subclass_not_compared(self):
        manifest = copy.deepcopy(self.manifest)
        manifest[HostileStr("extra")] = CANARY
        self.assert_denied(manifest, "P62_INVALID_TRACEABILITY_MANIFEST")

    def test_243_row_custom_key_not_compared(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["offline_synthetic_mappings"][0][HostileKey()] = CANARY
        self.assert_denied(manifest, "P62_SCHEMA_OR_SECRET_FIELD:1")

    def test_243_row_str_subclass_not_compared(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["offline_synthetic_mappings"][0][HostileStr("token")] = CANARY
        self.assert_denied(manifest, "P62_SCHEMA_OR_SECRET_FIELD:1")

    def test_243_row_dict_subclass_denied(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["offline_synthetic_mappings"][0] = HostileDict(
            manifest["offline_synthetic_mappings"][0])
        self.assert_denied(manifest, "P62_SCHEMA_OR_SECRET_FIELD:1")

    def test_244_boolean_disguised_as_permission_denied(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["offline_synthetic_mappings"][0]["production_authorized"] = 0
        self.assert_denied(manifest, "P62_MOCK_ONLY_RUNTIME_PERMISSION:1")

    def test_244_wrong_mapping_collection_denied(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["offline_synthetic_mappings"] = {}
        self.assert_denied(manifest, "P62_INVALID_TRACEABILITY_MANIFEST")

    def test_245_unexpected_child_auditor_exception_denied(self):
        with patch.object(p62.pinned, "_read", side_effect=RuntimeError(CANARY)):
            result = p62.snapshot(data=copy.deepcopy(self.manifest))
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P62_CANNOT_READ_PUBLIC_TRACEABILITY", result["errors"])
        self.assertNotIn(CANARY, str(result))

    def test_245_unexpected_child_validation_exception_denied(self):
        with patch.object(p62.pinned, "audit", side_effect=AssertionError(CANARY)):
            result = p62.snapshot(data=copy.deepcopy(self.manifest))
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P62_CANNOT_READ_PUBLIC_TRACEABILITY", result["errors"])
        self.assertNotIn(CANARY, str(result))

    def test_246_failure_then_clean_mock_audit(self):
        self.assert_denied({"private": CANARY}, "P62_INVALID_TRACEABILITY_MANIFEST")
        self.assertEqual(p62.snapshot()["status"], "PASS_OFFLINE_Q109_LINKS_ONLY")


if __name__ == "__main__":
    unittest.main()
