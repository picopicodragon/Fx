"""FORM-08..10 synthetic daily, DD and timebase tests, no real approvals."""
from dataclasses import replace
from decimal import Decimal
import unittest

from scripts.phase1_form08_10_synthetic_controls import (
    Daily, Drawdown, Observation, Freshness, Review, ny17_anchor_utc,
    review_daily, review_dd, review_freshness,
)


def daily():
    return Daily("100000", "98500", "0", "2026-07-01T21:00:00Z",
                 "2026-07-02T00:00:00Z", 9, 9, True, True, True,
                 "SYNTHETIC_COMPARISON_ONLY")


def dd():
    return Drawdown("96", "100", 9, True, True, True, True,
                    "SYNTHETIC_PRIOR_PEAK_ONLY")


def times():
    return Freshness("2026-07-02T00:00:00Z", 9, tuple(
        Observation(k, "2026-07-01T23:59:50Z", 9) for k in (
            "ACCOUNT", "POSITIONS", "PENDING", "FX_QUOTES",
            "CONVERSION", "LEDGER",
        )), False, False, True)


class Form08To10SyntheticTests(unittest.TestCase):
    def held(self, result):
        self.assertIs(type(result), Review)
        self.assertEqual(result.runtime_go_no_go, "NO_GO")
        self.assertEqual(result.phase_1, "BLOCKED")
        self.assertIs(result.safety_hold_latched, True)
        self.assertIs(result.order_allowed, False)
        self.assertIs(result.operational_stop_release_allowed, False)
        self.assertIs(result.automatic_retry_allowed, False)
        self.assertIs(result.production_authorized, False)
        self.assertIs(result.broker_account_verified, False)
        self.assertIs(result.owner_approval_recorded, False)
        self.assertIs(result.freshness_policy_verified, False)
        self.assertIs(result.cashflows_or_hwm_real_evidence_verified, False)
        self.assertIsNone(result.verified_values)

    def denied(self, result, reason):
        self.assertEqual(result.reason, reason)
        self.assertFalse(result.arithmetic_only)
        self.held(result)

    def test_form08_fixed_opening_denominator_triggers_at_exact_one_point_five(self):
        r = review_daily(daily())
        self.assertTrue(r.arithmetic_only)
        self.assertEqual(Decimal(r.daily_illustrative_loss_jpy), Decimal("1500"))
        self.assertEqual(Decimal(r.daily_illustrative_limit_jpy), Decimal("1500"))
        self.assertIs(r.daily_stop_triggered_in_synthetic_example, True)
        self.held(r)

    def test_form08_one_sen_below_above_limit_and_flow_adjustment(self):
        less = review_daily(replace(daily(), current_equity_jpy="98500.01"))
        more = review_daily(replace(daily(), current_equity_jpy="98499.99"))
        self.assertIs(less.daily_stop_triggered_in_synthetic_example, False)
        self.assertIs(more.daily_stop_triggered_in_synthetic_example, True)
        self.assertEqual(Decimal(more.daily_illustrative_loss_jpy), Decimal("1500.01"))
        deposit = review_daily(replace(daily(), net_external_cashflows_jpy="10000",
                                       current_equity_jpy="108500"))
        self.assertEqual(Decimal(deposit.daily_illustrative_loss_jpy), Decimal("1500"))
        self.held(less)
        self.held(more)
        self.held(deposit)

    def test_form08_nonreconciled_ledger_flow_fee_or_correction_denied(self):
        for k, v in (("cashflows_reconciled", False),
                     ("pnl_reconciled", None),
                     ("corrections_complete", 1)):
            with self.subTest(field=k):
                self.denied(review_daily(replace(daily(), **{k: v})),
                            "DAILY_EXTERNAL_FLOW_OR_PNL_NOT_RECONCILED")

    def test_form08_denominator_zero_negative_and_float_rejected(self):
        for field, val in (("opening_equity_jpy", "0"),
                           ("opening_equity_jpy", "-1"),
                           ("opening_equity_jpy", 100000),
                           ("current_equity_jpy", "NaN"),
                           ("net_external_cashflows_jpy", None)):
            with self.subTest(field=field, value=val):
                self.denied(review_daily(replace(daily(), **{field: val})),
                            "DAILY_AMOUNT_OR_DENOMINATOR_UNCOMPUTABLE")

    def test_form08_account_and_ledger_generation_must_match(self):
        for k, v in (("account_epoch", 8), ("account_epoch", True),
                     ("ledger_epoch", 10), ("ledger_epoch", None)):
            with self.subTest(field=k):
                self.denied(review_daily(replace(daily(), **{k: v})),
                            "DAILY_ACCOUNT_LEDGER_EPOCH_MISMATCH")

    def test_form08_profit_offset_cannot_be_mistaken_for_approved_policy(self):
        for value in ("BROKER_APPROVED", "UNSPECIFIED", None, True):
            self.denied(review_daily(replace(daily(), profit_offset_status=value)),
                        "DAILY_PROFIT_OFFSET_UNDECIDED")
        profit_example = review_daily(replace(daily(), current_equity_jpy="100500"))
        self.assertTrue(profit_example.arithmetic_only)
        self.assertEqual(Decimal(profit_example.daily_illustrative_loss_jpy), 0)
        self.held(profit_example)

    def test_form08_ny17_edt_boundary_and_est_boundary(self):
        from datetime import datetime, timezone
        edt = datetime(2026, 7, 1, 21, 0, tzinfo=timezone.utc)
        est = datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(ny17_anchor_utc(edt), edt)
        self.assertEqual(ny17_anchor_utc(est), est)
        edt_before = edt.replace(hour=20, minute=59)
        est_before = est.replace(hour=21, minute=59)
        self.assertEqual(ny17_anchor_utc(edt_before).day, 30)
        self.assertEqual(ny17_anchor_utc(est_before).day, 31)
        self.held(review_daily(daily()))
        winter = replace(daily(), opening_anchor_utc="2026-01-01T22:00:00Z",
                         asof_utc="2026-01-02T01:00:00Z")
        self.assertTrue(review_daily(winter).arithmetic_only)

    def test_form08_crossed_date_or_wrong_ny17_anchor_rejected(self):
        for key, value in (
            ("opening_anchor_utc", "2026-07-01T22:00:00Z"),
            ("opening_anchor_utc", "2026-07-02T21:00:00Z"),
            ("opening_anchor_utc", "2026-07-01T21:00:00+09:00"),
            ("asof_utc", "bad"),
        ):
            with self.subTest(field=key, value=value):
                self.denied(review_daily(replace(daily(), **{key: value})),
                            "NY17_BOUNDARY_OR_CLOCK_INVALID")

    def test_form09_exact_dd4_dd5_stop_and_nonrelease(self):
        at_4 = review_dd(dd())
        at_5 = review_dd(replace(dd(), current_unit_value="95"))
        before_4 = review_dd(replace(dd(), current_unit_value="96.01"))
        self.assertTrue(at_4.dd4_triggered_in_synthetic_example)
        self.assertFalse(at_4.dd5_triggered_in_synthetic_example)
        self.assertTrue(at_5.dd4_triggered_in_synthetic_example)
        self.assertTrue(at_5.dd5_triggered_in_synthetic_example)
        self.assertFalse(before_4.dd4_triggered_in_synthetic_example)
        self.assertEqual(Decimal(at_4.dd_illustrative_fraction), Decimal("0.04"))
        for item in (at_4, at_5, before_4):
            self.held(item)

    def test_form09_cashflow_unitization_hwm_restart_must_be_verified(self):
        for key in ("persistent_hwm_verified", "flow_unitization_reconciled",
                    "restart_consistent", "existing_stop_latched"):
            with self.subTest(field=key):
                self.denied(review_dd(replace(dd(), **{key: False})),
                            "DD_HWM_OR_STOP_PERSISTENCE_UNKNOWN")

    def test_form09_negative_or_zero_equity_untrusted_peak_rejected(self):
        for key, value in (("current_unit_value", "0"),
                           ("current_unit_value", "-1"),
                           ("historic_high_water_unit_value", "0"),
                           ("historic_high_water_unit_value", None),
                           ("current_unit_value", "101")):
            with self.subTest(key=key):
                self.denied(review_dd(replace(dd(), **{key: value})),
                            "UNIT_VALUE_OR_HWM_UNRELIABLE")
        self.denied(review_dd(replace(dd(), hwm_source="RESET_AT_DEPOSIT")),
                    "DD_HWM_SOURCE_UNVERIFIED")

    def test_form09_clock_epoch_and_restart_provenance_not_approved(self):
        for value in (True, -1, None, "9"):
            self.denied(review_dd(replace(dd(), state_epoch=value)),
                        "INVALID_DD_STATE_EPOCH")
        self.held(review_dd(dd()))

    def test_form10_all_sources_causally_match_but_no_universal_ttl(self):
        r = review_freshness(times())
        self.assertTrue(r.arithmetic_only)
        self.assertEqual(r.reason, "SYNTHETIC_TIME_SHAPE_ONLY_NO_TTL_NO_GO")
        self.held(r)
        old = replace(times(), observations=tuple(replace(x,
                  observed_at_utc="2026-06-01T00:00:00Z")
                  for x in times().observations))
        r2 = review_freshness(old)
        self.assertEqual(r2.reason, "SYNTHETIC_TIME_SHAPE_ONLY_NO_TTL_NO_GO")
        self.assertFalse(r2.freshness_policy_verified)
        self.held(r2)

    def test_form10_missing_duplicate_or_unknown_clock_source_denied(self):
        source = times()
        self.denied(review_freshness(replace(
            source, observations=source.observations[:-1])),
            "TIME_SOURCES_INCOMPLETE")
        o = list(source.observations)
        o[1] = replace(o[1], source="ACCOUNT")
        self.denied(review_freshness(replace(source, observations=tuple(o))),
                    "DUPLICATE_TIME_SOURCE")
        o = list(source.observations)
        o[1] = replace(o[1], source="NEWS")
        self.denied(review_freshness(replace(source, observations=tuple(o))),
                    "INVALID_TIME_SOURCE")

    def test_form10_future_missing_and_wrong_epoch_observation_denied(self):
        for key, val, expected in (
            ("observed_at_utc", "2026-07-02T00:00:01Z",
             "TIME_SOURCE_MISSING_OR_FUTURE"),
            ("observed_at_utc", "bad", "TIME_SOURCE_MISSING_OR_FUTURE"),
            ("epoch", 8, "CAUSAL_GENERATION_MISMATCH"),
            ("epoch", True, "CAUSAL_GENERATION_MISMATCH"),
        ):
            with self.subTest(key=key):
                s = times()
                entries = list(s.observations)
                entries[0] = replace(entries[0], **{key: val})
                self.denied(review_freshness(replace(
                    s, observations=tuple(entries))), expected)

    def test_form10_clock_jump_market_hours_and_false_ttl_approval_denied(self):
        for key, value, expected in (
            ("clock_discontinuity_detected", True,
             "CLOCK_DISCONTINUITY_OR_ROLLBACK"),
            ("market_hours_confirmed", False,
             "MARKET_HOURS_UNCONFIRMED"),
            ("source_age_policies_approved", True,
             "FALSE_UNIVERSAL_FRESHNESS_APPROVAL"),
            ("decision_utc", "2026-07-02T00:00:00+09:00",
             "DECISION_CLOCK_OR_EPOCH_INVALID"),
        ):
            with self.subTest(key=key):
                self.denied(review_freshness(replace(times(), **{key: value})),
                            expected)

    def test_invalid_input_types_never_return_go(self):
        for f in (review_daily, review_dd, review_freshness):
            for val in (None, {}, [], "approved"):
                with self.subTest(function=f.__name__, value=repr(val)):
                    r = f(val)
                    self.assertTrue(r.reason.startswith("INVALID_"))
                    self.held(r)


if __name__ == "__main__":
    unittest.main()
