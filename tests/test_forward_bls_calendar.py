"""FWD-02B: offline BLS ICS parsing, DST fail-closed and event timing."""
import json
import tempfile
import unittest
from pathlib import Path

from research import forward_bls_calendar as cal
from research.offline_backtest import InputError


def ics(at="20261110T083000", title="Employment Situation",
        key="DTSTART;TZID=America/New_York"):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        f"{key}:{at}\r\nSUMMARY:{title}\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode()


class BlsCalendarTests(unittest.TestCase):
    def test_release_within_15_minutes_requires_research_halt(self):
        report = cal.parse_calendar(
            ics(), asof_utc="2026-11-10T13:25:00Z")
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["imminent_event_count"], 1)
        self.assertEqual(
            report["events"][0]["scheduled_at_utc"],
            "2026-11-10T13:30:00Z")
        self.assertFalse(report["calendar_covers_all_fx_events"])
        self.assertFalse(report["real_orders_permitted"])

    def test_utc_input_and_future_filter(self):
        report = cal.parse_calendar(
            ics("20261110T133000Z", key="DTSTART"),
            asof_utc="2026-11-10T11:00:00Z")
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["imminent_event_count"], 0)
        old = cal.parse_calendar(
            ics("20250101T133000Z", key="DTSTART"),
            asof_utc="2026-11-10T11:00:00Z")
        self.assertEqual(old["event_count"], 0)

    def test_bad_dst_and_unknown_timezone_are_rejected(self):
        for data in (
            ics("20260308T023000"),
            ics("20261101T013000"),
            ics("20261110T083000", key="DTSTART;TZID=Mars/Base"),
            ics("20261110T083000", key="DTSTART"),
            b"BEGIN:NOTCALENDAR\nEND:NOTCALENDAR\n",
        ):
            with self.subTest(data=data), self.assertRaises(InputError):
                cal.parse_calendar(data, asof_utc="2026-11-10T11:00:00Z")

    def test_overwrite_fail_and_offline_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "calendar.ics"
            out = Path(folder) / "report.json"
            source.write_bytes(ics())
            self.assertEqual(cal.main([
                "--out", str(out), "--ics-file", str(source),
                "--asof-utc", "2026-11-10T13:25:00Z"]), 0)
            result = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["imminent_event_count"], 1)
            self.assertEqual(cal.main([
                "--out", str(out), "--ics-file", str(source),
                "--asof-utc", "2026-11-10T13:25:00Z"]), 2)
            self.assertEqual(cal.main([
                "--out", str(out),
                "--asof-utc", "2026-11-10T13:25:00Z"]), 2)

    def test_no_unbounded_horizon(self):
        with self.assertRaises(InputError):
            cal.parse_calendar(
                ics(), asof_utc="2026-11-10T13:25:00Z",
                days_forward=90)


if __name__ == "__main__":
    unittest.main()
