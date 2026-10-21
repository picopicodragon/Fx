"""P1-05: static tests for the offline mock-broker *design plan*.

No broker APIs, orders, real account data, or SQLite writes.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "specs" / "p1_05_mock_broker_scenarios.json"
SCHEMA = ROOT / "schemas" / "offline" / "mock_broker_evidence.schema.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MockBrokerBoundaryPlanTests(unittest.TestCase):
    def test_matrix_is_unexecuted_and_disconnected(self):
        plan = read_json(MATRIX)
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["plan_id"], "P1-05")
        self.assertEqual(plan["status"], "DRAFT_ONLY")
        self.assertFalse(plan["broker_connected"])
        self.assertFalse(plan["orders_permitted"])
        self.assertFalse(plan["implementation_approved"])
        self.assertFalse(plan["reconciliation_provider_verified"])

    def test_all_scenarios_are_synthetic_with_no_fabricated_evidence(self):
        cases = read_json(MATRIX)["test_cases"]
        self.assertEqual(len(cases), 27)
        self.assertEqual(
            {item["id"] for item in cases},
            {f"P1-05-F{i:02d}" for i in range(1, 28)},
        )
        for item in cases:
            with self.subTest(case=item["id"]):
                self.assertEqual(item["fixture"], "SYNTHETIC_MOCK_ONLY")
                self.assertEqual(item["status"], "NOT_EXECUTED")
                self.assertEqual(item["evidence_refs"], [])
                self.assertFalse(item["owner_safety_approved"])
                self.assertTrue(item["requirements"])
                self.assertTrue(all(ref.startswith("Q") for ref in item["requirements"]))
                self.assertTrue(item["stimulus"])
                self.assertTrue(item["expected"])

    def test_mock_case_categories_cover_major_failure_boundaries(self):
        categories = {x["category"] for x in read_json(MATRIX)["test_cases"]}
        self.assertEqual(categories, {
            "PRE_DISPATCH", "RESPONSE", "RECONCILIATION",
            "STOP_AND_RESTART", "DATA_AND_SECURITY", "AUTHORIZATION",
        })
        all_requirements = {
            req for x in read_json(MATRIX)["test_cases"] for req in x["requirements"]
        }
        for requirement in ("Q107", "Q110", "Q121", "Q171", "Q172",
                            "Q194", "Q195", "Q196", "Q197", "Q198", "Q199"):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, all_requirements)

    def test_ambiguous_responses_never_authorize_blind_retry(self):
        by_id = {x["id"]: x for x in read_json(MATRIX)["test_cases"]}
        for number in ("F08", "F09", "F10", "F12"):
            with self.subTest(case=number):
                expected = by_id["P1-05-" + number]["expected"]
                self.assertIn("OUTCOME_UNKNOWN", expected)
                self.assertIn("NO_BLIND_RETRY", expected)
                self.assertIn("NEW_ORDER_BLOCKED", expected)
        self.assertIn(
            "RESPONSE_ACCEPTED_NOT_FILL_PROOF", by_id["P1-05-F06"]["expected"]
        )
        self.assertIn(
            "RESPONSE_REJECTED_NOT_ABSENCE_PROOF", by_id["P1-05-F07"]["expected"]
        )
        self.assertIn("ABSENCE_UNPROVEN", by_id["P1-05-F13"]["expected"])
        self.assertIn("OWNER_APPROVAL_REQUIRED", by_id["P1-05-F21"]["expected"])
        self.assertIn("APPROVAL_FLAGS_UNCHANGED", by_id["P1-05-F27"]["expected"])

    def test_offline_schema_separates_response_from_broker_observations(self):
        doc = read_json(SCHEMA)
        self.assertEqual(doc["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(doc["type"], "object")
        self.assertFalse(doc["additionalProperties"])
        props = doc["properties"]
        self.assertEqual(props["schema_version"], {"const": 1})
        self.assertEqual(props["mock_only"], {"const": True})
        self.assertEqual(set(doc["required"]), set(props))
        self.assertEqual(set(props["response_classification"]["enum"]), {
            "RESPONSE_ACCEPTED", "RESPONSE_REJECTED", "OUTCOME_UNKNOWN",
        })
        for key in ("order_observation", "fill_observation", "position_observation"):
            self.assertIn(key, props)
        for name in ("submit", "execute", "trade_authorized", "broker_password",
                     "live_trading_enabled"):
            self.assertNotIn(name, props)


if __name__ == "__main__":
    unittest.main()
