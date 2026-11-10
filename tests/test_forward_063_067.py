"""FWD-063-067: honest offline compiler and tick-observation evidence tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_metaeditor_evidence import (
    SCHEMA as COMPILER_SCHEMA, inspect as compiler_inspect,
    main as compiler_cli)
from research.forward_mt4_v2_series import inspect as series_inspect
from research.forward_mt4_v2_quote import COLUMNS
from research.offline_backtest import InputError

ROOT = Path(__file__).resolve().parents[1]
MQL = (ROOT / "research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4").read_bytes()
ASOF = "2026-11-10T03:15:00Z"


def declaration(status="REPORTED_SUCCESS", errors=0):
    return {
        "schema": COMPILER_SCHEMA, "captured_at_utc": ASOF,
        "compiler_status": status, "source_sha256": hashlib.sha256(MQL).hexdigest(),
        "reported_error_count": errors, "reported_warning_count": 0,
        "operator_environment": "WINDOWS_MANUAL",
        "account_type_reported": "DEMO", "mt4_script_executed": False,
    }


def csv_snapshot(pair, utc, server_now, server_tick, age):
    conv = "1.00000" if pair.endswith("/JPY") else "150.00000"
    fields = [utc, pair, "150.001", "150.020", conv, server_tick,
              server_now, str(age), "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED"]
    return (",".join(COLUMNS) + "\n" + ",".join(fields) + "\n").encode()


def write(d, file_name, content):
    path = d / file_name
    path.write_bytes(content)
    return path


class CompilerEvidenceTests(unittest.TestCase):
    def test_claimed_success_does_not_prove_compilation(self):
        result = compiler_inspect(declaration(), MQL)
        self.assertEqual(result["compiler_status_self_reported"], "REPORTED_SUCCESS")
        self.assertFalse(result["metaeditor_compilation_independently_verified"])
        self.assertFalse(result["real_orders_permitted"])

    def test_unrun_is_accepted_as_no_go_evidence(self):
        result = compiler_inspect(declaration("NOT_RUN"), MQL)
        self.assertTrue(result["safety_hold_latched"])

    def test_hash_mismatch_fails(self):
        info = declaration()
        info["source_sha256"] = "f" * 64
        with self.assertRaises(InputError):
            compiler_inspect(info, MQL)

    def test_failure_with_no_errors_fails(self):
        with self.assertRaises(InputError):
            compiler_inspect(declaration("REPORTED_FAILURE", 0), MQL)

    def test_success_with_errors_fails(self):
        with self.assertRaises(InputError):
            compiler_inspect(declaration("REPORTED_SUCCESS", 1), MQL)

    def test_manifest_cannot_claim_script_executed(self):
        info = declaration()
        info["mt4_script_executed"] = True
        with self.assertRaises(InputError):
            compiler_inspect(info, MQL)

    def test_live_account_declaration_refused(self):
        info = declaration()
        info["account_type_reported"] = "LIVE"
        with self.assertRaises(InputError):
            compiler_inspect(info, MQL)

    def test_cli_is_exclusive_output(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            manifest = d / "evidence.json"
            manifest.write_text(json.dumps(declaration()))
            source = write(d, "script.mq4", MQL)
            result = d / "report.json"
            args = ["--manifest", str(manifest), "--source", str(source),
                    "--out", str(result)]
            self.assertEqual(compiler_cli(args), 0)
            self.assertEqual(compiler_cli(args), 2)
            self.assertFalse(json.loads(result.read_text())["real_orders_permitted"])


class QuoteSeriesTests(unittest.TestCase):
    def sample(self, d, pair="USD/JPY", *, utc="2026-11-10T03:14:55Z",
               server_now="2026-11-10T12:14:55",
               server_tick="2026-11-10T12:14:50", age=5, name="a.csv"):
        return write(d, name, csv_snapshot(pair, utc, server_now, server_tick, age))

    def test_valid_snapshot_always_no_go(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            r = series_inspect([self.sample(d)], asof_utc=ASOF)
            self.assertEqual(r["capture_count"], 1)
            self.assertFalse(r["long_duration_live_collection_verified"])
            self.assertFalse(r["real_orders_permitted"])

    def test_missing_third_pair_is_explicit(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            one = self.sample(d, name="a.csv")
            two = self.sample(d, pair="EUR/JPY", name="b.csv")
            result = series_inspect([one, two], asof_utc=ASOF)
            self.assertIn("MISSING_EUR_USD", result["blocking_reasons"])

    def test_duplicate_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            one = self.sample(d)
            two = write(d, "b.csv", one.read_bytes())
            with self.assertRaises(InputError):
                series_inspect([one, two], asof_utc=ASOF)

    def test_duplicate_path_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            one = self.sample(d)
            with self.assertRaises(InputError):
                series_inspect([one, one], asof_utc=ASOF)

    def test_stalled_server_clock_detected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = self.sample(d, utc="2026-11-10T03:10:00Z",
                            server_now="2026-11-10T12:10:00",
                            server_tick="2026-11-10T12:09:55",
                            name="a.csv")
            b = self.sample(d, utc="2026-11-10T03:12:00Z",
                            server_now="2026-11-10T12:10:00",
                            server_tick="2026-11-10T12:09:55",
                            name="b.csv")
            result = series_inspect([a,b], asof_utc=ASOF)
            self.assertIn("SERVER_CLOCK_STALLED",
                          result["by_pair"]["USD/JPY"]["anomalies"])

    def test_gap_detected_on_historical_snapshots(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = self.sample(d, utc="2026-11-10T03:00:00Z",
                            server_now="2026-11-10T12:00:00",
                            server_tick="2026-11-10T11:59:55",
                            name="a.csv")
            b = self.sample(d, utc="2026-11-10T03:10:00Z",
                            server_now="2026-11-10T12:10:00",
                            server_tick="2026-11-10T12:09:55",
                            name="b.csv")
            result = series_inspect([a,b], asof_utc=ASOF)
            self.assertIn("OBSERVATION_GAP_USD_JPY", result["blocking_reasons"])

    def test_client_time_repeated_rejected_for_continuity(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = self.sample(d, name="a.csv")
            b = self.sample(d, server_now="2026-11-10T12:14:56",
                            server_tick="2026-11-10T12:14:51", name="b.csv")
            result = series_inspect([a,b], asof_utc=ASOF)
            self.assertIn("REPEATED_OR_REVERSED_CLIENT_TIMESTAMP",
                          result["by_pair"]["USD/JPY"]["anomalies"])

    def test_future_capture_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = self.sample(d, utc="2026-11-10T03:16:00Z")
            with self.assertRaises(InputError):
                series_inspect([a], asof_utc=ASOF)

    def test_out_of_scope_pair_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            a = self.sample(d, pair="GBP/USD")
            with self.assertRaises(InputError):
                series_inspect([a], asof_utc=ASOF)


if __name__ == "__main__":
    unittest.main()
