"""Known official-source events hold virtual entries and paid AI research."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_event_blackout as gate
from research import final_paper_runtime as runtime
from research import final_paper_engine as paper
from research.offline_backtest import InputError

T = 1794963600
NOW = datetime.fromtimestamp(T, tz=timezone.utc)


def calendar(root:Path, when:int, *, currency="USD",
             url="https://www.bls.gov/schedule/news_release/") -> Path:
    file=root/"future_events.json"
    content={
        "schema": gate.SCHEMA,
        "captured_at_utc_pc": datetime.fromtimestamp(
            T-1800,tz=timezone.utc).isoformat(),
        "scope":"OPERATOR_SAVED_RESEARCH_ONLY",
        "events":[{
            "id":"bls-event-1",
            "currency":currency,
            "scheduled_at_utc":datetime.fromtimestamp(
                when,tz=timezone.utc).isoformat(),
            "source_url":url,
            "importance":"HIGH",
        }],
    }
    file.write_text(json.dumps(content),encoding="utf-8")
    return file


def quotes(epoch:int=T)->dict:
    return {"capture_epoch":epoch,"source_sha256":"a"*64,"quotes":{
        pair:{
            "bid":paper.D("159.5"),"ask":paper.D("159.505"),
            "ticksize":paper.D("0.001"),"tickvalue":paper.D("100"),
            "minlot":paper.D("0.01"),"step":paper.D("0.01"),
            "maxlot":paper.D("20"),"point":paper.D(".001")}
        for pair in paper.PAIRS}}


def signal(epoch=T)->dict:
    return {
        "id":"a"*64,"pair":"USD/JPY","action":"LONG",
        "verdict":"APPROVED","reviewed_epoch":epoch,
        "atr14":"0.15","packet_sha256":"b"*64,
    }


class FinalPaperMacroBlackoutTests(unittest.TestCase):
    def test_no_calendar_never_claims_coverage(self):
        result=gate.check(None,T,now=NOW)
        self.assertFalse(result["active_known_blackout"])
        self.assertFalse(result["independent_calendar_coverage_attested"])
        self.assertFalse(result["calendar_supplied"])

    def test_15_min_before_and_after_inclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for diff,expected in ((-901,False),(-900,True),
                                  (0,True),(900,True),(901,False)):
                with self.subTest(diff=diff):
                    file=calendar(folder,T+diff)
                    result=gate.check(file,T,now=NOW)
                    self.assertEqual(result["active_known_blackout"],expected)
                    self.assertFalse(result["independent_calendar_coverage_attested"])

    def test_unofficial_or_stale_event_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            file=calendar(folder,T,url="https://example.com/feed")
            with self.assertRaises(InputError):
                gate.check(file,T,now=NOW)
            file=calendar(folder,T)
            with self.assertRaises(InputError):
                gate.check(file,T,now=datetime.fromtimestamp(
                    T+90000,tz=timezone.utc))

    def test_approved_long_blocked_at_next_quote_but_close_still_works(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes(),signals=[signal()])
        state,report=paper.step(state,quotes(T+60),
                                known_event_blackout=True)
        self.assertEqual(state["positions"],[])
        self.assertIn("VIRTUAL_ENTRY_BLOCKED_KNOWN_MACRO_EVENT",
                      report["events"])
        self.assertEqual(report["broker_orders_sent_this_run"],0)

    def test_runtime_does_not_spend_ai_on_known_blackout(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            root=folder/"paper"
            runtime._initialize(root)
            file=calendar(folder,T)
            with patch.object(runtime,"_latest_quote",return_value=quotes()), \
                 patch.object(runtime,"_latest_h1_copy",return_value=folder), \
                 patch.object(runtime,"_signals_for_new_h1",
                              return_value=([],[],0)) as inferred:
                report=runtime.run_one_cycle(
                    folder,root,[],allow_paid=True,
                    analyst_model="a",reviewer_model="b",
                    paid_limit=6,now=NOW,event_blackout_file=file)
            self.assertFalse(inferred.call_args.kwargs["allow_paid"])
            self.assertTrue(report["known_macro_event_blackout_active"])
            self.assertFalse(report["independent_future_event_calendar_attested"])
            self.assertEqual(report["paid_calls_this_cycle"],0)
            self.assertEqual(report["broker_orders_sent_this_run"],0)

    def test_no_order_or_network_in_blackout_guard(self):
        src=(Path(__file__).resolve().parents[1]/
             "research/final_paper_event_blackout.py").read_text("utf-8")
        for forbidden in ("OrderSend(", "OrderClose(", "urllib.request",
                          "requests.", "TYPESAFE_API_KEY", "OPENAI_API_KEY",
                          "EnableDemoOrders=true"):
            self.assertNotIn(forbidden,src)


if __name__=="__main__":
    unittest.main()
