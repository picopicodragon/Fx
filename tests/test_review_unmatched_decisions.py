"""Unmatched FX decisions: parent-chain evidence remains human-reviewed."""
import unittest

from scripts.review_unmatched_decisions import (
    context_question_hints, make_review, original_chat, preceding_assistant,
)


def node(key, role, text, parent=None):
    return {
        "parent": parent,
        "message": {
            "id": key,
            "author": {"role": role},
            "content": {"parts": [text]},
            "create_time": 1,
        },
    }


class UnmatchedReviewTests(unittest.TestCase):
    def setUp(self):
        self.mapping = {
            "a1": node("a1", "assistant", "第6問：損失限度は？ A / B / C", None),
            "u1": node("u1", "user", "Cを採用", "a1"),
            "a2": node("a2", "assistant", "第7問：同時保有は？ A / B / C", "u1"),
            "u2": node("u2", "user", "第7問はB：採用", "a2"),
            "a3": node("a3", "assistant", "第8問：日次制限は？", "u2"),
            "u3": node("u3", "user", "その条件で", "a3"),
        }

    def test_counts_and_hints_without_assignment(self):
        report = make_review(self.mapping, "fx", max_q=8)
        self.assertEqual(report["unmatched_user_messages"], 2)
        self.assertEqual(report["explicitly_recognized_unique_questions"], 1)
        first = report["unmatched"][0]
        self.assertEqual(first["possible_question_ids_from_assistant"], ["Q6"])
        self.assertEqual(first["preceding_assistant_text"], "第6問：損失限度は？ A / B / C")
        self.assertIsNone(first["assigned_question_id"])
        self.assertFalse(first["safe_for_github"])
        self.assertFalse(first["owner_approved_for_safety"])
        self.assertIn("Q6", report["missing_question_ids_in_this_conversation"])
        self.assertNotIn("Q7", report["missing_question_ids_in_this_conversation"])

    def test_context_uses_message_branch_not_nearest_by_time(self):
        mapping = dict(self.mapping)
        mapping["off_branch"] = node("off_branch", "assistant", "第99問：別の枝", "a1")
        review = make_review(mapping, "fx")
        self.assertEqual(review["unmatched"][0]["possible_question_ids_from_assistant"], ["Q6"])

    def test_missing_parent_yields_no_false_hint(self):
        mapping = {"u": node("u", "user", "C", "missing")}
        report = make_review(mapping, "fx")
        self.assertEqual(report["unmatched"][0]["possible_question_ids_from_assistant"], [])
        self.assertIsNone(report["unmatched"][0]["preceding_assistant_text"])

    def test_parent_cycle_terminates(self):
        mapping = {
            "u": node("u", "user", "A", "intermediate"),
            "intermediate": node("intermediate", "tool", "", "u"),
        }
        self.assertIsNone(preceding_assistant(mapping, "u"))

    def test_multi_question_context_never_auto_assigns(self):
        self.assertEqual(context_question_hints("Q6と第7問を確認"), ["Q6", "Q7"])
        report = make_review({"a": node("a", "assistant", "Q6と第7問"), "u": node("u", "user", "了解", "a")}, "fx")
        self.assertEqual(report["unmatched"][0]["possible_question_ids_from_assistant"], ["Q6", "Q7"])
        self.assertIsNone(report["unmatched"][0]["assigned_question_id"])

    def test_conversation_lookup_fails_closed(self):
        with self.assertRaises(ValueError):
            original_chat([{"id": "other", "mapping": {}}], "fx")

    def test_duplicate_conversation_id_rejected(self):
        with self.assertRaises(ValueError):
            original_chat([
                {"id": "fx", "mapping": {}}, {"id": "fx", "mapping": {}}
            ], "fx")

    def test_full_chat_mapping_selected(self):
        mapping = original_chat([{"id": "fx", "mapping": self.mapping}], "fx")
        self.assertEqual(len(mapping), 6)


if __name__ == "__main__":
    unittest.main()
