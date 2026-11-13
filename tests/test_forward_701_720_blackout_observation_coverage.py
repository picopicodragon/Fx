"""FWD-701..720: no-order blackout observation coverage from saved sources."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_blackout_observation_coverage as blackout
from research import forward_bls_dual_snapshot as bls
from research import forward_global_macro_evidence as global_macro
from research.offline_backtest import InputError

ASOF = "2026-11-20T15:30:00Z"
OBS = "2026-11-13T01:48:45Z"
EVENT = "2026-11-20T15:00:00Z"
HTML = (
    b"<!doctype html><html><head><title>Schedule of Selected Releases"
    b"</title></head><body><h1>November 2026</h1>"
    b"<table><tr><th>Date</th><th>Time</th><th>Release</th></tr>"
    b"<tr><td>Tuesday, November 03, 2026</td><td>10:00 AM</td>"
    b"<td>JOLTS for September</td></tr>"
    b"<tr><td>Thursday, November 05, 2026</td><td>08:30 AM</td>"
    b"<td>Productivity for Q3</td></tr>"
    b"<tr><td>Friday, November 06, 2026</td><td>08:30 AM</td>"
    b"<td>Employment Situation for October</td></tr>"
    b"<tr><td>Tuesday, November 10, 2026</td><td>08:30 AM</td>"
    b"<td>Consumer Price Index for October</td></tr>"
    b"<tr><td>Friday, November 20, 2026</td><td>10:00 AM</td>"
    b"<td>State Employment and Unemployment (Monthly) for October 2026</td></tr>"
    b"<tr><td>Friday, November 20, 2026</td><td>10:00 AM</td>"
    b"<td>Total Factor Productivity for Major Industries for Annual 2025</td>"
    b"</tr></table></body></html>"
)
ICS = (
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
    b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261120T100000\r\n"
    b"SUMMARY:State Employment and Unemployment (Monthly)\r\n"
    b"END:VEVENT\r\nEND:VCALENDAR\r\n"
)


def bundle(folder):
    manifest, report = bls.prepare(
        ics=ICS, html=HTML, observed_ics_utc=OBS,
        observed_html_utc=OBS, mode="LOCAL_COPY", days_forward=14)
    bls.write_bundle(out_dir=folder, ics=ICS, html=HTML,
                     manifest=manifest, report=report)
    return folder


def interval(first="2026-11-20T14:50:00Z",
             last="2026-11-20T15:10:00Z", label="one"):
    return {"label": label,
            "first_observation_utc": first,
            "last_observation_utc": last}


def external(currency="EUR"):
    excerpt = "Example earlier calendar release claim"
    return {
        "schema": global_macro.SCHEMA,
        "observed_at_utc": OBS,
        "horizon_days": 14,
        "events": [{
            "event_id": "eur-event-example",
            "currency": currency,
            "event_type": "MONETARY_POLICY",
            "title": "Example unverified EUR policy event",
            "scheduled_at_utc": EVENT,
            "calendar_source": {
                "source_url": "https://example.org/cal",
                "source_text": excerpt,
                "source_sha256": hashlib.sha256(
                    excerpt.encode()).hexdigest(),
                "published_at_utc": "2026-11-12T12:00:00Z",
                "captured_at_utc": OBS,
            },
            "consensus": None,
        }],
    }


class ResearchBlackoutCoverageTests(unittest.TestCase):
    def test_without_events_or_copied_quotes_is_hold(self):
        r = blackout.inspect(asof_utc=ASOF)
        self.assertEqual(r["unique_pair_blackout_research_window_count"], 0)
        self.assertEqual(r["windows_with_intersecting_copied_quotes"], 0)
        self.assertIn("NO_RESEARCH_BLACKOUT_EVENT_WINDOWS_FROM_VERIFIED_SOURCE",
                      r["unresolved_holds"])
        self.assertFalse(r["demonstrated_order_suppression"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_bls_pair_windows_without_mt4_overlap_are_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            root = bundle(Path(td)/"bls")
            r = blackout.inspect(asof_utc=ASOF, bls_snapshot_dir=root)
        self.assertEqual(r["unique_pair_blackout_research_window_count"], 2)
        self.assertEqual(r["windows_with_intersecting_copied_quotes"], 0)
        self.assertEqual(r["windows_without_intersecting_copied_quotes"], 2)
        self.assertIn("BLS_HTML_ONLY_EVENTS_NOT_IN_REHEARSED_ICS_WINDOWS",
                      r["unresolved_holds"])
        self.assertTrue(r["bls_html_ics_disagreement_unresolved"])
        self.assertFalse(r["rehearsal_is_live_blackout_or_release_control"])

    def test_copied_observer_quotes_intersect_two_bls_pair_windows(self):
        with tempfile.TemporaryDirectory() as td:
            root = bundle(Path(td)/"bls")
            r = blackout.inspect(
                asof_utc=ASOF, bls_snapshot_dir=root,
                copied_sessions=[interval()])
        self.assertEqual(r["unique_pair_blackout_research_window_count"], 2)
        self.assertEqual(r["windows_with_intersecting_copied_quotes"], 2)
        self.assertEqual(r["pair_windows_with_copied_quote_overlap_unattested"],
                         {"USD/JPY": 1, "EUR/JPY": 0, "EUR/USD": 1})
        self.assertEqual(r["research_window_previews_unattested"][0][
            "blackout_start_utc_research_only"], "2026-11-20T14:45:00Z")
        self.assertFalse(r["demonstrated_order_suppression"])
        self.assertFalse(r["verified_order_recovery"])

    def test_boundary_touch_at_plus15min_counts_as_quote_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            root = bundle(Path(td)/"bls")
            r = blackout.inspect(
                asof_utc=ASOF, bls_snapshot_dir=root,
                copied_sessions=[interval(
                    first="2026-11-20T15:15:00Z",
                    last="2026-11-20T15:20:00Z")])
        self.assertEqual(r["windows_with_intersecting_copied_quotes"], 2)
        self.assertFalse(r["real_orders_permitted"])

    def test_no_overlap_when_quotes_are_outside_window(self):
        with tempfile.TemporaryDirectory() as td:
            root = bundle(Path(td)/"bls")
            r = blackout.inspect(
                asof_utc=ASOF, bls_snapshot_dir=root,
                copied_sessions=[interval(
                    first="2026-11-20T15:15:01Z",
                    last="2026-11-20T15:20:00Z")])
        self.assertEqual(r["windows_with_intersecting_copied_quotes"], 0)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_external_eur_event_research_scopes_two_pairs(self):
        r = blackout.inspect(
            asof_utc=ASOF,
            external_observations=external(),
            copied_sessions=[interval()])
        self.assertEqual(r["unique_pair_blackout_research_window_count"], 2)
        self.assertEqual(r["pair_windows_with_copied_quote_overlap_unattested"],
                         {"USD/JPY": 0, "EUR/JPY": 1, "EUR/USD": 1})
        self.assertEqual(r["external_event_observations_supplied"], 1)
        self.assertFalse(r["real_orders_permitted"])

    def test_cross_source_same_pair_and_time_deduped_without_authentication(self):
        with tempfile.TemporaryDirectory() as td:
            root = bundle(Path(td)/"bls")
            r = blackout.inspect(
                asof_utc=ASOF, bls_snapshot_dir=root,
                external_observations=external(),
                copied_sessions=[interval()])
        self.assertEqual(r["unique_pair_blackout_research_window_count"], 3)
        usd_eur = next(x for x in r["research_window_previews_unattested"]
                       if x["pair"] == "EUR/USD")
        self.assertEqual(usd_eur["source_families_unattested"],
                         ["BLS_ICS", "EXTERNAL_SOURCE_UNATTESTED"])
        self.assertFalse(usd_eur["real_order_stop_evidence"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_future_dated_copied_observer_interval_rejected(self):
        with self.assertRaises(InputError):
            blackout.inspect(asof_utc=ASOF,
                             copied_sessions=[interval(
                                 first="2026-11-21T00:00:00Z",
                                 last="2026-11-21T00:30:00Z")])

    def test_backward_copied_session_time_rejected(self):
        with self.assertRaises(InputError):
            blackout.inspect(asof_utc=ASOF,
                             copied_sessions=[interval(
                                 first="2026-11-20T15:10:00Z",
                                 last="2026-11-20T14:50:00Z")])

    def test_duplicate_session_label_rejected(self):
        with self.assertRaises(InputError):
            blackout.inspect(asof_utc=ASOF,
                             copied_sessions=[interval(), interval()])

    def test_more_than_24_session_intervals_rejected(self):
        with self.assertRaises(InputError):
            blackout.inspect(asof_utc=ASOF,
                             copied_sessions=[interval(label="s"+str(n))
                                              for n in range(25)])

    def test_tampered_bls_original_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = bundle(Path(td)/"bls")
            with (root/"bls.ics").open("ab") as f:
                f.write(b"spoof")
            with self.assertRaises(InputError):
                blackout.inspect(asof_utc=ASOF, bls_snapshot_dir=root)

    def test_invalid_external_source_hash_rejected(self):
        p = external()
        p["events"][0]["calendar_source"]["source_sha256"] = "f"*64
        with self.assertRaises(InputError):
            blackout.inspect(asof_utc=ASOF, external_observations=p)

    def test_one_copied_session_without_events_proves_nothing(self):
        r = blackout.inspect(asof_utc=ASOF, copied_sessions=[interval()])
        self.assertEqual(r["unique_pair_blackout_research_window_count"], 0)
        self.assertFalse(r["rehearsal_is_live_blackout_or_release_control"])
        self.assertIn("NO_RESEARCH_BLACKOUT_EVENT_WINDOWS_FROM_VERIFIED_SOURCE",
                      r["unresolved_holds"])


if __name__ == "__main__":
    unittest.main()
