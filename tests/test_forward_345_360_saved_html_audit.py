"""FWD-345..360: audited real saved HTML vs ICS, no network or orders."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_calendar as cal
from research import forward_bls_dual_snapshot as snap
from research import forward_bls_saved_html_audit as audit
from research.offline_backtest import InputError

T1 = "2026-11-13T00:47:40Z"
T2 = "2026-11-13T00:47:41Z"
RELEASES = [
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
    ("Wednesday, November 11, 2026", "", "Veterans Day"),
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
    ("Thursday, November 26, 2026", "", "Thanksgiving Day"),
]


def html(rows=RELEASES, *, extra_table=""):
    rendered = "".join(
        "<tr>" + "".join("<td><span>" + cell + "</span></td>"
                         for cell in entry) + "</tr>"
        for entry in rows)
    return (
        "<!DOCTYPE html><html><head><title>Schedule of Selected Releases"
        "</title></head><body><h1>November 2026</h1>"
        + extra_table
        + "<table id='bls-dated-releases'><thead>"
        "<tr><th>Date</th><th>Time</th><th>Release</th></tr></thead>"
        "<tbody>" + rendered + "</tbody></table></body></html>"
    ).encode()


def ics(include_productivity=False):
    events = [
        ("20261113T083000", "Producer Price Index"),
        ("20261117T083000", "U.S. Import and Export Price Indexes"),
        ("20261118T100000", "Employer-Reported Workplace Injuries and Illnesses (Annual)"),
        ("20261120T100000", "State Employment and Unemployment (Monthly)"),
    ]
    if include_productivity:
        events.append(("20261120T100000",
                       "Total Factor Productivity for Major Industries"))
    return (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
        + "".join(
            "BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:" + dt
            + "\r\nSUMMARY:" + title + "\r\nEND:VEVENT\r\n"
            for dt, title in events)
        + "END:VCALENDAR\r\n"
    ).encode()


def bundle(folder: Path, *, html_data=None, ics_data=None):
    h = html() if html_data is None else html_data
    i = ics() if ics_data is None else ics_data
    manifest, report = snap.prepare(
        ics=i, html=h, observed_ics_utc=T1,
        observed_html_utc=T2, mode="LOCAL_COPY")
    snap.write_bundle(
        out_dir=folder, ics=i, html=h, manifest=manifest, report=report)
    return folder


class SavedSourceAuditTests(unittest.TestCase):
    def test_real_structure_4_vs_5_detects_nov20_and_titles(self):
        with tempfile.TemporaryDirectory() as dirname:
            report = audit.inspect(bundle(Path(dirname) / "one"))
        self.assertEqual(report["ics_event_count"], 4)
        self.assertEqual(report["html_event_count_within_window"], 5)
        self.assertEqual(report["html_month_selected_release_item_count"], 10)
        self.assertEqual(report["missing_html_slot_instance_count"], 1)
        self.assertEqual(report["matched_slot_instance_count"], 4)
        self.assertEqual(report["unexpected_ics_slot_instance_count"], 0)
        self.assertEqual(report["comparison"],
                         "SAVED_HTML_ICS_SLOT_COUNTS_DISAGREE")
        disputed, = report["disputed_slot_title_evidence"]
        self.assertEqual(disputed["scheduled_at_utc"], "2026-11-20T15:00:00Z")
        rev = disputed["release_family_candidate_review"]
        self.assertEqual(rev["relationship_status"],
                         "UNIQUE_LEXICAL_CANDIDATES_ONLY")
        self.assertEqual(rev["html_only_title_candidates_not_in_ics"],
                         ["Total Factor Productivity for Major Industries for Annual 2025"])
        self.assertFalse(rev["source_revision_or_omission_resolved"])
        self.assertFalse(report["titles_or_event_identity_authenticated"])
        self.assertFalse(report["missing_events_automatically_added"])
        self.assertFalse(report["source_authenticity_independently_verified"])
        self.assertFalse(report["demo_orders_permitted"])
        self.assertFalse(report["real_orders_permitted"])
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")
        self.assertTrue(report["safety_hold_latched"])

    def test_both_releases_in_ics_match_at_slot_count_only(self):
        with tempfile.TemporaryDirectory() as dirname:
            result = audit.inspect(bundle(
                Path(dirname) / "one", ics_data=ics(True)))
        self.assertEqual(result["comparison"],
                         "SAVED_HTML_ICS_SLOT_COUNTS_MATCH_UNVERIFIED")
        self.assertEqual(result["ics_event_count"], 5)
        self.assertEqual(result["missing_html_slot_instance_count"], 0)
        self.assertEqual(result["disputed_slot_title_evidence"], [])
        self.assertFalse(result["titles_or_event_identity_authenticated"])

    def test_html_parser_ignores_an_unrelated_table(self):
        extra = "<table><tr><th>Other</th></tr><tr><td>spare</td></tr></table>"
        rows = audit._release_rows(html(extra_table=extra))
        self.assertEqual(len(rows), 10)

    def test_duplicate_valid_table_is_rejected(self):
        h = html()
        other = (
            b"<table><tr><th>Date</th><th>Time</th><th>Release</th></tr>"
            b"<tr><td>Friday, November 20, 2026</td>"
            b"<td>10:00 AM</td><td>Other</td></tr></table>")
        h = h.replace(b"</body>", other + b"</body>")
        with self.assertRaisesRegex(InputError, "ambiguous"):
            audit._release_rows(h)

    def test_not_a_release_table_fails_closed(self):
        h = html().replace(b"<th>Release</th>", b"<th>Other</th>")
        with self.assertRaisesRegex(InputError, "absent"):
            audit._release_rows(h)

    def test_unknown_date_format_rejected(self):
        wrong = list(RELEASES)
        wrong[0] = ("Tuesday, Oct 03, 2026",) + wrong[0][1:]
        with self.assertRaisesRegex(InputError, "date format"):
            audit._release_rows(html(wrong))

    def test_invalid_weekday_refused(self):
        wrong = list(RELEASES)
        wrong[0] = ("Monday, November 03, 2026",) + wrong[0][1:]
        with self.assertRaisesRegex(InputError, "weekday"):
            audit._release_rows(html(wrong))

    def test_invalid_time_refused_without_guessing(self):
        wrong = list(RELEASES)
        wrong[0] = (wrong[0][0], "10:00 PST", wrong[0][2])
        with self.assertRaisesRegex(InputError, "time format"):
            audit._release_rows(html(wrong))

    def test_missing_release_time_refused_without_guessing(self):
        wrong = list(RELEASES)
        wrong[0] = (wrong[0][0], "", wrong[0][2])
        with self.assertRaisesRegex(InputError, "untimed"):
            audit._release_rows(html(wrong))

    def test_reference_html_malformed_title_does_not_authenticate(self):
        wrong = list(RELEASES)
        wrong[-2] = (wrong[-2][0], wrong[-2][1], " ")
        with self.assertRaisesRegex(InputError, "title"):
            audit._release_rows(html(wrong))

    def test_html_headers_outside_table_do_not_count(self):
        h = (
            b"<!DOCTYPE html><html><body>"
            b"Schedule of Selected Releases November 2026 Date Time Release"
            b"</body></html>"
        )
        with self.assertRaises(InputError):
            audit._release_rows(h)

    def test_bundle_tamper_detected_prior_to_comparison(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = bundle(Path(dirname) / "one")
            with (folder / "bls_schedule.html").open("ab") as output:
                output.write(b"changed")
            with self.assertRaises(InputError):
                audit.inspect(folder)

    def test_partial_bundle_cannot_pass_verification(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = bundle(Path(dirname) / "one")
            (folder / "snapshot.json").unlink()
            with self.assertRaises(InputError):
                audit.inspect(folder)

    def test_cli_is_read_only_and_no_network(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = bundle(Path(dirname) / "one")
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            with patch.object(cal, "download",
                              side_effect=AssertionError("network used")):
                with patch("sys.stdout", new_callable=io.StringIO) as stream:
                    rc = audit.main(["--snapshot-dir", str(folder)])
            self.assertEqual(rc, 0)
            r = json.loads(stream.getvalue())
            self.assertFalse(r["source_authenticity_independently_verified"])
            self.assertEqual(r["network_calls_this_run"], 0)
            self.assertEqual(r["API_calls_this_run"], 0)
            self.assertEqual(r["actual_orders_sent"], 0)
            self.assertEqual(r["files_written_this_run"], 0)
            self.assertEqual(before, {p.name:p.read_bytes() for p in folder.iterdir()})

    def test_missing_bundle_is_safe_failure(self):
        with tempfile.TemporaryDirectory() as dirname:
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                code = audit.main(["--snapshot-dir",
                                   str(Path(dirname) / "missing")])
            self.assertEqual(code, 2)
            r = json.loads(stream.getvalue())
            self.assertEqual(r["status"],
                             "BLS_SAVED_HTML_ICS_AUDIT_FAIL_CLOSED_NO_GO")
            self.assertFalse(r["real_orders_permitted"])
            self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_raw_html_change_requires_new_complete_bundle(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = bundle(Path(dirname) / "one")
            p = folder / "bls_schedule.html"
            p.write_bytes(p.read_bytes().replace(
                b"State Employment", b"Revised State Employment"))
            with self.assertRaises(InputError):
                audit.inspect(folder)


if __name__ == "__main__":
    unittest.main()
