"""FWD-013: NY17 boundary, drawdown, and fail-closed shadow tests."""
import tempfile
import unittest
from pathlib import Path

from research.forward_risk_timeline import evaluate, trading_day, main
from research.offline_backtest import InputError


def point(time, equity, exposure="0"):
    return {
        "observed_at_utc": time,
        "equity_jpy": str(equity),
        "open_risk_jpy": str(exposure),
        "source_status": "HYPOTHETICAL_UNVERIFIED",
    }


class ShadowRiskTimelineTests(unittest.TestCase):
    def test_summer_ny17_boundary(self):
        self.assertEqual(trading_day("2026-07-01T20:59:59Z"), "2026-06-30")
        self.assertEqual(trading_day("2026-07-01T21:00:00Z"), "2026-07-01")

    def test_winter_ny17_boundary(self):
        self.assertEqual(trading_day("2026-11-10T21:59:59Z"), "2026-11-09")
        self.assertEqual(trading_day("2026-11-10T22:00:00Z"), "2026-11-10")

    def test_escalation_latched_despite_recovery(self):
        report = evaluate([
            point("2026-11-10T22:00:00Z", "100000"),
            point("2026-11-10T22:01:00Z", "94900", "1200"),
            point("2026-11-10T22:02:00Z", "102000"),
        ])
        self.assertTrue(report["hypothetical_dd_level3_latched"])
        self.assertTrue(report["hypothetical_dd_hard_stop_latched"])
        self.assertTrue(report["hypothetical_daily_loss_latched"])
        self.assertTrue(report["hypothetical_concurrent_risk_violated"])
        self.assertFalse(report["level3_or_dd5_human_approval_obtained"])
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")
        self.assertFalse(report["real_orders_permitted"])

    def test_trading_day_resets_but_dd_peak_persists(self):
        report = evaluate([
            point("2026-11-10T21:59:00Z", "100000"),
            point("2026-11-10T22:00:00Z", "98000"),
        ])
        self.assertEqual(report["trading_day_count"], 2)
        self.assertEqual(report["maximum_hypothetical_daily_loss_fraction"], "0")
        self.assertEqual(report["maximum_hypothetical_drawdown_fraction"], "0.02")

    def test_exact_daily_limit_triggers(self):
        report = evaluate([
            point("2026-11-10T22:00:00Z", "100000"),
            point("2026-11-10T22:01:00Z", "98500"),
        ])
        self.assertTrue(report["hypothetical_daily_loss_latched"])
        self.assertFalse(report["hypothetical_dd_level3_latched"])

    def test_duplicate_time_refused(self):
        with self.assertRaises(InputError):
            evaluate([point("2026-11-10T22:00:00Z", "100000"),
                      point("2026-11-10T22:00:00Z", "99000")])

    def test_reverse_time_refused(self):
        with self.assertRaises(InputError):
            evaluate([point("2026-11-10T22:01:00Z", "100000"),
                      point("2026-11-10T22:00:00Z", "99000")])

    def test_negative_or_nan_refused(self):
        for value in ("NaN", "-100", "Infinity", "0"):
            with self.subTest(value=value), self.assertRaises(InputError):
                evaluate([point("2026-11-10T22:00:00Z", value)])

    def test_untrusted_source_refused(self):
        sample = point("2026-11-10T22:00:00Z", "100000")
        sample["source_status"] = "REAL_BROKER"
        with self.assertRaises(InputError):
            evaluate([sample])

    def test_empty_samples_refused(self):
        with self.assertRaises(InputError):
            evaluate([])

    def test_cli_without_input_fails_without_creating_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            code = main(["--input", str(Path(directory) / "none.json"),
                         "--out", str(output)])
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
