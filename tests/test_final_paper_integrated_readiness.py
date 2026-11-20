"""Read-only LIVE readiness and original real quote integrated rehearsal."""
from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_integrated_readiness as ready
from research import final_paper_integrated_rehearsal as rehearsal
from research.offline_backtest import InputError

DATE=datetime(2026,11,20,6,0,0,tzinfo=timezone.utc)
EPOCH=int(DATE.timestamp())


class RealSourceReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name)
        self.root=base/"final_virtual_paper"
        self.root.mkdir()
        self.mt4=base/"MQL4"/"Files"
        self.mt4.mkdir(parents=True)
        self.official=base/"official_public_capture_20261120_113041_303"
        self.official.mkdir()
        self.journal=self.root/"journal"
        self.journal.mkdir()
        self.state=paper.initial_state()
        self.state["cycle_number"]=712
        self.state["last_quote_epoch"]=EPOCH-60
        self.state["paid_inference_calls"]=6
        self.state["communication_latched"]=True
        self.head="a"*64
        self.quote={
            "capture_epoch":EPOCH,
            "source_sha256":"b"*64,
            "quotes":{p:{
                "bid":D("159.50"),"ask":D("159.505"),
                "tickvalue":D("100"),"ticksize":D(".001"),
                "minlot":D(".01"),"maxlot":D("20"),
                "step":D(".01"),"point":D(".001")}
                for p in paper.PAIRS},
        }
        self.ai={
            "journal_head_sha256_local_only":self.head,
            "paid_calls_recorded_in_journal":6,
        }
        self.originals={
            "original_source_count":6,
            "all_saved_bytes_locally_consistent":True,
        }

    def check(self,paid_result=None,archive_result=None):
        with patch.object(ready.runtime,"_journal_load",
                          return_value=(self.state,self.head)), \
             patch.object(ready.paid,"audit",
                          return_value=self.ai if paid_result is None
                                             else paid_result), \
             patch.object(ready.archive,"audit",
                          return_value=self.originals if archive_result is None
                                                    else archive_result), \
             patch.object(ready.runtime,"_latest_quote",
                          return_value=self.quote):
            return ready.review(self.root,self.mt4,self.official,now=DATE)

    def test_live_readiness_is_detailed_and_no_go(self):
        report=self.check()
        self.assertEqual(report["status"],
                         "FINAL_FULL_AI_VIRTUAL_READINESS_HOLD_NO_GO")
        self.assertEqual(report["journal_cycle_count"],712)
        self.assertEqual(report["existing_paid_calls"],6)
        self.assertFalse(report["full_ai_virtual_trading_ready"])
        self.assertFalse(report["new_paid_ai_inference_permitted"])
        self.assertFalse(report["new_virtual_entries_permitted"])
        self.assertFalse(report["live_journal_modified"])
        self.assertFalse(report["communication_latch_mutated"])
        self.assertTrue(report["saved_official_document_hash_integrity"])
        self.assertIn("RISK_STOP_COMMUNICATION_LATCHED",
                      report["remaining_independent_review_requirements"])
        self.assertIn("PRE_RELEASE_CONSENSUS_NOT_TIME_ATTESTED",
                      report["remaining_independent_review_requirements"])

    def test_paid_journal_mismatch_refused(self):
        with self.assertRaises(InputError):
            self.check(paid_result={
                "journal_head_sha256_local_only":"c"*64,
                "paid_calls_recorded_in_journal":6,
            })

    def test_missing_official_original_refused(self):
        with self.assertRaises(InputError):
            self.check(archive_result={
                "original_source_count":5,
                "all_saved_bytes_locally_consistent":False,
            })

    def test_real_original_three_pair_mq4_bytes_never_edit(self):
        file=self.mt4/"FxPaperQuote_20261120_060000.csv"
        with file.open("w",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=paper.QUOTE_FIELDS)
            writer.writeheader()
            for idx,(sym,bid,wide) in enumerate((
                ("USDJPY","159.50",".005"),
                ("EURJPY","175.20",".01"),
                ("EURUSD","1.1000",".00005"),
            )):
                writer.writerow({
                    "pair":sym,
                    "bid":bid,"ask":str(D(bid)+D(wide)),
                    "capture_epoch_utc_pc":EPOCH,
                    "broker_time_epoch_unattested":EPOCH+7200,
                    "tick_time_broker_epoch_unattested":EPOCH+7199,
                    "tickvalue_jpy_broker_reported":"100",
                    "ticksize_broker_reported":
                        ".00001" if idx==2 else ".001",
                    "min_lot_broker_reported":".01",
                    "lot_step_broker_reported":".01",
                    "max_lot_broker_reported":"20",
                    "point_broker_reported":
                        ".00001" if idx==2 else ".001",
                })
        before=hashlib.sha256(file.read_bytes()).hexdigest()
        result=rehearsal.run_unattested_source(file)
        self.assertEqual(set(result["three_pair_statuses"]),
                         set(paper.PAIRS))
        self.assertTrue(all(
            p["hypothetical_position_count"]==0
            for p in result["three_pair_statuses"].values()))
        self.assertEqual(result["actual_new_virtual_entries"],0)
        self.assertEqual(result["actual_paid_requests"],0)
        self.assertEqual(result["broker_orders"],0)
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),
                         before)


if __name__=="__main__":
    unittest.main()
