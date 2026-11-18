"""Fully synthetic E2E final-paper risk gates; no MT4 order path."""
from __future__ import annotations

import unittest
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as paper

T=1794963600


def quote(epoch=T,offset=D("0")):
    return {"capture_epoch":epoch,"quotes":{
        "USD/JPY":{
            "bid":D("159.500")+offset,"ask":D("159.505")+offset,
            "tickvalue":D("100"),"ticksize":D(".001"),
            "minlot":D(".01"),"step":D(".01"),"maxlot":D("20"),
            "point":D(".001")},
        "EUR/JPY":{
            "bid":D("175.200")+offset,"ask":D("175.210")+offset,
            "tickvalue":D("100"),"ticksize":D(".001"),
            "minlot":D(".01"),"step":D(".01"),"maxlot":D("20"),
            "point":D(".001")},
        "EUR/USD":{
            "bid":D("1.10000"),"ask":D("1.10005"),
            "tickvalue":D("155"),"ticksize":D(".00001"),
            "minlot":D(".01"),"step":D(".01"),"maxlot":D("20"),
            "point":D(".00001")},
    }}


def signal(pair,ident,epoch=T,action="LONG",verdict="APPROVED"):
    return {
        "id":ident*64,"pair":pair,"action":action,
        "verdict":verdict,"reviewed_epoch":epoch,
        "atr14":"0.15" if pair.endswith("JPY") else "0.0015",
        "packet_sha256":"d"*64,
    }


class FinalPaperSyntheticSafetyCampaign(unittest.TestCase):
    def test_two_pairs_risk_and_drawdown_hard_latch(self):
        state=paper.initial_state()
        state,out=paper.step(state,quote(),signals=[
            signal("USD/JPY","a"),signal("EUR/JPY","b")])
        self.assertEqual(len(state["pending_signals"]),2)
        self.assertEqual(len(state["positions"]),0)
        state,out=paper.step(state,quote(T+60))
        self.assertEqual(len(state["positions"]),2)
        self.assertEqual(out["broker_orders_sent_this_run"],0)
        for pos in state["positions"]:
            self.assertLessEqual(D(pos["risk_jpy"]),D("500"))
        self.assertLessEqual(sum((D(pos["risk_jpy"])
                                for pos in state["positions"]),D("0")),
                             D("1000"))
        # Only an offline synthetic example: force DD hard stop to test
        # mechanical close-all; never manipulate live paper state like this.
        state["peak_equity_jpy"]="120000.00"
        state,out=paper.step(state,quote(T+120))
        self.assertTrue(state["dd4_latched"])
        self.assertTrue(state["dd5_latched"])
        self.assertEqual(len(state["positions"]),0)
        self.assertEqual(out["simulated_closed_trade_count"],2)
        self.assertFalse(out["real_orders_permitted"])

    def test_event_window_blocks_entry_and_not_pending_synthetic_flat_exit(self):
        state=paper.initial_state()
        state,_=paper.step(state,quote(),signals=[
            signal("USD/JPY","a")])
        state,out=paper.step(state,quote(T+60),
                             known_event_blackout=True,
                             entry_evidence_ready=True)
        self.assertEqual(len(state["positions"]),0)
        self.assertIn("VIRTUAL_ENTRY_BLOCKED_KNOWN_MACRO_EVENT",out["events"])
        self.assertEqual(out["broker_orders_sent_this_run"],0)

    def test_manual_stop_gap_then_fresh_quote_does_not_unlatch(self):
        state=paper.initial_state()
        state,_=paper.step(state,quote())
        state,out=paper.step(state,quote(T+3420),
                             entry_evidence_ready=False)
        self.assertTrue(state["communication_latched"])
        self.assertIn("VIRTUAL_COMMUNICATION_LEVEL2_LATCHED",out["events"])
        state,out=paper.step(state,quote(T+3480),
                             entry_evidence_ready=False)
        self.assertTrue(state["communication_latched"])
        self.assertFalse(out["virtual_entry_evidence_ready"])
        self.assertEqual(out["broker_orders_sent_this_run"],0)

    def test_approved_signal_with_unattested_calendar_never_opens(self):
        state=paper.initial_state()
        state,_=paper.step(state,quote(),signals=[
            signal("USD/JPY","a")],entry_evidence_ready=False)
        state,out=paper.step(state,quote(T+60),
                             entry_evidence_ready=False)
        self.assertEqual(state["positions"],[])
        self.assertIn("VIRTUAL_ENTRY_BLOCKED_UNATTESTED_SAFETY_EVIDENCE",
                      out["events"])

    def test_broker_order_api_absent_from_engine(self):
        source=(Path(__file__).resolve().parents[1]/
                "research/final_paper_engine.py").read_text("utf-8")
        for token in ("OrderSend(", "OrderModify(", "OrderClose(",
                      "WebRequest(", "OPENAI_API_KEY", "api.typesafe.ai"):
            self.assertNotIn(token,source)


if __name__=="__main__":
    unittest.main()
