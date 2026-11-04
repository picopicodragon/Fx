"""RISK-3P-08..12 offline-only FORM-03..07 negative matrix."""
from dataclasses import replace
from decimal import Decimal
import unittest

from scripts.phase1_form03_07_synthetic_bundle import (
    Quote, Cost, Slice, Snapshot, Review, review_synthetic_bundle,
)


def quotes():
    return {
        "USD/JPY": Quote("USD/JPY", "150", "151", 11, "snapshot-fixture"),
        "EUR/JPY": Quote("EUR/JPY", "181", "182", 11, "snapshot-fixture"),
        "EUR/USD": Quote("EUR/USD", "1.20", "1.21", 11, "snapshot-fixture"),
    }


def costs():
    return (
        Cost("SPREAD", "1", "INCLUDED_IN_BASE", True),
        Cost("COMMISSION", "2", "ADDITIONAL", False),
        Cost("SWAP", "0", "ADDITIONAL", False),
        Cost("SLIPPAGE", "3", "ADDITIONAL", False),
    )


def portions():
    return [
        Slice("a", "order-a", "EUR/USD", "BUY", "CANDIDATE", "WHOLE",
              "0.01", "0.01", "0.01", "1", "2", "USD", costs()),
        Slice("b", "order-b", "USD/JPY", "SELL", "POSITION", "WHOLE",
              "0.01", "0.01", "0.01", "1", "200", "JPY", costs()),
        Slice("c", "order-c", "EUR/JPY", "BUY", "PENDING", "WHOLE",
              "0.01", "0.01", "0.01", "1", "300", "JPY", costs()),
    ]


def snapshot():
    return Snapshot(
        epoch=11, broker_epoch=11, quote_epoch=11, reservation_epoch=11,
        snapshot_id="snapshot-fixture", broker_reconciled=True,
        pending_reconciled=True, inflight_reconciled=True,
        currency_exposure_reconciled=True,
        dispatch_state="QUIESCENT_SYNTHETIC_ONLY",
        gap_assumption="SYNTHETIC_BOUNDED_EXAMPLE_ONLY",
    )


def review(q=None, p=None, s=None, equity="100000"):
    return review_synthetic_bundle(
        quotes() if q is None else q,
        portions() if p is None else p,
        snapshot() if s is None else s, equity_jpy=equity,
    )


def zero_costs():
    return tuple(Cost(k, "0", "ADDITIONAL", False) for k in (
        "SPREAD", "COMMISSION", "SWAP", "SLIPPAGE"))


