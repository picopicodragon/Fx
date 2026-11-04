"""RISK-3P-04: only hypothetical decimals, never broker loss assurance."""
from dataclasses import replace
from decimal import Decimal
import unittest

from scripts.phase1_three_pair_synthetic_stop_conversion import (
    Contract, Quote, Ticket, Review, review_synthetic_stop_risk,
)


def contracts():
    return {name: Contract(name, "100000", "0.01", "0.01", "1")
            for name in ("USD/JPY", "EUR/JPY", "EUR/USD")}


def quotes():
    return {
        "USD/JPY": Quote("USD/JPY", "150", "151", 42, "fixture-1"),
        "EUR/JPY": Quote("EUR/JPY", "181", "182", 42, "fixture-1"),
        "EUR/USD": Quote("EUR/USD", "1.20", "1.21", 42, "fixture-1"),
    }


def tickets():
    return [
        Ticket("candidate", "EUR/USD", "BUY", "CANDIDATE",
               "0.01", "1.2000", "1.1990", "0.0001", "5", "fixture-1"),
        Ticket("position", "USD/JPY", "SELL", "POSITION",
               "0.01", "150", "150.05", "0.01", "0", "fixture-1"),
        Ticket("pending", "EUR/JPY", "BUY", "PENDING",
               "0.01", "181", "180.9", "0.01", "0", "fixture-1"),
    ]


def review(cs=None, qs=None, ts=None, **kw):
    options = {
        "equity_jpy": "100000", "asof": 42, "snapshot_id": "fixture-1",
        "positions_reconciled": True,
        "pending_reconciled": True,
        "inflight_reservations_reconciled": True,
    }
    options.update(kw)
    return review_synthetic_stop_risk(contracts() if cs is None else cs,
                                      quotes() if qs is None else qs,
                                      tickets() if ts is None else ts, **options)


