"""FWD-053..057 three-pair v2 manual read-only contract and failures."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_mt4_v2_quote import (
    parse, main as quote_main, COLUMNS, PAIRS_V2)
from research.forward_mt4_v2_four_pair import (
    review, main as four_main)
from research.forward_mt4_static_audit import inspect_source
from research.offline_backtest import InputError

NOW = "2026-11-10T03:00:00Z"
HEAD = ",".join(COLUMNS) + "\n"
ORIGIN = "MANUAL_MT4_DEMO_V2_UNVERIFIED"


def csv_sample(pair="USD/JPY", *, observed=NOW, tick="2026-11-10T11:59:50",
               server="2026-11-10T12:00:00", age=10, conversion=None,
               account="DEMO", origin=ORIGIN):
    conversion = conversion if conversion is not None else (
        "1.00000" if pair.endswith("/JPY") else "150.00000")
    return (HEAD + ",".join((
        observed, pair, "150.01", "150.03", conversion, tick, server,
        str(age), account, origin)) + "\n").encode("utf-8")


def source_v2():
    return (Path(__file__).resolve().parents[1] /
            "research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4").read_bytes()


class V2QuoteTests(unittest.TestCase):
    def test_all_three_pairs_research_only(self):
        for pair in PAIRS_V2:
            with self.subTest(pair=pair):
                report = parse(csv_sample(pair), asof_utc=NOW)
                self.assertEqual(report["pair"], pair)
                self.assertFalse(report["real_orders_permitted"])
                self.assertFalse(report["server_timestamp_authenticated"])
                self.assertFalse(report["independent_utc_clock_attested"])

    def test_out_of_scope_gbpusd_and_audusd_rejected(self):
        for pair in ("GBP/USD", "AUD/USD"):
            with self.subTest(pair=pair):
                with self.assertRaises(InputError):
                    parse(csv_sample(pair), asof_utc=NOW)

    def test_self_reported_live_account_rejected(self):
        with self.assertRaises(InputError):
            parse(csv_sample(account="LIVE"), asof_utc=NOW)

    def test_wrong_origin_rejected(self):
        with self.assertRaises(InputError):
            parse(csv_sample(origin="VERIFIED"), asof_utc=NOW)

    def test_crossed_sides_rejected(self):
        bad = csv_sample().replace(b"150.03", b"150.00")
        with self.assertRaises(InputError):
            parse(bad, asof_utc=NOW)

    def test_stale_server_relative_tick_rejected(self):
        with self.assertRaises(InputError):
            parse(csv_sample(tick="2026-11-10T11:58:00", age=120),
                  asof_utc=NOW)

    def test_inconsistent_reported_tick_age_rejected(self):
        with self.assertRaises(InputError):
            parse(csv_sample(age=5), asof_utc=NOW)

    def test_future_tick_rejected(self):
        with self.assertRaises(InputError):
            parse(csv_sample(tick="2026-11-10T12:00:01", age=0),
                  asof_utc=NOW)

    def test_stale_pc_timestamp_rejected(self):
        with self.assertRaises(InputError):
            parse(csv_sample(observed="2026-11-10T02:55:00Z"),
                  asof_utc=NOW)

    def test_nonunit_jpy_conversion_rejected(self):
        with self.assertRaises(InputError):
            parse(csv_sample(conversion="150.00"), asof_utc=NOW)

    def test_cli_creates_only_no_go_output(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            src = d / "sample.csv"
            out = d / "report.json"
            src.write_bytes(csv_sample())
            args = ["--csv", str(src), "--asof-utc", NOW, "--out", str(out)]
            self.assertEqual(quote_main(args), 0)
            self.assertEqual(quote_main(args), 2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])

    def test_static_mql4_has_no_order_api(self):
        raw = source_v2()
        scanned = inspect_source(raw)
        # Legacy static audit requires v1-specific origin; verify the v2
        # independently rather than pretending that legacy rules certify v2.
        for forbidden in (b"OrderSend(", b"OrderClose(", b"OrderModify(",
                          b"WebRequest(", b"FILE_COMMON", b"#import"):
            self.assertNotIn(forbidden, raw)
        self.assertIn(b"IsDemo()", raw)
        self.assertIn(b"IsConnected()", raw)
        self.assertIn(b"MODE_TIME", raw)
        self.assertIn(b"TimeCurrent()", raw)
        self.assertFalse(scanned["real_orders_permitted"])


class ThreePairTests(unittest.TestCase):
    def test_all_three_never_licenses_orders(self):
        values = [parse(csv_sample(pair), asof_utc=NOW) for pair in PAIRS_V2]
        report = review(values, asof_utc=NOW)
        self.assertEqual(len(report["pairs_present"]), 3)
        self.assertFalse(report["real_orders_permitted"])
        self.assertFalse(report["legacy_three_pair_pipeline_migrated"])
        self.assertFalse(report["mt4_terminal_execution_verified"])

    def test_missing_pair_is_explicit_blocker(self):
        values = [parse(csv_sample(pair), asof_utc=NOW) for pair in PAIRS_V2[:2]]
        out = review(values, asof_utc=NOW)
        self.assertIn("MISSING_EUR_USD", out["blocking_reasons"])

    def test_duplicate_pair_rejected(self):
        values = [parse(csv_sample("USD/JPY"), asof_utc=NOW)] * 2
        with self.assertRaises(InputError):
            review(values, asof_utc=NOW)

    def test_forged_go_rejected(self):
        value = parse(csv_sample(), asof_utc=NOW)
        value["runtime_go_no_go"] = "GO"
        with self.assertRaises(InputError):
            review([value], asof_utc=NOW)

    def test_stale_at_aggregate_is_explicit_hold(self):
        value = parse(csv_sample(), asof_utc=NOW)
        result = review([value], asof_utc="2026-11-10T03:02:00Z")
        self.assertIn("STALE_USD_JPY", result["blocking_reasons"])

    def test_three_pair_cli_never_overwrites(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = d / "first.json"
            a.write_text(json.dumps(parse(csv_sample(), asof_utc=NOW)))
            out = d / "three.json"
            args = ["--report", str(a), "--asof-utc", NOW,
                    "--out", str(out)]
            self.assertEqual(four_main(args), 0)
            self.assertEqual(four_main(args), 2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
