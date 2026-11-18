"""Final-paper entry/API spend guard when independent calendar/clock is absent."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime

NOW=datetime(2026,11,18,5,0,tzinfo=timezone.utc)
T=int(NOW.timestamp())


def quote(epoch=T):
    return {"capture_epoch":epoch,"source_sha256":"a"*64,
            "quotes":{pair:{
                "bid":paper.D("159.50"),"ask":paper.D("159.505"),
                "tickvalue":paper.D("100"),"ticksize":paper.D(".001"),
                "minlot":paper.D(".01"),"step":paper.D(".01"),
                "maxlot":paper.D("20"),"point":paper.D(".001")}
                for pair in paper.PAIRS}}


def signal(epoch=T):
    return {"id":"a"*64,"pair":"USD/JPY","action":"LONG",
            "verdict":"APPROVED","reviewed_epoch":epoch,
            "atr14":"0.15","packet_sha256":"b"*64}


class StrictEntryAndBillingGatesTests(unittest.TestCase):
    def test_pure_engine_blocks_entry_but_approved_flat_remains_risk_reducing(self):
        state=paper.initial_state()
        state,_=paper.step(state,quote(),signals=[signal()])
        state,report=paper.step(state,quote(T+60),
                                entry_evidence_ready=False)
        self.assertEqual(state["positions"],[])
        self.assertIn("VIRTUAL_ENTRY_BLOCKED_UNATTESTED_SAFETY_EVIDENCE",
                      report["events"])
        self.assertFalse(report["virtual_entry_evidence_ready"])
        # In offline synthetic research only, verified-test state can still
        # exercise entry and independently approved FLAT after a new quote.
        state=paper.initial_state()
        state,_=paper.step(state,quote(),signals=[signal()])
        state,_=paper.step(state,quote(T+60))
        self.assertEqual(len(state["positions"]),1)
        flat=signal(T+120)
        flat["id"]="f"*64
        flat["action"]="FLAT"
        state,_=paper.step(state,quote(T+120),signals=[flat],
                           entry_evidence_ready=False)
        state,report=paper.step(state,quote(T+180),
                                entry_evidence_ready=False)
        self.assertEqual(state["positions"],[])
        self.assertIn("AI_APPROVED_VIRTUAL_FLAT",report["events"])

    def test_runtime_never_renews_paid_ai_or_opens_entry_from_unattested_calendar(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"paper"
            runtime._initialize(root)
            state=paper.initial_state()
            state["communication_latched"]=True
            state["cycle_number"]=1
            state["last_quote_epoch"]=T-60
            runtime._journal_append(root/"journal",state,"0"*64,"a"*64,NOW)
            with patch.object(runtime,"_latest_quote",return_value=quote()), \
                 patch.object(runtime,"_latest_h1_copy",return_value=Path(temp)), \
                 patch.object(runtime,"_signals_for_new_h1",
                              return_value=([signal()],["USD/JPY:1"],0)) as model:
                report=runtime.run_one_cycle(
                    Path(temp),root,[],allow_paid=True,analyst_model="a",
                    reviewer_model="b",paid_limit=6,now=NOW)
            self.assertFalse(model.call_args.kwargs["allow_paid"])
            self.assertFalse(report["entry_readiness_gate_open"])
            self.assertFalse(report["new_paid_ai_allowed_by_evidence_gate"])
            self.assertFalse(report["virtual_entry_evidence_ready"])
            self.assertFalse(report["broker_orders_sent_this_run"])
            self.assertEqual(report["paid_calls_this_cycle"],0)
            self.assertTrue(report["communication_latched"])
            new_state,_=runtime._journal_load(root/"journal")
            self.assertEqual(new_state["paid_inference_calls"],0)
            self.assertEqual(len(new_state["pending_signals"]),1)
            new_state,entry=paper.step(new_state,quote(T+60),
                                       entry_evidence_ready=False)
            self.assertEqual(new_state["positions"],[])
            self.assertIn("VIRTUAL_ENTRY_BLOCKED_UNATTESTED_SAFETY_EVIDENCE",
                          entry["events"])

    def test_no_unknown_type_bypasses_entry_gate(self):
        state=paper.initial_state()
        with self.assertRaises(Exception):
            paper.step(state,quote(),entry_evidence_ready=1)
        with self.assertRaises(Exception):
            paper.step(state,quote(),entry_evidence_ready=None)


if __name__=="__main__":
    unittest.main()
