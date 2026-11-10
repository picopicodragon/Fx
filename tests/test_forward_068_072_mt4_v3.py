"""FWD-068..072 MT4 v3 source and manual handoff contract regression.

No local MT4 install or MetaEditor executable is required/used in CI.
"""
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_mt4_v3_source_review import inspect, main as cli
from research.forward_mt4_v2_quote import parse, COLUMNS
from research.offline_backtest import InputError

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "research/mt4_readonly/FxForwardReadOnlyQuoteV3.mq4"
PS1 = ROOT / "scripts/prepare_mt4_v3_manual_install_plan.ps1"
NOW = "2026-11-10T03:00:00Z"


def example(pair):
    conversion = "1" if pair.endswith("/JPY") else "150.00000"
    data = [NOW, pair, "150.001", "150.020", conversion,
            "2026-11-10T11:59:55", "2026-11-10T12:00:00", "5",
            "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED"]
    return (",".join(COLUMNS) + "\n" + ",".join(data) + "\n").encode()


class Mt4V3SourceTests(unittest.TestCase):
    def test_original_v3_source_static_contract(self):
        result = inspect(V3.read_bytes())
        self.assertTrue(result["static_preflight_passed"], result["static_failures"])
        self.assertFalse(result["metaeditor_compile_verified"])
        self.assertFalse(result["real_mt4_terminal_execution_verified"])
        self.assertFalse(result["real_orders_permitted"])

    def test_only_three_chart_symbols(self):
        src = V3.read_text(encoding="utf-8")
        for symbol in ("USDJPY", "EURJPY", "EURUSD"):
            self.assertIn('symbol == "' + symbol + '"', src)
        for symbol in ("GBPUSD", "AUDUSD"):
            self.assertNotIn('symbol == "' + symbol + '"', src)

    def test_static_guard_prevents_order_send(self):
        unsafe = V3.read_bytes() + b"\nvoid bad(){ OrderSend(); }\n"
        result = inspect(unsafe)
        self.assertFalse(result["static_preflight_passed"])

    def test_static_guard_prevents_file_common(self):
        unsafe = V3.read_bytes() + b"\nvoid bad(){ int flags=FILE_COMMON; }\n"
        self.assertFalse(inspect(unsafe)["static_preflight_passed"])

    def test_refresh_rates_false_does_not_abort_export(self):
        # A false return indicates that the local copy can already be current.
        source = V3.read_text(encoding="utf-8")
        self.assertIn("   RefreshRates();", source)
        self.assertNotIn("if(!RefreshRates())", source)
        self.assertNotIn("price refresh unavailable; no file", source)

    def test_static_guard_rejects_false_as_failure_regression(self):
        original = V3.read_bytes()
        damaged = original.replace(
            b"   RefreshRates();",
            b"   if(!RefreshRates()) { return; }")
        self.assertFalse(inspect(damaged)["static_preflight_passed"])
        self.assertIn("INVALID_REFRESH_RATES_FAILURE_GATE",
                      inspect(damaged)["static_failures"])

    def test_missing_demo_guard_detected(self):
        unsafe = V3.read_bytes().replace(b"IsDemo()", b"IsTradeAllowed()")
        self.assertFalse(inspect(unsafe)["static_preflight_passed"])

    def test_missing_collision_guard_detected(self):
        unsafe = V3.read_bytes().replace(b"FileIsExist(", b"SkipGuard(")
        self.assertFalse(inspect(unsafe)["static_preflight_passed"])

    def test_missing_eurusd_detected(self):
        unsafe = V3.read_bytes().replace(b'symbol == "EURUSD"',
                                         b'symbol == "GBPUSD"')
        self.assertFalse(inspect(unsafe)["static_preflight_passed"])

    def test_existing_v2_csv_parser_accepts_all_three_v3_columns(self):
        # This tests the *shape*, not actual MQL4 output or real market data.
        for pair in ("USD/JPY", "EUR/JPY", "EUR/USD"):
            with self.subTest(pair=pair):
                out = parse(example(pair), asof_utc=NOW)
                self.assertEqual(out["pair"], pair)
                self.assertFalse(out["real_orders_permitted"])

    def test_out_of_scope_symbol_rejected_in_csv(self):
        with self.assertRaises(InputError):
            parse(example("GBP/USD"), asof_utc=NOW)

    def test_offline_cli_never_replaces_report(self):
        with tempfile.TemporaryDirectory() as root:
            out = Path(root) / "source_review.json"
            args = ["--source", str(V3), "--out", str(out)]
            self.assertEqual(cli(args), 0)
            self.assertEqual(cli(args), 2)
            result = json.loads(out.read_text())
            self.assertFalse(result["real_orders_permitted"])

    def test_windows_plan_never_copies_compiles_or_trades(self):
        source = PS1.read_text(encoding="utf-8")
        self.assertIn("'NO_GO'", source)
        self.assertIn("manual_copy_performed = $false", source)
        self.assertIn("metaeditor_compilation_performed = $false", source)
        self.assertIn("real_orders_permitted = $false", source)
        self.assertNotIn("Copy-Item ", source)
        self.assertNotIn("Start-Process ", source)
        self.assertNotIn("ExecutionPolicy Bypass", source)


if __name__ == "__main__":
    unittest.main()
