"""Read-only proof that resumed DEMO prices reach the Python journal."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from research import final_paper_resumed_continuity as continuity
from research.offline_backtest import InputError

T = datetime(2026, 11, 20, 3, 0, 40, tzinfo=timezone.utc)
HEAD = "f"*64


def handoff(*, second=False):
    time = T + (timedelta(seconds=75) if second else timedelta())
    latest=("FxPaperQuote_20261120_030059.csv" if second else
            "FxPaperQuote_20261120_025959.csv")
    count=561 if second else 560
    return {
        "schema": "fx_final_paper_local_machine_handoff_v1",
        "captured_utc_pc_unattested":time.isoformat(),
        "paper_supervisor_process_count":1,
        "paper_supervisor_process_id":4173,
        "paper_supervisor_paid_ai_opt_in_cli_flag_present":False,
        "paper_supervisor_created_utc_pc_unattested":
            "2026-11-20T02:50:00Z",
        "mt4_terminal_process_count":1,
        "runtime_lock_present_not_process_proof":True,
        "journal_file_count":count,
        "journal_last_file_name":f"{count:08d}.json",
        "journal_last_file_sha256":("d" if second else "a")*64,
        "mt4_quote_source_files":[{
            "name":latest,
            "sha256":("e" if second else "b")*64,
            "bytes":400,
            "last_write_utc":time.isoformat(),
        }],
        "new_paid_ai_calls_authorized":False,
        "new_virtual_positions_permitted":False,
        "real_orders_permitted":False,
    }


def state():
    return {
        "cycle_number":561,
        "last_quote_epoch":int((T+timedelta(seconds=5)).timestamp()),
        "communication_latched":True,
        "daily_loss_latched":False,
        "dd4_latched":False,
        "dd5_latched":False,
        "positions":[],
        "pending_signals":[],
        "paid_inference_calls":6,
    }


class ResumedContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.first=self.root/"first.json"
        self.second=self.root/"second.json"
        self.write()

    def write(self, first=None, second=None):
        self.first.write_text(json.dumps(handoff() if first is None else first))
        self.second.write_text(json.dumps(
            handoff(second=True) if second is None else second))

    def verify(self, state_override=None, paid_count=6, prior_head=HEAD,
               after_head=HEAD):
        with patch.object(continuity.runtime,"_journal_load",
                          side_effect=[(state() if state_override is None
                                        else state_override,prior_head),
                                       (state(),after_head)]), \
             patch.object(continuity.paid,"audit",return_value={
                 "paid_calls_recorded_in_journal":paid_count,
                 "paid_calls_in_completed_ledgers":paid_count,
             }):
            return continuity.verify(self.root,self.first,self.second)

    def test_two_samples_and_chain_prove_observation_not_entry(self):
        x=self.verify()
        self.assertTrue(x["same_python_pid_and_start_time"])
        self.assertTrue(x["mt4_source_quote_advanced"])
        self.assertEqual(x["same_session_journal_advanced_cycles"],1)
        self.assertTrue(x["journal_hash_chain_valid"])
        self.assertTrue(x["communication_latched"])
        self.assertFalse(x["new_virtual_positions_permitted"])
        self.assertFalse(x["new_paid_ai_calls_permitted"])
        self.assertFalse(x["broker_clock_independently_verified"])

    def test_bad_pid_or_restart_is_rejected(self):
        for k,v in (
            ("paper_supervisor_process_id",4174),
            ("paper_supervisor_created_utc_pc_unattested",
                "2026-11-20T03:00:41Z"),
            ("runtime_lock_present_not_process_proof",False),
            ("paper_supervisor_process_count",0),
            ("paper_supervisor_paid_ai_opt_in_cli_flag_present",True),
            ("mt4_terminal_process_count",0),
        ):
            with self.subTest(k=k):
                bad=handoff(second=True)
                bad[k]=v
                self.write(second=bad)
                with self.assertRaises(InputError):
                    self.verify()
        self.write()

    def test_quote_stale_or_journal_not_advancing_is_rejected(self):
        for k,v in (
            ("captured_utc_pc_unattested",
                "2026-11-20T03:03:00Z"),
            ("journal_file_count",560),
            ("mt4_quote_source_files",handoff()[
                "mt4_quote_source_files"]),
        ):
            with self.subTest(k=k):
                bad=handoff(second=True)
                bad[k]=v
                self.write(second=bad)
                with self.assertRaises(InputError):
                    self.verify()
        self.write()

    def test_risk_and_billing_fail_closed(self):
        for key,val in (
            ("communication_latched",False),
            ("dd4_latched",True),
            ("positions",[{"hypothetical":True}]),
            ("paid_inference_calls",7),
        ):
            with self.subTest(key=key):
                bad=state()
                bad[key]=val
                with self.assertRaises(InputError):
                    self.verify(state_override=bad)
        with self.assertRaises(InputError):
            self.verify(paid_count=4)
        with self.assertRaises(InputError):
            self.verify(after_head="a"*64)

    def test_no_mutation_or_broker_calls_in_code_and_wrapper(self):
        base=Path(__file__).resolve().parents[1]
        source=(base/"research/final_paper_resumed_continuity.py"
               ).read_text(encoding="utf-8")
        ps=(base/"scripts/final_paper_verify_resumed_monitor_once.ps1"
            ).read_text(encoding="utf-8")
        self.assertIn("Start-Sleep -Seconds 75",ps)
        self.assertIn("final_paper_local_machine_handoff_once.ps1",ps)
        for forbidden in ("OrderSend(", "OrderClose(", "_journal_append(",
                          "allow_external_api=True", "OpenAI", "lock.unlink("):
            self.assertNotIn(forbidden,source)
        for forbidden in ("Stop-Process","Start-Process","Remove-Item",
                          "Rename-Item", "Invoke-WebRequest",
                          "AllowPaidAi", "ApproveObservationOnlyRecovery"):
            self.assertNotIn(forbidden,ps)


if __name__=="__main__":
    unittest.main()
