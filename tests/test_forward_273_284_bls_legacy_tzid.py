"""FWD-273..284: provisional legacy BLS TZID, guarded New York conversion."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_calendar as cal
from research import forward_bls_calendar_diagnose as diag
from research.offline_backtest import InputError

ASOF = "2026-11-01T00:00:00Z"


def ics(dtstart: str, title: str = "Producer Price Index") -> bytes:
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n" + dtstart + "\r\n"
        "SUMMARY:" + title + "\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode("utf-8")


class BlsEasternTimeCompatibilityTests(unittest.TestCase):
    def test_winter_legacy_tzid_matches_us_eastern(self):
        item = ics("DTSTART;TZID=US-Eastern:20261113T083000")
        r = cal.parse_calendar(item, asof_utc=ASOF)
        self.assertEqual(r["event_count"], 1)
        self.assertEqual(r["events"][0]["scheduled_at_utc"],
                         "2026-11-13T13:30:00Z")
        self.assertTrue(r["calendar_timezone_alias_us_eastern_assumed"])
        self.assertFalse(r["release_time_independently_verified"])
        self.assertFalse(r["source_authenticity_verified"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(r["safety_hold_latched"])

    def test_summer_legacy_tzid_has_utc_minus_four(self):
        r = cal.parse_calendar(
            ics("DTSTART;TZID=US-Eastern:20260715T083000"),
            asof_utc="2026-07-15T11:00:00Z")
        self.assertEqual(r["events"][0]["scheduled_at_utc"],
                         "2026-07-15T12:30:00Z")

    def test_utc_and_existing_timezone_conversion_not_changed(self):
        inputs = (
            "DTSTART;TZID=US-Eastern:20261113T083000",
            "DTSTART;TZID=US/Eastern:20261113T083000",
            "DTSTART;TZID=America/New_York:20261113T083000",
            "DTSTART:20261113T133000Z",
        )
        for date in inputs:
            with self.subTest(date=date):
                r = cal.parse_calendar(ics(date), asof_utc=ASOF)
                self.assertEqual(r["events"][0]["scheduled_at_utc"],
                                 "2026-11-13T13:30:00Z")

    def test_legacy_timezone_is_exact_case_sensitive(self):
        for tzid in ("US-eastern", "us-Eastern", "US_Eastern",
                     "US-Eastern ", "US/Easter", "US-Central",
                     "GMT-5", "EST", "America/Chicago"):
            with self.subTest(tzid=tzid):
                with self.assertRaisesRegex(
                        InputError, "unsupported or missing"):
                    cal.parse_calendar(
                        ics("DTSTART;TZID=" + tzid + ":20261113T083000"),
                        asof_utc=ASOF)

    def test_floating_and_date_only_do_not_inherit_eastern(self):
        for prop in ("DTSTART:20261113T083000",
                     "DTSTART;VALUE=DATE:20261113"):
            with self.subTest(prop=prop):
                with self.assertRaises(InputError):
                    cal.parse_calendar(ics(prop), asof_utc=ASOF)

    def test_dst_nonexistent_and_ambiguous_legacy_times_still_fail(self):
        for date in ("20260308T023000", "20261101T013000"):
            with self.subTest(date=date):
                with self.assertRaisesRegex(InputError, "DST"):
                    cal.parse_calendar(
                        ics("DTSTART;TZID=US-Eastern:" + date),
                        asof_utc=ASOF)

    def test_timezone_plus_utc_z_is_rejected(self):
        with self.assertRaisesRegex(InputError, "contradictory"):
            cal.parse_calendar(
                ics("DTSTART;TZID=US-Eastern:20261113T133000Z"),
                asof_utc=ASOF)

    def test_parser_still_rejects_duplicate_event_date(self):
        data = ics("DTSTART;TZID=US-Eastern:20261113T083000")
        data = data.replace(
            b"SUMMARY:Producer Price Index",
            b"DTSTART;TZID=US-Eastern:20261114T083000\r\n"
            b"SUMMARY:Producer Price Index")
        with self.assertRaisesRegex(InputError, "repeated ICS event property"):
            cal.parse_calendar(data, asof_utc=ASOF)

    def test_diagnostic_now_recognizes_legacy_as_research_only(self):
        raw = ics("DTSTART;TZID=US-Eastern:20261113T083000")
        with patch.object(cal, "download",
                          side_effect=AssertionError("network used")):
            report = diag.diagnose(raw=raw, asof_utc=ASOF)
        self.assertEqual(report["stage"], "PREFLIGHT")
        self.assertEqual(report["status"],
                         "BLS_CALENDAR_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")
        self.assertEqual(report["calendar_research_event_count"], 1)
        self.assertFalse(report["real_orders_permitted"])
        self.assertFalse(report["demo_orders_permitted"])
        self.assertNotIn("dtstart_timezone_observation", report)

    def test_offline_ics_cli_writes_only_fresh_output(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "calendar.ics"
            out = Path(temp) / "calendar.json"
            source.write_bytes(ics("DTSTART;TZID=US-Eastern:20261113T083000"))
            with patch.object(cal, "download",
                              side_effect=AssertionError("network used")):
                with patch("sys.stdout", new_callable=io.StringIO):
                    rc = cal.main([
                        "--ics-file", str(source), "--out", str(out),
                        "--asof-utc", ASOF])
            self.assertEqual(rc, 0)
            r = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(r["release_time_independently_verified"])
            self.assertTrue(r["calendar_timezone_alias_us_eastern_assumed"])
            self.assertEqual(r["events"][0]["scheduled_at_utc"],
                             "2026-11-13T13:30:00Z")
            self.assertEqual(set(Path(temp).iterdir()), {source, out})

    def test_date_after_dst_fall_back_is_unambiguous(self):
        r = cal.parse_calendar(
            ics("DTSTART;TZID=US-Eastern:20261101T023000"),
            asof_utc="2026-11-01T05:00:00Z")
        self.assertEqual(r["events"][0]["scheduled_at_utc"],
                         "2026-11-01T07:30:00Z")

    def test_summer_start_and_winter_start_research_gates(self):
        raw = ics("DTSTART;TZID=US-Eastern:20261113T083000")
        report = cal.parse_calendar(raw, asof_utc=ASOF)
        self.assertTrue(report["calendar_timezone_alias_us_eastern_assumed"])
        self.assertFalse(report["calendar_covers_all_fx_events"])
        self.assertFalse(report["release_content_or_consensus_verified"])
        self.assertFalse(report["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
