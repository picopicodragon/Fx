"""FINAL-PAPER-46: uninterrupted journal chain forensic gap replay."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_interruption_forensics as forensic
from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research.offline_backtest import InputError

NOW=datetime(2026,11,18,6,10,tzinfo=timezone.utc)
T=int(NOW.timestamp())


def _fixture(root:Path, *,gap:bool=True,cycles:int=21):
    runtime._initialize(root)
    prev="0"*64
    for index in range(1,cycles+1):
        # Includes a 2760-second interruption from cycle 11 to cycle 12.
        if gap and index<=11:
            epoch=T-3300-(11-index)*60
        else:
            epoch=T-40-(cycles-index)*60
        state=paper.initial_state()
        state["cycle_number"]=index
        state["last_quote_epoch"]=epoch
        state["paid_inference_calls"]=6
        state["communication_latched"]=bool(gap and index>=12)
        prev=runtime._journal_append(
            root/"journal",state,prev,"a"*64,NOW)
    return prev


class FinalPaperForensicTests(unittest.TestCase):
    def test_21_cycles_2760_second_gap_is_safely_identified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            head=_fixture(root)
            existing=(root/"journal"/"00000011.json").read_bytes()
            outcome=forensic.analyze(root,now=NOW)
            gap=outcome["latest_level2_gap_in_scanned_window"]
            self.assertEqual(gap["previous_cycle"],11)
            self.assertEqual(gap["first_cycle_after_gap"],12)
            self.assertEqual(gap["observation_gap_seconds_pc_derived"],2760)
            self.assertEqual(outcome["cycles_recorded_since_latest_level2_gap"],10)
            self.assertEqual(outcome["latest_processed_quote_age_seconds_pc_derived"],40)
            self.assertEqual(outcome["journal_head_sha256_local_only"],head)
            self.assertEqual((root/"journal"/"00000011.json").read_bytes(),existing)
            self.assertFalse(outcome["process_exit_reason_verified"])
            self.assertFalse(outcome["communication_latch_cleared"])
            self.assertFalse(outcome["new_paid_ai_calls_permitted"])
            self.assertFalse(outcome["real_orders_permitted"])

    def test_uninterrupted_quote_stream_does_not_invent_an_outage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            _fixture(root,gap=False,cycles=15)
            report=forensic.analyze(root,now=NOW)
            self.assertIsNone(report["latest_level2_gap_in_scanned_window"])
            self.assertIsNone(report["cycles_recorded_since_latest_level2_gap"])
            self.assertEqual(report["current_paid_ai_calls_lifetime"],6)

    def test_missing_or_tampered_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            _fixture(root,cycles=14)
            p=root/"journal"/"00000010.json"
            value=json.loads(p.read_text())
            value["state"]["last_quote_epoch"]=1
            p.write_text(json.dumps(value))
            with self.assertRaises(InputError):
                forensic.analyze(root,now=NOW)

    def test_readonly_cli_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            _fixture(root)
            out=Path(tmp)/"report.json"
            self.assertEqual(forensic.main([
                "--state-root",str(root),"--out",str(out)]),0)
            before=out.read_bytes()
            self.assertEqual(forensic.main([
                "--state-root",str(root),"--out",str(out)]),2)
            self.assertEqual(out.read_bytes(),before)

    def test_forensic_sources_do_not_execute_orders_paid_ai_or_clear_locks(self):
        root=Path(__file__).resolve().parents[1]
        py=(root/"research"/"final_paper_interruption_forensics.py").read_text()
        ps=(root/"scripts"/"final_paper_interruption_forensics_once.ps1").read_text()
        for prohibited in ("OrderSend(","OrderClose(","OrderModify(",
                           "TYPESAFE_API_KEY","OPENAI_API_KEY",
                           "lock.unlink(","_journal_append(","ai.run(",
                           "Remove-Item","Stop-Process"):
            self.assertNotIn(prohibited,py+ps)
        self.assertNotIn(" $_.Message",ps)
        self.assertIn("exact_root_cause_proved=$false",ps)


if __name__=="__main__":
    unittest.main()
