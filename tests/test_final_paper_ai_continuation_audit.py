"""FINAL-PAPER-16: no-cost AI call accounting and renewal refusal."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import final_paper_ai_continuation_audit as audit
from research import final_paper_runtime as runtime
from research.offline_backtest import InputError


def create_root(root: Path, n: int = 0) -> None:
    runtime._initialize(root)
    for k in range(n):
        (root/"ai_research"/
            f"ai_USDJPY_20261118_{k:06d}.json").write_text("{}")


COMPLETE = {
    "stage": "COMPLETE",
    "pending_role": None,
    "analyst": {"action": "HOLD"},
    "reviewer": {"verdict": "APPROVED"},
}


class PaperContinuationAuditTests(unittest.TestCase):
    def test_new_unfunded_portfolio_is_readonly_zero_spend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            create_root(root)
            with patch.object(audit.paid_ledgers,"check_directory",
                              return_value={"operator_reviewed_http401":0}) as check:
                result=audit.audit(root)
            check.assert_called_once()
            self.assertEqual(result["paid_calls_recorded_in_journal"],0)
            self.assertEqual(result["remaining_calls_under_existing_limit"],6)
            self.assertIsNone(result["estimated_or_actual_api_cost_jpy"])
            self.assertFalse(result["budget_renewal_authorized"])
            self.assertFalse(result["new_paid_inference_allowed_by_this_audit"])
            self.assertFalse(result["new_broker_orders_permitted"])

    def test_detects_three_complete_ledgers_but_no_journal_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            create_root(root,3)
            with patch.object(audit.paid_ledgers,"check_directory",
                              return_value={"operator_reviewed_http401":0}), \
                 patch.object(audit.paid_ledgers,"_read_ledger",
                              return_value=(COMPLETE,"a"*64)):
                with self.assertRaisesRegex(
                    InputError,"PAPER_JOURNAL_AND_PAID_LEDGER_COUNT_MISMATCH"):
                    audit.audit(root)

    def test_successful_six_call_reconciliation_still_never_renews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            create_root(root,3)
            state=__import__("research.final_paper_engine",
                             fromlist=["initial_state"]).initial_state()
            state["cycle_number"]=1
            state["paid_inference_calls"]=6
            runtime._journal_append(root/"journal",state,"0"*64,
                                     "a"*64,
                                     __import__("datetime").datetime(
                                         2026,11,18,tzinfo=__import__(
                                             "datetime").timezone.utc))
            with patch.object(audit.paid_ledgers,"check_directory",
                              return_value={"operator_reviewed_http401":1}), \
                 patch.object(audit.paid_ledgers,"_read_ledger",
                              return_value=(COMPLETE,"b"*64)):
                result=audit.audit(root)
            self.assertEqual(result["completed_two_model_ledgers"],3)
            self.assertEqual(result["remaining_calls_under_existing_limit"],0)
            self.assertEqual(result[
                "previous_401_rejections_manually_reviewed"],1)
            self.assertFalse(result["budget_renewal_authorized"])

    def test_pending_unreviewed_blocks_any_further_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            create_root(root)
            with patch.object(audit.paid_ledgers,"check_directory",
                              side_effect=InputError("PENDING")):
                with self.assertRaisesRegex(
                    InputError,"PAID_LEDGER_PENDING_OR_UNRECONCILED"):
                    audit.audit(root)

    def test_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            create_root(root)
            out=Path(tmp)/"result.json"
            with patch.object(audit.paid_ledgers,"check_directory",
                              return_value={"operator_reviewed_http401":0}):
                self.assertEqual(audit.main([
                    "--state-root",str(root),"--out",str(out)]),0)
                self.assertEqual(audit.main([
                    "--state-root",str(root),"--out",str(out)]),2)
            self.assertFalse(json.loads(out.read_text())[
                "budget_renewal_authorized"])

    def test_no_external_execution_primitives(self):
        root=Path(__file__).resolve().parents[1]
        src=(root/"research"/"final_paper_ai_continuation_audit.py").read_text()
        for forbidden in ("OrderSend(", "OrderClose(", "urllib.request",
                          "OPENAI_API_KEY", "TYPESAFE_API_KEY",
                          "allow_external_api=True", "EnableDemoOrders=true"):
            self.assertNotIn(forbidden,src)


if __name__ == "__main__":
    unittest.main()