class RiskThreePairSyntheticConversionTests(unittest.TestCase):
    def held(self, result):
        self.assertIs(type(result), Review)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertIs(result.safety_hold_latched, True)
        self.assertIs(result.order_allowed, False)
        self.assertIs(result.result_authorizes_trade, False)
        self.assertIs(result.broker_contract_verified, False)
        self.assertIs(result.costs_verified, False)
        self.assertIs(result.stop_execution_guaranteed, False)
        self.assertIs(result.stop_release_allowed, False)
        self.assertIs(result.automatic_retry_allowed, False)
        self.assertIsNone(result.verified_values)

    def rejected(self, r, reason):
        self.assertFalse(r.illustrative_complete)
        self.assertEqual(r.reason, reason)
        self.held(r)

    def test_eurusd_usd_loss_times_usdjpy_ask_plus_explicit_buffer_cost(self):
        r = review()
        self.assertTrue(r.illustrative_complete)
        values = dict(r.per_ticket_illustrative_loss_jpy)
        self.assertEqual(Decimal(values["candidate"]), Decimal("171.1"))
        self.assertEqual(Decimal(values["position"]), Decimal("60"))
        self.assertEqual(Decimal(values["pending"]), Decimal("110"))
        self.assertEqual(Decimal(r.total_illustrative_loss_jpy), Decimal("341.1"))
        self.assertEqual(Decimal(r.candidate_illustrative_loss_jpy), Decimal("171.1"))
        self.assertFalse(r.candidate_exceeds_existing_fraction)
        self.assertFalse(r.aggregate_exceeds_existing_fraction)
        self.assertEqual(r.reason, "SYNTHETIC_ARITHMETIC_ONLY_NEVER_AUTHORIZED")
        self.assertEqual(r.quote_conversion_method, "UNAPPROVED_SYNTHETIC_ONLY")
        self.held(r)

    def test_eurusd_short_has_adverse_stop_above_entry(self):
        t = tickets()
        t[0] = replace(t[0], side="SELL", stop_price="1.2010")
        r = review(ts=t)
        self.assertEqual(Decimal(dict(r.per_ticket_illustrative_loss_jpy)["candidate"]),
                         Decimal("171.1"))
        self.held(r)

    def test_same_usd_loss_uses_upper_ask_and_is_sensitive_to_quote(self):
        t = [Ticket("a", "EUR/USD", "BUY", "CANDIDATE",
                    "0.10", "1.20", "1.199", "0", "0", "fixture-1")]
        base = review(ts=t)
        self.assertEqual(Decimal(base.candidate_illustrative_loss_jpy),
                         Decimal("1510"))
        self.assertTrue(base.candidate_exceeds_existing_fraction)
        qs = quotes()
        qs["USD/JPY"] = replace(qs["USD/JPY"], bid="150", ask="150")
        lower = review(qs=qs, ts=t)
        self.assertEqual(Decimal(lower.candidate_illustrative_loss_jpy),
                         Decimal("1500"))
        self.held(base)
        self.held(lower)

    def test_account_boundaries_are_strict_without_rounding_or_netting(self):
        t = [
            Ticket("a", "USD/JPY", "BUY", "CANDIDATE",
                   "0.01", "150.50", "150.00", "0", "0", "fixture-1"),
            Ticket("b", "USD/JPY", "BUY", "POSITION",
                   "0.01", "150.3", "150.0", "0", "0", "fixture-1"),
            Ticket("c", "EUR/JPY", "SELL", "PENDING",
                   "0.01", "181.0", "181.2", "0", "0", "fixture-1"),
        ]
        r = review(ts=t)
        self.assertEqual(Decimal(r.candidate_illustrative_loss_jpy), Decimal("500"))
        self.assertEqual(Decimal(r.total_illustrative_loss_jpy), Decimal("1000"))
        self.assertFalse(r.candidate_exceeds_existing_fraction)
        self.assertFalse(r.aggregate_exceeds_existing_fraction)
        self.held(r)

        changed = list(t)
        changed[0] = replace(changed[0], additional_cost_jpy="0.01")
        r2 = review(ts=changed)
        self.assertTrue(r2.candidate_exceeds_existing_fraction)
        self.assertTrue(r2.aggregate_exceeds_existing_fraction)
        self.assertEqual(Decimal(r2.total_illustrative_loss_jpy), Decimal("1000.01"))
        self.held(r2)

    def test_min_lot_step_and_max_are_not_rounded_optimistically(self):
        for lots in ("0.001", "0.015", "1.01"):
            with self.subTest(lots=lots):
                t = tickets()
                t[0] = replace(t[0], volume_lots=lots)
                self.rejected(review(ts=t), "MIN_LOT_OR_STEP_NOT_SATISFIED")

    def test_lot_contract_missing_or_invalid_rejected(self):
        for field, value in (
            ("min_lot", None), ("lot_step", "0"), ("base_units_per_lot", "-1"),
            ("max_lot", "NaN"), ("min_lot", True),
            ("base_units_per_lot", "1e5"),
        ):
            with self.subTest(field=field):
                c = contracts()
                c["EUR/USD"] = replace(c["EUR/USD"], **{field: value})
                self.rejected(review(cs=c), "CONTRACT_ATTRIBUTES_UNKNOWN")
        for changes in (
            {"max_lot": "0.001"}, {"lot_step": "0.02"},
        ):
            c = contracts()
            c["EUR/USD"] = replace(c["EUR/USD"], **changes)
            self.rejected(review(cs=c), "INCOHERENT_SYNTHETIC_LOT_CONTRACT")

    def test_incomplete_contract_quote_or_pair_mismatch_is_rejected(self):
        c = contracts()
        del c["EUR/USD"]
        self.rejected(review(cs=c), "CONTRACT_SET_INCOMPLETE")
        c = contracts()
        c["AUD/USD"] = c["EUR/USD"]
        self.rejected(review(cs=c), "CONTRACT_SET_INCOMPLETE")
        c = contracts()
        c["EUR/USD"] = replace(c["EUR/USD"], pair="EUR/JPY")
        self.rejected(review(cs=c), "INVALID_SYNTHETIC_CONTRACT")
        q = quotes()
        del q["USD/JPY"]
        self.rejected(review(qs=q), "QUOTE_SET_INCOMPLETE")
        q = quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], pair="GBP/USD")
        self.rejected(review(qs=q), "INVALID_QUOTE")

    def test_bid_ask_quote_validation_and_stale_cross_rate(self):
        for bid, ask in (
            ("0", "151"), ("151", "150"), ("150", "NaN"),
            ("Infinity", "151"), ("150", "0"), ("1e2", "151"),
            (151, "151"), ("150", None), ("-1", "151"),
        ):
            with self.subTest(bid=bid, ask=ask):
                q = quotes()
                q["USD/JPY"] = replace(q["USD/JPY"], bid=bid, ask=ask)
                self.rejected(review(qs=q), "INVALID_BID_ASK")
        for key, value in (
            ("observed_at", 41), ("observed_at", True),
            ("snapshot_id", "old"), ("snapshot_id", None),
        ):
            q = quotes()
            q["USD/JPY"] = replace(q["USD/JPY"], **{key: value})
            self.rejected(review(qs=q), "STALE_OR_MIXED_QUOTE")

    def test_wrong_side_or_missing_server_stop_is_refused(self):
        for side, entry, stop in (
            ("BUY", "1.20", "1.20"), ("BUY", "1.20", "1.21"),
            ("SELL", "1.20", "1.20"), ("SELL", "1.20", "1.19"),
        ):
            with self.subTest(side=side, entry=entry, stop=stop):
                t = tickets()
                t[0] = replace(t[0], side=side, planned_entry=entry, stop_price=stop)
                self.rejected(review(ts=t), "MISSING_OR_WRONG_SIDE_STOP")
        for stop in (None, "", "-1", True):
            t = tickets()
            t[0] = replace(t[0], stop_price=stop)
            self.rejected(review(ts=t), "STOP_VOLUME_OR_COST_UNCOMPUTABLE")

    def test_unbounded_real_gap_and_unknown_fees_are_not_silently_zero(self):
        for key, v in (
            ("adverse_buffer_quote_per_base", None),
            ("additional_cost_jpy", None),
            ("adverse_buffer_quote_per_base", "-0.1"),
            ("additional_cost_jpy", "NaN"),
            ("additional_cost_jpy", 0),
        ):
            with self.subTest(key=key, value=v):
                t = tickets()
                t[0] = replace(t[0], **{key: v})
                self.rejected(review(ts=t), "STOP_VOLUME_OR_COST_UNCOMPUTABLE")

        t = tickets()
        t[0] = replace(t[0], adverse_buffer_quote_per_base="0", additional_cost_jpy="0")
        r = review(ts=t)
        self.assertTrue(r.illustrative_complete)
        self.assertFalse(r.stop_execution_guaranteed)
        self.assertFalse(r.costs_verified)
        self.held(r)

    def test_inflight_unknown_cancellation_unconfirmed_partial_fill_rejected(self):
        for kw in (
            {"positions_reconciled": None},
            {"pending_reconciled": False},
            {"inflight_reservations_reconciled": False},
            {"inflight_reservations_reconciled": 1},
            {"pending_reconciled": "yes"},
        ):
            with self.subTest(kw=kw):
                self.rejected(review(**kw), "BROKER_OR_INFLIGHT_STATE_UNKNOWN")
        for status in ("OUTCOME_UNKNOWN", "PARTIALLY_FILLED",
                       "CANCEL_REQUESTED", "OCO_ASSUMED"):
            t = tickets()
            t[1] = replace(t[1], status=status)
            self.rejected(review(ts=t), "INVALID_PAIR_SIDE_OR_ORDER_STATUS")

    def test_pending_and_hedged_orders_never_disappear_from_aggregate(self):
        t = [
            Ticket("c", "USD/JPY", "BUY", "CANDIDATE",
                   "0.01", "150.5", "150", "0", "0", "fixture-1"),
            Ticket("p", "USD/JPY", "SELL", "PENDING",
                   "0.01", "150.0", "150.5", "0", "0", "fixture-1"),
        ]
        r = review(ts=t)
        self.assertEqual(Decimal(r.candidate_illustrative_loss_jpy), Decimal(500))
        self.assertEqual(Decimal(r.total_illustrative_loss_jpy), Decimal(1000))
        self.held(r)

    def test_missing_duplicate_or_multiple_candidates_and_ids_are_rejected(self):
        self.rejected(review(ts=[]), "MISSING_TICKETS")
        t = tickets()
        t[1] = replace(t[1], ticket_id="candidate")
        self.rejected(review(ts=t), "DUPLICATE_OR_MISSING_TICKET_ID")
        t = tickets()
        t[0] = replace(t[0], status="PENDING")
        self.rejected(review(ts=t), "EXACTLY_ONE_CANDIDATE_REQUIRED")
        t = tickets()
        t[1] = replace(t[1], status="CANDIDATE")
        self.rejected(review(ts=t), "EXACTLY_ONE_CANDIDATE_REQUIRED")
        t = tickets()
        t[0] = replace(t[0], snapshot_id="stale")
        self.rejected(review(ts=t), "TICKET_SNAPSHOT_MISMATCH")

    def test_bad_input_types_or_missing_snapshot_never_emit_trade_go(self):
        for kw, reason in (
            ({"equity_jpy": "0"}, "MISSING_OR_INVALID_EQUITY"),
            ({"equity_jpy": "NaN"}, "MISSING_OR_INVALID_EQUITY"),
            ({"equity_jpy": 100000}, "MISSING_OR_INVALID_EQUITY"),
            ({"asof": True}, "MISSING_OR_INVALID_SNAPSHOT_IDENTITY"),
            ({"snapshot_id": ""}, "MISSING_OR_INVALID_SNAPSHOT_IDENTITY"),
        ):
            with self.subTest(kw=kw):
                self.rejected(review(**kw), reason)
        self.rejected(review(cs=object()), "CONTRACT_SET_INCOMPLETE")
        self.rejected(review(qs=object()), "QUOTE_SET_INCOMPLETE")
        self.rejected(review(ts=object()), "MISSING_TICKETS")

    def test_all_synthetic_limits_within_never_authorizes_phase_or_order(self):
        r = review()
        self.assertTrue(r.illustrative_complete)
        self.assertFalse(r.candidate_exceeds_existing_fraction)
        self.assertFalse(r.aggregate_exceeds_existing_fraction)
        self.held(r)


if __name__ == "__main__":
    unittest.main()
