"""FWD-366: BLS HTML structure metadata diagnostics and safe failure."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_dual_snapshot as snap
from research import forward_bls_html_structure_diagnose as diag

ICS = (b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
       b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261120T100000\r\n"
       b"SUMMARY:State Employment and Unemployment (Monthly)\r\n"
       b"END:VEVENT\r\nEND:VCALENDAR\r\n")
HTML = (
    b"<!doctype html><html><head><title>Schedule of Selected Releases</title>"
    b"</head><body><table><tr><td>BY MONTH</td>"
    b"<td><h1>November 2026</h1><table><tr>"
    b"<th>Date</th><th>Time</th><th>Release</th></tr>"
    b"<tr><td>Friday, November 20, 2026</td><td>10:00 AM</td>"
    b"<td>State Employment and Unemployment (Monthly)</td>"
    b"</tr></table>NOTE</td></tr></table></body></html>"
)


def create(folder: Path):
    m, r = snap.prepare(
        ics=ICS, html=HTML,
        observed_ics_utc="2026-11-13T00:47:40Z",
        observed_html_utc="2026-11-13T00:47:41Z",
        mode="LOCAL_COPY")
    snap.write_bundle(out_dir=folder, ics=ICS, html=HTML,
                      manifest=m, report=r)


class StructureDiagnosticTests(unittest.TestCase):
    def test_nested_table_summary_without_titles_or_timestamps(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "snap"
            create(path)
            a = diag.diagnose(path)
        self.assertEqual(a["table_count_all_nesting_depths"], 2)
        self.assertEqual(a["date_time_release_header_count"], 1)
        self.assertEqual(a["table_parser_open_depth_at_end"], 0)
        self.assertFalse(a["table_parser_invalid_structure"])
        self.assertTrue(a["html_sha256_verified_against_snapshot"])
        self.assertFalse(a["source_titles_dates_or_raw_body_included"])
        self.assertFalse(a["real_orders_permitted"])
        self.assertFalse(a["demo_orders_permitted"])
        self.assertEqual(a["runtime_go_no_go"], "NO_GO")
        self.assertNotIn("State Employment", json.dumps(a))

    def test_cli_read_only_and_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "snap"
            create(path)
            before = {p.name:p.read_bytes() for p in path.iterdir()}
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                status = diag.main(["--snapshot-dir", str(path)])
            self.assertEqual(status, 0)
            data = json.loads(out.getvalue())
            self.assertEqual(data["network_calls_this_run"], 0)
            self.assertEqual(data["files_written_this_run"], 0)
            self.assertEqual(data["actual_orders_sent"], 0)
            self.assertEqual(before, {
                p.name:p.read_bytes() for p in path.iterdir()})

    def test_missing_bundle_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                code = diag.main(["--snapshot-dir", str(Path(td)/"absent")])
            self.assertEqual(code, 2)
            r = json.loads(out.getvalue())
            self.assertEqual(
                r["status"], "BLS_SAVED_HTML_STRUCTURE_FAIL_CLOSED_NO_GO")
            self.assertEqual(r["runtime_go_no_go"], "NO_GO")
            self.assertFalse(r["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
