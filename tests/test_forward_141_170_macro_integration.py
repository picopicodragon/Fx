"""FWD-141..170 macro source chronology, journal linkage and scorecard tests."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import forward_ai_shadow as ai, forward_observation as obs
from research.forward_mt4_v2_quote import COLUMNS
from research.forward_macro_consensus_surprise import (
    SCHEMA as RELEASE_SCHEMA, inspect as surprise, main as surprise_main
)
from research.forward_macro_evidence_readiness import (
    inspect as readiness, main as readiness_main
)
from research.forward_macro_reviewed_outcomes import (
    inspect as outcomes, main as outcomes_main
)
from research.offline_backtest import InputError

ASOF = "2026-11-10T07:00:00Z"
BASE = datetime(2026, 11, 10, 6, 0, tzinfo=timezone.utc)
PAIRS = {"USDJPY":"USD/JPY", "EURJPY":"EUR/JPY","EURUSD":"EUR/USD"}


def dtime(sec):
    return BASE + timedelta(seconds=sec)


def z(sec):
    return dtime(sec).strftime("%Y-%m-%dT%H:%M:%SZ")


def csv_session(root: Path, name: str, *, count: int = 4,
                start_minute: int = 0) -> Path:
    directory = root/name
    directory.mkdir()
    for minute in range(start_minute, start_minute+count):
        stamp = dtime(minute*60).strftime("%Y%m%d_%H%M%S")
        observed = z(minute*60)
        servernow=(dtime(minute*60)+timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        tick=(dtime(minute*60)+timedelta(hours=2,seconds=-1)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        bid = 150 + minute*.01
        for symbol,pair in PAIRS.items():
            if symbol=="USDJPY":
                bidstr,askstr=f"{bid:.3f}",f"{bid+.005:.3f}"
            elif symbol=="EURJPY":
                bidstr,askstr="170.000","170.010"
            else:
                bidstr,askstr="1.12000","1.12005"
            conversion=f"{bid:.5f}" if symbol=="EURUSD" else "1.00000"
            values=[observed,pair,bidstr,askstr,conversion,tick,servernow,
                    "1","DEMO","MANUAL_MT4_DEMO_V2_UNVERIFIED"]
            (directory/f"FxFwdV3_{symbol}_{stamp}.csv").write_text(
                ",".join(COLUMNS)+"\n"+",".join(values)+"\n",encoding="utf-8")
    return directory


def add(store, obj, at):
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/"record.json"
        path.write_text(json.dumps(obj),encoding="utf-8")
        return obs.ingest(store,path,now=dtime(at))["record_sha256"]


def journal(root, *, status="APPROVED", side="LONG", consensus="1.2",
            reviewer="other-model", published="2026-11-10T05:00:00Z",
            multiple=False):
    store=root/"journal"
    obs.initialize(store,"macrotest",now=dtime(0))
    e={
        "schema":obs.SCHEMA,"kind":"MACRO_EVENT","observed_at_utc":z(1),
        "source_id":"offline_macro",
        "payload":{
            "pair":"USD/JPY","title":"Synthetic test event",
            "source_url":"https://www.bls.gov/schedule/",
            "published_at_utc":published,
            "content":"Synthetic only. Not sourced from real release.",
            "consensus":consensus,"released_value":"1.3",
            "source_status":"USER_SUPPLIED_UNVERIFIED",
        },
    }
    event_hash=add(store,e,1)
    h={
        "schema":obs.SCHEMA,"kind":"MACRO_HYPOTHESIS",
        "observed_at_utc":z(4),"source_id":"offline_ai",
        "payload":{
            "pair":"USD/JPY","direction":side,
            "thesis":"Synthetic; no live macro advice.",
            "counterevidence":"Synthetic adverse outcome not proven.",
            "model_id":"builder-model",
            "basis_sha256":event_hash,"research_only":True,
        }
    }
    hhash=add(store,h,4)
    r={
        "schema":obs.SCHEMA,"kind":"INDEPENDENT_REVIEW",
        "observed_at_utc":z(8),"source_id":"offline_review",
        "payload":{
            "pair":"USD/JPY","review_of_sha256":hhash,
            "verdict":status,"rationale":"Synthetic test only.",
            "model_id":reviewer,"research_only":True,
        },
    }
    add(store,r,8)
    if multiple:
        r2=json.loads(json.dumps(r))
        r2["observed_at_utc"]=z(9)
        add(store,r2,9)
    return store,event_hash


def economic(*, consensus=True, released=True):
    def source(value,text,published,captured):
        return {
            "value":value,"source_text":text,
            "source_sha256":hashlib.sha256(text.encode()).hexdigest(),
            "source_url":"https://www.bls.gov/news.release/",
            "published_at_utc":published,"captured_at_utc":captured,
        }
    return {
        "schema":RELEASE_SCHEMA,"event_id":"synthetic_cpi",
        "pair":"USD/JPY","event_type":"CPI",
        "unit":"percent","scheduled_at_utc":"2026-11-10T06:00:00Z",
        "forecast":source("1.2","Synthetic forecast record",
                          "2026-11-10T05:40:00Z",
                          "2026-11-10T05:45:00Z") if consensus else None,
        "release":source("1.3","Synthetic release record",
                         "2026-11-10T06:00:01Z",
                         "2026-11-10T06:00:05Z") if released else None,
    }


class EconomicSurpriseTests(unittest.TestCase):
    def test_release_surprise_exact_decimal(self):
        report=surprise(economic(),asof_utc="2026-11-10T07:00:00Z")
        self.assertEqual(report["released_minus_forecast_same_unit"],"0.1")
        self.assertTrue(report["signed_surprise_is_not_a_trade_signal"])
        self.assertFalse(report["real_orders_permitted"])

    def test_missing_consensus_holds_without_guess(self):
        report=surprise(economic(consensus=False),asof_utc=ASOF)
        self.assertIsNone(report["released_minus_forecast_same_unit"])
        self.assertIn("NO_POINT_IN_TIME_CONSENSUS",report["data_holds"])

    def test_unreleased_data_holds_without_guess(self):
        report=surprise(economic(released=False),asof_utc=ASOF)
        self.assertIsNone(report["released_minus_forecast_same_unit"])
        self.assertIn("OFFICIAL_RELEASE_VALUE_NOT_RECORDED",report["data_holds"])

    def test_forecast_captured_after_release_is_invalid(self):
        x=economic()
        x["forecast"]["captured_at_utc"]="2026-11-10T06:00:00Z"
        with self.assertRaises(InputError):
            surprise(x,asof_utc=ASOF)

    def test_outcome_before_scheduled_time_invalid(self):
        x=economic()
        x["release"]["published_at_utc"]="2026-11-10T05:59:59Z"
        with self.assertRaises(InputError):
            surprise(x,asof_utc=ASOF)

    def test_hash_mismatch_fails_closed(self):
        x=economic()
        x["forecast"]["source_text"]+=" altered"
        with self.assertRaises(InputError):
            surprise(x,asof_utc=ASOF)

    def test_unavailable_future_release_fails_closed(self):
        with self.assertRaises(InputError):
            surprise(economic(),asof_utc="2026-11-10T05:50:00Z")

    def test_blackout_flag(self):
        r=surprise(economic(),asof_utc="2026-11-10T06:10:00Z")
        self.assertIn("MACRO_15_MINUTE_BLACKOUT_RESEARCH_ONLY",r["data_holds"])

    def test_negative_delta_is_valid_not_direction_signal(self):
        x=economic()
        x["release"]["value"]="1.1"
        r=surprise(x,asof_utc=ASOF)
        self.assertEqual(r["released_minus_forecast_same_unit"],"-0.1")

    def test_cli_exclusive_report_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            source=root/"event.json"
            source.write_text(json.dumps(economic()),encoding="utf-8")
            report=root/"report.json"
            args=["--event",str(source),"--asof-utc",ASOF,"--out",str(report)]
            self.assertEqual(surprise_main(args),0)
            self.assertEqual(surprise_main(args),2)
            self.assertFalse(json.loads(report.read_text())["real_orders_permitted"])


class IntegratedMacroEvidenceTests(unittest.TestCase):
    def test_no_macro_event_is_hold_not_fabricated(self):
        with tempfile.TemporaryDirectory() as t:
            d=csv_session(Path(t),"prices")
            report=readiness([("s1",d)],asof_utc=ASOF)
            self.assertEqual(report["quote_csv_count"],12)
            self.assertEqual(report["macro_event_count"],0)
            self.assertEqual(report["research_only_candidate_count"],0)
            self.assertIn("NO_OBSERVED_MACRO_EVENT",
                          report["source_holds_and_warnings"])

    def test_hash_chained_three_stage_ai_journal(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root)
            r=readiness([("s1",d)],store=store,asof_utc=ASOF)
            self.assertEqual(r["macro_event_count"],1)
            self.assertEqual(r["macro_hypothesis_count"],1)
            self.assertEqual(r["macro_review_count"],1)
            self.assertEqual(r["research_only_candidate_count"],1)
            self.assertEqual(r["candidate_records"][0]["direction"],"LONG")
            self.assertFalse(r["independent_review_proven"])

    def test_missing_consensus_marked_unverifiable(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root,consensus="")
            r=readiness([("s1",d)],store=store,asof_utc=ASOF)
            self.assertEqual(r["macro_event_missing_consensus_count"],1)
            self.assertIn("PRE_RELEASE_CONSENSUS_NOT_PRESENT",
                          r["source_holds_and_warnings"])

    def test_review_rejected_never_candidate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root,status="REJECTED")
            r=readiness([("s1",d)],store=store,asof_utc=ASOF)
            self.assertEqual(r["research_only_candidate_count"],0)

    def test_hold_macro_never_candidate(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root,side="HOLD")
            r=readiness([("s1",d)],store=store,asof_utc=ASOF)
            self.assertEqual(r["research_only_candidate_count"],0)

    def test_same_model_id_is_not_independent(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root,reviewer="builder-model")
            r=readiness([("s1",d)],store=store,asof_utc=ASOF)
            self.assertIn("REVIEWER_AND_BUILDER_MODEL_ID_MATCH",
                          r["source_holds_and_warnings"])

    def test_multiple_reviews_flagged_and_outcome_suppressed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root,multiple=True)
            r=readiness([("s1",d)],store=store,asof_utc=ASOF)
            self.assertIn("MULTIPLE_RESEARCH_REVIEWS_FOR_ONE_HYPOTHESIS",
                          r["source_holds_and_warnings"])
            outcome=outcomes([("s1",d)],store=store,asof_utc=ASOF)
            self.assertTrue(outcome["structural_veto"])
            self.assertEqual(outcome["two_snapshot_descriptive_mark_count"],0)

    def test_pending_paid_ai_ledger_does_not_autoretry(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,event_hash=journal(root)
            event=ai._event(store,event_hash)
            base=ai._base(event_hash,ai.packet(event),
                          "analyst-test","reviewer-test")
            base["pending_request"]="analyst"
            file=root/"ledger.json"
            file.write_text(json.dumps(base))
            r=readiness([("s1",d)],store=store,asof_utc=ASOF,
                        ai_ledgers=[file])
            self.assertIn("AMBIGUOUS_API_REQUEST_MANUAL_RECONCILIATION",
                          r["source_holds_and_warnings"])
            self.assertFalse(r["actual_ai_provider_called"])

    def test_corrupt_observation_record_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root)
            file=store/"00000002.json"
            data=json.loads(file.read_text())
            data["snapshot"]["payload"]["direction"]="SHORT"
            file.write_text(json.dumps(data))
            with self.assertRaises(InputError):
                readiness([("s1",d)],store=store,asof_utc=ASOF)

    def test_cli_no_store_is_research_hold_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            out=root/"readiness.json"
            args=["--session",f"s1={d}","--asof-utc",ASOF,
                  "--out",str(out)]
            self.assertEqual(readiness_main(args),0)
            self.assertEqual(readiness_main(args),2)
            self.assertEqual(json.loads(out.read_text())["runtime_go_no_go"],
                             "NO_GO")

    def test_unmatched_ledger_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root)
            bogus=root/"bogus.json"
            bogus.write_text(json.dumps({"event_record_sha256":"0"*64}))
            with self.assertRaises(InputError):
                readiness([("s1",d)],store=store,asof_utc=ASOF,
                          ai_ledgers=[bogus])


class ReviewedMacroOutcomeTests(unittest.TestCase):
    def test_approved_review_next_quote_only_and_spread_paid(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root)
            r=outcomes([("s1",d)],store=store,asof_utc=ASOF)
            self.assertFalse(r["structural_veto"])
            self.assertEqual(r["two_snapshot_descriptive_mark_count"],1)
            m=r["spread_adjusted_marks"][0]
            self.assertEqual(m["entry_observation_utc"],z(60))
            self.assertEqual(m["exit_observation_utc"],z(120))
            self.assertEqual(m["entry_quote_side"],"150.015")
            self.assertEqual(m["exit_quote_side"],"150.020")
            self.assertEqual(m["two_snapshot_spread_adjusted_change_pips_per_unit"],
                             "0.5")
            self.assertEqual(r["simulated_order_fills_created"],0)
            self.assertEqual(r["actual_broker_order_calls"],0)

    def test_short_direction_debits_ask_spread(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root,side="SHORT")
            r=outcomes([("s1",d)],store=store,asof_utc=ASOF)
            m=r["spread_adjusted_marks"][0]
            self.assertEqual(m["entry_quote_side"],"150.010")
            self.assertEqual(m["exit_quote_side"],"150.025")
            self.assertEqual(m["two_snapshot_spread_adjusted_change_pips_per_unit"],
                             "-1.5")

    def test_publication_blackout_blocks_marks(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root,published=z(-30))
            r=outcomes([("s1",d)],store=store,asof_utc=ASOF)
            self.assertEqual(r["two_snapshot_descriptive_mark_count"],0)
            self.assertIn("NO_CAUSALLY_EVALUABLE_SHADOW_MARKS",
                          r["holds_and_limitations"])

    def test_review_after_final_capture_no_marks(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            store,_=journal(root)
            # Intentionally use only the first pre-review capture:
            # no two post-review observations in this session.
            for p in list(d.iterdir()):
                if "_060100" in p.name or "_060200" in p.name or "_060300" in p.name:
                    p.unlink()
            r=outcomes([("s1",d)],store=store,asof_utc=ASOF)
            self.assertEqual(r["two_snapshot_descriptive_mark_count"],0)

    def test_no_macro_journal_never_creates_marks(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            r=outcomes([("s1",d)],store=None,asof_utc=ASOF)
            self.assertEqual(r["macro_event_count"],0)
            self.assertEqual(r["two_snapshot_descriptive_mark_count"],0)

    def test_overlap_prevents_marks(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d1=csv_session(root,"a")
            d2=csv_session(root,"b")
            store,_=journal(root)
            r=outcomes([("a",d1),("b",d2)],store=store,asof_utc=ASOF)
            self.assertTrue(r["structural_veto"])
            self.assertEqual(r["two_snapshot_descriptive_mark_count"],0)

    def test_outcome_cli_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            d=csv_session(root,"prices")
            out=root/"outcomes.json"
            args=["--session",f"s1={d}","--asof-utc",ASOF,
                  "--out",str(out)]
            self.assertEqual(outcomes_main(args),0)
            self.assertEqual(outcomes_main(args),2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])


if __name__=="__main__":
    unittest.main()
