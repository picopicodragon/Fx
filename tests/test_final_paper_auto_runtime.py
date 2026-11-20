"""Integration: evidence -> budgeted dual AI -> next quote -> virtual only."""
from __future__ import annotations

import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research import final_paper_auto_entry_gate as gate
from research import final_paper_auto_budget as budget
from research import final_paper_auto_pipeline as pipeline
from research import final_paper_ai_continuation_audit as old_paid
from research.offline_backtest import InputError

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
EPOCH=int(NOW.timestamp())
CARRIES={pair:{"LONG":"10","SHORT":"10"} for pair in paper.PAIRS}


def quote(epoch:int)->dict:
    return {
        "capture_epoch":epoch,"source_sha256":"a"*64,
        "quotes":{
            pair:{
                "bid":D("159.500") if pair=="USD/JPY" else
                      D("175.200") if pair=="EUR/JPY" else D("1.1000"),
                "ask":D("159.505") if pair=="USD/JPY" else
                      D("175.210") if pair=="EUR/JPY" else D("1.10005"),
                "tickvalue":D("100"),
                "ticksize":D(".00001") if pair=="EUR/USD" else D(".001"),
                "minlot":D(".01"),"maxlot":D("20"),
                "step":D(".01"),
                "point":D(".00001") if pair=="EUR/USD" else D(".001"),
            } for pair in paper.PAIRS
        },
    }


def synthetic_signal(epoch:int)->dict:
    return {
        "id":"a"*64,"pair":"USD/JPY","action":"LONG",
        "verdict":"APPROVED","reviewed_epoch":epoch+1,
        "atr14":".10","packet_sha256":"b"*64,
    }


class AutomaticVirtualIntegrationTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root=Path(t.name)
        self.state_root=root/"final_virtual_paper"
        runtime._initialize(self.state_root)
        (self.state_root/"auto_budget_journal").mkdir()
        (self.state_root/"auto_ai_research").mkdir()
        self.mt4=root/"MQL4"/"Files"
        self.mt4.mkdir(parents=True)
        self.bundle=root/"news_bundle"
        self.bundle.mkdir()
        self.permit=root/"consented_entry.json"
        self.approved_budget=root/"consented_budget.json"
        self.archive=root/"official_public_capture_fake"
        self.archive.mkdir()
        initial=paper.initial_state()
        initial["cycle_number"]=1
        initial["last_quote_epoch"]=EPOCH-60
        initial["paid_inference_calls"]=6
        initial["communication_latched"]=False
        self.init_head=runtime._journal_append(
            self.state_root/"journal",initial,"0"*64,"a"*64,
            NOW-timedelta(minutes=1))
        self.gate={
            "entry_evidence_ready_by_operator_attestation":True,
            "known_event_blackout_active":False,
            "carry_costs_jpy_per_lot_day":CARRIES,
            "permit_sha256_local_only":"e"*64,
        }
        self.policy={"policy_sha256_local_only":"d"*64,
                     "max_calls":12,"max_jpy":2000,
                     "reserve_per_pair_jpy":300}

    def call(self,epoch:int,*,signals=None,fail_gate=False,fail_budget=False,
             communications=False):
        model=synthetic_signal(epoch) if signals is None else signals
        current=quote(epoch)
        # Legacy completed invoice never changes: six requests exactly.
        def old_reconciled(root):
            return {
                "journal_head_sha256_local_only":
                    runtime._journal_load(root/"journal")[1],
                "paid_calls_in_completed_ledgers":6,
                "paid_calls_recorded_in_journal":6,
            }
        with ExitStack() as e:
            e.enter_context(patch.object(runtime,"_latest_quote",
                                         return_value=current))
            e.enter_context(patch.object(runtime,"_latest_h1_copy",
                                         return_value=self.bundle))
            e.enter_context(patch.object(runtime.blackout,"check",
                  return_value={
                      "active_known_blackout":False,
                      "calendar_supplied":False,
                      "independent_calendar_coverage_attested":False,
                      "pc_clock_independently_attested":False,
                  }))
            e.enter_context(patch.object(old_paid,"audit",
                                         side_effect=old_reconciled))
            if fail_gate:
                e.enter_context(patch.object(gate,"evaluate",
                                             side_effect=InputError("BAD_PROOF")))
            else:
                e.enter_context(patch.object(gate,"evaluate",
                                             return_value=self.gate))
            if fail_budget:
                e.enter_context(patch.object(budget,"policy",
                                             side_effect=InputError("COST_MISSING")))
            else:
                e.enter_context(patch.object(budget,"policy",
                                             return_value=self.policy))
            e.enter_context(patch.object(budget,"check",return_value={}))
            new_receipts=(["f"*64] if model else [])
            e.enter_context(patch.object(pipeline,"decisions",
                return_value=(
                    [model] if model else [],
                    ["USD/JPY:18000"] if model else [],
                    new_receipts,2 if model else 0)))
            return runtime.run_one_cycle(
                self.mt4,self.state_root,[self.bundle],
                allow_paid=False,analyst_model="gpt-an",
                reviewer_model="gpt-review",paid_limit=0,
                now=datetime.fromtimestamp(epoch,tz=timezone.utc),
                final_auto_evidence=self.permit,
                final_auto_official_archive=self.archive,
                final_auto_budget_authorization=self.approved_budget,
                allow_final_paid=True)

    def test_ai_approved_signal_queued_then_open_only_on_next_source_quote(self):
        first=self.call(EPOCH)
        self.assertEqual(first["new_final_paid_calls_this_cycle"],2)
        self.assertTrue(first["final_operator_research_gate_open"])
        recorded,head=runtime._journal_load(self.state_root/"journal")
        self.assertEqual(recorded["paid_inference_calls"],6)
        self.assertEqual(recorded["auto_new_paid_inference_calls"],2)
        self.assertEqual(recorded["auto_budget_reservation_receipts"],
                         ["f"*64])
        self.assertEqual(recorded["positions"],[])
        self.assertEqual(len(recorded["pending_signals"]),1)
        second=self.call(EPOCH+60,signals=False)
        self.assertEqual(second["new_final_paid_calls_this_cycle"],0)
        self.assertEqual(second["virtual_position_count"],1)
        self.assertIn("VIRTUAL_POSITION_OPENED",second["events"])
        recorded,_=runtime._journal_load(self.state_root/"journal")
        self.assertEqual(recorded["paid_inference_calls"],6)
        self.assertEqual(len(recorded["positions"]),1)
        self.assertLessEqual(D(recorded["positions"][0]["risk_jpy"]),
                             D("500.00"))
        self.assertEqual(second["broker_orders_sent_this_run"],0)
        self.assertFalse(second["real_orders_permitted"])

    def test_unverified_macro_gate_does_not_even_load_paid_or_saved_ai(self):
        with patch.object(pipeline,"decisions") as no_ai:
            result=self.call(EPOCH,fail_gate=True)
            self.assertEqual(result["new_final_paid_calls_this_cycle"],0)
            self.assertFalse(result["entry_readiness_gate_open"])
            self.assertEqual(result["virtual_position_count"],0)
            self.assertEqual(result["final_auto_gate_hold_reason_code"],
                             "ENTRY_EVIDENCE_INCOMPLETE_OR_EXPIRED")
            no_ai.assert_not_called()

    def test_unverified_budget_stops_signal_even_if_entry_evidence_is_valid(self):
        result=self.call(EPOCH,fail_budget=True)
        self.assertFalse(result["entry_readiness_gate_open"])
        self.assertEqual(result["new_final_paid_calls_this_cycle"],0)
        self.assertEqual(result["virtual_position_count"],0)
        self.assertEqual(result["final_auto_gate_hold_reason_code"],
                         "PAID_BUDGET_PENDING_UNRECONCILED_OR_EXPIRED")

    def test_legacy_read_only_observer_does_not_gain_entry_permission(self):
        with patch.object(runtime,"_latest_quote",return_value=quote(EPOCH)), \
             patch.object(runtime,"_latest_h1_copy",
                          return_value=self.bundle), \
             patch.object(runtime.blackout,"check",
                          return_value={
                            "active_known_blackout":False,
                            "calendar_supplied":False,
                            "independent_calendar_coverage_attested":False,
                            "pc_clock_independently_attested":False,
                          }), \
             patch.object(runtime,"_signals_for_new_h1") as old_ai:
            out=runtime.run_one_cycle(
                self.mt4,self.state_root,[],allow_paid=False,
                analyst_model="",reviewer_model="",paid_limit=0,now=NOW)
            old_ai.assert_not_called()
        self.assertFalse(out["entry_readiness_gate_open"])
        self.assertEqual(out["virtual_position_count"],0)


if __name__=="__main__":
    unittest.main()
