"""Five-gate final-paper read-only readiness and E2E permission regression."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch, call

from research import final_paper_five_gate_readiness as m
from research.offline_backtest import InputError

HEAD = "a" * 64

def simulated(*, certified=False, released=False):
    state = {
        "cycle_number": 292,
        "communication_latched": not released,
        "dd4_latched": False, "dd5_latched": False,
        "daily_loss_latched": False,
        "positions": [], "virtual_only": True,
        "broker_orders_permitted": False,
    }
    if released:
        state["manual_comm_release_sha256"] = "b" * 64
    operating = {
        "journal_head_sha256_local_only": HEAD,
        "completed_cycles": 292,
        "price_stream_warning_level_pc_derived": "FRESH",
        "independent_broker_clock_attested": certified,
        "transaction_costs_fully_verified": certified,
        "paid_ai_calls_remaining_under_current_limit": 2 if certified else 0,
        "paid_ai_calls_lifetime": 6 if not certified else 4,
    }
    paid = {
        "journal_head_sha256_local_only": HEAD,
        "journal_cycles": 292,
        "paid_calls_recorded_in_journal": 6 if not certified else 4,
        "paid_calls_in_completed_ledgers": 6 if not certified else 4,
    }
    costs = {
        "operator_approved_paid_renewal": certified,
        "provider_billing_independently_verified": certified,
        "arithmetic_room_for_reserved_two_calls": certified,
        "future_paid_inference_authorized": certified,
    }
    calendar = {
        "calendar_source_independently_attested": certified,
        "all_important_events_covered": certified,
        "consensus_captured_before_release": certified,
    }
    contract = {
        "latest_quote_fresh_pc_derived": True,
        "broker_clock_independently_attested": certified,
        "full_transaction_costs_verified": certified,
    }
    gap = {"diagnosis": "LATEST_MT4_QUOTE_ALREADY_PROCESSED"}
    return state, operating, paid, costs, calendar, contract, gap


def run_synthetic(*, certified=False, released=False, mutate=False):
    state, operating, paid, costs, calendar, contract, gap = simulated(
        certified=certified, released=released)
    with patch.object(m.runtime, "_journal_load",
                      side_effect=[(state, HEAD), (state, "c" * 64
                                                  if mutate else HEAD)]), \
         patch.object(m.status, "summarize", return_value=operating), \
         patch.object(m.paid, "audit", return_value=paid), \
         patch.object(m.budget, "review", return_value=costs), \
         patch.object(m.events, "audit", return_value=calendar), \
         patch.object(m.contracts, "audit", return_value=contract), \
         patch.object(m.stream, "diagnose", return_value=gap):
        return m.assess(Path("/not-real-paper"), Path("/not-real-mt4"))


class FiveGateReadinessTests(unittest.TestCase):
    def test_realistic_292_cycle_evidence_remains_hold(self):
        result = run_synthetic()
        self.assertEqual(result["completed_cycles"], 292)
        self.assertEqual(result["passed_gate_count"], 0)
        self.assertFalse(result["new_paid_inference_permitted"])
        self.assertFalse(result["new_virtual_positions_permitted"])
        self.assertFalse(result["demo_orders_permitted"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["virtual_entry_preconditions_structurally_met"])

    def test_manual_comm_release_alone_never_opens_paid_or_entry(self):
        result = run_synthetic(released=True)
        self.assertTrue(result["gates"]["APPROVED_COMMUNICATION_RECOVERY"]["passed"])
        self.assertFalse(result["gates"]["MACRO_CLOCK_AND_COST_EVIDENCE"]["passed"])
        self.assertFalse(result["gates"]["PAID_AI_BUDGET_AND_AUTHORIZATION"]["passed"])
        self.assertFalse(result["new_virtual_positions_permitted"])

    def test_even_all_synthetic_pass_flags_cannot_masquerade_as_live_e2e(self):
        result = run_synthetic(certified=True, released=True)
        self.assertTrue(result["virtual_entry_preconditions_structurally_met"])
        self.assertEqual(result["passed_gate_count"], 3)
        self.assertFalse(result["gates"]["PAPER_CONSUMER_HEALTH"]["passed"])
        self.assertFalse(result["gates"]["NEW_VIRTUAL_ENTRY_E2E"]["passed"])
        self.assertFalse(result["live_new_virtual_entry_proven"])
        self.assertFalse(result["new_virtual_positions_permitted"])

    def test_concurrent_journal_mutation_fails_closed(self):
        with self.assertRaises(InputError):
            run_synthetic(mutate=True)

    def test_new_code_has_no_apis_trading_or_latch_mutation(self):
        base=Path(__file__).resolve().parents[1]
        audit=(base/"research/final_paper_five_gate_readiness.py").read_text("utf-8")
        script=(base/"scripts/final_paper_live_supervisor_check_once.ps1").read_text("utf-8")
        for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                          "WebRequest(", "OPENAI_API_KEY", "urllib.request",
                          "ai.run(", "lock.unlink(", "_journal_append("):
            self.assertNotIn(forbidden, audit)
        for forbidden in ("Stop-Process", "Start-Process", "Remove-Item",
                          "Invoke-WebRequest", "OrderSend", "OPENAI_API_KEY"):
            self.assertNotIn(forbidden, script)
        self.assertIn("Get-CimInstance", script)


if __name__=="__main__":
    unittest.main()
