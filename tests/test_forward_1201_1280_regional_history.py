"""FWD-1201..1280: authentic local byte fixtures, time-ordered snapshot audits."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_regional_evidence_history as history
from research import forward_regional_source_intake as intake
from research.offline_backtest import InputError

ASOF = "2026-11-15T05:00:00Z"
BASE = "2026-11-13T03:00:00Z"
NEXT = "2026-11-14T03:00:00Z"
EVENT = "2026-11-20T15:00:00Z"
LATE = "2026-11-20T16:00:00Z"


def snapshot(root: Path, label: str, *, observed=BASE,
             currency="USD", event_time=EVENT,
             event_id="monthly-cpi", title="Consumer Price Index",
             forecast=None, source_suffix=""):
    folder = root / label
    folder.mkdir()
    text = ("Saved original source for " + currency + ": " + title
            + " release clock " + event_time + source_suffix)
    (folder / "schedule.txt").write_text(text, encoding="utf-8")
    url = {
        "USD": "https://www.bls.gov/schedule/news_release/",
        "EUR": "https://www.ecb.europa.eu/press/calendars/",
        "JPY": "https://www.boj.or.jp/en/mopo/",
    }[currency]
    sources = [{
        "source_id": "calendar",
        "source_kind": "OFFICIAL_SCHEDULE",
        "filename": "schedule.txt",
        "source_url": url,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "published_at_utc": "2026-11-12T12:00:00Z",
        "captured_at_utc": "2026-11-13T02:00:00Z",
    }]
    consensus = None
    if forecast is not None:
        price_text = "Independent saved forecast: consensus "+forecast+" percent."
        (folder / "forecast.txt").write_text(price_text, encoding="utf-8")
        sources.append({
            "source_id": "forecast",
            "source_kind": "PRE_RELEASE_CONSENSUS",
            "filename": "forecast.txt",
            "source_url": "https://survey.example.org/consensus",
            "sha256": hashlib.sha256(price_text.encode("utf-8")).hexdigest(),
            "published_at_utc": "2026-11-12T20:00:00Z",
            "captured_at_utc": "2026-11-13T02:30:00Z",
        })
        consensus = {
            "source_id": "forecast", "excerpt": price_text,
            "value": forecast, "unit": "percent",
        }
    doc = {
        "schema": intake.SCHEMA,
        "observed_at_utc": observed,
        "horizon_days": 14,
        "sources": sources,
        "events": [{
            "event_id": event_id, "currency": currency,
            "event_type": "INFLATION", "title": title,
            "scheduled_at_utc": event_time,
            "calendar_source_id": "calendar",
            "calendar_excerpt": text, "consensus": consensus,
        }],
    }
    p = folder / "original_manifest.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def history_file(root, entries):
    p = root / "history.json"
    obj = {
        "schema": history.SCHEMA,
        "entries": [{
            "manifest_path": str(src.relative_to(root)),
            "manifest_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        } for src in entries],
    }
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def update(path, fn):
    data=json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def cli(path,asof=ASOF):
    with patch("sys.stdout", new_callable=io.StringIO) as o:
        rc=history.main(["--history-file", str(path), "--asof-utc", asof])
    return rc,json.loads(o.getvalue())


class RegionalTimelineTests(unittest.TestCase):
    def test_empty_history_is_no_go_not_complete(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=history_file(root, [])
            r=history.inspect(p,asof_utc=ASOF)
        self.assertEqual(r["registered_snapshot_count"],0)
        self.assertEqual(r["upcoming_unverified_event_count"],0)
        self.assertEqual(r["potentially_affected_pair_event_counts_research_only"],
                         {"USD/JPY":0,"EUR/JPY":0,"EUR/USD":0})
        self.assertIn("NO_SAVED_REGIONAL_EVIDENCE_HISTORY",r["unresolved_holds"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_single_us_event_is_not_three_currency_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first")
            p=history_file(root,[a])
            r=history.inspect(p,asof_utc=ASOF)
        self.assertEqual(r["registered_snapshot_count"],1)
        self.assertEqual(r["distinct_event_ids_across_history"],1)
        self.assertEqual(r["upcoming_event_count_by_currency_unattested"],
                         {"USD":1,"EUR":0,"JPY":0})
        self.assertEqual(r["potentially_affected_pair_event_counts_research_only"],
                         {"USD/JPY":1,"EUR/JPY":0,"EUR/USD":1})
        self.assertIn("NO_UPCOMING_EUR_EVENT_IN_SAVED_HISTORY",
                      r["unresolved_holds"])
        self.assertIn("NO_UPCOMING_JPY_EVENT_IN_SAVED_HISTORY",
                      r["unresolved_holds"])
        self.assertTrue(r["capture_missing_or_older_than_24h_by_currency"]["USD"])

    def test_3_currencies_with_3_manifests_still_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=snapshot(root,"usd",currency="USD",event_id="usd-cpi",forecast="2.7")
            b=snapshot(root,"eur",currency="EUR",event_id="eur-cpi",forecast="1.9")
            c=snapshot(root,"jpy",currency="JPY",event_id="jpy-cpi",forecast="1.4")
            p=history_file(root,[a,b,c])
            r=history.inspect(p,asof_utc=ASOF)
        self.assertEqual(r["upcoming_event_count_by_currency_unattested"],
                         {"USD":1,"EUR":1,"JPY":1})
        self.assertEqual(r["upcoming_event_with_consensus_count_by_currency_unattested"],
                         {"USD":1,"EUR":1,"JPY":1})
        self.assertEqual(r["potentially_affected_pair_event_counts_research_only"],
                         {"USD/JPY":2,"EUR/JPY":2,"EUR/USD":2})
        self.assertFalse(r["future_event_coverage_claimed_complete"])
        self.assertFalse(r["independent_publisher_or_clock_authentication"])
        self.assertFalse(r["real_time_release_blackout_executed"])
        self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_release_time_revision_detected_without_auto_schedule_update(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=snapshot(root,"first",forecast="2.7")
            b=snapshot(root,"second",observed=NEXT,event_time=LATE,forecast="2.7")
            p=history_file(root,[a,b])
            r=history.inspect(p,asof_utc=ASOF)
        self.assertEqual(r["recorded_revision_occurrence_count"],1)
        self.assertIn("PUBLISHED_RELEASE_CLOCK_CLAIM_CHANGED",
                      r["revision_preview"][0]["change_types"])
        self.assertEqual(r["distinct_event_ids_across_history"],1)
        self.assertFalse(r["title_or_schedule_revisions_automatically_applied_to_trading"])
        self.assertIn("SAVED_RELEASE_OR_CONSENSUS_REVISIONS_REQUIRE_REVIEW",
                      r["unresolved_holds"])

    def test_forecast_added_detected_without_publisher_authentication(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first")
            b=snapshot(root,"second",observed=NEXT,forecast="2.7")
            p=history_file(root,[a,b]); r=history.inspect(p,asof_utc=ASOF)
        self.assertIn("CONSENSUS_ADDED_WITH_SELF_REPORTED_TIME",
                      r["revision_preview"][0]["change_types"])
        self.assertEqual(r["upcoming_event_with_consensus_count_by_currency_unattested"]["USD"],1)
        self.assertFalse(r["point_in_time_forecast_meaning_independently_verified"])

    def test_forecast_disappeared_does_not_claim_covered(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first",forecast="2.7")
            b=snapshot(root,"second",observed=NEXT)
            p=history_file(root,[a,b]); r=history.inspect(p,asof_utc=ASOF)
        self.assertIn("CONSENSUS_NO_LONGER_PRESENT_IN_NEW_SNAPSHOT",
                      r["revision_preview"][0]["change_types"])
        self.assertEqual(r["upcoming_event_with_consensus_count_by_currency_unattested"]["USD"],0)
        self.assertIn("MISSING_USD_POINT_IN_TIME_CONSENSUS",r["unresolved_holds"])

    def test_forecast_value_change_reported_not_claimed_true(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first",forecast="2.7")
            b=snapshot(root,"second",observed=NEXT,forecast="2.8")
            p=history_file(root,[a,b]); r=history.inspect(p,asof_utc=ASOF)
        self.assertIn("CONSENSUS_VALUE_OR_SOURCE_CLAIM_CHANGED",
                      r["revision_preview"][0]["change_types"])
        self.assertFalse(r["independent_publisher_or_clock_authentication"])

    def test_same_event_unchanged_in_later_snapshot_no_revision(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first")
            b=snapshot(root,"second",observed=NEXT)
            p=history_file(root,[a,b]); r=history.inspect(p,asof_utc=ASOF)
        self.assertEqual(r["recorded_revision_occurrence_count"],0)
        self.assertEqual(r["total_raw_event_claim_instances"],2)
        self.assertEqual(r["distinct_event_ids_across_history"],1)

    def test_event_from_old_capture_not_automatically_wiped_if_new_currency_differs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=snapshot(root,"usd",currency="USD",event_id="usa")
            b=snapshot(root,"eur",currency="EUR",event_id="eur")
            p=history_file(root,[a,b]); r=history.inspect(p,asof_utc=ASOF)
        self.assertEqual(r["upcoming_event_count_by_currency_unattested"]["USD"],1)
        self.assertEqual(r["upcoming_event_count_by_currency_unattested"]["EUR"],1)

    def test_old_event_not_counted_as_upcoming(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"only")
            p=history_file(root,[a])
            r=history.inspect(p,asof_utc="2026-11-21T00:00:00Z")
        self.assertEqual(r["upcoming_unverified_event_count"],0)
        self.assertEqual(r["earliest_upcoming_release_utc_unattested"],None)
        self.assertIn("NO_UPCOMING_USD_EVENT_IN_SAVED_HISTORY",r["unresolved_holds"])

    def test_historical_manifest_digest_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"only"); p=history_file(root,[a])
            a.write_text(a.read_text()+" ")
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_original_saved_bytes_tamper_rejected_even_if_manifest_pin_valid(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"only"); p=history_file(root,[a])
            (a.parent/"schedule.txt").write_text("modified source")
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_same_manifest_listed_twice_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"only"); p=history_file(root,[a,a])
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_snapshot_observation_time_reversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=snapshot(root,"older")
            b=snapshot(root,"newer",observed=NEXT)
            p=history_file(root,[b,a])
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_same_timestamp_same_event_contradictory_revision_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=snapshot(root,"one",forecast="2.7")
            b=snapshot(root,"two",forecast="2.8")
            p=history_file(root,[a,b])
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_same_release_claim_conflicting_ids_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=snapshot(root,"one",event_id="cpi-a")
            b=snapshot(root,"two",observed=NEXT,event_id="cpi-b")
            p=history_file(root,[a,b])
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_future_capture_claim_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"later",observed=NEXT)
            p=history_file(root,[a])
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc="2026-11-13T12:00:00Z")

    def test_history_path_traversal_not_globbed_or_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first"); p=history_file(root,[a])
            update(p,lambda d:d["entries"][0].__setitem__(
                "manifest_path","*/original_manifest.json"))
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_history_with_unknown_keys_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first"); p=history_file(root,[a])
            update(p,lambda d:d.__setitem__("allow_demo_orders",True))
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_history_with_unknown_entry_keys_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first"); p=history_file(root,[a])
            update(p,lambda d:d["entries"][0].__setitem__("approve",True))
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_limit_33_entries_rejected_without_source_reads(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=history_file(root,[])
            update(p,lambda d:d.__setitem__(
                "entries",[{"manifest_path":"fake","manifest_sha256":"a"*64}]*33))
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_symlink_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"first")
            try:
                (root/"alias").symlink_to(a.parent,target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks disabled by test host")
            p=history_file(root,[a])
            update(p,lambda d:d["entries"][0].__setitem__(
                "manifest_path","alias/original_manifest.json"))
            with self.assertRaises(InputError):
                history.inspect(p,asof_utc=ASOF)

    def test_cli_invalid_provenance_fails_closed_no_order(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"only"); p=history_file(root,[a])
            update(p,lambda d:d["entries"][0].__setitem__(
                "manifest_sha256","f"*64))
            rc,res=cli(p)
        self.assertEqual(rc,2)
        self.assertEqual(res["status"],"REGIONAL_EVIDENCE_HISTORY_FAIL_CLOSED_NO_GO")
        self.assertFalse(res["real_orders_permitted"])
        self.assertFalse(res["demo_orders_permitted"])
        self.assertEqual(res["network_calls_this_run"],0)

    def test_cli_valid_history_never_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=snapshot(root,"only"); p=history_file(root,[a])
            before=p.read_bytes()
            rc,res=cli(p)
            self.assertEqual(p.read_bytes(),before)
        self.assertEqual(rc,0)
        self.assertEqual(res["runtime_go_no_go"],"NO_GO")
        self.assertEqual(res["orders_sent_this_run"],0)


if __name__ == "__main__":
    unittest.main()
