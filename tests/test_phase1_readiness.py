"""Synthetic-only tests of PHASE-1 metadata audit; no brokerage connection."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "phase1_readiness.py"
spec = importlib.util.spec_from_file_location("phase1_readiness", MODULE)
assert spec is not None and spec.loader is not None
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class Phase1ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "specs").mkdir()
        self.write("source_review_priority.json", {"items": [
            {"requirement_id": "FX-SAF-001", "source_review": "PENDING_ORIGINAL",
             "spec_comparison": "NOT_REVIEWED", "human_safety_approval": False}
        ]})
        self.write("reconciliation_registry.json", {"items": [
            {"requirement_id": "FX-SAF-001", "source_kind": "SUMMARY_ONLY",
             "comparison_status": "SOURCE_UNAVAILABLE", "implementation_approved": False,
             "owner_approval": None}
        ]})
        self.write("acceptance_registry.json", {"phases": [
            {"id": "PHASE-1", "status": "IN_PROGRESS", "approval": None}
        ]})

    def write(self, file_name, value):
        (self.root / "specs" / file_name).write_text(
            json.dumps(value), encoding="utf-8"
        )

    def test_unreviewed_and_missing_items_block_evidence(self):
        report = readiness.audit(self.root)
        self.assertFalse(report["evidence_metadata_complete"])
        self.assertEqual(len(report["pending_source_ids"]), 15)
        self.assertEqual(len(report["pending_reconciliation_ids"]), 15)
        self.assertFalse(report["safety_implementation_authorized"])
        self.assertFalse(report["ready_for_live_trading"])

    def test_even_complete_metadata_cannot_authorize_trading_or_implementation(self):
        keys = [f"FX-SAF-{n:03d}" for n in range(1, 16)]
        self.write("source_review_priority.json", {"items": [
            {"requirement_id": k, "source_review": "EXCERPT_VERIFIED",
             "spec_comparison": "COMPARISON_MATCHED", "human_safety_approval": True}
            for k in keys
        ]})
        self.write("reconciliation_registry.json", {"items": [
            {"requirement_id": k, "source_kind": "ORIGINAL", "comparison_status": "MATCH",
             "implementation_approved": True,
             "owner_approval": {"approved_by": "synthetic", "approved_at": "sample",
                                "decision_reference": "sample"},
             "source_reference": "synthetic", "issues": []}
            for k in keys
        ]})
        report = readiness.audit(self.root)
        self.assertTrue(report["evidence_metadata_complete"])
        self.assertFalse(report["safety_implementation_authorized"])
        self.assertFalse(report["ready_for_live_trading"])

    def test_missing_review_collection_is_error(self):
        self.write("source_review_priority.json", {"items": []})
        with self.assertRaises(ValueError):
            readiness.audit(self.root)

    def test_missing_reconciliation_collection_is_error(self):
        self.write("reconciliation_registry.json", {"items": []})
        with self.assertRaises(ValueError):
            readiness.audit(self.root)

    def test_duplicate_requirement_is_error(self):
        item = {"requirement_id": "FX-SAF-001"}
        self.write("source_review_priority.json", {"items": [item, item]})
        with self.assertRaises(ValueError):
            readiness.audit(self.root)


if __name__ == "__main__":
    unittest.main()
