"""H1-K public metadata and safety-gate consistency, not archive authentication."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class H1KSourceStatusTests(unittest.TestCase):
    def test_post147_rows_are_complete_and_remain_unverified(self):
        report = load("specs/h1k_20261104_source_status.json")
        self.assertEqual(report["source_format"], "VALID_JSON")
        self.assertTrue(report["fx_design_mapping_equal_to_2026_10_23"])
        self.assertEqual(report["post147_explicit_candidates"], 0)
        self.assertEqual(report["post147_context_hints"], 0)
        self.assertEqual(report["post147_missing_count"], 52)
        rows = report["question_statuses"]
        self.assertEqual(
            [row["question_id"] for row in rows],
            [f"Q{number}" for number in range(148, 200)],
        )
        evidence = {
            row["question_id"]: row
            for row in load("specs/source_evidence.json")["records"]
        }
        for row in rows:
            qid = row["question_id"]
            self.assertEqual(row["scoped_local_status"], "SOURCE_UNAVAILABLE")
            self.assertEqual(row["owner_original_review"], "PENDING")
            self.assertIs(row["safety_approval"], False)
            existing = evidence[qid]
            self.assertEqual(existing["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
            self.assertIs(existing["owner_approved_for_safety"], False)
            expected = (
                ("SUMMARY_ONLY", "PENDING", "SUMMARY_ONLY_PENDING")
                if qid == "Q199"
                else ("ORIGINAL", "DIRECT_CHAT", "DIRECT_CHAT_PENDING_LOCAL_ARCHIVE")
            )
            self.assertEqual(
                (
                    existing["source_kind"],
                    existing["verification"],
                    row["repository_evidence"],
                ),
                expected,
            )

    def test_phase_and_all_safety_approvals_stay_blocked(self):
        gates = load("specs/phase1_way_e_gate_register.json")
        self.assertEqual(gates["runtime_go_no_go"], "NO_GO")
        self.assertIs(gates["safety_hold_latched"], True)
        self.assertIsNone(gates["verified_values"])
        acceptance = load("specs/acceptance_registry.json")
        self.assertEqual(
            next(x for x in acceptance["phases"] if x["id"] == "PHASE-1")["status"],
            "BLOCKED",
        )
        self.assertTrue(all(x["status"] != "ACCEPTED" for x in acceptance["modules"]))
        priority = load("specs/source_review_priority.json")["items"]
        reconciliation = {
            x["requirement_id"]: x
            for x in load("specs/reconciliation_registry.json")["items"]
        }
        self.assertEqual(
            {x["requirement_id"] for x in priority},
            {f"FX-SAF-{number:03}" for number in range(1, 16)},
        )
        for item in priority:
            self.assertEqual(item["source_review"], "PENDING_ORIGINAL")
            self.assertIs(item["human_safety_approval"], False)
            entry = reconciliation[item["requirement_id"]]
            self.assertIs(entry["implementation_approved"], False)
            self.assertIsNone(entry["owner_approval"])


if __name__ == "__main__":
    unittest.main()
