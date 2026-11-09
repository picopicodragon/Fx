"""Backtest mechanics and no-live-permission boundary, synthetic inputs only."""
from __future__ import annotations

import contextlib
import csv
import io
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

from research import offline_backtest as bt


def row(t, pair="USD/JPY", o="150", h="150.1", l="149.9", c="150",
        signal="HOLD", spread="0", quote="1"):
    return [f"2026-10-05T{t:02d}:00:00Z", pair, o, h, l, c,
            spread, quote, signal]


def csv_text(rows):
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(bt.COLUMNS)
    writer.writerows(rows)
    return text.getvalue()


class InputTests(unittest.TestCase):
    def test_strict_input_header(self):
        self.assertEqual(len(bt.parse_csv(csv_text([row(0)]))), 1)
        with self.assertRaises(bt.InputError):
            bt.parse_csv("time_utc,pair,open\n")

    def test_utc_timezone_strict(self):
        for value in ("2026-10-05T00:00:00+09:00", "2026-10-05", "invalid"):
            bad = row(0)
            bad[0] = value
            with self.subTest(value=value), self.assertRaises(bt.InputError):
                bt.parse_csv(csv_text([bad]))

    def test_nonfinite_and_ohlc_invalid(self):
        for key, value in ((2, "NaN"), (5, "Infinity"), (3, "149"),
                           (4, "151"), (6, "-1"), (7, "0")):
            bad = row(0)
            bad[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(bt.InputError):
                bt.parse_csv(csv_text([bad]))

    def test_unknown_pair_duplicate_and_time_grid(self):
        with self.assertRaises(bt.InputError):
            bt.parse_csv(csv_text([row(0, pair="GBP/USD")]))
        with self.assertRaises(bt.InputError):
            bt.parse_csv(csv_text([row(0), row(0)]))
        with self.assertRaises(bt.InputError):
            bt.parse_csv(csv_text([row(0), row(1, pair="EUR/JPY")]))

    def test_eurusd_conversion_required_without_inference(self):
        eu = row(0, "EUR/USD", "1.08", "1.09", "1.07", "1.08",
                 quote="150")
        self.assertEqual(bt.parse_csv(csv_text([eu]))[0].quote_to_jpy, D("150"))
        with self.assertRaises(bt.InputError):
            bt.parse_csv(csv_text([row(0, quote="150")]))
        with self.assertRaises(bt.InputError):
            bt.parse_csv(csv_text([row(0, signal="BUY")]))

    def test_direct_bar_rejects_nonfinite_quote(self):
        bars = bt.parse_csv(csv_text([row(0), row(1)]))
        bars[0] = replace(bars[0], spread=D("NaN"))
        with self.assertRaises(bt.InputError):
            bt.simulate(bars)


class SimulationTests(unittest.TestCase):
    def run_rows(self, rows, **kw):
        return bt.simulate(bt.parse_csv(csv_text(rows)), **kw)

    def test_no_signals_and_forced_no_go(self):
        out = self.run_rows([row(0), row(1)])
        self.assertEqual(out["trade_count"], 0)
        self.assertEqual(out["ending_jpy"], "100000")
        self.assertEqual(out["runtime_go_no_go"], "NO_GO")
        self.assertIs(out["safety_hold_latched"], True)
        self.assertIs(out["real_mt4_read_authorized"], False)
        self.assertIs(out["real_order_execution_authorized"], False)
        self.assertIs(out["human_p05_signoff"], False)

    def test_next_bar_long_target_profit_and_stop_first(self):
        winning = self.run_rows([
            row(0, signal="LONG"),
            row(1, o="150", h="150.5", l="150", c="150.3")])
        self.assertEqual(winning["trades"][0]["reason"], "TARGET")
        self.assertEqual(winning["trades"][0]["units"], 2000)
        self.assertEqual(D(winning["net_pnl_jpy"]), D("800"))
        both = self.run_rows([
            row(0, signal="LONG"),
            row(1, o="150", h="150.5", l="149.5", c="150")])
        self.assertEqual(both["trades"][0]["reason"], "STOP")
        self.assertEqual(D(both["net_pnl_jpy"]), D("-400"))

    def test_short_target(self):
        result = self.run_rows([
            row(0, signal="SHORT"),
            row(1, o="150", h="150", l="149.5", c="149.6")])
        self.assertEqual(result["trades"][0]["reason"], "TARGET")
        self.assertEqual(D(result["net_pnl_jpy"]), D("800"))

    def test_current_final_signal_never_trades(self):
        out = self.run_rows([row(0), row(1, signal="LONG")])
        self.assertEqual(out["trade_count"], 0)

    def test_stop_gap_cannot_be_presented_as_budget_compliance(self):
        out = self.run_rows([
            row(0, signal="LONG"),
            row(1, o="150", h="150.1", l="149.99", c="150"),
            row(2, o="149", h="149.1", l="148.8", c="149")])
        self.assertEqual(out["trades"][0]["reason"], "STOP_GAP")
        self.assertGreater(out["gap_risk_budget_breaches"], 0)
        self.assertLess(D(out["net_pnl_jpy"]), D("-500"))

    def test_eurusd_roundtrip_jpy_conversion(self):
        rows = [row(0, "EUR/USD", "1.08", "1.081", "1.079", "1.08",
                    "LONG", "0", "150"),
                row(1, "EUR/USD", "1.08", "1.09", "1.08", "1.085",
                    "HOLD", "0", "150")]
        out = self.run_rows(rows)
        self.assertEqual(out["trades"][0]["units"], 1000)
        self.assertEqual(D(out["net_pnl_jpy"]), D("600"))

    def test_three_pairs_maximum_aggregate(self):
        rows = []
        for t in (0, 1, 2):
            signal = "LONG" if t == 0 else "HOLD"
            rows.extend([
                row(t, "USD/JPY", signal=signal),
                row(t, "EUR/JPY", "160", "160.01", "159.99", "160",
                    signal),
                row(t, "EUR/USD", "1.08", "1.0801", "1.0799", "1.08",
                    signal, "0", "150")])
        out = self.run_rows(rows)
        self.assertGreaterEqual(out["trade_count"], 2)
        self.assertLessEqual(out["max_open_positions"], 3)
        self.assertEqual(out["runtime_go_no_go"], "NO_GO")

    def test_commissions_lower_result(self):
        rows = [row(0, signal="LONG"),
                row(1, o="150", h="150.5", l="150", c="150.3")]
        free = self.run_rows(rows)
        paid = self.run_rows(rows, commission_jpy_per_1000_roundtrip="50")
        self.assertLess(D(paid["net_pnl_jpy"]), D(free["net_pnl_jpy"]))

    def test_daily_loss_halts_additional_signals(self):
        rows = [row(0, signal="LONG")]
        rows.extend(row(t, o="150", h="150.01", l="149.7",
                        c="150", signal="LONG") for t in range(1, 10))
        out = self.run_rows(rows)
        self.assertIs(out["daily_stop_last_day"], True)
        self.assertGreater(out["signals_rejected"], 0)

    def test_spread_or_min_lot_prevents_entry(self):
        for kw, rows in (
                ({}, [row(0, signal="LONG"), row(1, spread="25")]),
                ({"min_units": 5000}, [row(0, signal="LONG"), row(1)])):
            out = self.run_rows(rows, **kw)
            self.assertEqual(out["trade_count"], 0)
            self.assertGreater(out["signals_rejected"], 0)

    def test_last_position_closed_at_data_end(self):
        out = self.run_rows([row(0, signal="LONG"), row(1)])
        self.assertEqual(out["trade_count"], 1)
        self.assertEqual(out["trades"][0]["reason"], "END_OF_DATA")

    def test_new_york_17_dst(self):
        before = datetime(2026, 7, 1, 20, 59, tzinfo=timezone.utc)
        after = datetime(2026, 7, 1, 21, 0, tzinfo=timezone.utc)
        winter_before = datetime(2026, 1, 1, 21, 59, tzinfo=timezone.utc)
        winter_after = datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc)
        self.assertNotEqual(bt.session_day(before), bt.session_day(after))
        self.assertNotEqual(bt.session_day(winter_before), bt.session_day(winter_after))

    def test_invalid_parameters_and_lot_step(self):
        bars = bt.parse_csv(csv_text([row(0)]))
        for kw in ({"lot_step_units": 0}, {"min_units": 1500},
                   {"starting_jpy": "NaN"}, {"stop_pips": "0"},
                   {"reward_r": "Infinity"}):
            with self.subTest(kw=kw), self.assertRaises(bt.InputError):
                bt.simulate(bars, **kw)

    def test_cli_failure_never_echoes_private_path(self):
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink):
            code = bt.main(["--csv", "PRIVATE_CANARY_NO_FILE.csv"])
        self.assertEqual(code, 2)
        self.assertIn('"FAIL_CLOSED"', sink.getvalue())
        self.assertNotIn("PRIVATE_CANARY", sink.getvalue())

    def test_three_pair_synthetic_example_deterministic(self):
        fixture = (Path(__file__).resolve().parents[1] /
                   "research/fixtures/synthetic_three_pair_bars.csv")
        bars = bt.parse_csv(fixture.read_text(encoding="utf-8"))
        output = bt.simulate(bars)
        self.assertEqual(output, bt.simulate(bars))
        self.assertEqual(output["trade_count"], 4)
        self.assertEqual(D(output["net_pnl_jpy"]), D("2740"))
        self.assertEqual(output["runtime_go_no_go"], "NO_GO")


    def test_true_bid_low_triggers_stop_when_mid_proxy_would_not(self):
        t0 = datetime(2025, 1, 7, 0, tzinfo=timezone.utc)
        t1 = datetime(2025, 1, 7, 1, tzinfo=timezone.utc)
        first = bt.Bar(t0, "USD/JPY", D("150"), D("150.1"),
                       D("149.9"), D("150"), D("1"), D("1"), "LONG")
        # Mid low 149.85 minus proxy half spread .005 = 149.845.
        # Actual executable BID low is 149.79, beneath the 149.81 stop.
        second = bt.Bar(t1, "USD/JPY", D("150.005"), D("150.1"),
                        D("149.85"), D("150.005"), D("1"), D("1"), "HOLD",
                        (D("150"), D("150.09"), D("149.79"), D("150")),
                        (D("150.01"), D("150.11"), D("149.91"), D("150.01")))
        report = bt.simulate([first, second])
        self.assertEqual(report["trades"][0]["reason"], "STOP")
        self.assertEqual(D(report["net_pnl_jpy"]), D("-400"))

    def test_closed_market_gap_signal_not_executed(self):
        import datetime as dt
        first = bt.Bar(datetime(2025, 1, 3, 21, tzinfo=timezone.utc),
                       "USD/JPY", D("150"), D("150.1"), D("149.9"),
                       D("150"), D("0"), D("1"), "LONG")
        after = replace(first, time=datetime(2025, 1, 5, 22,
                                            tzinfo=timezone.utc),
                        signal="HOLD")
        report = bt.simulate([first, after])
        self.assertEqual(report["trade_count"], 0)
        self.assertEqual(report["stale_gap_signals_suppressed"], 1)
        self.assertEqual(report["signals_rejected"], 0)

    def test_rejection_reasons_accounting(self):
        rows = [row(0, signal="LONG"),
                row(1, o="150", h="150.01", l="149.7",
                    c="150", signal="LONG"),
                row(2, o="150", h="150.01", l="149.7",
                    c="150", signal="LONG"),
                row(3, o="150", h="150.01", l="149.7",
                    c="150", signal="LONG")]
        out = self.run_rows(rows)
        self.assertEqual(sum(out["signals_rejected_by_reason"].values()),
                         out["signals_rejected"])
        self.assertIs(out["safety_hold_latched"], True)

    def test_reject_inconsistent_actual_bid_ask_candles(self):
        t = datetime(2025, 1, 7, tzinfo=timezone.utc)
        bad = bt.Bar(t, "USD/JPY", D("150"), D("150.1"),
                     D("149.9"), D("150"), D("1"), D("1"), "HOLD",
                     (D("150"), D("150.1"), D("149.9"), D("150")),
                     (D("149"), D("150.1"), D("149.9"), D("150")))
        with self.assertRaises(bt.InputError):
            bt.simulate([bad])


if __name__ == "__main__":
    unittest.main()
