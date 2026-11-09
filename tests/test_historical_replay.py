"""Historical H1 replay tests: synthetic bid/ask inputs, no network/orders."""
from __future__ import annotations

import csv
import io
import tempfile
import unittest
from pathlib import Path

from research import historical_replay as hist
from research.offline_backtest import InputError


def make_csv(pair: str, side: str, *, count: int = 55,
             crossed: bool = False, missing: set[int] = frozenset(),
             change_last: bool = False) -> str:
    base = {"usdjpy": 150.0, "eurjpy": 160.0, "eurusd": 1.08}[pair]
    tick = 0.01 if pair.endswith("jpy") else 0.0001
    result = io.StringIO()
    writer = csv.writer(result, lineterminator="\n")
    writer.writerow(hist.REQUIRED)
    for i in range(count):
        if i in missing:
            continue
        # Trend flips after 30 to exercise SMA cross.
        drift = i if i < 30 else 60 - i
        value = base + drift * tick * 2
        if change_last and i == count - 1:
            value += tick * 80
        if side == "ask":
            value += tick
        if crossed and i == 10 and side == "ask":
            value -= tick * 5
        t = 1735689600000 + i * hist.INTERVAL_MS
        writer.writerow([t, format(value, ".6f"),
                         format(value + 3*tick, ".6f"),
                         format(value - 3*tick, ".6f"),
                         format(value, ".6f")])
    return result.getvalue()


class HistoryReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {}
        for symbol in hist.SYMBOLS:
            paths = []
            for side in ("bid", "ask"):
                p = self.root / (symbol + "-" + side + ".csv")
                p.write_text(make_csv(symbol, side), encoding="utf-8")
                paths.append(p)
            self.files[symbol] = tuple(paths)

    def replace_file(self, symbol, side, value):
        side_index = 0 if side == "bid" else 1
        self.files[symbol][side_index].write_text(value, encoding="utf-8")

    def test_h1_three_pair_replay_returns_no_go(self):
        out = hist.run(self.files)
        self.assertEqual(out["status"], "RESEARCH_ONLY_NO_GO")
        self.assertEqual(out["runtime_go_no_go"], "NO_GO")
        self.assertTrue(out["safety_hold_latched"])
        self.assertFalse(out["real_order_execution_authorized"])
        self.assertEqual(out["historical_research"]["aligned_bars_per_pair"], 54)
        self.assertEqual(out["historical_research"]["timestamps_removed_to_align"], 0)
        self.assertEqual(out["historical_research"]["strategy"],
                         "RESEARCH_SMA_CROSSOVER_NOT_AI_MACRO_STRATEGY")
        self.assertEqual(len(out["historical_research"]["input_checksums"]), 6)

    def test_deterministic_replay_and_no_order_side_effect(self):
        first = hist.run(self.files)
        self.assertEqual(first, hist.run(self.files))
        self.assertNotIn("broker_account", str(first))
        self.assertEqual(first["human_p05_signoff"], False)

    def test_lagged_conversion_only_uses_previous_timestamp(self):
        bars, _ = hist.prepare(self.files)
        usdjpy0 = hist.load_side(self.files["usdjpy"][0])[0][1735689600000]
        usdjpyask0 = hist.load_side(self.files["usdjpy"][1])[0][1735689600000]
        expected = (usdjpy0["close"] + usdjpyask0["close"]) / 2
        eurusd_first = next(b for b in bars if b.pair == "EUR/USD")
        self.assertEqual(eurusd_first.quote_to_jpy, expected)

    def test_bar_uses_open_close_spread_bid_ask(self):
        bars, meta = hist.prepare(self.files)
        first = next(b for b in bars if b.pair == "USD/JPY")
        self.assertEqual(first.spread, 1)
        self.assertEqual(meta["fill_model"],
                         "actual_bid_ask_OHLC_stop_first_ambiguous")
        self.assertIsNotNone(first.bid)
        self.assertIsNotNone(first.ask)
        self.assertLess(first.bid[0], first.ask[0])

    def test_sma_has_no_future_close_in_earlier_signal(self):
        before, _ = hist.prepare(self.files)
        self.replace_file("eurjpy", "bid",
                          make_csv("eurjpy", "bid", change_last=True))
        self.replace_file("eurjpy", "ask",
                          make_csv("eurjpy", "ask", change_last=True))
        after, _ = hist.prepare(self.files)
        self.assertEqual([(b.time, b.signal) for b in before
                          if b.pair == "EUR/JPY"][:-1],
                         [(b.time, b.signal) for b in after
                          if b.pair == "EUR/JPY"][:-1])

    def test_single_missing_pair_bar_disclosed(self):
        self.replace_file("eurjpy", "bid",
                          make_csv("eurjpy", "bid", missing={15}))
        self.replace_file("eurjpy", "ask",
                          make_csv("eurjpy", "ask", missing={15}))
        bars, meta = hist.prepare(self.files)
        self.assertEqual(meta["timestamps_removed_to_align"], 1)
        self.assertEqual(meta["aligned_bars_per_pair"], 53)
        self.assertTrue(all(b.time.hour != 15 or b.time.day != 1
                            for b in bars))

    def test_many_missing_bars_fail_closed(self):
        self.replace_file("eurjpy", "bid",
                          make_csv("eurjpy", "bid", missing=set(range(15, 20))))
        self.replace_file("eurjpy", "ask",
                          make_csv("eurjpy", "ask", missing=set(range(15, 20))))
        with self.assertRaises(InputError):
            hist.prepare(self.files)

    def test_crossed_spread_rejected(self):
        self.replace_file("usdjpy", "ask",
                          make_csv("usdjpy", "ask", crossed=True))
        with self.assertRaises(InputError):
            hist.prepare(self.files)

    def test_source_side_cannot_be_reused(self):
        self.files["eurusd"] = (self.files["eurusd"][0],
                               self.files["eurusd"][0])
        with self.assertRaises(InputError):
            hist.prepare(self.files)

    def test_short_history_rejected(self):
        self.replace_file("eurjpy", "bid",
                          make_csv("eurjpy", "bid", count=20))
        with self.assertRaises(InputError):
            hist.prepare(self.files)

    def test_unsupported_schema_rejected(self):
        self.replace_file("eurusd", "bid", "date,open,high,low,close\n")
        with self.assertRaises(InputError):
            hist.prepare(self.files)

    def test_unordered_history_rejected(self):
        value = make_csv("usdjpy", "bid").splitlines()
        value[2], value[3] = value[3], value[2]
        self.replace_file("usdjpy", "bid", "\n".join(value) + "\n")
        with self.assertRaises(InputError):
            hist.prepare(self.files)

    def test_wrong_timestamp_unit_rejected(self):
        value = make_csv("usdjpy", "bid").replace(
            "1735689600000", "1735689600")
        self.replace_file("usdjpy", "bid", value)
        with self.assertRaises(InputError):
            hist.prepare(self.files)

    def test_bad_windows_rejected(self):
        for fast, slow in ((1, 30), (30, 30), (40, 20), (10, 501)):
            with self.subTest(fast=fast, slow=slow), self.assertRaises(InputError):
                hist.prepare(self.files, fast=fast, slow=slow)

    def test_input_paths_not_echoed_on_cli_error(self):
        stdout = io.StringIO()
        from contextlib import redirect_stdout
        with redirect_stdout(stdout):
            result = hist.main([
                "--usdjpy-bid", "SECRET_CANARY_2026.csv",
                "--usdjpy-ask", str(self.files["usdjpy"][1]),
                "--eurjpy-bid", str(self.files["eurjpy"][0]),
                "--eurjpy-ask", str(self.files["eurjpy"][1]),
                "--eurusd-bid", str(self.files["eurusd"][0]),
                "--eurusd-ask", str(self.files["eurusd"][1])])
        self.assertEqual(result, 2)
        self.assertIn("FAIL_CLOSED", stdout.getvalue())
        self.assertNotIn("SECRET_CANARY_2026", stdout.getvalue())

    def test_weekend_market_new_york_dstu(self):
        from datetime import datetime, timezone
        def stamp(x):
            return int(datetime.fromisoformat(x).replace(
                tzinfo=timezone.utc).timestamp() * 1000)
        self.assertTrue(hist.market_open(stamp("2025-01-03T21:00:00")))
        self.assertFalse(hist.market_open(stamp("2025-01-03T22:00:00")))
        self.assertFalse(hist.market_open(stamp("2025-01-05T21:00:00")))
        self.assertTrue(hist.market_open(stamp("2025-01-05T22:00:00")))
        self.assertTrue(hist.market_open(stamp("2025-07-04T20:00:00")))
        self.assertFalse(hist.market_open(stamp("2025-07-04T21:00:00")))
        self.assertFalse(hist.market_open(stamp("2025-07-06T20:00:00")))
        self.assertTrue(hist.market_open(stamp("2025-07-06T21:00:00")))

    def test_synthetic_weekend_provider_candles_are_removed(self):
        for symbol in hist.SYMBOLS:
            for side in ("bid", "ask"):
                self.replace_file(symbol, side, make_csv(symbol, side, count=110))
        bars, meta = hist.prepare(self.files)
        self.assertEqual(
            meta["weekend_candles_removed_by_pair_and_side"]["usdjpy"]["bid"], 40)
        self.assertTrue(all(hist.market_open(int(b.time.timestamp() * 1000))
                            for b in bars))
        self.assertEqual(meta["special_holidays_verified"], False)
        self.assertEqual(meta["weekly_session_rule"],
                         "Sun17_to_Fri17_America/New_York_DST")

    def test_historical_bid_ask_fields_consistent(self):
        bars, _ = hist.prepare(self.files)
        for b in bars[:20]:
            self.assertEqual(b.open, (b.bid[0] + b.ask[0]) / 2)
            self.assertEqual(b.high, (b.bid[1] + b.ask[1]) / 2)
            self.assertEqual(b.low, (b.bid[2] + b.ask[2]) / 2)
            self.assertEqual(b.close, (b.bid[3] + b.ask[3]) / 2)



if __name__ == "__main__":
    unittest.main()
