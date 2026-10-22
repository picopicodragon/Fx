"""Static tests for owner-reported Q5-Q8 MATCH and Q14 UNCLEAR."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class P001OwnerRoundTwoTests(unittest.TestCase):
    def test_match_and_unclear_do_not_get_mixed(self):
        report = read_json("specs/p0_01_owner_question_reviews_round2.json")
        self.assertEqual(report["record_type"], "PARTIAL_OWNER_REVIEW")
        by_q = {item["q"]: item for item in report["results"]}
        self.assertEqual(set(by_q), {"Q5", "Q6", "Q7", "Q8", "Q14"})
        for q in ("Q5", "Q6", "Q7", "Q8"):
            self.assertEqual(by_q[q]["status"], "MATCH")
        self.assertEqual(by_q["Q14"]["status"], "UNCLEAR")
        self.assertIn("not acceptance", by_q["Q14"]["reason"])

    def test_no_source_certification_or_permission(self):
        report = read_json("specs/p0_01_owner_question_reviews_round2.json")
        for name in ("source_original_registered", "implementation_approved",
                     "human_safety_approval", "owner_approved_for_safety"):
            self.assertIs(report[name], False)

    def test_round_two_unclear_is_historical_and_superseded(self):
        ledger = read_json("specs/reconciliation_registry.json")
        saf003 = next(x for x in ledger["items"] if x["requirement_id"] == "FX-SAF-003")
        q14 = saf003["partial_owner_question_reviews"]
        self.assertEqual(len(q14), 1)
        self.assertEqual(q14[0]["question_id"], "Q14")
        self.assertEqual(q14[0]["result"], "UNCLEAR")
        self.assertEqual(q14[0]["review_lifecycle"], "HISTORICAL_SUPERSEDED")
        self.assertEqual(q14[0]["superseded_by"], "specs/p0_01_owner_q14_followup_match.json")
        self.assertIn("Q14", {x["question_id"] for x in saf003["partial_owner_question_matches"]})
        self.assertFalse(saf003["implementation_approved"])
        self.assertIsNone(saf003["owner_approval"])
        self.assertNotEqual(saf003["comparison_status"], "MATCH")

    def test_all_original_review_gates_remain_pending(self):
        review = read_json("specs/source_review_priority.json")
        for item in review["items"]:
            self.assertEqual(item["source_review"], "PENDING_ORIGINAL")
            self.assertFalse(item["human_safety_approval"])
        acceptance = read_json("specs/acceptance_registry.json")
        phase1 = next(x for x in acceptance["phases"] if x["id"] == "PHASE-1")
        self.assertEqual(phase1["status"], "BLOCKED")
        self.assertIsNone(phase1["approval"])


if __name__ == "__main__":
    unittest.main()
