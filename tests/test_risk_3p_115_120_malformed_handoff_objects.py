"""RISK-3P-115..120: hostile objects in *fictional* loss handoff data.

All mock fixtures are locally constructed. No broker, market, filesystem,
accounts, MT4, orders or permission changes. A successful mock binding is
never production authorization.
"""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch
import unittest

from scripts import phase1_three_pair_synthetic_risk as pf
from scripts import phase1_three_pair_synthetic_stop_conversion as sl


class DangerousComparison:
    """Would raise or run untrusted code if compared by a dataclass __eq__."""
    calls = 0

    def __eq__(self, other):
        type(self).calls += 1
        raise RuntimeError("PRIVATE_CANARY_115_COMPARISON_CALLED")


def fixtures():
    contracts = {
        pair: sl.Contract(pair, "100000", "0.01", "0.01", "1")
        for pair in sl.PAIRS
    }
    q = {
        "USD/JPY": sl.Quote("USD/JPY", "150", "151", 42, "SIM-P115"),
        "EUR/JPY": sl.Quote("EUR/JPY", "181", "182", 42, "SIM-P115"),
        "EUR/USD": sl.Quote("EUR/USD", "1.20", "1.21", 42, "SIM-P115"),
    }
    ts = [
        sl.Ticket("new", "EUR/USD", "BUY", "CANDIDATE", "0.01",
                  "1.2000", "1.1990", "0.0001", "5", "SIM-P115"),
        sl.Ticket("old", "USD/JPY", "SELL", "POSITION", "0.01",
                  "150", "150.05", "0.01", "0", "SIM-P115"),
        sl.Ticket("pending", "EUR/JPY", "BUY", "PENDING", "0.01",
                  "181", "180.9", "0.01", "0", "SIM-P115"),
    ]
    stop_result = sl.review_synthetic_stop_risk(
        contracts, q, ts, equity_jpy="100000", asof=42,
        snapshot_id="SIM-P115", positions_reconciled=True,
        pending_reconciled=True, inflight_reservations_reconciled=True)
    pq = {pair: pf.Quote(row.pair, row.bid, row.ask,
                          row.observed_at, row.snapshot_id)
          for pair, row in q.items()}
    rows = dict(stop_result.per_ticket_illustrative_loss_jpy)
    trades = [
        pf.Trade("new", "EUR/USD", "BUY", "CANDIDATE", "1000", rows["new"]),
        pf.Trade("old", "USD/JPY", "SELL", "POSITION", "1000", rows["old"]),
        pf.Trade("pending", "EUR/JPY", "BUY", "PENDING", "1000",
                 rows["pending"]),
    ]
    pf_result = pf.review_synthetic_portfolio(
        pq, trades, equity_jpy="100000", asof=42,
        snapshot_id="SIM-P115", positions_reconciled=True,
        pending_orders_reconciled=True)
    return dict(
        contracts=contracts, stop_quotes=q, tickets=ts,
        stop_result=stop_result, portfolio_quotes=pq, trades=trades,
        portfolio_result=pf_result, asof=42, snapshot_id="SIM-P115",
        equity_jpy="100000", positions_reconciled=True,
        pending_reconciled=True, inflight_reconciled=True,
    )


