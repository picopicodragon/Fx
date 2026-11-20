"""Observed 3-pair spread and broker-PC clock profiling, no trade proof."""
from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_quote_regime_profile as regime
from research.offline_backtest import InputError

UTC=timezone.utc
BASE=datetime(2026,11,20,3,0,tzinfo=UTC)


class QuoteRegimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"MQL4"/"Files"
        self.path.mkdir(parents=True)

    def add(self,dt, *, offset=7200, spread_jpy="0.005",
            spread_eur_jpy="0.010", spread_eur_usd="0.00005"):
        stamp=dt.strftime("%Y%m%d_%H%M%S")
        epoch=int(dt.timestamp())
        target=self.path/f"FxPaperQuote_{stamp}.csv"
        pairs=[
            ("USDJPY","159.500",spread_jpy),
            ("EURJPY","175.200",spread_eur_jpy),
            ("EURUSD","1.10000",spread_eur_usd),
        ]
        with target.open("w",encoding="utf-8",newline="") as out:
            writer=csv.DictWriter(out,fieldnames=paper.QUOTE_FIELDS)
            writer.writeheader()
            for sym,bid,wide in pairs:
                from decimal import Decimal as D
                writer.writerow({
                    "pair":sym,
                    "bid":bid,
                    "ask":str(D(bid)+D(wide)),
                    "tick_time_broker_epoch_unattested":epoch+offset-1,
                    "broker_time_epoch_unattested":epoch+offset,
                    "capture_epoch_utc_pc":epoch,
                    "tickvalue_jpy_broker_reported":"100",
                    "ticksize_broker_reported":"0.001" if sym!="EURUSD" else "0.00001",
                    "min_lot_broker_reported":"0.01",
                    "lot_step_broker_reported":"0.01",
                    "max_lot_broker_reported":"20.00",
                    "point_broker_reported":"0.001" if sym!="EURUSD" else "0.00001",
                })
        return target

    def test_exact_three_pair_real_quotes_profile_not_full_cost_attestation(self):
        for minutes in range(15):
            self.add(BASE+timedelta(minutes=minutes))
        found=regime.summarize(self.path)
        self.assertEqual(found["observed_complete_cycles"],15)
        self.assertEqual(found["quote_interval_min_seconds"],60)
        self.assertEqual(found["quote_interval_max_seconds"],60)
        self.assertEqual(found["quote_intervals_above_90_seconds"],0)
        self.assertEqual(found["unique_utc_hours"],[3])
        self.assertEqual(found["brokertime_minus_pc_capture_seconds_jitter"],0)
        pairs=found["three_pair_spread_and_tick_age"]
        self.assertEqual(pairs["USD/JPY"]["observed_spread_median_pips"],"0.50")
        self.assertEqual(pairs["EUR/JPY"]["observed_spread_max_pips"],"1.00")
        self.assertEqual(pairs["EUR/USD"]["observed_spread_p95_pips"],"0.50")
        self.assertFalse(found["broker_clock_independently_attested"])
        self.assertFalse(found["full_executable_transaction_cost_verified"])
        self.assertFalse(found["new_paid_ai_calls_permitted"])
        self.assertFalse(found["new_virtual_positions_permitted"])

    def test_long_gap_is_research_warning_not_new_go_permission(self):
        self.add(BASE)
        self.add(BASE+timedelta(minutes=15),offset=7260)
        result=regime.summarize(self.path)
        self.assertEqual(result["quote_intervals_above_90_seconds"],1)
        self.assertEqual(result["brokertime_minus_pc_capture_seconds_jitter"],60)
        self.assertFalse(result["new_virtual_positions_permitted"])

    def test_invalid_source_or_conflicting_capture_fails_closed(self):
        self.add(BASE)
        a=self.add(BASE+timedelta(minutes=1))
        with self.assertRaises(InputError):
            regime.summarize(self.path,max_files=1)
        content=a.read_text("utf-8")
        a.write_text(content.replace(str(int((BASE+timedelta(minutes=1)).timestamp())),
                                     str(int(BASE.timestamp()))))
        with self.assertRaises(InputError):
            regime.summarize(self.path)

    def test_no_mutation_or_paid_broker_dispatch(self):
        src=(Path(__file__).resolve().parents[1]/
             "research/final_paper_quote_regime_profile.py").read_text("utf-8")
        for forbidden in (
            "_journal_append(", "OrderSend(", "OrderClose(", "OrderModify(",
            "ai.run(", "OPENAI_API_KEY", "urllib.request",
            "lock.unlink(", "allow_external_api=True",
        ):
            self.assertNotIn(forbidden,src)


if __name__=="__main__":
    unittest.main()
