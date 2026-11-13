"""FWD-409..440: synthetic global macro/consensus provenance and NO_GO tests."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_global_macro_evidence as board
from research import forward_macro_integrated_readiness as integrated
from research.offline_backtest import InputError

ASOF = "2026-11-13T02:49:10Z"
CAPTURE = "2026-11-13T02:48:45Z"
FUTURE = "2026-11-20T15:00:00Z"


def provenance(text="Release schedule", *,
               captured=CAPTURE, published="2026-11-12T12:00:00Z",
               url="https://example.org/research/calendar"):
    return {
        "source_url": url,
        "source_text": text,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "published_at_utc": published,
        "captured_at_utc": captured,
    }


def event(currency, start, *, consensus=False):
    record = {
        "event_id": currency.lower() + "-observed-202611",
        "currency": currency,
        "event_type": "INFLATION" if currency == "EUR" else "MONETARY_POLICY",
        "title": currency + " placeholder scheduled announcement",
        "scheduled_at_utc": start,
        "calendar_source": provenance(currency + " calendar observed"),
        "consensus": None,
    }
    if consensus:
        record["consensus"] = {
            "value": "2.7",
            "unit": "percent",
            "source": provenance(currency + " consensus 2.7 percent",
                                 url="https://data.example.org/consensus"),
        }
    return record


def envelope():
    return {
        "schema": board.SCHEMA,
        "observed_at_utc": CAPTURE,
        "horizon_days": 14,
        "events": [
            event("USD", FUTURE, consensus=True),
            event("EUR", "2026-11-19T10:00:00Z"),
            event("JPY", "2026-11-18T01:00:00Z"),
        ],
    }


class MultiRegionMacroTests(unittest.TestCase):
    def test_three_currency_events_and_partial_consensus(self):
        r = board.inspect_observations(envelope(), asof_utc=ASOF)
        self.assertEqual(r["external_event_observations_supplied"], 3)
        self.assertEqual(r["external_by_currency"],
                         {"USD": 1, "EUR": 1, "JPY": 1})
        self.assertEqual(r["external_with_consensus_count"], 1)
        self.assertEqual(r["external_missing_consensus_count"], 2)
        self.assertEqual(r["event_evidence_preview"][0][
            "pair_scope_advisory_only"], ["USD/JPY", "EUR/USD"])
        self.assertIn("EXTERNAL_EVENT_PRE_RELEASE_CONSENSUS_MISSING",
                      r["unresolved_holds"])
        self.assertFalse(r["independent_event_calendar_coverage_proven"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertTrue(r["safety_hold_latched"])

    def test_source_integrity_does_not_certify_consensus_source(self):
        r = board.inspect_observations(envelope(), asof_utc=ASOF)
        self.assertFalse(r[
            "external_evidence_values_and_times_independently_authenticated"])
        self.assertIn("example.org", r["unverified_source_hosts"])
        self.assertTrue(r["no_orders_can_be_derived_from_this_observation"])

    def test_all_forecasts_present_still_no_go(self):
        p = envelope()
        for e in p["events"]:
            e["consensus"] = {
                "value": "1.1", "unit": "percent",
                "source": provenance("Consensus estimate 1.1 percent"),
            }
        r = board.inspect_observations(p, asof_utc=ASOF)
        self.assertEqual(r["external_missing_consensus_count"], 0)
        self.assertFalse(r["real_orders_permitted"])
        self.assertIn("GLOBAL_MACRO_EVENT_CALENDAR_COVERAGE_UNATTESTED",
                      r["unresolved_holds"])

    def test_missing_region_is_a_hold_not_a_fake_empty_calendar(self):
        p = envelope()
        p["events"] = [p["events"][0]]
        r = board.inspect_observations(p, asof_utc=ASOF)
        self.assertIn("NO_EUR_EVENT_OBSERVATION", r["unresolved_holds"])
        self.assertIn("NO_JPY_EVENT_OBSERVATION", r["unresolved_holds"])
        self.assertEqual(r["external_by_currency"]["EUR"], 0)

    def test_empty_list_is_explicit_no_go(self):
        p = envelope()
        p["events"] = []
        r = board.inspect_observations(p, asof_utc=ASOF)
        self.assertIn("NO_EXTERNAL_MACRO_EVENT_OBSERVATIONS",
                      r["unresolved_holds"])
        self.assertFalse(r["demo_orders_permitted"])

    def test_content_hash_tampering_rejected(self):
        p = envelope()
        p["events"][0]["calendar_source"]["source_text"] = "changed"
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_published_after_capture_rejected(self):
        p = envelope()
        p["events"][0]["calendar_source"][
            "published_at_utc"] = "2026-11-14T12:00:00Z"
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_capture_after_observation_rejected(self):
        p = envelope()
        p["events"][0]["calendar_source"][
            "captured_at_utc"] = "2026-11-14T12:00:00Z"
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_consensus_inside_15_minute_blackout_rejected(self):
        p = envelope()
        p["events"][0]["consensus"]["source"] = provenance(
            "last minute value", captured="2026-11-20T14:50:00Z",
            published="2026-11-19T11:00:00Z")
        # Later observation is necessary for realistic late capture.
        p["observed_at_utc"] = "2026-11-20T14:52:00Z"
        # Other events have already occurred, so isolate the USD event.
        p["events"] = [p["events"][0]]
        with self.assertRaises(InputError):
            board.inspect_observations(
                p, asof_utc="2026-11-20T14:52:01Z")

    def test_consensus_was_after_release_rejected(self):
        p = envelope()
        p["events"][0]["consensus"]["source"] = provenance(
            "hindsight", captured="2026-11-20T16:00:00Z",
            published="2026-11-20T15:30:00Z")
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_duplicate_id_and_slot_both_rejected(self):
        p = envelope()
        p["events"].append(copy.deepcopy(p["events"][0]))
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)
        p = envelope()
        x = copy.deepcopy(p["events"][0])
        x["event_id"] = "new-id"
        p["events"].append(x)
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_not_https_source_rejected(self):
        p = envelope()
        p["events"][0]["calendar_source"][
            "source_url"] = "http://example.org/source"
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_nonfinite_consensus_rejected(self):
        p = envelope()
        p["events"][0]["consensus"]["value"] = "NaN"
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_calendar_item_beyond_horizon_rejected(self):
        p = envelope()
        p["events"][0]["scheduled_at_utc"] = "2026-12-31T12:00:00Z"
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_utc_offsets_or_milliseconds_rejected(self):
        p = envelope()
        p["observed_at_utc"] = "2026-11-13T11:48:45+09:00"
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)
        with self.assertRaises(InputError):
            board.inspect_observations(envelope(), asof_utc="2026-11-13T02:49:10.000Z")

    def test_stale_evidence_explicitly_held(self):
        r = board.inspect_observations(
            envelope(), asof_utc="2026-11-15T12:00:00Z")
        self.assertTrue(r["external_observation_older_than_24h"])
        self.assertIn("EXTERNAL_MACRO_OBSERVATION_OLDER_THAN_24H",
                      r["unresolved_holds"])

    def test_oversized_event_count_rejected(self):
        p = envelope()
        p["events"] = [event("USD", FUTURE)] * 65
        with self.assertRaises(InputError):
            board.inspect_observations(p, asof_utc=ASOF)

    def test_combined_without_any_sources_remains_no_go(self):
        r = board.inspect(asof_utc=ASOF)
        self.assertFalse(r["bls_snapshot_supplied_and_integrity_checked"])
        self.assertEqual(r["external_event_observations_supplied"], 0)
        self.assertIn("NO_VERIFIED_BLS_DUAL_FORMAT_SOURCE_BUNDLE",
                      r["unresolved_holds"])
        self.assertFalse(r["real_orders_permitted"])

    def test_combined_source_and_external_holds_are_union(self):
        stub = {
            "html_ics_slot_count_disagreement": True,
            "missing_html_slot_instances": 1,
            "unresolved_holds": [
                "BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT",
                "POINT_IN_TIME_CONSENSUS_EVIDENCE_MISSING"],
            "next_research_actions": ["REVIEW_SAVED_HTML_ICS_RELEASE_DISCREPANCY"],
        }
        with patch.object(board.bls_gate, "inspect", return_value=stub) as b:
            r = board.inspect(
                asof_utc=ASOF, bls_snapshot_dir=Path("saved/bundle"),
                external_observations=envelope())
        b.assert_called_once()
        self.assertEqual(r["bls_html_only_missing_slot_instances"], 1)
        self.assertTrue(r["bls_html_ics_disagreement"])
        self.assertIn("BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT",
                      r["unresolved_holds"])
        self.assertIn("EXTERNAL_EVENT_PRE_RELEASE_CONSENSUS_MISSING",
                      r["unresolved_holds"])
        self.assertFalse(r["real_orders_permitted"])

    def test_no_bundle_does_not_falsify_original_bls_snapshot(self):
        r = board.inspect(asof_utc=ASOF, external_observations=envelope())
        self.assertIsNone(r["bls_html_ics_disagreement"])
        self.assertFalse(r["bls_snapshot_supplied_and_integrity_checked"])
        self.assertEqual(r["external_event_observations_supplied"], 3)

    def test_cli_file_read_only_and_no_network(self):
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / "external.json"
            path.write_text(json.dumps(envelope()), encoding="utf-8")
            before = path.read_bytes()
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                rc = board.main([
                    "--asof-utc", ASOF, "--external-macro-file", str(path)])
            self.assertEqual(rc, 0)
            r = json.loads(stream.getvalue())
            self.assertEqual(r["files_written_this_run"], 0)
            self.assertEqual(r["network_calls_this_run"], 0)
            self.assertEqual(r["API_calls_this_run"], 0)
            self.assertEqual(r["actual_orders_sent"], 0)
            self.assertFalse(r["demo_orders_permitted"])
            self.assertEqual(path.read_bytes(), before)

    def test_cli_invalid_missing_file_safe(self):
        with tempfile.TemporaryDirectory() as dirname:
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                rc = board.main([
                    "--asof-utc", ASOF,
                    "--external-macro-file",
                    str(Path(dirname) / "absent.json")])
            self.assertEqual(rc, 2)
            r = json.loads(stream.getvalue())
            self.assertEqual(r["status"], "GLOBAL_MACRO_EVIDENCE_FAIL_CLOSED_NO_GO")
            self.assertFalse(r["real_orders_permitted"])


class IntegratedBoardUseTests(unittest.TestCase):
    CAMPAIGN = {
        "unresolved_warnings_and_safety_holds": ["BROKER_NOT_VERIFIED"],
        "next_research_actions": ["VERIFY_BROKER_CLOCK"],
        "price_csv_count": 114,
        "complete_cycle_count": 0,
        "observed_macro_event_count": 0,
        "review_count": 0,
        "descriptive_two_snapshot_mark_count": 0,
    }

    def test_integrated_optional_external_evidence_propagates_holds(self):
        with patch.object(integrated, "campaign", return_value=self.CAMPAIGN):
            r = integrated.inspect(
                [], asof_utc=ASOF,
                external_macro_observations=envelope())
        self.assertTrue(r["external_macro_evidence_supplied"])
        self.assertEqual(r["external_macro_event_count"], 3)
        self.assertEqual(r["external_macro_by_currency"],
                         {"USD": 1, "EUR": 1, "JPY": 1})
        self.assertEqual(r["external_macro_missing_consensus_count"], 2)
        self.assertIn("EXTERNAL_EVENT_PRE_RELEASE_CONSENSUS_MISSING",
                      r["unresolved_holds"])
        self.assertIn("BROKER_NOT_VERIFIED", r["unresolved_holds"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertTrue(r["safety_hold_latched"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_integrated_without_external_input_keeps_legacy_shape(self):
        with patch.object(integrated, "campaign", return_value=self.CAMPAIGN):
            r = integrated.inspect([], asof_utc=ASOF)
        self.assertFalse(r["external_macro_evidence_supplied"])
        self.assertEqual(r["external_macro_event_count"], 0)
        self.assertIn("NO_BLS_CALENDAR_RESEARCH_SNAPSHOT",
                      r["unresolved_holds"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_integrated_invalid_data_fail_closed_before_campaign(self):
        bad = envelope()
        bad["events"][0]["consensus"]["value"] = "Infinity"
        with patch.object(integrated, "campaign") as f:
            with self.assertRaises(InputError):
                integrated.inspect(
                    [], asof_utc=ASOF, external_macro_observations=bad)
            f.assert_not_called()


if __name__ == "__main__":
    unittest.main()