class BatchForm03To07Tests(unittest.TestCase):
    def held(self, r):
        self.assertIs(type(r), Review)
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertIs(r.safety_hold_latched, True)
        self.assertIs(r.order_allowed, False)
        self.assertIs(r.stop_release_allowed, False)
        self.assertIs(r.automatic_retry_allowed, False)
        self.assertIs(r.production_authorized, False)
        self.assertIs(r.owner_approval_recorded, False)
        self.assertIs(r.price_conversion_policy_approved, False)
        self.assertIs(r.broker_contract_verified, False)
        self.assertIs(r.costs_verified, False)
        self.assertIs(r.account_and_order_state_verified, False)
        self.assertIs(r.real_gap_loss_bound_verified, False)
        self.assertIs(r.gross_loss_nonnetted, True)
        self.assertIsNone(r.verified_values)

    def denied(self, r, reason):
        self.assertEqual(r.reason, reason)
        self.assertFalse(r.computed_synthetic_only)
        self.held(r)

    def test_baseline_eurusd_loss_quote_is_usd_converted_at_ask(self):
        r = review()
        self.assertTrue(r.computed_synthetic_only)
        self.assertEqual(Decimal(dict(r.per_slice_jpy)["a"]), Decimal("307"))
        self.assertEqual(Decimal(dict(r.per_slice_jpy)["b"]), Decimal("205"))
        self.assertEqual(Decimal(dict(r.per_slice_jpy)["c"]), Decimal("305"))
        self.assertEqual(Decimal(r.candidate_jpy), Decimal("307"))
        self.assertEqual(Decimal(r.aggregate_jpy), Decimal("817"))
        self.assertFalse(r.candidate_above_existing_fraction)
        self.assertFalse(r.aggregate_above_existing_fraction)
        self.assertEqual(r.reason, "SYNTHETIC_ASSERTED_LOSS_ONLY_NO_GO")
        self.held(r)

    def test_form03_usdjpy_ask_example_varies_without_claiming_approved_policy(self):
        base = review()
        q = quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], ask="150")
        lower = review(q=q)
        self.assertEqual(Decimal(base.candidate_jpy) -
                         Decimal(lower.candidate_jpy), Decimal("2"))
        self.held(base)
        self.held(lower)

    def test_form03_unknown_quote_currency_or_pair_fail_closed(self):
        p = portions()
        p[0] = replace(p[0], quote_currency="JPY")
        self.denied(review(p=p), "WRONG_QUOTE_CURRENCY_FOR_PAIR")
        p = portions()
        p[0] = replace(p[0], pair="EUR/GBP")
        self.denied(review(p=p), "UNSUPPORTED_RISK_SLICE_STATE")

    def test_form03_quote_missing_wrong_epoch_crossed_and_nondecimal(self):
        q = quotes()
        del q["USD/JPY"]
        self.denied(review(q=q), "INCOMPLETE_THREE_PAIR_QUOTE_SET")
        for field, val, reason in (
            ("epoch", 10, "QUOTE_STALE_OR_MIXED_SNAPSHOT"),
            ("epoch", True, "QUOTE_STALE_OR_MIXED_SNAPSHOT"),
            ("snapshot_id", "different", "QUOTE_STALE_OR_MIXED_SNAPSHOT"),
            ("ask", "149", "QUOTE_BID_ASK_INVALID"),
            ("ask", "NaN", "QUOTE_BID_ASK_INVALID"),
            ("bid", "1e2", "QUOTE_BID_ASK_INVALID"),
        ):
            with self.subTest(field=field, value=val):
                q = quotes()
                q["USD/JPY"] = replace(q["USD/JPY"], **{field: val})
                self.denied(review(q=q), reason)

    def test_form04_spread_included_is_not_added_twice(self):
        r = review()
        p = portions()
        c = list(p[0].costs)
        c[0] = Cost("SPREAD", "25", "INCLUDED_IN_BASE", True)
        p[0] = replace(p[0], costs=tuple(c))
        r2 = review(p=p)
        self.assertEqual(r.candidate_jpy, r2.candidate_jpy)
        self.held(r2)

    def test_form04_spread_additional_is_explicit_and_not_silently_ignored(self):
        p = portions()
        c = list(p[0].costs)
        c[0] = Cost("SPREAD", "25", "ADDITIONAL", False)
        p[0] = replace(p[0], costs=tuple(c))
        r = review(p=p)
        self.assertEqual(Decimal(r.candidate_jpy), Decimal("332"))
        self.held(r)

    def test_form04_missing_fee_component_incomplete(self):
        p = portions()
        p[0] = replace(p[0], costs=p[0].costs[:-1])
        self.denied(review(p=p), "FOUR_COST_COMPONENTS_REQUIRED")

    def test_form04_duplicate_cost_kind_rejected(self):
        p = portions()
        p[0] = replace(p[0], costs=(
            Cost("SPREAD", "1", "ADDITIONAL", False),
            Cost("SPREAD", "1", "ADDITIONAL", False),
            Cost("SWAP", "1", "ADDITIONAL", False),
            Cost("SLIPPAGE", "1", "ADDITIONAL", False),
        ))
        self.denied(review(p=p), "DUPLICATE_OR_UNSUPPORTED_COST_KIND")

    def test_form04_wrong_cost_accounting_or_unknown_fee_rejected(self):
        for disposition, included, expected in (
            ("ADDITIONAL", True, "COST_ACCOUNTING_CONTRADICTION"),
            ("INCLUDED_IN_BASE", False, "COST_ACCOUNTING_CONTRADICTION"),
            ("UNKNOWN", False, "COST_ACCOUNTING_UNKNOWN"),
        ):
            with self.subTest(disposition=disposition):
                p = portions()
                c = list(p[0].costs)
                c[0] = replace(c[0], disposition=disposition,
                               asserted_in_base=included)
                p[0] = replace(p[0], costs=tuple(c))
                self.denied(review(p=p), expected)
        p = portions()
        c = list(p[0].costs)
        c[1] = replace(c[1], amount_jpy=None)
        p[0] = replace(p[0], costs=tuple(c))
        self.denied(review(p=p), "MISSING_OR_INVALID_COST_AMOUNT")

    def test_form04_gap_or_slippage_unbounded_prevents_calculation(self):
        for x in ("UNKNOWN", "ADVERSE_GAP", "UNBOUNDED", None, True):
            with self.subTest(x=x):
                self.denied(review(s=replace(snapshot(), gap_assumption=x)),
                            "GAP_OR_SLIPPAGE_UNBOUNDED")
        self.assertIs(review().real_gap_loss_bound_verified, False)

    def test_form05_all_generations_must_match_and_be_nonboolean_int(self):
        for field, x in (
            ("epoch", True), ("quote_epoch", 12), ("broker_epoch", 10),
            ("reservation_epoch", 9), ("epoch", -1),
            ("snapshot_id", None), ("snapshot_id", ""),
        ):
            with self.subTest(field=field, x=x):
                self.denied(review(s=replace(snapshot(), **{field: x})),
                            "MIXED_OR_INVALID_DECISION_GENERATION")

    def test_form05_broker_pending_inflight_and_exposure_flags_must_be_true(self):
        for field in (
            "broker_reconciled", "pending_reconciled",
            "inflight_reconciled", "currency_exposure_reconciled",
        ):
            for val in (False, None, 1, "yes"):
                with self.subTest(field=field, val=val):
                    self.denied(review(s=replace(snapshot(), **{field: val})),
                                "ACCOUNT_PENDING_RESERVATION_OR_EXPOSURE_UNRECONCILED")

    def test_form05_unknown_dispatch_or_cancel_and_replay_is_denied(self):
        for dispatch in ("DISPATCHING", "OUTCOME_UNKNOWN", "CANCEL_REQUESTED",
                         "RETRY", None, True):
            with self.subTest(dispatch=dispatch):
                self.denied(review(s=replace(snapshot(), dispatch_state=dispatch)),
                            "DISPATCH_OR_CANCEL_OUTCOME_UNKNOWN")

    def test_form06_reservation_and_opposite_orders_are_not_net_reduced(self):
        p = portions()
        p.append(replace(p[2], slice_id="d", order_id="order-d",
                         pair="EUR/USD", quote_currency="USD", side="SELL",
                         status="RESERVED", asserted_quote_loss="1"))
        r = review(p=p)
        self.assertEqual(Decimal(r.aggregate_jpy), Decimal("973"))
        self.assertEqual(Decimal(r.candidate_jpy), Decimal("307"))
        self.held(r)

    def test_form06_partial_fill_requires_unique_filled_and_remaining(self):
        p = portions()
        p[1] = replace(p[1], slice_id="part-1", order_id="order-split",
                       status="POSITION", portion="FILLED",
                       asserted_quote_loss="75")
        p.append(replace(p[1], slice_id="part-2",
                         status="PENDING", portion="REMAINDER",
                         asserted_quote_loss="125"))
        r = review(p=p)
        self.assertEqual(Decimal(r.aggregate_jpy), Decimal("822"))
        self.assertEqual(Decimal(dict(r.per_slice_jpy)["part-1"]), Decimal("80"))
        self.assertEqual(Decimal(dict(r.per_slice_jpy)["part-2"]), Decimal("130"))
        self.held(r)

    def test_form06_orphan_split_portion_and_duplicate_ticket_id_rejected(self):
        p = portions()
        p[1] = replace(p[1], portion="FILLED")
        self.denied(review(p=p), "ORPHAN_PARTIAL_FILL_PORTION")
        p = portions()
        p[1] = replace(p[1], slice_id=p[0].slice_id)
        self.denied(review(p=p), "DUPLICATE_OR_INVALID_SLICE_ID")
        p = portions()
        p[1] = replace(p[1], order_id=p[0].order_id)
        self.denied(review(p=p), "PARTIAL_FILL_NOT_RECONCILED")

    def test_form06_unknown_partial_or_cancelled_order_state_rejected(self):
        for state in ("PARTIALLY_FILLED_UNKNOWN", "CANCEL_REQUESTED", "OCO_ASSUMED",
                      "OUTCOME_UNKNOWN", "DISPATCHING"):
            with self.subTest(state=state):
                p = portions()
                p[1] = replace(p[1], status=state)
                self.denied(review(p=p), "UNSUPPORTED_RISK_SLICE_STATE")

    def test_form06_multiple_candidates_or_none_rejected(self):
        p = portions()
        p[1] = replace(p[1], status="CANDIDATE")
        self.denied(review(p=p), "EXACTLY_ONE_CANDIDATE_REQUIRED")
        p = portions()
        p[0] = replace(p[0], status="RESERVED")
        self.denied(review(p=p), "EXACTLY_ONE_CANDIDATE_REQUIRED")

    def test_form07_strict_equity_decimal_and_lot_grid(self):
        for equity in ("0", "-1", "NaN", "1e5", None, 100000.0, True):
            with self.subTest(equity=equity):
                self.denied(review(equity=equity), "EQUITY_UNCOMPUTABLE")
        for field, x in (
            ("volume_lots", "0.001"), ("volume_lots", "0.015"),
            ("min_lot", None), ("lot_step", "0"), ("max_lot", "0.001"),
            ("asserted_quote_loss", "-1"), ("asserted_quote_loss", 200.0),
        ):
            with self.subTest(field=field, value=x):
                p = portions()
                p[0] = replace(p[0], **{field: x})
                reason = ("LOT_GRID_OR_BOUNDARY_INVALID"
                          if field in ("volume_lots", "max_lot")
                          else "MISSING_OR_INVALID_LOT_OR_LOSS_ASSERTION")
                self.denied(review(p=p), reason)

    def test_form07_boundary_candidate_and_aggregate_are_strict(self):
        p = [
            replace(portions()[0], pair="USD/JPY", quote_currency="JPY",
                    asserted_quote_loss="500", costs=zero_costs()),
            replace(portions()[1], asserted_quote_loss="300", costs=zero_costs()),
            replace(portions()[2], asserted_quote_loss="200", costs=zero_costs()),
        ]
        r = review(p=p)
        self.assertFalse(r.candidate_above_existing_fraction)
        self.assertFalse(r.aggregate_above_existing_fraction)
        self.assertEqual(Decimal(r.aggregate_jpy), Decimal("1000"))
        self.held(r)
        p[0] = replace(p[0], asserted_quote_loss="500.01")
        r = review(p=p)
        self.assertTrue(r.candidate_above_existing_fraction)
        self.assertTrue(r.aggregate_above_existing_fraction)
        self.assertEqual(Decimal(r.aggregate_jpy), Decimal("1000.01"))
        self.held(r)

    def test_form07_no_real_permission_even_with_zero_cost_inputs(self):
        p = [replace(x, costs=zero_costs()) for x in portions()]
        r = review(p=p)
        self.assertTrue(r.computed_synthetic_only)
        self.assertEqual(r.reason, "SYNTHETIC_ASSERTED_LOSS_ONLY_NO_GO")
        self.held(r)

    def test_garbage_inputs_and_infinite_numbers_fail_closed(self):
        self.denied(review(q=object()), "INCOMPLETE_THREE_PAIR_QUOTE_SET")
        self.denied(review(p=object()), "RISK_SLICES_MISSING")
        self.denied(review(s=object()), "INVALID_SNAPSHOT")
        self.denied(review(p=[]), "RISK_SLICES_MISSING")
        p = portions()
        p[0] = replace(p[0], asserted_quote_loss="Infinity")
        self.denied(review(p=p), "MISSING_OR_INVALID_LOT_OR_LOSS_ASSERTION")
        p = portions()
        p[0] = object()
        self.denied(review(p=p), "SLICE_FORMAT_INVALID")


if __name__ == "__main__":
    unittest.main()
