"""No-cost combined release gate: price monitoring ≠ trading authorization."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import final_paper_release_matrix as matrix
from research.offline_backtest import InputError

H="a"*64
STATUS={
    "journal_head_sha256_local_only":H,
    "completed_cycles":153,
    "price_stream_warning_level_pc_derived":"FRESH",
    "last_recorded_quote_age_seconds_pc_derived":47,
    "communication_latched":True,
    "dd4_latched":False,"dd5_latched":False,
    "daily_loss_latched":False,
    "independent_broker_clock_attested":False,
    "market_consensus_calendar_attested":False,
    "transaction_costs_fully_verified":False,
    "virtual_open_position_count":0,
    "paid_ai_calls_lifetime":6,
    "paid_ai_calls_remaining_under_current_limit":0,
}
REVIEW={
    "journal_head_sha256_local_only":H,
    "journal_cycles":153,
    "recent_quote_continuity_and_risk_review_ok":True,
    "historical_manual_stop_attested":True,
    "explicit_release_approval_recorded":False,
}
BILL={
    "monthly_budget_limit_jpy":"3000.00",
    "operator_billing_statement_supplied":False,
    "arithmetic_room_for_reserved_two_calls":False,
    "old_lifetime_paid_call_cap_exhausted":True,
    "provider_billing_independently_verified":False,
    "operator_approved_paid_renewal":False,
}


class FinalPaperReleaseMatrixTests(unittest.TestCase):
    def _check(self,status_data=None,review_data=None,bill_data=None):
        with patch.object(matrix.status,"summarize",
                          return_value=status_data or STATUS), \
             patch.object(matrix.reentry,"review",
                          return_value=review_data or REVIEW), \
             patch.object(matrix.billing,"review",
                          return_value=bill_data or BILL):
            return matrix.evaluate(Path("not-used"))

    def test_user_153_cycle_manual_stop_observation_fresh_but_trade_blocked(self):
        result=self._check()
        self.assertEqual(result["completed_cycles"],153)
        self.assertTrue(result["price_feed_observation_viable_now"])
        self.assertTrue(result["historical_manual_stop_attested"])
        self.assertTrue(result["recent_continuity_review_sufficient"])
        self.assertEqual(result["ai_calls_cumulative"],6)
        self.assertEqual(result["monthly_budget_limit_jpy"],"3000.00")
        for blocker in (
            "COMMUNICATION_LEVEL2_LATCH_NOT_APPROVED_FOR_RELEASE",
            "PAID_AI_LIFETIME_6_CALL_LIMIT_EXHAUSTED",
            "INDEPENDENT_API_BILLING_EVIDENCE_ABSENT",
            "OFFICIAL_EVENT_COVERAGE_AND_POINT_IN_TIME_CONSENSUS_ABSENT",
            "INDEPENDENT_MT4_CLOCK_ATTESTATION_ABSENT",
            "EXPLICIT_OPERATOR_REENTRY_APPROVAL_ABSENT",
            "TRANSACTION_COSTS_NOT_FULLY_ATTESTED",
        ):
            self.assertIn(blocker,result["virtual_entry_blockers"])
        for prohibited in (
            "virtual_entry_phase_approved",
            "new_paid_inference_permitted",
            "new_virtual_positions_permitted",
            "demo_order_execution_permitted",
            "real_order_execution_permitted",
        ):
            self.assertFalse(result[prohibited])

    def test_new_stale_quote_blocks_even_observation_viability(self):
        state=dict(STATUS,
                   price_stream_warning_level_pc_derived="LEVEL2")
        result=self._check(status_data=state)
        self.assertFalse(result["price_feed_observation_viable_now"])
        self.assertIn("LAST_QUOTE_NOT_FRESH",result["virtual_entry_blockers"])

    def test_change_between_journal_snapshots_fails_closed(self):
        review=dict(REVIEW,journal_head_sha256_local_only="b"*64)
        with self.assertRaisesRegex(InputError,"snapshots raced"):
            self._check(review_data=review)

    def test_billing_room_still_not_sufficient_for_automatic_release(self):
        bill=dict(BILL,
                  operator_billing_statement_supplied=True,
                  arithmetic_room_for_reserved_two_calls=True)
        result=self._check(bill_data=bill)
        self.assertTrue(result["budget_arithmetic_room_for_two_calls_only"])
        self.assertFalse(result["new_paid_inference_permitted"])

    def test_optional_mt4_spread_samples_do_not_certify_total_cost(self):
        synthetic={
            "sampled_complete_three_pair_cycles":10,
            "latest_quote_age_seconds_pc_derived":16,
            "latest_quote_fresh_pc_derived":True,
            "per_pair":{
                "USD/JPY":{
                    "spread_min_pips_observed":"0.5",
                    "spread_max_pips_observed":"0.6"},
                "EUR/JPY":{
                    "spread_min_pips_observed":"1.0",
                    "spread_max_pips_observed":"1.2"},
                "EUR/USD":{
                    "spread_min_pips_observed":"0.5",
                    "spread_max_pips_observed":"0.5"},
            },
        }
        with patch.object(matrix.status,"summarize",return_value=STATUS), \
             patch.object(matrix.reentry,"review",return_value=REVIEW), \
             patch.object(matrix.billing,"review",return_value=BILL), \
             patch.object(matrix.quote_costs,"audit",return_value=synthetic):
            out=matrix.evaluate(Path("not-used"),
                                mt4_files=Path("MT4/MQL4/Files"))
        self.assertTrue(out["mt4_quote_contract_samples_supplied"])
        self.assertEqual(out["observed_mt4_quote_cycles"],10)
        self.assertEqual(out["observed_spread_pips_by_pair"]["USD/JPY"][
            "minimum"],"0.5")
        self.assertFalse(out["commission_slippage_swap_independently_verified"])
        self.assertIn("TRANSACTION_COSTS_NOT_FULLY_ATTESTED",
                      out["virtual_entry_blockers"])
        self.assertFalse(out["new_paid_inference_permitted"])
        self.assertFalse(out["new_virtual_positions_permitted"])

    def test_244_cycle_70_second_journal_level1_and_120_second_sample(self):
        # The real 16:24 PC report used journal age=70 seconds, raw CSV
        # freshness <=120 seconds. They do not share a strict threshold or
        # an atomic measurement instant. Never treat this as LEVEL2.
        state=dict(STATUS,
                   completed_cycles=244,
                   price_stream_warning_level_pc_derived="LEVEL1",
                   last_recorded_quote_age_seconds_pc_derived=70)
        reviewed=dict(REVIEW,journal_cycles=244)
        raw={
            "sampled_complete_three_pair_cycles":10,
            "latest_quote_age_seconds_pc_derived":70,
            "latest_quote_fresh_pc_derived":True,
            "per_pair": {
                pair:{"spread_min_pips_observed":value,
                      "spread_max_pips_observed":value}
                for pair,value in (
                    ("USD/JPY","0.5"),("EUR/JPY","1.0"),
                    ("EUR/USD","0.5"))
            },
        }
        with patch.object(matrix.status,"summarize",return_value=state), \
             patch.object(matrix.reentry,"review",return_value=reviewed), \
             patch.object(matrix.billing,"review",return_value=BILL), \
             patch.object(matrix.quote_costs,"audit",return_value=raw):
            result=matrix.evaluate(Path("not-used"),
                                   mt4_files=Path("MT4/MQL4/Files"))
        self.assertEqual(result["completed_cycles"],244)
        self.assertEqual(result["paper_journal_warning_level_pc_derived"],
                         "LEVEL1")
        self.assertEqual(result["paper_journal_fresh_threshold_seconds_exclusive"],
                         60)
        self.assertEqual(result["mt4_raw_sample_fresh_threshold_seconds_inclusive"],
                         120)
        self.assertTrue(result[
            "paper_journal_and_mt4_freshness_labels_diverge"])
        self.assertFalse(result["price_feed_observation_viable_now"])
        self.assertTrue(result["sampled_quote_stream_fresh_pc_unattested"])
        self.assertFalse(result[
            "producer_consumer_process_failure_proved_by_snapshot"])
        self.assertFalse(result["quote_clock_measurements_atomic_or_independent"])
        self.assertIn("LAST_QUOTE_NOT_FRESH",result["virtual_entry_blockers"])
        self.assertFalse(result["new_virtual_positions_permitted"])
        self.assertFalse(result["new_paid_inference_permitted"])

    def test_missing_raw_quote_sample_explains_it_is_unmeasured(self):
        out=self._check()
        self.assertIsNone(out["mt4_raw_sample_latest_quote_age_seconds_pc_derived"])
        self.assertFalse(out[
            "paper_journal_and_mt4_freshness_labels_diverge"])
        self.assertEqual(out["paper_journal_fresh_threshold_seconds_exclusive"],
                         60)

    def test_source_readonly_and_no_network_or_orders(self):
        src=(Path(__file__).resolve().parents[1]/
             "research"/"final_paper_release_matrix.py").read_text("utf-8")
        for forbidden in ("OrderSend(", "OrderClose(", "urllib.request",
                          "OPENAI_API_KEY", "ai.run(", "lock.unlink(",
                          "_journal_append(", "allow_external_api=True"):
            self.assertNotIn(forbidden,src)


if __name__=="__main__":
    unittest.main()
