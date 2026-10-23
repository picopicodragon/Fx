"""Owner-run Q116-Q122 archive EXACT reports are not safety approvals."""
import json
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation
from scripts.check_source_evidence import audit as audit_source_evidence

ROOT = Path(__file__).resolve().parents[1]
REF = "specs/p0_01_owner_archive_q116_122_exact.json"
QIDS = {f"Q{n}" for n in range(116, 123)}
EXPECTED = {
    "FX-SAF-001": {"Q116"},
    "FX-SAF-002": {"Q116"},
    "FX-SAF-003": {"Q117", "Q118", "Q120", "Q121"},
    "FX-SAF-004": {"Q121"},
    "FX-SAF-005": {"Q119", "Q120", "Q121", "Q122"},
    "FX-SAF-006": {"Q119", "Q121", "Q122"},
}

def read(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))

class OwnerArchiveExactTests(unittest.TestCase):
    def test_seven_quote_exact_checks(self):
        d = read(REF)
        self.assertEqual(d["comparison"]["owner_reported_result"], "ALL_SEVEN_EXACT")
        rows = d["comparison"]["per_question"]
        self.assertEqual({r["question_id"] for r in rows}, QIDS)
        self.assertEqual(len(rows), 7)
        for r in rows:
            self.assertEqual(r["comparison"], "EXACT")
            self.assertEqual(r["explicit_user_candidates"], 1)
            self.assertEqual(r["matching_markdown_quote_blocks"], 1)
            self.assertTrue(r["source_heading_found"])
            self.assertTrue((ROOT / r["existing_excerpt"]).is_file())

    def test_old_and_new_archive_metadata_not_private_contents(self):
        a = read(REF)["archive"]
        self.assertEqual(a["current_filename"], "conversations_20261023.json")
        self.assertEqual(a["previous_filename"], "conversations_20261016.json")
        self.assertEqual(a["current_file_size_bytes"], 8792840)
        self.assertEqual(a["previous_file_size_bytes"], 6729763)
        self.assertTrue(a["old_archive_sha256_matches_previous_local_worksheet_owner_reported"])
        self.assertFalse(a["archived_full_content_uploaded"])

    def test_manifest_marks_only_owner_exact_quote_check(self):
        d = read("specs/source_evidence.json")
        self.assertEqual(audit_source_evidence(ROOT, d), [])
        records = {r["question_id"]: r for r in d["records"] if r["question_id"] in QIDS}
        self.assertEqual(set(records), QIDS)
        for r in records.values():
            self.assertEqual(r["source_kind"], "ORIGINAL")
            self.assertEqual(r["verification"], "DIRECT_CHAT")
            self.assertEqual(r["archive_locator_status"], "PENDING_LOCAL_ARCHIVE")
            check = r["owner_reported_local_archive_check"]
            self.assertEqual(check["comparison"], "EXACT")
            self.assertEqual(check["evidence_ref"], REF)
            self.assertFalse(check["full_context_confirmed"])
            self.assertFalse(r["owner_approved_for_safety"])

    def test_six_requirements_remain_unapproved(self):
        registry = read("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        for r in registry["items"]:
            if r["requirement_id"] in EXPECTED:
                checks = r["partial_owner_archive_quote_checks"]
                self.assertEqual({x["question_id"] for x in checks}, EXPECTED[r["requirement_id"]])
                self.assertTrue(all(x["result"] == "EXACT" and x["evidence_ref"] == REF for x in checks))
            else:
                self.assertNotIn("partial_owner_archive_quote_checks", r)
            self.assertFalse(r["implementation_approved"])
            self.assertIsNone(r["owner_approval"])
            self.assertNotEqual(r["source_kind"], "ORIGINAL")
            self.assertNotEqual(r["comparison_status"], "MATCH")

    def test_phase_and_safety_flags(self):
        d = read(REF)
        for k in ("original_message_ids_independently_verified", "complete_context_verified",
                  "new_original_quotes_uploaded", "safety_requirements_reconciled",
                  "implementation_approved", "human_safety_approval",
                  "owner_approved_for_safety", "forward_trading_enabled"):
            self.assertFalse(d[k])
        self.assertEqual(next(p for p in read("specs/acceptance_registry.json")["phases"]
                              if p["id"] == "PHASE-1")["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
