"""MT4 self-reported manual status has no execution capabilities."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from research import mt4_manual_status_review as checker
from research.offline_backtest import InputError


def good():
    return {
        "schema": checker.SCHEMA,
        "sampled_at_utc": "2026-11-10T08:00:00Z",
        "account_type": "DEMO",
        "connection_display": "CONNECTED_LIKE",
        "autotrading_display": "OFF_LIKE",
        "scripts_or_eas_present": False,
        "open_positions": 0,
        "pending_orders": 0,
        "source": "MANUAL_UNVERIFIED_STATUS",
    }


class Mt4ManualStatusTests(unittest.TestCase):
    def test_clean_manual_report_does_not_enable_commands(self):
        report = checker.inspect_status(good())
        self.assertEqual(report["read_only_review_flags"], [])
        self.assertFalse(report["mt4_terminal_queried"])
        self.assertFalse(report["mt4_account_identity_verified"])
        self.assertFalse(report["demo_order_execution_enabled"])
        self.assertFalse(report["real_orders_permitted"])
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")

    def test_account_uncertainty_existing_orders_and_eas_flagged(self):
        input_ = {
            **good(), "account_type": "LIVE",
            "connection_display": "UNKNOWN",
            "autotrading_display": "ON_LIKE",
            "scripts_or_eas_present": True,
            "open_positions": 1, "pending_orders": 2,
        }
        report = checker.inspect_status(input_)
        self.assertEqual(len(report["read_only_review_flags"]), 5)
        self.assertFalse(report["connection_enabled"])
        self.assertFalse(report["demo_order_execution_enabled"])

    def test_malformed_and_credential_leakage_not_accepted(self):
        for bad in (
            {**good(), "open_positions": -1},
            {**good(), "open_positions": "0"},
            {**good(), "sampled_at_utc": "yesterday"},
            {**good(), "source": "MT4_ALREADY_AUTHENTICATED"},
            {**good(), "account_number": "PRIVATE"},
        ):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                checker.inspect_status(bad)

    def test_cli_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "input.json"
            out = Path(folder) / "out.json"
            p.write_text(json.dumps(good()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(checker.main([
                    "--input", str(p), "--out", str(out)]), 0)
                self.assertEqual(checker.main([
                    "--input", str(p), "--out", str(out)]), 2)
            self.assertFalse(json.loads(out.read_text(encoding="utf-8"))[
                "mt4_account_identity_verified"])


if __name__ == "__main__":
    unittest.main()
