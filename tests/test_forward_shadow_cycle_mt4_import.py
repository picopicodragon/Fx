"""FWD-05/06 tests for repeatable offline cycle and manual MT4 quote."""
import csv
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import forward_observation as obs
from research import forward_mt4_quote_import as mt4
from research import forward_shadow_cycle as shadow
from research import forward_paper as paper
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)


def quote_csv(when="2026-11-10T08:00:00Z", *, pair="USD/JPY",
              account="DEMO", bid="150.00", ask="150.01"):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=mt4.COLUMNS)
    writer.writeheader()
    writer.writerow({
        "observed_at_utc": when, "pair": pair, "bid": bid,
        "ask": ask, "quote_to_jpy": "1", "account_type": account,
        "origin": mt4.ORIGIN,
    })
    return stream.getvalue()


def scenario():
    return {
        "schema": paper.SCHEMA,
        "hypothetical_only": True, "starting_jpy": "100000",
        "stop_pips": "20", "reward_multiple": "1.5",
        "max_simulated_positions": 1, "commission_jpy": "0",
    }


class ForwardCycleAndMT4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "journal"
        obs.initialize(self.store, "fixture_shadow", now=NOW)

    def test_quote_is_unverified_and_not_a_mt4_connection(self):
        file = self.root / "quote.csv"
        file.write_text(quote_csv(), encoding="utf-8")
        result = mt4.import_quote(self.store, file, now=NOW)
        self.assertEqual(result["kind"], "PRICE_QUOTE")
        self.assertFalse(result["account_type_verified"])
        self.assertFalse(result["mt4_connected"])
        self.assertFalse(result["demo_order_execution_enabled"])
        self.assertEqual(obs.audit(self.store)["record_count"], 1)

    def test_bad_quote_files_and_old_quotes_fail(self):
        cases = [
            quote_csv(account="LIVE"),
            quote_csv(pair="GBP/USD"),
            quote_csv(bid="150.01", ask="150.00"),
            quote_csv(when="2026-11-10T07:00:00Z"),
            quote_csv(when="2026-11-10T09:00:00Z"),
            quote_csv().replace("MANUAL_MT4_DEMO_EXPORT_UNVERIFIED",
                                "AUTO_TRADING_ACTIVE"),
        ]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(InputError):
                mt4.parse_quote_csv(value, now=NOW)
        self.assertEqual(obs.audit(self.store)["record_count"], 0)

    def test_immutable_shadow_cycle_without_data_has_no_position(self):
        output = shadow.run_once(
            self.store, self.root, "cycle_001", scenario(),
            asof_utc="2026-11-10T08:00:00Z")
        self.assertEqual(output["status"], "FORWARD_SHADOW_CYCLE_NO_GO")
        self.assertFalse(output["hypothetical_position"])
        self.assertFalse(output["real_orders_permitted"])
        self.assertFalse(output["mt4_connected"])
        with self.assertRaises(InputError):
            shadow.run_once(self.store, self.root, "cycle_001", scenario(),
                            asof_utc="2026-11-10T08:00:00Z")
        output2 = shadow.run_once(
            self.store, self.root, "cycle_002", scenario(),
            asof_utc="2026-11-10T08:00:01Z")
        self.assertFalse(output2["hypothetical_position"])
        self.assertTrue((self.root / "cycle_001_quality.json").exists())

    def test_cycle_id_path_escape_prevented(self):
        for name in ("../secrets", "Cycle One", "X" * 50, ".hidden", ""):
            with self.subTest(name=name), self.assertRaises(InputError):
                shadow.run_once(
                    self.store, self.root, name, scenario(),
                    asof_utc="2026-11-10T08:00:00Z")


if __name__ == "__main__":
    unittest.main()
