"""P0-01 owner comparison attestations: audit metadata only, not original text."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "specs" / "p0_01_owner_question_matches.json"
REGISTRY = ROOT / "specs" / "reconciliation_registry.json"
PRIORITY = ROOT / "specs" / "source_review_priority.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class PartialOriginalComparisonTests(unittest.TestCase):
    def test_exactly_five_owner_reported_question_matches(self):
        data = load(LOG)
        self.assertEqual(data["record_type"], "OWNER_REPORTED_PARTIAL_QUESTION_MATCH")
        self.assertEqual(
            {x["question_id"] for x in data["items"]},
            {"Q9", "Q10", "Q11", "Q12", "Q13"},
        )
        self.assertEqual(len(data["items"]), 5)
        self.assertTrue(all(x["owner_reported_comparison"] == "MATCH" for x in data["items"]))
        self.assertTrue(all(x["question_level_only"] for x in data["items"]))
        self.assertTrue(all(not x["registered_original_excerpt"] for x in data["items"]))
        self.assertTrue(all(not x["safety_approval"] for x in data["items"]))

    def test_attestation_does_not_create_evidence_or_safety_approval(self):
        data = load(LOG)
        for key in (
            "source_excerpt_registered",
            "all_original_context_verified_by_repo",
            "implementation_approved",
            "human_safety_approval",
            "owner_approved_for_safety",
        ):
            with self.subTest(key=key):
                self.assertFalse(data[key])
        for item in data["items"]:
            if item["question_id"] in ("Q11", "Q13"):
                self.assertEqual(
                    item["unmatched_context_resolution"], "NOT_SEPARATELY_CONFIRMED"
                )

    def test_related_requirements_are_only_partially_marked(self):
        d = load(REGISTRY)
        self.assertEqual(check_reconciliation(d), [])
        expected = {
            "FX-SAF-001": {"Q5", "Q6", "Q13"},
            "FX-SAF-002": {"Q7"},
            "FX-SAF-003": {"Q8", "Q9", "Q13"},
            "FX-SAF-004": {"Q10"},
            "FX-SAF-005": {"Q11", "Q12"},
        }
        for record in d["items"]:
            ident = record["requirement_id"]
            if ident in expected:
                matches = record["partial_owner_question_matches"]
                self.assertEqual(
                    {x["question_id"] for x in matches}, expected[ident]
                )
                for match in matches:
                    self.assertEqual(match["result"], "MATCH")
                    self.assertEqual(
                        match["evidence_ref"], "specs/p0_01_owner_question_reviews_round2.json" if match["question_id"] in ("Q5", "Q6", "Q7", "Q8") else "specs/p0_01_owner_question_matches.json"
                    )
                    self.assertEqual(
                        match["record_kind"], "OWNER_ATTESTATION_ONLY_NOT_REGISTERED_ORIGINAL"
                    )
            else:
                self.assertNotIn("partial_owner_question_matches", record)
            self.assertFalse(record["implementation_approved"])
            self.assertIsNone(record["owner_approval"])
            self.assertNotEqual(record["source_kind"], "ORIGINAL")
            self.assertNotEqual(record["comparison_status"], "MATCH")

    def test_priority_registry_retains_all_original_review_blockers(self):
        d = load(PRIORITY)
        self.assertEqual(d["state"], "PLANNED_ONLY")
        self.assertEqual(len(d["items"]), 15)
        for item in d["items"]:
            self.assertEqual(item["source_review"], "PENDING_ORIGINAL")
            self.assertFalse(item["human_safety_approval"])


if __name__ == "__main__":
    unittest.main()
