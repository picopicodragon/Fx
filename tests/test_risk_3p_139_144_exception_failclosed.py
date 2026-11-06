"""RISK-3P-139..144: synthetic arithmetic exceptions must return NO_GO.

Fixtures are entirely invented, not live rates, Rakuten MT4 or real
positions. Python Decimal traps and deliberately raised exceptions test
the fail-closed boundary without changing any trading permission.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Context as DecimalContext, Inexact, InvalidOperation
from decimal import Overflow, Rounded, getcontext, localcontext
from unittest.mock import patch
import unittest

from scripts import phase1_three_pair_synthetic_risk as pf
from scripts import phase1_three_pair_synthetic_stop_conversion as sl


ASOF = 139
SID = "SIM-P139"
BIG = "999999999999"
BIG40 = "9" * 40


def portfolio_quotes():
    return {
        "USD/JPY": pf.Quote("USD/JPY", "150", "151", ASOF, SID),
        "EUR/JPY": pf.Quote("EUR/JPY", "180", "181", ASOF, SID),
        "EUR/USD": pf.Quote("EUR/USD", "1.20", "1.21", ASOF, SID),
    }


def portfolio_rows():
    return [pf.Trade("candidate", "EUR/USD", "BUY",
                     "CANDIDATE", "1000", "500.000000000001")]


def portfolio_run(*, q=None, ts=None, reconciled=True):
    return pf.review_synthetic_portfolio(
        portfolio_quotes() if q is None else q,
        portfolio_rows() if ts is None else ts,
        asof=ASOF, snapshot_id=SID, equity_jpy="100000",
        positions_reconciled=reconciled,
        pending_orders_reconciled=reconciled)


def contracts():
    return {pair: sl.Contract(pair, "100000", "0.01", "0.01", "1")
            for pair in sl.PAIRS}


def stop_quotes():
    return {
        "USD/JPY": sl.Quote("USD/JPY", "150", "151", ASOF, SID),
        "EUR/JPY": sl.Quote("EUR/JPY", "180", "181", ASOF, SID),
        "EUR/USD": sl.Quote("EUR/USD", "1.20", "1.21", ASOF, SID),
    }


def stops():
    return [sl.Ticket("candidate", "USD/JPY", "BUY", "CANDIDATE",
                      "0.01", "150.5", "150", "0", "0.000000000001", SID)]


def stop_run(*, cs=None, qs=None, ts=None, reconciled=True):
    return sl.review_synthetic_stop_risk(
        contracts() if cs is None else cs,
        stop_quotes() if qs is None else qs,
        stops() if ts is None else ts,
        equity_jpy="100000", asof=ASOF, snapshot_id=SID,
        positions_reconciled=reconciled,
        pending_reconciled=reconciled,
        inflight_reservations_reconciled=reconciled)


def low_exponent_context(**_ignored):
    return DecimalContext(prec=16, Emax=9, Emin=-9)


def forbidden_exactness_context(**_ignored):
    ctx = DecimalContext(prec=8)
    ctx.traps[Inexact] = True
    ctx.traps[Rounded] = True
    return ctx


class ArithmeticExceptionFailClosedTests(unittest.TestCase):
    def assert_held(self, outcome, *, complete=False):
        self.assertEqual(outcome.runtime_go_no_go, "NO_GO")
        self.assertEqual(outcome.phase_1, "BLOCKED")
        self.assertTrue(outcome.safety_hold_latched)
        self.assertFalse(outcome.order_allowed)
        self.assertFalse(outcome.automatic_retry_allowed)
        self.assertFalse(outcome.stop_release_allowed)
        self.assertIsNone(outcome.verified_values)
        if type(outcome) is pf.Review:
            self.assertIs(outcome.arithmetic_complete, complete)
            if not complete:
                self.assertIsNone(outcome.total_max_loss_jpy)
                self.assertIsNone(outcome.net_native)
                self.assertIsNone(outcome.gross_native)
        elif type(outcome) is sl.Review:
            self.assertIs(outcome.illustrative_complete, complete)
            self.assertFalse(outcome.result_authorizes_trade)
            self.assertFalse(outcome.stop_execution_guaranteed)
            self.assertFalse(outcome.broker_contract_verified)
            if not complete:
                self.assertIsNone(outcome.total_illustrative_loss_jpy)
                self.assertIsNone(outcome.per_ticket_illustrative_loss_jpy)
        else:
            self.fail("unexpected mock result type")

    def assert_exception_rejected(self, outcome):
        self.assertEqual(outcome.reason,
                         "SYNTHETIC_ARITHMETIC_EXCEPTION_FAIL_CLOSED")
        self.assert_held(outcome)

    def test_portfolio_baseline_exact_still_no_go(self):
        result = portfolio_run()
        self.assert_held(result, complete=True)
        self.assertTrue(result.candidate_exceeds_existing_limit)

    def test_stop_baseline_exact_still_no_go(self):
        result = stop_run()
        self.assert_held(result, complete=True)
        self.assertTrue(result.candidate_exceeds_existing_fraction)

    def test_portfolio_injected_decimal_overflow_fails_closed(self):
        q = portfolio_quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], bid=BIG40, ask=BIG40)
        q["EUR/USD"] = replace(q["EUR/USD"], bid=BIG40, ask=BIG40)
        rows = [pf.Trade("candidate", "EUR/USD", "BUY", "CANDIDATE",
                         BIG40, "500")]
        with patch.object(pf, "Context", side_effect=low_exponent_context):
            result = portfolio_run(q=q, ts=rows)
        self.assert_exception_rejected(result)

    def test_stop_injected_decimal_overflow_fails_closed(self):
        c = contracts()
        c["EUR/USD"] = sl.Contract("EUR/USD", BIG, "0.01", "0.01", BIG)
        q = stop_quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], bid=BIG, ask=BIG)
        rows = [sl.Ticket("candidate", "EUR/USD", "BUY", "CANDIDATE",
                          BIG, BIG, "1", "0", "0", SID)]
        with patch.object(sl, "Context", side_effect=low_exponent_context):
            result = stop_run(cs=c, qs=q, ts=rows)
        self.assert_exception_rejected(result)

    def test_portfolio_injected_inexact_trap_fails_closed(self):
        with patch.object(pf, "Context", side_effect=forbidden_exactness_context):
            result = portfolio_run()
        self.assert_exception_rejected(result)

    def test_stop_injected_inexact_trap_fails_closed(self):
        with patch.object(sl, "Context", side_effect=forbidden_exactness_context):
            result = stop_run()
        self.assert_exception_rejected(result)

    def test_portfolio_internal_invalid_operation_fails_closed(self):
        with patch.object(pf, "_review_synthetic_portfolio_impl",
                          side_effect=InvalidOperation("PRIVATE_CANARY_139")):
            result = portfolio_run()
        self.assert_exception_rejected(result)
        self.assertNotIn("PRIVATE_CANARY_139", repr(result))

    def test_stop_internal_invalid_operation_fails_closed(self):
        with patch.object(sl, "_review_synthetic_stop_risk_impl",
                          side_effect=InvalidOperation("PRIVATE_CANARY_139")):
            result = stop_run()
        self.assert_exception_rejected(result)
        self.assertNotIn("PRIVATE_CANARY_139", repr(result))

    def test_portfolio_unexpected_type_error_fails_closed(self):
        with patch.object(pf, "_review_synthetic_portfolio_impl",
                          side_effect=TypeError("PRIVATE_CANARY_139")):
            self.assert_exception_rejected(portfolio_run())

    def test_stop_unexpected_type_error_fails_closed(self):
        with patch.object(sl, "_review_synthetic_stop_risk_impl",
                          side_effect=TypeError("PRIVATE_CANARY_139")):
            self.assert_exception_rejected(stop_run())

    def test_portfolio_unexpected_runtime_error_fails_closed(self):
        with patch.object(pf, "_review_synthetic_portfolio_impl",
                          side_effect=RuntimeError("PRIVATE_CANARY_139")):
            self.assert_exception_rejected(portfolio_run())

    def test_stop_unexpected_runtime_error_fails_closed(self):
        with patch.object(sl, "_review_synthetic_stop_risk_impl",
                          side_effect=RuntimeError("PRIVATE_CANARY_139")):
            self.assert_exception_rejected(stop_run())

    def test_portfolio_system_exit_not_swallowed(self):
        with patch.object(pf, "_review_synthetic_portfolio_impl",
                          side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                portfolio_run()

    def test_stop_system_exit_not_swallowed(self):
        with patch.object(sl, "_review_synthetic_stop_risk_impl",
                          side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                stop_run()

    def test_portfolio_unknown_reconciliation_has_original_code(self):
        result = portfolio_run(reconciled=False)
        self.assertEqual(result.reason, "ACCOUNT_OR_PENDING_STATE_UNKNOWN")
        self.assert_held(result)

    def test_stop_unknown_reconciliation_has_original_code(self):
        result = stop_run(reconciled=False)
        self.assertEqual(result.reason, "BROKER_OR_INFLIGHT_STATE_UNKNOWN")
        self.assert_held(result)

    def test_portfolio_malformed_quote_keeps_existing_code(self):
        q = portfolio_quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], bid="NaN")
        result = portfolio_run(q=q)
        self.assertEqual(result.reason, "INVALID_BID_ASK")
        self.assert_held(result)

    def test_stop_malformed_quote_keeps_existing_code(self):
        q = stop_quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], bid="NaN")
        result = stop_run(qs=q)
        self.assertEqual(result.reason, "INVALID_BID_ASK")
        self.assert_held(result)

    def test_no_traps_or_context_leaks_to_caller(self):
        with localcontext() as caller:
            before = (caller.prec, caller.Emax, caller.Emin,
                      caller.rounding, dict(caller.traps))
            with patch.object(pf, "Context", side_effect=low_exponent_context):
                portfolio_run()
            with patch.object(sl, "Context", side_effect=low_exponent_context):
                stop_run()
            after = (caller.prec, caller.Emax, caller.Emin,
                     caller.rounding, dict(caller.traps))
            self.assertEqual(after, before)

    def test_both_engines_keep_risk_limit_percentages_unchanged(self):
        self.assertEqual(pf.PAIRS, sl.PAIRS)
        self.assertEqual(pf.PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))
        self.assertEqual(pf.DECIMAL_WORK_PRECISION, 256)
        self.assertEqual(sl.DECIMAL_WORK_PRECISION, 96)
        self.assertEqual(sl.SYNTHETIC_TRADE_LIMIT, sl.Decimal("0.005"))
        self.assertEqual(sl.SYNTHETIC_AGGREGATE_LIMIT, sl.Decimal("0.01"))

    def test_recovered_regular_portfolio_after_exception(self):
        with patch.object(pf, "_review_synthetic_portfolio_impl",
                          side_effect=Overflow("PRIVATE_CANARY_139")):
            self.assert_exception_rejected(portfolio_run())
        result = portfolio_run()
        self.assert_held(result, complete=True)

    def test_recovered_regular_stop_after_exception(self):
        with patch.object(sl, "_review_synthetic_stop_risk_impl",
                          side_effect=Overflow("PRIVATE_CANARY_139")):
            self.assert_exception_rejected(stop_run())
        result = stop_run()
        self.assert_held(result, complete=True)

    def test_automatic_authorization_impossible_on_any_mock_failure(self):
        for module, method, invoke in (
                (pf, "_review_synthetic_portfolio_impl", portfolio_run),
                (sl, "_review_synthetic_stop_risk_impl", stop_run)):
            for exc in (ArithmeticError, ValueError, TypeError, RuntimeError):
                with self.subTest(method=method, exc=exc):
                    with patch.object(module, method, side_effect=exc("SECRET")):
                        result = invoke()
                    self.assert_exception_rejected(result)
                    self.assertFalse(result.order_allowed)
                    self.assertFalse(result.stop_release_allowed)

    def test_stop_no_illusory_broker_or_cost_verification(self):
        result = stop_run()
        self.assertFalse(result.broker_contract_verified)
        self.assertFalse(result.costs_verified)
        self.assertEqual(result.quote_conversion_method,
                         "UNAPPROVED_SYNTHETIC_ONLY")
        self.assert_held(result, complete=True)


if __name__ == "__main__":
    unittest.main()
