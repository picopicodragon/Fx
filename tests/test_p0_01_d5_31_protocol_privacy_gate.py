"""P0-01 D5-31 strict G2 export metadata and G6 crash trace tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_31_protocol_privacy_gate import (
    _APPROVED_NONE, _STAGES, _THREATS, review_d531_protocol,
)

_ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def read(name):
    with (_ROOT / "specs" / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def plan():
    return read("p0_01_d5_31_protocol_privacy_contract.json")


def ledger():
    return read("p0_01_d5_17_evidence_reconciliation_status.json")


def gaps():
    return read("p0_01_d5_25_gap_verification_matrix.json")


def fixture():
    return read("p0_01_d5_31_synthetic_fixture.json")


class D531ProtocolPrivacyTests(TestCase):
    def check(self, expected, p=_UNSET, old=_UNSET, g=_UNSET,
              public=_UNSET, recovery=_UNSET):
        f = fixture()
        result = review_d531_protocol(
            plan() if p is _UNSET else p,
            ledger() if old is _UNSET else old,
            gaps() if g is _UNSET else g,
            f["public_metadata"] if public is _UNSET else public,
            f["synthetic_recovery"] if recovery is _UNSET else recovery,
        )
        self.assertEqual(result["status"], expected)
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertEqual(result["account_identity_consistency"], "NOT_RECONCILED")
        for key in ("current_positions", "current_pending_orders",
                    "current_ea_state"):
            self.assertEqual(result[key], "UNKNOWN")
        for key in _APPROVED_NONE:
            self.assertIs(result[key], False, key)
        self.assertEqual(set(result), set(_APPROVED_NONE) | {
            "status", "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return result

    def test_all_stages_complete_is_still_synthetic_no_go(self):
        self.check("D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED")

    def test_empty_stage_history_is_incomplete_no_go(self):
        r = fixture()["synthetic_recovery"]
        r["completed_stages"] = []
        self.check("D531_G6_PARTIAL_COMMIT_STOP_HELD_NO_GO", recovery=r)

    def test_each_partial_prefix_stays_stopped(self):
        for i in range(1, len(_STAGES)):
            with self.subTest(i=i):
                r = fixture()["synthetic_recovery"]
                r["completed_stages"] = list(_STAGES[:i])
                self.check("D531_G6_PARTIAL_COMMIT_STOP_HELD_NO_GO", recovery=r)

    def test_out_of_order_stages_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["completed_stages"][2], r["completed_stages"][3] = (
            r["completed_stages"][3], r["completed_stages"][2])
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_duplicate_stage_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["completed_stages"][2] = r["completed_stages"][1]
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_missing_initial_stop_latch_stage_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["completed_stages"] = list(_STAGES[1:])
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_unknown_stage_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["completed_stages"][-1] = "UNSAFE_AUTO_RESUME"
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_extra_stage_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["completed_stages"].append("RELEASE_STOP")
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_all_ten_faults_stay_no_go(self):
        for fault in _THREATS:
            with self.subTest(fault=fault):
                r = fixture()["synthetic_recovery"]
                r["fault"] = fault
                self.check("D531_G6_UNTRUSTED_FAULT_NO_GO", recovery=r)

    def test_anchor_mismatch_or_unknown_blocks(self):
        for status in ("SYNTHETIC_MISMATCH", "SYNTHETIC_UNKNOWN"):
            with self.subTest(status=status):
                r = fixture()["synthetic_recovery"]
                r["anchor_claim"] = status
                self.check("D531_G6_UNTRUSTED_FAULT_NO_GO", recovery=r)

    def test_storage_failure_or_unknown_blocks(self):
        for status in ("SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN"):
            with self.subTest(status=status):
                r = fixture()["synthetic_recovery"]
                r["storage_claim"] = status
                self.check("D531_G6_UNTRUSTED_FAULT_NO_GO", recovery=r)

    def test_writer_conflict_or_unknown_blocks(self):
        for status in ("SYNTHETIC_CONFLICT", "SYNTHETIC_UNKNOWN"):
            with self.subTest(status=status):
                r = fixture()["synthetic_recovery"]
                r["writer_claim"] = status
                self.check("D531_G6_UNTRUSTED_FAULT_NO_GO", recovery=r)

    def test_clock_anomaly_or_unknown_blocks(self):
        for status in ("SYNTHETIC_CLOCK_ANOMALY", "SYNTHETIC_UNKNOWN"):
            with self.subTest(status=status):
                r = fixture()["synthetic_recovery"]
                r["clock_claim"] = status
                self.check("D531_G6_UNTRUSTED_FAULT_NO_GO", recovery=r)

    def test_revocation_index_missing_or_unknown_blocks(self):
        for status in ("SYNTHETIC_TOMBSTONE_MISSING", "SYNTHETIC_UNKNOWN"):
            with self.subTest(status=status):
                r = fixture()["synthetic_recovery"]
                r["revocation_claim"] = status
                self.check("D531_G6_UNTRUSTED_FAULT_NO_GO", recovery=r)

    def test_stop_release_claim_blocks_even_complete_stage(self):
        r = fixture()["synthetic_recovery"]
        r["simulated_stop_release_claim"] = True
        self.check("D531_UNAUTHORIZED_STOP_RELEASE_NO_GO", recovery=r)

    def test_before_stop_latch_false_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["stop_latched"] = False
        self.check("D531_G6_STOP_LATCH_LOST_NO_GO", recovery=r)

    def test_after_stop_latch_false_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["after"]["stop_latched"] = False
        self.check("D531_G6_STOP_LATCH_LOST_NO_GO", recovery=r)

    def test_record_identity_mismatch_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["after"]["record_id"] = "SYNTHETIC_RECORD_OTHER"
        self.check("D531_G6_RECORD_SCOPE_MISMATCH_NO_GO", recovery=r)

    def test_generation_rollback_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["generation"] = 2
        self.check("D531_G6_ROLLBACK_NO_GO", recovery=r)

    def test_sequence_rollback_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["sequence"] = 4
        self.check("D531_G6_ROLLBACK_NO_GO", recovery=r)

    def test_revocation_erasure_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["after"]["revocation_tombstone"] = False
        self.check("D531_G6_REVOCATION_ERASURE_NO_GO", recovery=r)

    def test_revocation_new_without_evidence_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["revocation_tombstone"] = False
        self.check("D531_G6_REVOCATION_CHANGE_NO_GO", recovery=r)

    def test_generation_advance_without_external_proof_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["after"]["generation"] = 2
        self.check("D531_G6_UNPINNED_ADVANCE_NO_GO", recovery=r)

    def test_sequence_advance_without_external_proof_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["after"]["sequence"] = 4
        self.check("D531_G6_UNPINNED_ADVANCE_NO_GO", recovery=r)

    def test_hash_mismatch_blocks(self):
        r = fixture()["synthetic_recovery"]
        r["after"]["head_hash"] = "b" * 64
        self.check("D531_G6_HASH_MISMATCH_NO_GO", recovery=r)

    def test_jointly_forged_matching_hash_cannot_prove_authenticity(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["head_hash"] = "b" * 64
        r["after"]["head_hash"] = "b" * 64
        result = self.check(
            "D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED", recovery=r)
        self.assertIs(result["independent_trust_anchor_verified"], False)

    def test_tombstone_true_on_both_sides_still_no_real_proof(self):
        r = fixture()["synthetic_recovery"]
        self.assertIs(r["before"]["revocation_tombstone"], True)
        self.assertIs(r["after"]["revocation_tombstone"], True)
        self.check("D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED", recovery=r)

    def test_invalid_record_identifier_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["record_id"] = "12345678"
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_negative_or_bool_generation_rejected(self):
        for value in (0, -1, True):
            with self.subTest(value=value):
                r = fixture()["synthetic_recovery"]
                r["before"]["generation"] = value
                self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_negative_or_bool_sequence_rejected(self):
        for value in (-1, False):
            with self.subTest(value=value):
                r = fixture()["synthetic_recovery"]
                r["after"]["sequence"] = value
                self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_non_hex_hash_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["head_hash"] = "X" * 64
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_bool_stop_latch_as_integer_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["before"]["stop_latched"] = 1
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_bool_revocation_as_integer_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["after"]["revocation_tombstone"] = 0
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_unknown_os_success_claim_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["storage_claim"] = "OS_REAL_DURABLE"
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_real_operation_flag_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["simulated_only"] = False
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_extra_real_order_permission_in_recovery_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["order_authorized"] = True
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_missing_recovery_field_rejected(self):
        r = fixture()["synthetic_recovery"]
        del r["completed_stages"]
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_recovery_boolean_schema_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["schema_version"] = True
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_recovery_stop_release_as_integer_rejected(self):
        r = fixture()["synthetic_recovery"]
        r["simulated_stop_release_claim"] = 1
        self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED", recovery=r)

    def test_public_metadata_allowlist_only(self):
        self.check("D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED")

    def test_all_eight_public_check_ids_are_only_synthetic(self):
        for i in range(1, 9):
            with self.subTest(i=i):
                data = fixture()["public_metadata"]
                data["check_id"] = f"D530-G2-{i:02d}"
                self.check("D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED",
                           public=data)

    def test_private_account_number_field_rejected(self):
        data = fixture()["public_metadata"]
        data["account_number"] = "SYNTHETIC_SECRET_EXAMPLE"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_raw_mt4_log_field_rejected(self):
        data = fixture()["public_metadata"]
        data["raw_mt4_log"] = "SYNTHETIC_SECRET_EXAMPLE"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_screenshot_field_rejected(self):
        data = fixture()["public_metadata"]
        data["screenshot_bytes"] = "SYNTHETIC_BYTES"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_api_key_field_rejected(self):
        data = fixture()["public_metadata"]
        data["api_key"] = "SYNTHETIC_SECRET_EXAMPLE"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_actual_order_details_field_rejected(self):
        data = fixture()["public_metadata"]
        data["order_details"] = {"quantity": 1}
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_real_observation_time_field_rejected(self):
        data = fixture()["public_metadata"]
        data["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_free_text_note_field_rejected(self):
        data = fixture()["public_metadata"]
        data["notes"] = "Even synthetic notes can hide credentials"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_nested_extra_field_rejected(self):
        data = fixture()["public_metadata"]
        data["metadata"] = {"account_number": "SYNTHETIC_SECRET"}
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_misspelled_check_id_key_rejected(self):
        data = fixture()["public_metadata"]
        data["check_id "] = data.pop("check_id")
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_unknown_check_id_rejected(self):
        data = fixture()["public_metadata"]
        data["check_id"] = "D530-G2-09"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_public_state_must_be_unperformed(self):
        data = fixture()["public_metadata"]
        data["design_state"] = "COMPLETED"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_public_cannot_claim_real_evidence(self):
        data = fixture()["public_metadata"]
        data["simulation_only"] = False
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_public_boolean_schema_rejected(self):
        data = fixture()["public_metadata"]
        data["schema_version"] = True
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_public_real_origin_rejected(self):
        data = fixture()["public_metadata"]
        data["origin"] = "BROKER_LIVE"
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_public_integer_id_rejected(self):
        data = fixture()["public_metadata"]
        data["check_id"] = 1
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_public_missing_or_extra_field_rejected(self):
        data = fixture()["public_metadata"]
        del data["design_state"]
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)
        data = fixture()["public_metadata"]
        data["stop_release_approved"] = False
        self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED", public=data)

    def test_design_public_fields_cannot_be_expanded(self):
        p = plan()
        p["g2"]["public_fields"].append("notes")
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_approve_real_collection(self):
        p = plan()
        p["g2"]["real_collection_performed"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_claim_private_storage(self):
        p = plan()
        p["g2"]["private_storage_implemented"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_approve_raw_evidence(self):
        p = plan()
        p["g2"]["raw_evidence_approved"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_change_commit_order(self):
        p = plan()
        p["g6"]["commit_stages"].reverse()
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_remove_failure_scenarios(self):
        p = plan()
        p["g6"]["faults"].pop()
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_claim_trusted_anchor(self):
        p = plan()
        p["g6"]["independent_anchor_available"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_claim_real_atomic_storage(self):
        p = plan()
        p["g6"]["atomic_storage_implemented"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_claim_recovery_verified(self):
        p = plan()
        p["g6"]["recovery_verified"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_claim_real_signatures(self):
        p = plan()
        p["g6"]["signatures_implemented"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_claim_cross_store_atomicity(self):
        p = plan()
        p["g6"]["cross_store_atomicity_verified"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_approve_host_io(self):
        p = plan()
        p["g6"]["host_io_approved"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_cannot_approve_stop_release(self):
        p = plan()
        p["g6"]["stop_release_approved"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_approval_flags_must_be_false_bool(self):
        for key in plan()["approvals"]:
            with self.subTest(key=key):
                p = plan()
                p["approvals"][key] = 0
                self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)
                p = plan()
                p["approvals"][key] = True
                self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_go_rejected(self):
        p = plan()
        p["runtime_go_no_go"] = "GO"
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_verified_values_rejected(self):
        p = plan()
        p["verified_values"] = {}
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_design_extra_permission_field_rejected(self):
        p = plan()
        p["authorize_orders"] = True
        self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_old_evidence_cannot_be_forged_as_current(self):
        old = ledger()
        old["positions_status"] = "ABSENT"
        self.check("D531_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_evidence_cannot_add_invented_timestamp(self):
        old = ledger()
        old["evidence"][0]["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D531_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_evidence_cannot_mark_broker_confirmed(self):
        old = ledger()
        old["evidence"][0]["broker_confirmed"] = True
        self.check("D531_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_g2_gap_cannot_be_marked_resolved(self):
        g = gaps()
        next(x for x in g["gaps"] if x["id"] == "G2")[
            "real_world_verified"] = True
        self.check("D531_GAP_BASELINE_REJECTED_FAIL_CLOSED", g=g)

    def test_g6_gap_cannot_release_blocker(self):
        g = gaps()
        next(x for x in g["gaps"] if x["id"] == "G6")[
            "release_blocker"] = False
        self.check("D531_GAP_BASELINE_REJECTED_FAIL_CLOSED", g=g)

    def test_all_other_gaps_stay_unresolved(self):
        g = gaps()
        next(x for x in g["gaps"] if x["id"] == "G9")[
            "implementation_status"] = "RESOLVED"
        self.check("D531_GAP_BASELINE_REJECTED_FAIL_CLOSED", g=g)

    def test_invalid_plan_inputs_fail_closed(self):
        for data in (None, [], {}, "LIVE"):
            with self.subTest(data=repr(data)):
                self.check("D531_DESIGN_REJECTED_FAIL_CLOSED", p=data)

    def test_invalid_public_inputs_fail_closed(self):
        for data in (None, [], {}, "LIVE"):
            with self.subTest(data=repr(data)):
                self.check("D531_G2_PUBLIC_METADATA_REJECTED_FAIL_CLOSED",
                           public=data)

    def test_invalid_recovery_inputs_fail_closed(self):
        for data in (None, [], {}, "LIVE"):
            with self.subTest(data=repr(data)):
                self.check("D531_G6_PROTOCOL_INPUT_REJECTED_FAIL_CLOSED",
                           recovery=data)

    def test_pure_validation_does_not_read_files(self):
        p, old, g = plan(), ledger(), gaps()
        f = fixture()
        with patch("builtins.open", side_effect=AssertionError("I/O banned")):
            result = review_d531_protocol(
                p, old, g, f["public_metadata"], f["synthetic_recovery"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_pure_validation_does_not_mutate_inputs(self):
        p, old, g = plan(), ledger(), gaps()
        f = fixture()
        original = copy.deepcopy((p, old, g, f))
        review_d531_protocol(
            p, old, g, f["public_metadata"], f["synthetic_recovery"])
        self.assertEqual(original, (p, old, g, f))

    def test_repeat_calls_do_not_inherit_approval(self):
        self.check("D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED")
        r = fixture()["synthetic_recovery"]
        r["simulated_stop_release_claim"] = True
        self.check("D531_UNAUTHORIZED_STOP_RELEASE_NO_GO", recovery=r)
        self.check("D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED")

    def test_new_status_keeps_every_real_gap_blocked(self):
        status = read("p0_01_d5_31_status.json")
        self.assertEqual(status["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.assertEqual(status["phase_1"], "BLOCKED")
        self.assertEqual(status["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(status["verified_values"])
        for flag in ("g2_real_world_resolved", "g6_real_world_resolved",
                     "broker_verified", "production_usable", "host_io_approved",
                     "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(status[flag], False)


if __name__ == "__main__":
    main()
