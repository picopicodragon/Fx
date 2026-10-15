"""Q112 evidence gate regression tests."""
import copy
import unittest

from scripts.check_reconciliation import check_reconciliation


def initial():
    return {
        "schema_version": 1,
        "items": [
            {
                "requirement_id": f"FX-SAF-{n:03d}",
                "question_ids": ["Q6"],
                "source_kind": "SUMMARY_ONLY",
                "comparison_status": "SOURCE_UNAVAILABLE",
                "safety_critical": True,
                "source_reference": None,
                "spec_reference": "specs/safety_foundation.md",
                "issues": ["Original record not verified"],
                "implementation_approved": False,
                "owner_approval": None
            }
            for n in range(1, 16)
        ],
    }


class ReconciliationTests(unittest.TestCase):
    def test_unverified_baseline_valid(self):
        self.assertEqual(check_reconciliation(initial()), [])

    def test_missing_safety_id_rejected(self):
        r = initial()
        r["items"].pop()
        self.assertIn("Missing mandatory", "\n".join(check_reconciliation(r)))

    def test_summary_only_cannot_be_approved(self):
        r = initial()
        entry = r["items"][0]
        entry["implementation_approved"] = True
        self.assertIn("ORIGINAL", "\n".join(check_reconciliation(r)))

    def test_unresolved_difference_blocks_approval(self):
        r = initial()
        entry = r["items"][0]
        entry.update(
            source_kind="ORIGINAL",
            source_reference="source-q6",
            comparison_status="DISCREPANCY",
            implementation_approved=True,
            owner_approval={"approved_by": "owner", "approved_at": "date", "decision_reference": "DECISIONS.md"}
        )
        self.assertIn("MATCH/RESOLVED", "\n".join(check_reconciliation(r)))

    def test_approval_with_issues_rejected(self):
        r = initial()
        entry = r["items"][0]
        entry.update(
            source_kind="ORIGINAL",
            source_reference="source-q6",
            comparison_status="MATCH",
            implementation_approved=True,
            owner_approval={"approved_by": "owner", "approved_at": "date", "decision_reference": "DECISIONS.md"}
        )
        self.assertIn("open issues", "\n".join(check_reconciliation(r)))

    def test_structurally_complete_approved_entry(self):
        r = initial()
        entry = r["items"][0]
        entry.update(
            source_kind="ORIGINAL",
            source_reference="source-q6",
            comparison_status="MATCH",
            issues=[],
            implementation_approved=True,
            owner_approval={"approved_by": "owner", "approved_at": "date", "decision_reference": "DECISIONS.md"}
        )
        self.assertEqual(check_reconciliation(r), [])


if __name__ == "__main__":
    unittest.main()
