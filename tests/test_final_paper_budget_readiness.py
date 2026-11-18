"""Untrusted manual billing evidence never renews six-call cap."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_budget_readiness as budget
from research.offline_backtest import InputError

T=datetime(2026,11,18,6,0,tzinfo=timezone.utc)
AI={"paid_calls_recorded_in_journal":6,
    "remaining_calls_under_existing_limit":0}


def record(*,billed="500.00",reserve="200.00",calls=6):
    return {
        "schema":budget.EVIDENCE_SCHEMA,
        "month_utc":"2026-11",
        "captured_at_utc":"2026-11-18T05:55:00Z",
        "source":"OPENAI_PROVIDER_BILLING_OPERATOR_TRANSCRIPTION",
        "currency":"JPY","billed_jpy":billed,
        "future_two_call_reserve_jpy":reserve,
        "completed_paid_calls_observed":calls,
        "operator_checked_provider_page":True,
    }


class BudgetReadinessTests(unittest.TestCase):
    def _evaluate(self,values=None):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"billing.json"
            if values is not None:
                path.write_text(json.dumps(values),encoding="utf-8")
            with patch.object(budget.ai,"audit",return_value=AI):
                return budget.review(Path(tmp),path if values else None,now=T)

    def test_no_statement_stays_blocked(self):
        r=self._evaluate()
        self.assertIsNone(r["billed_jpy_operator_reported"])
        self.assertFalse(r["arithmetic_room_for_reserved_two_calls"])
        self.assertFalse(r["future_paid_inference_authorized"])
        self.assertTrue(r["old_lifetime_paid_call_cap_exhausted"])

    def test_operator_amount_within_cap_is_arithmetic_only(self):
        r=self._evaluate(record(billed="2400.00",reserve="500.00"))
        self.assertTrue(r["arithmetic_room_for_reserved_two_calls"])
        self.assertFalse(r["provider_billing_independently_verified"])
        self.assertFalse(r["operator_approved_paid_renewal"])
        self.assertFalse(r["future_paid_inference_authorized"])
        self.assertEqual(r["old_lifetime_paid_call_cap"],6)

    def test_over_budget_does_not_claim_room(self):
        self.assertFalse(self._evaluate(record(
            billed="2999.00",reserve="100.00"))[
                "arithmetic_room_for_reserved_two_calls"])

    def test_zero_reserve_does_not_claim_future_room(self):
        self.assertFalse(self._evaluate(record(
            billed="100.00",reserve="0.00"))[
                "arithmetic_room_for_reserved_two_calls"])

    def test_invalid_or_stale_statement_fails_closed(self):
        for change in [
            {"month_utc":"2026-10"},
            {"completed_paid_calls_observed":4},
            {"billed_jpy":"NaN"},
            {"billed_jpy":"-1.00"},
            {"billed_jpy":"1e2"},
            {"billed_jpy":"3000.001"},
            {"future_two_call_reserve_jpy":"-0.01"},
            {"operator_checked_provider_page":"true"},
            {"captured_at_utc":"2026-11-16T05:55:00Z"},
        ]:
            with self.subTest(change=change):
                evidence=record()
                evidence.update(change)
                with self.assertRaises(InputError):
                    self._evaluate(evidence)

    def test_no_network_order_or_api_spend_code(self):
        s=(Path(__file__).resolve().parents[1]/
           "research"/"final_paper_budget_readiness.py").read_text("utf-8")
        for forbidden in ("OrderSend(", "OrderClose(", "urllib.request",
                          "OPENAI_API_KEY", "ai.run(", "lock.unlink(",
                          "allow_external_api=True"):
            self.assertNotIn(forbidden,s)


if __name__=="__main__":
    unittest.main()
