"""RISK-3P-01: no broker, network, filesystem, or live-risk approval."""
from dataclasses import replace
from decimal import Decimal
import unittest

from scripts.phase1_three_pair_synthetic_risk import (
    Quote, Trade, Review, review_synthetic_portfolio,
)


def prices(asof=123, snapshot_id="synthetic-1"):
    return {
        "USD/JPY": Quote("USD/JPY", "150", "150", asof, snapshot_id),
        "EUR/JPY": Quote("EUR/JPY", "180", "180", asof, snapshot_id),
        "EUR/USD": Quote("EUR/USD", "1.2", "1.2", asof, snapshot_id),
    }


def portfolio():
    return [
        Trade("eurusd", "EUR/USD", "BUY", "CANDIDATE", "1", "400"),
        Trade("usdjpy", "USD/JPY", "BUY", "POSITION", "1.2", "300"),
        Trade("eurjpy", "EUR/JPY", "SELL", "PENDING", "1", "200"),
    ]


def review(quotes=None, trades=None, **overrides):
    defaults = {
        "asof": 123, "snapshot_id": "synthetic-1",
        "equity_jpy": "100000",
        "positions_reconciled": True, "pending_orders_reconciled": True,
    }
    defaults.update(overrides)
    return review_synthetic_portfolio(prices() if quotes is None else quotes,
                                      portfolio() if trades is None else trades,
                                      **defaults)


