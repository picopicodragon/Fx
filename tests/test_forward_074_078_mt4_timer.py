"""FWD-074..078 source-only regression for future DEMO timer observation."""
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_mt4_timer_observer_review import inspect, main

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research/mt4_readonly/FxForwardDemoTimerObserver.mq4"


class ForwardDemoTimerObserverTests(unittest.TestCase):
    def test_original_source_static_review(self):
        report = inspect(SOURCE.read_bytes())
        self.assertTrue(report["static_preflight_passed"], report["static_failures"])
        self.assertFalse(report["real_orders_permitted"])
        self.assertFalse(report["actual_continuous_capture_verified"])

    def test_exactly_three_symbols(self):
        src = SOURCE.read_text()
        for symbol in ("USDJPY", "EURJPY", "EURUSD"):
            self.assertIn('"'+symbol+'"', src)
        for symbol in ("GBPUSD", "AUDUSD"):
            self.assertNotIn('"'+symbol+'"', src)

    def test_order_call_is_refused(self):
        bad = SOURCE.read_bytes() + b"\nvoid unsafe(){ OrderSend(); }"
        self.assertFalse(inspect(bad)["static_preflight_passed"])

    def test_shared_file_access_is_refused(self):
        bad = SOURCE.read_bytes() + b"\nvoid unsafe(){ int a=FILE_COMMON; }"
        self.assertFalse(inspect(bad)["static_preflight_passed"])

    def test_webrequest_is_refused(self):
        bad = SOURCE.read_bytes() + b"\nvoid unsafe(){ WebRequest(); }"
        self.assertFalse(inspect(bad)["static_preflight_passed"])

    def test_missing_demo_gate_is_refused(self):
        bad = SOURCE.read_bytes().replace(b"IsDemo()", b"IsSomeOtherDemo()")
        self.assertFalse(inspect(bad)["static_preflight_passed"])

    def test_missing_timer_cleanup_is_refused(self):
        bad = SOURCE.read_bytes().replace(b"EventKillTimer()", b"DoNothing()")
        self.assertFalse(inspect(bad)["static_preflight_passed"])

    def test_missing_max_cycles_is_refused(self):
        bad = SOURCE.read_bytes().replace(b"FXFWD_MAX_CYCLES 30",
                                          b"FXFWD_MAX_CYCLES 30000")
        self.assertFalse(inspect(bad)["static_preflight_passed"])

    def test_missing_file_collision_check_is_refused(self):
        bad = SOURCE.read_bytes().replace(b"FileIsExist(", b"CanOverwrite(")
        self.assertFalse(inspect(bad)["static_preflight_passed"])

    def test_false_refresh_gate_refused(self):
        bad = SOURCE.read_bytes() + b"\nvoid bad(){if(!RefreshRates()){return;}}"
        self.assertIn("REFRESHRATES_BOOLEAN_MISUSE",
                      inspect(bad)["static_failures"])

    def test_static_success_never_enables_trading(self):
        result = inspect(SOURCE.read_bytes())
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])
        self.assertFalse(result["metaeditor_compilation_verified"])
        self.assertFalse(result["actual_mt4_runtime_verified"])

    def test_cli_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "review.json"
            args = ["--source", str(SOURCE), "--out", str(report)]
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args), 2)
            self.assertFalse(json.loads(report.read_text())["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
