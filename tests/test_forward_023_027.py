"""FWD-023..027 offline forwarding safety and regression tests."""
import copy
import tempfile
import unittest
from pathlib import Path

from research.forward_mt4_export_series import inspect_exports
from research.forward_calendar_revisions import compare
from research.forward_shadow_watch import evaluate
from research.forward_demo_gate_board import board
from research.offline_backtest import InputError

NOW = "2026-11-10T01:00:00Z"
HEAD = "observed_at_utc,pair,bid,ask,quote_to_jpy,account_type,origin\n"
ORIGIN = "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED"


def export(path, when, pair="USD/JPY", acc="DEMO"):
    path.write_text(HEAD + f"{when},{pair},150.000,150.010,1,{acc},{ORIGIN}\n")
    return path


def event(name, when):
    return {"title": name, "scheduled_at_utc": when,
            "source_url": "https://www.bls.gov/example",
            "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED"}


def schedule(when, events):
    return {"schema": "fx_forward_schedule_snapshot_v1",
            "source_key": "US_BLS",
            "retrieved_at_utc": when,
            "events": events,
            "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
            "source_authenticity_verified": False}


def reports():
    common = {"runtime_go_no_go": "NO_GO",
              "real_orders_permitted": False,
              "safety_hold_latched": True}
    obs = {**common, "status": "FORWARD_OBSERVABILITY_HOLD_NO_GO",
           "asof_utc": NOW, "latest_cycle_age_seconds": 0,
           "blocking_reasons": []}
    quote = {**common, "status": "QUOTE_CONTINUITY_RESEARCH_NO_GO",
             "asof_utc": NOW,
             "by_pair": {p: {"latest_quote_age_seconds": 0,
                            "blocking_reasons": []}
                         for p in ("USD/JPY", "EUR/JPY", "EUR/USD")}}
    return obs, quote


class ExportSeriesTests(unittest.TestCase):
    def test_offline_csv_series_no_authorization(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            files = [export(d / "a.csv", "2026-11-10T00:59:10Z"),
                     export(d / "b.csv", "2026-11-10T00:59:20Z")]
            out = inspect_exports(files, asof_utc=NOW)
            self.assertEqual(out["export_count"], 2)
            self.assertEqual(out["missing_pairs"], ["EUR/JPY", "EUR/USD"])
            self.assertFalse(out["mt4_connected"])
            self.assertFalse(out["real_orders_permitted"])

    def test_out_of_order_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root)
            files = [export(d/"a.csv", "2026-11-10T00:59:20Z"),
                     export(d/"b.csv", "2026-11-10T00:59:10Z")]
            with self.assertRaises(InputError):
                inspect_exports(files, asof_utc=NOW)

    def test_live_export_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            item = export(Path(root)/"a.csv", "2026-11-10T00:59:20Z", acc="LIVE")
            with self.assertRaises(InputError):
                inspect_exports([item], asof_utc=NOW)

    def test_stale_export_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            item = export(Path(root)/"a.csv", "2026-11-10T00:40:00Z")
            with self.assertRaises(InputError):
                inspect_exports([item], asof_utc=NOW)

    def test_repeated_path_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            item = export(Path(root)/"a.csv", "2026-11-10T00:59:20Z")
            with self.assertRaises(InputError):
                inspect_exports([item, item], asof_utc=NOW)


class CalendarRevisionTests(unittest.TestCase):
    def setUp(self):
        self.old = schedule("2026-11-10T00:00:00Z",
                            [event("CPI", "2026-11-11T01:00:00Z")])
        self.new = schedule("2026-11-10T00:10:00Z",
                            [event("CPI", "2026-11-11T02:00:00Z"),
                             event("Jobs", "2026-11-12T01:00:00Z")])

    def test_revision_and_add(self):
        result = compare(self.old, self.new)
        self.assertEqual(result["change_count"], 2)
        self.assertEqual({r["change"] for r in result["changes"]},
                         {"NEW", "RESCHEDULED"})
        self.assertFalse(result["real_orders_permitted"])

    def test_missing_is_not_confirmed_cancel(self):
        self.new["events"] = []
        result = compare(self.old, self.new)
        self.assertEqual(result["changes"][0]["change"], "MISSING")
        self.assertTrue(result["missing_events_are_not_confirmed_cancellations"])

    def test_duplicate_identity_fails(self):
        self.new["events"].append(copy.deepcopy(self.new["events"][0]))
        with self.assertRaises(InputError):
            compare(self.old, self.new)

    def test_reverse_retrieval_refused(self):
        self.new["retrieved_at_utc"] = "2026-11-09T23:00:00Z"
        with self.assertRaises(InputError):
            compare(self.old, self.new)

    def test_source_mismatch_refused(self):
        self.new["source_key"] = "JP_BOJ"
        with self.assertRaises(InputError):
            compare(self.old, self.new)


