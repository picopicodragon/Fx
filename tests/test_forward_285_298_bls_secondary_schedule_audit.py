"""FWD-285..298: selected HTML vs ICS independent-format, NO_GO audit."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_calendar as cal
from research import forward_bls_calendar_crosscheck as cross
from research.offline_backtest import InputError

REFERENCE = (Path(__file__).resolve().parents[1]
             / "research" / "references" / "bls_2026_11_selected_html_schedule.json")
ASOF = "2026-11-13T00:00:00Z"
DATES = [
    "2026-11-13T13:30:00Z",
    "2026-11-17T13:30:00Z",
    "2026-11-18T15:00:00Z",
    "2026-11-20T15:00:00Z",
    "2026-11-20T15:00:00Z",
]


def fixture(dates=None):
    dates = DATES if dates is None else dates
    return {
        "status": "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
        "asof_utc": ASOF,
        "horizon_days": 14,
        "source_url": cal.URL,
        "calendar_sha256": "a" * 64,
        "event_count": len(dates),
        "events": [
            {
                "title": "Unverified publisher ICS title " + str(i),
                "scheduled_at_utc": date,
                "source_url": cal.URL,
                "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
            }
            for i, date in enumerate(dates)
        ],
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
        "release_time_independently_verified": False,
        "source_authenticity_verified": False,
        "calendar_covers_all_fx_events": False,
        "calendar_timezone_alias_us_eastern_assumed": True,
    }


class BlsCrosscheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = json.loads(REFERENCE.read_text(encoding="utf-8"))

    def test_full_slot_counts_match_but_research_only(self):
        r = cross.inspect(fixture(), self.ref)
        self.assertEqual(r["slot_count_result"],
                         "SELECTED_HTML_SLOT_COUNTS_MATCH_UNVERIFIED")
        self.assertEqual(r["calendar_event_count"], 5)
        self.assertEqual(r["matching_slot_instance_count"], 5)
        self.assertEqual(r["missing_selected_html_slot_instances"], 0)
        self.assertEqual(r["unexpected_ics_slot_instances"], 0)
        self.assertFalse(r["release_time_independently_verified"])
        self.assertFalse(r["title_or_release_identity_verified"])
        self.assertFalse(r["source_authenticity_independently_verified"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertTrue(r["safety_hold_latched"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_four_events_detect_one_of_two_same_time_missing(self):
        r = cross.inspect(fixture(DATES[:-1]), self.ref)
        self.assertEqual(r["slot_count_result"],
                         "SELECTED_HTML_SLOT_COUNTS_DISAGREE")
        self.assertEqual(r["calendar_event_count"], 4)
        self.assertEqual(r["selected_html_event_count_within_window"], 5)
        self.assertEqual(r["missing_selected_html_slot_instances"], 1)
        self.assertEqual(
            r["missing_selected_html_slots"],
            [{"scheduled_at_utc": "2026-11-20T15:00:00Z", "count": 1}])
        self.assertEqual(r["unexpected_ics_slot_instances"], 0)

    def test_one_hour_shift_detected_both_directions(self):
        changed = list(DATES)
        changed[1] = "2026-11-17T14:30:00Z"
        r = cross.inspect(fixture(changed), self.ref)
        self.assertEqual(r["missing_selected_html_slot_instances"], 1)
        self.assertEqual(r["unexpected_ics_slot_instances"], 1)

    def test_no_events_fails_audit_coverage(self):
        r = cross.inspect(fixture([]), self.ref)
        self.assertEqual(r["missing_selected_html_slot_instances"], 5)
        self.assertEqual(r["calendar_event_count"], 0)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_matching_timestamp_with_wrong_title_is_not_authenticated(self):
        r = cross.inspect(fixture(), self.ref)
        self.assertTrue(r["date_time_slots_only_not_titles"])
        self.assertFalse(r["title_or_release_identity_verified"])

    def test_ref_month_cannot_cover_cross_month_window(self):
        report = fixture()
        report["asof_utc"] = "2026-11-27T00:00:00Z"
        report["event_count"] = 0
        report["events"] = []
        with self.assertRaisesRegex(InputError, "entire calendar horizon"):
            cross.inspect(report, self.ref)

    def test_bad_status_cannot_be_transformed_into_audit(self):
        report = fixture()
        report["runtime_go_no_go"] = "GO"
        with self.assertRaises(InputError):
            cross.inspect(report, self.ref)

    def test_wrong_event_count_fails_closed(self):
        report = fixture()
        report["event_count"] = 4
        with self.assertRaises(InputError):
            cross.inspect(report, self.ref)

    def test_outside_horizon_event_is_rejected(self):
        report = fixture(["2026-11-28T13:30:00Z"])
        with self.assertRaisesRegex(InputError, "outside claimed horizon"):
            cross.inspect(report, self.ref)

    def test_source_url_identity_required(self):
        report = fixture()
        report["source_url"] = "https://other.example/ics"
        with self.assertRaises(InputError):
            cross.inspect(report, self.ref)

    def test_reference_date_ambiguous_or_out_of_scope_refused(self):
        ref = copy.deepcopy(self.ref)
        ref["events"][0]["local_time_et"] = "2026-11-01T01:30:00"
        with self.assertRaisesRegex(InputError, "ambiguous"):
            cross.inspect(fixture(), ref)
        ref = copy.deepcopy(self.ref)
        ref["events"][0]["local_time_et"] = "2026-12-01T10:00:00"
        with self.assertRaises(InputError):
            cross.inspect(fixture(), ref)

    def test_invalid_reference_source_is_not_silent(self):
        ref = copy.deepcopy(self.ref)
        ref["source_url"] = "https://example.com/list"
        with self.assertRaises(InputError):
            cross.inspect(fixture(), ref)

    def test_different_month_and_digest_type_rejected(self):
        report = fixture()
        report["calendar_sha256"] = 0
        with self.assertRaises(InputError):
            cross.inspect(report, self.ref)

    def test_utc_timestamp_requires_explicit_z(self):
        report = fixture()
        report["events"][0]["scheduled_at_utc"] = "2026-11-13T13:30:00-00:00"
        with self.assertRaises(InputError):
            cross.inspect(report, self.ref)

    def test_cli_offline_reads_evidence_and_never_writes(self):
        with tempfile.TemporaryDirectory() as dirname:
            folder = Path(dirname)
            cal_path = folder / "calendar.json"
            ref_path = folder / "official.json"
            cal_path.write_text(json.dumps(fixture()), encoding="utf-8")
            ref_path.write_text(json.dumps(self.ref), encoding="utf-8")
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                result = cross.main([
                    "--calendar-report", str(cal_path),
                    "--reference-file", str(ref_path)])
            self.assertEqual(result, 0)
            obj = json.loads(stream.getvalue())
            self.assertEqual(obj["network_calls_this_run"], 0)
            self.assertFalse(obj["new_evidence_files_written"])
            self.assertEqual(set(folder.iterdir()), {cal_path, ref_path})

    def test_missing_local_file_returns_safe_fail_closed(self):
        with tempfile.TemporaryDirectory() as dirname:
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                code = cross.main([
                    "--calendar-report", str(Path(dirname) / "missing.json"),
                    "--reference-file", str(REFERENCE)])
            self.assertEqual(code, 2)
            result = json.loads(stream.getvalue())
            self.assertEqual(result["status"],
                             "BLS_SECOND_SOURCE_SLOT_AUDIT_FAIL_CLOSED_NO_GO")
            self.assertFalse(result["real_orders_permitted"])
            self.assertEqual(result["runtime_go_no_go"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
