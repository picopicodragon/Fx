"""FWD-325..344: bounded dual-format evidence capture and offline diff."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_calendar as cal
from research import forward_bls_dual_snapshot as snapshot
from research import forward_bls_snapshot_diff as diff
from research.offline_backtest import InputError

T1 = "2026-11-13T00:47:40Z"
T2 = "2026-11-13T00:47:41Z"
T3 = "2026-11-13T00:55:00Z"
T4 = "2026-11-13T00:55:01Z"
HTML = (
    b"<!DOCTYPE html><html><head><title>Schedule of Selected Releases"
    b"</title></head><body><h1>November 2026</h1>"
    b"<p>State Employment and Unemployment</p></body></html>"
)
ICS = (b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
       b"DTSTART;TZID=US-Eastern:20261120T100000\r\n"
       b"SUMMARY:State Employment and Unemployment (Monthly)\r\n"
       b"END:VEVENT\r\nEND:VCALENDAR\r\n")


def bundle(parent: Path, name: str, *, html=HTML, ics=ICS,
           t1=T1, t2=T2, mode="NETWORK_EXPLICIT_OPT_IN") -> Path:
    manifest, report = snapshot.prepare(
        ics=ics, html=html, observed_ics_utc=t1,
        observed_html_utc=t2, days_forward=14, mode=mode)
    folder = parent / name
    snapshot.write_bundle(
        out_dir=folder, ics=ics, html=html, manifest=manifest, report=report)
    return folder


class SnapshotTests(unittest.TestCase):
    def test_valid_record_is_unverified_research_no_go(self):
        m, r = snapshot.prepare(
            ics=ICS, html=HTML, observed_ics_utc=T1,
            observed_html_utc=T2, mode="NETWORK_EXPLICIT_OPT_IN")
        self.assertEqual(r["event_count"], 1)
        self.assertEqual(m["calendar_event_count"], 1)
        self.assertEqual(m["ics_sha256"], hashlib.sha256(ICS).hexdigest())
        self.assertEqual(m["network_calls_expected"], 2)
        self.assertTrue(m["two_sources_not_atomic_and_not_independently_authenticated"])
        self.assertFalse(m["source_authenticity_independently_verified"])
        self.assertFalse(m["historical_publication_time_proven"])
        self.assertEqual(m["runtime_go_no_go"], "NO_GO")
        self.assertTrue(m["safety_hold_latched"])
        self.assertFalse(m["real_orders_permitted"])
        self.assertFalse(m["demo_orders_permitted"])

    def test_exclusive_write_and_integrity_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bundle(Path(tmp), "one")
            self.assertEqual(set(x.name for x in path.iterdir()), {
                "bls.ics", "bls_schedule.html", "calendar.json", "snapshot.json"})
            m = diff.verify(path)
            self.assertEqual(m["ics_sha256"], hashlib.sha256(ICS).hexdigest())
            with self.assertRaises((InputError, FileExistsError)):
                bundle(Path(tmp), "one")

    def test_compare_identical_sources_research_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = bundle(root, "before")
            after = bundle(root, "after", t1=T3, t2=T4)
            report = diff.compare(before, after)
            self.assertEqual(report["raw_body_change_classification"],
                             "BOTH_SOURCE_BYTES_UNCHANGED")
            self.assertFalse(report["publication_or_revision_time_verified"])
            self.assertFalse(report["real_orders_permitted"])

    def test_compare_html_change_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = bundle(root, "before")
            changed_html = HTML.replace(b"Unemployment", b"Unemployment - revision")
            after = bundle(root, "after", html=changed_html, t1=T3, t2=T4)
            r = diff.compare(before, after)
            self.assertEqual(r["raw_body_change_classification"],
                             "HTML_SOURCE_BYTES_CHANGED")
            self.assertTrue(r["changed_bytes_not_equivalent_to_schedule_change"])

    def test_compare_ics_change_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = bundle(root, "before")
            revised = ICS.replace(b"(Monthly)", b"(Monthly) for October 2026")
            after = bundle(root, "after", ics=revised, t1=T3, t2=T4)
            r = diff.compare(before, after)
            self.assertEqual(r["raw_body_change_classification"],
                             "ICS_SOURCE_BYTES_CHANGED")
            self.assertFalse(r["event_title_and_datetime_identity_verified"])

    def test_compare_both_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = bundle(root, "before")
            after = bundle(root, "after", ics=ICS.replace(
                b"(Monthly)", b"(Monthly) for October 2026"),
                html=HTML.replace(b"November 2026</h1>",
                                  b"November 2026</h1>updated"),
                t1=T3, t2=T4)
            r = diff.compare(before, after)
            self.assertEqual(r["raw_body_change_classification"],
                             "BOTH_SOURCE_BYTES_CHANGED")

    def test_corrupt_raw_ics_must_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bundle(Path(tmp), "one")
            (path / "bls.ics").write_bytes(ICS + b"\nX:tampered")
            with self.assertRaisesRegex(InputError, "checksum"):
                diff.verify(path)

    def test_corrupt_html_must_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bundle(Path(tmp), "one")
            (path / "bls_schedule.html").write_bytes(
                HTML + b"\n<!-- tampered -->")
            with self.assertRaisesRegex(InputError, "checksum"):
                diff.verify(path)

    def test_corrupt_json_report_must_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bundle(Path(tmp), "one")
            report_path = path / "calendar.json"
            r = json.loads(report_path.read_text("utf-8"))
            r["real_orders_permitted"] = True
            report_path.write_text(json.dumps(r), encoding="utf-8")
            with self.assertRaisesRegex(InputError, "mismatch"):
                diff.verify(path)

    def test_missing_manifest_never_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = bundle(Path(tmp), "one")
            (path / "snapshot.json").unlink()
            with self.assertRaises(InputError):
                diff.verify(path)

    def test_backwards_wall_clock_capture_fails(self):
        with self.assertRaisesRegex(InputError, "clocks"):
            snapshot.prepare(ics=ICS, html=HTML,
                             observed_ics_utc=T2,
                             observed_html_utc=T1,
                             mode="LOCAL_COPY")

    def test_elapsed_window_over_120_seconds_fails(self):
        with self.assertRaisesRegex(InputError, "clocks"):
            snapshot.prepare(ics=ICS, html=HTML,
                             observed_ics_utc=T1, observed_html_utc=T3,
                             mode="NETWORK_EXPLICIT_OPT_IN")

    def test_wrong_html_cannot_be_substituted(self):
        with self.assertRaises(InputError):
            snapshot.prepare(
                ics=ICS, html=b"<!DOCTYPE html><html>Blocked</html>",
                observed_ics_utc=T1, observed_html_utc=T2, mode="LOCAL_COPY")

    def test_unknown_calendar_timezone_still_fails(self):
        with self.assertRaises(InputError):
            snapshot.prepare(ics=ICS.replace(b"US-Eastern", b"US-Mars"),
                             html=HTML, observed_ics_utc=T1,
                             observed_html_utc=T2, mode="LOCAL_COPY")

    def test_no_mode_silent_network_in_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(cal, "download",
                              side_effect=AssertionError("network called")):
                with patch("sys.stdout", new_callable=io.StringIO) as out:
                    code = snapshot.main(["--out-dir", str(Path(tmp) / "one"),
                                          "--ics-file", str(Path(tmp) / "x")])
            self.assertEqual(code, 2)
            self.assertIn("FAIL_CLOSED", out.getvalue())
            self.assertFalse((Path(tmp) / "one").exists())

    def test_offline_mode_never_fetches_and_only_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ics_path, html_path = root / "raw.ics", root / "raw.html"
            ics_path.write_bytes(ICS)
            html_path.write_bytes(HTML)
            with patch.object(cal, "download",
                              side_effect=AssertionError("network called")):
                with patch.object(snapshot, "_download_html",
                                  side_effect=AssertionError("network called")):
                    with patch.object(snapshot, "_now", side_effect=[T1, T2]):
                        with patch("sys.stdout", new_callable=io.StringIO) as out:
                            rc = snapshot.main([
                                "--out-dir", str(root / "one"),
                                "--ics-file", str(ics_path),
                                "--html-file", str(html_path)])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(out.getvalue())["collection_mode"],
                             "LOCAL_COPY")
            self.assertEqual(diff.verify(root / "one")["network_calls_expected"], 0)
            self.assertEqual(ics_path.read_bytes(), ICS)
            self.assertEqual(html_path.read_bytes(), HTML)

    def test_explicit_network_once_each_without_implicit_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "one"
            with patch.object(cal, "download", return_value=ICS) as ics_fetch:
                with patch.object(snapshot, "_download_html",
                                  return_value=HTML) as html_fetch:
                    with patch.object(snapshot, "_now", side_effect=[T1, T2]):
                        with patch("sys.stdout", new_callable=io.StringIO) as out:
                            rc = snapshot.main([
                                "--out-dir", str(dest), "--allow-network"])
            self.assertEqual(rc, 0)
            ics_fetch.assert_called_once_with()
            html_fetch.assert_called_once_with()
            self.assertEqual(json.loads(out.getvalue())["snapshot_dir_created"],
                             True)
            self.assertEqual(diff.verify(dest)["collection_mode"],
                             "NETWORK_EXPLICIT_OPT_IN")

    def test_existing_output_folder_blocks_network_before_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "one"
            dest.mkdir()
            with patch.object(cal, "download",
                              side_effect=AssertionError("network called")):
                with patch("sys.stdout", new_callable=io.StringIO) as out:
                    rc = snapshot.main([
                        "--out-dir", str(dest), "--allow-network"])
            self.assertEqual(rc, 2)
            self.assertEqual(json.loads(out.getvalue())["stage"], "INPUT")

    def test_compare_reversed_observations_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = bundle(root, "later", t1=T3, t2=T4)
            second = bundle(root, "earlier", t1=T1, t2=T2)
            with self.assertRaisesRegex(InputError, "order"):
                diff.compare(first, second)

    def test_cli_diff_read_only_and_no_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = bundle(root, "first")
            second = bundle(root, "second", t1=T3, t2=T4)
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                rc = diff.main(["--before-dir", str(first),
                                "--after-dir", str(second)])
            self.assertEqual(rc, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result["network_calls_this_run"], 0)
            self.assertEqual(result["files_written_this_run"], 0)
            self.assertEqual(result["runtime_go_no_go"], "NO_GO")
            self.assertFalse(result["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
