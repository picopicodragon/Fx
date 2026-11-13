"""FWD-361..376: live-shaped BLS nested layout table strict regression."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_saved_html_audit as audit
from research import forward_bls_dual_snapshot as snapshot
from research.offline_backtest import InputError

T1 = "2026-11-13T00:47:40Z"
T2 = "2026-11-13T00:47:41Z"
HTML_ROWS = [
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
ICS = (
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
    + b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261113T083000\r\n"
    + b"SUMMARY:Producer Price Index\r\nEND:VEVENT\r\n"
    + b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261117T083000\r\n"
    + b"SUMMARY:U.S. Import and Export Price Indexes\r\nEND:VEVENT\r\n"
    + b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261118T100000\r\n"
    + b"SUMMARY:Employer-Reported Workplace Injuries and Illnesses (Annual)\r\nEND:VEVENT\r\n"
    + b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261120T100000\r\n"
    + b"SUMMARY:State Employment and Unemployment (Monthly)\r\nEND:VEVENT\r\n"
    + b"END:VCALENDAR\r\n"
)


def inner_table(rows=HTML_ROWS):
    body = "".join(
        "<tr>" + "".join("<td>" + part + "</td>" for part in row)
        + "</tr>" for row in rows
    )
    return ("<table class='releases'><thead><tr>"
            "<th>Date</th><th>Time</th><th>Release</th>"
            "</tr></thead><tbody>" + body + "</tbody></table>")


def nested_html(inner=None):
    inner = inner_table() if inner is None else inner
    return (
        "<!DOCTYPE html><html><body><table class='layout'>"
        "<tr><td><p>BY MONTH FEBRUARY 2026 MARCH 2026 APRIL 2026</p></td>"
        "<td><h1>November 2026</h1>Month View | List View"
        + inner
        + "<p>NOTE: All times on calendar are Eastern Time."
        "Last Modified Date: November 03, 2026</p></td></tr>"
        "</table></body></html>"
    ).encode("utf-8")


def make_bundle(folder: Path, html=None) -> Path:
    raw_html = nested_html() if html is None else html
    manifest, report = snapshot.prepare(
        ics=ICS, html=raw_html,
        observed_ics_utc=T1, observed_html_utc=T2,
        mode="LOCAL_COPY")
    snapshot.write_bundle(
        out_dir=folder, ics=ICS, html=raw_html,
        manifest=manifest, report=report)
    return folder


class NestedHTMLTableTests(unittest.TestCase):
    def test_nested_structure_was_invisible_to_old_outer_only_parser(self):
        parser = audit._TableRows()
        parser.feed(nested_html().decode("utf-8"))
        parser.close()
        self.assertEqual(parser.depth, 0)
        self.assertFalse(parser.invalid_structure)
        self.assertEqual(len(parser.tables), 2)
        self.assertIn(1, [len(x) for x in parser.tables])
        self.assertEqual(len(audit._release_rows(nested_html())), 10)

    def test_safe_nested_original_bundle_4_vs_5(self):
        with tempfile.TemporaryDirectory() as td:
            result = audit.inspect(make_bundle(Path(td) / "snap"))
        self.assertEqual(result["status"], "BLS_SAVED_HTML_ICS_AUDIT_HOLD_NO_GO")
        self.assertEqual(result["ics_event_count"], 4)
        self.assertEqual(result["html_event_count_within_window"], 5)
        self.assertEqual(result["missing_html_slot_instance_count"], 1)
        self.assertEqual(result["unexpected_ics_slot_instance_count"], 0)
        disputed, = result["disputed_slot_title_evidence"]
        self.assertEqual(disputed["scheduled_at_utc"],
                         "2026-11-20T15:00:00Z")
        self.assertEqual(
            disputed["release_family_candidate_review"][
                "html_only_title_candidates_not_in_ics"],
            ["Total Factor Productivity for Major Industries for Annual 2025"])
        self.assertFalse(result["missing_events_automatically_added"])
        self.assertFalse(result["demo_orders_permitted"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertTrue(result["safety_hold_latched"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_double_nested_wrappers_still_require_exact_header(self):
        markup = nested_html("<table><tr><td>" + inner_table() +
                             "</td></tr></table>")
        rows = audit._release_rows(markup)
        self.assertEqual(len(rows), 10)

    def test_two_matching_schedule_tables_are_ambiguous(self):
        with self.assertRaisesRegex(InputError, "ambiguous"):
            audit._release_rows(nested_html(inner_table() + inner_table()))

    def test_outer_only_navigation_does_not_create_release_data(self):
        with self.assertRaisesRegex(InputError, "absent"):
            audit._release_rows(nested_html("<div>Date Time Release</div>"))

    def test_broken_inner_table_still_fails_closed(self):
        broken = inner_table().replace("</table>", "")
        with self.assertRaisesRegex(InputError, "incomplete"):
            audit._release_rows(nested_html(broken))

    def test_forged_another_month_raises_without_backfill(self):
        markup = nested_html(inner_table().replace(
            "Friday, November 20, 2026", "Friday, December 20, 2026"))
        with self.assertRaises(InputError):
            audit._release_rows(markup)

    def test_unverified_duplicated_event_names_remain_provisional(self):
        with tempfile.TemporaryDirectory() as td:
            r = audit.inspect(make_bundle(Path(td) / "one"))
        self.assertFalse(r["titles_or_event_identity_authenticated"])
        self.assertFalse(r["publication_timing_independently_verified"])
        self.assertFalse(r["complete_fx_macro_calendar_coverage"])
        self.assertFalse(r["consensus_evidence_captured"])

    def test_cli_cannot_write_to_verified_source_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            folder = make_bundle(Path(td) / "one")
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                rc = audit.main(["--snapshot-dir", str(folder)])
            self.assertEqual(rc, 0)
            output = json.loads(stream.getvalue())
            self.assertEqual(output["network_calls_this_run"], 0)
            self.assertEqual(output["files_written_this_run"], 0)
            self.assertEqual(output["actual_orders_sent"], 0)
            self.assertEqual(before, {
                p.name: p.read_bytes() for p in folder.iterdir()})

    def test_modified_html_fails_before_parsing(self):
        with tempfile.TemporaryDirectory() as td:
            folder = make_bundle(Path(td) / "one")
            (folder / "bls_schedule.html").write_bytes(
                nested_html().replace(b"November 2026", b"November 2027"))
            with self.assertRaises(InputError):
                audit.inspect(folder)


if __name__ == "__main__":
    unittest.main()
