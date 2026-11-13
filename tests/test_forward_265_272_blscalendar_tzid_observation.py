"""FWD-265..272: bounded BLS DTSTART metadata, no timezone inference."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from research import forward_bls_calendar as calendar
from research import forward_bls_calendar_diagnose as diagnosis

ASOF = "2026-11-12T03:00:00Z"


def sample(dtstart: str) -> bytes:
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        + dtstart + "\r\n"
        "SUMMARY:Private event headline must not be copied\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode("utf-8")


class TimezoneFormObservationTests(unittest.TestCase):
    def test_unrecognized_tzid_is_observed_without_conversion(self):
        raw = sample("DTSTART;TZID=US-Eastern:20261113T083000")
        report = diagnosis.diagnose(raw=raw, asof_utc=ASOF)
        self.assertEqual(report["status"],
                         "BLS_CALENDAR_DIAGNOSTIC_FAIL_CLOSED_NO_GO")
        self.assertEqual(report["reason_code"], "ICS_TIMEZONE_UNSUPPORTED")
        forms = report["dtstart_timezone_observation"]
        self.assertEqual(forms["forms"],
                         [{"form": "TZID=US-Eastern", "count": 1}])
        self.assertFalse(forms["event_titles_dates_or_body_included"])
        serialized = json.dumps(report)
        self.assertNotIn("Private event", serialized)
        self.assertNotIn("20261113T083000", serialized)
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")
        self.assertTrue(report["safety_hold_latched"])
        self.assertFalse(report["real_orders_permitted"])

    def test_floating_start_is_not_assigned_eastern_timezone(self):
        report = diagnosis.diagnose(
            raw=sample("DTSTART:20261113T083000"), asof_utc=ASOF)
        self.assertEqual(report["reason_code"], "ICS_TIMEZONE_UNSUPPORTED")
        self.assertEqual(
            report["dtstart_timezone_observation"]["forms"],
            [{"form": "FLOATING_NO_TZID", "count": 1}])

    def test_date_only_start_is_described_not_interpreted(self):
        report = diagnosis.diagnose(
            raw=sample("DTSTART;VALUE=DATE:20261113"), asof_utc=ASOF)
        self.assertEqual(report["reason_code"], "ICS_TIMEZONE_UNSUPPORTED")
        self.assertEqual(
            report["dtstart_timezone_observation"]["forms"],
            [{"form": "DATE_ONLY", "count": 1}])

    def test_unsafe_tzid_is_hashed_not_echoed(self):
        raw = sample("DTSTART;TZID=BAD|PRIVATE:20261113T083000")
        report = diagnosis.diagnose(raw=raw, asof_utc=ASOF)
        self.assertEqual(report["reason_code"], "ICS_TIMEZONE_UNSUPPORTED")
        form = report["dtstart_timezone_observation"]["forms"][0]["form"]
        self.assertTrue(form.startswith("TZID=OTHER_SHA256_"))
        self.assertNotIn("BAD|PRIVATE", json.dumps(report))

    def test_valid_utc_keeps_existing_strict_parser_result(self):
        report = diagnosis.diagnose(
            raw=sample("DTSTART:20261113T133000Z"), asof_utc=ASOF)
        self.assertEqual(report["status"],
                         "BLS_CALENDAR_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")
        self.assertNotIn("dtstart_timezone_observation", report)
        self.assertEqual(report["calendar_research_event_count"], 1)
        self.assertFalse(report["demo_orders_permitted"])

    def test_vtimezone_internal_dtstart_not_counted(self):
        raw = (
            b"BEGIN:VCALENDAR\nBEGIN:VTIMEZONE\n"
            b"TZID:US-Eastern\nBEGIN:STANDARD\n"
            b"DTSTART:20000101T020000\nEND:STANDARD\n"
            b"END:VTIMEZONE\nBEGIN:VEVENT\n"
            b"DTSTART;TZID=US-Eastern:20261113T083000\n"
            b"SUMMARY:No body\nEND:VEVENT\nEND:VCALENDAR\n"
        )
        report = diagnosis.diagnose(raw=raw, asof_utc=ASOF)
        self.assertEqual(
            report["dtstart_timezone_observation"]["dtstart_property_count"],
            1)
        self.assertEqual(
            report["dtstart_timezone_observation"]["forms"],
            [{"form": "TZID=US-Eastern", "count": 1}])

    def test_offline_metadata_observation_uses_no_network(self):
        raw = sample("DTSTART;TZID=EST:20261113T083000")
        with patch.object(calendar, "download",
                          side_effect=AssertionError("network used")):
            report = diagnosis.diagnose(raw=raw, asof_utc=ASOF)
        self.assertEqual(report["API_calls_this_run"], 0)
        self.assertFalse(report["automatic_retry_enabled"])
        self.assertFalse(report["report_or_original_journal_modified"])
        self.assertEqual(
            report["dtstart_timezone_observation"]["forms"],
            [{"form": "TZID=EST", "count": 1}])

    def test_network_path_uses_existing_fetch_once(self):
        raw = sample("DTSTART;TZID=Some East Coast Zone:20261113T083000")
        with patch.object(calendar, "download", return_value=raw) as fetch:
            report = diagnosis.diagnose(
                allow_network=True, asof_utc=ASOF)
        fetch.assert_called_once_with()
        self.assertEqual(report["reason_code"], "ICS_TIMEZONE_UNSUPPORTED")
        self.assertEqual(
            report["dtstart_timezone_observation"]["forms"],
            [{"form": "TZID=Some East Coast Zone", "count": 1}])
        self.assertEqual(report["actual_orders_sent"], 0)


if __name__ == "__main__":
    unittest.main()
