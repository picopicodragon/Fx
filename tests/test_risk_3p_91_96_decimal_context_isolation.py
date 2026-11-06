"""RISK-3P-91..96: ambient decimal context must never change mock risks.

All fixtures and 'reconciliation' booleans are fictional. This tests two
different arithmetic implementations, NOT two independent broker feeds.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import (Context, Decimal, Inexact, Overflow, ROUND_DOWN,
                     Rounded, getcontext, localcontext)
import unittest

from scripts import phase1_three_pair_synthetic_risk as portfolio
from scripts import phase1_three_pair_synthetic_stop_conversion as stop


def stop_contracts():
    return {pair: stop.Contract(pair, "100000", "0.01", "0.01", "1")
            for pair in stop.PAIRS}


def stop_quotes():
    return {
        "USD/JPY": stop.Quote("USD/JPY", "150", "151", 42, "fixture-1"),
        "EUR/JPY": stop.Quote("EUR/JPY", "181", "182", 42, "fixture-1"),
        "EUR/USD": stop.Quote("EUR/USD", "1.20", "1.21", 42, "fixture-1"),
    }


def stop_tickets():
    return [
        stop.Ticket("candidate", "EUR/USD", "BUY", "CANDIDATE",
                    "0.01", "1.2000", "1.1990", "0.0001", "5", "fixture-1"),
        stop.Ticket("position", "USD/JPY", "SELL", "POSITION",
                    "0.01", "150", "150.05", "0.01", "0", "fixture-1"),
        stop.Ticket("pending", "EUR/JPY", "BUY", "PENDING",
                    "0.01", "181", "180.9", "0.01", "0", "fixture-1"),
    ]


def stops(*, cs=None, qs=None, ts=None, equity="100000", pending=True):
    return stop.review_synthetic_stop_risk(
        stop_contracts() if cs is None else cs,
        stop_quotes() if qs is None else qs,
        stop_tickets() if ts is None else ts,
        equity_jpy=equity, asof=42, snapshot_id="fixture-1",
        positions_reconciled=True, pending_reconciled=pending,
        inflight_reservations_reconciled=True)


def portfolio_quotes():
    return {
        k: portfolio.Quote(v.pair, v.bid, v.ask, v.observed_at, v.snapshot_id)
        for k, v in stop_quotes().items()
    }


def portfolio_trades_from_stops(tickets=None, contracts=None, stop_result=None):
    ts = stop_tickets() if tickets is None else tickets
    cs = stop_contracts() if contracts is None else contracts
    result = stops(cs=cs, ts=ts) if stop_result is None else stop_result
    amounts = dict(result.per_ticket_illustrative_loss_jpy)
    with localcontext(Context(prec=96)):
        return [
            portfolio.Trade(t.ticket_id, t.pair, t.side, t.status,
                            str(Decimal(t.volume_lots) *
                                Decimal(cs[t.pair].base_units_per_lot)),
                            amounts[t.ticket_id])
            for t in ts
        ]


def portfolio_review(*, ts=None, q=None, equity="100000", pending=True):
    return portfolio.review_synthetic_portfolio(
        portfolio_quotes() if q is None else q,
        portfolio_trades_from_stops() if ts is None else ts,
        asof=42, snapshot_id="fixture-1", equity_jpy=equity,
        positions_reconciled=True, pending_orders_reconciled=pending)


def hostile_decimal_context():
    """Deliberately forbids precision loss and reduces default exponent range."""
    ctx = getcontext()
    ctx.prec = 3
    ctx.Emax = 9
    ctx.Emin = -9
    ctx.rounding = ROUND_DOWN
    ctx.clamp = 1
    ctx.traps[Inexact] = True
    ctx.traps[Rounded] = True
    ctx.traps[Overflow] = True


class DecimalContextIsolationTests(unittest.TestCase):
    def held_stop(self, result):
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertTrue(result.safety_hold_latched)
        self.assertFalse(result.order_allowed)
        self.assertFalse(result.result_authorizes_trade)
        self.assertFalse(result.stop_release_allowed)
        self.assertIsNone(result.verified_values)

    def held_portfolio(self, result):
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertTrue(result.safety_hold_latched)
        self.assertFalse(result.order_allowed)
        self.assertFalse(result.stop_release_allowed)
        self.assertIsNone(result.verified_values)

    def test_stop_default_fixture_unchanged_under_hostile_decimal_settings(self):
        regular = stops()
        with localcontext():
            hostile_decimal_context()
            altered = stops()
        self.assertEqual(altered, regular)
        self.assertTrue(altered.illustrative_complete)
        self.held_stop(altered)

    def test_portfolio_default_fixture_unchanged_under_hostile_settings(self):
        inputs = portfolio_trades_from_stops()
        regular = portfolio_review(ts=inputs)
        with localcontext():
            hostile_decimal_context()
            altered = portfolio_review(ts=inputs)
        self.assertEqual(altered, regular)
        self.assertTrue(altered.arithmetic_complete)
        self.held_portfolio(altered)

    def test_two_mock_calculators_agree_on_all_three_fictional_losses(self):
        first = stops()
        second = portfolio_review(
            ts=portfolio_trades_from_stops(stop_result=first))
        self.assertTrue(first.illustrative_complete)
        self.assertTrue(second.arithmetic_complete)
        self.assertEqual(first.candidate_illustrative_loss_jpy,
                         second.candidate_max_loss_jpy)
        self.assertEqual(first.total_illustrative_loss_jpy,
                         second.total_max_loss_jpy)
        self.assertEqual(first.candidate_exceeds_existing_fraction,
                         second.candidate_exceeds_existing_limit)
        self.assertEqual(first.aggregate_exceeds_existing_fraction,
                         second.total_exceeds_existing_limit)
        self.held_stop(first)
        self.held_portfolio(second)

    def test_cross_engine_consistency_under_low_precision_with_traps(self):
        expected = stops()
        t = portfolio_trades_from_stops(stop_result=expected)
        with localcontext():
            hostile_decimal_context()
            a = stops()
            b = portfolio_review(ts=t)
        self.assertEqual(a.total_illustrative_loss_jpy,
                         b.total_max_loss_jpy)
        self.assertEqual(a.candidate_illustrative_loss_jpy,
                         b.candidate_max_loss_jpy)
        self.assertEqual(Decimal(b.total_max_loss_jpy), Decimal("341.1"))
        self.held_stop(a)
        self.held_portfolio(b)

    def test_caller_context_is_not_modified_by_either_calculator(self):
        with localcontext() as ctx:
            hostile_decimal_context()
            before = (ctx.prec, ctx.Emax, ctx.Emin, ctx.rounding,
                      ctx.clamp, dict(ctx.traps))
            stops()
            portfolio_review(ts=portfolio_trades_from_stops())
            after = (ctx.prec, ctx.Emax, ctx.Emin, ctx.rounding,
                     ctx.clamp, dict(ctx.traps))
            self.assertEqual(after, before)
            self.assertEqual(ctx.prec, 3)
            self.assertTrue(ctx.traps[Inexact])
            self.assertEqual(ctx.Emax, 9)

    def test_hostile_caller_precision_does_not_round_half_percent_epsilon(self):
        ts = [
            portfolio.Trade("candidate", "USD/JPY", "BUY", "CANDIDATE",
                            "1", "500.00000000000000000000000000000000001")
        ]
        with localcontext():
            hostile_decimal_context()
            r = portfolio_review(ts=ts)
        self.assertTrue(r.arithmetic_complete)
        self.assertTrue(r.candidate_exceeds_existing_limit)
        self.assertEqual(
            r.candidate_max_loss_jpy,
            "500.00000000000000000000000000000000001")
        self.held_portfolio(r)

    def test_hostile_caller_precision_does_not_round_total_percent_epsilon(self):
        ts = [
            portfolio.Trade("candidate", "USD/JPY", "BUY",
                            "CANDIDATE", "1", "500"),
            portfolio.Trade("position", "EUR/JPY", "SELL",
                            "POSITION", "1",
                            "500.00000000000000000000000000000000001")
        ]
        with localcontext():
            hostile_decimal_context()
            r = portfolio_review(ts=ts)
        self.assertTrue(r.arithmetic_complete)
        self.assertTrue(r.total_exceeds_existing_limit)
        self.assertEqual(r.total_max_loss_jpy,
                         "1000.00000000000000000000000000000000001")
        self.held_portfolio(r)

    def test_stop_micro_cost_exceeds_exact_half_percent_under_hostile_context(self):
        ts = [
            stop.Ticket("candidate", "USD/JPY", "BUY", "CANDIDATE",
                        "0.01", "150.5", "150", "0", "0.000000000001",
                        "fixture-1")]
        with localcontext():
            hostile_decimal_context()
            r = stops(ts=ts)
        self.assertTrue(r.illustrative_complete)
        self.assertTrue(r.candidate_exceeds_existing_fraction)
        self.assertEqual(r.candidate_illustrative_loss_jpy,
                         "500.000000000001")
        self.held_stop(r)

    def test_stop_micro_cost_exceeds_total_percent_under_hostile_context(self):
        ts = [
            stop.Ticket("candidate", "USD/JPY", "BUY", "CANDIDATE",
                        "0.01", "150.5", "150", "0", "0", "fixture-1"),
            stop.Ticket("pending", "USD/JPY", "SELL", "PENDING",
                        "0.01", "150", "150.5", "0", "0.000000000001",
                        "fixture-1")]
        with localcontext():
            hostile_decimal_context()
            r = stops(ts=ts)
        self.assertTrue(r.aggregate_exceeds_existing_fraction)
        self.assertEqual(r.total_illustrative_loss_jpy,
                         "1000.000000000001")
        self.held_stop(r)

    def test_large_stop_multiplication_does_not_overflow_low_caller_emax(self):
        huge = "999999999999"
        cs = stop_contracts()
        cs["EUR/USD"] = stop.Contract("EUR/USD", huge, "0.01",
                                     "0.01", huge)
        qs = stop_quotes()
        qs["USD/JPY"] = replace(qs["USD/JPY"], bid=huge, ask=huge)
        ts = [stop.Ticket("candidate", "EUR/USD", "BUY", "CANDIDATE",
                          huge, huge, "1", "0", "0.000000000001",
                          "fixture-1")]
        with localcontext():
            hostile_decimal_context()
            r = stops(cs=cs, qs=qs, ts=ts, equity=huge)
        self.assertTrue(r.illustrative_complete)
        self.assertTrue(r.aggregate_exceeds_existing_fraction)
        self.assertTrue(r.total_illustrative_loss_jpy.endswith("000000000001"))
        self.held_stop(r)

    def test_large_portfolio_multiplication_does_not_overflow_caller_emax(self):
        big = "9" * 40
        q = portfolio_quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], bid=big, ask=big)
        ts = [portfolio.Trade("candidate", "USD/JPY", "BUY",
                              "CANDIDATE", big, "500")]
        with localcontext():
            hostile_decimal_context()
            r = portfolio_review(ts=ts, q=q)
        self.assertTrue(r.arithmetic_complete)
        self.assertGreater(len(dict(r.gross_native)["JPY"]), 50)
        self.held_portfolio(r)

    def test_rejected_portfolio_zero_loss_retains_no_go_with_hostile_context(self):
        ts = [portfolio.Trade("candidate", "EUR/USD", "BUY",
                              "CANDIDATE", "1", "0")]
        with localcontext():
            hostile_decimal_context()
            r = portfolio_review(ts=ts)
        self.assertFalse(r.arithmetic_complete)
        self.assertEqual(r.reason, "UNVERIFIABLE_SYNTHETIC_QUANTITY_OR_LOSS")
        self.held_portfolio(r)

    def test_rejected_stop_bad_contract_retains_no_go_with_hostile_context(self):
        cs = stop_contracts()
        cs["EUR/USD"] = replace(cs["EUR/USD"], lot_step="0")
        with localcontext():
            hostile_decimal_context()
            r = stops(cs=cs)
        self.assertFalse(r.illustrative_complete)
        self.assertEqual(r.reason, "CONTRACT_ATTRIBUTES_UNKNOWN")
        self.held_stop(r)

    def test_unreconciled_pending_never_becomes_allowed_from_decimal_settings(self):
        with localcontext():
            hostile_decimal_context()
            r1 = stops(pending=False)
            r2 = portfolio_review(pending=False)
        self.assertEqual(r1.reason, "BROKER_OR_INFLIGHT_STATE_UNKNOWN")
        self.assertEqual(r2.reason, "ACCOUNT_OR_PENDING_STATE_UNKNOWN")
        self.held_stop(r1)
        self.held_portfolio(r2)

    def test_pair_scope_does_not_change_with_caller_decimal_context(self):
        self.assertEqual(portfolio.PAIRS, stop.PAIRS)
        self.assertEqual(portfolio.PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))
        with localcontext():
            hostile_decimal_context()
            bad = portfolio_review(ts=[
                portfolio.Trade("candidate", "GBP/USD", "BUY",
                                "CANDIDATE", "1", "1")])
        self.assertEqual(bad.reason, "UNSUPPORTED_PAIR_SIDE_OR_STATUS")
        self.held_portfolio(bad)

    def test_trap_mutations_do_not_permit_any_trade(self):
        baseline = portfolio_trades_from_stops()
        for rounding in (ROUND_DOWN,):
            with self.subTest(rounding=rounding):
                with localcontext() as ctx:
                    hostile_decimal_context()
                    ctx.rounding = rounding
                    a = stops()
                    b = portfolio_review(ts=baseline)
                    self.held_stop(a)
                    self.held_portfolio(b)

    def test_explicit_context_precision_is_96_for_both(self):
        self.assertEqual(stop.DECIMAL_WORK_PRECISION, 96)
        self.assertEqual(portfolio.DECIMAL_WORK_PRECISION, 96)
        with localcontext() as ctx:
            hostile_decimal_context()
            a, b = stops(), portfolio_review()
            self.assertEqual(ctx.prec, 3)
        self.assertTrue(a.illustrative_complete)
        self.assertTrue(b.arithmetic_complete)

    def test_all_three_ticket_amounts_are_copied_not_revalidated_as_broker_truth(self):
        a = stops()
        transferred = portfolio_trades_from_stops(stop_result=a)
        self.assertEqual(len(transferred), 3)
        self.assertEqual(
            {t.trade_id for t in transferred},
            {"candidate", "position", "pending"})
        self.assertEqual(
            {t.status for t in transferred},
            {"CANDIDATE", "POSITION", "PENDING"})
        self.assertFalse(a.broker_contract_verified)
        self.assertFalse(a.stop_execution_guaranteed)
        b = portfolio_review(ts=transferred)
        self.assertTrue(b.arithmetic_complete)
        self.held_portfolio(b)

    def test_divergent_synthetic_assertion_is_not_a_broker_proof(self):
        base = portfolio_trades_from_stops()
        modified = [replace(base[0], max_loss_jpy="999")] + base[1:]
        result = portfolio_review(ts=modified)
        self.assertTrue(result.arithmetic_complete)
        self.assertNotEqual(result.candidate_max_loss_jpy,
                            stops().candidate_illustrative_loss_jpy)
        self.assertFalse(result.order_allowed)
        self.assertIsNone(result.verified_values)
        self.held_portfolio(result)


    def test_stop_mock_ticket_ids_with_newlines_or_controls_are_rejected(self):
        for value in ("ID\\nPRIVATE", "ID\\rPRIVATE", "ID\\tPRIVATE",
                      "ID\\x00PRIVATE", "ID\\x1bPRIVATE"):
            with self.subTest(value=repr(value)):
                tickets = stop_tickets()
                tickets[0] = replace(tickets[0], ticket_id=value)
                r = stops(ts=tickets)
                self.assertFalse(r.illustrative_complete)
                self.assertEqual(r.reason, "DUPLICATE_OR_MISSING_TICKET_ID")
                self.assertNotIn("PRIVATE", str(r))
                self.held_stop(r)

    def test_portfolio_mock_trade_ids_with_newlines_or_controls_rejected(self):
        for value in ("ID\\nPRIVATE", "ID\\rPRIVATE", "ID\\tPRIVATE",
                      "ID\\x00PRIVATE", "ID\\x1bPRIVATE"):
            with self.subTest(value=repr(value)):
                trades = portfolio_trades_from_stops()
                trades[0] = replace(trades[0], trade_id=value)
                r = portfolio_review(ts=trades)
                self.assertFalse(r.arithmetic_complete)
                self.assertEqual(r.reason, "DUPLICATE_OR_INVALID_TRADE_ID")
                self.assertNotIn("PRIVATE", str(r))
                self.held_portfolio(r)

    def test_unprintable_snapshot_identifiers_rejected_before_quote_data(self):
        for value in ("SIM\\nPRIVATE", "SIM\\rPRIVATE", "SIM\\x00PRIVATE"):
            with self.subTest(value=repr(value)):
                rs = stop.review_synthetic_stop_risk(
                    stop_contracts(), stop_quotes(), stop_tickets(),
                    equity_jpy="100000", asof=42, snapshot_id=value,
                    positions_reconciled=True, pending_reconciled=True,
                    inflight_reservations_reconciled=True)
                rp = portfolio.review_synthetic_portfolio(
                    portfolio_quotes(), portfolio_trades_from_stops(),
                    asof=42, snapshot_id=value, equity_jpy="100000",
                    positions_reconciled=True, pending_orders_reconciled=True)
                self.assertEqual(rs.reason, "MISSING_OR_INVALID_SNAPSHOT_IDENTITY")
                self.assertEqual(rp.reason, "INVALID_SYNTHETIC_SNAPSHOT_IDENTITY")
                self.held_stop(rs)
                self.held_portfolio(rp)

    def test_normal_mock_identifiers_remain_accepted(self):
        result = stops()
        self.assertTrue(result.illustrative_complete)
        trade = portfolio_trades_from_stops(stop_result=result)
        rp = portfolio_review(ts=trade)
        self.assertTrue(rp.arithmetic_complete)
        self.held_stop(result)
        self.held_portfolio(rp)


if __name__ == "__main__":
    unittest.main()
