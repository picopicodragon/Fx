"""FINAL-PAPER-27: safe no-cost status display for 106+ paper cycles.

The read-only diagnostic never changes a live journal or renews paid calls.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_status as status
from research import final_paper_runtime as runtime
from research.offline_backtest import InputError


T = datetime(2026, 11, 18, 5, 0, tzinfo=timezone.utc)
EPOCH = int(T.timestamp())


class FinalPaperStatusWatchdogTests(unittest.TestCase):
    def _status(self, age, *, calls=6, latched=False):
        state = paper.initial_state()
        state["paid_inference_calls"] = calls
        state["cycle_number"] = 106
        state["communication_latched"] = latched
        state["last_quote_epoch"] = 0 if age is None else EPOCH-age
        with patch.object(status.runtime,"_journal_load",
                          return_value=(state,"f"*64)):
            return status.summarize(Path("not-used"),now=T)

    def test_user_106_cycles_six_calls_still_block_paid_renewal(self):
        outcome=self._status(20)
        self.assertEqual(outcome["completed_cycles"],106)
        self.assertEqual(outcome["paid_ai_calls_lifetime"],6)
        self.assertEqual(outcome[
            "paid_ai_calls_remaining_under_current_limit"],0)
        self.assertTrue(outcome["paid_ai_lifetime_cap_reached"])
        self.assertFalse(outcome["api_cost_jpy_verified"])
        self.assertFalse(outcome["api_budget_renewal_authorized"])
        self.assertFalse(outcome["new_paid_ai_calls_authorized_by_status"])
        self.assertEqual(outcome["price_stream_warning_level_pc_derived"],
                         "FRESH")
        self.assertFalse(outcome["broker_orders_permitted"])

    def test_quote_freshness_warning_60_and_600_second_boundaries(self):
        for age, level in ((None,"NO_CAPTURE"),(0,"FRESH"),(59,"FRESH"),
                           (60,"LEVEL1"),(599,"LEVEL1"),(600,"LEVEL2"),
                           (1200,"LEVEL2")):
            with self.subTest(age=age):
                result=self._status(age)
                self.assertEqual(result["price_stream_warning_level_pc_derived"],level)
                self.assertEqual(result["last_recorded_quote_age_seconds_pc_derived"],
                                 age)
                self.assertEqual(result[
                    "quote_recent_enough_for_further_paper_evaluation"],
                    level=="FRESH")
                self.assertFalse(result["new_paid_ai_calls_authorized_by_status"])

    def test_latched_state_never_claims_fresh_evaluation_permission(self):
        self.assertFalse(self._status(5,latched=True)[
            "quote_recent_enough_for_further_paper_evaluation"])

    def test_future_pc_clock_or_corrupt_paid_counter_fail_closed(self):
        with self.assertRaises(InputError):
            self._status(-11)
        with self.assertRaises(InputError):
            self._status(5,calls=7)
        with self.assertRaises(InputError):
            self._status(5,calls=-1)

    def test_missing_first_capture_does_not_claim_operational_evidence(self):
        outcome=self._status(None,calls=0)
        self.assertEqual(outcome["price_stream_warning_level_pc_derived"],
                         "NO_CAPTURE")
        self.assertEqual(outcome["paid_ai_calls_remaining_under_current_limit"],6)
        self.assertFalse(outcome["new_paid_ai_calls_authorized_by_status"])

    def test_only_offline_status_without_order_or_network_calls(self):
        root=Path(__file__).resolve().parents[1]
        for name in ("research/final_paper_status.py",
                     "research/final_paper_ai_continuation_audit.py"):
            source=(root/name).read_text("utf-8")
            for forbidden in ("OrderSend(", "OrderClose(",
                              "urllib.request", "WebRequest(",
                              "OPENAI_API_KEY","TYPESAFE_API_KEY",
                              "allow_external_api=True"):
                self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
