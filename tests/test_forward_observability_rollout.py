"""FWD-018/020/021 smoke and failure-path tests, no external services."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research.forward_observability import observe, main
from research.forward_mt4_static_audit import inspect_source
from research.forward_quote_continuity import inspect as quotes
from research.offline_backtest import InputError, PAIRS


NOW = "2026-11-10T01:00:00Z"


def multi():
    return {
        "status": "FORWARD_MULTICYCLE_RESEARCH_HOLD_NO_GO",
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
        "cycle_count": 1,
        "cycles": [{
            "cycle_id": "cycle01", "asof_utc": "2026-11-10T00:59:00Z",
            "observation_count": 3,
            "quality_sha256": "1" * 64, "paper_sha256": "2" * 64,
            "hypothetical_pnl_jpy": "0", "hypothetical_equity_jpy": "100000",
        }],
        "blocking_reasons": ["BROKER_EQUITY_NOT_AUTHENTICATED"],
        "risk_timeline": {
            "status": "HYPOTHETICAL_RISK_MONITOR_NO_GO",
            "safety_hold_latched": True, "real_orders_permitted": False,
            "hypothetical_dd_level3_latched": False,
            "hypothetical_dd_hard_stop_latched": False,
            "hypothetical_daily_loss_latched": False,
            "hypothetical_concurrent_risk_violated": False,
        },
    }


def schedule(source="US_BLS", time=NOW):
    return {
        "schema": "fx_forward_schedule_snapshot_v1",
        "source_key": source,
        "retrieved_at_utc": "2026-11-10T00:50:00Z",
        "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
        "runtime_go_no_go": "NO_GO",
        "real_orders_permitted": False,
        "source_authenticity_verified": False,
        "events": [{
            "title": "sample event",
            "scheduled_at_utc": time,
            "source_url": "https://www.bls.gov/example",
            "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
        }],
    }


class ObservabilityTests(unittest.TestCase):
    def test_missing_schedules_no_go(self):
        out = observe(multi(), asof_utc=NOW)
        self.assertIn("NO_FUTURE_SCHEDULE_SNAPSHOT", out["blocking_reasons"])
        self.assertFalse(out["real_orders_permitted"])
        self.assertFalse(out["demo_order_execution_enabled"])

    def test_event_blackout_still_no_go(self):
        out = observe(multi(), asof_utc=NOW, schedules=[schedule()])
        self.assertIn("SCHEDULED_EVENT_BLACKOUT", out["blocking_reasons"])
        self.assertIn("PARTIAL_ECONOMIC_CALENDAR", out["blocking_reasons"])

    def test_all_sources_present_does_not_authenticate(self):
        reports = [schedule(x, "2026-11-11T01:00:00Z") for x in
                   ("US_BLS", "US_FED", "EU_ECB", "JP_BOJ")]
        out = observe(multi(), asof_utc=NOW, schedules=reports)
        self.assertTrue(all(out["schedule_sources_observed_not_verified"].values()))
        self.assertFalse(out["economic_calendar_coverage_verified"])
        self.assertFalse(out["real_orders_permitted"])

    def test_stale_cycle_and_schedule_hold(self):
        item = multi()
        item["cycles"][0]["asof_utc"] = "2026-11-09T22:00:00Z"
        old = schedule()
        old["retrieved_at_utc"] = "2026-11-08T00:00:00Z"
        out = observe(item, asof_utc=NOW, schedules=[old])
        self.assertIn("SHADOW_CYCLE_NOT_RECENT", out["blocking_reasons"])
        self.assertIn("STALE_SCHEDULE_US_BLS", out["blocking_reasons"])

    def test_fake_live_authorization_rejected(self):
        item = multi()
        item["real_orders_permitted"] = True
        with self.assertRaises(InputError):
            observe(item, asof_utc=NOW)

    def test_duplicate_schedule_source_rejected(self):
        with self.assertRaises(InputError):
            observe(multi(), asof_utc=NOW, schedules=[schedule(), schedule()])

    def test_cycle_count_mismatch_rejected(self):
        item = multi()
        item["cycle_count"] = 2
        with self.assertRaises(InputError):
            observe(item, asof_utc=NOW)

    def test_future_cycle_rejected(self):
        item = multi()
        item["cycles"][0]["asof_utc"] = "2026-11-10T02:00:00Z"
        with self.assertRaises(InputError):
            observe(item, asof_utc=NOW)

    def test_cli_missing_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            dst = Path(root) / "output.json"
            self.assertEqual(main(["--multicycle", str(Path(root) / "none"),
                                   "--asof-utc", NOW, "--out", str(dst)]), 2)
            self.assertFalse(dst.exists())


class QuoteContinuityTests(unittest.TestCase):
    @patch("research.forward_quote_continuity.records", return_value=[])
    def test_no_quotes_blocks_all_pairs(self, _):
        result = quotes(Path("unused"), asof_utc=NOW)
        self.assertEqual(set(result["by_pair"]), set(PAIRS))
        self.assertFalse(result["all_pairs_have_fresh_quotes"])
        self.assertTrue(all("MISSING_OR_STALE_LATEST_QUOTE" in x["blocking_reasons"]
                            for x in result["by_pair"].values()))
        self.assertFalse(result["real_orders_permitted"])

    @patch("research.forward_quote_continuity.records")
    def test_duplicate_tick_and_gap(self, mock):
        def row(seq, when):
            return {
                "captured_at_utc": when, "record_sha256": str(seq) * 64,
                "snapshot": {
                    "kind": "PRICE_QUOTE", "observed_at_utc": when,
                    "payload": {"pair": "USD/JPY", "bid": "150.00",
                                "ask": "150.01", "source_status":
                                "USER_SUPPLIED_UNVERIFIED"},
                },
            }
        mock.return_value = [
            row(1, "2026-11-10T00:40:00Z"),
            row(2, "2026-11-10T00:40:00Z"),
            row(3, "2026-11-10T00:55:00Z"),
        ]
        report = quotes(Path("unused"), asof_utc=NOW)
        flags = report["by_pair"]["USD/JPY"]["blocking_reasons"]
        self.assertIn("DUPLICATE_OR_REVERSED_TICK_TIME", flags)
        self.assertIn("TICK_GAP_EXCEEDED", flags)


class MT4StaticAuditTests(unittest.TestCase):
    def test_repository_source_only_static_audit(self):
        src = Path(__file__).resolve().parents[1] / (
            "research/mt4_readonly/FxForwardReadOnlyQuote.mq4")
        out = inspect_source(src.read_bytes())
        self.assertEqual(out["status"], "MT4_READONLY_SOURCE_STATIC_AUDIT_NO_GO")
        self.assertTrue(out["static_token_checks_passed"])
        self.assertFalse(out["metaeditor_compilation_verified"])
        self.assertFalse(out["real_orders_permitted"])

    def test_orders_and_network_api_blocked(self):
        unsafe = b'#property strict\nvoid OnStart(){IsDemo(); IsConnected(); OrderSend(); WebRequest();}'
        result = inspect_source(unsafe)
        self.assertFalse(result["static_token_checks_passed"])
        self.assertTrue(any("OrderSend" in t for t in result["static_blocking_reasons"]))

    def test_comments_do_not_satisfy_guards(self):
        raw = b'#property strict\n// IsDemo() IsConnected() MODE_BID MODE_ASK\nvoid OnStart(){}'
        result = inspect_source(raw)
        self.assertFalse(result["static_token_checks_passed"])

    def test_binary_invalid(self):
        with self.assertRaises(InputError):
            inspect_source(b'\x00')


if __name__ == "__main__":
    unittest.main()
