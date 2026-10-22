"""Structural tests only: synthetic source-review worksheet, no private files loaded."""
import unittest

from scripts.build_p0_01_review_worksheet import TARGETS, build_worksheet


def synthetic_export():
    def node(ident, role, text, parent=None):
        return {
            "parent": parent,
            "message": {
                "id": ident,
                "author": {"role": role},
                "content": {"parts": [text]},
                "create_time": None,
            },
        }

    return [{
        "id": "fake-fx",
        "title": "synthetic",
        "mapping": {
            "a": node("a", "assistant", "第5問と第6問の案を説明", None),
            "u1": node("u1", "user", "Bを採用", "a"),
            "a9": node("a9", "assistant", "第9問を確認", "u1"),
            "u9": node("u9", "user", "第9問はBを採用", "a9"),
            "a11": node("a11", "assistant", "第11問を提示", "u9"),
            "u11": node("u11", "user", "第11問はCを採用", "a11"),
            "a7": node("a7", "assistant", "第7問を提示", "u11"),
            "u99": node("u99", "user", "第99問はAを採用", "a7"),
            "a8": node("a8", "assistant", "Q8: リスク方針を質問", "u99"),
            "u8": node("u8", "user", "Cを採用する", "a8"),
        },
    }]


class P001ReviewWorksheetTests(unittest.TestCase):
    def test_ten_questions_and_all_permissions_false(self):
        result = build_worksheet(synthetic_export(), "fake-fx", "abc123")
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["plan_id"], "P0-01")
        self.assertEqual(result["conversation_id"], "fake-fx")
        self.assertEqual(result["source_file_sha256"], "abc123")
        self.assertFalse(result["source_verified_against_spec"])
        self.assertFalse(result["implementation_approved"])
        self.assertFalse(result["owner_approved_for_safety"])
        self.assertEqual([q["question_id"] for q in result["questions"]], list(TARGETS))
        for q in result["questions"]:
            self.assertEqual(q["review_status"], "OWNER_CONTEXT_REVIEW_REQUIRED")
            self.assertIsNone(q["selected_user_message_id"])
            self.assertFalse(q["owner_approved_for_safety"])

    def test_explicit_reply_and_unassigned_hint_remain_separate(self):
        result = build_worksheet(synthetic_export(), "fake-fx", "xx")
        by_id = {q["question_id"]: q for q in result["questions"]}
        self.assertEqual(len(by_id["Q5"]["explicit"]), 0)
        self.assertEqual(len(by_id["Q5"]["context_hints_unassigned"]), 1)
        self.assertEqual(len(by_id["Q6"]["context_hints_unassigned"]), 1)
        self.assertEqual(len(by_id["Q9"]["explicit"]), 1)
        self.assertEqual(len(by_id["Q9"]["context_hints_unassigned"]), 0)
        self.assertEqual(len(by_id["Q11"]["explicit"]), 1)
        self.assertEqual(len(by_id["Q7"]["context_hints_unassigned"]), 0)
        self.assertEqual(len(by_id["Q8"]["context_hints_unassigned"]), 1)
        self.assertEqual(len(by_id["Q14"]["explicit"]), 0)
        self.assertEqual(len(by_id["Q14"]["context_hints_unassigned"]), 0)

    def test_parent_chain_and_message_ids_preserved_for_human_review(self):
        result = build_worksheet(synthetic_export(), "fake-fx", "xx")
        q5 = result["questions"][0]["context_hints_unassigned"][0]
        self.assertEqual(q5["user_message_id"], "u1")
        self.assertEqual(q5["preceding_assistant_message_id"], "a")
        self.assertEqual(q5["user_text"], "Bを採用")
        self.assertIn("第5問", q5["preceding_assistant_text"])
        self.assertEqual(q5["identification"], "ASSISTANT_CONTEXT_HINT_ONLY")
        self.assertEqual(q5["status"], "UNVERIFIED_LOCAL_EVIDENCE")

    def test_missing_or_incorrect_conversation_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            build_worksheet(synthetic_export(), "not-fake", "xx")

    def test_does_not_automatically_promote_any_question(self):
        result = build_worksheet(synthetic_export(), "fake-fx", "xx")
        for q in result["questions"]:
            for evidence in q["explicit"] + q["context_hints_unassigned"]:
                self.assertEqual(evidence["status"], "UNVERIFIED_LOCAL_EVIDENCE")
                self.assertNotIn("verified", evidence)
                self.assertNotIn("approved", evidence)


if __name__ == "__main__":
    unittest.main()
