"""Pinned Q109 inventory: omission, replacement and fake approval regressions."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_67_source_index as mod


class PinnedOfflineIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {p: mod._read(mod.ROOT, p) for p in (mod.TRACE, mod.PINNED)}

    def refuse(self, path, mutation, code):
        docs = copy.deepcopy(self.docs)
        mutation(docs[path])
        result = mod.snapshot(injected=docs)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(code, result["errors"])
        self.assertFalse(result["real_source_authenticity_verified"])
        self.assertFalse(result["real_mt4_access_authorized"])
        self.assertFalse(result["main_auto_merge_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_baseline_has_45_pinned_mock_sources(self):
        r = mod.snapshot()
        self.assertEqual(r["status"], "PASS_PINNED_OFFLINE_INVENTORY_ONLY")
        self.assertEqual(r["expected_offline_sources"], 45)
        self.assertEqual(r["p05_passed"], 0)
        self.assertEqual(r["g1_real_verified"], 0)

    def test_deleting_any_historical_mapping_fails(self):
        for n in (0, 12, 27, 44):
            with self.subTest(n=n):
                self.refuse(mod.TRACE,
                            lambda d, i=n: d["offline_synthetic_mappings"].pop(i),
                            "P67_TRACEABILITY_ROWS_NOT_OFFLINE")

    def test_replacing_old_mapping_without_count_change_fails(self):
        self.refuse(mod.TRACE,
                    lambda d: d["offline_synthetic_mappings"][33].update(
                        source="scripts/unreviewed_mock_new.py"),
                    "P67_OMITTED_OR_UNREVIEWED_SOURCE_MAPPING")

    def test_duplicate_mapped_source_detected(self):
        self.refuse(mod.TRACE,
                    lambda d: d["offline_synthetic_mappings"][5].update(
                        source=d["offline_synthetic_mappings"][6]["source"]),
                    "P67_OMITTED_OR_UNREVIEWED_SOURCE_MAPPING")

    def test_fake_production_permission_rejected(self):
        self.refuse(mod.TRACE,
                    lambda d: d["offline_synthetic_mappings"][0].update(
                        production_authorized=True),
                    "P67_TRACEABILITY_ROWS_NOT_OFFLINE")
        self.refuse(mod.PINNED,
                    lambda d: d["safety"].update(main_auto_merge_authorized=True),
                    "P67_REAL_PERMISSION_OR_MERGE_FORGED")

    def test_pinned_index_cannot_drop_entries(self):
        self.refuse(mod.PINNED, lambda d: d["sources"].pop(),
                    "P67_EXPECTED_45_UNIQUE_SOURCE_NAMES")
        self.refuse(mod.PINNED, lambda d: d["sources"].reverse(),
                    "P67_EXPECTED_45_UNIQUE_SOURCE_NAMES")

    def test_unknown_private_columns_are_rejected(self):
        self.refuse(mod.PINNED,
                    lambda d: d.update(password="CANARY_67"),
                    "P67_PINNED_INDEX_SCOPE_CHANGED")
        self.refuse(mod.TRACE,
                    lambda d: d["offline_synthetic_mappings"][0].update(
                        account_login="CANARY_67"),
                    "P67_TRACEABILITY_ROWS_NOT_OFFLINE")

    def test_bool_version_not_equal_int_version(self):
        self.refuse(mod.PINNED,
                    lambda d: d.update(schema_version=True),
                    "P67_PINNED_INDEX_SCOPE_CHANGED")

    def test_missing_document_and_secret_not_reflected(self):
        docs = copy.deepcopy(self.docs)
        docs.pop(mod.PINNED)
        self.assertIn("P67_PUBLIC_INDEX_READ_OR_SCHEMA_FAILURE",
                      mod.audit(injected=docs))
        docs = copy.deepcopy(self.docs)
        docs[mod.PINNED] = {"password": "CANARY_67"}
        result = mod.snapshot(injected=docs)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn("CANARY_67", str(result))


if __name__ == "__main__":
    unittest.main()
