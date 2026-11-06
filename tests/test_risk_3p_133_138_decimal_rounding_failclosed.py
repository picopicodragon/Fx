"""RISK-3P-133..138: reject rounding of fictional FX risk arithmetic.

All input prices, tickets and position reconciliation flags are synthetic.
Small precision contexts are injected only to prove the fail-closed branch,
not to configure any broker or real trading engine.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Context as NativeContext
from decimal import Decimal, Inexact, Rounded, ROUND_DOWN, getcontext, localcontext
from unittest.mock import patch
import unittest

from scripts import phase1_three_pair_synthetic_risk as portfolio
from scripts import phase1_three_pair_synthetic_stop_conversion as stop


ASOF = 133
SID = "SIM-ROUNDING-133"
TINY_COST = "0.000000000001"


def portfolio_quotes():
    return {
        "USD/JPY": portfolio.Quote("USD/JPY", "150", "151", ASOF, SID),
        "EUR/JPY": portfolio.Quote("EUR/JPY", "181", "182", ASOF, SID),
        "EUR/USD": portfolio.Quote("EUR/USD", "1.20", "1.21", ASOF, SID),
    }


def portfolio_records():
    return [
        portfolio.Trade("candidate", "USD/JPY", "BUY", "CANDIDATE",
                        "1000", "500.000000000001"),
        portfolio.Trade("pending", "EUR/USD", "SELL", "PENDING",
                        "1000", TINY_COST),
    ]


def review_portfolio(trades=None, quotes=None, equity="100000",
                     reconciled=True):
    return portfolio.review_synthetic_portfolio(
        portfolio_quotes() if quotes is None else quotes,
        portfolio_records() if trades is None else trades,
        asof=ASOF, snapshot_id=SID, equity_jpy=equity,
        positions_reconciled=reconciled,
        pending_orders_reconciled=reconciled,
    )


def stop_contracts():
    return {pair: stop.Contract(pair, "100000", "0.01", "0.01", "1")
            for pair in stop.PAIRS}


def stop_quotes():
    return {
        "USD/JPY": stop.Quote("USD/JPY", "150", "151", ASOF, SID),
        "EUR/JPY": stop.Quote("EUR/JPY", "181", "182", ASOF, SID),
        "EUR/USD": stop.Quote("EUR/USD", "1.20", "1.21", ASOF, SID),
    }


def stop_tickets():
    return [
        stop.Ticket("candidate", "USD/JPY", "BUY", "CANDIDATE",
                    "0.01", "150.5", "150", "0", TINY_COST, SID),
        stop.Ticket("pending", "EUR/USD", "SELL", "PENDING",
                    "0.01", "1.19", "1.20", "0", "0", SID),
    ]


def review_stop(tickets=None, contracts=None, quotes=None,
                equity="100000", reconciled=True):
    return stop.review_synthetic_stop_risk(
        stop_contracts() if contracts is None else contracts,
        stop_quotes() if quotes is None else quotes,
        stop_tickets() if tickets is None else tickets,
        equity_jpy=equity, asof=ASOF, snapshot_id=SID,
        positions_reconciled=reconciled, pending_reconciled=reconciled,
        inflight_reservations_reconciled=reconciled,
    )


def weak_context(prec=8):
    return lambda **_: NativeContext(prec=prec)


class DecimalRoundingFailClosedTests(unittest.TestCase):
    def held_portfolio(self, r, complete=False):
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.stop_release_allowed)
        self.assertFalse(r.automatic_retry_allowed)
        self.assertIsNone(r.verified_values)
        self.assertIs(r.arithmetic_complete, complete)

    def held_stop(self, r, complete=False):
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.stop_release_allowed)
        self.assertFalse(r.automatic_retry_allowed)
        self.assertFalse(r.result_authorizes_trade)
        self.assertFalse(r.broker_contract_verified)
        self.assertFalse(r.stop_execution_guaranteed)
        self.assertIsNone(r.verified_values)
        self.assertIs(r.illustrative_complete, complete)

    def test_normal_portfolio_preserves_micro_excess_with_256_digits(self):
        r = review_portfolio()
        self.held_portfolio(r, True)
        self.assertEqual(r.candidate_max_loss_jpy, "500.000000000001")
        self.assertTrue(r.candidate_exceeds_existing_limit)
        self.assertEqual(r.total_max_loss_jpy, "500.000000000002")

    def test_normal_stop_preserves_micro_excess_with_96_digits(self):
        r = review_stop(tickets=[stop_tickets()[0]])
        self.held_stop(r, True)
        self.assertEqual(r.candidate_illustrative_loss_jpy,
                         "500.000000000001")
        self.assertTrue(r.candidate_exceeds_existing_fraction)

    def test_portfolio_rounded_micro_excess_now_fails_closed(self):
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            r = review_portfolio()
        self.held_portfolio(r)
        self.assertEqual(r.reason, "SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")

    def test_stop_rounded_micro_cost_now_fails_closed(self):
        with patch.object(stop, "Context", side_effect=weak_context(8)):
            r = review_stop(tickets=[stop_tickets()[0]])
        self.held_stop(r)
        self.assertEqual(r.reason, "SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")

    def test_stop_multi_ticket_sum_rounding_also_fails_closed(self):
        with patch.object(stop, "Context", side_effect=weak_context(8)):
            r = review_stop()
        self.held_stop(r)
        self.assertEqual(r.reason, "SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")

    def test_portfolio_micro_pending_loss_cannot_disappear_on_sum(self):
        rows = [
            replace(portfolio_records()[0], max_loss_jpy="500"),
            replace(portfolio_records()[1], max_loss_jpy=TINY_COST),
        ]
        regular = review_portfolio(trades=rows)
        self.held_portfolio(regular, True)
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            weak = review_portfolio(trades=rows)
        self.held_portfolio(weak)
        self.assertEqual(weak.reason,
                         "SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")

    def test_three_factor_extreme_gross_detects_reduced_precision(self):
        huge = "9" * 40
        q = portfolio_quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], bid=huge, ask=huge)
        q["USD/JPY"] = replace(q["USD/JPY"], bid=huge, ask=huge)
        rows = [portfolio.Trade("candidate", "EUR/USD", "BUY",
                                "CANDIDATE", huge, "100")]
        regular = review_portfolio(trades=rows, quotes=q)
        self.held_portfolio(regular, True)
        with patch.object(portfolio, "Context", side_effect=weak_context(96)):
            weak = review_portfolio(trades=rows, quotes=q)
        self.held_portfolio(weak)
        self.assertEqual(weak.reason,
                         "SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")

    def test_rounded_only_flag_is_distinct_from_inexact_and_still_rejected(self):
        with localcontext(NativeContext(prec=8)) as ctx:
            value = Decimal("100000000000") * Decimal("100000000000")
            self.assertEqual(value, Decimal("100000000000000000000000"))
            self.assertTrue(ctx.flags[Rounded])
            self.assertFalse(ctx.flags[Inexact])
        q = portfolio_quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], bid="100000000000",
                               ask="100000000000")
        rows = [portfolio.Trade("candidate", "EUR/USD", "BUY",
                                "CANDIDATE", "100000000000", "100")]
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            r = review_portfolio(trades=rows, quotes=q)
        self.held_portfolio(r)
        self.assertEqual(r.reason, "SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")

    def test_exact_low_precision_portfolio_amounts_remain_nonoperational(self):
        q = portfolio_quotes()
        rows = [portfolio.Trade("candidate", "USD/JPY", "BUY",
                                "CANDIDATE", "1", "1")]
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            r = review_portfolio(trades=rows, quotes=q)
        self.held_portfolio(r, True)
        self.assertFalse(r.candidate_exceeds_existing_limit)

    def test_exact_low_precision_stop_amounts_remain_nonoperational(self):
        row = replace(stop_tickets()[0], additional_cost_jpy="0")
        with patch.object(stop, "Context", side_effect=weak_context(8)):
            r = review_stop(tickets=[row])
        self.held_stop(r, True)
        self.assertEqual(r.candidate_illustrative_loss_jpy, "500")

    def test_rounded_failure_exposes_no_partial_portfolio_legs(self):
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            r = review_portfolio()
        self.assertIsNone(r.gross_currency_legs_jpy)
        self.assertIsNone(r.gross_native)
        self.assertIsNone(r.net_native)
        self.assertIsNone(r.candidate_max_loss_jpy)
        self.assertIsNone(r.total_max_loss_jpy)
        self.held_portfolio(r)

    def test_rounded_failure_exposes_no_partial_stop_rows(self):
        with patch.object(stop, "Context", side_effect=weak_context(8)):
            r = review_stop(tickets=[stop_tickets()[0]])
        self.assertIsNone(r.per_ticket_illustrative_loss_jpy)
        self.assertIsNone(r.candidate_illustrative_loss_jpy)
        self.assertIsNone(r.total_illustrative_loss_jpy)
        self.held_stop(r)

    def test_rounded_failures_remain_no_go_with_hostile_parent_context(self):
        with localcontext() as ctx:
            ctx.prec = 3
            ctx.rounding = ROUND_DOWN
            with patch.object(portfolio, "Context", side_effect=weak_context(8)):
                rp = review_portfolio()
            with patch.object(stop, "Context", side_effect=weak_context(8)):
                rs = review_stop(tickets=[stop_tickets()[0]])
            self.assertEqual(ctx.prec, 3)
            self.assertEqual(ctx.rounding, ROUND_DOWN)
        self.held_portfolio(rp)
        self.held_stop(rs)

    def test_portfolio_invalid_quote_still_has_original_error_code(self):
        q = portfolio_quotes()
        q["EUR/JPY"] = replace(q["EUR/JPY"], ask="NaN")
        r = review_portfolio(quotes=q)
        self.assertEqual(r.reason, "INVALID_BID_ASK")
        self.held_portfolio(r)

    def test_stop_invalid_price_still_has_original_error_code(self):
        q = stop_quotes()
        q["EUR/JPY"] = replace(q["EUR/JPY"], bid="1e20")
        r = review_stop(quotes=q)
        self.assertEqual(r.reason, "INVALID_BID_ASK")
        self.held_stop(r)

    def test_portfolio_unreconciled_still_stops_before_arithmetic(self):
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            r = review_portfolio(reconciled=False)
        self.assertEqual(r.reason, "ACCOUNT_OR_PENDING_STATE_UNKNOWN")
        self.held_portfolio(r)

    def test_stop_unreconciled_still_stops_before_arithmetic(self):
        with patch.object(stop, "Context", side_effect=weak_context(8)):
            r = review_stop(reconciled=False)
        self.assertEqual(r.reason, "BROKER_OR_INFLIGHT_STATE_UNKNOWN")
        self.held_stop(r)

    def test_portfolio_correct_precision_constant_remains_256(self):
        self.assertEqual(portfolio.DECIMAL_WORK_PRECISION, 256)
        self.held_portfolio(review_portfolio(), True)

    def test_stop_correct_precision_constant_remains_96(self):
        self.assertEqual(stop.DECIMAL_WORK_PRECISION, 96)
        self.held_stop(review_stop(), True)

    def test_mock_three_pair_scope_unchanged(self):
        self.assertEqual(portfolio.PAIRS, stop.PAIRS)
        self.assertEqual(stop.PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))

    def test_rounding_result_contains_no_secret_or_input_echo(self):
        marker = "SYNTHETIC_PRIVATE_CANARY_133"
        rows = [replace(portfolio_records()[0], trade_id=marker)]
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            r = review_portfolio(trades=rows)
        self.held_portfolio(r)
        self.assertEqual(r.reason, "SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")
        self.assertNotIn(marker, repr(r))

    def test_rounding_does_not_change_global_decimal_precision(self):
        original = getcontext().copy()
        with patch.object(portfolio, "Context", side_effect=weak_context(8)):
            review_portfolio()
        with patch.object(stop, "Context", side_effect=weak_context(8)):
            review_stop(tickets=[stop_tickets()[0]])
        self.assertEqual(getcontext().prec, original.prec)
        self.assertEqual(getcontext().rounding, original.rounding)


if __name__ == "__main__":
    unittest.main()
