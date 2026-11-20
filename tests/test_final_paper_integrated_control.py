"""Final AI/virtual integration: risk, billing and simulated signal boundary."""
from __future__ import annotations

import ast
import tempfile
import unittest
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research import final_paper_integrated_control as control
from research import final_paper_integrated_rehearsal as rehearsal
from research.offline_backtest import InputError

NOW=datetime(2026,11,20,6,0,tzinfo=timezone.utc)
EPOCH=int(NOW.timestamp())


def capture(epoch=EPOCH):
    return {
        "capture_epoch":epoch,"source_sha256":"a"*64,
        "quotes":{
            p:{
                "bid":D("159.5") if p!="EUR/USD" else D("1.10000"),
                "ask":D("159.505") if p!="EUR/USD" else D("1.10005"),
                "tickvalue":D("100"),"ticksize":D(".001") if p!="EUR/USD" else D(".00001"),
                "minlot":D(".01"),"maxlot":D("20"),
                "step":D(".01"),
                "point":D(".001") if p!="EUR/USD" else D(".00001"),
            } for p in paper.PAIRS
        },
    }


def signal(pair):
    from hashlib import sha256
    return {
        "id":sha256(("test-signal-"+pair).encode()).hexdigest(),
        "pair":pair,"action":"LONG","verdict":"APPROVED",
        "reviewed_epoch":EPOCH-1,
        "atr14":str(paper.PIP[pair]*D("10")),
        "packet_sha256":"b"*64,
    }


class FinalIntegratedControl(unittest.TestCase):
    def setUp(self):
        self.state=paper.initial_state()
        self.state["paid_inference_calls"]=6
        self.state["last_quote_epoch"]=EPOCH-60

    def gate(self,**override):
        kwargs={
            "quote_epoch":EPOCH,
            "known_important_event_blackout":False,
            "verified_complete_usd_eur_jpy_events":True,
            "verified_independent_broker_pc_clock":True,
            "verified_pre_release_consensus_time":True,
            "verified_spread_slippage_swap_costs":True,
            "verified_single_readonly_mt4_ea":True,
        }
        kwargs.update(override)
        return control.assess(self.state,**kwargs)

    def test_fully_hypothetical_evidence_never_directly_authorizes_live(self):
        result=self.gate()
        self.assertTrue(result["saved_two_model_ai_signal_eligible_by_evidence"])
        self.assertFalse(result["live_virtual_entry_authorized_by_this_pure_evaluator"])
        self.assertFalse(result["new_paid_two_model_ai_eligible_by_evidence_and_budget"])
        self.assertFalse(result["demo_broker_orders_permitted"])

    def test_each_required_attestation_individually_blocks_live(self):
        for field in ("verified_complete_usd_eur_jpy_events",
                      "verified_independent_broker_pc_clock",
                      "verified_pre_release_consensus_time",
                      "verified_spread_slippage_swap_costs",
                      "verified_single_readonly_mt4_ea"):
            with self.subTest(field=field):
                r=self.gate(**{field:False})
                self.assertFalse(r["saved_two_model_ai_signal_eligible_by_evidence"])
                self.assertTrue(r["block_reasons"])

    def test_each_risk_latch_blocks_regardless_of_good_market(self):
        for key in control.RISK:
            with self.subTest(key=key):
                self.state[key]=True
                r=self.gate()
                self.assertFalse(r["saved_two_model_ai_signal_eligible_by_evidence"])
                self.assertIn("RISK_STOP_"+key.upper(),r["block_reasons"])
                self.state[key]=False

    def test_event_15min_and_missing_quote_gap_blocks(self):
        event=self.gate(known_important_event_blackout=True)
        self.assertFalse(event["saved_two_model_ai_signal_eligible_by_evidence"])
        self.state["last_quote_epoch"]=EPOCH-601
        gap=self.gate()
        self.assertIn("QUOTE_GAP_EXCEEDS_600S",gap["block_reasons"])

    def test_budget_old_six_cannot_reset_and_no_new_money_without_receipts(self):
        result=control.budget_check(self.state)
        self.assertEqual(result["historic_api_calls_preserved"],6)
        self.assertFalse(result["conditions_satisfied_hypothetically"])
        self.assertFalse(result["new_billable_dispatch_authorized_by_this_review"])
        self.assertIn("NEW_AI_BUDGET_OPERATOR_APPROVAL_MISSING",result["failure_reasons"])
        self.assertIn("PROVIDER_COST_JPY_INVOICE_UNVERIFIED",result["failure_reasons"])

    def test_worst_case_yen_and_two_request_reservation(self):
        kwargs={
            "new_budget_operator_approved":True,
            "provider_jpy_invoice_independently_reconciled":True,
            "provider_spending_hard_limit_verified":True,
            "approved_month_cap_jpy":"3000.00",
            "provider_month_spend_jpy":"2800.00",
            "worst_case_next_two_calls_jpy":"200.00",
            "month_api_calls":8,"month_call_cap":10,
        }
        report=control.budget_check(self.state,**kwargs)
        self.assertTrue(report["conditions_satisfied_hypothetically"])
        self.assertFalse(report["new_billable_dispatch_authorized_by_this_review"])
        self.assertEqual(report["remaining_after_possible_reservation_jpy"],"0.00")
        report=control.budget_check(self.state,**{
            **kwargs,"worst_case_next_two_calls_jpy":"201.00"})
        self.assertFalse(report["conditions_satisfied_hypothetically"])
        self.assertIn("UPPER_BOUND_NEXT_PAIR_EXCEEDS_REMAINING_JPY",
                      report["failure_reasons"])
        report=control.budget_check(self.state,**{
            **kwargs,"month_api_calls":9})
        self.assertFalse(report["conditions_satisfied_hypothetically"])
        self.assertIn("ANALYST_REVIEWER_TWO_CALL_CAP_EXHAUSTED",
                      report["failure_reasons"])

    def test_budget_rejects_negative_nan_bool_excess_precision_and_over_3000(self):
        for bad in ("NaN","Infinity","-1",True,"10.001",3001):
            with self.subTest(bad=str(bad)):
                with self.assertRaises(InputError):
                    control.budget_check(self.state,approved_month_cap_jpy=bad)

    def test_current_runtime_does_not_accept_mock_operator_truth_values(self):
        future_saved_state=dict(self.state)
        future_saved_state["communication_latched"]=False
        gate,budget=control.existing_runtime_no_go(
            future_saved_state,capture(EPOCH),
            {"active_known_blackout":False,
             "independent_calendar_coverage_attested":True,
             "pc_clock_independently_attested":True})
        self.assertFalse(gate["saved_two_model_ai_signal_eligible_by_evidence"])
        self.assertFalse(budget["conditions_satisfied_hypothetically"])

    def test_isolated_full_signal_to_risk_engine_hypothetical_only(self):
        for pair in paper.PAIRS:
            with self.subTest(pair=pair):
                report=rehearsal.run_virtual_rehearsal(
                    capture(EPOCH),signal(pair),
                    verified_complete_usd_eur_jpy_events=True,
                    verified_independent_broker_pc_clock=True,
                    verified_pre_release_consensus_time=True,
                    verified_spread_slippage_swap_costs=True,
                    verified_single_readonly_mt4_ea=True,
                )
                self.assertEqual(report["actual_paid_api_calls"],0)
                self.assertEqual(report["actual_broker_orders"],0)
                self.assertFalse(report["live_paper_journal_touched"])
                self.assertFalse(report["new_live_virtual_entries_permitted"])
                self.assertLessEqual(
                    D(report["hypothetical_total_risk_jpy"]),D("500.00"))
                self.assertIn(report["hypothetical_virtual_position_count"],(0,1))

    def test_hypothetical_event_halt_blocks_even_approved_model(self):
        outcome=rehearsal.run_virtual_rehearsal(
            capture(EPOCH),signal("USD/JPY"),
            verified_complete_usd_eur_jpy_events=True,
            verified_independent_broker_pc_clock=True,
            verified_pre_release_consensus_time=True,
            verified_spread_slippage_swap_costs=True,
            verified_single_readonly_mt4_ea=True,
            known_important_event_blackout=True,
        )
        self.assertEqual(outcome["hypothetical_virtual_position_count"],0)
        self.assertFalse(outcome["hypothetical_evidence_eligible"])


