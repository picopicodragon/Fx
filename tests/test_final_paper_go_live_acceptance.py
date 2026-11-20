"""Final user-controlled but NO-GO locked startup acceptance regressions."""
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
from research import final_paper_go_live_acceptance as launch
from research import final_paper_clockfix_prospective as clockfix
from research.offline_backtest import InputError

BASE=datetime(2026,11,20,7,0,tzinfo=timezone.utc)


def original_file(folder:Path):
    stamp=BASE.strftime("%Y%m%d_%H%M%S")
    f=folder/f"FxPaperQuote_{stamp}.csv"
    epoch=int(BASE.timestamp())
    with f.open("w",encoding="utf-8",newline="") as out:
        w=csv.DictWriter(out,fieldnames=paper.QUOTE_FIELDS)
        w.writeheader()
        for i,(symbol,bid,sp) in enumerate((
            ("USDJPY","159.50",".005"),
            ("EURJPY","175.20",".01"),
            ("EURUSD","1.10000",".00005"),
        )):
            w.writerow({
                "pair":symbol,"bid":bid,"ask":str(D(bid)+D(sp)),
                "capture_epoch_utc_pc":epoch,
                "broker_time_epoch_unattested":epoch+7200,
                "tick_time_broker_epoch_unattested":epoch+7199,
                "tickvalue_jpy_broker_reported":"100",
                "ticksize_broker_reported":".00001" if i==2 else ".001",
                "min_lot_broker_reported":".01",
                "lot_step_broker_reported":".01",
                "max_lot_broker_reported":"20",
                "point_broker_reported":".00001" if i==2 else ".001",
            })
    return f


class LaunchAcceptanceTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base=Path(t.name)
        self.root=self.base/"evidence"
        self.root.mkdir()
        self.mt4=self.base/"MQL4"/"Files"
        self.mt4.mkdir(parents=True)
        self.archive=self.base/"official_public_capture_test"
        self.archive.mkdir()
        self.baseline=self.root/"baseline.json"
        self.baseline.write_text("{}",encoding="utf-8")
        self.a=self.root/"first.json"
        self.a.write_text("{}",encoding="utf-8")
        self.b=self.root/"second.json"
        self.b.write_text("{}",encoding="utf-8")
        self.mq4=Path(__file__).resolve().parents[1]/"mt4"/"read_only"/"FxFinalPaperReadOnlyObserver.mq4"
        self.source=original_file(self.mt4)
        self.sha=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.state=paper.initial_state()
        self.state["cycle_number"]=802
        self.state["last_quote_epoch"]=int(BASE.timestamp())
        self.state["communication_latched"]=True
        self.state["paid_inference_calls"]=6
        self.head="b"*64
        self.proof={
            "status":"PAPER_RESUMED_OBSERVATION_TWO_POINT_CONSISTENT_NO_GO",
            "communication_latched":True,
            "paid_calls_reconciled_and_unchanged":True,
            "journal_hash_chain_valid":True,
            "latest_journal_cycles":801,
            "latest_journal_head_sha256_local_only":"a"*64,
        }
        self.billed={
            "paid_calls_recorded_in_journal":6,
            "paid_calls_in_completed_ledgers":6,
            "journal_head_sha256_local_only":self.head,
            "journal_cycles":802,
        }
        self.originals={
            "original_source_count":6,
            "all_saved_bytes_locally_consistent":True,
        }
        self.snapshot={
            "quote_name":self.source.name,
            "quote_sha256":self.sha,
            "captured_epoch":int(BASE.timestamp())+30,
            "quote_epoch":int(BASE.timestamp()),
        }
        self.baseline_values={
            "original_sequence_sha256_local_only":"c"*64,
        }

    def evaluate(self,proof=None,billed=None,orig=None,
                 state=None,snap=None,baseline=None):
        with patch.object(launch.continuity,"verify",
                          return_value=self.proof if proof is None else proof), \
             patch.object(launch.runtime,"_journal_load",
                          return_value=(self.state if state is None else state,
                                        self.head)), \
             patch.object(launch.paid,"audit",
                          return_value=self.billed if billed is None else billed), \
             patch.object(launch.official,"audit",
                          return_value=self.originals if orig is None else orig), \
             patch.object(launch,"_historical_chain",
                          return_value=(
                            self.baseline_values if baseline is None else baseline,
                            "d"*64,3020)), \
             patch.object(launch.continuity,"_read",return_value={}), \
             patch.object(launch.continuity,"_snap",
                          return_value=self.snapshot if snap is None else snap):
            return launch.review(self.root,self.mt4,self.archive,
                                 self.baseline,self.mq4,self.a,self.b)

    def test_operator_go_live_candidate_is_explicit_no_go(self):
        output=self.evaluate()
        self.assertEqual(output["status"],
                         "GO_LIVE_EVIDENCE_VERIFIED_OPERATOR_GATES_REMAIN_NO_GO")
        self.assertEqual(output["journal_cycles"],802)
        self.assertEqual(output["observed_paid_ai_calls_not_reset"],6)
        self.assertEqual(output["historical_quote_count_verified"],3020)
        self.assertEqual(output["official_original_local_bytes_verified"],6)
        self.assertEqual(len(output["operator_approvals_not_yet_given"]),3)
        self.assertEqual(len(output["independent_evidence_not_yet_attested"]),6)
        self.assertEqual(output["runtime_go_no_go"],"NO_GO")
        self.assertTrue(output["safety_hold_latched"])
        self.assertFalse(output["new_live_virtual_entry_eligible"])
        self.assertFalse(output["paid_api_dispatch_eligible"])
        self.assertFalse(output["demo_orders_permitted"])
        self.assertFalse(output["real_orders_permitted"])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),self.sha)

    def test_immutable_or_missing_paid_receipts_always_reject(self):
        with self.assertRaises(InputError):
            self.evaluate(billed={
                **self.billed,"paid_calls_in_completed_ledgers":5})
        with self.assertRaises(InputError):
            self.evaluate(orig={
                **self.originals,"all_saved_bytes_locally_consistent":False})

    def test_latch_clear_without_new_approved_incident_reject(self):
        changed=dict(self.state)
        changed["communication_latched"]=False
        with self.assertRaises(InputError):
            self.evaluate(state=changed)

    def test_advanced_journal_head_is_allowed_if_paid_receipt_matches(self):
        # A later append-only hash head than the second snapshot is normal.
        report=self.evaluate()
        self.assertEqual(report["journal_head_sha256_local_only"],self.head)
        self.assertNotEqual(self.head,
                            self.proof["latest_journal_head_sha256_local_only"])

    def test_changed_latest_original_after_snapshot_never_trusted(self):
        changed=dict(self.snapshot)
        changed["quote_sha256"]="9"*64
        with self.assertRaises(InputError):
            self.evaluate(snap=changed)

    def test_real_historical_chain_checks_all_3020_bytes(self):
        # Generate 3020 bounded original paths and assert byte-for-byte
        # historical anchoring, then show one byte tamper fails closed.
        initial=datetime(2026,11,18,2,22,49,tzinfo=timezone.utc)
        last=datetime(2026,11,20,5,0,56,tzinfo=timezone.utc)
        f=self.mt4
        self.source.unlink()
        files=[]
        for i in range(3019):
            dt=initial+timedelta(minutes=i)
            src=f/f"FxPaperQuote_{dt.strftime('%Y%m%d_%H%M%S')}.csv"
            src.write_bytes(b"VALID_ORIGINAL_BYTES_TEST")
            files.append(src)
        final=f/f"FxPaperQuote_{last.strftime('%Y%m%d_%H%M%S')}.csv"
        final.write_bytes(b"FINAL_ORIGINAL_BYTES")
        files.append(final)
        chain=b"\x00"*32
        for src in files:
            chain=hashlib.sha256(
                chain+src.name.encode("ascii")+
                hashlib.sha256(src.read_bytes()).digest()).digest()
        baseline={
            "last_source_basename":final.name,
            "first_source_basename":files[0].name,
            "original_sequence_sha256_local_only":chain.hex(),
        }
        with patch.object(clockfix,"_read_baseline",return_value={}), \
             patch.object(clockfix,"BASELINE",baseline):
            result=launch._historical_chain(
                f,self.baseline,self.mq4)
            self.assertEqual(result[0],baseline)
            self.assertEqual(result[2],3020)
            files[1550].write_bytes(b"ORIGINAL_CHANGED")
            with self.assertRaises(InputError):
                launch._historical_chain(f,self.baseline,self.mq4)

    def test_handoff_success_uses_validated_json_not_stale_native_exit(self):
        base=Path(__file__).resolve().parents[1]
        source=(base/"scripts"/"final_paper_go_live_acceptance_once.ps1"
               ).read_text(encoding="utf-8")
        child=(base/"scripts"/"final_paper_local_machine_handoff_once.ps1"
              ).read_text(encoding="utf-8")
        # w32tm.exe is a DIAGNOSTIC inside the child, not the child's
        # success/failed code. Its nonzero LASTEXITCODE must not falsely
        # abort after a valid saved source; no unverified snapshot accepted.
        self.assertIn("w32tm.exe /query /status",child)
        self.assertIn("$timeStatusExitCode=$LASTEXITCODE",child)
        self.assertNotIn(
            "if ($LASTEXITCODE -ne 0) { throw 'Read-only host snapshot failed",
            source)
        self.assertIn("ConvertFrom-Json -ErrorAction Stop",source)
        self.assertIn("Expected precisely one new read-only snapshot",source)
        for field in ("fx_final_paper_local_machine_handoff_v1",
                      "READ_ONLY_LOCAL_EVIDENCE_NOT_LIVE_TRADE_APPROVAL",
                      "paper_supervisor_process_count",
                      "mt4_terminal_process_count",
                      "runtime_lock_present_not_process_proof",
                      "new_paid_ai_calls_authorized",
                      "new_virtual_positions_permitted",
                      "demo_orders_permitted","real_orders_permitted"):
            self.assertIn(field,source)

    def test_powershell_never_stops_or_restarts_runtime(self):
        script=(Path(__file__).resolve().parents[1]/
                "scripts/final_paper_go_live_acceptance_once.ps1"
               ).read_text(encoding="utf-8")
        self.assertIn("Start-Sleep -Seconds 75",script)
        self.assertIn("final_paper_local_machine_handoff_once.ps1",script)
        self.assertIn("final_paper_go_live_acceptance",script)
        for forbidden in ("Stop-Process","Start-Process","Remove-Item",
                          "Rename-Item","Invoke-WebRequest","Set-Content",
                          "OrderSend","AllowPaidAi"):
            self.assertNotIn(forbidden,script)


if __name__=="__main__":
    unittest.main()