class ThreePairOfflineRiskTests(unittest.TestCase):
    def held(self, result):
        self.assertIs(type(result), Review)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertIs(result.safety_hold_latched, True)
        self.assertIs(result.order_allowed, False)
        self.assertIs(result.automatic_retry_allowed, False)
        self.assertIs(result.stop_release_allowed, False)
        self.assertIsNone(result.verified_values)

    def test_triangular_net_zero_never_zeroes_gross_or_asserted_max_loss(self):
        r = review()
        self.assertTrue(r.arithmetic_complete)
        self.assertEqual(dict(r.net_native), {"USD": "0.0", "EUR": "0", "JPY": "0.0"})
        self.assertEqual(dict(r.gross_native), {"USD": "2.4", "EUR": "2", "JPY": "360.0"})
        self.assertEqual(r.gross_currency_legs_jpy, "1080.0")
        self.assertEqual(r.candidate_max_loss_jpy, "400")
        self.assertEqual(r.total_max_loss_jpy, "900")
        self.assertFalse(r.candidate_exceeds_existing_limit)
        self.assertFalse(r.total_exceeds_existing_limit)
        self.assertEqual(r.reason, "SYNTHETIC_ARITHMETIC_ONLY_NOT_AUTHORIZED")
        self.held(r)

    def test_two_legs_resemble_eurjpy_only_at_matching_size_price_and_time(self):
        synthetic_eurusd_usdjpy = [
            Trade("a", "EUR/USD", "BUY", "CANDIDATE", "1", "100"),
            Trade("b", "USD/JPY", "BUY", "POSITION", "1.2", "100"),
        ]
        single_eurjpy = [
            Trade("c", "EUR/JPY", "BUY", "CANDIDATE", "1", "100"),
        ]
        a = review(trades=synthetic_eurusd_usdjpy)
        b = review(trades=single_eurjpy)
        self.assertEqual({currency: Decimal(value) for currency, value in a.net_native},
                         {currency: Decimal(value) for currency, value in b.net_native})
        self.assertNotEqual(a.gross_native, b.gross_native)
        self.assertNotEqual(a.total_max_loss_jpy, b.total_max_loss_jpy)
        self.held(a)
        self.held(b)

    def test_pending_orders_and_candidates_are_not_omitted_or_offset(self):
        p = portfolio()
        r = review(trades=p)
        only_candidate = review(trades=p[:1])
        self.assertEqual(r.total_max_loss_jpy, "900")
        self.assertEqual(only_candidate.total_max_loss_jpy, "400")
        self.assertNotEqual(r.gross_native, only_candidate.gross_native)
        self.held(r)

    def test_partially_hedged_and_one_side_execution_show_residual_risk(self):
        partial = portfolio()[:2]
        net = dict(review(trades=partial).net_native)
        self.assertEqual(net["EUR"], "1")
        self.assertEqual(net["JPY"], "-180.0")
        self.assertEqual(net["USD"], "0.0")
        one_side = review(trades=portfolio()[:1])
        self.assertEqual(dict(one_side.net_native)["USD"], "-1.2")
        self.assertEqual(one_side.total_max_loss_jpy, "400")
        self.held(one_side)

    def test_candidate_limit_and_aggregate_limit_are_not_net_reduced(self):
        p = portfolio()
        p[0] = replace(p[0], max_loss_jpy="501")
        r = review(trades=p)
        self.assertTrue(r.arithmetic_complete)
        self.assertTrue(r.candidate_exceeds_existing_limit)
        self.assertTrue(r.total_exceeds_existing_limit)
        self.assertEqual(r.total_max_loss_jpy, "1001")
        self.assertEqual(r.reason, "EXISTING_HARD_LIMIT_OVER_IN_SYNTHETIC_INPUT")
        self.assertEqual(dict(r.net_native)["EUR"], "0")
        self.held(r)

    def test_exact_existing_equity_percent_threshold_is_informational_only(self):
        p = portfolio()
        p[0] = replace(p[0], max_loss_jpy="500")
        p[1] = replace(p[1], max_loss_jpy="300")
        p[2] = replace(p[2], max_loss_jpy="200")
        r = review(trades=p)
        self.assertFalse(r.candidate_exceeds_existing_limit)
        self.assertFalse(r.total_exceeds_existing_limit)
        self.assertEqual(r.total_max_loss_jpy, "1000")
        self.held(r)

    def test_same_pair_opposing_orders_net_zero_but_do_not_offset_loss(self):
        p = [
            Trade("a", "USD/JPY", "BUY", "CANDIDATE", "1", "400"),
            Trade("b", "USD/JPY", "SELL", "PENDING", "1", "400"),
        ]
        r = review(trades=p)
        self.assertEqual(dict(r.net_native)["USD"], "0")
        self.assertEqual(dict(r.gross_native)["USD"], "2")
        self.assertEqual(r.total_max_loss_jpy, "800")
        self.held(r)

    def test_bid_ask_spread_creates_residual_even_for_equal_opposing_units(self):
        q = prices()
        q["USD/JPY"] = Quote("USD/JPY", "149", "151", 123, "synthetic-1")
        p = [
            Trade("a", "USD/JPY", "BUY", "CANDIDATE", "1", "100"),
            Trade("b", "USD/JPY", "SELL", "POSITION", "1", "100"),
        ]
        r = review(quotes=q, trades=p)
        self.assertEqual(dict(r.net_native)["JPY"], "-2")
        self.assertEqual(dict(r.gross_native)["JPY"], "300")
        self.held(r)

    def test_every_currency_pair_is_required_for_convertibility(self):
        q = prices()
        del q["EUR/USD"]
        r = review(quotes=q)
        self.assertEqual(r.reason, "QUOTE_SET_INCOMPLETE_OR_EXTRA")
        self.assertFalse(r.arithmetic_complete)
        self.held(r)
        q = prices()
        q["GBP/USD"] = Quote("GBP/USD", "1.3", "1.3", 123, "synthetic-1")
        self.assertEqual(review(quotes=q).reason, "QUOTE_SET_INCOMPLETE_OR_EXTRA")

    def test_stale_and_mixed_time_and_source_snapshots_fail_closed(self):
        for mutated in (
            replace(prices()["EUR/USD"], observed_at=122),
            replace(prices()["EUR/USD"], snapshot_id="stale"),
            replace(prices()["EUR/USD"], observed_at=True),
            replace(prices()["EUR/USD"], snapshot_id=None),
        ):
            with self.subTest(mutated=repr(mutated)):
                q = prices()
                q["EUR/USD"] = mutated
                r = review(quotes=q)
                self.assertEqual(r.reason, "STALE_OR_MIXED_PRICE_SNAPSHOT")
                self.assertFalse(r.arithmetic_complete)
                self.held(r)

    def test_invalid_or_crossed_bid_ask_is_not_usable(self):
        for bid, ask in (("151", "150"), ("0", "150"),
                         ("100", "0"), ("NaN", "120"),
                         ("Infinity", "120"), ("1e4", "2e4"),
                         ("100", "-1"), ("", "1")):
            with self.subTest(bid=bid, ask=ask):
                q = prices()
                q["USD/JPY"] = replace(q["USD/JPY"], bid=bid, ask=ask)
                r = review(quotes=q)
                self.assertEqual(r.reason, "INVALID_BID_ASK")
                self.held(r)

    def test_incomplete_broker_position_or_order_snapshot_blocks(self):
        for state in ({"positions_reconciled": False},
                      {"pending_orders_reconciled": False},
                      {"positions_reconciled": None},
                      {"pending_orders_reconciled": 1}):
            with self.subTest(state=state):
                r = review(**state)
                self.assertEqual(r.reason, "ACCOUNT_OR_PENDING_STATE_UNKNOWN")
                self.held(r)

    def test_unapproved_or_missing_pair_is_rejected(self):
        p = portfolio()
        p[0] = replace(p[0], pair="GBP/USD")
        r = review(trades=p)
        self.assertEqual(r.reason, "UNSUPPORTED_PAIR_SIDE_OR_STATUS")
        self.held(r)
        p[0] = replace(p[0], pair="AUD/USD")
        self.assertEqual(review(trades=p).reason, "UNSUPPORTED_PAIR_SIDE_OR_STATUS")

    def test_missing_or_duplicate_candidate_blocks(self):
        p = portfolio()
        p[0] = replace(p[0], status="PENDING")
        self.assertEqual(review(trades=p).reason,
                         "EXACTLY_ONE_NEW_CANDIDATE_REQUIRED")
        p[0] = replace(p[0], status="CANDIDATE")
        p[1] = replace(p[1], status="CANDIDATE")
        self.assertEqual(review(trades=p).reason,
                         "EXACTLY_ONE_NEW_CANDIDATE_REQUIRED")
        self.assertEqual(review(trades=[]).reason, "MISSING_CANDIDATE_OR_TRADES")

    def test_duplicate_id_and_invalid_instrument_attributes_block(self):
        p = portfolio()
        p[1] = replace(p[1], trade_id="eurusd")
        self.assertEqual(review(trades=p).reason, "DUPLICATE_OR_INVALID_TRADE_ID")
        for field, value in (("side", "FLAT"), ("side", None),
                             ("status", "CANCEL_EXPECTED"),
                             ("status", "PARTIALLY_FILLED"),
                             ("pair", None)):
            with self.subTest(field=field, value=value):
                q = portfolio()
                q[0] = replace(q[0], **{field: value})
                self.assertEqual(review(trades=q).reason,
                                 "UNSUPPORTED_PAIR_SIDE_OR_STATUS")

    def test_invalid_quantity_or_loss_cannot_be_repaired_by_netting(self):
        for field, value in (("base_units", "0"), ("base_units", ""),
                             ("base_units", "-1"), ("base_units", "NaN"),
                             ("base_units", 1.0), ("max_loss_jpy", "-1"),
                             ("max_loss_jpy", "Infinity"),
                             ("max_loss_jpy", None), ("max_loss_jpy", 0.1)):
            with self.subTest(field=field, value=value):
                p = portfolio()
                p[0] = replace(p[0], **{field: value})
                r = review(trades=p)
                self.assertEqual(r.reason, "UNVERIFIABLE_SYNTHETIC_QUANTITY_OR_LOSS")
                self.assertFalse(r.arithmetic_complete)
                self.held(r)

    def test_invalid_equity_and_clock_inputs_are_denied(self):
        for eq in ("0", "-1", "NaN", "", "1e5", 100000, None):
            with self.subTest(equity=eq):
                r = review(equity_jpy=eq)
                self.assertEqual(r.reason, "INVALID_SYNTHETIC_EQUITY")
                self.held(r)
        for clock in (True, -1, None, "123"):
            with self.subTest(clock=clock):
                self.assertEqual(review(asof=clock).reason,
                                 "INVALID_SYNTHETIC_SNAPSHOT_IDENTITY")

    def test_invalid_quote_or_trade_container_fails_closed(self):
        self.assertEqual(review(quotes=object()).reason, "QUOTE_SET_INCOMPLETE_OR_EXTRA")
        self.assertEqual(review(trades=object()).reason, "MISSING_CANDIDATE_OR_TRADES")
        q = prices()
        q["USD/JPY"] = object()
        self.assertEqual(review(quotes=q).reason, "INVALID_QUOTE")
        p = portfolio()
        p[0] = object()
        self.assertEqual(review(trades=p).reason, "INVALID_TRADE")

    def test_nonzero_net_in_one_currency_can_coexist_with_other_hedge(self):
        p = portfolio()
        p[2] = replace(p[2], base_units="0.5")
        r = review(trades=p)
        native = dict(r.net_native)
        self.assertEqual(native["EUR"], "0.5")
        self.assertEqual(native["USD"], "0.0")
        self.assertEqual(native["JPY"], "-90.0")
        self.assertEqual(r.total_max_loss_jpy, "900")
        self.held(r)


if __name__ == "__main__":
    unittest.main()
