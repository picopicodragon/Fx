"""Final-test V1 boots from existing DEMO observation, never paid/trading."""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_final_test_operation as operation
from research.offline_backtest import InputError

BASE=datetime(2026,11,20,6,0,tzinfo=timezone.utc)
STAMP="20261120_060000"


class FinalTestOperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name)
        self.root=base/"final_virtual_paper"
        self.root.mkdir()
        self.mt4=base/"MQL4"/"Files"
        self.mt4.mkdir(parents=True)
        self.first=self.root/"first.json"
        self.first.write_text("{}",encoding="utf-8")
        self.second=self.root/"second.json"
        name=f"FxPaperQuote_{STAMP}.csv"
        file=self.mt4/name
        epoch=int(BASE.timestamp())
        with file.open("w",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=paper.QUOTE_FIELDS)
            writer.writeheader()
            for n,(sym,bid,spread) in enumerate((
                ("USDJPY","159.500",".005"),
                ("EURJPY","175.200",".010"),
                ("EURUSD","1.10000",".00005"),
            )):
                writer.writerow({
                    "pair":sym,
                    "bid":bid,"ask":str(D(bid)+D(spread)),
                    "tick_time_broker_epoch_unattested":epoch+7199,
                    "broker_time_epoch_unattested":epoch+7200,
                    "capture_epoch_utc_pc":epoch,
                    "tickvalue_jpy_broker_reported":"100",
                    "ticksize_broker_reported":".00001" if n==2 else ".001",
                    "min_lot_broker_reported":".01",
                    "lot_step_broker_reported":".01",
                    "max_lot_broker_reported":"20",
                    "point_broker_reported":".00001" if n==2 else ".001",
                })
        self.quote=file
        self.quote_hash=hashlib.sha256(file.read_bytes()).hexdigest()
        self.second.write_text(json.dumps({
            "schema":"fx_final_paper_local_machine_handoff_v1",
            "captured_utc_pc_unattested":(
                BASE+timedelta(seconds=45)).isoformat(),
            "mt4_quote_source_files":[{
                "name":name,"sha256":self.quote_hash,
            }]
        }),encoding="utf-8")
        self.archive=base/"official_public_capture_20261120_113041_303"
        self.archive.mkdir()
        self.live=paper.initial_state()
        self.live["cycle_number"]=577
        self.live["last_quote_epoch"]=epoch
        self.live["paid_inference_calls"]=6
        self.live["communication_latched"]=True
        self.proof={
            "status":"PAPER_RESUMED_OBSERVATION_TWO_POINT_CONSISTENT_NO_GO",
            "same_python_pid_and_start_time":True,
            "same_session_journal_advanced_cycles":2,
            "paid_calls_reconciled_and_unchanged":True,
            "communication_latched":True,
            "other_risk_latches_absent":True,
            "new_paid_ai_calls_permitted":False,
            "new_virtual_positions_permitted":False,
            "interval_seconds_pc_derived":75,
            "latest_journal_cycles":576,
            "first_snapshot_epoch_pc_unattested":epoch-65,
        }
        self.arch={
            "status":"SIX_LOCAL_OFFICIAL_ORIGINALS_HASH_MATCH_RESEARCH_NO_GO",
            "original_source_count":6,
            "local_manifest_sha256":"a"*64,
        }

    def verify(self,*,proof=None,arch=None,live=None):
        with patch.object(operation.continuity,"verify",
                          return_value=self.proof if proof is None else proof), \
             patch.object(operation.official,"audit",
                          return_value=self.arch if arch is None else arch), \
             patch.object(operation.runtime,"_journal_load",
                          return_value=(self.live if live is None else live,
                                        "b"*64)):
            return operation.assess(self.root,self.mt4,self.first,
                                    self.second,self.archive)

    def test_one_command_report_is_observation_only_and_sandbox_mechanics(self):
        report=self.verify()
        self.assertEqual(report["status"],
                         "FINAL_TEST_V1_OBSERVATION_RUNNING_TRADING_HOLD_NO_GO")
        self.assertTrue(report["current_supervisor_running_evidenced_by_two_snapshots"])
        self.assertTrue(report["mt4_quote_capture_and_paper_journal_advancing"])
        self.assertTrue(report["six_saved_official_sources_byte_hash_consistent"])
        self.assertEqual(len(report["isolated_synthetic_risk_and_block_tests"]),3)
        self.assertTrue(all(x["live_communications_hold_blocked_entry"]
                            for x in report["isolated_synthetic_risk_and_block_tests"]))
        self.assertFalse(report["actual_live_virtual_position_opened"])
        self.assertFalse(report["final_full_virtual_trading_go"])
        self.assertEqual(report["existing_paid_ai_calls_used"],6)
        for field in ("new_virtual_entries_permitted",
                      "new_paid_ai_inference_permitted",
                      "demo_broker_orders_permitted",
                      "real_broker_orders_permitted"):
            self.assertFalse(report[field])
        self.assertEqual(report["runtime_go_no_go"],"NO_GO")
        self.assertEqual(self.live["positions"],[])
        self.assertEqual(self.live["paid_inference_calls"],6)

    def test_one_original_byte_change_fails_closed(self):
        self.quote.write_bytes(self.quote.read_bytes()+b"\n")
        with self.assertRaises(InputError):
            self.verify()

    def test_paid_or_communication_safety_rejection(self):
        for key,value in (
            ("paid_inference_calls",7),("communication_latched",False),
            ("dd4_latched",True),("daily_loss_latched",True),
            ("positions",[{"synthetic":True}]),
            ("pending_signals",[{"synthetic":True}]),
        ):
            with self.subTest(key=key):
                live=dict(self.live)
                live[key]=value
                with self.assertRaises(InputError):
                    self.verify(live=live)

    def test_no_six_official_documents_no_operation_certificate(self):
        bad=dict(self.arch)
        bad["original_source_count"]=5
        with self.assertRaises(InputError):
            self.verify(arch=bad)

    def test_no_running_python_process_evidence(self):
        invalid=dict(self.proof)
        invalid["same_python_pid_and_start_time"]=False
        with self.assertRaises(InputError):
            self.verify(proof=invalid)

    def test_win_wrapper_never_starts_or_stops_existing_runtime(self):
        base=Path(__file__).resolve().parents[1]
        ps=(base/"scripts"/"final_paper_start_final_test_v1_once.ps1"
            ).read_text("utf-8")
        self.assertIn("Start-Sleep -Seconds 75",ps)
        self.assertIn("final_paper_local_machine_handoff_once.ps1",ps)
        self.assertIn("final_paper_final_test_operation",ps)
        for forbidden in ("Start-Process","Stop-Process","Remove-Item",
                          "Rename-Item","Invoke-WebRequest","AllowPaidAi",
                          "OrderSend","Set-Content"):
            self.assertNotIn(forbidden,ps)
        src=(base/"research"/"final_paper_final_test_operation.py"
            ).read_text("utf-8")
        for forbidden in ("_journal_append(","urllib.request",
                          "allow_external_api=True","OPENAI_API_KEY",
                          "lock.unlink(", "OrderSend("):
            self.assertNotIn(forbidden,src)


if __name__=="__main__":
    unittest.main()
