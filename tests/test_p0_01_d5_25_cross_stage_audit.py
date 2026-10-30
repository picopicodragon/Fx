"""D5-25: cross-stage denial audit, spoof resistance and G1-G9 gap ledger."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.p0_01_d5_23_history_checkpoint import build_synthetic_history_chain
from scripts.p0_01_d5_24_reference_fault_gate import build_synthetic_reference_fixture
from scripts.p0_01_d5_25_cross_stage_audit import (
    audit_synthetic_cross_stage_no_go as audit,
)


def lifecycle(action="EA_EXECUTION", cause="NONE"):
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "record": {
            "record_id": "SYNTH_APPROVAL_TEST",
            "action": action,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A",
            "stop_cause": cause,
            "issued_at_utc": "2026-07-01T21:00:00Z",
            "expires_at_utc": "2026-07-01T21:30:00Z",
        },
        "events": [{
            "sequence": 0, "event_type": "PROPOSED",
            "record_id": "SYNTH_APPROVAL_TEST",
            "occurred_at_utc": "2026-07-01T21:00:00Z",
        }],
        "request": {
            "action": action, "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A", "stop_cause": cause,
        },
        "as_of_utc": "2026-07-01T21:10:00Z",
    }


def claim(p):
    p["events"].append({
        "sequence": len(p["events"]), "event_type": "APPROVAL_CLAIMED",
        "record_id": p["record"]["record_id"],
        "occurred_at_utc": "2026-07-01T21:05:00Z",
    })


def revoke(p):
    p["events"].append({
        "sequence": len(p["events"]), "event_type": "REVOKED",
        "record_id": p["record"]["record_id"],
        "occurred_at_utc": "2026-07-01T21:06:00Z",
    })


def integrated():
    snapshot = {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "trading_day_start_ny_date": "2026-07-01",
        "daily_stop_latched": False,
        "last_status": "SYNTHETIC_MONITORING_ONLY", "sequence": 10,
    }
    def observation(eid, kind):
        return {
            "evidence_id": eid, "source_kind": kind,
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
                observation("EVID_A", "USER_REPORT"),
                observation("EVID_B", "VISUAL_OBSERVATION"),
            ],
        },
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
        "expected_day": "2026-07-01", "minimum_sequence": 10,
    }


def fixture(p=None):
    p = lifecycle() if p is None else p
    journal = build_synthetic_history_chain(p)
    if journal is None:
        raise ValueError("invalid synthetic lifecycle fixture")
    hb = {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "lifecycle": p,
        "journal": journal,
        "checkpoint": {
            "record_id": p["record"]["record_id"],
            "sequence": journal[-1]["sequence"],
            "head_hash": journal[-1]["event_hash"],
        },
        "integrated_fixture": integrated(),
    }
    reference = build_synthetic_reference_fixture(hb)
    if reference is None:
        raise ValueError("invalid synthetic reference fixture")
    return {
        "origin": "SYNTHETIC_ONLY",
        "schema_version": 1,
        "anchor_fixture": {
            "origin": "SYNTHETIC_ONLY",
            "schema_version": 1,
            "history_bundle": hb,
            "reference": reference,
            "minimum_generation": 1,
            "simulated_storage": {
                "write_state": "SYNTHETIC_CONFIRMED",
                "restore_state": "SYNTHETIC_CONFIRMED",
                "reference_read_state": "SYNTHETIC_CONFIRMED",
                "clock_state": "SYNTHETIC_CLOCK_STABLE",
                "concurrent_writer_detected": False,
            },
        },
    }


def hb(data):
    return data["anchor_fixture"]["history_bundle"]


def g(data):
    return hb(data)["integrated_fixture"]


def fresh_history(data):
    """Rebuild all untrusted chain data after a synthetic edit."""
    p = hb(data)["lifecycle"]
    j = build_synthetic_history_chain(p)
    hb(data)["journal"] = j
    hb(data)["checkpoint"] = {
        "record_id": p["record"]["record_id"],
        "sequence": j[-1]["sequence"], "head_hash": j[-1]["event_hash"],
    }
    ref = data["anchor_fixture"]["reference"]
    ref["record_id"] = p["record"]["record_id"]
    ref["sequence"] = j[-1]["sequence"]
    ref["head_hash"] = j[-1]["event_hash"]
    ref["revocation_tombstone"] = any(
        x["event_type"] == "REVOKED" for x in p["events"])


class D525CrossStageAuditTests(unittest.TestCase):
    def denied(self, r):
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertIs(r["safety_hold_latched"], True)
        self.assertIsNone(r["verified_values"])
        self.assertEqual(r["effective_approved_actions"], [])
        self.assertEqual(set(r), {
            "status", "integrated_status", "authority_status",
            "lifecycle_status", "history_status", "anchor_status",
            "account_scope_verified", "history_authentic",
            "trust_anchor_verified", "actual_replay_protection",
            "approval_verified", "action_authorized",
            "ea_execution_authorized", "order_authorized",
            "stop_release_authorized", "effective_approved_actions",
            "safety_hold_latched", "phase_1", "runtime_go_no_go",
            "verified_values", "broker_verified", "production_usable",
            "orders_generated", "read_only_ex4_execution_approved",
            "terminal_execution_approved", "forward_trading_enabled",
        })
        for key in (
            "account_scope_verified", "history_authentic",
            "trust_anchor_verified", "actual_replay_protection",
            "approval_verified", "action_authorized",
            "ea_execution_authorized", "order_authorized",
            "stop_release_authorized", "broker_verified",
            "production_usable", "orders_generated",
            "read_only_ex4_execution_approved",
            "terminal_execution_approved", "forward_trading_enabled",
        ):
            self.assertIs(r[key], False)
        for k in ("integrated_status", "authority_status", "lifecycle_status",
                  "history_status", "anchor_status"):
            self.assertIs(type(r[k]), str)
        return r

    def check(self, payload, expected):
        r = self.denied(audit(payload))
        self.assertEqual(r["status"], expected)
        return r

    def test_proposal_all_stages_coherent_but_never_authorized(self):
        r = self.check(fixture(), "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["authority_status"],
                         "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")

    def test_claim_all_stages_coherent_but_never_authorized(self):
        p = lifecycle()
        claim(p)
        r = self.check(fixture(p), "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["authority_status"],
                         "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO")

    def test_revoked_claim_does_not_inherit_old_approval(self):
        p = lifecycle()
        claim(p)
        revoke(p)
        r = self.check(fixture(p), "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["lifecycle_status"], "LIFECYCLE_REVOKED_NO_GO")
        self.assertEqual(r["authority_status"],
                         "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")

    def test_expired_claim_does_not_inherit_old_approval(self):
        p = lifecycle()
        claim(p)
        p["as_of_utc"] = "2026-07-01T21:30:00Z"
        r = self.check(fixture(p), "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["lifecycle_status"], "LIFECYCLE_EXPIRED_NO_GO")
        self.assertEqual(r["authority_status"],
                         "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")

    def test_stop_release_approval_claim_remains_no_go(self):
        p = lifecycle("STOP_RELEASE", "DD5")
        claim(p)
        r = self.check(fixture(p), "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["authority_status"], "STOP_RELEASE_CLAIM_DENIED_NO_GO")

    def test_daily_stop_priority_even_with_clean_anchor(self):
        data = fixture()
        g(data)["daily_fixture"]["previous_daily_stop"] = True
        g(data)["snapshots"][-1]["daily_stop_latched"] = True
        g(data)["snapshots"][-1]["last_status"] = "DAILY_STOP"
        r = self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")
        self.assertEqual(r["integrated_status"], "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")

    def test_stop_disagreement_blocks_all_stages(self):
        data = fixture()
        g(data)["daily_fixture"]["previous_daily_stop"] = True
        r = self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED")

    def test_conflicting_positions_block(self):
        data = fixture()
        g(data)["evidence"]["records"][1]["positions"] = "PRESENT"
        r = self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")
        self.assertEqual(r["integrated_status"], "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")

    def test_unknown_pending_orders_block(self):
        data = fixture()
        for item in g(data)["evidence"]["records"]:
            item["pending_orders"] = "UNKNOWN"
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_stale_synthetic_evidence_time_block(self):
        data = fixture()
        for item in g(data)["evidence"]["records"]:
            item["observed_at_utc"] = "2026-06-30T21:00:00Z"
        r = self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_EVIDENCE_TIME_MISMATCH_NO_GO")

    def test_stale_stop_snapshot_block(self):
        data = fixture()
        g(data)["expected_day"] = "2026-07-02"
        g(data)["daily_fixture"]["utc_timestamp"] = "2026-07-02T21:00:00+00:00"
        g(data)["daily_fixture"]["previous_day_label"] = "2026-07-02"
        r = self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_STALE_STOP_RECORD_FAIL_CLOSED")

    def test_cross_source_account_mismatch_detected_when_internal_gates_clean(self):
        data = fixture()
        p = hb(data)["lifecycle"]
        p["record"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        p["request"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        fresh_history(data)
        r = self.check(data, "CROSS_STAGE_SCOPE_MISMATCH_NO_GO")
        self.assertEqual(r["anchor_status"], "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")

    def test_mismatched_synthetic_account_label_is_not_real_identity_proof(self):
        data = fixture()
        g(data)["evidence"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        self.check(data, "CROSS_STAGE_SCOPE_MISMATCH_NO_GO")

    def test_d517_history_scope_not_assumed_reconciled(self):
        data = fixture()
        g(data)["evidence_mode"] = "D517_LEDGER"
        g(data)["evidence"] = {"origin": "SYNTHETIC_ONLY"}
        r = self.check(data, "CROSS_STAGE_SCOPE_UNVERIFIED_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")

    def test_missing_evidence_scope_is_unverified(self):
        data = fixture()
        del g(data)["evidence"]["account_scope"]
        self.check(data, "CROSS_STAGE_SCOPE_UNVERIFIED_NO_GO")

    def test_corrupted_history_chain_blocks(self):
        data = fixture()
        hb(data)["journal"][0]["event_hash"] = "f" * 64
        r = self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")
        self.assertEqual(r["history_status"], "HISTORY_CHAIN_MISMATCH_NO_GO")

    def test_checkpoint_sequence_rollback_blocks(self):
        data = fixture()
        hb(data)["checkpoint"]["sequence"] = 2
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_revocation_erasure_detected_with_original_reference(self):
        p = lifecycle()
        claim(p)
        revoke(p)
        data = fixture(p)
        hb(data)["lifecycle"]["events"].pop()
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_anchor_generation_rollback_blocks(self):
        data = fixture()
        data["anchor_fixture"]["minimum_generation"] = 2
        r = self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")
        self.assertEqual(r["anchor_status"],
                         "ANCHOR_REFERENCE_GENERATION_ROLLBACK_NO_GO")

    def test_anchor_tombstone_mismatch_blocks(self):
        data = fixture()
        data["anchor_fixture"]["reference"]["revocation_tombstone"] = True
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_anchor_hash_mismatch_blocks(self):
        data = fixture()
        data["anchor_fixture"]["reference"]["head_hash"] = "f" * 64
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_rollback_with_older_proposal_under_newer_ref_blocks(self):
        old = fixture()
        p = lifecycle()
        claim(p)
        new = fixture(p)
        old["anchor_fixture"]["reference"] = copy.deepcopy(
            new["anchor_fixture"]["reference"])
        self.check(old, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_write_failure_blocks(self):
        data = fixture()
        data["anchor_fixture"]["simulated_storage"]["write_state"] = "SYNTHETIC_FAILED"
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_restore_failure_blocks(self):
        data = fixture()
        data["anchor_fixture"]["simulated_storage"]["restore_state"] = "SYNTHETIC_FAILED"
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_reference_read_unknown_blocks(self):
        data = fixture()
        data["anchor_fixture"]["simulated_storage"]["reference_read_state"] = "SYNTHETIC_UNKNOWN"
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_clock_fault_blocks(self):
        data = fixture()
        data["anchor_fixture"]["simulated_storage"]["clock_state"] = "SYNTHETIC_CLOCK_ANOMALY"
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_concurrent_writer_blocks(self):
        data = fixture()
        data["anchor_fixture"]["simulated_storage"]["concurrent_writer_detected"] = True
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_invalid_lifecycle_event_is_blocked(self):
        data = fixture()
        hb(data)["lifecycle"]["events"][0]["event_type"] = "APPROVED"
        self.check(data, "CROSS_STAGE_BLOCKED_NO_GO")

    def test_cross_stage_fake_history_status_disagreement(self):
        data = fixture()
        from scripts.p0_01_d5_23_history_checkpoint import (
            audit_synthetic_history_checkpoint as original,
        )
        faked = original(hb(data))
        faked["lifecycle_status"] = "LIFECYCLE_EXPIRED_NO_GO"
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_history_checkpoint",
            return_value=faked,
        ):
            self.check(data, "CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO")

    def test_cross_stage_fake_authority_status_disagreement(self):
        data = fixture()
        from scripts.p0_01_d5_21_authority_audit import (
            audit_offline_authority_separation as original,
        )
        claim_ = {
            "origin": "SYNTHETIC_ONLY", "schema_version": 1,
            "requested_action": "EA_EXECUTION",
            "claimed_human_approval": False,
            "claimed_safety_review_passed": False,
            "claimed_stop_release": False, "approval_reference": None,
        }
        faked = original(g(data), claim_)
        faked["integrated_status"] = "INTEGRATED_EVIDENCE_BLOCKED_NO_GO"
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_offline_authority_separation",
            return_value=faked,
        ):
            self.check(data, "CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO")

    def test_cross_stage_fake_anchor_history_disagreement(self):
        data = fixture()
        from scripts.p0_01_d5_24_reference_fault_gate import (
            audit_synthetic_reference_and_failures as original,
        )
        faked = original(data["anchor_fixture"])
        faked["history_status"] = "HISTORY_CHAIN_MISMATCH_NO_GO"
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_reference_and_failures",
            return_value=faked,
        ):
            self.check(data, "CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO")

    def test_fake_integration_go_rejected(self):
        data = fixture()
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.evaluate_offline_integrated_no_go",
            return_value={"status": "GO", "runtime_go_no_go": "GO"},
        ):
            self.check(data, "CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")

    def test_fake_authority_grant_rejected(self):
        data = fixture()
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_offline_authority_separation",
            return_value={"status": "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO",
                          "action_authorized": True},
        ):
            self.check(data, "CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")

    def test_fake_lifecycle_verified_rejected(self):
        data = fixture()
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_approval_lifecycle",
            return_value={"status": "LIFECYCLE_PROPOSED_NO_GO",
                          "approval_verified": True},
        ):
            self.check(data, "CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")

    def test_fake_history_stop_release_rejected(self):
        data = fixture()
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_history_checkpoint",
            return_value={"status": "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO",
                          "stop_release_authorized": True},
        ):
            self.check(data, "CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")

    def test_fake_anchor_authenticity_rejected(self):
        data = fixture()
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_reference_and_failures",
            return_value={"status": "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO",
                          "reference_authentic": True},
        ):
            self.check(data, "CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")

    def test_future_unknown_d5_status_rejected(self):
        data = fixture()
        from scripts.p0_01_d5_24_reference_fault_gate import (
            audit_synthetic_reference_and_failures as original,
        )
        unexpected = original(data["anchor_fixture"])
        unexpected["status"] = "ANCHOR_APPROVED"
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_reference_and_failures",
            return_value=unexpected,
        ):
            self.check(data, "CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")

    def test_bool_replacing_false_child_field_rejected(self):
        data = fixture()
        from scripts.p0_01_d5_24_reference_fault_gate import (
            audit_synthetic_reference_and_failures as original,
        )
        unexpected = original(data["anchor_fixture"])
        unexpected["broker_verified"] = 0
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_reference_and_failures",
            return_value=unexpected,
        ):
            self.check(data, "CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")

    def test_child_exception_denies_without_runtime_side_effect(self):
        data = fixture()
        with patch(
            "scripts.p0_01_d5_25_cross_stage_audit.audit_synthetic_history_checkpoint",
            side_effect=RuntimeError("simulated fault"),
        ):
            self.check(data, "CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")

    def test_missing_outer_fields_rejected(self):
        for key in ("origin", "schema_version", "anchor_fixture"):
            with self.subTest(key=key):
                data = fixture()
                del data[key]
                self.check(data, "CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")

    def test_extra_permission_field_rejected(self):
        data = fixture()
        data["live_trading_approved"] = True
        self.check(data, "CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")

    def test_invalid_outer_origin_and_schema_rejected(self):
        for field, value in (
            ("origin", "BROKER_LIVE"),
            ("schema_version", True),
            ("schema_version", 2),
        ):
            with self.subTest(field=field):
                data = fixture()
                data[field] = value
                self.check(data, "CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")

    def test_invalid_outer_payload_types_rejected(self):
        for value in (None, "LIVE", [], {}, True):
            with self.subTest(value=repr(value)):
                self.check(value, "CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")

    def test_missing_nested_integrated_fixture_rejected(self):
        data = fixture()
        hb(data)["integrated_fixture"] = None
        self.check(data, "CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")

    def test_missing_nested_anchor_fixture_rejected(self):
        data = fixture()
        data["anchor_fixture"] = None
        self.check(data, "CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")

    def test_no_input_mutation(self):
        data = fixture()
        old = copy.deepcopy(data)
        self.denied(audit(data))
        self.assertEqual(data, old)

    def test_two_calls_do_not_retain_stale_permission(self):
        first = fixture()
        claim(hb(first)["lifecycle"])
        fresh_history(first)
        second = fixture()
        self.denied(audit(first))
        r = self.check(second, "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["authority_status"],
                         "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")

    def test_g1_g9_audit_ledger_all_unresolved(self):
        file = (Path(__file__).resolve().parents[1] /
                "specs/p0_01_d5_25_gap_verification_matrix.json")
        with file.open(encoding="utf-8") as stream:
            data = json.load(stream)
        self.assertEqual([item["id"] for item in data["gaps"]],
                         [f"G{i}" for i in range(1, 10)])
        for item in data["gaps"]:
            self.assertIs(item["release_blocker"], True)
            self.assertIs(item["real_world_verified"], False)
            self.assertEqual(item["implementation_status"], "UNRESOLVED")
            self.assertTrue(item["offline_synthetic_coverage"])
            self.assertTrue(item["external_or_real_evidence_required"])
        self.assertEqual(data["runtime_go_no_go"], "NO_GO")
        self.assertEqual(data["phase_1"], "BLOCKED")
        self.assertIsNone(data["verified_values"])

    def test_new_status_file_and_matrix_never_authorize(self):
        root = Path(__file__).resolve().parents[1] / "specs"
        for name in (
            "p0_01_d5_25_gap_verification_matrix.json",
            "p0_01_d5_25_audit_status.json",
        ):
            with self.subTest(name=name):
                with (root / name).open(encoding="utf-8") as stream:
                    obj = json.load(stream)
                self.assertIs(obj["broker_verified"], False)
                self.assertIs(obj["terminal_execution_approved"], False)
                self.assertIs(obj["forward_trading_enabled"], False)
                self.assertEqual(obj["phase_1"], "BLOCKED")
                self.assertEqual(obj["runtime_go_no_go"], "NO_GO")
                self.assertIsNone(obj["verified_values"])

    def test_same_synthetic_fixture_not_real_account_verification(self):
        r = self.check(fixture(), "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.assertIs(r["account_scope_verified"], False)
        self.assertIs(r["trust_anchor_verified"], False)
        self.assertIs(r["history_authentic"], False)


if __name__ == "__main__":
    unittest.main()