class ProductionWiring(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"paper"
        runtime._initialize(self.root)
        self.state=paper.initial_state()
        self.state["cycle_number"]=1
        self.state["last_quote_epoch"]=EPOCH-60
        self.state["paid_inference_calls"]=6
        self.state["communication_latched"]=True
        runtime._journal_append(self.root/"journal",self.state,
                                "0"*64,"b"*64,NOW)
        (self.root/"captured").mkdir()

    def test_real_runtime_rejects_even_mocked_attested_calendar(self):
        bogus={
            "active_known_blackout":False,
            "independent_calendar_coverage_attested":True,
            "pc_clock_independently_attested":True,
            "calendar_supplied":True,
        }
        with patch.object(runtime,"_latest_quote",return_value=capture(EPOCH)), \
             patch.object(runtime,"_latest_h1_copy",return_value=self.root/"captured"), \
             patch.object(runtime.blackout,"check",return_value=bogus), \
             patch.object(runtime,"_signals_for_new_h1") as signals, \
             patch.object(runtime.ai,"run") as provider:
            report=runtime.run_one_cycle(self.root,self.root,[],
                allow_paid=True,analyst_model="analyst",reviewer_model="reviewer",
                paid_limit=6,now=NOW)
            signals.assert_not_called()
            provider.assert_not_called()
        end,_=runtime._journal_load(self.root/"journal")
        self.assertEqual(end["cycle_number"],2)
        self.assertEqual(end["paid_inference_calls"],6)
        self.assertEqual(end["positions"],[])
        self.assertEqual(end["pending_signals"],[])
        self.assertTrue(end["communication_latched"])
        self.assertFalse(report["final_new_billable_ai_authorized"])
        self.assertFalse(report["final_ai_virtual_execution_authorized"])
        self.assertIn("COMPLETE_USD_EUR_JPY_CALENDAR_UNATTESTED",
                      report["integrated_block_reasons"])
        self.assertEqual(report["broker_orders_sent_this_run"],0)

    def test_static_no_network_broker_or_embedded_key_and_price_fabrication(self):
        base=Path(__file__).resolve().parents[1]
        for file in ("research/final_paper_integrated_control.py",
                     "research/final_paper_integrated_rehearsal.py",
                     "research/final_paper_integrated_readiness.py"):
            source=(base/file).read_text("utf-8")
            parsed=ast.parse(source)
            imports=[n for n in ast.walk(parsed) if isinstance(
                n,(ast.Import,ast.ImportFrom))]
            self.assertFalse(any(
                getattr(n,"module","") in (
                    "urllib.request","requests","MetaTrader5")
                for n in imports))
            for forbidden in ("allow_external_api=True","OPENAI_API_KEY",
                              "_journal_append(","OrderSend(","OrderClose("):
                self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
