"""FWD-377..392: saved BLS source evidence and consensus NO_GO gate."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_dual_snapshot as snap
from research import forward_bls_macro_source_gate as gate
from research.offline_backtest import InputError

ASOF = "2026-11-13T02:00:00Z"
OBS_ICS = "2026-11-13T01:48:45Z"
OBS_HTML = "2026-11-13T01:48:45Z"
SLOT = "2026-11-20T15:00:00Z"

ROWS = [
    ("Tuesday, November 03, 2026", "10:00 AM",
     "Job Openings and Labor Turnover Survey for September 2026"),
    ("Thursday, November 05, 2026", "08:30 AM",
     "Productivity and Costs (P) for Third Quarter 2026"),
    ("Friday, November 06, 2026", "08:30 AM",
     "Employment Situation for October 2026"),
    ("Tuesday, November 10, 2026", "08:30 AM",
     "Consumer Price Index for October 2026"),
    ("Tuesday, November 10, 2026", "08:30 AM",
     "Real Earnings for October 2026"),
    ("Friday, November 13, 2026", "08:30 AM",
     "Producer Price Index for October 2026"),
    ("Tuesday, November 17, 2026", "08:30 AM",
     "U.S. Import and Export Price Indexes for October 2026"),
    ("Wednesday, November 18, 2026", "10:00 AM",
     "Employer-Reported Workplace Injuries and Illnesses (Annual) for 2025"),
    ("Friday, November 20, 2026", "10:00 AM",
     "State Employment and Unemployment (Monthly) for October 2026"),
    ("Friday, November 20, 2026", "10:00 AM",
     "Total Factor Productivity for Major Industries for Annual 2025"),
]
ICS_EVENTS = [
    ("20261113T083000", "Producer Price Index"),
    ("20261117T083000", "U.S. Import and Export Price Indexes"),
    ("20261118T100000",
     "Employer-Reported Workplace Injuries and Illnesses (Annual)"),
    ("20261120T100000", "State Employment and Unemployment (Monthly)"),
]


def html(rows=ROWS):
    release = "".join(
        "<tr>" + "".join("<td>" + cell + "</td>" for cell in item)
        + "</tr>" for item in rows)
    return (
        "<!doctype html><html><head>"
        "<title>Schedule of Selected Releases</title></head>"
        "<body><table><tr><td>BY MONTH</td>"
        "<td><h1>November 2026</h1><table>"
        "<tr><th>Date</th><th>Time</th><th>Release</th></tr>"
        + release + "</table></td></tr></table></body></html>").encode()


def ics(events=ICS_EVENTS):
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        + "".join(
            "BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:" + start
            + "\r\nSUMMARY:" + name + "\r\nEND:VEVENT\r\n"
            for start, name in events)
        + "END:VCALENDAR\r\n").encode()


def bundle(folder: Path, *, events=None, rows=None):
    i = ics(ICS_EVENTS if events is None else events)
    h = html(ROWS if rows is None else rows)
    manifest, report = snap.prepare(
        ics=i, html=h, observed_ics_utc=OBS_ICS,
        observed_html_utc=OBS_HTML,
        mode="LOCAL_COPY", days_forward=14)
    snap.write_bundle(out_dir=folder, ics=i, html=h,
                      manifest=manifest, report=report)
    return folder


class SourceConsensusGateTests(unittest.TestCase):
    def test_real_world_discrepancy_causes_explicit_hold(self):
        with tempfile.TemporaryDirectory() as td:
            result = gate.inspect(bundle(Path(td) / "snap"), asof_utc=ASOF)
        self.assertEqual(result["status"],
                         "BLS_MACRO_SOURCE_CONSENSUS_READINESS_HOLD_NO_GO")
        self.assertTrue(result["html_ics_slot_count_disagreement"])
        self.assertEqual(result["ics_event_count"], 4)
        self.assertEqual(result["html_selected_event_count_within_window"], 5)
        self.assertEqual(result["missing_html_slot_instances"], 1)
        self.assertEqual(result["disputed_slots_unverified"], [SLOT])
        self.assertIn("BLS_ICS_HTML_SCHEDULE_COUNT_DISAGREEMENT",
                      result["unresolved_holds"])
        self.assertIn("POINT_IN_TIME_CONSENSUS_EVIDENCE_MISSING",
                      result["unresolved_holds"])
        self.assertFalse(result["macro_event_coverage_complete"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["demo_orders_permitted"])
        self.assertTrue(result["safety_hold_latched"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_even_full_slot_match_does_not_authorize_trading(self):
        complete = ICS_EVENTS + [(
            "20261120T100000",
            "Total Factor Productivity for Major Industries")]
        with tempfile.TemporaryDirectory() as td:
            result = gate.inspect(bundle(
                Path(td) / "snap", events=complete), asof_utc=ASOF)
        self.assertFalse(result["html_ics_slot_count_disagreement"])
        self.assertIn(
            "BLS_MATCHING_SLOT_COUNTS_DO_NOT_VERIFY_EVENT_IDENTITIES",
            result["unresolved_holds"])
        self.assertIn("FULL_FX_MACRO_CALENDAR_NOT_ATTESTED",
                      result["unresolved_holds"])
        self.assertFalse(result["real_orders_permitted"])

    def test_snapshot_older_than_24h_is_explicitly_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            result = gate.inspect(
                bundle(Path(td) / "snap"),
                asof_utc="2026-11-15T01:48:46Z")
        self.assertTrue(result["snapshot_older_than_24h"])
        self.assertIn("BLS_SAVED_SNAPSHOT_OLDER_THAN_24H",
                      result["unresolved_holds"])

    def test_future_captured_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = bundle(Path(td) / "snap")
            with self.assertRaises(InputError):
                gate.inspect(p, asof_utc="2026-11-13T01:00:00Z")

    def test_invalid_utc_format_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = bundle(Path(td) / "snap")
            with self.assertRaises(InputError):
                gate.inspect(p, asof_utc="2026-11-13 02:00")

    def test_verified_forecast_aligned_is_still_unattested(self):
        with tempfile.TemporaryDirectory() as td:
            p = bundle(Path(td) / "snap")
            snapshot_data = json.loads((p / "snapshot.json").read_text())
            faux = {
                "calendar_report_sha256_self_reported":
                    snapshot_data["ics_sha256"],
                "event_title_unverified": "State Employment and Unemployment (Monthly)",
                "scheduled_at_utc_unverified": SLOT,
            }
            with patch.object(gate, "verify_forecast", return_value=faux) as call:
                result = gate.inspect(
                    p, asof_utc=ASOF, forecast_archive={"simulated": True})
            call.assert_called_once()
        self.assertTrue(result["forecast_archive_supplied"])
        self.assertTrue(
            result["forecast_archive_matches_saved_ics_title_time_and_digest"])
        self.assertFalse(result["pre_release_consensus_truth_authenticated"])
        self.assertIn("CONSENSUS_SOURCE_AND_PUBLICATION_TIME_UNATTESTED",
                      result["unresolved_holds"])
        self.assertFalse(result["demo_orders_permitted"])

    def test_forecast_mismatch_holds_without_faking_identity(self):
        with tempfile.TemporaryDirectory() as td:
            p = bundle(Path(td) / "snap")
            faux = {
                "calendar_report_sha256_self_reported": "f" * 64,
                "event_title_unverified": "State Employment and Unemployment (Monthly)",
                "scheduled_at_utc_unverified": SLOT,
            }
            with patch.object(gate, "verify_forecast", return_value=faux):
                result = gate.inspect(
                    p, asof_utc=ASOF, forecast_archive={"simulated": True})
        self.assertFalse(
            result["forecast_archive_matches_saved_ics_title_time_and_digest"])
        self.assertIn("FORECAST_ARCHIVE_NOT_LINKED_TO_THIS_ICS_SNAPSHOT",
                      result["unresolved_holds"])

    def test_actual_invalid_forecast_integrity_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = bundle(Path(td) / "snap")
            with self.assertRaises((InputError, ValueError, KeyError)):
                gate.inspect(
                    p, asof_utc=ASOF,
                    forecast_archive={"record": {}, "record_sha256": "0" * 64})

    def test_corrupt_saved_html_fails_before_gate(self):
        with tempfile.TemporaryDirectory() as td:
            p = bundle(Path(td) / "snap")
            (p / "bls_schedule.html").write_bytes(
                (p / "bls_schedule.html").read_bytes() + b"\nspoof")
            with self.assertRaises(InputError):
                gate.inspect(p, asof_utc=ASOF)

    def test_cli_no_forecast_is_offline_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            p = bundle(Path(td) / "snap")
            before = {x.name: x.read_bytes() for x in p.iterdir()}
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                code = gate.main(["--snapshot-dir", str(p),
                                  "--asof-utc", ASOF])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["network_calls_this_run"], 0)
            self.assertEqual(result["files_written_this_run"], 0)
            self.assertEqual(result["API_calls_this_run"], 0)
            self.assertEqual(result["actual_orders_sent"], 0)
            self.assertEqual(before, {
                x.name: x.read_bytes() for x in p.iterdir()})

    def test_cli_nonexistent_bundle_fails_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                code = gate.main([
                    "--snapshot-dir", str(Path(td) / "not-there"),
                    "--asof-utc", ASOF])
            self.assertEqual(code, 2)
            result = json.loads(out.getvalue())
            self.assertEqual(result["status"],
                             "BLS_MACRO_SOURCE_CONSENSUS_FAIL_CLOSED_NO_GO")
            self.assertEqual(result["runtime_go_no_go"], "NO_GO")
            self.assertFalse(result["real_orders_permitted"])

    def test_cli_rejects_invalid_forecast_file_and_keeps_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = bundle(root / "snap")
            f = root / "bad_forecast.json"
            f.write_text('{"record": {}}')
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                code = gate.main([
                    "--snapshot-dir", str(p),
                    "--asof-utc", ASOF,
                    "--forecast-archive", str(f)])
            self.assertEqual(code, 2)
            result = json.loads(out.getvalue())
            self.assertEqual(result["runtime_go_no_go"], "NO_GO")
            self.assertFalse(result["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
