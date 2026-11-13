"""FWD-489..520: real archive schema against a verified synthetic BLS bundle."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_dual_snapshot as bls
from research import forward_consensus_archive_batch as batch
from research import forward_macro_pre_release_capture as forecasts
from research.offline_backtest import InputError

OBS = "2026-11-13T01:48:45Z"
ASOF = "2026-11-13T02:49:10Z"
EVENT_TIME = "2026-11-20T15:00:00Z"
TITLE = "State Employment and Unemployment (Monthly)"
ICS = (
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
    b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261120T100000\r\n"
    b"SUMMARY:State Employment and Unemployment (Monthly)\r\n"
    b"END:VEVENT\r\nEND:VCALENDAR\r\n"
)
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


def saved_bls(directory: Path):
    manifest, calendar = bls.prepare(
        ics=ICS, html=HTML, observed_ics_utc=OBS,
        observed_html_utc=OBS, days_forward=14, mode="LOCAL_COPY")
    bls.write_bundle(out_dir=directory, ics=ICS, html=HTML,
                     manifest=manifest, report=calendar)
    return calendar


def record(calendar, *, pair="USD/JPY", title=TITLE,
           at=EVENT_TIME, text="Consensus estimate 2.7 percent"):
    form = {
        "schema": forecasts.FORM,
        "event_title": title,
        "scheduled_at_utc": at,
        "pair": pair,
        "value": "2.7",
        "unit": "percent",
        "source_text": text,
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_url": "https://example.org/economics/forecast",
        "source_published_at_utc": "2026-11-12T12:00:00Z",
    }
    rec = forecasts.validate_submission(form, calendar,
                                         captured_at_utc=OBS)
    return {"record": rec, "record_sha256": forecasts.sha(rec)}


def archive(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class BatchForecastTests(unittest.TestCase):
    def test_absent_bls_is_visible_hold_not_claimed_zero(self):
        r = batch.inspect([], asof_utc=ASOF)
        self.assertFalse(r["bls_bundle_integrity_verified"])
        self.assertIn("NO_BLS_ORIGINAL_CALENDAR_FOR_CONSENSUS_AUDIT",
                      r["unresolved_holds"])
        self.assertFalse(r["all_pairwise_consensus_proven"])
        self.assertFalse(r["demo_orders_permitted"])

    def test_archives_without_bls_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "fake.json"
            p.write_text('{"hello":true}')
            with self.assertRaises(InputError):
                batch.inspect([p], asof_utc=ASOF)

    def test_saved_bls_without_forecast_has_missing_event_hold(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"bls"
            saved_bls(path)
            r = batch.inspect([], asof_utc=ASOF, bls_snapshot_dir=path)
        self.assertTrue(r["bls_bundle_integrity_verified"])
        self.assertEqual(r["bls_unique_calendar_event_count"], 1)
        self.assertEqual(r["bls_events_without_archive_count"], 1)
        self.assertIn("NO_POINT_IN_TIME_FORECAST_ARCHIVES_PROVIDED",
                      r["unresolved_holds"])

    def test_accepted_archive_matches_title_time_and_raw_digest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cal = saved_bls(root/"bls")
            p = archive(root/"forecast.json", record(cal))
            r = batch.inspect([p], asof_utc=ASOF,
                              bls_snapshot_dir=root/"bls")
        self.assertEqual(r["archive_count"], 1)
        self.assertEqual(r["matched_unique_bls_event_count"], 1)
        self.assertEqual(r["unmatched_archive_count"], 0)
        self.assertEqual(r["bls_events_without_archive_count"], 0)
        self.assertFalse(r["consensus_publisher_authenticated"])
        self.assertFalse(r["all_pairwise_consensus_proven"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertFalse(r["real_orders_permitted"])

    def test_matching_two_pairs_still_only_one_unique_event(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cal=saved_bls(root/"bls")
            p1=archive(root/"1.json",record(cal,pair="USD/JPY"))
            p2=archive(root/"2.json",record(cal,pair="EUR/USD"))
            r=batch.inspect([p1,p2],asof_utc=ASOF,
                            bls_snapshot_dir=root/"bls")
        self.assertEqual(r["archive_count"],2)
        self.assertEqual(r["matched_unique_bls_event_count"],1)
        self.assertFalse(r["all_pairwise_consensus_proven"])

    def test_outdated_bls_digest_is_explicit_unmatched_hold(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cal=saved_bls(root/"bls")
            data=record(cal)
            data["record"]["calendar_report_sha256_self_reported"]="f"*64
            data["record_sha256"]=forecasts.sha(data["record"])
            p=archive(root/"old.json",data)
            r=batch.inspect([p],asof_utc=ASOF,
                            bls_snapshot_dir=root/"bls")
        self.assertEqual(r["unmatched_archive_count"],1)
        self.assertIn("FORECAST_ARCHIVE_BLS_CALENDAR_IDENTITY_MISMATCH",
                      r["unresolved_holds"])
        self.assertEqual(r["bls_events_without_archive_count"],1)

    def test_corrupt_archive_fails_closed_not_as_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cal=saved_bls(root/"bls")
            data=record(cal)
            data["record"]["forecast_value_self_reported"]="999.0"
            p=archive(root/"bad.json",data)
            with self.assertRaises(InputError):
                batch.inspect([p],asof_utc=ASOF,
                              bls_snapshot_dir=root/"bls")

    def test_duplicate_path_is_not_silently_deduplicated(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cal=saved_bls(root/"bls")
            p=archive(root/"1.json",record(cal))
            with self.assertRaises(InputError):
                batch.inspect([p,p],asof_utc=ASOF,
                              bls_snapshot_dir=root/"bls")

    def test_duplicate_same_event_and_pair_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cal=saved_bls(root/"bls")
            p1=archive(root/"1.json",record(cal))
            p2=archive(root/"2.json",record(cal))
            with self.assertRaises(InputError):
                batch.inspect([p1,p2],asof_utc=ASOF,
                              bls_snapshot_dir=root/"bls")

    def test_symlink_forecast_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            cal=saved_bls(root/"bls")
            p=archive(root/"forecast.json",record(cal))
            link=root/"linked.json"
            try:
                link.symlink_to(p)
            except (OSError, NotImplementedError):
                self.skipTest("host forbids symlinks")
            with self.assertRaises(InputError):
                batch.inspect([link],asof_utc=ASOF,
                              bls_snapshot_dir=root/"bls")

    def test_archive_exceeding_cap_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            saved_bls(root/"bls")
            p=root/"huge.json"
            p.write_bytes(b"x"*(batch.MAX_ARCHIVE_BYTES+1))
            with self.assertRaises(InputError):
                batch.inspect([p],asof_utc=ASOF,
                              bls_snapshot_dir=root/"bls")

    def test_over64_forecasts_fail_early(self):
        with self.assertRaises(InputError):
            batch.inspect([Path("x.json")]*65, asof_utc=ASOF)

    def test_cli_invalid_archive_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"broken.json"
            path.write_text("not JSON")
            with patch("sys.stdout",new_callable=io.StringIO) as output:
                rc=batch.main(["--forecast-archive",str(path),
                               "--asof-utc",ASOF])
        self.assertEqual(rc,2)
        self.assertIn("FAIL_CLOSED_NO_GO",output.getvalue())

    def test_cli_no_archive_no_bls_offline_no_go(self):
        with patch("sys.stdout",new_callable=io.StringIO) as output:
            rc=batch.main(["--asof-utc",ASOF])
        self.assertEqual(rc,0)
        response=json.loads(output.getvalue())
        self.assertEqual(response["network_calls_this_run"],0)
        self.assertEqual(response["files_written_this_run"],0)
        self.assertFalse(response["demo_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
