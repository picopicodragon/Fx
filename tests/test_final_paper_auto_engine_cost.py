"""Virtual FX engine: 14-day max hold and pessimistic NY17 carrying cost."""
from __future__ import annotations

import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D

from research import final_paper_engine as paper
from research.offline_backtest import InputError

BASE=datetime(2026,11,20,21,58,0,tzinfo=timezone.utc)
CARRY={pair:{"LONG":"10","SHORT":"10"} for pair in paper.PAIRS}


def quote(moment:datetime)->dict:
    return {
        "capture_epoch":int(moment.timestamp()),
        "source_sha256":"a"*64,
        "quotes":{
            pair:{
                "bid":D("159.500") if pair=="USD/JPY" else
                      D("175.200") if pair=="EUR/JPY" else D("1.10000"),
                "ask":D("159.505") if pair=="USD/JPY" else
                      D("175.210") if pair=="EUR/JPY" else D("1.10005"),
                "tickvalue":D("100"),"ticksize":D(".00001")
                if pair=="EUR/USD" else D(".001"),
                "minlot":D(".01"),"maxlot":D("20"),
                "step":D(".01"),"point":D(".00001")
                if pair=="EUR/USD" else D(".001"),
            } for pair in paper.PAIRS
        },
    }


def signal(moment:datetime)->dict:
    return {
        "id":"e"*64,"pair":"USD/JPY",
        "action":"LONG","verdict":"APPROVED",
        "reviewed_epoch":int(moment.timestamp()),
        "atr14":"0.10","packet_sha256":"f"*64,
    }


class FinalAutoCarryingRiskTests(unittest.TestCase):
    def _opened(self):
        state=paper.initial_state()
        state,_=paper.step(state,quote(BASE))
        review=BASE+timedelta(minutes=1,seconds=1)
        state,_=paper.step(
            state,quote(BASE+timedelta(minutes=1)),
            signals=[signal(review)],carry_costs=CARRY,
            entry_evidence_ready=True)
        self.assertEqual(state["positions"],[])
        self.assertEqual(len(state["pending_signals"]),1)
        state,report=paper.step(
            state,quote(BASE+timedelta(minutes=1,seconds=30)),
            carry_costs=CARRY,entry_evidence_ready=True)
        self.assertIn("VIRTUAL_POSITION_OPENED",report["events"])
        self.assertEqual(len(state["positions"]),1)
        self.assertLessEqual(D(state["positions"][0]["risk_jpy"]),
                             D("500.00"))
        return state

    def test_next_real_quote_only_then_ny17_daily_carry_deducted(self):
        state=self._opened()
        previous_cash=D(state["cash_jpy"])
        following=BASE+timedelta(minutes=4)
        state,report=paper.step(state,quote(following),
                                carry_costs=CARRY,
                                entry_evidence_ready=True)
        self.assertIn("AUTO_PAPER_CONSERVATIVE_NY17_CARRY_CHARGED",
                      report["events"])
        self.assertEqual(D(state["cash_jpy"]),
                         previous_cash-D("10")*
                         D(state["positions"][0]["lots"]))
        self.assertGreater(D(state["auto_carry_charged_jpy"]),0)
        self.assertFalse(report["demo_broker_orders_permitted"])
        self.assertFalse(report["real_orders_permitted"])

    def test_position_cannot_outlive_reserved_14_day_swap_horizon(self):
        state=self._opened()
        after=BASE+timedelta(days=14,minutes=2)
        state,report=paper.step(state,quote(after),
                                carry_costs=CARRY,
                                entry_evidence_ready=False)
        self.assertEqual(state["positions"],[])
        self.assertIn("FINAL_AUTO_MAX_14_DAY_HOLD",report["events"])
        self.assertEqual(state["trade_log"][-1]["reason"],
                         "FINAL_AUTO_MAX_14_DAY_HOLD")
        self.assertTrue(state["communication_latched"])
        self.assertEqual(report["broker_orders_sent_this_run"],0)

    def test_invalid_carry_risk_model_cannot_open_trade(self):
        state=paper.initial_state()
        for invalid in (
            {},{"USD/JPY":{"LONG":"0","SHORT":"10"}},
            {pair:{"LONG":"-10","SHORT":"10"} for pair in paper.PAIRS},
            {pair:{"LONG":"100001","SHORT":"10"} for pair in paper.PAIRS},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises((InputError,KeyError)):
                    paper.step(state,quote(BASE),carry_costs=invalid)

    def test_legacy_engine_behavior_remains_unchanged(self):
        state=paper.initial_state()
        new,out=paper.step(state,quote(BASE))
        self.assertEqual(new["positions"],[])
        self.assertNotIn("auto_carry_charged_jpy",new)
        self.assertEqual(out["broker_orders_sent_this_run"],0)


if __name__=="__main__":
    unittest.main()
