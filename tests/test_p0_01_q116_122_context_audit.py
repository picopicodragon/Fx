"""Tests for offline review leads; synthetic messages only, no real conversation."""
import json
import unittest
from pathlib import Path

from scripts.audit_p0_01_q116_122_context import build_report, chain, q_reference

ROOT = Path(__file__).resolve().parents[1]


def node(key, role, text, parent, timestamp):
    return {
        "parent": parent,
        "message": {
            "id": key,
            "author": {"role": role},
            "content": {"parts": [text]},
            "create_time": timestamp,
        },
    }


def fixture():
    mapping = {}
    prev = None
    clock = 0
    for n in range(116, 123):
        clock += 1
        a = f"a{n}"
        mapping[a] = node(a, "assistant", f"第{n}問：どれを採用しますか", prev, clock)
        clock += 1
        u = f"u{n}"
        answer = f"第{n}問はA：採用"
        if n == 117:
            answer += "。Q116を維持"
        if n == 122:
            answer += "。Q118を変更する"
        mapping[u] = node(u, "user", answer, a, clock)
        prev = u
    return {"id": "fx", "title": "FX", "current_node": prev, "mapping": mapping}


class ContextAuditTests(unittest.TestCase):
    def test_answer_context_and_future_references_are_not_auto_approved(self):
        d = fixture()
        by_q = {r["question_id"]: r for r in build_report([d], "fx")}
        self.assertEqual(set(by_q), {f"Q{n}" for n in range(116, 123)})
        for record in by_q.values():
            self.assertEqual(record["explicit"], 1)
            self.assertEqual(record["prompt_hint"], "YES")
            self.assertEqual(record["active_branch"], "YES")
        self.assertEqual(by_q["Q116"]["later_references"], 1)
        self.assertEqual(by_q["Q116"]["change_word_references"], 0)
        self.assertEqual(by_q["Q118"]["later_references"], 1)
        self.assertEqual(by_q["Q118"]["change_word_references"], 1)

    def test_unlabeled_parent_context_flag_does_not_assign_decision(self):
        d = fixture()
        d["mapping"]["a_extra"] = node(
            "a_extra", "assistant", "第116問の補足はありますか", "u122", 15
        )
        d["mapping"]["u_extra"] = node("u_extra", "user", "そのままで", "a_extra", 16)
        d["current_node"] = "u_extra"
        q116 = build_report([d], "fx")[0]
        self.assertEqual(q116["later_unlabeled_hints"], 1)
        self.assertEqual(q116["later_references"], 1)

    def test_alternate_branch_cannot_be_silently_certified(self):
        d = fixture()
        d["mapping"]["off"] = node("off", "user", "第116問はB：別案", "a116", 2.5)
        q116 = build_report([d], "fx")[0]
        self.assertEqual(q116["explicit"], 2)
        self.assertEqual(q116["prompt_hint"], "REVIEW_REQUIRED")
        self.assertEqual(q116["active_branch"], "UNDETERMINED")

    def test_unknown_current_node_and_timestamp_do_not_imply_no_changes(self):
        d = fixture()
        d["current_node"] = "missing"
        d["mapping"]["u117"]["message"]["create_time"] = None
        records = {r["question_id"]: r for r in build_report([d], "fx")}
        self.assertEqual(records["Q116"]["active_branch"], "UNKNOWN")
        self.assertEqual(records["Q116"]["order_uncertain_refs"], 1)

    def test_question_number_reference_requires_boundary(self):
        self.assertTrue(q_reference("Q116について", "Q116"))
        self.assertTrue(q_reference("第116問はA", "Q116"))
        self.assertFalse(q_reference("Q1160について", "Q116"))
        self.assertFalse(q_reference("abcQ116について", "Q116"))
        self.assertIsNone(chain({"a": {"parent": "b"}, "b": {"parent": "a"}}, "a"))

    def test_repository_safety_state_is_unmodified(self):
        safety = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8"))
        self.assertTrue(all(
            x["implementation_approved"] is False and x["owner_approval"] is None
            for x in safety["items"]
        ))
        acceptance = json.loads((ROOT / "specs/acceptance_registry.json").read_text(encoding="utf-8"))
        self.assertEqual(
            next(x for x in acceptance["phases"] if x["id"] == "PHASE-1")["status"],
            "BLOCKED",
        )


if __name__ == "__main__":
    unittest.main()
