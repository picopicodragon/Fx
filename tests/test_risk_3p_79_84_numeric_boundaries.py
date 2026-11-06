"""RISK-3P-79/84: high precision FX math remains illustrative and NO_GO.

No market, MT4, filesystem or account I/O.  The exact-boundary tests are
specifically designed to catch Decimal's default-precision rounding of a
positive loss just above the 0.5% or 1.0% ceilings.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, localcontext
import unittest

from scripts import phase1_three_pair_synthetic_risk as mod


def quotes(*, asof=123, snapshot_id="SIM-BOUNDARY"):
    return {
        "USD/JPY": mod.Quote("USD/JPY", "150", "150", asof, snapshot_id),
        "EUR/JPY": mod.Quote("EUR/JPY", "180", "180", asof, snapshot_id),
        "EUR/USD": mod.Quote("EUR/USD", "1.2", "1.2", asof, snapshot_id),
    }


def trades():
    return [
        mod.Trade("candidate", "EUR/USD", "BUY", "CANDIDATE", "1", "400"),
        mod.Trade("existing", "USD/JPY", "SELL", "POSITION", "1", "300"),
        mod.Trade("pending", "EUR/JPY", "BUY", "PENDING", "1", "200"),
    ]


def evaluate(*, q=None, t=None, asof=123, sid="SIM-BOUNDARY", equity="100000",
             positions=True, pending=True):
    return mod.review_synthetic_portfolio(
        quotes(asof=asof, snapshot_id=sid) if q is None else q,
        trades() if t is None else t, asof=asof, snapshot_id=sid,
        equity_jpy=equity, positions_reconciled=positions,
        pending_orders_reconciled=pending)


class NumericFailClosedTests(unittest.TestCase):
    def held(self, result):
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertTrue(result.safety_hold_latched)
        self.assertFalse(result.order_allowed)
        self.assertFalse(result.automatic_retry_allowed)
        self.assertFalse(result.stop_release_allowed)
        self.assertIsNone(result.verified_values)

    def test_base_triangular_example_still_is_no_go(self):
        r = evaluate()
        self.assertTrue(r.arithmetic_complete)
        self.assertEqual(r.total_max_loss_jpy, "900")
        self.assertEqual(r.candidate_max_loss_jpy, "400")
        self.held(r)

    def test_above_half_percent_by_tiny_fraction_is_not_rounded_down(self):
        tiny_excess = "500.00000000000000000000000000000000001"
        rows = [replace(trades()[0], max_loss_jpy=tiny_excess)]
        r = evaluate(t=rows)
        self.assertTrue(r.arithmetic_complete)
        self.assertTrue(r.candidate_exceeds_existing_limit)
        self.assertFalse(r.total_exceeds_existing_limit)
        self.assertEqual(Decimal(r.candidate_max_loss_jpy), Decimal(tiny_excess))
        self.assertEqual(r.reason, "EXISTING_HARD_LIMIT_OVER_IN_SYNTHETIC_INPUT")
        self.held(r)

    def test_above_one_percent_by_tiny_fraction_is_not_rounded_down(self):
        tiny_excess = "500.00000000000000000000000000000000001"
        rows = [replace(trades()[0], max_loss_jpy="500"),
                replace(trades()[1], max_loss_jpy=tiny_excess)]
        r = evaluate(t=rows)
        self.assertTrue(r.arithmetic_complete)
        self.assertFalse(r.candidate_exceeds_existing_limit)
        self.assertTrue(r.total_exceeds_existing_limit)
        self.assertEqual(Decimal(r.total_max_loss_jpy),
                         Decimal("1000.00000000000000000000000000000000001"))
        self.held(r)

    def test_exact_half_percent_and_one_percent_are_not_falsely_exceeded(self):
        rows = [replace(trades()[0], max_loss_jpy="500"),
                replace(trades()[1], max_loss_jpy="500")]
        r = evaluate(t=rows)
        self.assertTrue(r.arithmetic_complete)
        self.assertFalse(r.candidate_exceeds_existing_limit)
        self.assertFalse(r.total_exceeds_existing_limit)
        self.assertEqual(r.total_max_loss_jpy, "1000")
        self.held(r)

    def test_tiny_loss_below_limit_is_retained_exactly(self):
        original = "0.00000000000000000000000000000000001"
        r = evaluate(t=[replace(trades()[0], max_loss_jpy=original)])
        self.assertTrue(r.arithmetic_complete)
        self.assertFalse(r.candidate_exceeds_existing_limit)
        self.assertEqual(Decimal(r.candidate_max_loss_jpy), Decimal(original))
        self.held(r)

    def test_zero_max_loss_never_becomes_zero_risk_certification(self):
        for status in ("CANDIDATE", "POSITION", "PENDING"):
            with self.subTest(status=status):
                rows = [mod.Trade("candidate", "EUR/USD", "BUY",
                                  "CANDIDATE", "1", "100")]
                if status == "CANDIDATE":
                    rows[0] = replace(rows[0], max_loss_jpy="0")
                else:
                    rows.append(mod.Trade("other", "USD/JPY", "BUY",
                                          status, "1", "0"))
                r = evaluate(t=rows)
                self.assertEqual(
                    r.reason, "UNVERIFIABLE_SYNTHETIC_QUANTITY_OR_LOSS")
                self.assertFalse(r.arithmetic_complete)
                self.held(r)

    def test_more_than_128_records_rejected_before_arithmetic(self):
        values = [mod.Trade("new", "EUR/USD", "BUY",
                            "CANDIDATE", "1", "100")]
        values += [mod.Trade("old-" + str(i), "USD/JPY", "BUY",
                              "POSITION", "1", "1") for i in range(128)]
        r = evaluate(t=values)
        self.assertEqual(r.reason, "SYNTHETIC_WORKLOAD_BOUND_EXCEEDED")
        self.assertFalse(r.arithmetic_complete)
        self.held(r)

    def test_exactly_128_mock_records_can_be_evaluated(self):
        values = [mod.Trade("new", "EUR/USD", "BUY",
                            "CANDIDATE", "1", "100")]
        values += [mod.Trade("old-" + str(i), "USD/JPY", "BUY",
                              "POSITION", "1", "1") for i in range(127)]
        r = evaluate(t=values)
        self.assertTrue(r.arithmetic_complete)
        self.assertEqual(Decimal(r.total_max_loss_jpy), Decimal("227"))
        self.held(r)

    def test_trade_identifier_over_bounded_length_rejected(self):
        rows = trades()
        rows[0] = replace(rows[0], trade_id="X" * 129)
        r = evaluate(t=rows)
        self.assertEqual(r.reason, "DUPLICATE_OR_INVALID_TRADE_ID")
        self.held(r)

    def test_trade_identifier_at_exact_bound_supported_offline(self):
        rows = trades()
        rows[0] = replace(rows[0], trade_id="X" * 128)
        r = evaluate(t=rows)
        self.assertTrue(r.arithmetic_complete)
        self.held(r)

    def test_snapshot_identifier_too_long_fails_before_quote_access(self):
        sid = "SIM" * 43
        r = evaluate(sid=sid)
        self.assertGreater(len(sid), 128)
        self.assertEqual(r.reason, "INVALID_SYNTHETIC_SNAPSHOT_IDENTITY")
        self.held(r)

    def test_snapshot_identifier_at_exact_bound_is_allowed_offline(self):
        sid = "A" * 128
        r = evaluate(sid=sid)
        self.assertTrue(r.arithmetic_complete)
        self.held(r)

    def test_asof_outside_signed_64bit_range_rejected(self):
        for value in (-1, mod.MAX_SYNTHETIC_ASOF + 1, True, "123"):
            with self.subTest(value=value):
                r = evaluate(asof=value)
                self.assertEqual(r.reason,
                                 "INVALID_SYNTHETIC_SNAPSHOT_IDENTITY")
                self.held(r)

    def test_asof_at_exact_maximum_supported_for_fake_snapshots(self):
        r = evaluate(asof=mod.MAX_SYNTHETIC_ASOF)
        self.assertTrue(r.arithmetic_complete)
        self.held(r)

    def test_missing_or_unreconciled_state_stays_fail_closed(self):
        for kwargs in ({"positions": False}, {"pending": False}):
            with self.subTest(kwargs=kwargs):
                r = evaluate(**kwargs)
                self.assertEqual(r.reason, "ACCOUNT_OR_PENDING_STATE_UNKNOWN")
                self.held(r)

    def test_long_numeric_string_is_rejected_without_float_coercion(self):
        rows = trades()
        rows[0] = replace(rows[0], max_loss_jpy="9" * 41)
        r = evaluate(t=rows)
        self.assertEqual(
            r.reason, "UNVERIFIABLE_SYNTHETIC_QUANTITY_OR_LOSS")
        self.held(r)

    def test_large_decimal_multiplication_retains_native_gross(self):
        # At most 40 input digits each; 96-digit internal context leaves
        # ample room for an 80-digit product and 128-entry accumulation.
        max40 = "9" * 40
        q = quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], bid=max40, ask=max40)
        r = evaluate(q=q, t=[
            mod.Trade("new", "USD/JPY", "BUY",
                      "CANDIDATE", max40, "1")],
            equity=max40)
        self.assertTrue(r.arithmetic_complete)
        with localcontext() as ctx:
            ctx.prec = mod.DECIMAL_WORK_PRECISION
            self.assertEqual(Decimal(dict(r.gross_native)["JPY"]),
                             Decimal(max40) * Decimal(max40))
        self.held(r)

    def test_current_three_pairs_remain_only_scope(self):
        self.assertEqual(mod.PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))
        for bad in ("GBP/USD", "AUD/USD"):
            rows = trades()
            rows[0] = replace(rows[0], pair=bad)
            r = evaluate(t=rows)
            self.assertEqual(r.reason, "UNSUPPORTED_PAIR_SIDE_OR_STATUS")
            self.held(r)

    def test_no_real_trading_permission_from_boundary_success(self):
        self.assertEqual(mod.DECIMAL_WORK_PRECISION, 96)
        self.assertEqual(mod.MAX_SYNTHETIC_TRADES, 128)
        r = evaluate()
        self.assertTrue(r.arithmetic_complete)
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertFalse(r.order_allowed)
        self.assertIsNone(r.verified_values)


if __name__ == "__main__":
    unittest.main()
