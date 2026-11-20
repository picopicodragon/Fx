"""Preserve 3020-like baseline and never promote claimed new-EA data to GO."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as engine
from research import final_paper_quote_time_order_campaign as campaign
from research import final_paper_clockfix_prospective as future
from research.offline_backtest import InputError

BEGIN=datetime(2026,11,20,3,55,tzinfo=timezone.utc)
REAL_BASELINE_INVALID_RATE=(future.BASELINE["invalid_original_count"]/
                            future.BASELINE["reviewed_original_count"])


def csv_source(folder:Path,dt:datetime, *, inverted=False,
               eur_future=False, capture_offset=0)->Path:
    epoch=int(dt.timestamp())
    name=f"FxPaperQuote_{dt.strftime('%Y%m%d_%H%M%S')}.csv"
    file=folder/name
    with file.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=engine.QUOTE_FIELDS)
        writer.writeheader()
        for n,(sym,bid,spread) in enumerate((
            ("USDJPY","159.500",".005"),
            ("EURJPY","175.200",".01"),
            ("EURUSD","1.10000",".00005"),
        )):
            broker=epoch+7200
            tick=broker-1
            if inverted and n==0 or eur_future and n==1:
                tick=broker+1
            writer.writerow({
                "pair":sym,
                "bid":bid,
                "ask":str(D(bid)+D(spread)),
                "tick_time_broker_epoch_unattested":tick,
                "broker_time_epoch_unattested":broker,
                "capture_epoch_utc_pc":epoch+capture_offset,
                "tickvalue_jpy_broker_reported":"100",
                "ticksize_broker_reported":".00001" if n==2 else ".001",
                "min_lot_broker_reported":".01",
                "lot_step_broker_reported":".01",
                "max_lot_broker_reported":"20",
                "point_broker_reported":".00001" if n==2 else ".001",
            })
    return file


class ProspectiveClockFixAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.quotes=self.root/"MQL4"/"Files"
        self.quotes.mkdir(parents=True)
        self.originals=[]
        for i in range(6):
            self.originals.append(csv_source(
                self.quotes,BEGIN+timedelta(minutes=i),
                inverted=i in (1,2,3,4),eur_future=i==1,
            ))
        self.baseline_report=self.root/"baseline.json"
        baseline=campaign.review(self.quotes)
        self.baseline_report.write_text(json.dumps(baseline),encoding="utf-8")
        self.mock_expectation={
            key:baseline[key] for key in future.BASELINE
        }
        self.candidate=(
            Path(__file__).resolve().parents[1]/
            "mt4"/"read_only"/"FxFinalPaperReadOnlyObserver.mq4"
        )
        self.cutover="2026-11-20T04:01:00Z"
        self.patch_baseline=patch.object(future,"BASELINE",
                                         self.mock_expectation)
        self.patch_baseline.start()
        self.addCleanup(self.patch_baseline.stop)

    def audit(self):
        return future.audit(self.quotes,self.baseline_report,
                            self.cutover,candidate_source=self.candidate)

    def test_real_legacy_rate_needs_over_two_thousand_illustrative_samples(self):
        self.assertEqual(
            math.ceil(math.log(0.05)/math.log1p(-REAL_BASELINE_INVALID_RATE)),
            2261)
        self.assertAlmostEqual((1-REAL_BASELINE_INVALID_RATE)**120,
                               0.8529573361925464)
        report=self.audit()
        self.assertFalse(report["iid_assumption_independently_validated"])
        self.assertFalse(report["statistics_can_enable_new_virtual_entries"])

    def test_preexisting_four_anomalies_are_anchored_even_without_new_quotes(self):
        report=self.audit()
        self.assertEqual(report["baseline_original_count"],6)
        self.assertEqual(report["baseline_invalid_original_count"],4)
        self.assertEqual(report["post_cutover_quote_count"],0)
        self.assertFalse(report["research_120_observations_two_ny17_days_reached"])
        self.assertFalse(report["new_ea_deployment_independently_confirmed"])
        self.assertFalse(report["proof_clock_race_eliminated"])
        self.assertFalse(report["new_virtual_entries_permitted"])
        self.assertFalse(report["extra_paid_ai_permitted"])
        self.assertEqual(report["runtime_go_no_go"],"NO_GO")

    def test_post_cutover_clean_121_samples_two_days_still_no_trading(self):
        for i in range(60):
            csv_source(self.quotes,BEGIN+timedelta(minutes=6+i))
        for i in range(61):
            csv_source(self.quotes,BEGIN+timedelta(days=1,minutes=6+i))
        report=self.audit()
        self.assertEqual(report["post_cutover_quote_count"],121)
        self.assertEqual(report["post_cutover_invalid_quote_count"],0)
        self.assertEqual(report["post_cutover_valid_quote_count"],121)
        self.assertEqual(report["post_cutover_observed_ny17_buckets"],2)
        self.assertTrue(report["research_120_observations_two_ny17_days_reached"])
        self.assertTrue(report["baseline_still_byte_for_byte_preserved"])
        self.assertFalse(report["new_ea_expert_log_and_old_ea_stop_verified"])
        self.assertFalse(report["proof_clock_race_eliminated"])
        self.assertFalse(report["new_virtual_entries_permitted"])

    def test_one_future_tick_ahead_is_detected_without_discarding_source(self):
        first=csv_source(self.quotes,BEGIN+timedelta(minutes=6))
        bad=csv_source(self.quotes,BEGIN+timedelta(minutes=7),
                       inverted=True,eur_future=True)
        recorded=hashlib.sha256(bad.read_bytes()).hexdigest()
        report=self.audit()
        self.assertEqual(report["post_cutover_quote_count"],2)
        self.assertEqual(report["post_cutover_invalid_quote_count"],1)
        self.assertEqual(report["post_cutover_future_tick_counts"],
                         {"USDJPY":1,"EURJPY":1,"EURUSD":0})
        self.assertEqual(report["post_cutover_max_future_lead_seconds"]["USDJPY"],1)
        self.assertEqual(report["post_cutover_issues_first_25"][0][
            "source_basename"],bad.name)
        self.assertEqual(hashlib.sha256(bad.read_bytes()).hexdigest(),recorded)
        self.assertFalse(report["new_virtual_entries_permitted"])

    def test_original_historical_bytes_cannot_be_rewritten_to_pass(self):
        self.originals[2].write_bytes(self.originals[2].read_bytes()+b"\n")
        with self.assertRaises(InputError):
            self.audit()

    def test_missing_original_cannot_hide_baseline_anomaly(self):
        self.originals[2].unlink()
        with self.assertRaises(InputError):
            self.audit()

    def test_wrong_baseline_report_and_cutover_rejected(self):
        data=json.loads(self.baseline_report.read_text("utf-8"))
        data["invalid_original_count"]=0
        self.baseline_report.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaises(InputError):
            self.audit()
        baseline=campaign.review(self.quotes)
        self.baseline_report.write_text(json.dumps(baseline),encoding="utf-8")
        for boundary in ("2026-11-20T04:00:00Z",
                         "2026-11-20T04:00:30+09:00","not-a-date"):
            with self.subTest(boundary=boundary):
                with self.assertRaises(InputError):
                    future.audit(self.quotes,self.baseline_report,boundary,
                                 candidate_source=self.candidate)

    def test_future_file_with_different_capture_epoch_is_not_valid(self):
        csv_source(self.quotes,BEGIN+timedelta(minutes=6))
        csv_source(self.quotes,BEGIN+timedelta(minutes=7),
                   capture_offset=1)
        report=self.audit()
        self.assertEqual(report["post_cutover_invalid_quote_count"],1)
        self.assertIn("CAPTURE_TIME_DIFFERS_FROM_FILENAME",
                      report["post_cutover_issues_first_25"][0]["reason_codes"])

    def test_version_marked_source_stays_manual_and_no_orders(self):
        content=self.candidate.read_text("utf-8")
        self.assertIn('PAPER_BUILD_TAG "FXPAPER-CLOCKFREEZE-20261120-V2"',
                      content)
        self.assertIn("enabled; orders=0; build=",content)
        self.assertIn("observer stopped; reason=",content)
        for forbidden in ("OrderSend(","OrderClose(","OrderModify(",
                          "WebRequest(","#import"):
            self.assertNotIn(forbidden,content)
        py=(Path(__file__).resolve().parents[1]/
            "research"/"final_paper_clockfix_prospective.py").read_text("utf-8")
        # The offline checker searches for the literal forbidden token
        # OrderSend( in candidate source bytes. Only actual Python calls
        # are unsafe; the guard itself is not a broker API invocation.
        calls=[node for node in ast.walk(ast.parse(py))
               if isinstance(node,ast.Call)]
        forbidden_calls={"OrderSend","OrderClose","_journal_append"}
        for call in calls:
            name=(call.func.id if isinstance(call.func,ast.Name)
                  else call.func.attr if isinstance(call.func,ast.Attribute)
                  else "")
            self.assertNotIn(name,forbidden_calls)
        for forbidden in ("allow_external_api=True","urllib.request",
                          "lock.unlink(","OPENAI_API_KEY"):
            self.assertNotIn(forbidden,py)


if __name__=="__main__":
    unittest.main()
