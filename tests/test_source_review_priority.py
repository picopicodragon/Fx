"""Q115 safety-source priority gate: synthetic regression tests only."""
import copy
import unittest

from scripts.check_source_review_priority import audit


def fixture():
    ids = [f"FX-SAF-{i:03d}" for i in range(1, 16)]
    batches = [
        {"batch_id": f"P0-{i:02d}", "order": i, "requirement_ids": chunk}
        for i, chunk in enumerate(
            [ids[:6], ids[9:10]+ids[12:13], ids[10:12], ids[6:9], ids[13:]],
            start=1,
        )
    ]
    by_id = {ref: b["batch_id"] for b in batches for ref in b["requirement_ids"]}
    entries = [
        {"requirement_id": ref, "question_ids": [f"Q{i}"],
         "batch_id": by_id[ref], "source_review": "PENDING_ORIGINAL",
         "spec_comparison": "NOT_REVIEWED", "confidentiality_review": "NOT_REVIEWED",
         "human_safety_approval": False, "github_excerpt_refs": [],
         "outstanding_issues": ["needs original"]}
        for i, ref in enumerate(ids, 1)
    ]
    return (
        {"schema_version": 1, "decision_ref": "Q115",
         "batches": batches, "items": entries},
        {"items": [
            {"requirement_id": x["requirement_id"], "question_ids": x["question_ids"],
             "implementation_approved": False, "owner_approval": None}
            for x in entries
        ]},
        {"records": []},
    )


class PriorityAuditTests(unittest.TestCase):
    def test_unverified_baseline_is_valid(self):
        self.assertEqual(audit(*fixture()), [])

    def test_missing_requirement_rejected(self):
        plan, rec, ev = fixture()
        plan["items"].pop()
        self.assertIn("exact coverage", "\n".join(audit(plan, rec, ev)))

    def test_duplicate_assigned_requirement_rejected(self):
        plan, rec, ev = fixture()
        plan["batches"][1]["requirement_ids"].append("FX-SAF-001")
        self.assertIn("duplicate assigned", "\n".join(audit(plan, rec, ev)))

    def test_unverified_origins_cannot_be_claimed_as_matched(self):
        plan, rec, ev = fixture()
        plan["items"][0]["spec_comparison"] = "COMPARISON_MATCHED"
        self.assertIn("cannot claim", "\n".join(audit(plan, rec, ev)))

    def test_approval_without_reconciliation_rejected(self):
        plan, rec, ev = fixture()
        plan["items"][0]["human_safety_approval"] = True
        self.assertIn("unsupported", "\n".join(audit(plan, rec, ev)))

    def test_missing_original_evidence_for_verified_status_rejected(self):
        plan, rec, ev = fixture()
        first = plan["items"][0]
        first.update(source_review="EXCERPT_VERIFIED",
                     confidentiality_review="REVIEWED_FOR_GITHUB",
                     github_excerpt_refs=["specs/source_excerpts/Q1.md"])
        self.assertIn("no verified original", "\n".join(audit(plan, rec, ev)))

    def test_question_id_disagreement_rejected(self):
        plan, rec, ev = fixture()
        plan["items"][0]["question_ids"] = ["Q999"]
        self.assertIn("conflict", "\n".join(audit(plan, rec, ev)))


if __name__ == "__main__":
    unittest.main()
