"""RISK-3P-121..126: adversarial dictionary keys never invoke mock comparators.

All fixtures are synthetic and in-memory. NO_GO and latched safety apply even
when a positive mock binding result is returned. No broker, MT4, orders,
private logs, network or production permission are accessed.
"""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch
import unittest

from scripts import phase1_three_pair_synthetic_stop_conversion as sl
from scripts import phase1_three_pair_synthetic_risk as pf


class PoisonString(str):
    hashes = 0
    compares = 0

    def __hash__(self):
        type(self).hashes += 1
        return hash(str.__str__(self))

    def __eq__(self, other):
        type(self).compares += 1
        raise RuntimeError("PRIVATE_CANARY_121_KEY_COMPARISON")


class PoisonObject:
    hashes = 0
    compares = 0

    def __hash__(self):
        type(self).hashes += 1
        return hash("USD/JPY")

    def __eq__(self, other):
        type(self).compares += 1
        raise RuntimeError("PRIVATE_CANARY_121_KEY_COMPARISON")


class PoisonDict(dict):
    iterates = 0

    def __iter__(self):
        type(self).iterates += 1
        raise RuntimeError("PRIVATE_CANARY_121_DICT_ITERATION")


def fixture():
    c = {p: sl.Contract(p, "100000", "0.01", "0.01", "1")
         for p in sl.PAIRS}
    q = {
        "USD/JPY": sl.Quote("USD/JPY", "150", "151", 42, "SIM-121"),
        "EUR/JPY": sl.Quote("EUR/JPY", "181", "182", 42, "SIM-121"),
        "EUR/USD": sl.Quote("EUR/USD", "1.20", "1.21", 42, "SIM-121"),
    }
    tickets = [
        sl.Ticket("new", "EUR/USD", "BUY", "CANDIDATE", "0.01",
                  "1.2000", "1.1990", "0.0001", "5", "SIM-121"),
        sl.Ticket("old", "USD/JPY", "SELL", "POSITION", "0.01",
                  "150", "150.05", "0.01", "0", "SIM-121"),
        sl.Ticket("pending", "EUR/JPY", "BUY", "PENDING", "0.01",
                  "181", "180.9", "0.01", "0", "SIM-121"),
    ]
    s = sl.review_synthetic_stop_risk(
        c, q, tickets, equity_jpy="100000", asof=42,
        snapshot_id="SIM-121", positions_reconciled=True,
        pending_reconciled=True, inflight_reservations_reconciled=True)
    pq = {k: pf.Quote(v.pair, v.bid, v.ask, v.observed_at, v.snapshot_id)
          for k, v in q.items()}
    losses = dict(s.per_ticket_illustrative_loss_jpy)
    trades = [
        pf.Trade("new", "EUR/USD", "BUY", "CANDIDATE", "1000", losses["new"]),
        pf.Trade("old", "USD/JPY", "SELL", "POSITION", "1000", losses["old"]),
        pf.Trade("pending", "EUR/JPY", "BUY", "PENDING", "1000",
                 losses["pending"]),
    ]
    p = pf.review_synthetic_portfolio(
        pq, trades, equity_jpy="100000", asof=42, snapshot_id="SIM-121",
        positions_reconciled=True, pending_orders_reconciled=True)
    return {
        "contracts": c, "stop_quotes": q, "tickets": tickets,
        "stop_result": s, "portfolio_quotes": pq, "trades": trades,
        "portfolio_result": p, "equity_jpy": "100000",
        "asof": 42, "snapshot_id": "SIM-121",
        "positions_reconciled": True, "pending_reconciled": True,
        "inflight_reconciled": True,
    }


def replace_key(d, name, key):
    old = d[name]
    replacement = {k: v for k, v in old.items() if k != "USD/JPY"}
    replacement[key] = old["USD/JPY"]
    d[name] = replacement
    PoisonString.hashes = PoisonString.compares = 0
    PoisonObject.hashes = PoisonObject.compares = 0


class HostileKeyGuardTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture()
        PoisonString.hashes = PoisonString.compares = 0
        PoisonObject.hashes = PoisonObject.compares = 0
        PoisonDict.iterates = 0

    def held(self, report, pass_mock=False):
        self.assertEqual(report.runtime_go_no_go, "NO_GO")
        self.assertEqual(report.phase_1, "BLOCKED")
        self.assertTrue(report.safety_hold_latched)
        self.assertFalse(report.order_allowed)
        self.assertFalse(report.automatic_retry_allowed)
        self.assertFalse(report.stop_release_allowed)
        self.assertFalse(report.independent_broker_origin_verified)
        self.assertFalse(report.human_p05_signoff)
        self.assertIsNone(report.verified_values)
        self.assertIs(report.mock_binding_consistent, pass_mock)
        self.assertNotIn("PRIVATE_CANARY_121", str(report))

    def rejected(self, changes, reason="P103_MOCK_THREE_PAIR_SCOPE_MISMATCH"):
        args = dict(self.base)
        changes(args)
        r = pf.review_synthetic_loss_handoff(**args)
        self.assertEqual(r.reason, reason)
        self.assertEqual(r.mock_records_bound, 0)
        self.held(r)
        self.assertEqual(PoisonString.hashes, 0)
        self.assertEqual(PoisonString.compares, 0)
        self.assertEqual(PoisonObject.hashes, 0)
        self.assertEqual(PoisonObject.compares, 0)
        self.assertEqual(PoisonDict.iterates, 0)

    def test_normal_three_plain_pair_maps_keep_mock_binding_no_go(self):
        self.assertEqual(pf._mock_plain_three_pair_map(self.base["contracts"]),
                         True)
        self.assertEqual(pf._mock_plain_three_pair_map(self.base["stop_quotes"]),
                         True)
        self.assertEqual(pf._mock_plain_three_pair_map(self.base["portfolio_quotes"]),
                         True)
        r = pf.review_synthetic_loss_handoff(**self.base)
        self.assertEqual(r.reason, "PASS_OFFLINE_MOCK_BINDING_ONLY")
        self.assertEqual(r.mock_records_bound, 3)
        self.held(r, True)

    def test_string_subclass_key_never_hashed_inside_guard_for_each_map(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(map=name):
                self.rejected(lambda d, n=name: replace_key(
                    d, n, PoisonString("USD/JPY")))

    def test_object_key_never_hashed_inside_guard_for_each_map(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(map=name):
                self.rejected(lambda d, n=name: replace_key(
                    d, n, PoisonObject()))

    def test_dict_subclass_with_evil_iteration_never_iterated_for_each_map(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(map=name):
                self.rejected(lambda d, n=name: d.update({
                    n: PoisonDict(d[n])}))

    def test_all_three_malicious_maps_rejected_at_first_guard(self):
        def mutate(d):
            for name in ("contracts", "stop_quotes", "portfolio_quotes"):
                replace_key(d, name, PoisonString("USD/JPY"))
        self.rejected(mutate)

    def test_mixed_malicious_key_types_rejected_before_any_comparison(self):
        def mutate(d):
            replace_key(d, "contracts", PoisonString("USD/JPY"))
            replace_key(d, "stop_quotes", PoisonObject())
        self.rejected(mutate)

    def test_str_subclass_in_extra_key_is_refused_by_length_before_hash(self):
        def mutate(d):
            x = dict(d["contracts"])
            x[PoisonString("GBP/USD")] = x["EUR/USD"]
            d["contracts"] = x
            PoisonString.hashes = PoisonString.compares = 0
        self.rejected(mutate)

    def test_missing_required_pair_is_rejected(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                self.rejected(lambda d, n=name: d.update({
                    n: {k:v for k,v in d[n].items() if k != "EUR/USD"}}))

    def test_unknown_extra_plain_string_pair_is_rejected(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                self.rejected(lambda d, n=name: d.update({
                    n: {**d[n], "GBP/USD": next(iter(d[n].values()))}}))

    def test_wrong_plain_string_instead_of_required_pair_is_rejected(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                def mutate(d, n=name):
                    x = dict(d[n])
                    v = x.pop("USD/JPY")
                    x["GBP/USD"] = v
                    d[n] = x
                self.rejected(mutate)

    def test_boolean_key_does_not_pass_plain_string_gate(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                self.rejected(lambda d,n=name: replace_key(d,n,True))

    def test_integer_key_does_not_pass_plain_string_gate(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                self.rejected(lambda d,n=name: replace_key(d,n,1))

    def test_bytes_key_does_not_pass_plain_string_gate(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                self.rejected(lambda d,n=name: replace_key(d,n,b"USD/JPY"))

    def test_none_key_does_not_pass_plain_string_gate(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                self.rejected(lambda d,n=name: replace_key(d,n,None))

    def test_tuple_key_does_not_pass_plain_string_gate(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                self.rejected(lambda d,n=name: replace_key(d,n,("USD", "JPY")))

    def test_list_or_tuple_as_mapping_is_rejected(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            for typ in (list, tuple):
                with self.subTest(name=name, typ=typ):
                    self.rejected(lambda d,n=name,t=typ: d.update({
                        n: t(d[n].items())}))

    def test_nonsensical_none_or_string_mapping_is_rejected(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            for obj in (None, "", "USD/JPY"):
                with self.subTest(name=name, obj=obj):
                    self.rejected(lambda d,n=name,v=obj: d.update({n:v}))

    def test_helper_does_not_invoke_hash_for_poison_string_key(self):
        d = dict(self.base["contracts"])
        d.pop("USD/JPY")
        d[PoisonString("USD/JPY")] = self.base["contracts"]["USD/JPY"]
        PoisonString.hashes = PoisonString.compares = 0
        self.assertFalse(pf._mock_plain_three_pair_map(d))
        self.assertEqual(PoisonString.hashes, 0)
        self.assertEqual(PoisonString.compares, 0)

    def test_helper_accepts_no_extra_pair_and_no_missing_pair(self):
        d = dict(self.base["contracts"])
        self.assertTrue(pf._mock_plain_three_pair_map(d))
        d.pop("EUR/USD")
        self.assertFalse(pf._mock_plain_three_pair_map(d))
        d["EUR/USD"] = self.base["contracts"]["EUR/USD"]
        self.assertTrue(pf._mock_plain_three_pair_map(d))
        d["GBP/USD"] = self.base["contracts"]["EUR/USD"]
        self.assertFalse(pf._mock_plain_three_pair_map(d))

    def test_no_key_guard_result_can_enable_trades(self):
        self.held(pf.review_synthetic_loss_handoff(**self.base), True)
        self.rejected(lambda d: replace_key(
            d, "contracts", PoisonString("USD/JPY")))
        self.assertEqual(sl.PAIRS, pf.PAIRS)
        self.assertEqual(pf.PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))

    def test_exception_in_mock_recomputation_remains_fail_closed(self):
        with patch.object(pf.stop_conversion, "review_synthetic_stop_risk",
                          side_effect=RuntimeError("PRIVATE_CANARY_121")):
            self.rejected(lambda d: None, "P103_MOCK_RECOMPUTATION_EXCEPTION")

    def test_unknown_reconciliation_still_refused_before_three_pair_check(self):
        self.rejected(lambda d: d.update(pending_reconciled=False),
                      "P103_UNKNOWN_MOCK_RECONCILIATION")

    def test_report_with_forged_order_permission_still_refused(self):
        self.rejected(lambda d: d.update(portfolio_result=replace(
            d["portfolio_result"], order_allowed=True)),
            "P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")

    def test_mismatched_mock_quote_time_still_refused_after_key_gate(self):
        def mutate(d):
            q = dict(d["portfolio_quotes"])
            q["EUR/USD"] = replace(q["EUR/USD"], observed_at=44)
            d["portfolio_quotes"] = q
        self.rejected(mutate, "P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")

    def test_mismatched_asserted_loss_still_refused_after_key_gate(self):
        def mutate(d):
            t = list(d["trades"])
            t[0] = replace(t[0], max_loss_jpy="0.000000000001")
            d["trades"] = t
        self.rejected(mutate, "P103_MOCK_UNIT_OR_LOSS_ASSERTION_DRIFT")

    def test_schema_rejects_control_character_in_unknown_key(self):
        for name in ("contracts", "stop_quotes", "portfolio_quotes"):
            with self.subTest(name=name):
                def mutate(d, n=name):
                    x = dict(d[n])
                    x["USD" + chr(10) + "JPY"] = x.pop("USD/JPY")
                    d[n] = x
                self.rejected(mutate)


if __name__ == "__main__":
    unittest.main()
