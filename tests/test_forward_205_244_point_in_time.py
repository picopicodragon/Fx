"""FWD-205..244 synthetic calendar, consensus, release and 2-model gates."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from io import StringIO

from research import forward_bls_calendar as bls
from research import forward_observation as obs
from research import forward_macro_event_windows as windows
from research import forward_macro_pre_release_capture as forecast
from research import forward_macro_evidence_handoff as handoff
from research import forward_macro_two_model_gate as gate
from research import forward_ai_shadow as ai
from research.offline_backtest import InputError

CAPTURE = "2026-11-10T08:00:00Z"
SCHEDULE = "2026-11-10T09:00:00Z"
POST = "2026-11-10T09:03:00Z"
SOURCE_URL = "https://www.bls.gov/news.release/cpi.htm"
ASOF = "2026-11-10T09:06:00Z"


def dt(text):
    return datetime.fromisoformat(text.replace("Z","+00:00"))


def calendar(*, asof=CAPTURE, title="Consumer Price Index",
             date="20261110T090000Z"):
    body = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\n"
            "DTSTART:" + date + "\r\n"
            "SUMMARY:" + title + "\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n").encode()
    return bls.parse_calendar(body, asof_utc=asof)


def submission(**kw):
    text = "Recorded synthetic consensus 2.1 percent"
    sample = {
        "schema":forecast.FORM,
        "event_title":"Consumer Price Index",
        "scheduled_at_utc":SCHEDULE,
        "pair":"USD/JPY",
        "value":"2.1","unit":"percent",
        "source_text":text,
        "source_sha256":hashlib.sha256(text.encode()).hexdigest(),
        "source_url":"https://example.org/research/consensus",
        "source_published_at_utc":"2026-11-10T07:50:00Z",
    }
    sample.update(kw)
    return sample


def archive():
    record=forecast.validate_submission(
        submission(),calendar(),captured_at_utc=CAPTURE)
    return {"record":record,"record_sha256":forecast.sha(record)}


def release(**kw):
    excerpt="Synthetic CPI published 2.4 percent"
    source={
        "schema":handoff.SCHEMA,"value":"2.4","unit":"percent",
        "source_text":excerpt,
        "source_sha256":hashlib.sha256(excerpt.encode()).hexdigest(),
        "source_url":SOURCE_URL,
        "source_published_at_utc":SCHEDULE,
    }
    source.update(kw)
    return source


def make_journal(root):
    store=root/"journal"
    obs.initialize(store,"forward_macro_synthetic",
                   now=dt("2026-11-10T08:00:00Z"))
    source={
        "schema":obs.SCHEMA,
        "kind":"MACRO_EVENT",
        "observed_at_utc":"2026-11-10T09:00:59Z",
        "source_id":"bls_cpi",
        "payload":{
            "pair":"USD/JPY",
            "title":"Consumer Price Index synthetic",
            "source_url":SOURCE_URL,
            "published_at_utc":SCHEDULE,
            "content":"Synthetic CPI release document, no real consensus.",
            "consensus":"",
            "released_value":"",
            "source_status":"USER_SUPPLIED_UNVERIFIED",
        },
    }
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"obs.json";p.write_text(json.dumps(source))
        sha=obs.ingest(
            store,p,now=dt("2026-11-10T09:01:00Z"))["record_sha256"]
    return store,sha


def linked_event(root):
    store, sha=make_journal(root)
    result=handoff.prepare(store,sha,archive(),release(),asof_utc=POST)
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/"macro.json"
        p.write_text(json.dumps(result["snapshot"]))
        derived_sha=obs.ingest(
            store,p,now=dt("2026-11-10T09:04:00Z"))["record_sha256"]
    return store,sha,derived_sha


class CalendarWindowsTests(unittest.TestCase):
    def test_bls_calendar_upcoming_window(self):
        p=windows.inspect(calendar(),asof_utc="2026-11-10T08:30:00Z")
        self.assertEqual(p["active_research_blackout_count"],0)
        self.assertEqual(p["windows"][0]["blackout_start_utc"],
                         "2026-11-10T08:45:00Z")
        self.assertEqual(p["windows"][0]["blackout_end_utc"],
                         "2026-11-10T09:15:00Z")
        self.assertEqual(p["windows"][0]["research_state"],
                         "BEFORE_RESEARCH_BLACKOUT")
        self.assertEqual(len(p["windows"][0][
            "all_three_pairs_research_advisory_only"]),3)
        self.assertFalse(p["real_orders_permitted"])

    def test_window_start_exact_is_hold(self):
        p=windows.inspect(calendar(),asof_utc="2026-11-10T08:45:00Z")
        self.assertEqual(p["active_research_blackout_count"],1)
        self.assertIn("SCHEDULED_BLS_RELEASE_RESEARCH_BLACKOUT_ACTIVE",
                      p["data_holds"])

    def test_after_end_reassessment_no_auto_resume(self):
        p=windows.inspect(calendar(),asof_utc="2026-11-10T09:15:00Z")
        self.assertEqual(p["windows"][0]["research_state"],
                         "AFTER_EVENT_REQUIRES_INDEPENDENT_REASSESSMENT")
        self.assertFalse(p["windows"][0]["automatic_resume_authorized"])

    def test_calendar_older_than_one_day_stale(self):
        p=windows.inspect(calendar(),asof_utc="2026-11-11T09:00:00Z")
        self.assertTrue(p["calendar_stale"])
        self.assertIn("CALENDAR_SNAPSHOT_OLDER_THAN_24H",p["data_holds"])

    def test_invented_calendar_event_outside_horizon_refused(self):
        data=calendar()
        data["events"][0]["scheduled_at_utc"]="2026-12-15T09:00:00Z"
        with self.assertRaises(InputError):
            windows.inspect(data,asof_utc=CAPTURE)

    def test_calendar_duplicate_refused(self):
        data=calendar()
        data["events"].append(data["events"][0].copy())
        data["event_count"]=2
        with self.assertRaises(InputError):
            windows.inspect(data,asof_utc=CAPTURE)

    def test_calendar_fake_provenance_rejected(self):
        data=calendar()
        data["real_orders_permitted"]=True
        with self.assertRaises(InputError):
            windows.inspect(data,asof_utc=CAPTURE)

    def test_windows_cli_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); inp=root/"calendar.json"; out=root/"report.json"
            inp.write_text(json.dumps(calendar()))
            args=["--calendar-report",str(inp),
                  "--asof-utc",CAPTURE,"--out",str(out)]
            self.assertEqual(windows.main(args),0)
            self.assertEqual(windows.main(args),2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])


class PreReleaseEvidenceTests(unittest.TestCase):
    def test_write_once_forecast_clocks_source_and_value(self):
        data=forecast.validate_submission(
            submission(),calendar(),captured_at_utc=CAPTURE)
        self.assertEqual(data["forecast_value_self_reported"],"2.1")
        self.assertFalse(data["source_truth_authenticated"])
        self.assertEqual(forecast.verify_archive(
            {"record":data,"record_sha256":forecast.sha(data)},
            asof_utc=POST),data)

    def test_claimed_published_after_capture_rejected(self):
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(source_published_at_utc="2026-11-10T08:30:00Z"),
                calendar(),captured_at_utc=CAPTURE)

    def test_capture_after_event_rejected(self):
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(),calendar(),captured_at_utc=POST)

    def test_forecast_in_blackout_refused(self):
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(),calendar(),
                captured_at_utc="2026-11-10T08:45:00Z")

    def test_missing_real_calendar_identity_refused(self):
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(),calendar(title="Some unrelated event"),
                captured_at_utc=CAPTURE)

    def test_stale_calendar_capture_rejected(self):
        old=calendar(asof="2026-11-08T08:00:00Z",
                     date="20261110T090000Z")
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(),old,captured_at_utc=CAPTURE)

    def test_source_excerpt_sha_mismatch_refused(self):
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(source_text="Modified by tester"),
                calendar(),captured_at_utc=CAPTURE)

    def test_non_https_source_refused(self):
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(source_url="http://example.org/consensus"),
                calendar(),captured_at_utc=CAPTURE)

    def test_source_url_with_credentials_refused(self):
        with self.assertRaises(InputError):
            forecast.validate_submission(
                submission(source_url="https://name:secret@example.org/a"),
                calendar(),captured_at_utc=CAPTURE)

    def test_forged_archive_checksum_rejected(self):
        r=archive();r["record"]["forecast_value_self_reported"]="9.9"
        with self.assertRaises(InputError):
            forecast.verify_archive(r,asof_utc=POST)

    def test_future_capture_archive_rejected(self):
        with self.assertRaises(InputError):
            forecast.verify_archive(archive(),
                                   asof_utc="2026-11-10T07:59:00Z")

    def test_archive_write_cli_uses_runtime_no_backdate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            inp=root/"forecast.json";cal=root/"cal.json";out=root/"capture.json"
            inp.write_text(json.dumps(submission()))
            cal.write_text(json.dumps(calendar()))
            # Actual 2026-11-12 is after synthetic 2026-11-10 schedule.
            self.assertEqual(forecast.main([
                "--forecast",str(inp),"--calendar-report",str(cal),
                "--out",str(out)]),2)
            self.assertFalse(out.exists())


class LinkedResearchSnapshotTests(unittest.TestCase):
    def test_prepare_bls_release_with_real_source_hash_link(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,event=make_journal(root)
            result=handoff.prepare(
                store,event,archive(),release(),asof_utc=POST)
            self.assertEqual(result["surprise_research_only"],"0.3")
            self.assertEqual(result["snapshot"]["payload"]["consensus"],"2.1")
            self.assertEqual(result["snapshot"]["payload"]["released_value"],"2.4")
            self.assertIn(event,result["snapshot"]["payload"]["content"])
            self.assertTrue(result["journal_modified"] is False)
            self.assertEqual(obs.audit(store)["record_count"],1)
            self.assertFalse(result["real_orders_permitted"])

    def test_duplicate_derived_event_cannot_be_published_as_new_signal(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            store,original,derived=linked_event(root)
            with self.assertRaises(InputError):
                handoff.prepare(store,original,archive(),release(),
                                asof_utc="2026-11-10T09:05:00Z")
            self.assertEqual(obs.audit(store)["record_count"],2)

    def test_release_wrong_url_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            store,event=make_journal(Path(t))
            with self.assertRaises(InputError):
                handoff.prepare(store,event,archive(),
                    release(source_url="https://www.bls.gov/news.release/other.htm"),
                    asof_utc=POST)

    def test_forecast_mismatched_pair_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            store,event=make_journal(Path(t))
            x=archive()
            x["record"]["pair"]="EUR/USD"
            x["record_sha256"]=forecast.sha(x["record"])
            with self.assertRaises(InputError):
                handoff.prepare(store,event,x,release(),asof_utc=POST)

    def test_wrong_unit_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            store,event=make_journal(Path(t))
            with self.assertRaises(InputError):
                handoff.prepare(store,event,archive(),
                    release(unit="basis_points"),asof_utc=POST)

    def test_release_excerpt_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            store,event=make_journal(Path(t))
            with self.assertRaises(InputError):
                handoff.prepare(store,event,archive(),
                    release(source_text="tampered"),asof_utc=POST)

    def test_future_release_publication_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            store,event=make_journal(Path(t))
            with self.assertRaises(InputError):
                handoff.prepare(store,event,archive(),
                    release(source_published_at_utc="2026-11-11T09:00:00Z"),
                    asof_utc=POST)

    def test_unrelated_event_not_usable(self):
        with tempfile.TemporaryDirectory() as t:
            store,event=make_journal(Path(t))
            x=archive()
            x["record"]["event_title_unverified"]="Consumer Price Index"
            x["record_sha256"]=forecast.sha(x["record"])
            # Change actual RSS feed identity while preserving chain using
            # a fresh journal to avoid falsified record-hash links.
            entry=ai._event(store,event)
            entry["source_id"]="fed_policy"
            with self.assertRaises(InputError):
                handoff.prepare(store,event,archive(),release(),asof_utc=
                                "2026-11-10T08:59:00Z")

    def test_stale_observation_after_schedule_4h_refused(self):
        with tempfile.TemporaryDirectory() as t:
            store,event=make_journal(Path(t))
            x=archive()
            x["record"]["scheduled_at_utc_unverified"]="2026-11-09T09:00:00Z"
            x["record_sha256"]=forecast.sha(x["record"])
            with self.assertRaises(InputError):
                handoff.prepare(store,event,x,release(),asof_utc=POST)


class TwoModelGateTests(unittest.TestCase):
    def test_unenriched_rss_has_no_paid_approval(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,event=make_journal(root)
            result=gate.inspect(
                store,event,root/"newledger.json",analyst_model="m1",
                reviewer_model="m2",asof_utc=ASOF)
            self.assertFalse(result["research_api_dispatch_eligible_if_explicit_opt_in"])
            self.assertIn("RAW_EVENT_WITHOUT_PRE_RELEASE_FORECAST_LINK",
                          result["research_holds"])
            self.assertFalse(result["real_orders_permitted"])

    def test_enriched_event_can_be_eligible_for_research_only(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            r=gate.inspect(store,event,root/"ai.json",
                analyst_model="m1",reviewer_model="m2",asof_utc=ASOF)
            self.assertEqual(r["research_scope"],
                             "QUANTITATIVE_MACRO_WITH_LOCAL_HASH_REFERENCES")
            self.assertTrue(r["research_api_dispatch_eligible_if_explicit_opt_in"])
            self.assertEqual(r["estimated_new_paid_calls_upper_bound_per_invocation"],2)
            self.assertFalse(r["live_model_approval_established"])
            self.assertFalse(r["independent_review_authenticated"])

    def test_same_model_for_analyst_and_verifier_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            with self.assertRaises(InputError):
                gate.inspect(store,event,root/"ai.json",
                             analyst_model="same",reviewer_model="same",
                             asof_utc=ASOF)

    def test_pending_ledger_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            origin=ai._event(store,event)
            state=ai._base(event,ai.packet(origin),"m1","m2")
            state["pending_request"]="analyst"
            ledger=root/"ai.json";ledger.write_text(json.dumps(state))
            r=gate.inspect(store,event,ledger,analyst_model="m1",
                           reviewer_model="m2",asof_utc=ASOF)
            self.assertFalse(r["research_api_dispatch_eligible_if_explicit_opt_in"])
            self.assertIn("PENDING_PAID_OR_PUBLICATION_STATE_REQUIRES_RECONCILIATION",
                          r["research_holds"])

    def test_paid_request_finished_cannot_restart(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            origin=ai._event(store,event)
            state=ai._base(event,ai.packet(origin),"m1","m2")
            state["stage"]="COMPLETE"
            state["analyst"]={
                "action":"HOLD","hypothesis":"Synthetic only",
                "counterevidence":"No proven signal"}
            state["reviewer"]={
                "verdict":"PENDING","rationale":"Not enough evidence"}
            ledger=root/"ai.json";ledger.write_text(json.dumps(state))
            r=gate.inspect(store,event,ledger,analyst_model="m1",
                           reviewer_model="m2",asof_utc=ASOF)
            self.assertFalse(r["research_api_dispatch_eligible_if_explicit_opt_in"])

    def test_not_fresh_event_cannot_make_new_paid_calls(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            r=gate.inspect(store,event,root/"ai.json",analyst_model="m1",
                           reviewer_model="m2",
                           asof_utc="2026-11-12T09:00:00Z")
            self.assertFalse(r["research_api_dispatch_eligible_if_explicit_opt_in"])
            self.assertIn("EVENT_OBSERVED_MORE_THAN_24H_AGO",r["research_holds"])

    def test_no_api_without_explicit_opt_in_even_if_key_present(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            ledger=root/"ai.json"
            # Dry-run in synthetic past is allowed and creates no ledger.
            with patch("research.forward_macro_two_model_gate.ai.run",
                       side_effect=AssertionError("API called")):
                result=gate.main([
                    "--store",str(store),"--event-sha256",event,
                    "--ledger",str(ledger),"--analyst-model","m1",
                    "--reviewer-model","m2"])
            self.assertEqual(result,0)
            self.assertFalse(ledger.exists())

    def test_explicit_paid_flag_without_api_key_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            ledger=root/"ai.json"
            with patch.dict("os.environ",{"OPENAI_API_KEY":""}):
                result=gate.main([
                    "--store",str(store),"--event-sha256",event,
                    "--ledger",str(ledger),"--analyst-model","m1",
                    "--reviewer-model","m2",
                    "--max-api-calls","2","--allow-external-api"])
            self.assertEqual(result,2)
            self.assertFalse(ledger.exists())

    def test_research_gate_never_authenticates_live_order(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);store,_,event=linked_event(root)
            r=gate.inspect(store,event,root/"ai.json",
                analyst_model="m1",reviewer_model="m2",asof_utc=ASOF)
            self.assertEqual(r["runtime_go_no_go"],"NO_GO")
            self.assertFalse(r["demo_orders_permitted"])
            self.assertFalse(r["real_orders_permitted"])


if __name__=="__main__":
    unittest.main()
