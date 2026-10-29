"""D5-19: combine synthetic evidence, daily stop and recovery, always NO_GO."""
import copy
import json
from pathlib import Path
import unittest

from scripts.p0_01_d5_19_integrated_no_go import (
    evaluate_offline_integrated_no_go as check,
)


def synthetic_evidence():
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "account_scope": "SYNTHETIC_ACCOUNT_A",
        "records": [
            {"evidence_id": "EVID_A", "source_kind": "USER_REPORT",
             "account_scope": "SYNTHETIC_ACCOUNT_A",
             "observed_at_utc": "2026-07-01T21:00:00Z",
             "positions": "ABSENT", "pending_orders": "ABSENT",
             "ea_running": "ABSENT"},
            {"evidence_id": "EVID_B", "source_kind": "VISUAL_OBSERVATION",
             "account_scope": "SYNTHETIC_ACCOUNT_A",
             "observed_at_utc": "2026-07-01T21:00:00Z",
             "positions": "ABSENT", "pending_orders": "ABSENT",
             "ea_running": "ABSENT"},
        ],
    }


def ledger():
    file = (Path(__file__).resolve().parents[1] /
            "specs/p0_01_d5_17_evidence_reconciliation_status.json")
    with file.open(encoding="utf-8") as handle:
        return json.load(handle)


def fixture():
    snapshot = {
        "origin": "SYNTHETIC_ONLY",
        "schema_version": 1,
        "trading_day_start_ny_date": "2026-07-01",
        "daily_stop_latched": False,
        "last_status": "SYNTHETIC_MONITORING_ONLY",
        "sequence": 10,
    }
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "evidence_mode": "SYNTHETIC_RECORDS",
        "evidence": synthetic_evidence(),
        "daily_fixture": {
            "origin": "SYNTHETIC_ONLY",
            "utc_timestamp": "2026-07-01T21:00:00+00:00",
            "previous_day_label": "2026-07-01",
            "previous_daily_stop": False,
            "next_day_safety_checked": False,
            "risk_fixture": {
                "origin": "SYNTHETIC_ONLY",
                "equity_jpy": "100000",
                "peak_equity_jpy": "100000",
                "single_trade_risk_jpy": "0",
                "aggregate_risk_jpy": "0",
                "daily_loss_jpy": "0",
            },
        },
        "snapshots": [snapshot],
        "restored_snapshot": snapshot,
        "expected_day": "2026-07-01",
        "minimum_sequence": 10,
    }


def latch(f, last_status="DAILY_STOP"):
    f["daily_fixture"]["previous_daily_stop"] = True
    f["snapshots"][-1]["daily_stop_latched"] = True
    f["snapshots"][-1]["last_status"] = last_status


