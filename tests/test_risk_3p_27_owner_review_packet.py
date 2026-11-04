"""RISK-3P-27 offline owner packet must never sign itself or authorize trades."""
from __future__ import annotations

from unittest import mock
import unittest

from scripts import print_risk_3p_27_owner_review_packet as mod
from scripts import audit_risk_3p_23_26_decision_critical_path as graph


class OwnerPacketPrinterTests(unittest.TestCase):
    def test_all_43_questions_print_once_in_four_review_cohorts(self):
        output = mod.render()
        d = graph._read(graph.ROOT, graph.DOCKET)
        markers = [f"### {item['id']}（本人未決）"
                   for item in d["decisions"]]
        self.assertEqual(len(markers), 43)
        self.assertEqual(len(set(markers)), 43)
        for mark in markers:
            with self.subTest(id=mark):
                self.assertEqual(output.count(mark), 1)
        for decision in d["decisions"]:
            self.assertIn(decision["original_question"], output)
            self.assertIn(decision["source_recommendation"], output)

    def test_review_order_matches_1_2_5_6_3_4_7_8_9_10(self):
        output = mod.render()
        ids = (
            "F01-1", "F02-1", "FORM05-1", "FORM06-1",
            "FORM03-1", "FORM04-1", "FORM07-1", "FORM08-1",
            "FORM09-1", "FORM10-1",
        )
        self.assertEqual([output.index("### " + ident + "（本人未決）")
                          for ident in ids],
                         sorted(output.index("### " + ident + "（本人未決）")
                                for ident in ids))

    def test_packet_prominently_maintains_no_go_and_no_live_permissions(self):
        out = mod.render()
        for text in ("PHASE-1 BLOCKED", "runtime NO_GO",
                     "43件 / 43件", "0件 / 15件",
                     "未承認", "停止ラッチ維持",
                     "MT4", "新規発注", "本人の明示決定"):
            self.assertIn(text, out)
        self.assertNotIn("実証済み：15", out)
        self.assertNotIn("自動売買を開始", out)

    def test_no_document_is_printed_if_integrity_audit_fails(self):
        with mock.patch.object(mod, "audit", return_value=["SOURCE_INTEGRITY_BAD"]):
            with self.assertRaisesRegex(ValueError,
                                        "unsafe or inconsistent source"):
                mod.render()

    def test_no_document_is_printed_if_readiness_is_false_positive(self):
        with mock.patch.object(mod, "snapshot", return_value={"readiness": "GO"}):
            with self.assertRaisesRegex(ValueError,
                                        "only blocked documentary packets"):
                mod.render()

    def test_empty_or_duplicate_decisions_have_no_render_permission(self):
        base = graph._read(graph.ROOT, graph.DOCKET)
        for mode in ("missing", "duplicate"):
            changed = __import__("copy").deepcopy(base)
            if mode == "missing":
                changed["decisions"].pop()
            else:
                changed["decisions"][1]["id"] = changed["decisions"][0]["id"]
            original = mod._read

            def load(root, filename):
                return changed if filename == graph.DOCKET else original(root, filename)

            with self.subTest(mode=mode), mock.patch.object(mod, "_read", side_effect=load):
                with self.assertRaises((ValueError, KeyError)):
                    mod.render()


if __name__ == "__main__":
    unittest.main()
