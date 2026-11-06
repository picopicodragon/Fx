"""RISK-3P-109..114: exact rational oracle for three-factor mock FX gross.

These are artificial extreme values, not permissible trade sizes or prices.
No MT4, broker, network, files, orders, runtime permission, or real account.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Context, Decimal, Inexact, Rounded, Overflow, ROUND_DOWN
from decimal import localcontext
from fractions import Fraction
from itertools import product
import unittest

from scripts import phase1_three_pair_synthetic_risk as pf
from scripts import phase1_three_pair_synthetic_stop_conversion as sl


BIG = "9" * 40
TINY = "0." + "0" * 37 + "1"  # smallest positive 40-character string
SID = "SIM-EXPOSURE-109"
ASOF = 109
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
CURRENCIES = ("USD", "EUR", "JPY")


def prices(usd=BIG, eur=BIG, cross=BIG):
    return {
        "USD/JPY": pf.Quote("USD/JPY", usd, usd, ASOF, SID),
        "EUR/JPY": pf.Quote("EUR/JPY", eur, eur, ASOF, SID),
        "EUR/USD": pf.Quote("EUR/USD", cross, cross, ASOF, SID),
    }


def ticket(pair="EUR/USD", side="BUY", units=BIG, loss="1",
           status="CANDIDATE", ident="candidate"):
    return pf.Trade(ident, pair, side, status, units, loss)


def evaluate(trades, q=None, *, equity="100000", reconciled=True):
    return pf.review_synthetic_portfolio(
        prices() if q is None else q, trades, asof=ASOF,
        snapshot_id=SID, equity_jpy=equity,
        positions_reconciled=reconciled,
        pending_orders_reconciled=reconciled)


def num(text):
    return Fraction(Decimal(text))


def oracle(trades, quotes):
    """Independent exact rational gross/net semantics, no Decimal math."""
    net = {x: Fraction(0) for x in CURRENCIES}
    gross = {x: Fraction(0) for x in CURRENCIES}
    candidate = total = Fraction(0)
    for t in trades:
        base, quote = t.pair.split("/")
        sign = 1 if t.side == "BUY" else -1
        units = num(t.base_units)
        price = num(quotes[t.pair].ask if sign == 1
                    else quotes[t.pair].bid)
        for c, v in ((base, sign * units),
                     (quote, -sign * units * price)):
            net[c] += v
            gross[c] += abs(v)
        amount = num(t.max_loss_jpy)
        total += amount
        if t.status == "CANDIDATE":
            candidate += amount
    converted = (gross["JPY"] + gross["USD"] * num(quotes["USD/JPY"].ask)
                 + gross["EUR"] * num(quotes["EUR/JPY"].ask))
    return net, gross, converted, candidate, total


class GrossExactnessTests(unittest.TestCase):
    def held(self, result):
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertTrue(result.safety_hold_latched)
        self.assertFalse(result.order_allowed)
        self.assertFalse(result.stop_release_allowed)
        self.assertFalse(result.automatic_retry_allowed)
        self.assertIsNone(result.verified_values)

    def matched(self, rows, q=None, *, equity="100000"):
        q = prices() if q is None else q
        result = evaluate(rows, q=q, equity=equity)
        self.assertTrue(result.arithmetic_complete, result)
        net, gross, jpy, candidate, total = oracle(rows, q)
        self.assertEqual(tuple(x for x, _ in result.net_native), CURRENCIES)
        self.assertEqual(tuple(x for x, _ in result.gross_native), CURRENCIES)
        for key, value in result.net_native:
            self.assertEqual(num(value), net[key])
        for key, value in result.gross_native:
            self.assertEqual(num(value), gross[key])
        self.assertEqual(num(result.gross_currency_legs_jpy), jpy)
        self.assertEqual(num(result.candidate_max_loss_jpy), candidate)
        self.assertEqual(num(result.total_max_loss_jpy), total)
        self.assertIs(result.candidate_exceeds_existing_limit,
                      candidate > num(equity) / 200)
        self.assertIs(result.total_exceeds_existing_limit,
                      total > num(equity) / 100)
        self.held(result)
        return result

    def test_40_digit_eur_usd_quantity_times_two_40_digit_rates_is_exact(self):
        rows = [ticket()]
        result = self.matched(rows)
        b = int(BIG)
        self.assertEqual(int(Decimal(result.gross_currency_legs_jpy)),
                         b ** 3 + b ** 2)
        self.assertEqual(num(dict(result.gross_native)["USD"]), b ** 2)
        self.assertGreater(len(str(int(Decimal(
            result.gross_currency_legs_jpy)))), 100)

    def test_historical_96_digit_context_did_round_triple_product(self):
        with localcontext(Context(prec=96)):
            old = Decimal(BIG) * Decimal(BIG) * Decimal(BIG)
        self.assertNotEqual(old, Decimal(int(BIG) ** 3))
        self.assertEqual(pf.DECIMAL_WORK_PRECISION, 256)

    def test_40_digit_ask_conversion_exact_for_both_directions(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.matched([ticket(side=side)])

    def test_jpy_quoted_pair_exposure_exact_for_both_directions(self):
        for pair, side in product(("USD/JPY", "EUR/JPY"),
                                  ("BUY", "SELL")):
            with self.subTest(pair=pair, side=side):
                self.matched([ticket(pair=pair, side=side)])

    def test_mixed_three_pair_native_legs_and_jpy_gross_have_no_rounding(self):
        rows = [
            ticket("EUR/USD", "BUY", BIG, "300", "CANDIDATE", "c"),
            ticket("USD/JPY", "SELL", BIG, "200", "POSITION", "o"),
            ticket("EUR/JPY", "BUY", BIG, "100", "PENDING", "p"),
        ]
        self.matched(rows)

    def test_40_digit_large_position_preserves_additional_micro_position(self):
        rows = [ticket()]
        rows.append(ticket("EUR/USD", "SELL", TINY, TINY, "PENDING", "tiny"))
        r = self.matched(rows)
        net, gross, jpy, _, _ = oracle(rows, prices())
        self.assertEqual(num(dict(r.net_native)["EUR"]), net["EUR"])
        self.assertEqual(num(r.gross_currency_legs_jpy), jpy)
        self.assertGreater(gross["EUR"], num(BIG))

    def test_128_positions_include_all_microtails_exactly_in_gross_and_net(self):
        rows = [ticket()]
        for i in range(127):
            rows.append(ticket("EUR/USD", "SELL" if i % 2 else "BUY",
                               TINY, TINY, "PENDING" if i % 2
                               else "POSITION", f"p-{i}"))
        r = self.matched(rows)
        self.assertTrue(r.arithmetic_complete)
        self.assertEqual(len(rows), 128)
        self.assertGreater(num(r.total_max_loss_jpy), Fraction(1))

    def test_more_than_128_positions_are_rejected_before_arithmetic(self):
        rows = [ticket()] + [
            ticket("EUR/USD", "BUY", TINY, "1", "POSITION", f"x{i}")
            for i in range(128)
        ]
        r = evaluate(rows)
        self.assertEqual(r.reason, "SYNTHETIC_WORKLOAD_BOUND_EXCEEDED")
        self.assertFalse(r.arithmetic_complete)
        self.held(r)

    def test_128_large_40_digit_gross_exposures_are_exact(self):
        rows = [ticket()]
        for i in range(127):
            rows.append(ticket("EUR/USD", "SELL" if i % 2 else "BUY",
                               BIG, "1", "POSITION", f"e{i}"))
        self.matched(rows)

    def test_128_mixed_three_pair_gross_exposure_is_exact(self):
        rows = [ticket()]
        for i in range(127):
            pair = PAIRS[i % 3]
            side = "BUY" if i % 2 else "SELL"
            units = BIG if i % 4 else TINY
            rows.append(ticket(pair, side, units, TINY,
                               "POSITION" if i % 2 else "PENDING", f"m{i}"))
        self.matched(rows)

    def test_very_small_input_only_preserves_rational_valuation(self):
        self.matched([ticket(units=TINY, loss=TINY)])

    def test_spread_bid_and_ask_affect_sign_correctly(self):
        q = prices()
        q["EUR/USD"] = replace(q["EUR/USD"], bid="8" * 40, ask=BIG)
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.matched([ticket(side=side)], q=q)

    def test_small_cross_rate_and_large_usd_conversion_are_exact(self):
        q = prices(cross=TINY)
        self.matched([ticket()], q=q)

    def test_tiny_usd_jpy_rate_and_large_eur_usd_are_exact(self):
        q = prices(usd=TINY)
        self.matched([ticket()], q=q)

    def test_small_eur_jpy_and_large_eur_usd_are_exact(self):
        q = prices(eur=TINY)
        self.matched([ticket()], q=q)

    def test_hostile_external_decimal_context_cannot_round_256_digit_gross(self):
        rows = [ticket(), ticket("EUR/USD", "SELL", TINY, TINY,
                                 "PENDING", "tail")]
        reference = self.matched(rows)
        with localcontext() as ctx:
            ctx.prec = 3
            ctx.Emax = 9
            ctx.Emin = -9
            ctx.rounding = ROUND_DOWN
            ctx.traps[Inexact] = True
            ctx.traps[Rounded] = True
            ctx.traps[Overflow] = True
            calculated = self.matched(rows)
            self.assertEqual(ctx.prec, 3)
        self.assertEqual(calculated, reference)

    def test_hard_limit_fraction_comparison_still_detects_tiny_excess(self):
        rows = [ticket(units=TINY,
                       loss="500.00000000000000000000000000000000001")]
        r = self.matched(rows)
        self.assertTrue(r.candidate_exceeds_existing_limit)
        self.held(r)

    def test_pending_risk_is_not_netted_against_position_loss(self):
        rows = [ticket(loss="500")]
        rows.append(ticket("EUR/USD", "SELL", TINY,
                           "500.00000000000000000000000000000000001",
                           "PENDING", "pending"))
        r = self.matched(rows)
        self.assertTrue(r.total_exceeds_existing_limit)

    def test_equal_boundary_remains_allowed_arithmetic_but_not_trading(self):
        rows = [ticket(loss="500")]
        rows.append(ticket("EUR/USD", "SELL", TINY, "500",
                           "PENDING", "pending"))
        r = self.matched(rows)
        self.assertFalse(r.candidate_exceeds_existing_limit)
        self.assertFalse(r.total_exceeds_existing_limit)
        self.held(r)

    def test_nonprintable_identifier_is_rejected_without_leaking_content(self):
        rows = [replace(ticket(), trade_id="s" + chr(10) + "PRIVATE")]
        r = evaluate(rows)
        self.assertEqual(r.reason, "DUPLICATE_OR_INVALID_TRADE_ID")
        self.assertFalse(r.arithmetic_complete)
        self.assertNotIn("PRIVATE", str(r))
        self.held(r)

    def test_bad_decimal_inputs_rejected_without_order_authorization(self):
        for x in ("NaN", "Infinity", "1e40", "-1", "0", "9" * 41):
            with self.subTest(x=x):
                r = evaluate([ticket(units=x)])
                self.assertEqual(r.reason,
                                 "UNVERIFIABLE_SYNTHETIC_QUANTITY_OR_LOSS")
                self.held(r)

    def test_unreconciled_order_state_always_returns_no_go(self):
        r = evaluate([ticket()], reconciled=False)
        self.assertEqual(r.reason, "ACCOUNT_OR_PENDING_STATE_UNKNOWN")
        self.held(r)

    def test_3pair_scope_and_distinct_pure_stop_budget_remain_unchanged(self):
        self.assertEqual(pf.PAIRS, PAIRS)
        self.assertEqual(sl.PAIRS, PAIRS)
        self.assertEqual(pf.DECIMAL_WORK_PRECISION, 256)
        self.assertEqual(sl.DECIMAL_WORK_PRECISION, 96)
        r = evaluate([ticket(pair="GBP/USD")])
        self.assertEqual(r.reason, "UNSUPPORTED_PAIR_SIDE_OR_STATUS")
        self.held(r)


if __name__ == "__main__":
    unittest.main()
