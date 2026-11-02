"""H1-F/J metadata coverage, not original-source authentication."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Post147SourceStatusTests(unittest.TestCase):
    def test_scoped_archive_absence_is_not_promoted_to_original_evidence(self):
        status = json.loads(
            (ROOT / "specs/h1_post147_local_source_status.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(status["status"], "SOURCE_UNAVAILABLE_IN_SCOPED_LOCAL_ARCHIVE")
        self.assertEqual(status["new_archive_files_found"], 0)
        rows = status["question_statuses"]
        self.assertEqual(
            [row["question_id"] for row in rows],
            [f"Q{number}" for number in range(148, 200)],
        )
        evidence = json.loads(
            (ROOT / "specs/source_evidence.json").read_text(encoding="utf-8")
        )
        by_question = {row["question_id"]: row for row in evidence["records"]}
        for row in rows:
            self.assertEqual(row["local_archive_candidate"], "SOURCE_UNAVAILABLE")
            self.assertEqual(row["owner_context_review"], "PENDING")
            self.assertIs(row["safety_implementation_approved"], False)
            self.assertEqual(
                row["existing_repository_evidence"],
                "SUMMARY_ONLY_PENDING"
                if row["question_id"] == "Q199"
                else "DIRECT_CHAT_LOCAL_ARCHIVE_PENDING",
            )
            source = by_question[row["question_id"]]
            self.assertEqual(source["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
            self.assertIs(source["owner_approved_for_safety"], False)
            self.assertEqual(
                (source["source_kind"], source["verification"]),
                ("SUMMARY_ONLY", "PENDING")
                if row["question_id"] == "Q199"
                else ("ORIGINAL", "DIRECT_CHAT"),
            )

    def test_all_safety_requirements_remain_pending_and_unapproved(self):
        priority = json.loads(
            (ROOT / "specs/source_review_priority.json").read_text(encoding="utf-8")
        )
        reconciliation = json.loads(
            (ROOT / "specs/reconciliation_registry.json").read_text(encoding="utf-8")
        )
        by_id = {row["requirement_id"]: row for row in reconciliation["items"]}
        self.assertEqual(
            {row["requirement_id"] for row in priority["items"]},
            {f"FX-SAF-{number:03}" for number in range(1, 16)},
        )
        for item in priority["items"]:
            self.assertEqual(item["source_review"], "PENDING_ORIGINAL")
            self.assertIs(item["human_safety_approval"], False)
            self.assertIs(by_id[item["requirement_id"]]["implementation_approved"], False)
            self.assertIsNone(by_id[item["requirement_id"]]["owner_approval"])


if __name__ == "__main__":
    unittest.main()
