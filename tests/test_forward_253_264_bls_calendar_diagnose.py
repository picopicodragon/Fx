"""FWD-253..264: classified BLS ICS failures are read-only and fail-closed."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_calendar as calendar
from research import forward_bls_calendar_diagnose as diagnostic


ASOF = "2026-11-12T03:00:00Z"


def ics(*, date="20261113T083000", key="DTSTART;TZID=America/New_York",
        title="Producer Price Index"):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n" + key + ":" + date +
        "\r\nSUMMARY:" + title +
        "\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode("utf-8")


class CalendarDiagnosticsTests(unittest.TestCase):
    def test_valid_offline_calendar_parses_without_side_effect(self):
        with patch.object(calendar, "download",
                          side_effect=AssertionError("network attempted")):
            result = diagnostic.diagnose(raw=ics(), asof_utc=ASOF)
        self.assertEqual(result["status"],
                         "BLS_CALENDAR_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")
        self.assertEqual(result["stage"], "PREFLIGHT")
        self.assertEqual(result["calendar_research_event_count"], 1)
        self.assertEqual(result["body_sha256_for_local_comparison"],
                         hashlib.sha256(ics()).hexdigest())
        self.assertEqual(result["document_class"], "VCALENDAR_TEXT")
        self.assertEqual(result["API_calls_this_run"], 0)
        self.assertFalse(result["report_or_original_journal_modified"])
        self.assertFalse(result["real_orders_permitted"])

    def test_http_403_is_classified_without_error_body(self):
        exc=urllib.error.HTTPError(
            calendar.URL,403,"secret network information",None,None)
        with patch.object(calendar,"download",side_effect=exc):
            report=diagnostic.diagnose(
                raw=None,allow_network=True,asof_utc=ASOF)
        self.assertEqual(report["stage"],"FETCH")
        self.assertEqual(report["reason_code"],"HTTP_403")
        self.assertNotIn("secret",json.dumps(report))
        self.assertFalse(report["automatic_retry_enabled"])

    def test_rate_limit_and_server_errors_are_fixed_codes(self):
        for status,expected in ((429,"HTTP_429"),(503,"HTTP_5XX")):
            with self.subTest(status=status):
                exc=urllib.error.HTTPError(
                    calendar.URL,status,"private message",None,None)
                with patch.object(calendar,"download",side_effect=exc):
                    report=diagnostic.diagnose(
                        allow_network=True,asof_utc=ASOF)
                self.assertEqual(report["reason_code"],expected)
                self.assertNotIn("private",json.dumps(report))

    def test_dns_tls_failure_avoids_exposing_exception_message(self):
        with patch.object(calendar,"download",side_effect=
                          urllib.error.URLError("sensitive diagnostic path")):
            report=diagnostic.diagnose(
                allow_network=True,asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"NETWORK_DNS_TLS_OR_TIMEOUT")
        self.assertNotIn("sensitive",json.dumps(report))

    def test_redirect_is_still_blocked(self):
        with patch.object(calendar,"download",side_effect=
                          calendar.InputError(
                              "BLS schedule redirect not allowlisted")):
            report=diagnostic.diagnose(
                allow_network=True,asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"HTTP_REDIRECT_BLOCKED")

    def test_html_response_is_not_parsed_as_calendar(self):
        report=diagnostic.diagnose(
            raw=b"<!DOCTYPE html><html><body>Blocked</body></html>",
            asof_utc=ASOF)
        self.assertEqual(report["document_class"],"HTML_NOT_CALENDAR")
        self.assertEqual(report["stage"],"STRICT_PARSE")
        self.assertEqual(report["reason_code"],"UNEXPECTED_CALENDAR_ROOT")
        self.assertNotIn("Blocked",json.dumps(report))

    def test_xml_response_is_not_calendar(self):
        report=diagnostic.diagnose(
            raw=b"<?xml version='1.0'?><feed></feed>",asof_utc=ASOF)
        self.assertEqual(report["document_class"],"XML_OR_OTHER_DOCUMENT")
        self.assertEqual(report["reason_code"],"UNEXPECTED_CALENDAR_ROOT")

    def test_unsupported_time_zone_not_softened(self):
        report=diagnostic.diagnose(
            raw=ics(key="DTSTART;TZID=America/Chicago"),asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"ICS_TIMEZONE_UNSUPPORTED")
        self.assertFalse(report["real_orders_permitted"])

    def test_ics_date_without_timezone_fails_closed(self):
        report=diagnostic.diagnose(
            raw=ics(key="DTSTART"),asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"ICS_TIMEZONE_UNSUPPORTED")

    def test_malformed_event_missing_title_classified(self):
        raw=ics().replace(b"SUMMARY:Producer Price Index\r\n",b"")
        report=diagnostic.diagnose(raw=raw,asof_utc=ASOF)
        self.assertEqual(report["reason_code"],
                         "ICS_EVENT_DATE_OR_TITLE_MISSING")

    def test_nonexistent_dst_classified(self):
        raw=ics(date="20260308T023000")
        report=diagnostic.diagnose(raw=raw,asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"ICS_DST_GAP")

    def test_ambiguous_dst_classified(self):
        raw=ics(date="20261101T013000")
        report=diagnostic.diagnose(raw=raw,asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"ICS_DST_AMBIGUOUS")

    def test_overlong_ics_line_is_classified(self):
        raw=b"BEGIN:VCALENDAR\n" + b"X"*2510 + b"\nEND:VCALENDAR\n"
        report=diagnostic.diagnose(raw=raw,asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"ICS_LINE_TOO_LONG")

    def test_oversized_response_is_refused(self):
        raw=b"a"*(calendar.MAX_ICS_BYTES+1)
        report=diagnostic.diagnose(raw=raw,asof_utc=ASOF)
        self.assertEqual(report["reason_code"],"ICS_RESPONSE_SIZE_LIMIT")
        self.assertNotIn("body_sha256_for_local_comparison",report)

    def test_source_modes_mutually_exclusive_and_no_implicit_network(self):
        with patch.object(calendar,"download",
                          side_effect=AssertionError("network attempted")):
            result=diagnostic.diagnose(asof_utc=ASOF)
        self.assertEqual(result["stage"],"INPUT")
        self.assertEqual(result["status"],
                         "BLS_CALENDAR_DIAGNOSTIC_FAIL_CLOSED_NO_GO")

    def test_offline_cli_reads_local_ics_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/"cal.ics"
            source.write_bytes(ics())
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                code=diagnostic.main(["--ics-file",str(source)])
            self.assertEqual(code,0)
            data=json.loads(stream.getvalue())
            self.assertEqual(data["status"],
                             "BLS_CALENDAR_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")
            self.assertEqual(set(Path(t).iterdir()),{source})

    def test_nonexistent_local_ics_safe_message(self):
        with tempfile.TemporaryDirectory() as t:
            with patch("sys.stdout",new_callable=io.StringIO) as stream:
                code=diagnostic.main(
                    ["--ics-file",str(Path(t)/"absent.ics")])
            self.assertEqual(code,2)
            self.assertEqual(json.loads(stream.getvalue())["reason_code"],
                             "LOCAL_CALENDAR_FILE_INVALID")

    def test_network_flag_invokes_exactly_one_existing_fetch(self):
        with patch.object(calendar,"download",return_value=ics()) as fetch:
            result=diagnostic.diagnose(allow_network=True,asof_utc=ASOF)
        fetch.assert_called_once_with()
        self.assertTrue(result["network_opted_in"])
        self.assertFalse(result["automatic_retry_enabled"])

    def test_no_order_or_api_permission_for_synthetically_valid_file(self):
        result=diagnostic.diagnose(raw=ics(),asof_utc=ASOF)
        self.assertEqual(result["runtime_go_no_go"],"NO_GO")
        self.assertFalse(result["demo_orders_permitted"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["calendar_covers_all_fx_events"])


if __name__=="__main__":
    unittest.main()
