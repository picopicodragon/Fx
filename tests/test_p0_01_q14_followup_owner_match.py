"""Q14 owner-reported follow-up acceptance: structural checks, no original claims."""
import json
from pathlib import Path
import unittest

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class Q14OwnerFollowupTests(unittest.TestCase):
    def test_followup_supersedes_earlier_unclear_without_erasing_it(self):
        old = load("specs/p0_01_owner_question_reviews_round2.json")
        former = next(x for x in old["results"] if x["q"] == "Q14")
        self.assertEqual(former["status"], "UNCLEAR")
        new = load("specs/p0_01_owner_q14_followup_match.json")
        self.assertEqual(new["record_type"], "OWNER_REPORTED_Q14_FOLLOWUP_MATCH")
        self.assertEqual(new["question_id"], "Q14")
        self.assertEqual(new["owner_reported_comparison"], "MATCH")
        self.assertTrue(new["supersedes_prior_interpretation"])
        self.assertEqual(
            new["previous_record_ref"],
            "specs/p0_01_owner_question_reviews_round2.json",
        )

    def test_every_question_q5_to_q14_has_owner_match(self):
        register = load("specs/reconciliation_registry.json")
        all_matched = {
            entry["question_id"]
            for requirement in register["items"]
            for entry in requirement.get("partial_owner_question_matches", [])
        }
        self.assertEqual({f"Q{i}" for i in range(5, 15)}, all_matched)
        self.assertEqual(check_reconciliation(register), [])

    def test_latest_q14_match_and_history_are_distinct(self):
        reg = load("specs/reconciliation_registry.json")
        item = next(i for i in reg["items"] if i["requirement_id"] == "FX-SAF-003")
        current = [x for x in item["partial_owner_question_matches"] if x["question_id"] == "Q14"]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["result"], "MATCH")
        self.assertEqual(current[0]["evidence_ref"], "specs/p0_01_owner_q14_followup_match.json")
        historic = item["partial_owner_question_reviews"]
        self.assertEqual(len(historic), 1)
        self.assertEqual(historic[0]["result"], "UNCLEAR")
        self.assertEqual(historic[0]["review_lifecycle"], "HISTORICAL_SUPERSEDED")

    def test_design_vs_permission_separation(self):
        report = load("specs/p0_01_owner_q14_followup_match.json")
        for key in ("recorded_original_quote", "registered_original_excerpt",
                    "all_original_context_verified_by_repo", "implementation_approved",
                    "human_safety_approval", "owner_approved_for_safety"):
            self.assertIs(report[key], False)
        reg = load("specs/reconciliation_registry.json")
        for entry in reg["items"]:
            self.assertFalse(entry["implementation_approved"])
            self.assertIsNone(entry["owner_approval"])
            self.assertNotEqual(entry["source_kind"], "ORIGINAL")
        phase = next(x for x in load("specs/acceptance_registry.json")["phases"] if x["id"] == "PHASE-1")
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
