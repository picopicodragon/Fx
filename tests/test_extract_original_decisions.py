"""Q114 decision candidate extractor tests, synthetic content only."""
import json
import unittest

from scripts.extract_original_decisions import build_result, detect_question, export_messages


class ExtractionTests(unittest.TestCase):
    def test_explicit_question(self):
        self.assertEqual(detect_question("第114問はC：ハイブリッド型を採用する。"), "Q114")

    def test_short_consent_not_guessed(self):
        self.assertIsNone(detect_question("CでOK。"))

    def test_manual_requires_question(self):
        with self.assertRaises(ValueError):
            build_result("CでOK".encode(), "manual", None, None)

    def test_manual_candidate_never_approved(self):
        report = build_result("CでOK".encode(), "manual", None, "Q114")
        self.assertEqual(report["candidate_count"], 1)
        self.assertFalse(report["candidates"][0]["safe_for_github"])
        self.assertFalse(report["candidates"][0]["owner_approved_for_safety"])

    def test_manual_wrong_question_rejected(self):
        with self.assertRaises(ValueError):
            build_result("第113問はC".encode(), "manual", None, "Q114")

    def test_export_selects_user_only_and_specific_conversation(self):
        blob = [
            {"id": "target", "mapping": {
                "a": {"message": {"id": "a", "author": {"role": "assistant"},
                                  "content": {"parts": ["第114問はAとする"]}}},
                "u": {"message": {"id": "u", "author": {"role": "user"},
                                  "create_time": 100, "content": {"parts": ["第114問はCを採用する"]}}},
                "n": {"message": {"id": "n", "author": {"role": "user"},
                                  "create_time": 101, "content": {"parts": ["CでOK"]}}}
            }},
            {"id": "other", "mapping": {
                "s": {"message": {"id": "s", "author": {"role": "user"},
                                  "content": {"parts": ["第1問はA"]}}}
            }}
        ]
        report = build_result(json.dumps(blob).encode(), "export", "target", None)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["unmatched_user_messages"], 1)
        self.assertEqual(report["candidates"][0]["question_id"], "Q114")
        self.assertEqual(report["candidates"][0]["message_id"], "u")

    def test_wrong_conversation_id_fails_closed(self):
        with self.assertRaises(ValueError):
            export_messages([], "missing")

    def test_duplicate_q_retained_for_review(self):
        blob = [{"id": "target", "mapping": {
            k: {"message": {"id": k, "author": {"role": "user"},
                            "content": {"parts": ["第114問はCを採用する"]}}}
            for k in ("a", "b")
        }}]
        report = build_result(json.dumps(blob).encode(), "export", "target", None)
        self.assertEqual(report["duplicate_question_ids"], ["Q114"])


if __name__ == "__main__":
    unittest.main()
