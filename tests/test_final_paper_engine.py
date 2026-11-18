"""FINAL-PAPER: paper risk, next-quote fills and DEMO no-order contract."""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_engine as paper
from research.offline_backtest import InputError

T=1794963600


def quotes(epoch=T,bid="159.500",ask="159.505"):
    specs=[("USD/JPY",bid,ask,"100",".001"),
           ("EUR/JPY","175.220","175.230","100",".001"),
           ("EUR/USD","1.09854","1.09859","159.5",".00001")]
    return {
        "capture_epoch":epoch,
        "quotes":{pair:{
            "bid":paper.D(b),"ask":paper.D(a),
            "tickvalue":paper.D(tv),"ticksize":paper.D(tick),
            "minlot":paper.D(".01"),"step":paper.D(".01"),
            "maxlot":paper.D("20"),"point":paper.D(tick)}
            for pair,b,a,tv,tick in specs}}


def signal(epoch=T,action="LONG",pair="USD/JPY",uid="a"*64):
    return {"id":uid,"pair":pair,"action":action,
            "verdict":"APPROVED","reviewed_epoch":epoch,
            "atr14":"0.15" if pair.endswith("JPY") else "0.001",
            "packet_sha256":"b"*64}


class FinalPaperEngineTests(unittest.TestCase):
    def test_no_same_quote_lookahead_then_virtual_open_and_stop(self):
        state=paper.initial_state()
        state,report=paper.step(state,quotes(),signals=[signal()])
        self.assertEqual(len(state["positions"]),0)
        self.assertEqual(len(state["pending_signals"]),1)
        self.assertEqual(report["broker_orders_sent_this_run"],0)
        state,report=paper.step(state,quotes(T+60))
        self.assertEqual(len(state["positions"]),1)
        self.assertEqual(report["virtual_position_count"],1)
        self.assertEqual(state["start_capital_jpy"],"100000.00")
        self.assertLessEqual(paper.D(state["positions"][0]["risk_jpy"]),
                             paper.D("500"))
        state,report=paper.step(state,quotes(T+120,bid="158.200",ask="158.205"))
        self.assertEqual(len(state["positions"]),0)
        self.assertEqual(report["simulated_closed_trade_count"],1)
        self.assertEqual(state["trade_log"][0]["reason"],"VIRTUAL_STOP")
        self.assertEqual(report["real_orders_permitted"],False)

    def test_approved_hold_never_creates_paper_position(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes(),signals=[
            signal(action="HOLD")])
        state,report=paper.step(state,quotes(T+60))
        self.assertEqual(state["positions"],[])
        self.assertIn("AI_HOLD_OR_NONAPPROVED_NO_POSITION",
                      report["events"])

    def test_approved_flat_closes_only_matching_virtual_pair_next_quote(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes(),signals=[signal()])
        state,_=paper.step(state,quotes(T+60))
        self.assertEqual(len(state["positions"]),1)
        state,_=paper.step(state,quotes(T+120),
                           signals=[signal(epoch=T+120,action="FLAT",
                                           uid="f"*64)])
        self.assertEqual(len(state["positions"]),1)
        state,report=paper.step(state,quotes(T+180))
        self.assertEqual(len(state["positions"]),0)
        self.assertEqual(report["broker_orders_sent_this_run"],0)
        self.assertEqual(state["trade_log"][-1]["reason"],
                         "AI_APPROVED_VIRTUAL_FLAT")

    def test_nonapproved_flat_does_not_force_close(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes(),signals=[signal()])
        state,_=paper.step(state,quotes(T+60))
        s=signal(epoch=T+120,action="FLAT",uid="f"*64)
        s["verdict"]="REJECTED"
        state,_=paper.step(state,quotes(T+120),signals=[s])
        state,_=paper.step(state,quotes(T+180))
        self.assertEqual(len(state["positions"]),1)

    def test_cross_pair_broker_clock_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"FxPaperQuote_20261118_010000.csv"
            with path.open("w",newline="",encoding="utf-8") as out:
                writer=csv.writer(out)
                writer.writerow(paper.QUOTE_FIELDS)
                for j,sym in enumerate(paper.SYMS):
                    writer.writerow([sym,"159.5","159.505",T,T+j,T,
                                      "100",".001",".01",".01","20",".001"])
            with self.assertRaises(InputError):
                paper.validate_quotes(
                    path,now=datetime.fromtimestamp(T+10,tz=timezone.utc))

    def test_nonapproved_signal_does_not_trade(self):
        state=paper.initial_state()
        sig=signal()
        sig["verdict"]="PENDING"
        state,_=paper.step(state,quotes(),signals=[sig])
        state,_=paper.step(state,quotes(T+60))
        self.assertEqual(state["positions"],[])

    def test_dd4_halt_blocks_entries_and_dd5_latches(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes(),signals=[signal()])
        state,_=paper.step(state,quotes(T+60))
        state,report=paper.step(state,quotes(T+120,bid="153.000",ask="153.005"))
        # With a 0.01 lot at 0.3 JPY risk, loss is finite; no artificial
        # global drawdown should be fabricated from one bounded trade.
        self.assertLess(paper.D(report["virtual_equity_jpy"]),
                        paper.D("100000"))
        state["peak_equity_jpy"]="110000.00"
        state,report=paper.step(state,quotes(T+180),signals=[signal(
            epoch=T+180,uid="c"*64)])
        self.assertTrue(state["dd5_latched"])
        self.assertEqual(len(state["positions"]),0)

    def test_communication_gap_latches_without_broker_order(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes())
        state,report=paper.step(state,quotes(T+601))
        self.assertTrue(state["communication_latched"])
        self.assertIn("VIRTUAL_COMMUNICATION_LEVEL2_LATCHED",report["events"])
        self.assertFalse(report["demo_broker_orders_permitted"])

    def test_risk_latches_do_not_reset_after_ny17(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes())
        state["dd4_latched"]=True
        state["dd5_latched"]=True
        state,report=paper.step(state,quotes(T+86400))
        self.assertTrue(state["dd4_latched"])
        self.assertTrue(state["dd5_latched"])
        self.assertEqual(state["positions"],[])

    def test_repeated_quote_or_signal_fails_closed(self):
        state=paper.initial_state()
        state,_=paper.step(state,quotes(),signals=[signal()])
        with self.assertRaises(InputError):
            paper.step(state,quotes())
        with self.assertRaises(InputError):
            paper.step(state,quotes(T+60),signals=[signal()])

    def test_real_three_pair_quote_csv_validates_and_redacts_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/"FxPaperQuote_20261118_010000.csv"
            at=1794963600
            with path.open("w",encoding="utf-8",newline="") as out:
                writer=csv.writer(out)
                writer.writerow(paper.QUOTE_FIELDS)
                for sym,bid,ask,tickvalue,ticksize in (
                        ("USDJPY","159.5","159.505","100",".001"),
                        ("EURJPY","175.22","175.23","100",".001"),
                        ("EURUSD","1.09854","1.09859","159.5",".00001")):
                    writer.writerow([sym,bid,ask,at,at,at,tickvalue,
                                      ticksize,".01",".01","20",ticksize])
            data=paper.validate_quotes(
                path,now=datetime.fromtimestamp(at+10,tz=timezone.utc))
            self.assertEqual(data["capture_epoch"],at)
            self.assertEqual(set(data["quotes"]),set(paper.PAIRS))
            self.assertEqual(len(data["source_sha256"]),64)
            with self.assertRaises(InputError):
                paper.validate_quotes(
                    path,now=datetime.fromtimestamp(at+200,tz=timezone.utc))

    def test_source_boundaries_no_network_and_no_order(self):
        base=Path(__file__).resolve().parents[1]
        for path in ("research/final_paper_engine.py",
                     "mt4/read_only/FxFinalPaperReadOnlyObserver.mq4"):
            data=(base/path).read_text(encoding="utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                              "OrderDelete(", "WebRequest(", "#import ",
                              "FILE_COMMON", "EnableDemoOrders = true"):
                self.assertNotIn(forbidden,data)
        self.assertNotIn("jev",json.dumps(paper.initial_state()).replace(
            '"jev_required": false',""))


if __name__=="__main__":
    unittest.main()
