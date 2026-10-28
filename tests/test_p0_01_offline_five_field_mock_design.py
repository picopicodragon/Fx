"""Safety contract tests for the P0-01 synthetic five-field DESIGN, not a mock implementation."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "specs/p0_01_five_field_offline_mock_design.json"
BROKER_PLAN = ROOT / "specs/p0_01_mt4_readonly_observation_plan.json"
ISOLATION_PLAN = ROOT / "specs/p0_01_isolated_demo_environment_design.json"
FIELDS = {
    "min_lot": "MODE_MINLOT",
    "lot_step": "MODE_LOTSTEP",
    "point_quote": "MODE_POINT",
    "tick_size_points": "MODE_TICKSIZE",
    "tick_value_deposit_currency": "MODE_TICKVALUE",
}
PAIRS = ["USD/JPY", "EUR/JPY", "GBP/USD", "AUD/USD"]


class OfflineFiveFieldDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design = json.loads(DESIGN.read_text(encoding="utf-8"))
        cls.broker = json.loads(BROKER_PLAN.read_text(encoding="utf-8"))
        cls.isolated = json.loads(ISOLATION_PLAN.read_text(encoding="utf-8"))

    def test_exact_20_field_mapping_and_no_synthetic_broker_attestation(self):
        p = self.design
        self.assertEqual(
            p["status"], "DESIGN_ONLY_NOT_IMPLEMENTED_AND_NOT_AUTHORIZED_FOR_MT4_RUNTIME"
        )
        scope = p["scope"]
        self.assertEqual(scope["pairs"], PAIRS)
        self.assertEqual(scope["fields"], FIELDS)
        self.assertEqual(scope["fixture_count"], 20)
        self.assertEqual(scope["input_type"], "IN_MEMORY_SYNTHETIC_FIXTURES_ONLY")
        self.assertFalse(scope["always_production_usable"])
        self.assertEqual(scope["fixture_identity"],
                         "SYNTHETIC_NON_BROKER_VALUES_DO_NOT_EXPORT")
        self.assertEqual(scope["output"], "SAFE_STATUS_CODES_AND_FIELD_NAMES_ONLY")
        from scripts.audit_mt4_readonly_source import EXPECTED_FIELDS, EXPECTED_SYMBOLS
        self.assertEqual(scope["fields"], EXPECTED_FIELDS)
        self.assertEqual(
            [x.replace("/", "") for x in PAIRS], list(EXPECTED_SYMBOLS)
        )
        self.assertEqual(
            self.broker["status"],
            "READONLY_MQL4_COMPILATION_OWNER_REPORTED_ALL_RUNTIME_VALUES_PENDING",
        )
        for row in self.broker["symbol_status"]:
            self.assertFalse(row["production_usable"])
            self.assertTrue(all(x is None for x in row["verified_values"].values()))

    def test_design_disallows_terminal_calls_private_data_and_trading(self):
        p = self.design
        s = p["safety"]
        self.assertEqual(s["phase_1"], "BLOCKED")
        for key in ("terminal_execution_approved", "terminal_deployed",
                    "broker_queried", "orders_generated", "forward_trading_enabled",
                    "implementation_approved", "human_safety_approval",
                    "owner_approved_for_safety"):
            self.assertFalse(s[key])
        self.assertIn("OrderSend", s["never_call"])
        self.assertIn("MarketInfo", s["never_call"])
        self.assertIn("MQL4/Scripts", s["never_write_paths"])
        self.assertIn("Documents/FxLocalReview", s["never_read_paths"])
        self.assertTrue(s["no_implicit_promotion_from_valid_mock"])
        self.assertFalse(
            self.isolated["unresolved_broker_policy"]["new_demo_opening_currently_authorized"]
        )

    def test_scenarios_and_human_stage_boundary(self):
        p = self.design
        self.assertGreaterEqual(len(p["synthetic_scenarios"]), 10)
        self.assertEqual({x["id"] for x in p["requirements"]},
                         {f"F{i:02d}" for i in range(1, 11)})
        gates = p["proposal_sequence"]
        self.assertEqual([x["id"] for x in gates], ["D1","D2","D3","D4"])
        self.assertEqual(gates[1]["status"], "NOT_STARTED")
        self.assertEqual(gates[3]["status"], "NOT_AUTHORIZED")
        for req in p["requirements"]:
            self.assertIn(req["on_failure"],
                          {"REVIEW_REQUIRED","INCOMPLETE","UNVERIFIED"})
        self.assertIn("MQL4_EX4_EXECUTION", p["non_goals"])
        self.assertIn("FORM_01_03_PRODUCTION_APPROVAL", p["non_goals"])


if __name__ == "__main__":
    unittest.main()
