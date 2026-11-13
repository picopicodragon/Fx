"""FWD-1121..1200: BLS ICS/HTML vs raw user-saved official title/time claims."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_bls_dual_snapshot as bls
from research import forward_saved_macro_conflict as conflict
from research import forward_regional_source_intake as regional
from research import forward_evidence_runbook as runbook
from research.offline_backtest import InputError

OBS="2026-11-13T01:48:45Z"
ASOF="2026-11-13T05:00:00Z"
EVENT="2026-11-20T15:00:00Z"
TITLE="State Employment and Unemployment (Monthly)"
CALTXT="Official November 2026 BLS test: State Employment and Unemployment (Monthly), November 20 at 10:00 AM."
ICS=(
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
    b"BEGIN:VEVENT\r\nDTSTART;TZID=US-Eastern:20261120T100000\r\n"
    b"SUMMARY:State Employment and Unemployment (Monthly)\r\n"
    b"END:VEVENT\r\nEND:VCALENDAR\r\n"
)
HTML=(
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


def saved_bls(folder:Path):
    m,calendar=bls.prepare(
        ics=ICS,html=HTML,observed_ics_utc=OBS,
        observed_html_utc=OBS,mode="LOCAL_COPY",days_forward=14)
    bls.write_bundle(out_dir=folder,ics=ICS,html=HTML,
                     manifest=m,report=calendar)
    return folder


def regional_manifest(folder:Path, *, title=TITLE, when=EVENT,
                      currency="USD"):
    folder.mkdir()
    (folder/"calendar.txt").write_text(CALTXT)
    host={
        "USD":"https://www.bls.gov/schedule/news_release/",
        "EUR":"https://www.ecb.europa.eu/press/calendar/",
        "JPY":"https://www.boj.or.jp/en/mopo/",
    }[currency]
    content={
        "schema":regional.SCHEMA,
        "observed_at_utc":"2026-11-13T03:00:00Z",
        "horizon_days":14,
        "sources":[{
            "source_id":"calendar",
            "source_kind":"OFFICIAL_SCHEDULE",
            "filename":"calendar.txt",
            "source_url":host,
            "sha256":hashlib.sha256(CALTXT.encode()).hexdigest(),
            "published_at_utc":"2026-11-12T12:00:00Z",
            "captured_at_utc":"2026-11-13T02:30:00Z",
        }],
        "events":[{
            "event_id":"test-release",
            "currency":currency,
            "event_type":"EMPLOYMENT",
            "title":title,
            "scheduled_at_utc":when,
            "calendar_source_id":"calendar",
            "calendar_excerpt":CALTXT,
            "consensus":None,
        }],
    }
    manifest=folder/"original_manifest.json"
    manifest.write_text(json.dumps(content))
    return manifest


class SavedPublisherScheduleCrosscheckTests(unittest.TestCase):
    def test_exact_title_and_utc_match_is_descriptive_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            regional_file=regional_manifest(root/"regional")
            r=conflict.inspect(asof_utc=ASOF,bls_bundle=b,
                               regional_source_manifest=regional_file)
        self.assertEqual(r["ics_saved_event_count"],1)
        self.assertEqual(r["regional_saved_bls_event_count"],1)
        self.assertEqual(r["exact_same_utc_and_title_count_local_only"],1)
        self.assertEqual(r["ics_only_title_time_claim_count"],0)
        self.assertEqual(r["regional_only_title_time_claim_count"],0)
        self.assertTrue(r["bls_ics_html_slot_disagreement_unresolved"])
        self.assertFalse(r["event_identity_independently_authenticated"])
        self.assertFalse(r["all_fx_calendar_coverage_proven"])
        self.assertFalse(r["bls_html_only_events_automatically_inserted"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_same_title_different_utc_is_conflict_not_auto_revision(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            regional_file=regional_manifest(
                root/"regional", when="2026-11-20T16:00:00Z")
            r=conflict.inspect(asof_utc=ASOF,bls_bundle=b,
                               regional_source_manifest=regional_file)
        self.assertEqual(r["exact_same_utc_and_title_count_local_only"],0)
        self.assertEqual(r["same_title_different_time_unverified_count"],1)
        self.assertIn("SAVED_BLS_SAME_TITLE_DIFFERENT_RELEASE_TIME_CLAIMS",
                      r["unresolved_holds"])
        self.assertFalse(r["real_orders_permitted"])

    def test_same_time_different_title_is_provisional_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            regional_file=regional_manifest(
                root/"regional",title="State Employment and Unemployment")
            r=conflict.inspect(asof_utc=ASOF,bls_bundle=b,
                               regional_source_manifest=regional_file)
        self.assertEqual(r["same_time_different_title_unverified_count"],1)
        self.assertIn("SAVED_BLS_SAME_TIME_DIFFERENT_EVENT_NAME_CLAIMS",
                      r["unresolved_holds"])
        self.assertEqual(r["regional_only_title_time_claim_count"],1)
        self.assertFalse(r["generated_or_authorized_trading_orders"])

    def test_euro_region_event_does_not_claim_bls_exact_match(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            f=regional_manifest(root/"regional",currency="EUR")
            r=conflict.inspect(asof_utc=ASOF,bls_bundle=b,
                               regional_source_manifest=f)
        self.assertEqual(r["regional_saved_bls_event_count"],0)
        self.assertEqual(r["exact_same_utc_and_title_count_local_only"],0)
        self.assertIn("NO_SAVED_BLS_PUBLISHER_REGIONAL_EVENTS",
                      r["unresolved_holds"])

    def test_no_sources_never_claims_reconciled(self):
        r=conflict.inspect(asof_utc=ASOF)
        self.assertEqual(r["exact_same_utc_and_title_count_local_only"],0)
        self.assertIn("BLS_SAVED_SNAPSHOT_MISSING",r["unresolved_holds"])
        self.assertIn("REGIONAL_ORIGINAL_SOURCE_MANIFEST_MISSING",
                      r["unresolved_holds"])
        self.assertFalse(r["real_orders_permitted"])

    def test_regional_only_no_bls_holds(self):
        with tempfile.TemporaryDirectory() as td:
            f=regional_manifest(Path(td)/"regional")
            r=conflict.inspect(asof_utc=ASOF,regional_source_manifest=f)
        self.assertEqual(r["ics_saved_event_count"],0)
        self.assertEqual(r["regional_saved_bls_event_count"],1)
        self.assertIn("BLS_SAVED_SNAPSHOT_MISSING",r["unresolved_holds"])

    def test_bls_only_no_regional_holds(self):
        with tempfile.TemporaryDirectory() as td:
            b=saved_bls(Path(td)/"bls")
            r=conflict.inspect(asof_utc=ASOF,bls_bundle=b)
        self.assertIn("REGIONAL_ORIGINAL_SOURCE_MANIFEST_MISSING",
                      r["unresolved_holds"])
        self.assertEqual(r["regional_saved_bls_event_count"],0)

    def test_changed_bls_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            f=regional_manifest(root/"regional")
            (b/"bls.ics").write_bytes(b"fraud")
            with self.assertRaises(InputError):
                conflict.inspect(asof_utc=ASOF,bls_bundle=b,
                                 regional_source_manifest=f)

    def test_changed_regional_original_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            f=regional_manifest(root/"regional")
            (f.parent/"calendar.txt").write_text(CALTXT+" altered")
            with self.assertRaises(InputError):
                conflict.inspect(asof_utc=ASOF,bls_bundle=b,
                                 regional_source_manifest=f)

    def test_future_bls_capture_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            f=regional_manifest(root/"regional")
            with self.assertRaises(InputError):
                conflict.inspect(asof_utc="2026-11-12T00:00:00Z",
                                 bls_bundle=b,regional_source_manifest=f)

    def test_runbook_includes_crosscheck_without_enabling_orders(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            b=saved_bls(root/"bls")
            f=regional_manifest(root/"regional")
            plan=runbook.empty_plan()
            plan["bls_snapshot_dir"]=str(b)
            plan["regional_source_manifest"]=str(f)
            path=root/"plan.json"
            path.write_text(json.dumps(plan))
            with patch("sys.stdout",new_callable=io.StringIO) as out:
                code=runbook.main([
                    "--plan-file",str(path),"--asof-utc",ASOF])
                result=json.loads(out.getvalue())
            self.assertEqual(code,0)
            cross=result["saved_bls_regional_original_crosscheck"]
            self.assertEqual(cross["exact_same_utc_and_title_count_local_only"],1)
            self.assertTrue(cross["bls_ics_html_slot_disagreement_unresolved"])
            self.assertFalse(result["real_orders_permitted"])
            self.assertFalse(result["demo_orders_permitted"])
            self.assertEqual(result["runtime_go_no_go"],"NO_GO")

    def test_default_runbook_no_crosscheck_because_missing_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=root/"plan.json"
            p.write_text(json.dumps(runbook.empty_plan()))
            with patch("sys.stdout",new_callable=io.StringIO) as out:
                code=runbook.main(["--plan-file",str(p),"--asof-utc",ASOF])
                r=json.loads(out.getvalue())
        self.assertEqual(code,0)
        self.assertIsNone(r["saved_bls_regional_original_crosscheck"])
        self.assertTrue(r["saved_bls_regional_crosscheck_missing"])
        self.assertFalse(r["real_orders_permitted"])

    def test_cli_missing_source_is_read_only_no_go(self):
        with patch("sys.stdout",new_callable=io.StringIO) as out:
            rc=conflict.main(["--asof-utc",ASOF])
            data=json.loads(out.getvalue())
        self.assertEqual(rc,0)
        self.assertEqual(data["network_calls_this_run"],0)
        self.assertEqual(data["orders_sent_this_run"],0)
        self.assertFalse(data["demo_orders_permitted"])

    def test_cli_invalid_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"not-a-snapshot"
            with patch("sys.stdout",new_callable=io.StringIO) as out:
                code=conflict.main(["--asof-utc",ASOF,
                                    "--bls-snapshot-dir",str(bad)])
                data=json.loads(out.getvalue())
        self.assertEqual(code,2)
        self.assertEqual(data["status"],
                         "SAVED_MACRO_SOURCE_CONFLICT_FAIL_CLOSED_NO_GO")
        self.assertFalse(data["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
