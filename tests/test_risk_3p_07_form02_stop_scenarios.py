"""FORM-02 offline order/stop shape tests, never MT4 or trade permission."""
from dataclasses import replace
import unittest

from scripts.phase1_form02_synthetic_stop_scenarios import (
    SyntheticStopCase, Review, review_synthetic_stop_shape,
)


def market_buy():
    return SyntheticStopCase(
        pair="USD/JPY", side="BUY", order_kind="MARKET", stage="CANDIDATE",
        planned_entry="151", trigger_price=None, fill_price=None,
        stop_price="150", quote_bid="150", quote_ask="151", epoch=17,
        quote_epoch=17, stop_ack_epoch=None, server_stop_state="NOT_SENT",
        stop_update_state="NONE", execution_state="NOT_DISPATCHED",
        gap_state="NO_GAP_IN_SYNTHETIC_EXAMPLE",
        broker_state_reconciled=True, pending_state_reconciled=True,
        inflight_state_reconciled=True,
    )


def pending(side, kind):
    args = {
        ("BUY", "LIMIT"): ("148", "147"),
        ("SELL", "LIMIT"): ("152", "153"),
        ("BUY", "STOP"): ("152", "150"),
        ("SELL", "STOP"): ("149", "150"),
    }
    trigger, stop = args[(side, kind)]
    return replace(
        market_buy(), side=side, order_kind=kind, stage="PENDING",
        planned_entry=None, trigger_price=trigger, stop_price=stop,
        stop_ack_epoch=17, server_stop_state="CONFIRMED",
        execution_state="PENDING_CONFIRMED",
    )


def position(side="BUY", kind="MARKET"):
    trigger = None if kind == "MARKET" else ("148" if side == "BUY" else "152")
    return replace(
        market_buy(), side=side, order_kind=kind, stage="POSITION",
        planned_entry="120", trigger_price=trigger,
        fill_price="149" if side == "BUY" else "151",
        stop_price="148" if side == "BUY" else "152",
        stop_ack_epoch=17, server_stop_state="CONFIRMED",
        execution_state="FILLED_CONFIRMED",
    )


