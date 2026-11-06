"""Q109 offline mapping audit prevents untracked safety source or test paths."""
from __future__ import annotations

import copy
import json
import unittest

from scripts import audit_risk_3p_62_offline_traceability_graph as mod


class SourceTraceabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((mod.ROOT / mod.TRACE).read_text(encoding="utf-8"))

    def reject(self, edit, code):
        d = copy.deepcopy(self.data)
        edit(d)
        r = mod.snapshot(data=d)
        self.assertEqual(r["status"], "FAIL_CLOSED", r)
        self.assertIn(code, r["errors"], r)
        self.assertFalse(r["all_sources_production_authorized"])
        self.assertFalse(r["real_evidence_or_signoff_verified"])
        self.assertFalse(r["real_mt4_read_authorized"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(r["safety_hold_latched"])

    def test_complete_traceability_manifest_remains_offline_and_mapped(self):
        self.assertEqual(mod.audit(), [])
        r = mod.snapshot()
        self.assertEqual(r["status"], "PASS_OFFLINE_Q109_LINKS_ONLY")
        self.assertFalse(r["runtime_dependency_closure_verified"])
        self.assertGreaterEqual(len(self.data["offline_synthetic_mappings"]), 41)

    def test_duplicate_source_cannot_hide_in_repository_map(self):
        self.reject(lambda d: d["offline_synthetic_mappings"].append(
            copy.deepcopy(d["offline_synthetic_mappings"][0])),
            "P62_DUPLICATE_SOURCE_MAPPING:" +
            str(len(self.data["offline_synthetic_mappings"]) + 1))

    def test_production_authorization_cannot_be_changed(self):
        self.reject(lambda d: d["offline_synthetic_mappings"][0].update(
            production_authorized=True),
            "P62_MOCK_ONLY_RUNTIME_PERMISSION:1")

    def test_secret_or_extra_fields_refused(self):
        self.reject(lambda d: d["offline_synthetic_mappings"][0].update(
            real_broker_password="CANARY_62"),
            "P62_SCHEMA_OR_SECRET_FIELD:1")

    def test_unsafe_path_traversal_and_outside_repository_paths_rejected(self):
        for bad in ("scripts/../private.py", "/tmp/private.py",
                    "scripts/real\\windows.py", "C:\\Users\\Private.py",
                    "specs/fake.py", "scripts/subdir/unsafe.py"):
            with self.subTest(path=bad):
                self.reject(
                    lambda d, x=bad: d["offline_synthetic_mappings"][0].update(
                        source=x),
                    "P62_UNSAFE_SOURCE_PATH:1")

    def test_unsafe_test_paths_and_missing_files_rejected(self):
        self.reject(lambda d: d["offline_synthetic_mappings"][0].update(
            tests=["tests/../private.py"]),
            "P62_INVALID_TEST_PATH:1")
        self.reject(lambda d: d["offline_synthetic_mappings"][0].update(
            tests=["tests/test_file_never_created_62.py"]),
            "P62_SOURCE_OR_TEST_MISSING:1")

    def test_invalid_spec_ids_or_duplicate_tests_rejected(self):
        self.reject(lambda d: d["offline_synthetic_mappings"][0].update(
            spec_ids=["INVALID PRIVATE VALUE"]),
            "P62_INVALID_SPEC_TRACE:1")
        self.reject(lambda d: d["offline_synthetic_mappings"][0].update(
            tests=[d["offline_synthetic_mappings"][0]["tests"][0]] * 2),
            "P62_INVALID_TEST_PATH:1")

    def test_new_modules_cannot_be_untracked_silently(self):
        self.reject(lambda d: d["offline_synthetic_mappings"].pop(0),
                    "P62_NEW_SAFETY_SOURCES_UNTRACKED")

    def test_malformed_manifest_never_echoes_sensitive_value(self):
        result = mod.snapshot(data={"secret": "CANARY_62"})
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn("CANARY_62", str(result))
        self.assertFalse(result["real_mt4_read_authorized"])


if __name__ == "__main__":
    unittest.main()
