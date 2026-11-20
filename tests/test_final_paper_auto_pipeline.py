"""Complete simulated TWO AI provider flow with REAL on-disk budget journal."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_auto_pipeline as auto
from research import final_paper_auto_budget as budget
from research import final_demo_periodic as period
from research import final_demo_periodic_ai as ai
from research import final_paper_engine as paper
from research.offline_backtest import InputError

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
ANALYST="gpt-6-analyst"
REVIEWER="gpt-6-reviewer"
PAIR_SHA={pair:hashlib.sha256(pair.encode("ascii")).hexdigest()
          for pair in paper.PAIRS}


class AutoTwoModelPipelineTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        (self.root/"auto_budget_journal").mkdir()
        (self.root/"auto_ai_research").mkdir()
        self.captures=self.root/"captures"
        self.captures.mkdir()
        self.news=self.root/"verified_news"
        self.news.mkdir()
        self.policy={
            "max_calls":6,
            "max_jpy":1200,
            "reserve_per_pair_jpy":400,
        }
        self.state=paper.initial_state()
        self.state["paid_inference_calls"]=6
        self.h1={
            "captures":{
                period.PAIRS[pair]:{
                    "candles":[{"server_epoch":1763632000}]
                } for pair in paper.PAIRS
            },
        }

    def _mock_period_packet(self,capture,bundles,pair,unused,*,now,
                            output_must_be_new):
        return {"pair":pair,"macro_coverage_complete_research_only":True,
                "technical":{"atr14":"0.10"}}

    def _mock_ai_completion(self,captures,bundles,pair,ledger,**kwargs):
        # The reservation MUST exist before either mock provider dispatch.
        st=budget._load(self.root/"auto_budget_journal")
        self.assertEqual(len(st["pending_reservations"]),1)
        self.assertFalse(ledger.exists())
        self.assertTrue(kwargs["allow_external_api"])
        self.assertEqual(kwargs["max_api_calls"],2)
        packet=PAIR_SHA[pair]
        state={
            "schema":ai.SCHEMA,
            "packet_sha256":packet,
            "analyst_model":ANALYST,
            "reviewer_model":REVIEWER,
            "stage":"COMPLETE","pending_role":None,
            "analyst":{"action":"LONG" if pair=="USD/JPY" else "HOLD",
                       "hypothesis":"macro cause",
                       "counterevidence":"credible alternative"},
            "reviewer":{"verdict":"APPROVED",
                        "rationale":"independent source review"},
            "execution_authorized":False,
            "real_orders_permitted":False,
        }
        ledger.write_text(json.dumps(state),encoding="utf-8")
        return {
            "status":"PERIODIC_AI_TWO_MODELS_REVIEWED_RESEARCH_NO_GO",
            "stage":"COMPLETE","paid_calls_this_run":2,
            "packet_sha256_local_only":packet,
            "model_action_research_only":state["analyst"]["action"],
            "model_verdict":"APPROVED",
        }

    def _execute(self,api=None):
        with patch.object(period,"_read_h1",return_value=self.h1), \
             patch.object(period,"run",side_effect=self._mock_period_packet), \
             patch.object(ai,"_identity",
                          side_effect=lambda report,analyst_model,
                          reviewer_model:{
                              "packet_sha256":PAIR_SHA[report["pair"]]}), \
             patch.object(ai,"run",side_effect=api or self._mock_ai_completion):
            return auto.decisions(
                self.state,self.captures,[self.news],self.root,NOW,
                policy=self.policy,analyst_model=ANALYST,
                reviewer_model=REVIEWER)

    def test_all_three_pairs_two_models_six_reserved_settled_before_signal(self):
        signals,seen,receipts,used=self._execute()
        self.assertEqual(used,6)
        self.assertEqual(len(seen),3)
        self.assertEqual(len(receipts),3)
        self.assertEqual(len(signals),3)
        self.assertTrue(all(paper._valid_signal(s) for s in signals))
        self.assertEqual(signals[0]["action"],"LONG")
        self.assertEqual(signals[1]["action"],"HOLD")
        self.assertEqual(signals[2]["action"],"HOLD")
        account=budget.check(self.policy,self.root/"auto_budget_journal",
                             journal_reserve_shas=receipts)
        self.assertEqual(account["spent_or_reserved_jpy"],1200)
        self.assertEqual(account["spent_or_reserved_calls"],6)
        self.assertEqual(account["sequence"],6)
        self.assertEqual(self.state["paid_inference_calls"],6)
        self.state["processed_h1_keys"]=seen
        self.state["auto_budget_reservation_receipts"]=receipts
        next_signals,next_seen,next_receipts,next_used=self._execute()
        self.assertEqual((next_signals,next_seen,next_receipts,next_used),
                         ([],[],[],0))

    def test_network_unknown_after_reservation_stops_all_future_dispatches(self):
        def network_unknown(*args,**kwargs):
            self.assertEqual(budget._load(
                self.root/"auto_budget_journal")["sequence"],1)
            raise InputError("POSSIBLY_BILLED_NETWORK_UNKNOWN")
        with self.assertRaises(InputError):
            self._execute(api=network_unknown)
        unresolved=budget._load(self.root/"auto_budget_journal")
        self.assertEqual(len(unresolved["pending_reservations"]),1)
        self.assertEqual(unresolved["spent_or_reserved_calls"],2)
        with self.assertRaises(InputError):
            self._execute(api=network_unknown)
        self.assertEqual(budget._load(
            self.root/"auto_budget_journal")["sequence"],1)

    def test_exhausted_new_budget_defers_other_pairs_without_network_retry(self):
        self.policy["max_calls"]=2
        self.policy["max_jpy"]=400
        signals,seen,receipts,used=self._execute()
        self.assertEqual(used,2)
        self.assertEqual(len(signals),1)
        self.assertEqual(len(seen),3)
        self.assertEqual(len(receipts),1)
        self.assertEqual(budget._load(
            self.root/"auto_budget_journal")["spent_or_reserved_calls"],2)


if __name__=="__main__":
    unittest.main()
