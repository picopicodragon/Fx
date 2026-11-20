"""No-order user-staged CURRENT incident release with exact head and gap."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research import final_paper_current_incident_release as current
from research.offline_backtest import InputError

NOW=datetime(2026,11,20,8,0,tzinfo=timezone.utc)
T=int(NOW.timestamp())


def observed(epoch:int)->dict:
    return {
        "capture_epoch":epoch,
        "source_sha256":"a"*64,
        "quotes":{
            p:{"bid":paper.D("159.50"),
               "ask":paper.D("159.505"),
               "tickvalue":paper.D("100"),
               "ticksize":paper.D(".001"),
               "minlot":paper.D(".01"),
               "maxlot":paper.D("20"),
               "step":paper.D(".01"),
               "point":paper.D(".001")} for p in paper.PAIRS},
    }


def populated(root:Path, *, current_gap:bool=True)->tuple[dict,str]:
    runtime._initialize(root)
    n=150
    old_extra=3360
    current_extra=660 if current_gap else 0
    base=T-(n-1)*60-old_extra-current_extra
    state=paper.initial_state()
    prior="0"*64
    for cycle in range(1,n+1):
        epoch=(base+(cycle-1)*60+
               (old_extra if cycle>=107 else 0)+
               (current_extra if cycle>=126 else 0))
        state,_=paper.step(
            state,observed(epoch),entry_evidence_ready=False)
        prior=runtime._journal_append(
            root/"journal",state,prior,"a"*64,
            datetime.fromtimestamp(epoch,tz=timezone.utc))
    assert state["last_quote_epoch"]==T
    assert state["communication_latched"] is True
    return state,prior


class CurrentIncidentApprovalTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.root=self.base/"paper"
        self.mt4=self.base/"MQL4"/"Files"
        self.mt4.mkdir(parents=True)
        self.state,self.head=populated(self.root)
        self.billed={
            "paid_calls_recorded_in_journal":6,
            "paid_calls_in_completed_ledgers":6,
            "journal_head_sha256_local_only":self.head,
        }
        # Existing research review requires all six charges to reconcile.
        self.state["paid_inference_calls"]=6
        # The immutable 150-cycle journal must reflect same paid total:
        last=self.root/"journal"/"00000150.json"
        record=json.loads(last.read_text("utf-8"))
        record["state"]["paid_inference_calls"]=6
        content={k:v for k,v in record.items() if k!="event_sha256"}
        record["event_sha256"]=runtime._digest(content)
        last.write_text(json.dumps(record),encoding="utf-8")
        self.state,self.head=runtime._journal_load(self.root/"journal")
        self.billed["journal_head_sha256_local_only"]=self.head

    def _stage(self, approval=current.APPROVAL):
        with patch.object(current.runtime,"_latest_quote",
                          return_value=observed(T)), \
             patch.object(current.ai_audit,"audit",return_value=self.billed):
            return current.stage(self.root,self.mt4,approval=approval,now=NOW)

    def test_actual_last_incident_after_107_has_exact_gap_and_sha(self):
        incident=current.most_recent_incident(self.root,self.state)
        self.assertEqual(incident["incident_previous_cycle"],125)
        self.assertEqual(incident["incident_next_cycle"],126)
        self.assertEqual(incident["incident_gap_seconds_pc_unattested"],720)
        staged=self._stage()
        self.assertEqual(
            staged["status"],
            "CURRENT_INCIDENT_MANUAL_COMM_RELEASE_STAGED_NOT_APPLIED_NO_GO")
        self.assertFalse(staged["communication_latch_cleared"])
        self.assertEqual(staged["bound_head_sha256"],self.head)
        saved=json.loads((self.root/current.NAME).read_text("utf-8"))
        self.assertEqual(saved["incident_next_cycle"],126)
        self.assertTrue(self.state["communication_latched"])

    def test_new_approval_one_use_6_of_6_preserved_and_relatch_future_gap(self):
        self._stage()
        nxt,ok=current.apply_if_valid(
            self.root,self.state,self.head,observed(T+60),
            NOW+timedelta(seconds=60))
        self.assertTrue(ok)
        self.assertFalse(nxt["communication_latched"])
        self.assertEqual(nxt["paid_inference_calls"],6)
        self.assertEqual(nxt["positions"],[])
        self.assertEqual(nxt["pending_signals"],[])
        self.assertNotEqual(nxt["manual_comm_release_sha256"],None)
        changed,out=paper.step(
            nxt,observed(T+60),entry_evidence_ready=False)
        self.assertFalse(changed["communication_latched"])
        same,again=current.apply_if_valid(
            self.root,changed,self.head,observed(T+120),
            NOW+timedelta(seconds=120))
        self.assertFalse(again)
        self.assertEqual(same["paid_inference_calls"],6)
        later,_=paper.step(
            changed,observed(T+900),entry_evidence_ready=False)
        self.assertTrue(later["communication_latched"])
        _,again=current.apply_if_valid(
            self.root,later,self.head,observed(T+960),
            NOW+timedelta(seconds=960))
        self.assertFalse(again)

    def test_explicit_approval_and_runtime_lock_mandatory(self):
        with self.assertRaises(InputError):
            self._stage(approval="")
        (self.root/".single_operator.lock").write_text("running")
        with self.assertRaises(InputError):
            self._stage()
        self.assertFalse((self.root/current.NAME).exists())

    def test_old_incident_is_not_sufficient_for_current_release(self):
        other=self.base/"old_only"
        state,_=populated(other,current_gap=False)
        with self.assertRaises(InputError):
            current.most_recent_incident(other,state)

    def test_head_tamper_and_expiration_fail_closed(self):
        self._stage()
        with self.assertRaises(InputError):
            current.apply_if_valid(
                self.root,self.state,"b"*64,observed(T+60),
                NOW+timedelta(seconds=60))
        with self.assertRaises(InputError):
            current.apply_if_valid(
                self.root,self.state,self.head,observed(T+360),
                NOW+timedelta(seconds=360))
        obj=json.loads((self.root/current.NAME).read_text("utf-8"))
        obj["incident_gap_seconds_pc_unattested"]=1234
        (self.root/current.NAME).write_text(json.dumps(obj),encoding="utf-8")
        with self.assertRaises(InputError):
            current.apply_if_valid(
                self.root,self.state,self.head,observed(T+60),
                NOW+timedelta(seconds=60))

    def test_runtime_integration_with_staged_permit_and_no_orders(self):
        self._stage()
        with patch.object(runtime,"_latest_quote",
                          return_value=observed(T+60)), \
             patch.object(runtime,"_latest_h1_copy",
                          return_value=None):
            result=runtime.run_one_cycle(
                self.mt4,self.root,[],
                allow_paid=False,analyst_model="",reviewer_model="",
                paid_limit=0,now=NOW+timedelta(seconds=60))
        self.assertTrue(result["current_incident_release_applied_this_cycle"])
        self.assertTrue(result["manual_comm_release_applied_this_cycle"])
        self.assertEqual(result["paid_calls_this_cycle"],0)
        self.assertFalse(result["final_ai_virtual_execution_authorized"])
        self.assertFalse(result["final_new_billable_ai_authorized"])
        self.assertEqual(result["broker_orders_sent_this_run"],0)
        after,_=runtime._journal_load(self.root/"journal")
        self.assertFalse(after["communication_latched"])
        self.assertEqual(after["paid_inference_calls"],6)
        self.assertEqual(after["positions"],[])

    def test_script_never_stops_supervisor_automatically(self):
        src=(Path(__file__).resolve().parents[1]/
             "scripts/final_paper_stage_current_comm_release_once.ps1"
            ).read_text("utf-8")
        self.assertIn("Get-CimInstance Win32_Process",src)
        self.assertIn("--operator-approval",src)
        for forb in ("Stop-Process","Start-Process","Remove-Item",
                     "Rename-Item","Invoke-WebRequest",
                     "OrderSend","Set-Content"):
            self.assertNotIn(forb,src)


if __name__=="__main__":
    unittest.main()
