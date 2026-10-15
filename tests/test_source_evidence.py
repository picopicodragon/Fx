"""Q113 source evidence manifest regression tests."""
import copy
import tempfile
import unittest
from pathlib import Path

from scripts.check_source_evidence import audit


class EvidenceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.excerpt = self.root / "specs/source_excerpts/Q113.md"
        self.excerpt.parent.mkdir(parents=True)
        self.excerpt.write_text("# Q113\n\nConfirmed user decision.\n", encoding="utf-8")
        self.data = {
            "schema_version": 1,
            "records": [{
                "question_id": "Q113",
                "excerpt_path": "specs/source_excerpts/Q113.md",
                "source_kind": "ORIGINAL",
                "verification": "DIRECT_CHAT",
                "archive_locator_status": "PENDING_LOCAL_ARCHIVE",
                "source_locator": "Current design chat, decision Q113",
                "confidentiality_review": "REVIEWED_FOR_GITHUB",
                "owner_approved_for_safety": False
            }],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_original_seen_in_chat_local_archive_pending_is_valid(self):
        self.assertEqual(audit(self.root, self.data), [])

    def test_pending_summary_must_not_pretend_to_be_original(self):
        d = copy.deepcopy(self.data)
        d["records"][0]["verification"] = "PENDING"
        self.assertIn("direct verification", "\n".join(audit(self.root, d)))

    def test_unreviewed_excerpt_is_rejected(self):
        d = copy.deepcopy(self.data)
        d["records"][0]["confidentiality_review"] = "NOT_REVIEWED"
        self.assertIn("reviewed for confidentiality", "\n".join(audit(self.root, d)))

    def test_nonexistent_excerpt_is_rejected(self):
        self.excerpt.unlink()
        self.assertIn("missing", "\n".join(audit(self.root, self.data)))

    def test_fake_approval_is_rejected(self):
        d = copy.deepcopy(self.data)
        d["records"][0]["owner_approved_for_safety"] = True
        self.assertIn("cannot act as a safety", "\n".join(audit(self.root, d)))

    def test_traversal_is_rejected(self):
        d = copy.deepcopy(self.data)
        d["records"][0]["excerpt_path"] = "../../private/original.md"
        self.assertIn("must be specs/source_excerpts", "\n".join(audit(self.root, d)))

    def test_local_archive_needs_confirmation(self):
        d = copy.deepcopy(self.data)
        d["records"][0]["verification"] = "LOCAL_ARCHIVE"
        self.assertIn("needs confirmed archive", "\n".join(audit(self.root, d)))


if __name__ == "__main__":
    unittest.main()
