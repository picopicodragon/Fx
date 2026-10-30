"""D5-24: untrusted reference-anchor and simulated persistence fault checks."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts.p0_01_d5_23_history_checkpoint import (
    build_synthetic_history_chain as build_chain,
)
from scripts.p0_01_d5_24_reference_fault_gate import (
    audit_synthetic_reference_and_failures as audit,
    build_synthetic_reference_fixture as build_ref,
)


def lifecycle():
    rid = "SYNTH_APPROVAL_TEST"
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "record": {
            "record_id": rid, "action": "EA_EXECUTION",
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A",
            "stop_cause": "NONE", "issued_at_utc": "2026-07-01T21:00:00Z",
            "expires_at_utc": "2026-07-01T21:30:00Z",
        },
        "events": [{
            "sequence": 0, "event_type": "PROPOSED", "record_id": rid,
            "occurred_at_utc": "2026-07-01T21:00:00Z",
        }],
        "request": {
            "action": "EA_EXECUTION", "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A", "stop_cause": "NONE",
        },
        "as_of_utc": "2026-07-01T21:10:00Z",
    }


def claimed(p):
    p["events"].append({
        "sequence": 1, "event_type": "APPROVAL_CLAIMED",
        "record_id": p["record"]["record_id"],
        "occurred_at_utc": "2026-07-01T21:05:00Z",
    })


def revoked(p):
    p["events"].append({
        "sequence": len(p["events"]), "event_type": "REVOKED",
        "record_id": p["record"]["record_id"],
        "occurred_at_utc": "2026-07-01T21:06:00Z",
    })


def integrated():
    snap = {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "trading_day_start_ny_date": "2026-07-01",
        "daily_stop_latched": False,
        "last_status": "SYNTHETIC_MONITORING_ONLY", "sequence": 10,
    }

    def ev(eid, source):
        return {
            "evidence_id": eid, "source_kind": source,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "observed_at_utc": "2026-07-01T21:00:00Z",
            "positions": "ABSENT", "pending_orders": "ABSENT",
            "ea_running": "ABSENT",
        }
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "evidence_mode": "SYNTHETIC_RECORDS",
        "evidence": {
            "origin": "SYNTHETIC_ONLY", "schema_version": 1,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "records": [
                ev("EVID_A", "USER_REPORT"), ev("EVID_B", "VISUAL_OBSERVATION"),
            ],
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
        "snapshots": [snap], "restored_snapshot": snap,
        "expected_day": "2026-07-01", "minimum_sequence": 10,
    }


def history(p=None):
    p = lifecycle() if p is None else p
    journal = build_chain(p)
    if journal is None:
        raise ValueError("invalid lifecycle fixture")
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "lifecycle": p, "journal": journal,
        "checkpoint": {
            "record_id": p["record"]["record_id"],
            "sequence": journal[-1]["sequence"],
            "head_hash": journal[-1]["event_hash"],
        },
        "integrated_fixture": integrated(),
    }


def case(p=None, generation=1):
    hb = history(p)
    ref = build_ref(hb, generation)
    if ref is None:
        raise ValueError("invalid baseline fixture")
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "history_bundle": hb,
        "reference": ref, "minimum_generation": generation,
        "simulated_storage": {
            "write_state": "SYNTHETIC_CONFIRMED",
            "restore_state": "SYNTHETIC_CONFIRMED",
            "reference_read_state": "SYNTHETIC_CONFIRMED",
            "clock_state": "SYNTHETIC_CLOCK_STABLE",
            "concurrent_writer_detected": False,
        },
    }


class D524SyntheticReferenceFaultTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        for name in (
            "reference_authentic", "revocation_persisted",
            "trusted_clock_verified", "actual_replay_protection",
            "approval_verified", "action_authorized", "ea_execution_authorized",
            "order_authorized", "stop_release_authorized", "broker_verified",
            "production_usable", "read_only_ex4_execution_approved",
            "terminal_execution_approved", "orders_generated",
            "forward_trading_enabled",
        ):
            self.assertIs(result[name], False)

    def check(self, data, expected):
        result = audit(data)
        self.assertEqual(result["status"], expected)
        self.denied(result)
        return result

    def test_synthetic_proposal_match_does_not_authorize(self):
        r = self.check(case(), "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")
        self.assertEqual(r["history_status"],
                         "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO")

    def test_synthetic_claim_match_does_not_authorize(self):
        p = lifecycle()
        claimed(p)
        self.check(case(p), "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_synthetic_revocation_match_does_not_release(self):
        p = lifecycle()
        claimed(p)
        revoked(p)
        c = case(p)
        self.assertIs(c["reference"]["revocation_tombstone"], True)
        self.check(c, "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_revoke_before_claim_match_still_no_go(self):
        p = lifecycle()
        revoked(p)
        self.check(case(p), "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_expired_claimed_history_still_denies(self):
        p = lifecycle()
        claimed(p)
        p["as_of_utc"] = "2026-07-01T21:30:01Z"
        self.check(case(p), "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_stop_release_dd5_claim_still_denies(self):
        p = lifecycle()
        p["record"]["action"] = p["request"]["action"] = "STOP_RELEASE"
        p["record"]["stop_cause"] = p["request"]["stop_cause"] = "DD5"
        claimed(p)
        self.check(case(p), "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_daily_stop_does_not_lose_authority_hold(self):
        c = case()
        g = c["history_bundle"]["integrated_fixture"]
        g["daily_fixture"]["previous_daily_stop"] = True
        g["snapshots"][-1]["daily_stop_latched"] = True
        g["snapshots"][-1]["last_status"] = "DAILY_STOP"
        self.check(c, "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_evidence_conflict_does_not_lose_authority_hold(self):
        c = case()
        c["history_bundle"]["integrated_fixture"]["evidence"][
            "records"][1]["positions"] = "PRESENT"
        self.check(c, "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_replayed_proposal_against_claim_anchor_detected(self):
        p = lifecycle()
        old = case(copy.deepcopy(p))
        claimed(p)
        current = case(p)
        old["reference"] = copy.deepcopy(current["reference"])
        self.check(old, "ANCHOR_HISTORY_ROLLBACK_NO_GO")

    def test_replayed_claim_against_revocation_anchor_detected(self):
        p = lifecycle()
        claimed(p)
        old = case(copy.deepcopy(p))
        revoked(p)
        now = case(p)
        old["reference"] = copy.deepcopy(now["reference"])
        self.check(old, "ANCHOR_HISTORY_ROLLBACK_NO_GO")

    def test_revocation_erasure_then_rehash_and_checkpoint_detected(self):
        p = lifecycle()
        claimed(p)
        revoked(p)
        now = case(p)
        reduced = copy.deepcopy(p)
        reduced["events"].pop()
        old = case(reduced)
        old["reference"] = copy.deepcopy(now["reference"])
        self.check(old, "ANCHOR_HISTORY_ROLLBACK_NO_GO")

    def test_claim_history_and_checkpoint_forgery_without_ref_detected(self):
        c = case()
        p = c["history_bundle"]["lifecycle"]
        claimed(p)
        revised = history(p)
        c["history_bundle"] = revised
        self.check(c, "ANCHOR_REFERENCE_STALE_NO_GO")

    def test_same_length_altered_record_and_rehashed_checkpoint_detected(self):
        c = case()
        h = c["history_bundle"]
        h["lifecycle"]["record"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        h["lifecycle"]["request"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        c["history_bundle"] = history(h["lifecycle"])
        self.check(c, "ANCHOR_HEAD_MISMATCH_NO_GO")

    def test_same_length_altered_terminal_and_rehashed_checkpoint_detected(self):
        c = case()
        p = c["history_bundle"]["lifecycle"]
        p["record"]["terminal_scope"] = p["request"][
            "terminal_scope"] = "SYNTHETIC_TERMINAL_B"
        c["history_bundle"] = history(p)
        self.check(c, "ANCHOR_HEAD_MISMATCH_NO_GO")

    def test_same_length_altered_action_and_rehashed_checkpoint_detected(self):
        c = case()
        p = c["history_bundle"]["lifecycle"]
        p["record"]["action"] = p["request"]["action"] = "ORDER_ACTION"
        c["history_bundle"] = history(p)
        self.check(c, "ANCHOR_HEAD_MISMATCH_NO_GO")

    def test_full_history_checkpoint_and_ref_forgery_undetectable_but_denied(self):
        c = case()
        p = c["history_bundle"]["lifecycle"]
        p["record"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        p["request"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        fake = case(p)
        self.check(fake, "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_tombstone_false_while_revoked_detected(self):
        p = lifecycle()
        claimed(p)
        revoked(p)
        c = case(p)
        c["reference"]["revocation_tombstone"] = False
        self.check(c, "ANCHOR_REVOCATION_MISMATCH_NO_GO")

    def test_tombstone_true_without_revocation_detected(self):
        c = case()
        c["reference"]["revocation_tombstone"] = True
        self.check(c, "ANCHOR_REVOCATION_MISMATCH_NO_GO")

    def test_reference_record_id_mismatch_detected(self):
        c = case()
        c["reference"]["record_id"] = "SYNTH_APPROVAL_OTHER"
        self.check(c, "ANCHOR_RECORD_MISMATCH_NO_GO")

    def test_reference_sequence_ahead_detected(self):
        c = case()
        c["reference"]["sequence"] = 2
        self.check(c, "ANCHOR_HISTORY_ROLLBACK_NO_GO")

    def test_reference_behind_history_detected(self):
        p = lifecycle()
        claimed(p)
        c = case(p)
        c["reference"]["sequence"] = 0
        self.check(c, "ANCHOR_REFERENCE_STALE_NO_GO")

    def test_reference_head_hash_mismatch_detected(self):
        c = case()
        c["reference"]["head_hash"] = "f" * 64
        self.check(c, "ANCHOR_HEAD_MISMATCH_NO_GO")

    def test_generation_lower_than_supplied_floor_detected(self):
        c = case(generation=2)
        c["reference"]["generation"] = 1
        self.check(c, "ANCHOR_REFERENCE_GENERATION_ROLLBACK_NO_GO")

    def test_generation_equal_floor_still_denied(self):
        self.check(case(generation=2), "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_generation_greater_than_supplied_floor_not_proof_of_freshness(self):
        c = case(generation=2)
        c["minimum_generation"] = 1
        self.check(c, "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")

    def test_write_failure_and_unknown_fail_closed(self):
        for val in ("SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"):
            with self.subTest(val=val):
                c = case()
                c["simulated_storage"]["write_state"] = val
                self.check(c, "ANCHOR_STORAGE_UNCERTAIN_NO_GO")

    def test_restore_failure_and_unknown_fail_closed(self):
        for val in ("SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"):
            with self.subTest(val=val):
                c = case()
                c["simulated_storage"]["restore_state"] = val
                self.check(c, "ANCHOR_STORAGE_UNCERTAIN_NO_GO")

    def test_reference_read_failure_and_unknown_fail_closed(self):
        for val in ("SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"):
            with self.subTest(val=val):
                c = case()
                c["simulated_storage"]["reference_read_state"] = val
                self.check(c, "ANCHOR_STORAGE_UNCERTAIN_NO_GO")

    def test_clock_anomaly_and_unknown_fail_closed(self):
        for val in ("SYNTHETIC_CLOCK_ANOMALY", "SYNTHETIC_UNKNOWN"):
            with self.subTest(val=val):
                c = case()
                c["simulated_storage"]["clock_state"] = val
                self.check(c, "ANCHOR_CONTINUITY_UNTRUSTED_NO_GO")

    def test_concurrent_writer_detected_fail_closed(self):
        c = case()
        c["simulated_storage"]["concurrent_writer_detected"] = True
        self.check(c, "ANCHOR_CONTINUITY_UNTRUSTED_NO_GO")

    def test_storage_fault_priority_over_consistent_reference(self):
        c = case()
        c["simulated_storage"]["restore_state"] = "SYNTHETIC_FAILED"
        c["reference"]["head_hash"] = "f" * 64
        self.check(c, "ANCHOR_STORAGE_UNCERTAIN_NO_GO")

    def test_continuity_fault_priority_over_reference_hash_mismatch(self):
        c = case()
        c["simulated_storage"]["clock_state"] = "SYNTHETIC_UNKNOWN"
        c["reference"]["head_hash"] = "f" * 64
        self.check(c, "ANCHOR_CONTINUITY_UNTRUSTED_NO_GO")

    def test_history_chain_corruption_is_blocked(self):
        c = case()
        c["history_bundle"]["journal"][0]["event_hash"] = "f" * 64
        r = self.check(c, "ANCHOR_HISTORY_BLOCKED_NO_GO")
        self.assertEqual(r["history_status"], "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_expired_or_rejected_lifecycle_invalid_history_blocks(self):
        c = case()
        c["history_bundle"]["lifecycle"]["events"][0]["event_type"] = "APPROVED"
        self.check(c, "ANCHOR_HISTORY_BLOCKED_NO_GO")

    def test_missing_history_bundle_blocked(self):
        c = case()
        c["history_bundle"] = None
        self.check(c, "ANCHOR_HISTORY_BLOCKED_NO_GO")

    def test_forged_go_from_d523_is_blocked(self):
        c = case()
        with patch(
            "scripts.p0_01_d5_24_reference_fault_gate.audit_synthetic_history_checkpoint",
            return_value={"status": "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO",
                          "runtime_go_no_go": "GO"},
        ):
            self.check(c, "ANCHOR_HISTORY_BLOCKED_NO_GO")

    def test_forged_broker_verified_from_d523_is_blocked(self):
        c = case()
        with patch(
            "scripts.p0_01_d5_24_reference_fault_gate.audit_synthetic_history_checkpoint",
            return_value={"status": "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO",
                          "runtime_go_no_go": "NO_GO",
                          "broker_verified": True},
        ):
            self.check(c, "ANCHOR_HISTORY_BLOCKED_NO_GO")

    def test_invalid_outer_schemas_rejected(self):
        for val in (None, [], {}, "LIVE", True):
            with self.subTest(value=repr(val)):
                self.check(val, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_invalid_origin_and_bool_schema_rejected(self):
        for key, val in (("origin", "LIVE"),
                         ("schema_version", True), ("schema_version", 2)):
            with self.subTest(key=key, val=val):
                c = case()
                c[key] = val
                self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_extra_or_missing_top_field_rejected(self):
        c = case()
        c["execute_order"] = True
        self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")
        c = case()
        del c["reference"]
        self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_reference_unknown_or_missing_field_rejected(self):
        c = case()
        c["reference"]["signature_valid"] = True
        self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")
        c = case()
        del c["reference"]["head_hash"]
        self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_reference_invalid_id_and_hash_rejected(self):
        for name, value in (
            ("reference_id", "REAL_EXTERNAL_ANCHOR"),
            ("record_id", "12345678"),
            ("head_hash", "A" * 64), ("head_hash", "e" * 63),
        ):
            with self.subTest(name=name, value=value):
                c = case()
                c["reference"][name] = value
                self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_reference_boolean_sequence_or_generation_rejected(self):
        for name, value in (
            ("sequence", True), ("sequence", -1),
            ("generation", False), ("generation", 0),
            ("generation", 1000001), ("revocation_tombstone", 1),
        ):
            with self.subTest(name=name, value=value):
                c = case()
                c["reference"][name] = value
                self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_invalid_minimum_generation_rejected(self):
        for val in (None, True, 0, -1, 1000001, "2"):
            with self.subTest(val=val):
                c = case()
                c["minimum_generation"] = val
                self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_storage_missing_extra_and_wrong_types_rejected(self):
        c = case()
        c["simulated_storage"]["is_approved"] = True
        self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")
        c = case()
        del c["simulated_storage"]["restore_state"]
        self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")
        c = case()
        c["simulated_storage"]["concurrent_writer_detected"] = 0
        self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_storage_unrecognized_outcomes_rejected(self):
        for key, val in (
            ("write_state", "GO"), ("restore_state", True),
            ("reference_read_state", "LIVE_CONFIRMED"),
            ("clock_state", "REAL_VERIFIED"),
        ):
            with self.subTest(key=key):
                c = case()
                c["simulated_storage"][key] = val
                self.check(c, "ANCHOR_INPUT_REJECTED_FAIL_CLOSED")

    def test_reference_builder_refuses_invalid_history(self):
        c = case()
        c["history_bundle"]["journal"][0]["event_hash"] = "f" * 64
        self.assertIsNone(build_ref(c["history_bundle"]))

    def test_reference_builder_refuses_invalid_generation(self):
        for val in (True, None, 0, -1, 1000001, "1"):
            with self.subTest(value=repr(val)):
                self.assertIsNone(build_ref(history(), val))

    def test_reference_builder_deterministic_without_side_effects(self):
        b = history()
        before = copy.deepcopy(b)
        r1 = build_ref(b)
        r2 = build_ref(copy.deepcopy(b))
        self.assertEqual(r1, r2)
        self.assertEqual(b, before)
        self.assertTrue(r1["reference_id"].startswith("SYNTHETIC_REFERENCE_"))

    def test_input_unmodified_by_audit(self):
        c = case()
        before = copy.deepcopy(c)
        self.denied(audit(c))
        self.assertEqual(c, before)

    def test_replaying_both_original_inputs_does_not_prove_freshness(self):
        p = lifecycle()
        old = case(copy.deepcopy(p))
        claimed(p)
        newer = case(p, generation=2)
        self.check(old, "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")
        self.check(newer, "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")
        old["minimum_generation"] = 2
        self.check(old, "ANCHOR_REFERENCE_GENERATION_ROLLBACK_NO_GO")


if __name__ == "__main__":
    unittest.main()