class Form02SyntheticStopTests(unittest.TestCase):
    def held(self, result):
        self.assertIs(type(result), Review)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertIs(result.safety_hold_latched, True)
        self.assertIs(result.order_allowed, False)
        self.assertIs(result.stop_release_allowed, False)
        self.assertIs(result.automatic_retry_allowed, False)
        self.assertIs(result.result_authorizes_protective_order_change, False)
        self.assertIs(result.real_broker_stop_verified, False)
        self.assertIs(result.trading_contract_verified, False)
        self.assertIs(result.form02_approved, False)
        self.assertIs(result.production_authorized, False)
        self.assertIs(result.finite_gap_loss_bound_verified, False)
        self.assertIsNone(result.measured_loss_jpy)
        self.assertIsNone(result.verified_values)

    def denied(self, case, reason):
        r = review_synthetic_stop_shape(case)
        self.assertEqual(r.reason, reason)
        self.assertFalse(r.synthetic_shape_reviewed)
        self.assertIsNone(r.reference_origin)
        self.held(r)

    def test_unconnected_market_buy_and_sell_shape_not_loss_bound(self):
        for side, stop in (("BUY", "150"), ("SELL", "152")):
            with self.subTest(side=side):
                case = replace(market_buy(), side=side, stop_price=stop)
                r = review_synthetic_stop_shape(case)
                self.assertEqual(r.reason, "SYNTHETIC_SHAPE_ONLY_NO_LOSS_BOUND_NO_GO")
                self.assertTrue(r.synthetic_shape_reviewed)
                self.assertEqual(r.reference_origin, "UNGUARANTEED_MARKET_PLAN")
                self.held(r)

    def test_four_pending_limit_and_stop_side_combinations_are_only_shapes(self):
        for side in ("BUY", "SELL"):
            for kind in ("LIMIT", "STOP"):
                with self.subTest(side=side, kind=kind):
                    r = review_synthetic_stop_shape(pending(side, kind))
                    self.assertTrue(r.synthetic_shape_reviewed)
                    self.assertEqual(r.reference_origin, "UNGUARANTEED_PENDING_TRIGGER")
                    self.held(r)

    def test_recorded_fill_replaces_planned_entry_as_reference(self):
        for side in ("BUY", "SELL"):
            for kind in ("MARKET", "LIMIT", "STOP"):
                with self.subTest(side=side, kind=kind):
                    r = review_synthetic_stop_shape(position(side, kind))
                    self.assertEqual(r.reference_origin, "SYNTHETIC_RECORDED_FILL")
                    self.assertEqual(r.reference_price, "149" if side == "BUY" else "151")
                    self.assertTrue(r.synthetic_shape_reviewed)
                    self.held(r)

    def test_stop_update_requires_ack_but_cannot_release_any_protection(self):
        case = replace(position(), stop_update_state="CONFIRMED")
        r = review_synthetic_stop_shape(case)
        self.assertTrue(r.synthetic_shape_reviewed)
        self.held(r)
        for state in ("PENDING", "FAILED", "UNKNOWN", "REMOVED", None, True):
            with self.subTest(state=state):
                self.denied(replace(position(), stop_update_state=state),
                            "STOP_REPLACE_OR_REMOVAL_UNCONFIRMED")
        self.denied(replace(market_buy(), stop_update_state="CONFIRMED"),
                    "STOP_REPLACE_ON_NONPOSITION")

    def test_server_stop_missing_stale_or_pending_blocks(self):
        for value in ("MISSING", "UNKNOWN", "PENDING", None):
            with self.subTest(server=value):
                self.denied(replace(position(), server_stop_state=value),
                            "SERVER_STOP_MISSING_OR_STALE")
        for epoch in (None, 16, 18, True, "17"):
            with self.subTest(epoch=epoch):
                self.denied(replace(position(), stop_ack_epoch=epoch),
                            "SERVER_STOP_MISSING_OR_STALE")
        self.denied(replace(market_buy(), server_stop_state="CONFIRMED"),
                    "CANDIDATE_CANNOT_CLAIM_SERVER_STOP")
        self.denied(replace(market_buy(), stop_ack_epoch=17),
                    "CANDIDATE_CANNOT_CLAIM_SERVER_STOP")

    def test_wrong_side_missing_and_zero_distance_stops_are_denied(self):
        for side, stop in (("BUY", "151"), ("BUY", "152"),
                           ("SELL", "151"), ("SELL", "150")):
            with self.subTest(side=side, stop=stop):
                self.denied(replace(market_buy(), side=side, stop_price=stop),
                            "STOP_WRONG_SIDE_OR_ZERO_DISTANCE")
        for value in (None, "", "-1", "0", "NaN", "1e5", 12.0, True):
            with self.subTest(value=repr(value)):
                self.denied(replace(market_buy(), stop_price=value),
                            "STOP_PRICE_MISSING_OR_INVALID")

    def test_pending_trigger_wrong_side_or_equal_to_quote_blocks(self):
        for side, kind, price in (
            ("BUY", "LIMIT", "151"), ("BUY", "LIMIT", "152"),
            ("SELL", "LIMIT", "150"), ("SELL", "LIMIT", "149"),
            ("BUY", "STOP", "151"), ("BUY", "STOP", "150"),
            ("SELL", "STOP", "150"), ("SELL", "STOP", "151"),
        ):
            with self.subTest(side=side, kind=kind, price=price):
                self.denied(replace(pending(side, kind), trigger_price=price),
                            "TRIGGER_NOT_ON_EXPECTED_SIDE_OF_SYNTHETIC_QUOTE")

    def test_market_pending_is_invalid_and_market_trigger_not_allowed(self):
        self.denied(replace(market_buy(), stage="PENDING",
                            server_stop_state="CONFIRMED", stop_ack_epoch=17,
                            execution_state="PENDING_CONFIRMED"),
                    "UNSUPPORTED_MARKET_PENDING")
        self.denied(replace(market_buy(), trigger_price="150"),
                    "MARKET_WITH_UNEXPECTED_TRIGGER")

    def test_pending_stop_level_must_be_correct_relative_to_trigger(self):
        for case in (replace(pending("BUY", "STOP"), stop_price="152"),
                     replace(pending("BUY", "LIMIT"), stop_price="148"),
                     replace(pending("SELL", "LIMIT"), stop_price="152"),
                     replace(pending("SELL", "STOP"), stop_price="149")):
            with self.subTest(case=case):
                self.denied(case, "STOP_WRONG_SIDE_OR_ZERO_DISTANCE")

    def test_unsupported_order_pair_side_stage_rejected(self):
        for name, value in (
            ("pair", "AUD/USD"), ("pair", "GBP/USD"), ("pair", None),
            ("side", "SHORT"), ("side", None), ("order_kind", "STOP_LIMIT"),
            ("order_kind", None), ("stage", "DISPATCHING"),
            ("stage", "OUTCOME_UNKNOWN"),
        ):
            with self.subTest(name=name):
                self.denied(replace(market_buy(), **{name: value}),
                            "PAIR_SIDE_KIND_OR_STAGE_UNSUPPORTED")

    def test_partial_fill_and_cancel_uncertain_refuse_new_orders(self):
        for status in ("PARTIALLY_FILLED", "CANCEL_REQUESTED",
                       "REPLACED_UNKNOWN", "OUTCOME_UNKNOWN",
                       "ACK_PENDING", None, True):
            with self.subTest(status=status):
                self.denied(replace(position(), execution_state=status),
                            "EXECUTION_PARTIAL_OR_UNKNOWN")
        self.denied(replace(market_buy(), execution_state="FILLED_CONFIRMED"),
                    "EXECUTION_PARTIAL_OR_UNKNOWN")

    def test_gap_or_slippage_unknown_cannot_have_finite_risk_claim(self):
        for gap in ("ADVERSE_GAP", "GAP_UNKNOWN", "SLIPPAGE_UNKNOWN",
                    "FINITE_GAP_ASSUMED", None, True):
            with self.subTest(gap=gap):
                self.denied(replace(market_buy(), gap_state=gap),
                            "GAP_OR_SLIPPAGE_UNBOUNDED")
        r = review_synthetic_stop_shape(market_buy())
        self.assertFalse(r.finite_gap_loss_bound_verified)
        self.assertIsNone(r.measured_loss_jpy)
        self.held(r)

    def test_stale_or_mixed_epoch_rejects(self):
        for field, value in (("epoch", True), ("epoch", None), ("epoch", -1),
                             ("quote_epoch", 16), ("quote_epoch", 18),
                             ("quote_epoch", True), ("quote_epoch", "17")):
            with self.subTest(field=field, value=value):
                self.denied(replace(market_buy(), **{field: value}),
                            "STALE_OR_INVALID_SYNTHETIC_QUOTE_EPOCH")

    def test_unreconciled_account_pending_and_inflight_refuse(self):
        for field in ("broker_state_reconciled", "pending_state_reconciled",
                      "inflight_state_reconciled"):
            for value in (False, None, 1, "True"):
                with self.subTest(field=field, value=value):
                    self.denied(replace(market_buy(), **{field: value}),
                                "BROKER_PENDING_OR_INFLIGHT_UNKNOWN")

    def test_crossed_quote_invalid_bid_ask_and_missing_planned_price_refuse(self):
        for bid, ask in (("151", "150"), ("0", "151"), ("150", "0"),
                         ("NaN", "151"), ("150", "Infinity"),
                         ("149", None), ("1e2", "151"), ("-1", "151")):
            with self.subTest(bid=bid, ask=ask):
                self.denied(replace(market_buy(), quote_bid=bid, quote_ask=ask),
                            "QUOTE_MISSING_OR_CROSSED")
        self.denied(replace(market_buy(), planned_entry=None),
                    "ENTRY_REFERENCE_MISSING")

    def test_missing_actual_fill_refuses_even_if_market_plan_present(self):
        self.denied(replace(position(), fill_price=None),
                    "POSITION_FILL_UNCONFIRMED")
        self.denied(replace(position(), fill_price="0"),
                    "POSITION_FILL_UNCONFIRMED")
        self.denied(replace(market_buy(), fill_price="151"),
                    "UNEXPECTED_FILL_BEFORE_POSITION")

    def test_missing_pending_trigger_is_rejected(self):
        self.denied(replace(pending("BUY", "LIMIT"), trigger_price=None),
                    "PENDING_TRIGGER_MISSING_OR_INVALID")
        self.denied(replace(pending("BUY", "STOP"), trigger_price="NaN"),
                    "PENDING_TRIGGER_MISSING_OR_INVALID")

    def test_false_safety_promotion_impossible_on_both_results(self):
        for case in (market_buy(),
                     replace(position(), stop_update_state="UNKNOWN"),
                     pending("SELL", "STOP")):
            r = review_synthetic_stop_shape(case)
            self.held(r)

    def test_unstructured_input_fails_closed(self):
        for bad in (None, [], {}, True, "BUY"):
            with self.subTest(bad=repr(bad)):
                self.denied(bad, "INVALID_CASE")


if __name__ == "__main__":
    unittest.main()
