"""FWD-553..600: one-shot no-order all-evidence readiness hub integration."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_fullstack_noorder_hub as hub
from research.offline_backtest import InputError

ASOF = "2026-11-13T02:49:10Z"
M = {
    "status": "GLOBAL_MACRO_FORWARD_EVIDENCE_HOLD_NO_GO",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "demo_orders_permitted": False,
    "real_orders_permitted": False,
    "unresolved_holds": [
        "BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT",
        "NO_EUR_EVENT_OBSERVATION"],
    "next_research_actions": ["VERIFY_MACRO_TIME"],
    "bls_snapshot_supplied_and_integrity_checked": True,
    "bls_html_ics_disagreement": True,
    "bls_html_only_missing_slot_instances": 1,
    "official_news_bundle_verified": True,
    "official_news_items_observed": 3,
    "external_event_observations_supplied": 0,
    "external_by_currency": {"USD": 0, "EUR": 0, "JPY": 0},
    "external_missing_consensus_count": 0,
}
F = {
    "status": "CONSENSUS_ARCHIVE_BATCH_RESEARCH_HOLD_NO_GO",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "demo_orders_permitted": False,
    "real_orders_permitted": False,
    "unresolved_holds": ["NO_POINT_IN_TIME_FORECAST_ARCHIVES_PROVIDED"],
    "next_research_actions": ["GET_FORECAST"],
    "archive_count": 0,
    "matched_unique_bls_event_count": 0,
    "unmatched_archive_count": 0,
    "bls_events_without_archive_count": 4,
}
T = {
    "status": "MT4_MULTIDAY_NOORDER_OBSERVATION_HOLD_NO_GO",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "demo_orders_permitted": False,
    "real_orders_permitted": False,
    "unresolved_holds": ["MT4_CLOCK_UNATTESTED"],
    "next_research_actions": ["VERIFY_BROKER_TIME"],
    "verified_format_copied_session_count": 2,
    "distinct_ny17_bucket_count": 2,
    "complete_observation_cycle_count": 60,
    "copied_observation_intervals_unattested": [],
}
C = {
    "status": "MACRO_FORWARD_RESEARCH_CAMPAIGN_HOLD_NO_GO",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "real_orders_permitted": False,
    "unresolved_warnings_and_safety_holds": ["PRICE_DATA_QUALITY_UNVERIFIED"],
    "next_research_actions": ["VERIFY_BROKER_TIME"],
    "price_csv_count": 114,
    "observed_macro_event_count": 0,
    "review_count": 0,
}


class FullstackHubTests(unittest.TestCase):
    def setUp(self):
        # Legacy tests isolate the new blackout input using a strict
        # NO_GO fixture; dedicated FWD-701 tests audit real source parsing.
        p = patch.object(hub.blackout, "inspect", return_value={
            "status": "OFFLINE_BLACKOUT_OBSERVATION_COVERAGE_HOLD_NO_GO",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "unresolved_holds": [],
            "next_research_actions": [],
            "unique_pair_blackout_research_window_count": 0,
            "windows_with_intersecting_copied_quotes": 0,
        })
        p.start()
        self.addCleanup(p.stop)

    def test_no_sources_is_useful_holds_not_fake_zero_go(self):
        r=hub.inspect(asof_utc=ASOF)
        self.assertEqual(r["status"],"FULLSTACK_FORWARD_RESEARCH_READINESS_HOLD_NO_GO")
        self.assertFalse(r["bls_snapshot_verified"])
        self.assertFalse(r["official_news_bundle_verified"])
        self.assertFalse(r["price_ai_campaign_inspected"])
        self.assertEqual(r["mt4_copied_observation_session_count"],0)
        self.assertEqual(r["archived_consensus_records"],0)
        self.assertGreater(r["number_of_holds"],4)
        self.assertFalse(r["coverage_completeness_proven"])
        self.assertFalse(r["broker_and_mt4_order_safety_independently_verified"])
        self.assertFalse(r["live_trading_authorization_established"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertTrue(r["safety_hold_latched"])
        self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_one_hub_joins_all_stages_once_with_114_csv_summary(self):
        with patch.object(hub.global_macro,"inspect",return_value=M) as macro:
            with patch.object(hub.consensus,"inspect",return_value=F) as forecasts:
                with patch.object(hub.mt4,"inspect",return_value=T) as mt4:
                    with patch.object(hub.campaign,"inspect",return_value=C) as ai:
                        r=hub.inspect(
                            asof_utc=ASOF,
                            bls_snapshot_dir=Path("out/bls"),
                            external_macro_observations=None,
                            forecast_archives=[],
                            sessions=[("one",Path("out/one")),
                                      ("two",Path("out/two"))])
        self.assertEqual(macro.call_count,1)
        self.assertEqual(forecasts.call_count,1)
        self.assertEqual(mt4.call_count,1)
        self.assertEqual(ai.call_count,1)
        self.assertEqual(r["price_csv_count"],114)
        self.assertEqual(r["bls_html_missing_ics_slot_instances"],1)
        self.assertEqual(r["bls_events_without_archived_consensus"],4)
        self.assertEqual(r["mt4_observed_ny17_time_bucket_count"],2)
        self.assertIn("BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT",
                      r["unresolved_holds"])
        self.assertIn("NO_POINT_IN_TIME_FORECAST_ARCHIVES_PROVIDED",
                      r["unresolved_holds"])
        self.assertIn("MT4_CLOCK_UNATTESTED",r["unresolved_holds"])
        self.assertIn("PRICE_DATA_QUALITY_UNVERIFIED",r["unresolved_holds"])
        self.assertEqual(r["next_research_actions"].count("VERIFY_BROKER_TIME"),1)
        self.assertFalse(r["real_orders_permitted"])

    def test_bad_campaign_status_is_explicit_failure(self):
        c=dict(C,status="FAKE_GO")
        with patch.object(hub.global_macro,"inspect",return_value=M):
            with patch.object(hub.consensus,"inspect",return_value=F):
                with patch.object(hub.mt4,"inspect",return_value=T):
                    with patch.object(hub.campaign,"inspect",return_value=c):
                        with self.assertRaises(InputError):
                            hub.inspect(asof_utc=ASOF,
                                        sessions=[("one",Path("out/a"))])

    def test_bad_campaign_order_permission_is_explicit_failure(self):
        c=dict(C,real_orders_permitted=True)
        with patch.object(hub.global_macro,"inspect",return_value=M):
            with patch.object(hub.consensus,"inspect",return_value=F):
                with patch.object(hub.mt4,"inspect",return_value=T):
                    with patch.object(hub.campaign,"inspect",return_value=c):
                        with self.assertRaises(InputError):
                            hub.inspect(asof_utc=ASOF,
                                        sessions=[("one",Path("out/a"))])

    def test_no_fake_price_ai_store_without_sessions(self):
        with self.assertRaises(InputError):
            hub.inspect(asof_utc=ASOF,observation_store=Path("out/store"))
        with self.assertRaises(InputError):
            hub.inspect(asof_utc=ASOF,ai_ledgers=[Path("out/ledger")])

    def test_old_news_snapshot_is_hold_not_fresh_future_schedule(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"manifest.json").write_text(json.dumps({
                "captured_at_utc_local_clock_unattested":
                    "2026-11-10T00:00:00Z"}))
            with patch.object(hub.global_macro,"inspect",return_value=M):
                with patch.object(hub.consensus,"inspect",return_value=F):
                    with patch.object(hub.mt4,"inspect",return_value=T):
                        r=hub.inspect(asof_utc=ASOF,
                                      official_news_bundle=folder)
        self.assertTrue(r["official_news_snapshot_older_than_24h"])
        self.assertIn("OFFICIAL_NEWS_SNAPSHOT_OLDER_THAN_24H",
                      r["unresolved_holds"])
        self.assertTrue(r["official_news_not_future_calendar"])
        self.assertFalse(r["real_orders_permitted"])

    def test_future_news_capture_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"manifest.json").write_text(json.dumps({
                "captured_at_utc_local_clock_unattested":
                    "2026-11-16T00:00:00Z"}))
            with patch.object(hub.global_macro,"inspect",return_value=M):
                with patch.object(hub.consensus,"inspect",return_value=F):
                    with patch.object(hub.mt4,"inspect",return_value=T):
                        with self.assertRaises(InputError):
                            hub.inspect(asof_utc=ASOF,
                                        official_news_bundle=folder)

    def test_verified_sources_but_source_truth_still_not_certified(self):
        with patch.object(hub.global_macro,"inspect",return_value=M):
            with patch.object(hub.consensus,"inspect",return_value=F):
                with patch.object(hub.mt4,"inspect",return_value=T):
                    r=hub.inspect(asof_utc=ASOF)
        self.assertFalse(
            r["publisher_clock_and_consensus_independently_authenticated"])
        self.assertIn(
            "COMPLETE_USD_EUR_JPY_FUTURE_CALENDAR_NOT_AUTHENTICATED",
            r["unresolved_holds"])

    def test_cli_no_inputs_safe_no_output_files(self):
        with patch("sys.stdout",new_callable=io.StringIO) as stream:
            rc=hub.main(["--asof-utc",ASOF])
        self.assertEqual(rc,0)
        r=json.loads(stream.getvalue())
        self.assertEqual(r["network_calls_this_run"],0)
        self.assertEqual(r["API_calls_this_run"],0)
        self.assertEqual(r["orders_sent_this_run"],0)
        self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_cli_out_explicit_write_once_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/"result.json"
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                rc=hub.main(["--asof-utc",ASOF,"--out",str(dest)])
            self.assertEqual(rc,0)
            original=dest.read_bytes()
            self.assertEqual(json.loads(original)["runtime_go_no_go"],"NO_GO")
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                rc=hub.main(["--asof-utc",ASOF,"--out",str(dest)])
            self.assertEqual(rc,2)
            self.assertEqual(original,dest.read_bytes())

    def test_cli_cannot_write_inside_immutable_source_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            evidence=root/"raw"
            evidence.mkdir()
            dest=evidence/"unsafe.json"
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                rc=hub.main(["--asof-utc",ASOF,
                             "--bls-snapshot-dir",str(evidence),
                             "--out",str(dest)])
            self.assertEqual(rc,2)
            self.assertFalse(dest.exists())

    def test_cli_missing_external_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"not-exist.json"
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                rc=hub.main(["--asof-utc",ASOF,
                             "--external-macro-file",str(src)])
            self.assertEqual(rc,2)
            r=json.loads(stream.getvalue())
            self.assertFalse(r["real_orders_permitted"])

    def test_cli_bad_json_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"garbage.json"
            src.write_text("hello world")
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                rc=hub.main(["--asof-utc",ASOF,
                             "--external-macro-file",str(src)])
            self.assertEqual(rc,2)
            self.assertIn("FAIL_CLOSED_NO_GO",stream.getvalue())

    def test_invalid_asof_rejected(self):
        with patch("sys.stdout",new_callable=io.StringIO) as stream:
            rc=hub.main(["--asof-utc","2026-11-13 11:49"])
        self.assertEqual(rc,2)
        self.assertIn("NO_GO",stream.getvalue())

    def test_cli_bad_session_label_rejected(self):
        with patch("sys.stdout",new_callable=io.StringIO) as stream:
            rc=hub.main(["--asof-utc",ASOF,
                         "--session","unsafe?=out/session"])
        self.assertEqual(rc,2)
        self.assertIn("FAIL_CLOSED_NO_GO",stream.getvalue())

    def test_cli_forecast_without_bls_does_not_use_fabricated_calendar(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"forecast.json"
            p.write_text('{"record": {}}')
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                rc=hub.main(["--asof-utc",ASOF,
                             "--forecast-archive",str(p)])
            self.assertEqual(rc,2)
            self.assertIn("FAIL_CLOSED_NO_GO",stream.getvalue())

    def test_cli_no_backround_download_even_if_no_sources(self):
        with patch.object(hub.global_macro,"inspect",
                          side_effect=InputError("offline invalid")):
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                rc=hub.main(["--asof-utc",ASOF])
        self.assertEqual(rc,2)
        self.assertIn("FAIL_CLOSED_NO_GO",stream.getvalue())


if __name__ == "__main__":
    unittest.main()
