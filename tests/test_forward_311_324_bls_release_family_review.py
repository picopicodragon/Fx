"""FWD-311..324: fail-closed, provisional BLS release-family title review."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from research import forward_bls_calendar_crosscheck as cross
from research.forward_bls_calendar import URL

REF = (Path(__file__).resolve().parents[1] / "research" / "references"
       / "bls_2026_11_selected_html_schedule.json")
SLOT = "2026-11-20T15:00:00Z"
SHORT = "State Employment and Unemployment (Monthly)"
LONG = "State Employment and Unemployment (Monthly) for October 2026"
OTHER = "Total Factor Productivity for Major Industries for Annual 2025"


def calendar(ics_title: str = SHORT) -> dict:
    events = [
        ("2026-11-13T13:30:00Z", "Producer Price Index"),
        ("2026-11-17T13:30:00Z", "U.S. Import and Export Price Indexes"),
        ("2026-11-18T15:00:00Z", "Employer-Reported Workplace Injuries and Illnesses (Annual)"),
        (SLOT, ics_title),
    ]
    return {
        "status": "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
        "asof_utc": "2026-11-13T00:47:40Z",
        "horizon_days": 14,
        "source_url": URL,
        "calendar_sha256": "a" * 64,
        "event_count": len(events),
        "events": [
            {"title": name, "scheduled_at_utc": when,
             "source_url": URL,
             "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED"}
            for when, name in events
        ],
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
        "release_time_independently_verified": False,
        "source_authenticity_verified": False,
        "calendar_covers_all_fx_events": False,
        "calendar_timezone_alias_us_eastern_assumed": True,
    }


class ReleaseFamilyReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(REF.read_text("utf-8"))

    def test_actual_ics_title_has_single_provisional_family_candidate(self):
        audit = cross.inspect(calendar(), self.reference)
        self.assertEqual(audit["slot_count_result"],
                         "SELECTED_HTML_SLOT_COUNTS_DISAGREE")
        evidence, = audit["disputed_slot_title_evidence"]
        self.assertEqual(evidence["scheduled_at_utc"], SLOT)
        review = evidence["release_family_candidate_review"]
        self.assertEqual(review["relationship_status"],
                         "UNIQUE_LEXICAL_CANDIDATES_ONLY")
        self.assertEqual(review["provisional_title_pairs"], [{
            "ics_title_unverified": SHORT,
            "html_title_unverified": LONG,
            "relation": "ICS_TITLE_PREFIX_BEFORE_FOR",
            "correspondence_provisional_only": True,
        }])
        self.assertEqual(review["html_only_title_candidates_not_in_ics"],
                         [OTHER])
        self.assertFalse(review["source_revision_or_omission_resolved"])
        self.assertFalse(review["automatic_missing_event_creation_permitted"])
        self.assertFalse(audit["missing_calendar_event_auto_insert_allowed"])
        self.assertFalse(audit["title_or_release_identity_verified"])
        self.assertFalse(audit["release_time_independently_verified"])
        self.assertFalse(audit["real_orders_permitted"])
        self.assertFalse(audit["demo_orders_permitted"])
        self.assertTrue(audit["safety_hold_latched"])

    def test_exact_title_is_a_candidate_not_verified(self):
        review = cross._family_correspondence_for_review(
            [LONG], [LONG, OTHER])
        self.assertEqual(review["provisional_title_pairs"][0]["relation"],
                         "EXACT_TITLE")
        self.assertEqual(review["html_only_title_candidates_not_in_ics"],
                         [OTHER])
        self.assertFalse(review["all_title_relationships_independently_verified"])

    def test_unmatched_ics_title_never_forces_missing_candidate(self):
        review = cross._family_correspondence_for_review(
            ["Different release"], [LONG, OTHER])
        self.assertEqual(review["relationship_status"],
                         "NO_UNIQUE_TITLE_RELATIONSHIP")
        self.assertEqual(review["html_only_title_candidates_not_in_ics"], [])

    def test_ambiguous_same_family_name_disables_guessing(self):
        review = cross._family_correspondence_for_review(
            [SHORT], [LONG, SHORT + " for September 2026"])
        self.assertEqual(review["relationship_status"],
                         "NO_UNIQUE_TITLE_RELATIONSHIP")
        self.assertEqual(review["provisional_title_pairs"], [])
        self.assertEqual(review["html_only_title_candidates_not_in_ics"], [])

    def test_duplicate_observed_titles_disables_guessing(self):
        review = cross._family_correspondence_for_review(
            [SHORT, SHORT], [LONG, OTHER])
        self.assertEqual(review["relationship_status"],
                         "DUPLICATE_TITLES_AMBIGUOUS")
        self.assertFalse(review["source_revision_or_omission_resolved"])

    def test_many_to_one_candidate_disables_guessing(self):
        review = cross._family_correspondence_for_review(
            [LONG, SHORT], [LONG, OTHER])
        self.assertEqual(review["relationship_status"],
                         "MANY_TO_ONE_TITLE_AMBIGUOUS")
        self.assertEqual(review["html_only_title_candidates_not_in_ics"], [])

    def test_limit_prevents_suggesting_incomplete_title_set(self):
        names = [SHORT + " " + str(i) for i in range(13)]
        review = cross._family_correspondence_for_review(names, [LONG, OTHER])
        self.assertEqual(review["relationship_status"],
                         "BOUNDED_REVIEW_REQUIRED")
        self.assertEqual(review["html_only_title_candidates_not_in_ics"], [])

    def test_unrelated_titles_remain_no_match_in_full_audit(self):
        audit = cross.inspect(calendar("Unrelated observed ICS item"),
                              self.reference)
        review = audit["disputed_slot_title_evidence"][0][
            "release_family_candidate_review"]
        self.assertEqual(review["relationship_status"],
                         "NO_UNIQUE_TITLE_RELATIONSHIP")
        self.assertEqual(review["html_only_title_candidates_not_in_ics"], [])

    def test_source_records_and_calendar_are_unchanged(self):
        source = calendar()
        reference = copy.deepcopy(self.reference)
        before_source, before_ref = copy.deepcopy(source), copy.deepcopy(reference)
        audit = cross.inspect(source, reference)
        self.assertEqual(source, before_source)
        self.assertEqual(reference, before_ref)
        self.assertEqual(audit["network_calls_this_run"], 0)
        self.assertEqual(audit["API_calls_this_run"], 0)
        self.assertEqual(audit["actual_orders_sent"], 0)
        self.assertFalse(audit["new_evidence_files_written"])

    def test_no_ics_titles_is_unverified_not_authenticated(self):
        review = cross._family_correspondence_for_review([], [LONG, OTHER])
        self.assertEqual(review["html_only_title_candidates_not_in_ics"],
                         [LONG, OTHER])
        self.assertFalse(review["source_revision_or_omission_resolved"])
        self.assertFalse(review["automatic_missing_event_creation_permitted"])


if __name__ == "__main__":
    unittest.main()
