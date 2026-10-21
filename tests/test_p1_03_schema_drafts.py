"""P1-03: offline schema draft structure checks (NOT runtime JSON Schema validation)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "offline"
NAMES = (
    "source_record",
    "ai_research_result",
    "ai_review_result",
    "bounded_decision_result",
)


def schema_for(name: str) -> dict:
    return json.loads((SCHEMA_DIR / (name + ".schema.json")).read_text(encoding="utf-8"))


class OfflineContractDraftTests(unittest.TestCase):
    def test_all_schema_drafts_are_closed_and_versioned(self):
        for name in NAMES:
            with self.subTest(name=name):
                doc = schema_for(name)
                self.assertEqual(doc["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(doc["type"], "object")
                self.assertFalse(doc["additionalProperties"])
                self.assertEqual(doc["properties"]["schema_version"], {"const": 1})
                self.assertEqual(set(doc["required"]), set(doc["properties"]))
                self.assertNotIn("order", name)
                for forbidden in (
                    "order_send", "trade_authorized", "forward_trading_enabled",
                    "implementation_approved", "owner_approved_for_safety",
                    "broker_credentials", "live_order"
                ):
                    self.assertNotIn(forbidden, doc["properties"])

    def test_research_cannot_directly_claim_approval(self):
        doc = schema_for("ai_research_result")
        self.assertEqual(doc["properties"]["role"]["const"], "MACRO_RESEARCH")
        self.assertEqual(
            set(doc["properties"]["evidence_state"]["enum"]),
            {"PENDING", "INSUFFICIENT", "CANDIDATE"},
        )

    def test_review_preserves_exact_q28_verdicts_and_q29_limit(self):
        doc = schema_for("ai_review_result")
        self.assertEqual(doc["properties"]["role"]["const"], "INDEPENDENT_REVIEW")
        self.assertEqual(
            set(doc["properties"]["verdict"]["enum"]),
            {"APPROVED", "REVISION", "REJECTED", "PENDING"},
        )
        self.assertEqual(doc["properties"]["revision_count"]["maximum"], 2)

    def test_bounded_decision_confidence_is_capped_and_nullable(self):
        doc = schema_for("bounded_decision_result")
        confidence = doc["properties"]["confidence"]
        self.assertEqual(confidence["minimum"], 0)
        self.assertEqual(confidence["maximum"], 1)
        self.assertIn("null", confidence["type"])
        self.assertNotIn("BUY", doc["properties"]["decision_type"]["enum"])
        self.assertNotIn("SELL", doc["properties"]["decision_type"]["enum"])

    def test_market_source_retrieval_and_publication_are_separate(self):
        doc = schema_for("source_record")
        self.assertIn("retrieved_at_utc", doc["required"])
        self.assertIn("published_at_utc", doc["required"])
        self.assertNotEqual(doc["properties"]["published_at_utc"],
                            doc["properties"]["retrieved_at_utc"])


if __name__ == "__main__":
    unittest.main()
