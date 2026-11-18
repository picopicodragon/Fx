"""FINAL-PAPER-35: no-restart/no-spend recovery gate after consumer stops."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_free_resume_preflight as pre
from research.offline_backtest import InputError

NOW=datetime(2026,11,18,5,0,tzinfo=timezone.utc)


def diag(*,gap=2700,age=13,condition="FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON"):
    return {
        "diagnosis":condition,
        "latest_raw_quote_age_seconds_pc_derived":age,
        "last_processed_quote_epoch_pc_unattested":1794974931,
        "latest_raw_quote_epoch_pc_unattested":1794974931+gap,
    }


def status(*,positions=0):
    return {"virtual_open_position_count":positions}


def paid(*,used=6,ledger=6):
    return {
        "journal_cycles":106,
        "journal_head_sha256_local_only":"a"*64,
        "paid_calls_recorded_in_journal":used,
        "paid_calls_in_completed_ledgers":ledger,
        "remaining_calls_under_existing_limit":6-used,
    }


class FreeResumePreflightTests(unittest.TestCase):
    def test_fresh_mt4_python_stopped_45m_gap_no_auto_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(pre.stream,"diagnose",return_value=diag()), \
                 patch.object(pre.paper_status,"summarize",return_value=status()), \
                 patch.object(pre.paid,"audit",return_value=paid()):
                result=pre.preflight(root,root,now=NOW)
            self.assertEqual(result["journal_cycles"],106)
            self.assertEqual(result["paid_ai_calls_used"],6)
            self.assertTrue(result["communication_gap_will_latch_on_next_quote"])
            self.assertTrue(result["operator_must_verify_no_python_supervisor_process"])
            self.assertFalse(result["actual_process_absence_verified_by_python"])
            self.assertFalse(result["start_paid_ai_allowed"])
            self.assertFalse(result["new_virtual_entries_allowed_by_preflight"])
            self.assertFalse(result["existing_risk_latches_cleared"])
            self.assertFalse(result["auto_restart_performed"])
            self.assertFalse(result["real_orders_permitted"])

    def test_existing_operator_lock_blocks_even_fresh_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/".single_operator.lock").write_text("running")
            with self.assertRaisesRegex(InputError,"RUNNING_LOCK"):
                pre.preflight(root,root,now=NOW)

    def test_stale_quote_or_unprocessed_old_quote_is_not_restart_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for d in (
                diag(age=600),
                diag(condition="UNPROCESSED_MT4_QUOTES_ALREADY_STALE"),
                diag(condition="MT4_OBSERVER_QUOTE_STREAM_STALE"),
                diag(age=-1),
            ):
                with patch.object(pre.stream,"diagnose",return_value=d):
                    with self.assertRaisesRegex(
                            InputError,"MT4_FRESH_QUOTE_REQUIRED"):
                        pre.preflight(root,root,now=NOW)

    def test_any_open_virtual_position_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(pre.stream,"diagnose",return_value=diag()), \
                 patch.object(pre.paper_status,"summarize",
                              return_value=status(positions=1)):
                with self.assertRaisesRegex(
                    InputError,"EXISTING_PAPER_POSITIONS_REQUIRE_REVIEW"):
                    pre.preflight(root,root,now=NOW)

    def test_unreconciled_ai_rejected_before_any_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(pre.stream,"diagnose",return_value=diag()), \
                 patch.object(pre.paper_status,"summarize",return_value=status()), \
                 patch.object(pre.paid,"audit",return_value=paid(used=6,ledger=4)):
                with self.assertRaisesRegex(
                    InputError,"PAID_AI_LEDGER_UNRECONCILED"):
                    pre.preflight(root,root,now=NOW)

    def test_persistence_only_new_preflight_report_not_existing_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"00000001.json").write_text("PREVIOUS-JOURNAL")
            out=root/"report.json"
            with patch.object(pre.stream,"diagnose",return_value=diag()), \
                 patch.object(pre.paper_status,"summarize",return_value=status()), \
                 patch.object(pre.paid,"audit",return_value=paid()):
                with patch.object(pre,"preflight") as stub:
                    stub.return_value=pre.preflight(root,root,now=NOW)
                    self.assertEqual(pre.main([
                        "--state-root",str(root),
                        "--mt4-files",str(root),"--out",str(out)]),0)
            self.assertEqual((root/"00000001.json").read_text(),
                             "PREVIOUS-JOURNAL")
            self.assertTrue(json.loads(out.read_text())[
                "communication_gap_will_latch_on_next_quote"])

    def test_sources_have_no_order_or_budget_activation(self):
        base=Path(__file__).resolve().parents[1]
        py=(base/"research"/"final_paper_free_resume_preflight.py").read_text()
        ps=(base/"scripts"/"final_paper_free_resume_preflight_once.ps1").read_text()
        for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                          "lock.unlink(", "paid.run(", "ai.run(",
                          "OPENAI_API_KEY", "TYPESAFE_API_KEY"):
            self.assertNotIn(forbidden,py+ps)
        self.assertIn("Get-CimInstance Win32_Process",ps)
        self.assertIn("research\\.final_paper_runtime",ps)
        self.assertIn("Existing paper Python supervisor PID",ps)


if __name__=="__main__":
    unittest.main()
