"""FWD-048..052 manual multi-capture observation and MT4 source contract tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_manual_handoff import capture
from research.forward_manual_session import assess, main as session_main, _load_manifest, SCHEMA
from research.forward_mt4_source_contract import review
from research.offline_backtest import InputError

ASOF = "2026-11-10T03:05:00Z"
ORIGIN = "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED"
HEADER = "observed_at_utc,pair,bid,ask,quote_to_jpy,account_type,origin\n"


def put(root, name, pair, time, price="150.00"):
    src = root / (name + ".csv")
    src.write_text(
        HEADER + f"{time},{pair},{price},150.50,1,DEMO,{ORIGIN}\n",
        encoding="utf-8")
    directory = root / name
    capture(src, directory, capture_id=name,
            asof_utc=time)
    return directory


def real_source():
    return (Path(__file__).resolve().parents[1] /
            "research/mt4_readonly/FxForwardReadOnlyQuote.mq4").read_bytes()


class SessionTests(unittest.TestCase):
    def test_three_pairs_with_nearby_timestamps_is_never_go(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            folders = [
                put(d, "usd", "USD/JPY", "2026-11-10T03:04:55Z"),
                put(d, "eurj", "EUR/JPY", "2026-11-10T03:04:55Z"),
                put(d, "euru", "EUR/USD", "2026-11-10T03:04:55Z"),
            ]
            report = assess(folders, asof_utc=ASOF)
            self.assertEqual(report["capture_count"], 3)
            self.assertFalse(report["real_orders_permitted"])
            self.assertFalse(report["continuous_automated_collection_enabled"])
            self.assertEqual(report["by_pair"]["USD/JPY"]["research_interruption_level"], "NONE")

    def test_gap_identified_without_implied_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            first = put(d, "a1", "USD/JPY", "2026-11-10T02:55:00Z")
            second = put(d, "a2", "USD/JPY", "2026-11-10T03:04:00Z")
            report = assess([first, second], asof_utc=ASOF)
            self.assertEqual(report["by_pair"]["USD/JPY"]["gap_count"], 1)
            self.assertEqual(report["by_pair"]["USD/JPY"]["gaps"][0]["seconds"], 540)
            self.assertFalse(report["restart_automatically_permitted"])

    def test_missing_all_captures_for_pair_is_level2(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = put(d, "a1", "USD/JPY", "2026-11-10T03:04:55Z")
            report = assess([a], asof_utc=ASOF)
            self.assertEqual(report["by_pair"]["EUR/USD"]["research_interruption_level"], "LEVEL2")

    def test_stale_quote_is_level2(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = put(d, "a1", "USD/JPY", "2026-11-10T02:54:00Z")
            report = assess([a], asof_utc=ASOF)
            self.assertEqual(report["by_pair"]["USD/JPY"]["research_interruption_level"], "LEVEL2")

    def test_replayed_timestamp_is_hold(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = put(d, "a1", "USD/JPY", "2026-11-10T03:04:55Z")
            b = put(d, "a2", "USD/JPY", "2026-11-10T03:04:55Z")
            report = assess([a, b], asof_utc=ASOF)
            self.assertIn("REPEAT_USD_JPY", report["blocking_reasons"])

    def test_duplicate_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = put(d, "a1", "USD/JPY", "2026-11-10T03:04:55Z")
            with self.assertRaises(InputError):
                assess([a, a], asof_utc=ASOF)

    def test_tampered_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = put(d, "a1", "USD/JPY", "2026-11-10T03:04:55Z")
            (a / "quote.csv").write_text("tampered")
            with self.assertRaises(InputError):
                assess([a], asof_utc=ASOF)

    def test_manifest_directory_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(InputError):
                _load_manifest({"schema": SCHEMA, "capture_folders": ["../private"]},
                               Path(root))

    def test_manifest_end_to_end(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            put(d, "a1", "USD/JPY", "2026-11-10T03:04:55Z")
            manifest = d / "manifest.json"
            manifest.write_text(json.dumps({
                "schema": SCHEMA, "capture_folders": ["a1"]}))
            result = d / "result.json"
            args = ["--manifest", str(manifest), "--captures-dir", str(d),
                    "--asof-utc", ASOF, "--out", str(result)]
            self.assertEqual(session_main(args), 0)
            self.assertEqual(session_main(args), 2)
            self.assertEqual(json.loads(result.read_text())["runtime_go_no_go"], "NO_GO")

    def test_empty_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(InputError):
                _load_manifest({"schema": SCHEMA, "capture_folders": []},
                               Path(root))


class SourceContractTests(unittest.TestCase):
    def test_repository_mql4_static_contract(self):
        result = review(real_source())
        self.assertTrue(result["source_fragment_checks_passed"])
        self.assertFalse(result["source_compiled_in_metaeditor"])
        self.assertIn("BROKER_TICK_TIMESTAMP_NOT_VERIFIED", result["blocking_reasons"])
        self.assertFalse(result["real_orders_permitted"])

    def test_mql4_order_api_detected(self):
        unsafe = real_source() + b"\nvoid not_safe(){ OrderSend(); }\n"
        result = review(unsafe)
        self.assertFalse(result["static_token_checks_passed"])
        self.assertFalse(result["source_fragment_checks_passed"])

    def test_missing_demo_guard_detected(self):
        bad = real_source().replace(b"if(!IsDemo())", b"if(true)")
        result = review(bad)
        self.assertFalse(result["source_fragment_checks_passed"])

    def test_missing_csv_columns_detected(self):
        bad = real_source().replace(
            b'"quote_to_jpy", "account_type", "origin");',
            b'"wrong_column", "account_type", "origin");')
        result = review(bad)
        self.assertFalse(result["source_fragment_checks_passed"])

    def test_source_contract_does_not_prove_broker(self):
        result = review(real_source())
        self.assertFalse(result["broker_account_authenticated"])
        self.assertFalse(result["terminal_quote_export_tested"])
        self.assertTrue(result["safety_hold_latched"])


if __name__ == "__main__":
    unittest.main()
