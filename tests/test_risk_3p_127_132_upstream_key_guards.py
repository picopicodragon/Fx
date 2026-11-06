"""RISK-3P-127..132: upstream synthetic arithmetic rejects hostile keys/fields.

All data are fictional and in-memory. This protects checks on previously
constructed built-in dictionaries only. It is not a Python sandbox and
cannot authenticate real broker contracts, prices, positions, or orders.
"""
from __future__ import annotations

from dataclasses import replace
import unittest

from scripts import phase1_three_pair_synthetic_risk as portfolio
from scripts import phase1_three_pair_synthetic_stop_conversion as stop


class PoisonString(str):
    hashes = 0
    comparisons = 0

    def __hash__(self):
        type(self).hashes += 1
        return hash(str(self))

    def __eq__(self, other):
        type(self).comparisons += 1
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_127")

    def __ne__(self, other):
        type(self).comparisons += 1
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_127")


class PoisonKey:
    hashes = 0
    comparisons = 0

    def __hash__(self):
        type(self).hashes += 1
        return hash("USD/JPY")

    def __eq__(self, other):
        type(self).comparisons += 1
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_127")

    def __ne__(self, other):
        type(self).comparisons += 1
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_127")


class PoisonPair:
    comparisons = 0

    def __eq__(self, other):
        type(self).comparisons += 1
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_127")

    def __ne__(self, other):
        type(self).comparisons += 1
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_127")


class PoisonDict(dict):
    iterations = 0

    def __iter__(self):
        type(self).iterations += 1
        raise RuntimeError("SYNTHETIC_SECRET_CANARY_127")


def quotes():
    return {
        "USD/JPY": portfolio.Quote("USD/JPY", "150", "151", 127, "SIM-127"),
        "EUR/JPY": portfolio.Quote("EUR/JPY", "181", "182", 127, "SIM-127"),
        "EUR/USD": portfolio.Quote("EUR/USD", "1.20", "1.21", 127, "SIM-127"),
    }


def contracts():
    return {pair: stop.Contract(pair, "100000", "0.01", "0.01", "1")
            for pair in stop.PAIRS}


def stop_quotes():
    return {p: stop.Quote(q.pair, q.bid, q.ask, q.observed_at, q.snapshot_id)
            for p, q in quotes().items()}


def trades():
    return [portfolio.Trade("new", "EUR/USD", "BUY", "CANDIDATE",
                            "1000", "100")]


def tickets():
    return [stop.Ticket("new", "EUR/USD", "BUY", "CANDIDATE",
                        "0.01", "1.2000", "1.1990", "0.0001", "5",
                        "SIM-127")]


# Explicit None is a malformed argument to exercise, NOT an omitted fixture.
_OMITTED = object()


def run_portfolio(q=_OMITTED):
    return portfolio.review_synthetic_portfolio(
        quotes() if q is _OMITTED else q, trades(), equity_jpy="100000",
        asof=127, snapshot_id="SIM-127",
        positions_reconciled=True, pending_orders_reconciled=True)


def run_stop(c=_OMITTED, q=_OMITTED):
    return stop.review_synthetic_stop_risk(
        contracts() if c is _OMITTED else c,
        stop_quotes() if q is _OMITTED else q,
        tickets(), equity_jpy="100000", asof=127, snapshot_id="SIM-127",
        positions_reconciled=True, pending_reconciled=True,
        inflight_reservations_reconciled=True)


def new_key_map(original, key):
    copy = dict(original)
    original_value = copy.pop("USD/JPY")
    copy[key] = original_value
    # Key insertion is outside the checked API and may hash the injected key.
    # Only accesses *after* this reset are asserted not to execute poison code.
    PoisonString.hashes = PoisonString.comparisons = 0
    PoisonKey.hashes = PoisonKey.comparisons = 0
    return copy


