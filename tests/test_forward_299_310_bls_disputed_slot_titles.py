"""FWD-299..310: bounded title evidence for BLS calendar discrepancies."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from research import forward_bls_calendar_crosscheck as cross
from research.forward_bls_calendar import URL

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "research/references/bls_2026_11_selected_html_schedule.json"
ASOF = "2026-11-13T00:47:40Z"
FRIDAY = "2026-11-20T15:00:00Z"
EVENTS = [
    ("2026-11-13T13:30:00Z", "Producer Price Index for October 2026"),
    ("2026-11-17T13:30:00Z", "U.S. Import and Export Price Indexes for October 2026"),
    ("2026-11-18T15:00:00Z",
     "Employer-Reported Workplace Injuries and Illnesses (Annual) for 2025"),
    (FRIDAY, "State Employment and Unemployment (Monthly) for October 2026"),
]


def report(events=None):
    events = EVENTS if events is None else events
    return {
        "status": "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
        "source_url": URL,
        "asof_utc": ASOF,
        "horizon_days": 14,
        "calendar_sha256": "a" * 64,
        "event_count": len(events),
        "events": [
            {"title": title, "scheduled_at_utc": dt,
             "source_url": URL,
             "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED"}
            for dt, title in events
        ],
        "source_authenticity_verified": False,
        "calendar_covers_all_fx_events": False,
        "calendar_timezone_alias_us_eastern_assumed": True,
        "release_time_independently_verified": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


class TitleDiscrepancyEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = json.loads(REF.read_text(encoding="utf-8"))

    def test_missing_duplicate_slot_shows_both_html_candidates(self):
        result = cross.inspect(report(), self.ref)
        evidence, = result["disputed_slot_title_evidence"]
        self.assertEqual(evidence["scheduled_at_utc"], FRIDAY)
        self.assertEqual(evidence["ics_event_title_count"], 1)
        self.assertEqual(evidence["selected_html_title_count"], 2)
        self.assertEqual(evidence["ics_titles_unverified"],
                         [EVENTS[-1][1]])
        self.assertEqual(len(evidence["html_titles_unverified"]), 2)
        self.assertEqual(evidence["literal_identical_titles_unverified"],
                         [EVENTS[-1][1]])
        self.assertFalse(evidence["candidate_identity_verified"])
        self.assertFalse(evidence["auto_resolve_or_backfill_allowed"])
        self.assertFalse(result["missing_calendar_event_auto_insert_allowed"])
        self.assertEqual(result["missing_selected_html_slot_instances"], 1)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_when_ics_title_differs_the_missing_identity_is_unknown(self):
        events = EVENTS[:-1] + [(FRIDAY, "Industry productivity event")]
        result = cross.inspect(report(events), self.ref)
        evidence = result["disputed_slot_title_evidence"][0]
        self.assertEqual(evidence["literal_identical_titles_unverified"], [])
        self.assertEqual(len(evidence["html_titles_unverified"]), 2)
        self.assertFalse(result["title_alias_or_release_identity_inference_allowed"])
        self.assertFalse(result["release_time_independently_verified"])

    def test_matching_slot_counts_produce_no_disputed_candidates(self):
        complete = EVENTS + [(
            FRIDAY,
            "Total Factor Productivity for Major Industries for Annual 2025")]
        result = cross.inspect(report(complete), self.ref)
        self.assertEqual(result["slot_count_result"],
                         "SELECTED_HTML_SLOT_COUNTS_MATCH_UNVERIFIED")
        self.assertEqual(result["disputed_slot_title_evidence"], [])
        self.assertFalse(result["title_or_release_identity_verified"])

    def test_mismatched_title_but_matching_slot_is_not_identity_proof(self):
        complete = EVENTS + [(FRIDAY, "unrecognized same-time event")]
        result = cross.inspect(report(complete), self.ref)
        self.assertEqual(result["disputed_slot_title_evidence"], [])
        self.assertFalse(result["title_or_release_identity_verified"])

    def test_extra_calendar_slot_is_reported_with_ics_title(self):
        extra = EVENTS + [("2026-11-23T13:30:00Z", "Additional unverified item")]
        result = cross.inspect(report(extra), self.ref)
        self.assertEqual(len(result["disputed_slot_title_evidence"]), 2)
        candidates = {x["scheduled_at_utc"]: x
                      for x in result["disputed_slot_title_evidence"]}
        self.assertEqual(candidates["2026-11-23T13:30:00Z"][
            "ics_titles_unverified"], ["Additional unverified item"])
        self.assertEqual(candidates["2026-11-23T13:30:00Z"][
            "html_titles_unverified"], [])

    def test_evidence_caps_long_same_slot_lists(self):
        repeated = [(FRIDAY, "unverified title " + str(i))
                    for i in range(20)]
        result = cross.inspect(report(EVENTS[:-1] + repeated), self.ref)
        x = result["disputed_slot_title_evidence"][0]
        self.assertEqual(x["ics_event_title_count"], 20)
        self.assertEqual(x["ics_titles_omitted_count"], 8)
        self.assertEqual(len(x["ics_titles_unverified"]), 12)

    def test_evidence_caps_number_of_slots(self):
        baseline = datetime.fromisoformat("2026-11-21T00:00:00+00:00")
        added = [
            ((baseline + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "unverified item " + str(i))
            for i in range(20)
        ]
        result = cross.inspect(report(EVENTS + added), self.ref)
        self.assertEqual(len(result["disputed_slot_title_evidence"]), 12)
        self.assertEqual(result["disputed_slot_title_evidence_omitted_count"], 9)
        self.assertFalse(result["real_orders_permitted"])

    def test_bogus_event_title_still_rejected_before_display(self):
        modified = report()
        modified["events"][0]["title"] = "x" * 251
        with self.assertRaises(Exception):
            cross.inspect(modified, self.ref)

    def test_read_only_inspection_has_no_input_mutation(self):
        a = report()
        b = copy.deepcopy(self.ref)
        a_before, b_before = copy.deepcopy(a), copy.deepcopy(b)
        r = cross.inspect(a, b)
        self.assertEqual(a, a_before)
        self.assertEqual(b, b_before)
        self.assertEqual(r["network_calls_this_run"], 0)
        self.assertFalse(r["new_evidence_files_written"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertEqual(r["actual_orders_sent"], 0)


if __name__ == "__main__":
    unittest.main()
