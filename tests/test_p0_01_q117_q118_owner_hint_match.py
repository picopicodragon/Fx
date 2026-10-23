"""P0-01 Q117/Q118 unnumbered follow-up review is not safety approval."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
REPORT = "specs/p0_01_owner_q116_122_context_review.json"


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class Q116ToQ122OwnerContextReviewTests(unittest.TestCase):
    def test_seven_original_answers_and_exact_quote_comparisons(self):
        report = load(REPORT)
        expected = {f"Q{n}" for n in range(116, 123)}
        rows = report["audit_results"]
        self.assertEqual({r["question_id"] for r in rows}, expected)
        self.assertEqual(len(rows), 7)
        for row in rows:
            self.assertEqual(row["explicit_answers"], 1)
            self.assertEqual(row["preceding_assistant_question_hint"], "YES")
            self.assertEqual(row["on_active_branch"], "YES")
            self.assertEqual(row["later_explicit_question_references"], 0)
            self.assertEqual(row["later_references_with_change_keywords"], 0)
            self.assertEqual(row["unknown_order_references"], 0)
            self.assertEqual(row["previous_exact_quote_check"], "EXACT")

    def test_only_q117_q118_had_owner_classified_hints(self):
        d = load(REPORT)
        counts = {r["question_id"]: r["unnumbered_followup_context_hints"]
                  for r in d["audit_results"]}
        self.assertEqual({q for q, count in counts.items() if count}, {"Q117", "Q118"})
        self.assertEqual(counts["Q117"], 1)
        self.assertEqual(counts["Q118"], 1)
        reviews = d["owner_reviewed_unnumbered_hints"]
        self.assertEqual({r["hint_question_id"] for r in reviews}, {"Q117", "Q118"})
        self.assertEqual(len(reviews), 2)
        for review in reviews:
            self.assertEqual(review["hint_count"], 1)
            self.assertEqual(review["owner_classification"], "MATCH")
            self.assertFalse(review["original_message_id_verified_by_assistant"])
            self.assertFalse(review["full_text_saved_to_github"])

    def test_exact_quote_evidence_is_distinct_from_unnumbered_hint_match(self):
        previous = load("specs/p0_01_owner_archive_q116_122_exact.json")
        quotes = {r["question_id"]: r for r in previous["comparison"]["per_question"]}
        current = load(REPORT)
        self.assertEqual(
            current["previous_quote_comparison_ref"],
            "specs/p0_01_owner_archive_q116_122_exact.json"
        )
        for q in ("Q117", "Q118"):
            self.assertEqual(quotes[q]["comparison"], "EXACT")
            self.assertEqual(quotes[q]["explicit_user_candidates"], 1)
        self.assertEqual(
            {r["hint_question_id"]: r["owner_classification"]
             for r in current["owner_reviewed_unnumbered_hints"]},
            {"Q117": "MATCH", "Q118": "MATCH"}
        )
        self.assertFalse(current["safety_requirement_comparison_upgraded"])

    def test_registry_marks_owner_hint_not_full_safety_match(self):
        registry = load("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        entry = next(i for i in registry["items"] if i["requirement_id"] == "FX-SAF-003")
        refs = entry["partial_owner_context_hint_reviews"]
        self.assertEqual({x["question_id"] for x in refs}, {"Q117", "Q118"})
        for x in refs:
            self.assertEqual(x["owner_classification"], "MATCH")
            self.assertEqual(x["evidence_ref"], REPORT)
            self.assertEqual(x["record_kind"],
                             "OWNER_CLASSIFIED_UNNUMBERED_CONTEXT_HINT_NOT_SAFETY_REQUIREMENT_MATCH")
            self.assertFalse(x["implementation_approved"])
            self.assertFalse(x["original_message_id_verified"])
        self.assertEqual(entry["source_kind"], "SUMMARY_ONLY")
        self.assertEqual(entry["comparison_status"], "NEEDS_CLARIFICATION")

    def test_requirements_and_live_trading_stay_blocked(self):
        d = load(REPORT)
        for key in ("original_user_messages_uploaded",
                    "original_message_ids_verified_by_assistant",
                    "safety_requirement_comparison_upgraded",
                    "implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety", "forward_trading_enabled"):
            self.assertIs(d[key], False)
        for i in load("specs/reconciliation_registry.json")["items"]:
            self.assertFalse(i["implementation_approved"])
            self.assertIsNone(i["owner_approval"])
        for i in load("specs/source_review_priority.json")["items"]:
            self.assertEqual(i["source_review"], "PENDING_ORIGINAL")
            self.assertFalse(i["human_safety_approval"])
        phase = next(
            p for p in load("specs/acceptance_registry.json")["phases"]
            if p["id"] == "PHASE-1"
        )
        self.assertEqual(phase["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