class D519IntegratedNoGoTests(unittest.TestCase):
    def deny(self, r):
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(r["verified_values"])
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertIs(r["safety_hold_latched"], True)
        for k in ("broker_verified", "production_usable", "orders_generated",
                  "read_only_ex4_execution_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(r[k], False)

    def test_clean_synthetic_maintains_policy_hold(self):
        r = check(fixture())
        self.assertEqual(r["status"],
                         "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertIs(r["daily_stop_latched"], False)
        self.deny(r)

    def test_existing_unreconciled_d517_ledger_blocks(self):
        f = fixture()
        f["evidence_mode"] = "D517_LEDGER"
        f["evidence"] = ledger()
        r = check(f)
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.assertEqual(r["evidence_status"],
                         "D517_REPORTS_NOT_RECONCILED_NO_GO")
        self.deny(r)

    def test_daily_stop_remains_latched_with_coherent_evidence(self):
        f = fixture()
        latch(f)
        r = check(f)
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.assertIs(r["daily_stop_latched"], True)
        self.deny(r)

    def test_daily_stop_and_unreconciled_ledger_both_block(self):
        f = fixture()
        latch(f)
        f["evidence_mode"] = "D517_LEDGER"
        f["evidence"] = ledger()
        r = check(f)
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.deny(r)

    def test_new_day_review_does_not_release_stop(self):
        f = fixture()
        latch(f, "NEXT_DAY_REVIEW_PENDING")
        f["daily_fixture"]["previous_day_label"] = "2026-06-30"
        r = check(f)
        self.assertEqual(r["daily_status"], "NEXT_DAY_REVIEW_PENDING")
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.deny(r)

    def test_hard_dd5_block(self):
        f = fixture()
        f["daily_fixture"]["risk_fixture"]["equity_jpy"] = "95000"
        f["snapshots"][-1]["daily_stop_latched"] = True
        f["snapshots"][-1]["last_status"] = "HARD_STOP_DD5"
        r = check(f)
        self.assertEqual(r["daily_status"], "HARD_STOP_DD5")
        self.assertEqual(r["status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.deny(r)

    def test_daily_loss_limit_block(self):
        f = fixture()
        f["daily_fixture"]["risk_fixture"]["daily_loss_jpy"] = "1500"
        f["snapshots"][-1]["daily_stop_latched"] = True
        f["snapshots"][-1]["last_status"] = "DAILY_STOP"
        r = check(f)
        self.assertEqual(r["daily_status"], "DAILY_STOP")
        self.deny(r)

    def test_daily_stopped_recovery_clean_disagreement(self):
        f = fixture()
        f["daily_fixture"]["previous_daily_stop"] = True
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED")
        self.assertIs(r["daily_stop_latched"], True)
        self.deny(r)

    def test_daily_clean_recovery_stopped_disagreement(self):
        f = fixture()
        f["snapshots"][-1]["daily_stop_latched"] = True
        f["snapshots"][-1]["last_status"] = "DAILY_STOP"
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED")
        self.assertIs(r["daily_stop_latched"], True)
        self.deny(r)

    def test_conflicting_position_claim_blocks(self):
        f = fixture()
        f["evidence"]["records"][1]["positions"] = "PRESENT"
        r = check(f)
        self.assertEqual(r["evidence_status"], "EVIDENCE_CONFLICT_NO_GO")
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.deny(r)

    def test_conflicting_pending_order_claim_blocks(self):
        f = fixture()
        f["evidence"]["records"][1]["pending_orders"] = "PRESENT"
        self.assertEqual(check(f)["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")

    def test_conflicting_ea_claim_blocks(self):
        f = fixture()
        f["evidence"]["records"][1]["ea_running"] = "PRESENT"
        self.assertEqual(check(f)["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")

    def test_missing_evidence_stays_blocked(self):
        f = fixture()
        f["evidence"]["records"] = f["evidence"]["records"][:1]
        r = check(f)
        self.assertEqual(r["evidence_status"], "EVIDENCE_INSUFFICIENT_NO_GO")
        self.assertEqual(r["status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.deny(r)

    def test_different_evidence_instant_stays_insufficient(self):
        f = fixture()
        f["evidence"]["records"][1]["observed_at_utc"] = (
            "2026-07-02T21:00:00Z")
        r = check(f)
        self.assertEqual(r["evidence_status"], "EVIDENCE_INSUFFICIENT_NO_GO")
        self.deny(r)

    def test_different_account_scope_stays_blocked(self):
        f = fixture()
        f["evidence"]["records"][1]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        r = check(f)
        self.assertEqual(r["evidence_status"], "ACCOUNT_SCOPE_MISMATCH_NO_GO")
        self.deny(r)

    def test_corrupted_evidence_rejected(self):
        f = fixture()
        f["evidence"]["records"][0]["evidence_id"] = 10
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_d517_spoofed_broker_confirmation_rejected(self):
        f = fixture()
        f["evidence_mode"] = "D517_LEDGER"
        f["evidence"] = ledger()
        f["evidence"]["broker_verified"] = True
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_risk_invalid_rejected(self):
        f = fixture()
        f["daily_fixture"]["risk_fixture"]["equity_jpy"] = "0"
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_corrupted_recovery_chain_rejected(self):
        f = fixture()
        f["snapshots"][-1]["schema_version"] = 9
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_stale_recovery_sequence_rejected(self):
        f = fixture()
        f["minimum_sequence"] = 11
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_nonmatching_restore_rejected(self):
        f = fixture()
        f["restored_snapshot"] = copy.deepcopy(f["snapshots"][-1])
        f["restored_snapshot"]["sequence"] = 11
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_invalid_previous_day_rejected_even_if_old_daily_gate_lax(self):
        f = fixture()
        f["daily_fixture"]["previous_day_label"] = "2026-07-00"
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_nonexistent_previous_day_rejected(self):
        f = fixture()
        f["daily_fixture"]["previous_day_label"] = "2026-02-30"
        self.assertEqual(check(f)["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")

    def test_future_previous_day_rejected(self):
        f = fixture()
        f["daily_fixture"]["previous_day_label"] = "2026-07-02"
        self.assertEqual(check(f)["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")

    def test_wrong_expected_day_rejected(self):
        f = fixture()
        f["expected_day"] = "2026-07-02"
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_bad_utc_timestamp_rejected(self):
        f = fixture()
        f["daily_fixture"]["utc_timestamp"] = "2026-07-01T21:00:00"
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_bad_top_level_types_rejected(self):
        for bad in (None, [], "invalid", {}, True, {"origin": "SYNTHETIC_ONLY"}):
            with self.subTest(bad=repr(bad)):
                r = check(bad)
                self.assertEqual(r["status"],
                                 "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
                self.deny(r)

    def test_wrong_schema_bool_or_live_origin_rejected(self):
        for key, value in (
            ("schema_version", True),
            ("schema_version", 2),
            ("origin", "LIVE"),
            ("evidence_mode", "MT4_LIVE"),
            ("minimum_sequence", True),
        ):
            with self.subTest(field=key, value=value):
                f = fixture()
                f[key] = value
                r = check(f)
                self.assertEqual(r["status"],
                                 "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED"
                                 if key != "minimum_sequence"
                                 else "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
                self.deny(r)

    def test_extra_field_or_missing_field_rejected(self):
        f = fixture()
        f["orders_enabled"] = True
        self.assertEqual(check(f)["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")
        f = fixture()
        del f["snapshots"]
        self.assertEqual(check(f)["status"],
                         "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED")

    def test_malformed_snapshot_list_fails_closed(self):
        f = fixture()
        f["snapshots"] = [None]
        r = check(f)
        self.assertEqual(r["status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.deny(r)

    def test_integration_does_not_mutate_input(self):
        f = fixture()
        old = copy.deepcopy(f)
        self.deny(check(f))
        self.assertEqual(f, old)


if __name__ == "__main__":
    unittest.main()
