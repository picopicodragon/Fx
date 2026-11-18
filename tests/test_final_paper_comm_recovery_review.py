"""FINAL-PAPER-40: communication latch review, never release or spend."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_comm_recovery_review as review
from research import final_paper_engine as paper
from research.offline_backtest import InputError

NOW=datetime(2026,11,18,5,20,tzinfo=timezone.utc)
NOW_EPOCH=int(NOW.timestamp())


def fixture(root:Path, *,count=121,delta=60,age=51,
            latch=True,positions=0,pending=0,other=False):
    journal=root/"journal"
    journal.mkdir()
    last=NOW_EPOCH-age
    for i in range(count-10,count+1):
        state=paper.initial_state()
        state["cycle_number"]=i
        state["last_quote_epoch"]=last-(count-i)*delta
        state["communication_latched"]=latch
        state["paid_inference_calls"]=6
        state["dd5_latched"]=other
        state["positions"]=[{} for _ in range(positions)]
        state["pending_signals"]=[{} for _ in range(pending)]
        (journal/f"{i:08d}.json").write_text(
            json.dumps({"state":state}),encoding="utf-8")
    return state


def summary(state,age=51):
    return {
        "completed_cycles":state["cycle_number"],
        "journal_head_sha256_local_only":"a"*64,
        "last_recorded_quote_age_seconds_pc_derived":age,
    }


class CommunicationReviewTests(unittest.TestCase):
    def _evaluate(self,*,delta=60,age=51,latch=True,
                  positions=0,pending=0,other=False):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            state=fixture(root,delta=delta,age=age,latch=latch,
                          positions=positions,pending=pending,other=other)
            with patch.object(review.runtime,"_journal_load",
                              return_value=(state,"a"*64)), \\
                 patch.object(review.status,"summarize",
                              return_value=summary(state,age=age)):
                return review.review(root,now=NOW)

    def test_user_121_cycles_15_more_fresh_6of6_not_auto_released(self):
        result=self._evaluate()
        self.assertEqual(result["journal_cycles"],121)
        self.assertTrue(result["communication_latched"])
        self.assertTrue(result["consecutive_quote_sequence_evidence_ok"])
        self.assertTrue(result["ready_for_manual_root_cause_review"])
        self.assertFalse(result["root_cause_explained"])
        self.assertFalse(result["communication_latch_cleared"])
        self.assertFalse(result["operator_approval_to_clear_communication_latch_recorded"])
        self.assertFalse(result["new_virtual_entries_permitted"])
        self.assertFalse(result["new_paid_ai_calls_permitted"])
        self.assertEqual(result["paid_ai_calls_remaining_under_current_limit"],0)
        self.assertFalse(result["broker_orders_permitted"])

    def test_gap_in_last_ten_keeps_review_from_claiming_sufficient_data(self):
        self.assertFalse(self._evaluate(delta=180)[
            "ready_for_manual_root_cause_review"])

    def test_stale_quote_keeps_review_blocked(self):
        self.assertFalse(self._evaluate(age=300)[
            "ready_for_manual_root_cause_review"])

    def test_unrelated_risk_latch_keeps_review_blocked(self):
        result=self._evaluate(other=True)
        self.assertFalse(result["no_other_risk_latches"])
        self.assertFalse(result["ready_for_manual_root_cause_review"])

    def test_any_virtual_position_or_pending_signal_blocks(self):
        self.assertFalse(self._evaluate(positions=1)[
            "ready_for_manual_root_cause_review"])
        self.assertFalse(self._evaluate(pending=1)[
            "ready_for_manual_root_cause_review"])

    def test_not_latched_never_claims_communication_recovery_eligibility(self):
        self.assertFalse(self._evaluate(latch=False)[
            "ready_for_manual_root_cause_review"])

    def test_report_does_not_use_order_api_or_mutate_state(self):
        root=Path(__file__).resolve().parents[1]
        for filename in ("research/final_paper_comm_recovery_review.py",
                         "scripts/final_paper_comm_recovery_review_once.ps1"):
            s=(root/filename).read_text("utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                              "OPENAI_API_KEY","TYPESAFE_API_KEY",
                              "lock.unlink(", "journal_append(", "ai.run("):
                self.assertNotIn(forbidden,s)

    def test_missing_report_folder_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(InputError):
                review.review(Path(temp)/"missing",now=NOW)


if __name__=="__main__":
    unittest.main()
