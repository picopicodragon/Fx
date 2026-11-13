"""FWD-393..408: propagate verified BLS provenance/consensus holds to integrated board."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_macro_integrated_readiness as integrated
from research.offline_backtest import InputError

TIME = "2026-11-13T02:49:10Z"
ICS_SHA = "a" * 64
BUNDLE = Path("out/mock-saved-bundle")
ORIGINAL = {
    "status": "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
    "calendar_sha256": ICS_SHA,
    "events": [
        {"title": "State Employment and Unemployment (Monthly)",
         "scheduled_at_utc": "2026-11-20T15:00:00Z"}
    ],
}
SOURCE = {
    "html_ics_slot_count_disagreement": True,
    "missing_html_slot_instances": 1,
    "snapshot_older_than_24h": False,
    "calendar_ics_sha256": ICS_SHA,
    "unresolved_holds": [
        "BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT",
        "POINT_IN_TIME_CONSENSUS_EVIDENCE_MISSING",
        "FULL_FX_MACRO_CALENDAR_NOT_ATTESTED",
    ],
    "next_research_actions": [
        "CAPTURE_PRE_RELEASE_CONSENSUS_WITH_TIMESTAMP_EVIDENCE",
        "ESTABLISH_INDEPENDENT_ECONOMIC_CALENDAR_COVERAGE",
    ],
}
CAMPAIGN = {
    "unresolved_warnings_and_safety_holds": ["BROKER_NOT_REVIEWED"],
    "next_research_actions": ["VERIFY_MT4_ACCOUNT_CLOCK_RISK_AND_ORDER_DISABLE_CONTROLS"],
    "price_csv_count": 114,
    "complete_cycle_count": 0,
    "observed_macro_event_count": 0,
    "review_count": 0,
    "descriptive_two_snapshot_mark_count": 0,
}
WINDOWS = {
    "data_holds": ["BLS_CALENDAR_NOT_COMPLETE_FX_EVENT_COVERAGE"],
    "calendar_stale": False,
    "windows": [
        {"title_unverified": "State Employment and Unemployment (Monthly)",
         "scheduled_at_utc_unverified": "2026-11-20T15:00:00Z"}
    ],
    "active_research_blackout_count": 0,
    "calendar_sha256_self_reported": ICS_SHA,
}


class IntegratedSourceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(integrated, "campaign", return_value=CAMPAIGN),
            patch.object(integrated, "windows", return_value=WINDOWS),
            patch.object(integrated.source_gate, "inspect", return_value=SOURCE),
            patch.object(integrated.bls_integrity, "verify", return_value={}),
            patch.object(integrated.bls_integrity, "_bytes",
                         return_value=json.dumps(ORIGINAL).encode()),
        ]
        self.mocks = [p.start() for p in self.patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def run_board(self, **kwargs):
        return integrated.inspect(
            [("session1", Path("out/test-session"))],
            asof_utc=TIME, **kwargs)

    def test_new_verified_bundle_sets_calendar_from_original(self):
        r = self.run_board(bls_snapshot_dir=BUNDLE)
        self.assertTrue(r["bls_original_source_bundle_verified"])
        self.assertTrue(r["calendar_supplied"])
        self.assertEqual(r["scheduled_bls_event_count"], 1)
        self.assertEqual(r["bls_saved_calendar_ics_sha256"], ICS_SHA)
        self.assertEqual(r["price_csv_count"], 114)
        self.assertEqual(r["macro_event_count"], 0)
        self.assertFalse(r["demo_orders_permitted"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(r["safety_hold_latched"])
        self.mocks[2].assert_called_once_with(
            BUNDLE, asof_utc=TIME, forecast_archive=None)

    def test_concrete_disagreement_and_consensus_missing_become_holds(self):
        r = self.run_board(bls_snapshot_dir=BUNDLE)
        self.assertTrue(r["bls_html_ics_schedule_disagreement"])
        self.assertEqual(r["bls_html_only_missing_slot_instances"], 1)
        self.assertIn("BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT",
                      r["unresolved_holds"])
        self.assertIn("POINT_IN_TIME_CONSENSUS_EVIDENCE_MISSING",
                      r["unresolved_holds"])
        self.assertIn("BROKER_NOT_REVIEWED", r["unresolved_holds"])
        self.assertFalse(r["independent_economic_calendar_coverage_certified"])
        self.assertFalse(r["pre_release_consensus_source_authenticity_certified"])

    def test_tasks_deduplicated_preserving_order(self):
        r = self.run_board(bls_snapshot_dir=BUNDLE)
        tasks = r["next_research_actions"]
        self.assertEqual(len(tasks), len(set(tasks)))
        self.assertIn("ESTABLISH_INDEPENDENT_ECONOMIC_CALENDAR_COVERAGE",
                      tasks)
        self.assertIn("ARCHIVE_POINT_IN_TIME_CONSENSUS_BEFORE_BLACKOUT",
                      tasks)

    def test_stale_snapshot_is_conveyed_without_enabling_orders(self):
        stale = dict(SOURCE, snapshot_older_than_24h=True,
                     unresolved_holds=SOURCE["unresolved_holds"]+[
                         "BLS_SAVED_SNAPSHOT_OLDER_THAN_24H"])
        self.mocks[2].return_value = stale
        r = self.run_board(bls_snapshot_dir=BUNDLE)
        self.assertTrue(r["bls_snapshot_older_than_24h"])
        self.assertIn("BLS_SAVED_SNAPSHOT_OLDER_THAN_24H",
                      r["unresolved_holds"])
        self.assertFalse(r["demo_orders_permitted"])

    def test_even_apparent_slot_match_does_not_enable_go(self):
        self.mocks[2].return_value = dict(
            SOURCE, html_ics_slot_count_disagreement=False,
            missing_html_slot_instances=0)
        r = self.run_board(bls_snapshot_dir=BUNDLE)
        self.assertFalse(r["bls_html_ics_schedule_disagreement"])
        self.assertFalse(r["independent_economic_calendar_coverage_certified"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_without_bundle_legacy_behavior_remains_compatible(self):
        r = self.run_board(calendar=ORIGINAL)
        self.assertFalse(r["bls_original_source_bundle_verified"])
        self.assertIsNone(r["bls_html_ics_schedule_disagreement"])
        self.assertIsNone(r["bls_html_only_missing_slot_instances"])
        self.assertTrue(r["calendar_supplied"])
        self.assertIn("NO_PRE_RELEASE_FORECAST_CAPTURE_PROVIDED",
                      r["unresolved_holds"])
        self.mocks[2].assert_not_called()

    def test_without_calendar_or_bundle_holds_calendar_missing(self):
        r = self.run_board()
        self.assertFalse(r["calendar_supplied"])
        self.assertIn("NO_BLS_CALENDAR_RESEARCH_SNAPSHOT",
                      r["unresolved_holds"])
        self.assertEqual(r["scheduled_bls_event_count"], 0)
        self.mocks[1].assert_not_called()

    def test_matching_explicit_calendar_is_allowed(self):
        r = self.run_board(
            bls_snapshot_dir=BUNDLE,
            calendar=json.loads(json.dumps(ORIGINAL)))
        self.assertTrue(r["bls_original_source_bundle_verified"])

    def test_conflicting_calendar_is_rejected_before_campaign(self):
        changed = dict(ORIGINAL, calendar_sha256="b" * 64)
        with self.assertRaisesRegex(InputError, "disagrees"):
            self.run_board(bls_snapshot_dir=BUNDLE, calendar=changed)
        self.mocks[0].assert_not_called()

    def test_altered_event_with_same_ics_digest_is_rejected(self):
        changed = json.loads(json.dumps(ORIGINAL))
        changed["events"][0]["title"] = "Unrelated event"
        with self.assertRaisesRegex(InputError, "disagrees"):
            self.run_board(bls_snapshot_dir=BUNDLE, calendar=changed)

    def test_malformed_source_bundle_rejected_early(self):
        self.mocks[2].side_effect = InputError("snapshot integrity invalid")
        with self.assertRaises(InputError):
            self.run_board(bls_snapshot_dir=BUNDLE)
        self.mocks[0].assert_not_called()

    def test_corrupted_source_calendar_does_not_get_used(self):
        self.mocks[4].return_value = b"[]"
        with self.assertRaisesRegex(InputError, "root invalid"):
            self.run_board(bls_snapshot_dir=BUNDLE)

    def test_forecast_supplied_without_any_calendar_must_fail(self):
        with self.assertRaisesRegex(InputError, "needs matching"):
            self.run_board(forecast_archive={"record": "unknown"})

    def test_valid_forecast_match_remains_unattested(self):
        record = {
            "calendar_report_sha256_self_reported": ICS_SHA,
            "event_title_unverified": ORIGINAL["events"][0]["title"],
            "scheduled_at_utc_unverified":
                ORIGINAL["events"][0]["scheduled_at_utc"],
        }
        with patch.object(integrated, "verify_forecast",
                          return_value=record):
            r = self.run_board(
                bls_snapshot_dir=BUNDLE, forecast_archive={"trusted": False})
        self.assertTrue(r["forecast_archive_matches_current_schedule"])
        self.assertTrue(r["pre_release_forecast_archive_supplied"])
        self.assertFalse(r["pre_release_consensus_source_authenticity_certified"])
        self.assertFalse(r["real_orders_permitted"])
        self.mocks[2].assert_called_once_with(
            BUNDLE, asof_utc=TIME, forecast_archive={"trusted": False})

    def test_mismatched_forecast_keeps_consensus_hold(self):
        record = {
            "calendar_report_sha256_self_reported": "f" * 64,
            "event_title_unverified": ORIGINAL["events"][0]["title"],
            "scheduled_at_utc_unverified":
                ORIGINAL["events"][0]["scheduled_at_utc"],
        }
        with patch.object(integrated, "verify_forecast", return_value=record):
            r = self.run_board(
                bls_snapshot_dir=BUNDLE, forecast_archive={"trusted": False})
        self.assertFalse(r["forecast_archive_matches_current_schedule"])
        self.assertIn("CONSENSUS_ARCHIVE_CALENDAR_IDENTITY_CHANGED",
                      r["unresolved_holds"])

    def test_cli_invalid_bundle_has_no_outfile_and_is_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "report.json"
            self.mocks[2].side_effect = InputError("invalid snapshot")
            with patch.object(integrated, "_parse_labeled_entries",
                              return_value={"one": Path(td)}):
                with patch("sys.stdout", new_callable=io.StringIO) as buf:
                    rc = integrated.main([
                        "--session", "one="+td,
                        "--bls-snapshot-dir", str(BUNDLE),
                        "--asof-utc", TIME, "--out", str(out)])
            self.assertEqual(rc, 2)
            self.assertFalse(out.exists())
            data = json.loads(buf.getvalue())
            self.assertEqual(data["status"], "FAIL_CLOSED")
            self.assertEqual(data["runtime_go_no_go"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
