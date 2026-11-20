"""The current 38-hour incident must be approved exactly once, never erased."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_engine as paper
from research import final_paper_current_comm_release as comm
from research.offline_backtest import InputError

START=datetime(2026,11,20,10,0,tzinfo=timezone.utc)


class CurrentIncidentSingleUseTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"state"
        runtime._initialize(self.root)
        initial=paper.initial_state()
        initial["cycle_number"]=1
        initial["paid_inference_calls"]=6
        initial["communication_latched"]=True
        initial["last_quote_epoch"]=int(START.timestamp())
        head=runtime._journal_append(
            self.root/"journal",initial,"0"*64,"a"*64,START)
        second=dict(initial)
        second["cycle_number"]=2
        second["last_quote_epoch"]=int(START.timestamp())+38*3600
        self.now=START+timedelta(hours=38,seconds=5)
        self.head=runtime._journal_append(
            self.root/"journal",second,head,"b"*64,self.now)
        self.state=second

    def test_preview_includes_38h_gap_without_mutating_latch(self):
        result=comm.gaps(self.root)
        self.assertTrue(result["current_communication_latched"])
        self.assertEqual(result["known_gaps_over_600_seconds"][0][
            "unobserved_seconds"],38*3600)
        self.assertEqual(result["journal_head_sha256"],self.head)
        self.assertFalse(result["operator_has_approved"])
        self.assertFalse((self.root/comm.FILE_NAME).exists())

    def test_manual_staging_does_not_clear_and_consumption_is_single_use(self):
        fingerprint=comm.gaps(self.root)[
            "all_historical_gaps_fingerprint_sha256"]
        pending=comm.stage(
            self.root,approval=comm.APPROVAL,
            gap_fingerprint=fingerprint,
            supervisor_absence_checked=True,now=self.now)
        self.assertFalse(pending["latch_released"])
        self.assertTrue((self.root/comm.FILE_NAME).is_file())
        self.assertTrue(self.state["communication_latched"])
        quote={"capture_epoch":self.state["last_quote_epoch"]+60}
        fresh=self.now+timedelta(seconds=59)
        changed,applied=comm.apply_if_valid(
            self.root,self.state,self.head,quote,fresh)
        self.assertTrue(applied)
        self.assertFalse(changed["communication_latched"])
        self.assertEqual(changed["auto_current_comm_release_sha256"],
                         pending["permit_sha256"])
        again,repeat=comm.apply_if_valid(
            self.root,changed,"f"*64,
            {"capture_epoch":quote["capture_epoch"]+60},fresh)
        self.assertFalse(repeat)
        self.assertIs(again,changed)

    def test_wrong_gap_fingerprint_or_missing_stop_approval_never_applies(self):
        fingerprint=comm.gaps(self.root)[
            "all_historical_gaps_fingerprint_sha256"]
        for granted,hash_value,checked in (
            (comm.APPROVAL,"0"*64,True),
            ("",fingerprint,True),
            (comm.APPROVAL,fingerprint,False),
        ):
            with self.subTest(approval=granted,checked=checked):
                with self.assertRaises(InputError):
                    comm.stage(self.root,approval=granted,
                               gap_fingerprint=hash_value,
                               supervisor_absence_checked=checked,now=self.now)
        self.assertFalse((self.root/comm.FILE_NAME).exists())

    def test_live_supervisor_lock_prevents_manual_release_staging(self):
        (self.root/".single_operator.lock").write_text("active")
        fp=comm.gaps(self.root)["all_historical_gaps_fingerprint_sha256"]
        with self.assertRaises(InputError):
            comm.stage(self.root,approval=comm.APPROVAL,
                       gap_fingerprint=fp,
                       supervisor_absence_checked=True,now=self.now)

    def test_same_permit_cannot_release_a_new_communication_gap(self):
        fp=comm.gaps(self.root)["all_historical_gaps_fingerprint_sha256"]
        comm.stage(self.root,approval=comm.APPROVAL,
                   gap_fingerprint=fp,
                   supervisor_absence_checked=True,now=self.now)
        recent=self.state["last_quote_epoch"]+660
        with self.assertRaises(InputError):
            comm.apply_if_valid(
                self.root,self.state,self.head,{"capture_epoch":recent},
                self.now+timedelta(seconds=660))


if __name__=="__main__":
    unittest.main()
