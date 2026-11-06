"""RISK-3P-103..108: forbid forged synthetic loss assertion handoffs.

These are synthetic-only, in-memory Python examples; no broker, MT4, order,
account, network, filesystem, evidence authentication or production authority.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Context, Decimal, Inexact, Overflow, ROUND_DOWN, Rounded
from decimal import localcontext
import unittest

from scripts import phase1_three_pair_synthetic_risk as pf
from scripts import phase1_three_pair_synthetic_stop_conversion as sl


def sample():
    contracts = {
        p: sl.Contract(p, "100000", "0.01", "0.01", "1")
        for p in ("USD/JPY", "EUR/JPY", "EUR/USD")
    }
    quotes = {
        "USD/JPY": sl.Quote("USD/JPY", "150", "151", 42, "SIM-HANDOFF"),
        "EUR/JPY": sl.Quote("EUR/JPY", "181", "182", 42, "SIM-HANDOFF"),
        "EUR/USD": sl.Quote("EUR/USD", "1.20", "1.21", 42, "SIM-HANDOFF"),
    }
    tickets = [
        sl.Ticket("candidate", "EUR/USD", "BUY", "CANDIDATE",
                  "0.01", "1.2000", "1.1990", "0.0001", "5", "SIM-HANDOFF"),
        sl.Ticket("position", "USD/JPY", "SELL", "POSITION",
                  "0.01", "150", "150.05", "0.01", "0", "SIM-HANDOFF"),
        sl.Ticket("pending", "EUR/JPY", "BUY", "PENDING",
                  "0.01", "181", "180.9", "0.01", "0", "SIM-HANDOFF"),
    ]
    return contracts, quotes, tickets


def evaluate(c, q, ts, *, equity="100000", asof=42, sid="SIM-HANDOFF",
             positions=True, pending=True, inflight=True):
    stops = sl.review_synthetic_stop_risk(
        c, q, ts, equity_jpy=equity, asof=asof, snapshot_id=sid,
        positions_reconciled=positions, pending_reconciled=pending,
        inflight_reservations_reconciled=inflight)
    pq = {p: pf.Quote(q0.pair, q0.bid, q0.ask, q0.observed_at,
                      q0.snapshot_id) for p, q0 in q.items()}
    amounts = dict(stops.per_ticket_illustrative_loss_jpy or ())
    with localcontext(Context(prec=96)):
        trades = [
            pf.Trade(t.ticket_id, t.pair, t.side, t.status,
                     str(Decimal(t.volume_lots)
                         * Decimal(c[t.pair].base_units_per_lot)),
                     amounts.get(t.ticket_id, "1"))
            for t in ts
        ]
    portfolio = pf.review_synthetic_portfolio(
        pq, trades, equity_jpy=equity, asof=asof, snapshot_id=sid,
        positions_reconciled=positions,
        pending_orders_reconciled=pending)
    return dict(contracts=c, stop_quotes=q, tickets=ts, stop_result=stops,
                portfolio_quotes=pq, trades=trades,
                portfolio_result=portfolio, equity_jpy=equity,
                asof=asof, snapshot_id=sid,
                positions_reconciled=positions,
                pending_reconciled=pending, inflight_reconciled=inflight)


class MockLossBindingTests(unittest.TestCase):
    def setUp(self):
        self.base = evaluate(*sample())

    def check_held(self, result, *, accepted=False):
        self.assertIs(type(result), pf.SyntheticHandoffReview)
        self.assertEqual(result.mock_binding_consistent, accepted)
        self.assertFalse(result.independent_broker_origin_verified)
        self.assertFalse(result.human_p05_signoff)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertTrue(result.safety_hold_latched)
        self.assertFalse(result.order_allowed)
        self.assertFalse(result.automatic_retry_allowed)
        self.assertFalse(result.stop_release_allowed)
        self.assertIsNone(result.verified_values)

    def refuse(self, mutate, reason):
        args = dict(self.base)
        mutate(args)
        r = pf.review_synthetic_loss_handoff(**args)
        self.assertEqual(r.reason, reason)
        self.check_held(r)
        self.assertEqual(r.mock_records_bound, 0)

    def test_valid_three_ticket_handoff_binds_but_never_authorizes(self):
        r = pf.review_synthetic_loss_handoff(**self.base)
        self.assertEqual(r.reason, "PASS_OFFLINE_MOCK_BINDING_ONLY")
        self.assertEqual(r.mock_records_bound, 3)
        self.check_held(r, accepted=True)
        self.assertFalse(self.base["stop_result"].result_authorizes_trade)
        self.assertFalse(self.base["portfolio_result"].order_allowed)

    def test_lowered_asserted_loss_can_pass_arithmetic_but_not_handoff(self):
        args = dict(self.base)
        args["trades"] = [replace(args["trades"][0],
                                   max_loss_jpy="0.000000000001")] + args["trades"][1:]
        args["portfolio_result"] = pf.review_synthetic_portfolio(
            args["portfolio_quotes"], args["trades"], asof=42,
            snapshot_id="SIM-HANDOFF", equity_jpy="100000",
            positions_reconciled=True, pending_orders_reconciled=True)
        self.assertTrue(args["portfolio_result"].arithmetic_complete)
        rejected = pf.review_synthetic_loss_handoff(**args)
        self.assertEqual(rejected.reason, "P103_MOCK_UNIT_OR_LOSS_ASSERTION_DRIFT")
        self.check_held(rejected)

    def test_higher_asserted_loss_is_not_a_matching_original(self):
        self.refuse(lambda d: d.update(trades=[
            replace(d["trades"][0], max_loss_jpy="999")] + d["trades"][1:]),
            "P103_MOCK_UNIT_OR_LOSS_ASSERTION_DRIFT")

    def test_wrong_lot_to_base_units_conversion_rejected(self):
        self.refuse(lambda d: d.update(trades=[
            replace(d["trades"][0], base_units="999")] + d["trades"][1:]),
            "P103_MOCK_UNIT_OR_LOSS_ASSERTION_DRIFT")

    def test_altered_contract_requires_new_handoff_and_recomputation(self):
        def changed(d):
            x = dict(d["contracts"])
            x["EUR/USD"] = replace(x["EUR/USD"], base_units_per_lot="200000")
            d["contracts"] = x
        self.refuse(changed, "P103_MOCK_UNIT_OR_LOSS_ASSERTION_DRIFT")

    def test_mismatched_ticket_id_pair_side_and_status_rejected(self):
        for key, value in (("trade_id", "other"), ("pair", "USD/JPY"),
                           ("side", "SELL"), ("status", "POSITION")):
            with self.subTest(field=key):
                self.refuse(
                    lambda d, k=key, v=value: d.update(trades=[
                        replace(d["trades"][0], **{k:v})] + d["trades"][1:]),
                    "P103_MOCK_IDENTITY_OR_ORDER_CHANGED")

    def test_reordering_trades_without_recomputing_is_rejected(self):
        self.refuse(lambda d: d.update(trades=list(reversed(d["trades"]))),
                    "P103_MOCK_IDENTITY_OR_ORDER_CHANGED")

    def test_missing_extra_or_overloaded_mock_rows_rejected(self):
        for kind in ("missing", "extra", "overload"):
            with self.subTest(kind=kind):
                def change(d):
                    if kind == "missing":
                        d["trades"] = d["trades"][:-1]
                    elif kind == "extra":
                        d["trades"] = d["trades"] + [d["trades"][0]]
                    else:
                        d["tickets"] = d["tickets"] * 43
                        d["trades"] = d["trades"] * 43
                self.refuse(change, "P103_MISSING_OR_MISMATCHED_MOCK_ROWS")

    def test_cross_snapshot_bid_ask_drift_is_rejected(self):
        def changed(d):
            q = dict(d["portfolio_quotes"])
            q["USD/JPY"] = replace(q["USD/JPY"], ask="151.01")
            d["portfolio_quotes"] = q
        self.refuse(changed, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")

    def test_cross_snapshot_time_drift_is_rejected(self):
        def changed(d):
            q = dict(d["portfolio_quotes"])
            q["EUR/JPY"] = replace(q["EUR/JPY"], observed_at=43)
            d["portfolio_quotes"] = q
        self.refuse(changed, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")

    def test_renamed_or_wrong_quote_type_refused_without_private_echo(self):
        def changed(d):
            q = dict(d["portfolio_quotes"])
            q["EUR/JPY"] = "PRIVATE_CANARY_103"
            d["portfolio_quotes"] = q
        self.refuse(changed, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")
        d = dict(self.base)
        changed(d)
        self.assertNotIn("PRIVATE_CANARY_103",
                         str(pf.review_synthetic_loss_handoff(**d)))

    def test_only_exact_three_pair_sets_are_permitted(self):
        def changed(d):
            c = dict(d["contracts"])
            c["GBP/USD"] = c["EUR/USD"]
            d["contracts"] = c
        self.refuse(changed, "P103_MOCK_THREE_PAIR_SCOPE_MISMATCH")

    def test_stop_report_forged_trade_approval_is_rejected(self):
        self.refuse(lambda d: d.update(
            stop_result=replace(d["stop_result"],
                                result_authorizes_trade=True)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_portfolio_report_forged_order_permission_is_rejected(self):
        self.refuse(lambda d: d.update(
            portfolio_result=replace(d["portfolio_result"],
                                     order_allowed=True)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_portfolio_report_forged_stop_release_is_rejected(self):
        self.refuse(lambda d: d.update(
            portfolio_result=replace(d["portfolio_result"],
                                     stop_release_allowed=True)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_incomplete_or_wrong_type_report_is_rejected(self):
        self.refuse(lambda d: d.update(portfolio_result=object()),
                    "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")
        self.refuse(lambda d: d.update(
            stop_result=replace(d["stop_result"], illustrative_complete=False)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_stop_row_loss_drift_is_rejected_even_with_original_portfolio(self):
        def changed(d):
            rows = list(d["stop_result"].per_ticket_illustrative_loss_jpy)
            rows[0] = (rows[0][0], "1")
            d["stop_result"] = replace(
                d["stop_result"], per_ticket_illustrative_loss_jpy=tuple(rows))
        self.refuse(changed, "P103_MOCK_UNIT_OR_LOSS_ASSERTION_DRIFT")

    def test_candidate_or_aggregate_total_forgery_is_rejected(self):
        self.refuse(lambda d: d.update(stop_result=replace(
            d["stop_result"], total_illustrative_loss_jpy="1")),
            "P103_MOCK_TOTAL_OR_LIMIT_DRIFT")
        self.refuse(lambda d: d.update(portfolio_result=replace(
            d["portfolio_result"], candidate_max_loss_jpy="1")),
            "P103_MOCK_TOTAL_OR_LIMIT_DRIFT")

    def test_limit_boolean_forgery_is_rejected(self):
        self.refuse(lambda d: d.update(portfolio_result=replace(
            d["portfolio_result"], total_exceeds_existing_limit=True)),
            "P103_MOCK_TOTAL_OR_LIMIT_DRIFT")

    def test_both_forged_aggregates_cannot_bypass_recomputation(self):
        def changed(d):
            d["stop_result"] = replace(
                d["stop_result"], total_illustrative_loss_jpy="50")
            d["portfolio_result"] = replace(
                d["portfolio_result"], total_max_loss_jpy="50")
        self.refuse(changed, "P103_MOCK_RECOMPUTATION_MISMATCH")

    def test_changed_contract_and_updated_trades_need_fresh_stop_result(self):
        def changed(d):
            c = dict(d["contracts"])
            c["EUR/USD"] = replace(c["EUR/USD"], base_units_per_lot="200000")
            d["contracts"] = c
            d["trades"] = [replace(d["trades"][0], base_units="2000")] + d["trades"][1:]
        self.refuse(changed, "P103_MOCK_RECOMPUTATION_MISMATCH")

    def test_reconciled_flags_are_not_assumed_from_arithmetic_success(self):
        for name in ("positions_reconciled", "pending_reconciled",
                     "inflight_reconciled"):
            with self.subTest(name=name):
                self.refuse(lambda d, x=name: d.update({x:False}),
                            "P103_UNKNOWN_MOCK_RECONCILIATION")

    def test_changed_snapshot_identity_is_not_accepted_as_old_result(self):
        self.refuse(lambda d: d.update(snapshot_id="SIM-OTHER"),
                    "P103_MOCK_RECOMPUTATION_MISMATCH")

    def test_changed_equity_does_not_bind_to_previous_hard_limit_flags(self):
        self.refuse(lambda d: d.update(equity_jpy="1"),
                    "P103_MOCK_RECOMPUTATION_MISMATCH")

    def test_float_and_noncanonical_amounts_are_rejected(self):
        for bad in (1000.0, "1e3", "NaN", "0001"):
            with self.subTest(bad=bad):
                self.refuse(lambda d, v=bad: d.update(trades=[
                    replace(d["trades"][0], max_loss_jpy=v)] + d["trades"][1:]),
                    "P103_MOCK_UNPARSABLE_AMOUNT")

    def test_hostile_external_decimal_context_keeps_mock_handoff_exact(self):
        regular = pf.review_synthetic_loss_handoff(**self.base)
        with localcontext() as ctx:
            ctx.prec = 3
            ctx.Emax = 9
            ctx.Emin = -9
            ctx.rounding = ROUND_DOWN
            ctx.traps[Inexact] = True
            ctx.traps[Rounded] = True
            ctx.traps[Overflow] = True
            hostile = pf.review_synthetic_loss_handoff(**self.base)
            self.assertEqual(ctx.prec, 3)
        self.assertEqual(hostile, regular)
        self.check_held(hostile, accepted=True)

    def test_exact_128_mock_rows_are_audited_without_production_permission(self):
        c, q, ts = sample()
        candidate = ts[0]
        ts = [candidate] + [
            replace(ts[1], ticket_id=f"p-{i}")
            for i in range(127)]
        args = evaluate(c, q, ts)
        self.assertTrue(args["stop_result"].illustrative_complete)
        self.assertTrue(args["portfolio_result"].arithmetic_complete)
        result = pf.review_synthetic_loss_handoff(**args)
        self.assertEqual(result.reason, "PASS_OFFLINE_MOCK_BINDING_ONLY")
        self.assertEqual(result.mock_records_bound, 128)
        self.check_held(result, accepted=True)

    def test_failure_result_does_not_echo_untrusted_identifiers(self):
        d = dict(self.base)
        d["trades"] = [replace(d["trades"][0],
                               trade_id="PRIVATE_CANARY_103")] + d["trades"][1:]
        outcome = pf.review_synthetic_loss_handoff(**d)
        self.assertNotIn("PRIVATE_CANARY_103", str(outcome))
        self.check_held(outcome)

    def test_no_mock_consistency_result_ever_promotes_p05_or_trade(self):
        result = pf.review_synthetic_loss_handoff(**self.base)
        self.assertTrue(result.mock_binding_consistent)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertFalse(result.independent_broker_origin_verified)
        self.assertFalse(result.human_p05_signoff)
        self.assertFalse(result.order_allowed)


if __name__ == "__main__":
    unittest.main()
