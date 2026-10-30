"""D5-23: synthetic checkpoint, replay, rollback and revocation-erasure regression."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts.p0_01_d5_23_history_checkpoint import (
    audit_synthetic_history_checkpoint as audit,
    build_synthetic_history_chain as build,
)


def lifecycle():
    record_id = "SYNTH_APPROVAL_TEST"
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "record": {
            "record_id": record_id, "action": "EA_EXECUTION",
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A",
            "stop_cause": "NONE",
            "issued_at_utc": "2026-07-01T21:00:00Z",
            "expires_at_utc": "2026-07-01T21:30:00Z",
        },
        "events": [{
            "sequence": 0, "event_type": "PROPOSED", "record_id": record_id,
            "occurred_at_utc": "2026-07-01T21:00:00Z",
        }],
        "request": {
            "action": "EA_EXECUTION", "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A", "stop_cause": "NONE",
        },
        "as_of_utc": "2026-07-01T21:10:00Z",
    }


def claim(p):
    p["events"].append({
        "sequence": 1, "event_type": "APPROVAL_CLAIMED",
        "record_id": p["record"]["record_id"],
        "occurred_at_utc": "2026-07-01T21:05:00Z",
    })


def revoke(p):
    p["events"].append({
        "sequence": len(p["events"]), "event_type": "REVOKED",
        "record_id": p["record"]["record_id"],
        "occurred_at_utc": "2026-07-01T21:06:00Z",
    })


def gate():
    snapshot = {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "trading_day_start_ny_date": "2026-07-01",
        "daily_stop_latched": False, "last_status": "SYNTHETIC_MONITORING_ONLY",
        "sequence": 10,
    }
    def rec(id_, kind):
        return {
            "evidence_id": id_, "source_kind": kind,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "observed_at_utc": "2026-07-01T21:00:00Z",
            "positions": "ABSENT", "pending_orders": "ABSENT", "ea_running": "ABSENT",
        }
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "evidence_mode": "SYNTHETIC_RECORDS",
        "evidence": {
            "origin": "SYNTHETIC_ONLY", "schema_version": 1,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "records": [rec("EVID_A", "USER_REPORT"),
                        rec("EVID_B", "VISUAL_OBSERVATION")],
        },
        "daily_fixture": {
            "origin": "SYNTHETIC_ONLY",
            "utc_timestamp": "2026-07-01T21:00:00+00:00",
            "previous_day_label": "2026-07-01", "previous_daily_stop": False,
            "next_day_safety_checked": False,
            "risk_fixture": {
                "origin": "SYNTHETIC_ONLY", "equity_jpy": "100000",
                "peak_equity_jpy": "100000", "single_trade_risk_jpy": "0",
                "aggregate_risk_jpy": "0", "daily_loss_jpy": "0",
            },
        },
        "snapshots": [snapshot], "restored_snapshot": snapshot,
        "expected_day": "2026-07-01", "minimum_sequence": 10,
    }


def bundle(p=None):
    p = lifecycle() if p is None else p
    j = build(p)
    if j is None:
        raise ValueError("Synthetic fixture invalid")
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "lifecycle": p, "journal": j,
        "checkpoint": {
            "record_id": p["record"]["record_id"],
            "sequence": j[-1]["sequence"], "head_hash": j[-1]["event_hash"],
        },
        "integrated_fixture": gate(),
    }


class D523HistoryCheckpointTests(unittest.TestCase):
    def denied(self, r):
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertIsNone(r["verified_values"])
        self.assertIs(r["safety_hold_latched"], True)
        self.assertEqual(r["effective_approved_actions"], [])
        self.assertEqual(set(r), {
            "status", "lifecycle_status", "downstream_status", "events_checked",
            "approval_verified", "action_authorized", "ea_execution_authorized",
            "order_authorized", "stop_release_authorized",
            "effective_approved_actions", "safety_hold_latched",
            "runtime_go_no_go", "verified_values", "broker_verified",
            "production_usable", "read_only_ex4_execution_approved",
            "terminal_execution_approved", "orders_generated",
            "forward_trading_enabled", "phase_1",
        })
        for field in ("approval_verified", "action_authorized",
                      "ea_execution_authorized", "order_authorized",
                      "stop_release_authorized", "broker_verified",
                      "production_usable", "read_only_ex4_execution_approved",
                      "terminal_execution_approved", "orders_generated",
                      "forward_trading_enabled"):
            self.assertIs(r[field], False)

    def assert_status(self, p, status):
        r = audit(p)
        self.assertEqual(r["status"], status)
        self.denied(r)
        return r

    def test_proposed_history_coherent_but_not_trusted(self):
        r = self.assert_status(bundle(), "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assertEqual(r["events_checked"], 1)
        self.assertEqual(r["downstream_status"], "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")

    def test_claimed_history_coherent_but_not_approved(self):
        p = lifecycle()
        claim(p)
        r = self.assert_status(bundle(p), "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assertEqual(r["lifecycle_status"], "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO")
        self.assertEqual(r["downstream_status"],
                         "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO")

    def test_revoked_history_coherent_but_no_permission(self):
        p = lifecycle()
        claim(p)
        revoke(p)
        r = self.assert_status(bundle(p), "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assertEqual(r["events_checked"], 3)
        self.assertEqual(r["lifecycle_status"], "LIFECYCLE_REVOKED_NO_GO")

    def test_expired_claimed_history_remains_no_go(self):
        p = lifecycle()
        claim(p)
        p["as_of_utc"] = "2026-07-01T21:30:00Z"
        r = self.assert_status(bundle(p), "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assertEqual(r["lifecycle_status"], "LIFECYCLE_EXPIRED_NO_GO")

    def test_stop_release_history_never_releases(self):
        p = lifecycle()
        p["record"]["action"] = p["request"]["action"] = "STOP_RELEASE"
        p["record"]["stop_cause"] = p["request"]["stop_cause"] = "DD5"
        claim(p)
        r = self.assert_status(bundle(p), "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assertEqual(r["downstream_status"], "STOP_RELEASE_CLAIM_DENIED_NO_GO")

    def test_integrated_stop_latch_still_blocks(self):
        p = bundle()
        g = p["integrated_fixture"]
        g["daily_fixture"]["previous_daily_stop"] = True
        g["snapshots"][0]["daily_stop_latched"] = True
        g["snapshots"][0]["last_status"] = "DAILY_STOP"
        r = self.assert_status(p, "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assertEqual(r["downstream_status"], "EVIDENCE_OR_STOP_BLOCKED_NO_GO")

    def test_integrated_conflicting_evidence_blocks(self):
        p = bundle()
        p["integrated_fixture"]["evidence"]["records"][1]["positions"] = "PRESENT"
        r = self.assert_status(p, "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assertEqual(r["downstream_status"], "EVIDENCE_OR_STOP_BLOCKED_NO_GO")

    def test_replayed_proposal_against_claimed_checkpoint_detected(self):
        p = lifecycle()
        old = bundle(copy.deepcopy(p))
        claim(p)
        current = bundle(p)
        old["checkpoint"] = copy.deepcopy(current["checkpoint"])
        self.assert_status(old, "HISTORY_ROLLBACK_DETECTED_NO_GO")

    def test_replayed_claim_against_revoked_checkpoint_detected(self):
        p = lifecycle()
        claim(p)
        old = bundle(copy.deepcopy(p))
        revoke(p)
        current = bundle(p)
        old["checkpoint"] = copy.deepcopy(current["checkpoint"])
        self.assert_status(old, "HISTORY_ROLLBACK_DETECTED_NO_GO")

    def test_revocation_deleted_and_old_journal_rebuilt_detected(self):
        p = lifecycle()
        claim(p)
        revoke(p)
        original = bundle(p)
        p2 = copy.deepcopy(p)
        p2["events"] = p2["events"][:-1]
        shortened = bundle(p2)
        shortened["checkpoint"] = original["checkpoint"]
        self.assert_status(shortened, "HISTORY_ROLLBACK_DETECTED_NO_GO")

    def test_revocation_deleted_without_journal_update_detected(self):
        p = lifecycle()
        claim(p)
        revoke(p)
        original = bundle(p)
        original["lifecycle"]["events"].pop()
        self.assert_status(original, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_claim_deleted_while_checkpoint_kept_detected(self):
        p = lifecycle()
        claim(p)
        old = bundle(p)
        old["lifecycle"]["events"].pop()
        old["journal"] = build(old["lifecycle"])
        self.assert_status(old, "HISTORY_ROLLBACK_DETECTED_NO_GO")

    def test_earlier_checkpoint_is_stale_even_if_prefix_matches(self):
        p = lifecycle()
        claim(p)
        b = bundle(p)
        b["checkpoint"]["sequence"] = 0
        b["checkpoint"]["head_hash"] = b["journal"][0]["event_hash"]
        self.assert_status(b, "HISTORY_CHECKPOINT_STALE_NO_GO")

    def test_stale_checkpoint_with_revocation_tail_rejected(self):
        p = lifecycle()
        claim(p)
        revoke(p)
        b = bundle(p)
        b["checkpoint"]["sequence"] = 1
        b["checkpoint"]["head_hash"] = b["journal"][1]["event_hash"]
        self.assert_status(b, "HISTORY_CHECKPOINT_STALE_NO_GO")

    def test_checkpoint_hash_wrong_even_when_sequence_valid(self):
        p = bundle()
        p["checkpoint"]["head_hash"] = "f" * 64
        self.assert_status(p, "HISTORY_CHECKPOINT_MISMATCH_NO_GO")

    def test_checkpoint_record_id_swapped(self):
        p = bundle()
        p["checkpoint"]["record_id"] = "SYNTH_APPROVAL_OTHER"
        self.assert_status(p, "HISTORY_CHECKPOINT_MISMATCH_NO_GO")

    def test_checkpoint_sequence_ahead_of_history(self):
        p = bundle()
        p["checkpoint"]["sequence"] = 3
        self.assert_status(p, "HISTORY_ROLLBACK_DETECTED_NO_GO")

    def test_bool_checkpoint_sequence_rejected(self):
        p = bundle()
        p["checkpoint"]["sequence"] = True
        self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_negative_checkpoint_sequence_rejected(self):
        p = bundle()
        p["checkpoint"]["sequence"] = -1
        self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_checkpoint_hash_invalid_or_uppercase_rejected(self):
        for hash_value in ("AA" * 32, "", "0" * 63, True, None):
            with self.subTest(hash_value=repr(hash_value)):
                p = bundle()
                p["checkpoint"]["head_hash"] = hash_value
                self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_journal_hash_changed_detected(self):
        p = bundle()
        p["journal"][0]["event_hash"] = "f" * 64
        self.assert_status(p, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_journal_previous_hash_changed_detected(self):
        p = lifecycle()
        claim(p)
        b = bundle(p)
        b["journal"][1]["previous_hash"] = "f" * 64
        self.assert_status(b, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_journal_row_order_swap_detected(self):
        p = lifecycle()
        claim(p)
        b = bundle(p)
        b["journal"].reverse()
        self.assert_status(b, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_journal_sequence_duplicate_detected(self):
        p = lifecycle()
        claim(p)
        b = bundle(p)
        b["journal"][1]["sequence"] = 0
        self.assert_status(b, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_journal_sequence_boolean_rejected_as_mismatch(self):
        p = bundle()
        p["journal"][0]["sequence"] = False
        self.assert_status(p, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_journal_shorter_than_lifecycle_detected(self):
        p = lifecycle()
        claim(p)
        b = bundle(p)
        b["journal"] = b["journal"][:-1]
        self.assert_status(b, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_journal_row_extra_or_missing_field_detected(self):
        p = bundle()
        p["journal"][0]["orders_allowed"] = True
        self.assert_status(p, "HISTORY_CHAIN_MISMATCH_NO_GO")
        p = bundle()
        del p["journal"][0]["previous_hash"]
        self.assert_status(p, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_journal_nonlist_rejected(self):
        p = bundle()
        p["journal"] = {}
        self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_empty_journal_rejected(self):
        p = bundle()
        p["journal"] = []
        self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_missing_checkpoint_rejected(self):
        p = bundle()
        del p["checkpoint"]
        self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_checkpoint_extra_field_rejected(self):
        p = bundle()
        p["checkpoint"]["approved"] = True
        self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_record_scope_tamper_without_rehash_detected(self):
        p = bundle()
        p["lifecycle"]["record"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        self.assert_status(p, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_record_action_tamper_without_rehash_detected(self):
        p = bundle()
        p["lifecycle"]["record"]["action"] = "ORDER_ACTION"
        self.assert_status(p, "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_event_time_tamper_without_rehash_detected(self):
        p = bundle()
        p["lifecycle"]["events"][0]["occurred_at_utc"] = "2026-07-01T21:00:01Z"
        self.assert_status(p, "HISTORY_LIFECYCLE_REJECTED_FAIL_CLOSED")

    def test_event_reorder_rejected_by_lifecycle(self):
        p = lifecycle()
        claim(p)
        b = bundle(p)
        b["lifecycle"]["events"].reverse()
        self.assert_status(b, "HISTORY_LIFECYCLE_REJECTED_FAIL_CLOSED")

    def test_unrecognized_event_rejected(self):
        p = bundle()
        p["lifecycle"]["events"][0]["event_type"] = "APPROVED"
        self.assert_status(p, "HISTORY_LIFECYCLE_REJECTED_FAIL_CLOSED")

    def test_lifecycle_and_journal_both_rewritten_without_anchor_detected(self):
        p = bundle()
        p["lifecycle"]["record"]["terminal_scope"] = "SYNTHETIC_TERMINAL_B"
        p["lifecycle"]["request"]["terminal_scope"] = "SYNTHETIC_TERMINAL_B"
        p["journal"] = build(p["lifecycle"])
        self.assert_status(p, "HISTORY_CHECKPOINT_MISMATCH_NO_GO")

    def test_both_chain_and_checkpoint_rewritten_cannot_prove_authenticity(self):
        p = bundle()
        p["lifecycle"]["record"]["terminal_scope"] = "SYNTHETIC_TERMINAL_B"
        p["lifecycle"]["request"]["terminal_scope"] = "SYNTHETIC_TERMINAL_B"
        p["journal"] = build(p["lifecycle"])
        p["checkpoint"]["head_hash"] = p["journal"][-1]["event_hash"]
        # The *limitation* is explicit: synthetic comparison cannot detect
        # replacement of every untrusted input. Still NEVER grants authority.
        self.assert_status(p, "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")

    def test_replayed_revoked_log_with_forged_reference_remains_denied(self):
        p = lifecycle()
        claim(p)
        revoke(p)
        old = bundle(p)
        self.assert_status(old, "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        self.assert_status(copy.deepcopy(old),
                           "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")

    def test_outer_live_origin_or_bool_schema_rejected(self):
        for field, value in (("origin", "BROKER_LIVE"),
                             ("schema_version", True), ("schema_version", 2)):
            with self.subTest(field=field, value=value):
                p = bundle()
                p[field] = value
                self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_extra_authorization_field_rejected(self):
        p = bundle()
        p["terminal_execution_approved"] = True
        self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_malformed_bundle_inputs_rejected(self):
        for p in (None, [], {}, "invalid", False):
            with self.subTest(value=repr(p)):
                self.assert_status(p, "HISTORY_INPUT_REJECTED_FAIL_CLOSED")

    def test_build_refuses_invalid_lifecycle(self):
        p = lifecycle()
        p["record"]["issued_at_utc"] = "2026-02-30T00:00:00Z"
        self.assertIsNone(build(p))

    def test_build_canonical_chain_is_deterministic_without_authority(self):
        p = lifecycle()
        claim(p)
        j1, j2 = build(p), build(copy.deepcopy(p))
        self.assertEqual(j1, j2)
        self.assertEqual(j1[0]["previous_hash"], "0" * 64)
        self.assertEqual(j1[1]["previous_hash"], j1[0]["event_hash"])
        self.assertEqual(len(j1[1]["event_hash"]), 64)

    def test_input_not_mutated(self):
        p = bundle()
        original = copy.deepcopy(p)
        self.denied(audit(p))
        self.assertEqual(p, original)

    def test_independent_calls_do_not_retain_checkpoint_state(self):
        p = lifecycle()
        claim(p)
        old = bundle(copy.deepcopy(p))
        revoke(p)
        current = bundle(p)
        self.assert_status(current, "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        # Reusing older locally supplied checkpoint is not a proof of freshness.
        self.assert_status(old, "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")
        old["checkpoint"] = current["checkpoint"]
        self.assert_status(old, "HISTORY_ROLLBACK_DETECTED_NO_GO")

    def test_downstream_fake_go_rejected(self):
        p = bundle()
        with patch(
            "scripts.p0_01_d5_23_history_checkpoint.audit_synthetic_lifecycle_with_authority",
            return_value={"status": "GO", "runtime_go_no_go": "GO"},
        ):
            self.assert_status(p, "HISTORY_DOWNSTREAM_REJECTED_FAIL_CLOSED")

    def test_downstream_fake_grant_rejected(self):
        p = bundle()
        with patch(
            "scripts.p0_01_d5_23_history_checkpoint.audit_synthetic_lifecycle_with_authority",
            return_value={"status": "LIFECYCLE_AND_AUTHORITY_NO_GO",
                          "runtime_go_no_go": "NO_GO",
                          "action_authorized": True},
        ):
            self.assert_status(p, "HISTORY_DOWNSTREAM_REJECTED_FAIL_CLOSED")

    def test_downstream_fake_stop_release_rejected(self):
        p = bundle()
        with patch(
            "scripts.p0_01_d5_23_history_checkpoint.audit_synthetic_lifecycle_with_authority",
            return_value={"status": "LIFECYCLE_AND_AUTHORITY_NO_GO",
                          "safety_hold_latched": False},
        ):
            self.assert_status(p, "HISTORY_DOWNSTREAM_REJECTED_FAIL_CLOSED")


if __name__ == "__main__":
    unittest.main()