class UpstreamGuardTests(unittest.TestCase):
    def setUp(self):
        PoisonString.hashes = PoisonString.comparisons = 0
        PoisonKey.hashes = PoisonKey.comparisons = 0
        PoisonPair.comparisons = 0
        PoisonDict.iterations = 0

    def held(self, r, *, reason=None, complete=False):
        if reason is not None:
            self.assertEqual(r.reason, reason)
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.stop_release_allowed)
        self.assertFalse(r.automatic_retry_allowed)
        self.assertIsNone(r.verified_values)
        if type(r) is portfolio.Review:
            self.assertEqual(r.arithmetic_complete, complete)
        else:
            self.assertEqual(r.illustrative_complete, complete)
            self.assertFalse(r.result_authorizes_trade)
            self.assertFalse(r.broker_contract_verified)
        self.assertNotIn("SYNTHETIC_SECRET_CANARY_127", str(r))

    def counters_unchanged(self):
        self.assertEqual(PoisonString.hashes, 0)
        self.assertEqual(PoisonString.comparisons, 0)
        self.assertEqual(PoisonKey.hashes, 0)
        self.assertEqual(PoisonKey.comparisons, 0)
        self.assertEqual(PoisonPair.comparisons, 0)
        self.assertEqual(PoisonDict.iterations, 0)

    def test_normal_three_pair_portfolio_still_blocked_without_errors(self):
        r = run_portfolio()
        self.held(r, complete=True)
        self.counters_unchanged()

    def test_normal_three_pair_stop_still_blocked_without_errors(self):
        r = run_stop()
        self.held(r, complete=True)
        self.counters_unchanged()

    def test_portfolio_quote_string_subclass_key_never_rehashed(self):
        q = new_key_map(quotes(), PoisonString("USD/JPY"))
        self.held(run_portfolio(q), reason="QUOTE_SET_INCOMPLETE_OR_EXTRA")
        self.counters_unchanged()

    def test_portfolio_quote_object_key_never_rehashed(self):
        q = new_key_map(quotes(), PoisonKey())
        self.held(run_portfolio(q), reason="QUOTE_SET_INCOMPLETE_OR_EXTRA")
        self.counters_unchanged()

    def test_stop_contract_string_subclass_key_never_rehashed(self):
        c = new_key_map(contracts(), PoisonString("USD/JPY"))
        self.held(run_stop(c=c), reason="CONTRACT_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_stop_contract_object_key_never_rehashed(self):
        c = new_key_map(contracts(), PoisonKey())
        self.held(run_stop(c=c), reason="CONTRACT_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_stop_quote_string_subclass_key_never_rehashed(self):
        q = new_key_map(stop_quotes(), PoisonString("USD/JPY"))
        self.held(run_stop(q=q), reason="QUOTE_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_stop_quote_object_key_never_rehashed(self):
        q = new_key_map(stop_quotes(), PoisonKey())
        self.held(run_stop(q=q), reason="QUOTE_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_multiple_malicious_map_keys_are_rejected_at_first_boundary(self):
        c = new_key_map(contracts(), PoisonKey())
        q = new_key_map(stop_quotes(), PoisonString("USD/JPY"))
        self.held(run_stop(c=c, q=q), reason="CONTRACT_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_malicious_dict_subclasses_are_not_iterated(self):
        q = PoisonDict(quotes())
        self.held(run_portfolio(q), reason="QUOTE_SET_INCOMPLETE_OR_EXTRA")
        self.held(run_stop(c=PoisonDict(contracts())),
                  reason="CONTRACT_SET_INCOMPLETE")
        self.held(run_stop(q=PoisonDict(stop_quotes())),
                  reason="QUOTE_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_portfolio_quote_pair_field_object_never_compared(self):
        q = quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], pair=PoisonPair())
        self.held(run_portfolio(q), reason="INVALID_QUOTE")
        self.counters_unchanged()

    def test_stop_contract_pair_field_object_never_compared(self):
        c = contracts()
        c["EUR/USD"] = replace(c["EUR/USD"], pair=PoisonPair())
        self.held(run_stop(c=c), reason="INVALID_SYNTHETIC_CONTRACT")
        self.counters_unchanged()

    def test_stop_quote_pair_field_object_never_compared(self):
        q = stop_quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], pair=PoisonPair())
        self.held(run_stop(q=q), reason="INVALID_QUOTE")
        self.counters_unchanged()

    def test_str_subclass_in_portfolio_quote_pair_field_refused(self):
        q = quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], pair=PoisonString("EUR/USD"))
        PoisonString.hashes = PoisonString.comparisons = 0
        self.held(run_portfolio(q), reason="INVALID_QUOTE")
        self.counters_unchanged()

    def test_str_subclass_in_stop_contract_pair_field_refused(self):
        c = contracts()
        c["USD/JPY"] = replace(c["USD/JPY"], pair=PoisonString("USD/JPY"))
        PoisonString.hashes = PoisonString.comparisons = 0
        self.held(run_stop(c=c), reason="INVALID_SYNTHETIC_CONTRACT")
        self.counters_unchanged()

    def test_str_subclass_in_stop_quote_pair_field_refused(self):
        q = stop_quotes()
        q["USD/JPY"] = replace(q["USD/JPY"], pair=PoisonString("USD/JPY"))
        PoisonString.hashes = PoisonString.comparisons = 0
        self.held(run_stop(q=q), reason="INVALID_QUOTE")
        self.counters_unchanged()

    def test_bool_key_not_equivalent_to_string_key(self):
        for key in (True, False, 0, 1, None):
            with self.subTest(key=key):
                q = new_key_map(quotes(), key)
                self.held(run_portfolio(q), reason="QUOTE_SET_INCOMPLETE_OR_EXTRA")
                self.counters_unchanged()

    def test_other_collection_types_fail_before_iteration(self):
        for source in ([], tuple(), None, "USD/JPY"):
            with self.subTest(value=repr(source)):
                self.held(run_portfolio(source),
                          reason="QUOTE_SET_INCOMPLETE_OR_EXTRA")
                self.held(run_stop(c=source), reason="CONTRACT_SET_INCOMPLETE")
                self.held(run_stop(q=source), reason="QUOTE_SET_INCOMPLETE")
                self.counters_unchanged()

    def test_missing_required_pair_refused_in_each_upstream_map(self):
        q = quotes()
        q.pop("USD/JPY")
        self.held(run_portfolio(q), reason="QUOTE_SET_INCOMPLETE_OR_EXTRA")
        c = contracts()
        c.pop("EUR/USD")
        self.held(run_stop(c=c), reason="CONTRACT_SET_INCOMPLETE")
        sq = stop_quotes()
        sq.pop("EUR/JPY")
        self.held(run_stop(q=sq), reason="QUOTE_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_unknown_extra_pair_refused_in_each_upstream_map(self):
        q = quotes()
        q["GBP/USD"] = q["EUR/USD"]
        self.held(run_portfolio(q), reason="QUOTE_SET_INCOMPLETE_OR_EXTRA")
        c = contracts()
        c["GBP/USD"] = c["EUR/USD"]
        self.held(run_stop(c=c), reason="CONTRACT_SET_INCOMPLETE")
        sq = stop_quotes()
        sq["GBP/USD"] = sq["EUR/USD"]
        self.held(run_stop(q=sq), reason="QUOTE_SET_INCOMPLETE")
        self.counters_unchanged()

    def test_plain_wrong_pair_label_in_quote_fields_refused(self):
        q = quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], pair="GBP/USD")
        self.held(run_portfolio(q), reason="INVALID_QUOTE")
        sq = stop_quotes()
        sq["EUR/USD"] = replace(sq["EUR/USD"], pair="GBP/USD")
        self.held(run_stop(q=sq), reason="INVALID_QUOTE")
        self.counters_unchanged()

    def test_plain_wrong_pair_label_in_contract_refused(self):
        c = contracts()
        c["EUR/USD"] = replace(c["EUR/USD"], pair="GBP/USD")
        self.held(run_stop(c=c), reason="INVALID_SYNTHETIC_CONTRACT")
        self.counters_unchanged()

    def test_stop_unknown_timestamp_and_snapshot_stay_rejected(self):
        q = stop_quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], observed_at=True)
        self.held(run_stop(q=q), reason="STALE_OR_MIXED_QUOTE")
        self.counters_unchanged()

    def test_portfolio_unknown_timestamp_and_snapshot_stay_rejected(self):
        q = quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], snapshot_id="SIM-OTHER")
        self.held(run_portfolio(q), reason="STALE_OR_MIXED_PRICE_SNAPSHOT")
        self.counters_unchanged()

    def test_quoted_price_object_not_promoted_or_executed(self):
        q = quotes()
        q["EUR/USD"] = replace(q["EUR/USD"], bid=PoisonPair())
        self.held(run_portfolio(q), reason="INVALID_BID_ASK")
        sq = stop_quotes()
        sq["EUR/USD"] = replace(sq["EUR/USD"], ask=PoisonPair())
        self.held(run_stop(q=sq), reason="INVALID_BID_ASK")
        self.counters_unchanged()

    def test_stop_contract_numeric_object_refused_without_code_execution(self):
        c = contracts()
        c["EUR/USD"] = replace(c["EUR/USD"], min_lot=PoisonPair())
        self.held(run_stop(c=c), reason="CONTRACT_ATTRIBUTES_UNKNOWN")
        self.counters_unchanged()

    def test_stop_reconciled_false_always_no_go_even_normal_map(self):
        r = stop.review_synthetic_stop_risk(
            contracts(), stop_quotes(), tickets(), equity_jpy="100000",
            asof=127, snapshot_id="SIM-127",
            positions_reconciled=True, pending_reconciled=False,
            inflight_reservations_reconciled=True)
        self.held(r, reason="BROKER_OR_INFLIGHT_STATE_UNKNOWN")

    def test_portfolio_reconciled_false_always_no_go_even_normal_map(self):
        r = portfolio.review_synthetic_portfolio(
            quotes(), trades(), equity_jpy="100000",
            asof=127, snapshot_id="SIM-127",
            positions_reconciled=True, pending_orders_reconciled=False)
        self.held(r, reason="ACCOUNT_OR_PENDING_STATE_UNKNOWN")

    def test_three_pair_scope_and_existing_precision_preserved(self):
        self.assertEqual(stop.PAIRS, portfolio.PAIRS)
        self.assertEqual(stop.PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))
        self.assertEqual(portfolio.DECIMAL_WORK_PRECISION, 256)
        self.assertEqual(stop.DECIMAL_WORK_PRECISION, 96)
        self.held(run_portfolio(), complete=True)
        self.held(run_stop(), complete=True)


if __name__ == "__main__":
    unittest.main()
