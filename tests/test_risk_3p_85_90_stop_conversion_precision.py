"""RISK-3P-85..90: only fictional three-pair stop and JPY arithmetic.

No broker, market, MT4, EA or real stop-loss proof. Any numeric success
must retain BLOCKED/NO_GO and disallow orders/stop release.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, getcontext, localcontext
import unittest

from scripts import phase1_three_pair_synthetic_stop_conversion as mod
def contracts():
    return {pair: mod.Contract(pair, "100000", "0.01", "0.01", "1")
            for pair in mod.PAIRS}


def quotes():
    return {
        "USD/JPY": mod.Quote("USD/JPY", "150", "151", 42, "fixture-1"),
        "EUR/JPY": mod.Quote("EUR/JPY", "181", "182", 42, "fixture-1"),
        "EUR/USD": mod.Quote("EUR/USD", "1.20", "1.21", 42, "fixture-1"),
    }


def tickets():
    return [
        mod.Ticket("candidate", "EUR/USD", "BUY", "CANDIDATE",
                   "0.01", "1.2000", "1.1990", "0.0001", "5", "fixture-1"),
        mod.Ticket("position", "USD/JPY", "SELL", "POSITION",
                   "0.01", "150", "150.05", "0.01", "0", "fixture-1"),
        mod.Ticket("pending", "EUR/JPY", "BUY", "PENDING",
                   "0.01", "181", "180.9", "0.01", "0", "fixture-1"),
    ]


def review(*, cs=None, qs=None, ts=None, equity="100000", asof=42,
           sid="fixture-1", positions=True, pending=True, inflight=True):
    return mod.review_synthetic_stop_risk(
        contracts() if cs is None else cs,
        quotes() if qs is None else qs,
        tickets() if ts is None else ts,
        equity_jpy=equity, asof=asof, snapshot_id=sid,
        positions_reconciled=positions,
        pending_reconciled=pending,
        inflight_reservations_reconciled=inflight,
    )


def jpy_ticket(cost="0", *, ticket_id="c", status="CANDIDATE",
               volume="0.01", entry="150.5", stop="150"):
    return mod.Ticket(ticket_id, "USD/JPY", "BUY", status,
                      volume, entry, stop, "0", cost, "fixture-1")


class StopConversionPrecisionTests(unittest.TestCase):
    def held(self, r):
        self.assertIs(type(r), mod.Review)
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.result_authorizes_trade)
        self.assertFalse(r.stop_release_allowed)
        self.assertFalse(r.automatic_retry_allowed)
        self.assertFalse(r.broker_contract_verified)
        self.assertFalse(r.stop_execution_guaranteed)
        self.assertIsNone(r.verified_values)

    def test_old_three_pair_example_retains_original_mock_results(self):
        r = review()
        self.assertTrue(r.illustrative_complete)
        self.assertEqual(Decimal(r.total_illustrative_loss_jpy),
                         Decimal("341.1"))
        self.assertEqual(Decimal(r.candidate_illustrative_loss_jpy),
                         Decimal("171.1"))
        self.held(r)

    def test_large_four_factor_product_does_not_erase_sub_yen_cost(self):
        max_value = "999999999999"
        cs = contracts()
        cs["EUR/USD"] = mod.Contract("EUR/USD", max_value,
                                     "0.01", "0.01", max_value)
        qs = quotes()
        qs["USD/JPY"] = replace(qs["USD/JPY"],
                                bid=max_value, ask=max_value)
        tiny = "0.000000000001"
        ts = [mod.Ticket("c", "EUR/USD", "BUY", "CANDIDATE",
                         max_value, max_value, "1", "0", tiny, "fixture-1")]
        r = review(cs=cs, qs=qs, ts=ts)
        self.assertTrue(r.illustrative_complete)
        with localcontext() as ctx:
            ctx.prec = mod.DECIMAL_WORK_PRECISION
            expected = ((Decimal(max_value) - Decimal("1"))
                        * Decimal(max_value) ** 3 + Decimal(tiny))
        self.assertEqual(Decimal(r.candidate_illustrative_loss_jpy),
                         expected)
        self.assertTrue(r.candidate_illustrative_loss_jpy.endswith("000000000001"))
        self.assertTrue(r.candidate_exceeds_existing_fraction)
        self.assertTrue(r.aggregate_exceeds_existing_fraction)
        self.held(r)

    def test_500_boundary_stays_strict_for_small_additional_cost(self):
        base = [jpy_ticket()]
        exact = review(ts=base)
        self.assertTrue(exact.illustrative_complete)
        self.assertEqual(Decimal(exact.candidate_illustrative_loss_jpy),
                         Decimal("500"))
        self.assertFalse(exact.candidate_exceeds_existing_fraction)
        over = review(ts=[jpy_ticket("0.000000000001")])
        self.assertEqual(Decimal(over.candidate_illustrative_loss_jpy),
                         Decimal("500.000000000001"))
        self.assertTrue(over.candidate_exceeds_existing_fraction)
        self.assertFalse(over.aggregate_exceeds_existing_fraction)
        self.held(exact)
        self.held(over)

    def test_1000_boundary_stays_strict_for_pending_risk(self):
        rows = [
            jpy_ticket(),
            mod.Ticket("p", "USD/JPY", "SELL", "PENDING", "0.01",
                       "150", "150.5", "0", "0", "fixture-1"),
        ]
        exact = review(ts=rows)
        self.assertEqual(Decimal(exact.total_illustrative_loss_jpy),
                         Decimal("1000"))
        self.assertFalse(exact.aggregate_exceeds_existing_fraction)
        changed = list(rows)
        changed[1] = replace(rows[1], additional_cost_jpy="0.000000000001")
        over = review(ts=changed)
        self.assertTrue(over.aggregate_exceeds_existing_fraction)
        self.assertEqual(Decimal(over.total_illustrative_loss_jpy),
                         Decimal("1000.000000000001"))
        self.held(over)

    def test_tiny_positive_cost_is_not_mistaken_for_zero(self):
        r = review(ts=[jpy_ticket("0.000000000001")])
        self.assertEqual(Decimal(r.candidate_illustrative_loss_jpy)
                         - Decimal("500"), Decimal("0.000000000001"))
        self.held(r)

    def test_zero_assumed_costs_do_not_claim_broker_fee_authenticity(self):
        r = review(ts=[jpy_ticket(cost="0")])
        self.assertTrue(r.illustrative_complete)
        self.assertFalse(r.costs_verified)
        self.assertFalse(r.broker_contract_verified)
        self.held(r)

    def test_upper_bound_exactly_128_tickets_is_calculated_offline(self):
        rows = [jpy_ticket(cost="0")]
        rows += [jpy_ticket(cost="0", ticket_id=f"p-{i}",
                            status="PENDING") for i in range(127)]
        r = review(ts=rows)
        self.assertTrue(r.illustrative_complete)
        self.assertEqual(len(r.per_ticket_illustrative_loss_jpy), 128)
        self.assertEqual(Decimal(r.total_illustrative_loss_jpy),
                         Decimal("64000"))
        self.held(r)

    def test_129_tickets_fail_before_risk_arithmetic(self):
        rows = [jpy_ticket()]
        rows += [jpy_ticket(ticket_id=f"p-{i}", status="POSITION")
                 for i in range(128)]
        r = review(ts=rows)
        self.assertEqual(r.reason, "SYNTHETIC_WORKLOAD_BOUND_EXCEEDED")
        self.assertFalse(r.illustrative_complete)
        self.held(r)

    def test_ticket_id_longer_than_128_characters_is_rejected(self):
        r = review(ts=[jpy_ticket(ticket_id="A" * 129)])
        self.assertEqual(r.reason, "DUPLICATE_OR_MISSING_TICKET_ID")
        self.assertFalse(r.illustrative_complete)
        self.held(r)

    def test_ticket_id_equal_128_characters_allowed_only_as_mock(self):
        r = review(ts=[jpy_ticket(ticket_id="A" * 128)])
        self.assertTrue(r.illustrative_complete)
        self.held(r)

    def test_snapshot_identity_longer_than_128_is_rejected(self):
        r = review(sid="a" * 129)
        self.assertEqual(r.reason, "MISSING_OR_INVALID_SNAPSHOT_IDENTITY")
        self.held(r)

    def test_snapshot_identity_equal_128_is_accepted_when_matched(self):
        sid = "a" * 128
        ts = [replace(jpy_ticket(), snapshot_id=sid)]
        qs = {name: replace(value, snapshot_id=sid)
              for name, value in quotes().items()}
        r = review(sid=sid, ts=ts, qs=qs)
        self.assertTrue(r.illustrative_complete)
        self.held(r)

    def test_asof_over_signed_64bit_max_and_bool_rejected(self):
        for bad in (mod.MAX_SYNTHETIC_ASOF + 1, -1, True, "42"):
            with self.subTest(bad=bad):
                r = review(asof=bad)
                self.assertEqual(r.reason,
                                 "MISSING_OR_INVALID_SNAPSHOT_IDENTITY")
                self.held(r)

    def test_asof_exact_signed_64bit_max_on_fake_quotes(self):
        q = {p: replace(v, observed_at=mod.MAX_SYNTHETIC_ASOF)
             for p, v in quotes().items()}
        r = review(qs=q, asof=mod.MAX_SYNTHETIC_ASOF)
        self.assertTrue(r.illustrative_complete)
        self.held(r)

    def test_context_restored_after_all_simulated_decisions(self):
        previous = getcontext().prec
        result = review()
        self.assertEqual(getcontext().prec, previous)
        self.assertTrue(result.illustrative_complete)
        result = review(ts=[jpy_ticket(ticket_id="A" * 129)])
        self.assertEqual(getcontext().prec, previous)
        self.held(result)

    def test_underfilled_or_unknown_inflight_state_stays_blocked(self):
        for kwargs in ({"positions": False}, {"pending": False},
                       {"inflight": False}, {"inflight": True,
                                           "pending": "YES"}):
            with self.subTest(kwargs=kwargs):
                r = review(**kwargs)
                self.assertEqual(r.reason, "BROKER_OR_INFLIGHT_STATE_UNKNOWN")
                self.held(r)

    def test_nonstring_or_overlong_loss_cost_is_rejected(self):
        for bad in (None, 0, True, "NaN", "Infinity",
                    "1" * 41, "-0.00001", "1e-12"):
            with self.subTest(bad=bad):
                r = review(ts=[jpy_ticket(cost=bad)])
                self.assertEqual(r.reason, "STOP_VOLUME_OR_COST_UNCOMPUTABLE")
                self.held(r)

    def test_unapproved_fourth_pair_stays_rejected(self):
        self.assertEqual(mod.PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))
        r = review(ts=[replace(jpy_ticket(), pair="GBP/USD")])
        self.assertEqual(r.reason, "INVALID_PAIR_SIDE_OR_ORDER_STATUS")
        self.held(r)

    def test_current_mock_risk_math_and_stop_conversion_use_same_budgets(self):
        from scripts import phase1_three_pair_synthetic_risk as portfolio
        self.assertEqual(mod.PAIRS, portfolio.PAIRS)
        self.assertEqual(mod.MAX_SYNTHETIC_TICKETS,
                         portfolio.MAX_SYNTHETIC_TRADES)
        self.assertEqual(mod.MAX_SYNTHETIC_ID_CHARS,
                         portfolio.MAX_SIMULATED_ID_CHARS)
        self.assertEqual(mod.DECIMAL_WORK_PRECISION,
                         portfolio.DECIMAL_WORK_PRECISION)
        self.assertEqual(mod.SYNTHETIC_TRADE_LIMIT, Decimal("0.005"))
        self.assertEqual(mod.SYNTHETIC_AGGREGATE_LIMIT, Decimal("0.01"))

    def test_precision_digit_check_is_independent_of_low_caller_context(self):
        nineteen = "0.1234567890123456789"
        eighteen = "0.123456789012345678"
        with localcontext() as ctx:
            ctx.prec = 3
            self.assertIsNone(mod._parse(nineteen))
            self.assertEqual(mod._parse(eighteen), Decimal(eighteen))
            wrong = review(ts=[jpy_ticket(cost=nineteen)])
            self.assertEqual(wrong.reason, "STOP_VOLUME_OR_COST_UNCOMPUTABLE")
            self.assertFalse(wrong.illustrative_complete)
            self.held(wrong)

    def test_noncanonical_leading_or_scientific_numbers_still_rejected(self):
        for bad in ("01", "1e5", "+1", "1_000", " 1", "NaN", "-0"):
            with self.subTest(bad=bad):
                r = review(ts=[jpy_ticket(cost=bad)])
                self.assertEqual(r.reason, "STOP_VOLUME_OR_COST_UNCOMPUTABLE")
                self.held(r)

    def test_trailing_zeroes_do_not_create_fake_significant_digits(self):
        value = "1.00000000000000000000000000000000000000"
        self.assertLessEqual(len(value), 40)
        with localcontext() as ctx:
            ctx.prec = 3
            self.assertEqual(mod._parse(value), Decimal("1"))
            self.assertEqual(getcontext().prec, 3)

    def test_all_synthetic_successes_are_never_order_permission(self):
        self.assertEqual(mod.DECIMAL_WORK_PRECISION, 96)
        r = review()
        self.assertTrue(r.illustrative_complete)
        self.held(r)


if __name__ == "__main__":
    unittest.main()
