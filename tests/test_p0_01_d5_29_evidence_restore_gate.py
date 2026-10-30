"""D5-29: synthetic evidence provenance / restore comparison regression."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.p0_01_d5_29_evidence_restore_gate import evaluate_d529_evidence_restore

ROOT = Path(__file__).resolve().parents[1]
THREATS = (
    "ATOMIC_COMMIT_TORN", "POWER_LOSS_MID_WRITE", "REFERENCE_ROLLBACK",
    "CO_EDIT_ALL_REFERENCES", "REVOCATION_ERASURE", "CONCURRENT_WRITER",
    "CLOCK_RESTART_OR_ANOMALY", "SIGNATURE_KEY_TAMPER",
    "STORAGE_UNAVAILABLE", "STALE_BACKUP_RESTORE",
)


def load(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def contract():
    return load("p0_01_d5_29_preacceptance_contract.json")


def source():
    return load("p0_01_d5_17_evidence_reconciliation_status.json")


def d528():
    return load("p0_01_d5_28_acceptance_contract.json")


def fixture():
    return load("p0_01_d5_29_synthetic_fixture.json")


def restoration(x):
    return x["restoration"]


def evidence(x):
    return x["acceptance_case"]["g2_records"]


def sync_envelope(x, index, field):
    x["evidence_envelopes"][index][field] = evidence(x)[index][field]


_UNSET = object()


class D529EvidenceRestoreTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertIs(type(result["d528_status"]), str)
        for key in (
            "g2_real_world_resolved", "g6_real_world_resolved",
            "evidence_provenance_authenticated", "account_identity_verified",
            "positions_verified", "pending_orders_verified",
            "ea_state_verified", "trusted_clock_verified",
            "trusted_anchor_verified", "atomic_persistence_verified",
            "revocation_durable_verified", "real_transition_authorized",
            "visual_review_approved", "mt4_launch_approved",
            "mt4_read_only_approved", "host_io_approved",
            "approval_verified", "action_authorized", "ea_execution_authorized",
            "order_authorized", "stop_release_authorized",
            "broker_verified", "production_usable",
            "read_only_ex4_execution_approved",
            "terminal_execution_approved", "orders_generated",
            "forward_trading_enabled",
            "g2_preacceptance_authenticated", "g6_restoration_verified",
            "g6_real_rollback_detected", "g6_real_revocation_persisted",
            "real_identity_reconciled", "restoration_authorized",
        ):
            self.assertIs(result[key], False, key)
        return result

    def check(self, expected, c=_UNSET, s=_UNSET, d=_UNSET, p=_UNSET):
        result = evaluate_d529_evidence_restore(
            contract() if c is _UNSET else c,
            source() if s is _UNSET else s,
            d528() if d is _UNSET else d,
            fixture() if p is _UNSET else p,
        )
        self.denied(result)
        self.assertEqual(result["status"], expected)
        return result

    def test_fully_coherent_synthetic_not_authentication(self):
        r = self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED")
        self.assertEqual(r["d528_status"],
                         "D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO")

    def test_original_user_reports_remain_unverified(self):
        s = source()
        self.assertEqual(s["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(s["positions_status"], "UNKNOWN")
        self.assertEqual(s["pending_orders_status"], "UNKNOWN")
        self.assertEqual(s["ea_running_status"], "UNKNOWN")
        self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", s=s)

    def test_mock_matching_account_not_real_identity(self):
        p = fixture()
        self.assertEqual(p["evidence_envelopes"][0]["account_token"],
                         p["evidence_envelopes"][1]["account_token"])
        r = self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", p=p)
        self.assertIs(r["real_identity_reconciled"], False)

    def test_mock_matching_timestamp_not_real_clock(self):
        p = fixture()
        self.assertEqual(evidence(p)[0]["observed_at_utc"],
                         evidence(p)[1]["observed_at_utc"])
        self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", p=p)

    def test_report_provenance_types_are_distinct_and_untrusted(self):
        p = fixture()
        self.assertEqual([e["source_kind"] for e in p["evidence_envelopes"]],
                         ["PRIOR_USER_VISUAL_REPORT", "LATEST_USER_REPORTED"])
        self.assertTrue(all(e["provenance_attested"] is False
                            for e in p["evidence_envelopes"]))
        self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", p=p)

    def test_mock_source_scope_mismatch_is_not_accepted(self):
        p = fixture()
        evidence(p)[1]["account_token"] = "SYNTHETIC_ACCOUNT_B"
        sync_envelope(p, 1, "account_token")
        r = self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)
        self.assertEqual(r["d528_status"],
                         "D528_G2_SYNTHETIC_SCOPE_MISMATCH_NO_GO")

    def test_mock_source_terminal_mismatch_is_not_accepted(self):
        p = fixture()
        evidence(p)[1]["terminal_token"] = "SYNTHETIC_TERMINAL_B"
        sync_envelope(p, 1, "terminal_token")
        self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)

    def test_mock_source_time_mismatch_is_not_accepted(self):
        p = fixture()
        evidence(p)[1]["observed_at_utc"] = "2026-07-01T21:00:01Z"
        sync_envelope(p, 1, "observed_at_utc")
        self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)

    def test_mock_positions_conflict_not_accepted(self):
        p = fixture()
        evidence(p)[1]["positions"] = "PRESENT"
        self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)

    def test_mock_pending_conflict_not_accepted(self):
        p = fixture()
        evidence(p)[1]["pending_orders"] = "PRESENT"
        self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)

    def test_mock_ea_conflict_not_accepted(self):
        p = fixture()
        evidence(p)[1]["ea_attachment"] = "PRESENT"
        self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)

    def test_mock_autotrading_conflict_not_accepted(self):
        p = fixture()
        evidence(p)[1]["autotrading"] = "PRESENT"
        self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)

    def test_mock_unknown_positions_not_accepted(self):
        p = fixture()
        for rec in evidence(p):
            rec["positions"] = "UNKNOWN"
        self.check("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", p=p)

    def test_missing_evidence_provenance_rejected(self):
        p = fixture()
        del p["evidence_envelopes"][0]["source_kind"]
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_mislabelled_old_as_later_provenance_rejected(self):
        p = fixture()
        p["evidence_envelopes"][0]["source_kind"] = "LATEST_USER_REPORTED"
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_synthetic_provenance_cannot_claim_attestation(self):
        p = fixture()
        p["evidence_envelopes"][0]["provenance_attested"] = True
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_synthetic_account_attestation_rejected(self):
        p = fixture()
        p["evidence_envelopes"][1]["account_attested"] = True
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_evidence_marked_real_verified_rejected(self):
        p = fixture()
        p["evidence_envelopes"][0]["real_world_verified"] = True
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_evidence_marked_real_source_rejected(self):
        p = fixture()
        p["evidence_envelopes"][0]["synthetic_only"] = False
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_evidence_envelope_timestamp_changed_without_record_rejected(self):
        p = fixture()
        p["evidence_envelopes"][0]["observed_at_utc"] = "2026-07-01T21:00:02Z"
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_evidence_envelope_account_changed_without_record_rejected(self):
        p = fixture()
        p["evidence_envelopes"][0]["account_token"] = "SYNTHETIC_ACCOUNT_B"
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_evidence_envelope_recorded_timestamp_changed_rejected(self):
        p = fixture()
        p["evidence_envelopes"][1]["recorded_at_utc"] = "2026-07-01T21:04:00Z"
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_evidence_extra_real_account_number_rejected(self):
        p = fixture()
        p["evidence_envelopes"][0]["real_account_number"] = "SECRET"
        self.check("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", p=p)

    def test_d528_missing_source_field_rejected(self):
        p = fixture()
        del evidence(p)[1]["provenance_class"]
        r = self.check("D529_EVIDENCE_CASE_REJECTED_FAIL_CLOSED", p=p)
        self.assertEqual(r["d528_status"], "D528_CASE_REJECTED_FAIL_CLOSED")

    def test_old_source_report_mutation_rejected(self):
        s = source()
        s["evidence"][0]["positions_or_pending_orders"] = "NO_ORDERS"
        self.check("D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", s=s)

    def test_old_source_observation_date_invented_rejected(self):
        s = source()
        s["evidence"][0]["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", s=s)

    def test_old_source_reconciled_claim_rejected(self):
        s = source()
        s["account_identity_consistency"] = "RECONCILED"
        self.check("D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", s=s)

    def test_old_source_order_absent_claim_rejected(self):
        s = source()
        s["pending_orders_status"] = "ABSENT"
        self.check("D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", s=s)

    def test_old_source_visual_approval_claim_rejected(self):
        s = source()
        s["approvals"]["visual_inspection"] = True
        self.check("D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", s=s)

    def test_restoration_snapshot_equal_still_not_real_evidence(self):
        p = fixture()
        self.assertEqual(restoration(p)["baseline"],
                         restoration(p)["restored"])
        r = self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", p=p)
        self.assertIs(r["g6_restoration_verified"], False)

    def test_g6_all_ten_synthetic_faults_denied(self):
        for threat in THREATS:
            with self.subTest(threat=threat):
                p = fixture()
                restoration(p)["fault_injected"] = threat
                self.check("D529_RESTORE_UNCERTAIN_NO_GO", p=p)

    def test_restore_write_failure_and_unknown_denied(self):
        for state in ("SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                p = fixture()
                restoration(p)["write_state"] = state
                self.check("D529_RESTORE_UNCERTAIN_NO_GO", p=p)

    def test_restore_read_failure_and_unknown_denied(self):
        for state in ("SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                p = fixture()
                restoration(p)["read_state"] = state
                self.check("D529_RESTORE_UNCERTAIN_NO_GO", p=p)

    def test_revocation_index_read_failure_and_unknown_denied(self):
        for state in ("SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                p = fixture()
                restoration(p)["revocation_index_state"] = state
                self.check("D529_RESTORE_UNCERTAIN_NO_GO", p=p)

    def test_restore_clock_anomaly_or_unknown_denied(self):
        for state in ("SYNTHETIC_CLOCK_ANOMALY", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                p = fixture()
                restoration(p)["clock_state"] = state
                self.check("D529_RESTORE_UNCERTAIN_NO_GO", p=p)

    def test_restore_writer_conflict_or_unknown_denied(self):
        for state in ("SYNTHETIC_CONFLICT", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                p = fixture()
                restoration(p)["writer_state"] = state
                self.check("D529_RESTORE_UNCERTAIN_NO_GO", p=p)

    def test_old_stop_latch_missing_denied(self):
        p = fixture()
        restoration(p)["baseline"]["stop_latched"] = False
        self.check("D529_STOP_LATCH_LOSS_NO_GO", p=p)

    def test_restored_stop_latch_missing_denied(self):
        p = fixture()
        restoration(p)["restored"]["stop_latched"] = False
        self.check("D529_STOP_LATCH_LOSS_NO_GO", p=p)

    def test_restore_record_id_mismatch_denied(self):
        p = fixture()
        restoration(p)["restored"]["record_id"] = "SYNTHETIC_RECORD_OTHER"
        self.check("D529_RESTORE_SCOPE_MISMATCH_NO_GO", p=p)

    def test_restore_lower_generation_denied(self):
        p = fixture()
        restoration(p)["baseline"]["generation"] = 2
        self.check("D529_RESTORE_ROLLBACK_NO_GO", p=p)

    def test_restore_lower_sequence_denied(self):
        p = fixture()
        restoration(p)["baseline"]["sequence"] = 4
        self.check("D529_RESTORE_ROLLBACK_NO_GO", p=p)

    def test_revocation_erased_denied(self):
        p = fixture()
        restoration(p)["baseline"]["revocation_tombstone"] = True
        self.check("D529_REVOCATION_ERASURE_NO_GO", p=p)

    def test_revocation_unexpectedly_added_denied(self):
        p = fixture()
        restoration(p)["restored"]["revocation_tombstone"] = True
        self.check("D529_REVOCATION_CHANGE_NO_GO", p=p)

    def test_matching_revocation_tombstones_still_not_authority(self):
        p = fixture()
        for k in ("baseline", "restored"):
            restoration(p)[k]["revocation_tombstone"] = True
        self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", p=p)

    def test_restore_generation_ahead_without_external_pin_denied(self):
        p = fixture()
        restoration(p)["restored"]["generation"] = 2
        self.check("D529_RESTORE_UNPINNED_ADVANCE_NO_GO", p=p)

    def test_restore_sequence_ahead_without_external_pin_denied(self):
        p = fixture()
        restoration(p)["restored"]["sequence"] = 4
        self.check("D529_RESTORE_UNPINNED_ADVANCE_NO_GO", p=p)

    def test_restore_head_hash_mismatch_denied(self):
        p = fixture()
        restoration(p)["restored"]["head_hash"] = "f" * 64
        self.check("D529_RESTORE_HEAD_MISMATCH_NO_GO", p=p)

    def test_simultaneously_replacing_all_untrusted_inputs_not_detectable(self):
        p = fixture()
        for k in ("baseline", "restored"):
            restoration(p)[k]["head_hash"] = "b" * 64
        # There is no independent authenticated anchor: apparent agreement
        # MUST NOT be confused with real recovery, revocation or identity.
        self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", p=p)

    def test_restoration_claimed_stop_release_denied(self):
        p = fixture()
        restoration(p)["simulated_stop_release_claim"] = True
        self.check("D529_STOP_RELEASE_CLAIM_DENIED_NO_GO", p=p)

    def test_restore_failure_precedes_evidence_mismatch(self):
        p = fixture()
        restoration(p)["write_state"] = "SYNTHETIC_FAILED"
        evidence(p)[1]["positions"] = "PRESENT"
        self.check("D529_RESTORE_UNCERTAIN_NO_GO", p=p)

    def test_unknown_restoration_state_rejected(self):
        p = fixture()
        restoration(p)["read_state"] = "REAL_OS_OK"
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_restoration_mode_cannot_be_live(self):
        p = fixture()
        restoration(p)["simulated_only"] = False
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_restoration_integer_bool_rejected(self):
        p = fixture()
        restoration(p)["restored"]["stop_latched"] = 1
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_restoration_bool_sequence_rejected(self):
        p = fixture()
        restoration(p)["restored"]["sequence"] = True
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_restoration_negative_generation_rejected(self):
        p = fixture()
        restoration(p)["baseline"]["generation"] = 0
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_restoration_invalid_hash_rejected(self):
        p = fixture()
        restoration(p)["baseline"]["head_hash"] = "X" * 64
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_restoration_untrusted_record_identifier_rejected(self):
        p = fixture()
        restoration(p)["baseline"]["record_id"] = "REAL_ACCOUNT_1"
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_restoration_extra_permission_flag_rejected(self):
        p = fixture()
        restoration(p)["order_authorized"] = True
        self.check("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_contract_missing_g6_acceptance_rejected(self):
        c = contract()
        c["g6_acceptance_ids"].pop()
        self.check("D529_DESIGN_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_identity_scope_cannot_grant_real_permission(self):
        c = contract()
        c["scope"] = "LIVE_ACCOUNT_GO"
        self.check("D529_DESIGN_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_no_real_verification_cannot_flip(self):
        c = contract()
        c["no_real_verification"] = False
        self.check("D529_DESIGN_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_extra_permission_rejected(self):
        c = contract()
        c["mt4_approved"] = True
        self.check("D529_DESIGN_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_go_claim_rejected(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D529_DESIGN_REJECTED_FAIL_CLOSED", c=c)

    def test_d528_contract_grant_claim_rejected(self):
        d = d528()
        d["approvals"]["mt4_launch"] = True
        self.check("D529_CHILD_CONTRACT_REJECTED_FAIL_CLOSED", d=d)

    def test_d528_child_forged_go_rejected(self):
        p = fixture()
        with patch(
            "scripts.p0_01_d5_29_evidence_restore_gate.audit_d528_acceptance_design",
            return_value={"status": "D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO",
                          "runtime_go_no_go": "GO"},
        ):
            self.check("D529_CHILD_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_d528_child_forged_broker_verified_rejected(self):
        p = fixture()
        from scripts.p0_01_d5_28_acceptance_criteria import (
            audit_d528_acceptance_design as original,
        )
        r = original(d528(), p["acceptance_case"])
        r["broker_verified"] = True
        with patch(
            "scripts.p0_01_d5_29_evidence_restore_gate.audit_d528_acceptance_design",
            return_value=r,
        ):
            self.check("D529_CHILD_CONTRACT_REJECTED_FAIL_CLOSED", p=p)

    def test_invalid_outer_payload_rejected(self):
        for val in (None, {}, [], "LIVE", True):
            with self.subTest(val=repr(val)):
                self.check("D529_INPUT_REJECTED_FAIL_CLOSED", p=val)

    def test_input_extra_order_grant_rejected(self):
        p = fixture()
        p["live_orders_allowed"] = True
        self.check("D529_INPUT_REJECTED_FAIL_CLOSED", p=p)

    def test_invalid_source_ledger_rejected(self):
        for val in (None, {}, [], "UNVERIFIED"):
            with self.subTest(val=repr(val)):
                self.check("D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", s=val)

    def test_invalid_contract_rejected(self):
        for val in (None, {}, [], "OFFLINE"):
            with self.subTest(val=repr(val)):
                self.check("D529_DESIGN_REJECTED_FAIL_CLOSED", c=val)

    def test_input_not_mutated(self):
        c, s, d, p = contract(), source(), d528(), fixture()
        before = copy.deepcopy((c, s, d, p))
        self.denied(evaluate_d529_evidence_restore(c, s, d, p))
        self.assertEqual((c, s, d, p), before)

    def test_repeat_calls_never_remember_permission(self):
        c, s, d = contract(), source(), d528()
        self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED",
                   c=c, s=s, d=d)
        p = fixture()
        restoration(p)["simulated_stop_release_claim"] = True
        self.check("D529_STOP_RELEASE_CLAIM_DENIED_NO_GO", c=c, s=s, d=d, p=p)
        self.check("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED",
                   c=c, s=s, d=d)

    def test_status_ledger_never_promotes_gates(self):
        data = load("p0_01_d5_29_status.json")
        self.assertEqual(data["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.assertEqual(data["phase_1"], "BLOCKED")
        self.assertEqual(data["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(data["verified_values"])
        self.assertIs(data["broker_verified"], False)
        self.assertIs(data["terminal_execution_approved"], False)
        self.assertIs(data["forward_trading_enabled"], False)
        self.assertIs(data["g2_real_world_resolved"], False)
        self.assertIs(data["g6_real_world_resolved"], False)


if __name__ == "__main__":
    unittest.main()
