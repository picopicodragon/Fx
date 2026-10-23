"""Validate risk formula decision blockers and hypothetical JPY examples.

Documentation-stage tests only, never a broker calculation or order approval.
"""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
REPORT = "specs/p0_01_risk_formula_open_decisions.json"
D = Decimal


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class RiskFormulaOpenDecisionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = read(REPORT)
        cls.cases = {
            row["id"]: row
            for row in cls.record["hypothetical_numeric_scenarios"]["cases"]
        }

    def test_ten_open_owner_decisions_each_block_implementation(self):
        rows = self.record["open_decisions"]
        self.assertEqual({d["id"] for d in rows},
                         {f"FORM-{i:02d}" for i in range(1, 11)})
        self.assertEqual(len(rows), 10)
        for d in rows:
            self.assertEqual(d["priority"], "P0")
            self.assertEqual(d["owner_status"], "UNDECIDED_IMPLEMENTATION_DETAIL")
            self.assertIs(d["blocking"], True)
            self.assertTrue(d["question_ids"])
            self.assertTrue(d["required_choice"])
            self.assertTrue(d["unsafe_guess"])
            self.assertTrue(d["evidence_to_collect"])
            self.assertTrue(d["acceptance_condition"])

    def test_existing_percentage_policy_unchanged_and_inputs_included(self):
        policy = self.record["adopted_fixed_controls"]
        self.assertEqual(D(policy["individual_risk_fraction_of_current_equity"]),
                         D("0.005"))
        self.assertEqual(D(policy["combined_risk_fraction_of_current_equity"]),
                         D("0.010"))
        self.assertEqual(D(policy["daily_loss_fraction_of_ny17_opening_equity"]),
                         D("0.015"))
        for flag in ("aggregate_include_existing_pending_candidate",
                     "reject_uncomputable_new_order", "daily_denominator_frozen",
                     "drawdown_unitized_for_external_flows",
                     "stop_latches_separate",
                     "external_order_unknown_no_blind_retry",
                     "live_trading_forbidden"):
            self.assertIs(policy[flag], True)
        for source in self.record["evidence_refs"]:
            self.assertTrue((ROOT / source).is_file(), source)

    def test_jpy_quote_sl_price_difference_is_hypothetical(self):
        row = self.cases["HF-01"]
        self.assertEqual(row["kind"], "JPY_QUOTED_STOP_EXAMPLE")
        movement = D(row["hypothetical_entry_jpy_per_base"]) - D(
            row["hypothetical_stop_jpy_per_base"]
        )
        exposure = movement * D(row["hypothetical_base_units"])
        self.assertEqual(exposure, D("500"))
        self.assertEqual(exposure, D(row["quote_loss_jpy"]))

    def test_usd_quote_conversion_varies_with_fx_rate(self):
        a, b = self.cases["HF-02"], self.cases["HF-03"]
        usd_amount = (
            D(a["hypothetical_entry_usd_per_base"])
            - D(a["hypothetical_stop_usd_per_base"])
        ) * D(a["hypothetical_base_units"])
        self.assertEqual(usd_amount, D("10"))
        self.assertEqual(usd_amount, D(a["quote_loss_usd"]))
        self.assertEqual(usd_amount, D(b["quote_loss_usd"]))
        self.assertEqual(usd_amount * D(a["hypothetical_usd_jpy_rate"]),
                         D(a["converted_loss_jpy"]))
        self.assertEqual(usd_amount * D(b["hypothetical_usd_jpy_rate"]),
                         D(b["converted_loss_jpy"]))
        self.assertGreater(D(b["converted_loss_jpy"]),
                           D(a["converted_loss_jpy"]))

    def test_decimal_boundary_never_rounds_down_to_single_risk_limit(self):
        row = self.cases["HF-04"]
        ceiling = D(row["equity_jpy"]) * D(
            self.record["adopted_fixed_controls"][
                "individual_risk_fraction_of_current_equity"
            ]
        )
        self.assertEqual(ceiling, D(row["individual_ceiling_jpy"]))
        self.assertGreater(D(row["candidate_risk_jpy"]), ceiling)
        self.assertEqual(row["numeric_comparison"], "EXCEEDS_SINGLE_LIMIT")
        self.assertEqual(D(row["candidate_risk_jpy"]), D("500.01"))

    def test_aggregated_pending_and_costs_can_cross_limit(self):
        rate = D(self.record["adopted_fixed_controls"][
            "combined_risk_fraction_of_current_equity"
        ])
        row = self.cases["HF-05"]
        total = (D(row["existing_risk_jpy"]) +
                 D(row["pending_risk_jpy"]) +
                 D(row["candidate_risk_jpy"]))
        ceiling = D(row["equity_jpy"]) * rate
        self.assertEqual(total, D(row["combined_jpy"]))
        self.assertEqual(total, D("1000.01"))
        self.assertEqual(ceiling, D(row["combined_ceiling_jpy"]))
        self.assertGreater(total, ceiling)
        row2 = self.cases["HF-06"]
        cost_total = (D(row2["existing_risk_jpy"]) +
                      D(row2["pending_risk_jpy"]) +
                      D(row2["candidate_base_risk_jpy"]) +
                      D(row2["hypothetical_extra_cost_jpy"]))
        self.assertEqual(cost_total, D(row2["combined_with_cost_jpy"]))
        self.assertGreater(cost_total, D(row2["equity_jpy"]) * rate)

    def test_all_registers_remain_unapproved_and_no_live_orders(self):
        self.assertEqual(self.record["status"], "OPEN_DESIGN_DECISIONS_ONLY")
        gates = self.record["review_gates"]
        self.assertTrue(all(gates[key] is False for key in (
            "all_open_decisions_authorized",
            "formula_implementation_approved",
            "original_complete_reconciliation_approved",
            "safety_level_owner_approval",
            "new_order_permission",
            "forward_trading_enabled",
        )))
        self.assertIsNone(gates["owner_approval_reference"])
        self.assertEqual(gates["phase_1"], "BLOCKED")
        self.assertIn("not a trading order", self.record["note"])
        registry = read("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        for item in registry["items"]:
            self.assertIs(item["implementation_approved"], False)
            self.assertIsNone(item["owner_approval"])
        phase = next(p for p in read("specs/acceptance_registry.json")["phases"]
                     if p["id"] == "PHASE-1")
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
