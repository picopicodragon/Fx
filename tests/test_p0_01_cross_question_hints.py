"""Safeguard against assigning unrelated responses to FX risk questions."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class CrossQuestionHintTests(unittest.TestCase):
    def test_owner_reports_both_hints_belong_to_other_questions(self):
        d = read("specs/p0_01_cross_question_context_classifications.json")
        self.assertEqual(d["record_type"], "P0_01_OWNER_CROSS_QUESTION_CONTEXT_CLASSIFICATION")
        self.assertEqual(len(d["items"]), 2)
        qmap = {x["hint_owner_question_id"]: x for x in d["items"]}
        self.assertEqual(set(qmap), {"Q11", "Q13"})
        self.assertEqual(qmap["Q11"]["actual_question_id"], "Q106")
        self.assertEqual(qmap["Q13"]["actual_question_id"], "Q14")
        for item in d["items"]:
            self.assertEqual(item["classification"], "CROSS_QUESTION_UNRELATED_TO_RISK_SETTING")
        self.assertEqual(qmap["Q11"]["owner_original_label"], "追加決定")
        self.assertEqual(qmap["Q13"]["owner_original_label"], "無関係")

    def test_owner_match_attestations_remain_unchanged(self):
        d = read("specs/p0_01_owner_question_matches.json")
        records = {x["question_id"]: x for x in d["items"]}
        for q in ("Q11", "Q13"):
            self.assertEqual(records[q]["owner_reported_comparison"], "MATCH")
            self.assertEqual(
                records[q]["unmatched_context_resolution"],
                "CROSS_QUESTION_UNRELATED_TO_RISK_SETTING",
            )
            self.assertEqual(
                records[q]["unmatched_context_resolution_ref"],
                "specs/p0_01_cross_question_context_classifications.json",
            )
            self.assertFalse(records[q]["safety_approval"])

    def test_target_q106_spec_and_risk_descriptions_unchanged(self):
        spec = (ROOT / "MASTER_SPEC.md").read_text(encoding="utf-8")
        for entry in (
            "| Q106 | 分割Markdown＋ローカルGit",
            "| Q11 | 口座純資産高水位からの最大ドローダウン5.0%",
            "| Q13 | リスク%は口座純資産連動",
            "| Q14 | 取引日の区切りはニューヨーク17:00",
        ):
            self.assertIn(entry, spec)

    def test_no_source_promotion_or_trading_enablement(self):
        d = read("specs/p0_01_cross_question_context_classifications.json")
        for key in (
            "original_message_ids_independently_verified",
            "original_excerpts_registered",
            "source_kind_upgraded",
            "requirement_comparison_upgraded",
            "human_safety_approval",
            "implementation_approved",
            "owner_approved_for_safety",
            "trade_enabled",
        ):
            self.assertFalse(d[key])
        reg = read("specs/reconciliation_registry.json")
        for item in reg["items"]:
            self.assertFalse(item["implementation_approved"])
            self.assertIsNone(item["owner_approval"])
            self.assertNotEqual(item["source_kind"], "ORIGINAL")
            self.assertNotEqual(item["comparison_status"], "MATCH")
        self.assertEqual(
            next(x for x in read("specs/acceptance_registry.json")["phases"] if x["id"] == "PHASE-1")["status"],
            "BLOCKED",
        )


if __name__ == "__main__":
    unittest.main()
