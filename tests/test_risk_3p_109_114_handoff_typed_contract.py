"""RISK-3P-109..114: exact types and fields for fake FX risk handoff.

In-memory synthetic fixtures only. Malicious __eq__ methods in report
values must not be evaluated. All paths retain NO_GO, BLOCKED, no orders.
"""
from __future__ import annotations

from collections import namedtuple
from dataclasses import replace
from decimal import Context, Decimal, localcontext
import unittest

from scripts import phase1_three_pair_synthetic_risk as pf
from scripts import phase1_three_pair_synthetic_stop_conversion as sl


def fixture(*, cost="5"):
    c = {p: sl.Contract(p, "100000", "0.01", "0.01", "1")
         for p in sl.PAIRS}
    q = {
        "USD/JPY": sl.Quote("USD/JPY", "150", "151", 42, "SIM-TYPED"),
        "EUR/JPY": sl.Quote("EUR/JPY", "181", "182", 42, "SIM-TYPED"),
        "EUR/USD": sl.Quote("EUR/USD", "1.20", "1.21", 42, "SIM-TYPED"),
    }
    ts = [
        sl.Ticket("c", "EUR/USD", "BUY", "CANDIDATE",
                  "0.01", "1.2000", "1.1990", "0.0001", cost, "SIM-TYPED"),
        sl.Ticket("o", "USD/JPY", "SELL", "POSITION",
                  "0.01", "150", "150.05", "0.01", "0", "SIM-TYPED"),
        sl.Ticket("p", "EUR/JPY", "BUY", "PENDING",
                  "0.01", "181", "180.9", "0.01", "0", "SIM-TYPED"),
    ]
    stop_result = sl.review_synthetic_stop_risk(
        c, q, ts, equity_jpy="100000", asof=42, snapshot_id="SIM-TYPED",
        positions_reconciled=True, pending_reconciled=True,
        inflight_reservations_reconciled=True)
    assert stop_result.illustrative_complete
    pq = {p: pf.Quote(row.pair, row.bid, row.ask, row.observed_at,
                      row.snapshot_id) for p, row in q.items()}
    amounts = dict(stop_result.per_ticket_illustrative_loss_jpy)
    with localcontext(Context(prec=96)):
        trades = [
            pf.Trade(t.ticket_id, t.pair, t.side, t.status,
                     str(Decimal(t.volume_lots)
                         * Decimal(c[t.pair].base_units_per_lot)),
                     amounts[t.ticket_id])
            for t in ts
        ]
    portfolio_result = pf.review_synthetic_portfolio(
        pq, trades, equity_jpy="100000", asof=42,
        snapshot_id="SIM-TYPED", positions_reconciled=True,
        pending_orders_reconciled=True)
    assert portfolio_result.arithmetic_complete
    return dict(
        contracts=c, stop_quotes=q, tickets=ts, stop_result=stop_result,
        portfolio_quotes=pq, trades=trades,
        portfolio_result=portfolio_result,
        asof=42, snapshot_id="SIM-TYPED", equity_jpy="100000",
        positions_reconciled=True, pending_reconciled=True,
        inflight_reconciled=True,
    )


class TrapOnEquality:
    def __eq__(self, other):
        raise AssertionError("untrusted __eq__ was called")

    def __ne__(self, other):
        raise AssertionError("untrusted __ne__ was called")


class MaliciousText(str):
    def __eq__(self, other):
        raise AssertionError("text __eq__ should not execute")


class HandoffTypedContractTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture()

    def check_no_go(self, result, *, accepted=False):
        self.assertIs(type(result), pf.SyntheticHandoffReview)
        self.assertIs(result.mock_binding_consistent, accepted)
        self.assertIs(result.independent_broker_origin_verified, False)
        self.assertIs(result.human_p05_signoff, False)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertIs(result.safety_hold_latched, True)
        self.assertIs(result.order_allowed, False)
        self.assertIs(result.stop_release_allowed, False)
        self.assertIs(result.automatic_retry_allowed, False)
        self.assertIsNone(result.verified_values)

    def reject(self, edit, code="P109_MOCK_TYPED_REPORT_DRIFT"):
        args = dict(self.base)
        edit(args)
        result = pf.review_synthetic_loss_handoff(**args)
        self.assertEqual(result.reason, code, result)
        self.check_no_go(result)
        self.assertEqual(result.mock_records_bound, 0)

    def test_baseline_still_binds_only_offline_and_not_production(self):
        result = pf.review_synthetic_loss_handoff(**self.base)
        self.assertEqual(result.reason, "PASS_OFFLINE_MOCK_BINDING_ONLY")
        self.assertEqual(result.mock_records_bound, 3)
        self.check_no_go(result, accepted=True)

    def test_false_candidate_limit_flags_changed_to_zero_on_both_outputs(self):
        self.assertIs(self.base["stop_result"].candidate_exceeds_existing_fraction, False)
        self.assertIs(self.base["portfolio_result"].candidate_exceeds_existing_limit, False)
        def edit(args):
            args["stop_result"] = replace(
                args["stop_result"], candidate_exceeds_existing_fraction=0)
            args["portfolio_result"] = replace(
                args["portfolio_result"], candidate_exceeds_existing_limit=0)
        self.reject(edit)

    def test_false_aggregate_limit_flags_changed_to_zero_on_both_outputs(self):
        def edit(args):
            args["stop_result"] = replace(
                args["stop_result"], aggregate_exceeds_existing_fraction=0)
            args["portfolio_result"] = replace(
                args["portfolio_result"], total_exceeds_existing_limit=0)
        self.reject(edit)

    def test_true_candidate_flag_changed_to_integer_one_on_both_outputs(self):
        args = fixture(cost="505")
        self.assertIs(args["stop_result"].candidate_exceeds_existing_fraction, True)
        self.assertIs(args["portfolio_result"].candidate_exceeds_existing_limit, True)
        args["stop_result"] = replace(
            args["stop_result"], candidate_exceeds_existing_fraction=1)
        args["portfolio_result"] = replace(
            args["portfolio_result"], candidate_exceeds_existing_limit=1)
        result = pf.review_synthetic_loss_handoff(**args)
        self.assertEqual(result.reason, "P109_MOCK_TYPED_REPORT_DRIFT")
        self.check_no_go(result)

    def test_float_false_flag_same_identity_on_both_reports_still_rejected(self):
        zero = 0.0
        def edit(args):
            args["stop_result"] = replace(
                args["stop_result"], candidate_exceeds_existing_fraction=zero)
            args["portfolio_result"] = replace(
                args["portfolio_result"], candidate_exceeds_existing_limit=zero)
        self.reject(edit)

    def test_extra_stop_report_attribute_is_not_ignored_by_dataclass_equality(self):
        def edit(args):
            object.__setattr__(args["stop_result"],
                               "unreviewed_real_trade_authorized", True)
        self.reject(edit)

    def test_extra_portfolio_attribute_does_not_leak_private_canary(self):
        secret = "PRIVATE_FAKE_CANARY_109"
        def edit(args):
            object.__setattr__(args["portfolio_result"], "password", secret)
        args = dict(self.base)
        edit(args)
        result = pf.review_synthetic_loss_handoff(**args)
        self.assertEqual(result.reason, "P109_MOCK_TYPED_REPORT_DRIFT")
        self.assertNotIn(secret, str(result))
        self.check_no_go(result)

    def test_tuple_subclass_in_net_native_cannot_pass_equal_value(self):
        def edit(args):
            value = args["portfolio_result"]
            args["portfolio_result"] = replace(
                value, net_native=tuple(
                    namedtuple("CurrencyAmount", "ccy amount")(*row)
                    for row in value.net_native))
        self.reject(edit)

    def test_tuple_subclass_in_gross_native_cannot_pass_equal_value(self):
        def edit(args):
            value = args["portfolio_result"]
            class PretendTuple(tuple):
                pass
            args["portfolio_result"] = replace(
                value, gross_native=tuple(
                    PretendTuple(row) for row in value.gross_native))
        self.reject(edit)

    def test_str_subclass_inside_a_numeric_claim_is_rejected(self):
        class PretendStr(str):
            pass
        def edit(args):
            args["portfolio_result"] = replace(
                args["portfolio_result"],
                gross_currency_legs_jpy=PretendStr(
                    args["portfolio_result"].gross_currency_legs_jpy))
        self.reject(edit)

    def test_malicious_custom_eq_in_portfolio_report_is_never_run(self):
        def edit(args):
            args["portfolio_result"] = replace(
                args["portfolio_result"], net_native=TrapOnEquality())
        self.reject(edit)

    def test_malicious_custom_eq_in_stop_report_is_never_run(self):
        def edit(args):
            args["stop_result"] = replace(
                args["stop_result"], quote_conversion_method=TrapOnEquality())
        self.reject(edit, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_malicious_string_subclass_in_reason_is_rejected_without_eq(self):
        def edit(args):
            args["stop_result"] = replace(
                args["stop_result"],
                reason=MaliciousText(args["stop_result"].reason))
        self.reject(edit, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_missing_checked_stop_field_is_fail_closed_not_exception(self):
        def edit(args):
            object.__delattr__(args["stop_result"], "reason")
        self.reject(edit, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_missing_unchecked_stop_field_is_fail_closed_not_exception(self):
        def edit(args):
            object.__delattr__(args["stop_result"],
                               "per_ticket_illustrative_loss_jpy")
        self.reject(edit, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_missing_portfolio_field_is_fail_closed_not_exception(self):
        def edit(args):
            object.__delattr__(args["portfolio_result"], "net_native")
        self.reject(edit, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_missing_stop_numeric_report_becomes_fail_closed(self):
        def edit(args):
            object.__delattr__(args["stop_result"],
                               "total_illustrative_loss_jpy")
        self.reject(edit, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_string_loss_change_preserves_previous_drift_error_code(self):
        def edit(args):
            args["portfolio_result"] = replace(
                args["portfolio_result"], total_max_loss_jpy="42")
        self.reject(edit, "P103_MOCK_TOTAL_OR_LIMIT_DRIFT")

    def test_both_totals_forged_preserve_previous_recomputation_error(self):
        def edit(args):
            args["stop_result"] = replace(
                args["stop_result"], total_illustrative_loss_jpy="50")
            args["portfolio_result"] = replace(
                args["portfolio_result"], total_max_loss_jpy="50")
        self.reject(edit, "P103_MOCK_RECOMPUTATION_MISMATCH")

    def test_explicit_type_and_unknown_fields_guard_is_pure(self):
        a = self.base["portfolio_result"]
        b = replace(a)
        self.assertTrue(pf._mock_report_type_shape(a, b))
        self.assertTrue(pf._exact_mock_structure(a, b))
        self.assertFalse(pf._mock_report_type_shape(
            replace(a, net_native=TrapOnEquality()), b))

    def test_false_zero_are_not_equal_under_strict_helper(self):
        self.assertFalse(pf._exact_mock_structure(False, 0))
        self.assertFalse(pf._exact_mock_structure(True, 1))
        self.assertFalse(pf._mock_report_type_shape(False, 0))
        self.assertFalse(pf._exact_mock_structure(
            ("USD", "1"), ["USD", "1"]))

    def test_stop_report_forged_production_flag_stays_refused(self):
        def edit(args):
            args["stop_result"] = replace(
                args["stop_result"], result_authorizes_trade=1)
        self.reject(edit, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_all_report_assertions_remain_no_go_after_type_fix(self):
        r = pf.review_synthetic_loss_handoff(**self.base)
        self.check_no_go(r, accepted=True)
        self.assertFalse(self.base["stop_result"].broker_contract_verified)
        self.assertFalse(self.base["stop_result"].stop_execution_guaranteed)
        self.assertFalse(self.base["portfolio_result"].order_allowed)


if __name__ == "__main__":
    unittest.main()