class PureMockTypeGuardTests(unittest.TestCase):
    def setUp(self):
        DangerousComparison.calls = 0
        self.base = fixtures()

    def reject(self, edits, expected):
        d = dict(self.base)
        edits(d)
        r = pf.review_synthetic_loss_handoff(**d)
        self.assertEqual(r.reason, expected)
        self.assertFalse(r.mock_binding_consistent)
        self.assertEqual(r.mock_records_bound, 0)
        self.assertFalse(r.independent_broker_origin_verified)
        self.assertFalse(r.human_p05_signoff)
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.automatic_retry_allowed)
        self.assertFalse(r.stop_release_allowed)
        self.assertIsNone(r.verified_values)
        self.assertEqual(DangerousComparison.calls, 0)
        self.assertNotIn("PRIVATE_CANARY_115", repr(r))

    def test_baseline_inert_mock_pass_is_not_order_permission(self):
        r = pf.review_synthetic_loss_handoff(**self.base)
        self.assertEqual(r.reason, "PASS_OFFLINE_MOCK_BINDING_ONLY")
        self.assertTrue(r.mock_binding_consistent)
        self.assertEqual(r.mock_records_bound, 3)
        self.assertFalse(r.independent_broker_origin_verified)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.human_p05_signoff)
        self.assertEqual(r.runtime_go_no_go, "NO_GO")

    def test_stop_report_reason_object_does_not_run_custom_equality(self):
        self.reject(lambda d: d.update(stop_result=replace(
            d["stop_result"], reason=DangerousComparison())),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_portfolio_report_reason_object_does_not_run_custom_equality(self):
        self.reject(lambda d: d.update(portfolio_result=replace(
            d["portfolio_result"], reason=DangerousComparison())),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_stop_report_status_object_does_not_run_custom_equality(self):
        self.reject(lambda d: d.update(stop_result=replace(
            d["stop_result"], runtime_go_no_go=DangerousComparison())),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_portfolio_report_status_object_does_not_run_custom_equality(self):
        self.reject(lambda d: d.update(portfolio_result=replace(
            d["portfolio_result"], runtime_go_no_go=DangerousComparison())),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_forged_non_boolean_order_permission_is_rejected(self):
        self.reject(lambda d: d.update(portfolio_result=replace(
            d["portfolio_result"], order_allowed=0)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_forged_non_boolean_stop_release_is_rejected(self):
        self.reject(lambda d: d.update(stop_result=replace(
            d["stop_result"], stop_release_allowed=0)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_stop_loss_row_object_does_not_escape_type_boundary(self):
        def change(d):
            rows = list(d["stop_result"].per_ticket_illustrative_loss_jpy)
            rows[0] = ("new", DangerousComparison())
            d["stop_result"] = replace(
                d["stop_result"], per_ticket_illustrative_loss_jpy=tuple(rows))
        self.reject(change, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_portfolio_native_leg_object_does_not_escape_type_boundary(self):
        def change(d):
            items = list(d["portfolio_result"].net_native)
            items[0] = ("USD", DangerousComparison())
            d["portfolio_result"] = replace(
                d["portfolio_result"], net_native=tuple(items))
        self.reject(change, "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_portfolio_native_leg_list_instead_of_tuple_is_refused(self):
        self.reject(lambda d: d.update(portfolio_result=replace(
            d["portfolio_result"], gross_native=[("USD", "1")])),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_report_overlong_text_is_not_echoed(self):
        self.reject(lambda d: d.update(stop_result=replace(
            d["stop_result"], reason="PRIVATE_CANARY_115" * 40)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_report_tuple_over_128_rows_refused(self):
        self.reject(lambda d: d.update(stop_result=replace(
            d["stop_result"], per_ticket_illustrative_loss_jpy=
            (("new", "1"),) * 129)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_stop_quote_bid_object_cannot_trigger_comparator(self):
        def change(d):
            q = dict(d["stop_quotes"])
            q["USD/JPY"] = replace(q["USD/JPY"], bid=DangerousComparison())
            d["stop_quotes"] = q
        self.reject(change, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")

    def test_portfolio_quote_ask_object_cannot_trigger_comparator(self):
        def change(d):
            q = dict(d["portfolio_quotes"])
            q["EUR/USD"] = replace(q["EUR/USD"], ask=DangerousComparison())
            d["portfolio_quotes"] = q
        self.reject(change, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")

    def test_quote_timestamp_as_boolean_is_rejected(self):
        def change(d):
            q = dict(d["stop_quotes"])
            q["USD/JPY"] = replace(q["USD/JPY"], observed_at=True)
            d["stop_quotes"] = q
        self.reject(change, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")

    def test_quote_pair_object_is_rejected_without_equality(self):
        def change(d):
            q = dict(d["stop_quotes"])
            q["EUR/JPY"] = replace(q["EUR/JPY"], pair=DangerousComparison())
            d["stop_quotes"] = q
        self.reject(change, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")

    def test_contract_pair_object_is_rejected_before_recomputation(self):
        def change(d):
            contracts = dict(d["contracts"])
            contracts["EUR/JPY"] = replace(
                contracts["EUR/JPY"], pair=DangerousComparison())
            d["contracts"] = contracts
        self.reject(change, "P103_MOCK_CONTRACT_FIELD_INVALID")

    def test_contract_numeric_object_is_rejected_before_recomputation(self):
        def change(d):
            contracts = dict(d["contracts"])
            contracts["EUR/USD"] = replace(
                contracts["EUR/USD"], max_lot=DangerousComparison())
            d["contracts"] = contracts
        self.reject(change, "P103_MOCK_CONTRACT_FIELD_INVALID")

    def test_ticket_id_object_is_rejected_before_comparing_report_rows(self):
        def change(d):
            ts = list(d["tickets"])
            ts[0] = replace(ts[0], ticket_id=DangerousComparison())
            d["tickets"] = ts
        self.reject(change, "P103_MOCK_IDENTITY_OR_ORDER_CHANGED")

    def test_ticket_quantity_object_is_rejected_before_decimal_parse(self):
        def change(d):
            ts = list(d["tickets"])
            ts[0] = replace(ts[0], volume_lots=DangerousComparison())
            d["tickets"] = ts
        self.reject(change, "P103_MOCK_UNPARSABLE_AMOUNT")

    def test_trade_id_object_is_rejected_before_equal_comparison(self):
        def change(d):
            ts = list(d["trades"])
            ts[0] = replace(ts[0], trade_id=DangerousComparison())
            d["trades"] = ts
        self.reject(change, "P103_MOCK_IDENTITY_OR_ORDER_CHANGED")

    def test_trade_loss_object_is_rejected_before_fraction_constructor(self):
        def change(d):
            ts = list(d["trades"])
            ts[0] = replace(ts[0], max_loss_jpy=DangerousComparison())
            d["trades"] = ts
        self.reject(change, "P103_MOCK_UNPARSABLE_AMOUNT")

    def test_snapshot_object_is_rejected_before_recompute(self):
        self.reject(lambda d: d.update(snapshot_id=DangerousComparison()),
                    "P103_MOCK_SNAPSHOT_OR_EQUITY_INVALID")

    def test_equity_object_is_rejected_before_recompute(self):
        self.reject(lambda d: d.update(equity_jpy=DangerousComparison()),
                    "P103_MOCK_SNAPSHOT_OR_EQUITY_INVALID")

    def test_bogus_timestamp_bool_is_rejected_before_recompute(self):
        self.reject(lambda d: d.update(asof=True),
                    "P103_MOCK_SNAPSHOT_OR_EQUITY_INVALID")

    def test_recomputation_fault_from_stop_is_a_fixed_fail_closed_code(self):
        with patch.object(pf.stop_conversion, "review_synthetic_stop_risk",
                          side_effect=RuntimeError("PRIVATE_CANARY_115")):
            self.reject(lambda d: None, "P103_MOCK_RECOMPUTATION_EXCEPTION")

    def test_recomputation_fault_from_portfolio_is_a_fixed_fail_closed_code(self):
        with patch.object(pf, "review_synthetic_portfolio",
                          side_effect=ValueError("PRIVATE_CANARY_115")):
            self.reject(lambda d: None, "P103_MOCK_RECOMPUTATION_EXCEPTION")

    def test_unknown_string_reconciliation_does_not_promote(self):
        self.reject(lambda d: d.update(inflight_reconciled="yes"),
                    "P103_UNKNOWN_MOCK_RECONCILIATION")

    def test_unprintable_snapshot_rejected_without_echoing_text(self):
        self.reject(lambda d: d.update(
            snapshot_id="PRIVATE_CANARY_115" + chr(10) + "next"),
            "P103_MOCK_SNAPSHOT_OR_EQUITY_INVALID")

    def test_extra_record_without_binding_fails(self):
        self.reject(lambda d: d.update(trades=d["trades"][:-1]),
                    "P103_MISSING_OR_MISMATCHED_MOCK_ROWS")

    def test_mock_field_helpers_refuse_subclass_and_unknown_data(self):
        self.assertFalse(pf._mock_plain_report({}, pf.Review))
        self.assertFalse(pf._mock_plain_dataclass({}, sl.Quote))
        self.assertTrue(pf._mock_plain_report(
            self.base["portfolio_result"], pf.Review))
        self.assertTrue(pf._mock_plain_report(
            self.base["stop_result"], sl.Review))
        self.assertTrue(pf._mock_plain_dataclass(
            self.base["stop_quotes"]["USD/JPY"], sl.Quote))
        self.assertEqual(DangerousComparison.calls, 0)


if __name__ == "__main__":
    unittest.main()