class ShadowWatchTests(unittest.TestCase):
    def test_healthy_research_remains_no_go(self):
        result = evaluate(*reports(), asof_utc=NOW)
        self.assertEqual(result["interruption_level"], "NONE")
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["resume_automatically_permitted"])

    def test_level1_from_late_ticks(self):
        obs, quote = reports()
        quote["by_pair"]["EUR/USD"]["latest_quote_age_seconds"] = 61
        out = evaluate(obs, quote, asof_utc=NOW)
        self.assertEqual(out["interruption_level"], "LEVEL1")
        self.assertTrue(out["watchdog_latched"])

    def test_level2_from_missing_tick(self):
        obs, quote = reports()
        quote["by_pair"]["EUR/USD"]["latest_quote_age_seconds"] = None
        self.assertEqual(evaluate(obs, quote, asof_utc=NOW)["interruption_level"],
                         "LEVEL2")

    def test_latched_wont_recover_automatically(self):
        obs, quote = reports()
        prior = evaluate(obs, quote, asof_utc=NOW)
        prior["watchdog_latched"] = True
        later = evaluate(obs, quote, asof_utc="2026-11-10T01:00:05Z",
                         prior=prior)
        self.assertTrue(later["watchdog_latched"])
        self.assertFalse(later["resume_automatically_permitted"])

    def test_forged_go_refused(self):
        obs, quote = reports()
        obs["real_orders_permitted"] = True
        with self.assertRaises(InputError):
            evaluate(obs, quote, asof_utc=NOW)

    def test_backwards_time_refused(self):
        obs, quote = reports()
        prior = evaluate(obs, quote, asof_utc=NOW)
        with self.assertRaises(InputError):
            evaluate(obs, quote, asof_utc=NOW, prior=prior)


class DemoBoardTests(unittest.TestCase):
    def test_empty_board_still_no_go(self):
        out = board({})
        self.assertIn("MISSING_DEMO", out["blocking_reasons"])
        self.assertFalse(out["real_orders_permitted"])
        self.assertFalse(out["demo_order_execution_enabled"])

    def test_self_report_all_good_still_blocked(self):
        samples = {}
        for key, status in (
                ("demo", "FWD_DEMO_READINESS_RESEARCH_NO_GO"),
                ("watch", "FORWARD_SHADOW_WATCH_HOLD_NO_GO"),
                ("mt4", "MT4_READONLY_EXPORT_RESEARCH_NO_GO"),
                ("calendar", "CALENDAR_REVISION_RESEARCH_NO_GO")):
            samples[key] = {"status": status, "runtime_go_no_go": "NO_GO",
                            "safety_hold_latched": True,
                            "real_orders_permitted": False,
                            "demo_order_execution_enabled": False}
        samples["demo"]["blocking_reasons"] = []
        samples["watch"]["watchdog_latched"] = False
        samples["mt4"]["missing_pairs"] = []
        samples["calendar"]["change_count"] = 0
        out = board(samples)
        self.assertFalse(out["research_evidence_sufficient_to_enable_orders"])
        self.assertIn("FORWARD_REAL_EXECUTION_FORBIDDEN", out["blocking_reasons"])

    def test_untrusted_demo_report_refused(self):
        samples = {"demo": {"status": "FWD_DEMO_READINESS_RESEARCH_NO_GO",
                            "runtime_go_no_go": "GO",
                            "safety_hold_latched": True,
                            "real_orders_permitted": True,
                            "demo_order_execution_enabled": True}}
        with self.assertRaises(InputError):
            board(samples)


if __name__ == "__main__":
    unittest.main()
