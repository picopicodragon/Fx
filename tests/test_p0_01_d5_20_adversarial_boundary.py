"""D5-20: offline adversarial cross-gate regression; all outcomes deny trading."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from scripts.p0_01_d5_19_integrated_no_go import (
    evaluate_offline_integrated_no_go as evaluate,
)


def scenario():
    snapshot = {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "trading_day_start_ny_date": "2026-07-01",
        "daily_stop_latched": False, "last_status": "SYNTHETIC_MONITORING_ONLY",
        "sequence": 42,
    }
    rec = lambda id_, source: {
        "evidence_id": id_, "source_kind": source,
        "account_scope": "SYNTHETIC_ACCOUNT_A",
        "observed_at_utc": "2026-07-01T21:00:00Z",
        "positions": "ABSENT", "pending_orders": "ABSENT", "ea_running": "ABSENT",
    }
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "evidence_mode": "SYNTHETIC_RECORDS",
        "evidence": {"origin": "SYNTHETIC_ONLY", "schema_version": 1,
                     "account_scope": "SYNTHETIC_ACCOUNT_A",
                     "records": [rec("EVID_A", "USER_REPORT"),
                                 rec("EVID_B", "VISUAL_OBSERVATION")]},
        "daily_fixture": {
            "origin": "SYNTHETIC_ONLY",
            "utc_timestamp": "2026-07-01T21:00:00+00:00",
            "previous_day_label": "2026-07-01",
            "previous_daily_stop": False, "next_day_safety_checked": False,
            "risk_fixture": {
                "origin": "SYNTHETIC_ONLY", "equity_jpy": "100000",
                "peak_equity_jpy": "100000", "single_trade_risk_jpy": "0",
                "aggregate_risk_jpy": "0", "daily_loss_jpy": "0",
            },
        },
        "snapshots": [snapshot], "restored_snapshot": snapshot,
        "expected_day": "2026-07-01", "minimum_sequence": 42,
    }


def actual_ledger():
    with (Path(__file__).resolve().parents[1] /
          "specs/p0_01_d5_17_evidence_reconciliation_status.json").open(
              encoding="utf-8") as handle:
        return json.load(handle)


class D520AdversarialBoundaryTests(unittest.TestCase):
    def deny(self, result):
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(type(result["daily_stop_latched"]), bool)
        for field in ("broker_verified", "production_usable", "orders_generated",
                      "read_only_ex4_execution_approved",
                      "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(result[field], False)
        self.assertEqual(set(result), {
            "status", "evidence_status", "daily_status", "recovery_status",
            "daily_stop_latched", "safety_hold_latched", "runtime_go_no_go",
            "verified_values", "broker_verified", "production_usable",
            "orders_generated", "read_only_ex4_execution_approved",
            "terminal_execution_approved", "forward_trading_enabled", "phase_1",
        })

    def test_synthetic_consistency_still_denied(self):
        r = evaluate(scenario())
        self.assertEqual(r["status"],
                         "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertIs(r["daily_stop_latched"], False)
        self.deny(r)

    def test_d517_reported_history_never_reconciles_itself(self):
        p = scenario()
        p["evidence_mode"] = "D517_LEDGER"
        p["evidence"] = actual_ledger()
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.deny(r)

    def test_current_day_stale_clean_snapshot_rejected(self):
        p = scenario()
        p["daily_fixture"]["utc_timestamp"] = "2026-07-02T21:00:00+00:00"
        p["expected_day"] = "2026-07-02"
        p["daily_fixture"]["previous_day_label"] = "2026-07-02"
        self.assertEqual(evaluate(p)["status"],
                         "INTEGRATED_STALE_STOP_RECORD_FAIL_CLOSED")

    def test_stale_snapshot_with_existing_stop_is_not_cleared(self):
        p = scenario()
        p["daily_fixture"]["utc_timestamp"] = "2026-07-02T21:00:00+00:00"
        p["expected_day"] = "2026-07-02"
        p["daily_fixture"]["previous_day_label"] = "2026-07-01"
        p["daily_fixture"]["previous_daily_stop"] = True
        p["snapshots"][-1]["daily_stop_latched"] = True
        p["snapshots"][-1]["last_status"] = "DAILY_STOP"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_STALE_STOP_RECORD_FAIL_CLOSED")
        self.deny(r)

    def test_current_day_snapshot_with_prior_day_label_allowed_as_review(self):
        p = scenario()
        p["daily_fixture"]["previous_day_label"] = "2026-06-30"
        p["daily_fixture"]["previous_daily_stop"] = True
        p["snapshots"][-1]["daily_stop_latched"] = True
        p["snapshots"][-1]["last_status"] = "NEXT_DAY_REVIEW_PENDING"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.deny(r)

    def test_future_snapshot_rejected_by_restoration(self):
        p = scenario()
        p["snapshots"][-1]["trading_day_start_ny_date"] = "2026-07-02"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_old_but_internally_consistent_evidence_has_time_mismatch(self):
        p = scenario()
        for rec in p["evidence"]["records"]:
            rec["observed_at_utc"] = "2026-06-30T21:00:00Z"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_TIME_MISMATCH_NO_GO")
        self.assertEqual(r["evidence_status"],
                         "SYNTHETIC_INTERNALLY_CONSISTENT_NO_GO")
        self.deny(r)

    def test_evidence_one_second_stale_has_time_mismatch(self):
        p = scenario()
        for rec in p["evidence"]["records"]:
            rec["observed_at_utc"] = "2026-07-01T20:59:59Z"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_TIME_MISMATCH_NO_GO")
        self.deny(r)

    def test_valid_utc_z_and_offset_zero_are_equivalent(self):
        p = scenario()
        p["daily_fixture"]["utc_timestamp"] = "2026-07-01T21:00:00Z"
        r = evaluate(p)
        self.assertEqual(r["status"],
                         "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.deny(r)

    def test_fractional_synthetic_clock_cannot_be_declared_same_second(self):
        p = scenario()
        p["daily_fixture"]["utc_timestamp"] = "2026-07-01T21:00:00.500+00:00"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_TIME_MISMATCH_NO_GO")
        self.deny(r)

    def test_non_utc_offset_refused_by_daily_gate(self):
        p = scenario()
        p["daily_fixture"]["utc_timestamp"] = "2026-07-02T06:00:00+09:00"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_daily_stop_priority_over_stale_evidence(self):
        p = scenario()
        for rec in p["evidence"]["records"]:
            rec["observed_at_utc"] = "2026-06-30T21:00:00Z"
        p["daily_fixture"]["previous_daily_stop"] = True
        p["snapshots"][-1]["daily_stop_latched"] = True
        p["snapshots"][-1]["last_status"] = "DAILY_STOP"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.deny(r)

    def test_stale_snapshot_priority_over_evidence_conflict(self):
        p = scenario()
        p["expected_day"] = "2026-07-02"
        p["daily_fixture"]["utc_timestamp"] = "2026-07-02T21:00:00+00:00"
        p["daily_fixture"]["previous_day_label"] = "2026-07-02"
        p["evidence"]["records"][1]["positions"] = "PRESENT"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_STALE_STOP_RECORD_FAIL_CLOSED")
        self.deny(r)

    def test_synthetic_evidence_scope_mismatch_denied(self):
        p = scenario()
        p["evidence"]["records"][0]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.deny(r)

    def test_evidence_two_different_instants_stays_insufficient(self):
        p = scenario()
        p["evidence"]["records"][1]["observed_at_utc"] = (
            "2026-07-01T20:59:59Z")
        r = evaluate(p)
        self.assertEqual(r["evidence_status"], "EVIDENCE_INSUFFICIENT_NO_GO")
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.deny(r)

    def test_unknown_ea_and_pending_orders_do_not_infer_absent(self):
        p = scenario()
        for rec in p["evidence"]["records"]:
            rec["ea_running"] = "UNKNOWN"
            rec["pending_orders"] = "UNKNOWN"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.deny(r)

    def test_duplicate_evidence_ids_do_not_promote(self):
        p = scenario()
        p["evidence"]["records"][1]["evidence_id"] = "EVID_A"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_broker_confirmation_claim_in_d517_is_rejected(self):
        p = scenario()
        p["evidence_mode"] = "D517_LEDGER"
        p["evidence"] = actual_ledger()
        p["evidence"]["broker_verified"] = True
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_evidence_wrong_schema_boolean_is_rejected(self):
        p = scenario()
        p["evidence"]["schema_version"] = True
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_corrupt_stop_status_and_misleading_evidence(self):
        p = scenario()
        p["snapshots"][-1]["last_status"] = "ORDER_APPROVED"
        p["evidence"]["records"][1]["positions"] = "PRESENT"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_missing_restore_never_unlocks_even_when_evidence_coherent(self):
        p = scenario()
        p["restored_snapshot"] = None
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_missing_or_out_of_order_sequence_denied(self):
        for minimum in (-1, True, 10**12, "42", None):
            with self.subTest(minimum=minimum):
                p = scenario()
                p["minimum_sequence"] = minimum
                r = evaluate(p)
                self.assertEqual(r["status"],
                                 "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
                self.deny(r)

    def test_restore_same_day_with_lower_sequence_denied(self):
        p = scenario()
        p["minimum_sequence"] = 43
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_snapshot_chain_gap_denied(self):
        p = scenario()
        first = copy.deepcopy(p["snapshots"][-1])
        first["sequence"] = 40
        p["snapshots"].insert(0, first)
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_snapshot_chain_stop_disappears_denied(self):
        p = scenario()
        first = copy.deepcopy(p["snapshots"][-1])
        first["sequence"] = 41
        first["daily_stop_latched"] = True
        first["last_status"] = "DAILY_STOP"
        p["snapshots"].insert(0, first)
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_snapshot_chain_hard_stop_downgrade_denied(self):
        p = scenario()
        first = copy.deepcopy(p["snapshots"][-1])
        first["sequence"] = 41
        first["daily_stop_latched"] = True
        first["last_status"] = "HARD_STOP_DD5"
        p["snapshots"].insert(0, first)
        p["snapshots"][-1]["daily_stop_latched"] = True
        p["snapshots"][-1]["last_status"] = "DAILY_STOP"
        p["daily_fixture"]["previous_daily_stop"] = True
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_risk_exceeded_but_no_daily_stop_blocks_as_review(self):
        p = scenario()
        p["daily_fixture"]["risk_fixture"]["single_trade_risk_jpy"] = "501"
        r = evaluate(p)
        self.assertEqual(r["daily_status"], "RISK_REVIEW_REQUIRED")
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.deny(r)

    def test_daily_loss_at_limit_and_dd_both_stop(self):
        p = scenario()
        p["daily_fixture"]["risk_fixture"]["equity_jpy"] = "95000"
        p["daily_fixture"]["risk_fixture"]["daily_loss_jpy"] = "1500"
        p["daily_fixture"]["previous_daily_stop"] = True
        p["snapshots"][-1]["daily_stop_latched"] = True
        p["snapshots"][-1]["last_status"] = "HARD_STOP_DD5"
        r = evaluate(p)
        self.assertEqual(r["daily_status"], "HARD_STOP_DD5")
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.deny(r)

    def test_daily_risk_invalid_and_snapshot_stopped_remains_blocked(self):
        p = scenario()
        p["daily_fixture"]["risk_fixture"]["equity_jpy"] = "bad"
        p["snapshots"][-1]["daily_stop_latched"] = True
        p["snapshots"][-1]["last_status"] = "DAILY_STOP"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_date_calendar_invalid_patterns_are_rejected(self):
        for bad in ("2026-00-01", "2026-02-30", "2026-13-01",
                    "2026-07-00", "2026-07-1 ", "2000-00-00"):
            with self.subTest(date=bad):
                p = scenario()
                p["daily_fixture"]["previous_day_label"] = bad
                r = evaluate(p)
                self.assertEqual(r["status"],
                                 "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
                self.deny(r)

    def test_utc_timestamp_without_offset_denied(self):
        p = scenario()
        p["daily_fixture"]["utc_timestamp"] = "2026-07-01T21:00:00"
        r = evaluate(p)
        self.assertEqual(r["status"], "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_outer_unknown_and_spoofed_fields_rejected(self):
        for key, value in (("orders_enabled", True),
                           ("broker_verified", True),
                           ("verified_values", {"USDJPY": "verified"})):
            with self.subTest(field=key):
                p = scenario()
                p[key] = value
                r = evaluate(p)
                self.assertEqual(r["status"],
                                 "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
                self.deny(r)

    def test_outer_missing_fields_rejected(self):
        for key in ("origin", "evidence", "daily_fixture",
                    "expected_day", "restored_snapshot", "snapshots"):
            with self.subTest(key=key):
                p = scenario()
                del p[key]
                r = evaluate(p)
                self.assertEqual(r["status"],
                                 "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
                self.deny(r)

    def test_input_objects_are_not_mutated(self):
        p = scenario()
        old = copy.deepcopy(p)
        self.deny(evaluate(p))
        self.assertEqual(p, old)
        p["evidence"]["records"][1]["positions"] = "PRESENT"
        old = copy.deepcopy(p)
        self.deny(evaluate(p))
        self.assertEqual(p, old)

    def test_two_independent_calls_do_not_share_authority_state(self):
        good = scenario()
        bad = copy.deepcopy(good)
        bad["daily_fixture"]["previous_daily_stop"] = True
        result_bad = evaluate(bad)
        self.assertEqual(result_bad["status"],
                         "INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED")
        self.deny(result_bad)
        result_good = evaluate(good)
        self.assertEqual(result_good["status"],
                         "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.deny(result_good)

    def test_every_result_stays_non_authorizing_after_input_mutations(self):
        changes = [
            lambda p: p["evidence"]["records"][1].update(positions="PRESENT"),
            lambda p: p["evidence"]["records"][1].update(ea_running="UNKNOWN"),
            lambda p: p["snapshots"][0].update(sequence=12),
            lambda p: p["daily_fixture"].update(previous_daily_stop=True),
            lambda p: p["daily_fixture"].update(utc_timestamp="invalid"),
            lambda p: p.update(expected_day="2026-07-02"),
            lambda p: p["evidence"].update(origin="LIVE"),
        ]
        for change in changes:
            p = scenario()
            change(p)
            with self.subTest(change=repr(change)):
                self.deny(evaluate(p))


if __name__ == "__main__":
    unittest.main()
