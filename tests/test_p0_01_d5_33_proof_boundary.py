"""D5-33: hypothetical independent proof and G2 privacy boundary tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_33_proof_boundary import (
    _FALSE, _WITNESSES, review_d533_independent_proofs,
)

_ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def read(name):
    with (_ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def contract():
    return read("p0_01_d5_33_proof_boundary_contract.json")


def d532():
    return read("p0_01_d5_32_crash_matrix_contract.json")


def d531():
    return read("p0_01_d5_31_protocol_privacy_contract.json")


def old():
    return read("p0_01_d5_17_evidence_reconciliation_status.json")


def gaps():
    return read("p0_01_d5_25_gap_verification_matrix.json")


def prior():
    return read("p0_01_d5_32_synthetic_fixture.json")


def case():
    return read("p0_01_d5_33_synthetic_fixture.json")


class D533ProofBoundaryTests(TestCase):
    def check(self, expected, c=_UNSET, p32=_UNSET, p31=_UNSET,
              ev=_UNSET, gs=_UNSET, matrix=_UNSET, sc=_UNSET):
        result = review_d533_independent_proofs(
            contract() if c is _UNSET else c,
            d532() if p32 is _UNSET else p32,
            d531() if p31 is _UNSET else p31,
            old() if ev is _UNSET else ev,
            gaps() if gs is _UNSET else gs,
            prior() if matrix is _UNSET else matrix,
            case() if sc is _UNSET else sc,
        )
        self.assertEqual(result["status"], expected)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        for k in _FALSE:
            self.assertIs(result[k], False, k)
        self.assertEqual(result["account_identity_consistency"],
                         "NOT_RECONCILED")
        for key in ("current_positions", "current_pending_orders",
                    "current_ea_state"):
            self.assertEqual(result[key], "UNKNOWN")
        self.assertEqual(set(result), set(_FALSE) | {
            "status", "d532_status", "effective_approved_actions",
            "safety_hold_latched", "account_identity_consistency",
            "current_positions", "current_pending_orders",
            "current_ea_state", "phase_1", "runtime_go_no_go",
            "verified_values",
        })
        return result

    def test_complete_mock_witness_format_never_authorized(self):
        r = self.check("D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["d532_status"],
                         "D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED")

    def test_five_witnesses_only_have_synthetic_labels(self):
        ps = case()["synthetic_proofs"]
        self.assertEqual([p["witness"] for p in ps], list(_WITNESSES))
        self.assertTrue(all(
            p["source_boundary"] == "SYNTHETIC_SEPARATE_LABEL_ONLY"
            and p["real_signature_verified"] is False
            and p["real_independence_verified"] is False
            for p in ps))
        self.check("D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED")

    def test_d533_proofs_never_verify_current_broker_state(self):
        r = self.check("D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED")
        for name in ("account_identity_verified", "positions_verified",
                     "pending_orders_verified", "ea_state_verified",
                     "g6_real_anchor_verified", "g6_real_signature_verified"):
            self.assertIs(r[name], False)

    def test_private_export_request_is_denied(self):
        sc = case()
        sc["private_envelope"]["private_export_requested"] = True
        self.check("D533_G2_PRIVATE_EXPORT_DENIED_NO_GO", sc=sc)

    def test_private_raw_payload_present_is_denied(self):
        sc = case()
        sc["private_envelope"]["raw_payload_present"] = True
        self.check("D533_G2_PRIVATE_EVIDENCE_UNTRUSTED_NO_GO", sc=sc)

    def test_private_fake_source_authentication_denied(self):
        sc = case()
        sc["private_envelope"]["provenance_authenticated"] = True
        self.check("D533_G2_PRIVATE_EVIDENCE_UNTRUSTED_NO_GO", sc=sc)

    def test_private_fake_account_verification_denied(self):
        sc = case()
        sc["private_envelope"]["account_identity_verified"] = True
        self.check("D533_G2_PRIVATE_EVIDENCE_UNTRUSTED_NO_GO", sc=sc)

    def test_private_fake_observation_time_verification_denied(self):
        sc = case()
        sc["private_envelope"]["observed_at_verified"] = True
        self.check("D533_G2_PRIVATE_EVIDENCE_UNTRUSTED_NO_GO", sc=sc)

    def test_private_extra_nested_secret_field_rejected(self):
        sc = case()
        sc["private_envelope"]["raw_mt4_log"] = {
            "password": "SYNTHETIC_SECRET"
        }
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_private_account_number_instead_of_mock_token_rejected(self):
        sc = case()
        sc["private_envelope"]["account_token"] = "1234567890"
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_private_extra_real_screenshot_field_rejected(self):
        sc = case()
        sc["private_envelope"]["screenshot"] = "SYNTHETIC_BYTES"
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_private_prior_report_ids_cannot_be_reassigned(self):
        sc = case()
        sc["private_envelope"]["source_ids"].reverse()
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_private_provenance_bool_integer_rejected(self):
        sc = case()
        sc["private_envelope"]["provenance_authenticated"] = 0
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_private_real_mode_rejected(self):
        sc = case()
        sc["private_envelope"]["simulated_only"] = False
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_g2_public_json_must_match_predecessor(self):
        sc = case()
        sc["public_json"] = sc["public_json"].replace(
            "D530-G2-01", "D530-G2-02")
        self.check("D533_G2_PUBLIC_PRIVATE_MISMATCH_NO_GO", sc=sc)

    def test_public_json_extra_private_field_rejected(self):
        sc = case()
        data = json.loads(sc["public_json"])
        data["account_number"] = "SYNTHETIC_SECRET"
        sc["public_json"] = json.dumps(
            data, sort_keys=True, separators=(",", ":"))
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_public_json_extra_nested_metadata_rejected(self):
        sc = case()
        data = json.loads(sc["public_json"])
        data["extra"] = {"notes": ["SYNTHETIC_SECRET"]}
        sc["public_json"] = json.dumps(
            data, sort_keys=True, separators=(",", ":"))
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_public_json_duplicate_key_rejected(self):
        sc = case()
        sc["public_json"] = sc["public_json"].replace(
            '"schema_version":1',
            '"schema_version":1,"schema_version":1')
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_public_json_unicode_escaped_literal_rejected(self):
        sc = case()
        sc["public_json"] = sc["public_json"].replace(
            "SYNTHETIC_ONLY", "SYNTHETIC_\\u004fNLY")
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_public_json_raw_confusable_key_rejected(self):
        sc = case()
        sc["public_json"] = sc["public_json"].replace(
            "check_id", "check_іd")
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_public_case_extra_field_rejected(self):
        sc = case()
        sc["private_data"] = "SYNTHETIC_SECRET"
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_public_json_in_predecessor_cannot_be_changed_without_case(self):
        matrix = prior()
        matrix["public_json"] = matrix["public_json"].replace(
            "D530-G2-01", "D530-G2-02")
        self.check("D533_G2_PUBLIC_PRIVATE_MISMATCH_NO_GO", matrix=matrix)

    def test_missing_proof_rejected(self):
        sc = case()
        sc["synthetic_proofs"].pop()
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_extra_duplicate_proof_rejected(self):
        sc = case()
        sc["synthetic_proofs"].append(
            copy.deepcopy(sc["synthetic_proofs"][0]))
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_duplicate_witness_names_rejected(self):
        sc = case()
        sc["synthetic_proofs"][1]["witness"] = "LOCAL_JOURNAL"
        self.check("D533_G6_PROOF_SCOPE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_witness_order_change_rejected(self):
        sc = case()
        sc["synthetic_proofs"].reverse()
        self.check("D533_G6_PROOF_SCOPE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_forged_real_independence_claim_denied(self):
        sc = case()
        sc["synthetic_proofs"][1]["real_independence_verified"] = True
        self.check("D533_G6_FALSE_AUTHENTICATION_CLAIM_NO_GO", sc=sc)

    def test_forged_real_signature_claim_denied(self):
        sc = case()
        sc["synthetic_proofs"][3]["real_signature_verified"] = True
        self.check("D533_G6_FALSE_AUTHENTICATION_CLAIM_NO_GO", sc=sc)

    def test_shared_input_boundary_cannot_pretend_independence(self):
        sc = case()
        sc["synthetic_proofs"][1]["source_boundary"] = "SYNTHETIC_SHARED_INPUT"
        self.check("D533_G6_SHARED_TRUST_BOUNDARY_NO_GO", sc=sc)

    def test_claimed_proof_boundary_real_hsm_label_rejected(self):
        sc = case()
        sc["synthetic_proofs"][1]["source_boundary"] = "REAL_HSM"
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_mock_witness_staleness_is_not_real_time(self):
        sc = case()
        sc["simulated_reference_tick"] = 104
        r = self.check(
            "D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", sc=sc)
        self.assertIs(r["g6_proof_freshness_real"], False)

    def test_mock_witness_future_tick_denied(self):
        sc = case()
        sc["synthetic_proofs"][1]["observed_tick"] = 101
        self.check("D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", sc=sc)

    def test_mock_witness_at_max_synthetic_age_never_authorized(self):
        sc = case()
        for witness in sc["synthetic_proofs"]:
            witness["observed_tick"] = 95
        self.check(
            "D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED",
            sc=sc)

    def test_mock_reference_tick_bool_rejected(self):
        sc = case()
        sc["simulated_reference_tick"] = True
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_mock_observed_tick_bool_rejected(self):
        sc = case()
        sc["synthetic_proofs"][0]["observed_tick"] = True
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_mock_observed_tick_negative_rejected(self):
        sc = case()
        sc["synthetic_proofs"][0]["observed_tick"] = -1
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_generation_changed_detects_witness_conflict(self):
        sc = case()
        sc["synthetic_proofs"][1]["generation"] = 2
        self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

    def test_sequence_changed_detects_witness_conflict(self):
        sc = case()
        sc["synthetic_proofs"][2]["sequence"] = 2
        self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

    def test_hash_changed_detects_witness_conflict(self):
        sc = case()
        sc["synthetic_proofs"][3]["head_hash"] = "f" * 64
        self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

    def test_revocation_tombstone_missing_denied(self):
        sc = case()
        sc["synthetic_proofs"][2]["revocation_tombstone"] = False
        self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

    def test_stop_latch_loss_denied(self):
        sc = case()
        sc["synthetic_proofs"][1]["stop_latched"] = False
        self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

    def test_record_scope_changed_denied(self):
        sc = case()
        sc["synthetic_proofs"][0]["record_id"] = "SYNTHETIC_RECORD_OTHER"
        self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

    def test_all_witness_hashes_jointly_rewritten_is_not_real_proof(self):
        sc = case()
        source = prior()
        for p in sc["synthetic_proofs"]:
            p["head_hash"] = "f" * 64
        for row in source["matrix"]:
            row["recovery"]["before"]["head_hash"] = "f" * 64
            row["recovery"]["after"]["head_hash"] = "f" * 64
        result = self.check(
            "D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED",
            matrix=source, sc=sc)
        self.assertIs(result["g6_witness_independence_authenticated"], False)

    def test_stop_release_claim_denied(self):
        sc = case()
        sc["stop_release_claim"] = True
        self.check("D533_OPERATION_CLAIM_DENIED_NO_GO", sc=sc)

    def test_real_operation_claim_denied(self):
        sc = case()
        sc["real_operation_claim"] = True
        self.check("D533_OPERATION_CLAIM_DENIED_NO_GO", sc=sc)

    def test_g6_previous_crash_cutpoint_not_complete(self):
        source = prior()
        source["matrix"][-1]["recovery"]["completed_stages"].pop()
        self.check("D533_PREVIOUS_STAGE_DENIED_NO_GO", matrix=source)

    def test_g6_previous_stale_backup_denied(self):
        source = prior()
        source["matrix"][3]["recovery"]["fault"] = "STALE_BACKUP_RESTORE"
        self.check("D533_PREVIOUS_STAGE_DENIED_NO_GO", matrix=source)

    def test_g6_previous_anchor_mismatch_denied(self):
        source = prior()
        source["matrix"][4]["recovery"]["anchor_claim"] = "SYNTHETIC_MISMATCH"
        self.check("D533_PREVIOUS_STAGE_DENIED_NO_GO", matrix=source)

    def test_g6_previous_stage_claim_go_denied(self):
        p = d532()
        p["runtime_go_no_go"] = "GO"
        self.check("D533_PREVIOUS_STAGE_DENIED_NO_GO", p32=p)

    def test_forged_child_result_with_runtime_go_rejected(self):
        with patch(
            "scripts.p0_01_d5_33_proof_boundary.review_d532_crash_matrix",
            return_value={"status":
                "D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED",
                "runtime_go_no_go": "GO"},
        ):
            self.check("D533_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_forged_child_claim_broker_verified_rejected(self):
        from scripts.p0_01_d5_32_crash_matrix_privacy import (
            review_d532_crash_matrix as original,
        )
        source = prior()
        child = original(
            d532(), d531(), old(), gaps(), source["public_json"],
            source["matrix"])
        child["broker_verified"] = True
        with patch(
            "scripts.p0_01_d5_33_proof_boundary.review_d532_crash_matrix",
            return_value=child,
        ):
            self.check("D533_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_fake_child_status_go_still_no_authority(self):
        from scripts.p0_01_d5_32_crash_matrix_privacy import (
            review_d532_crash_matrix as original,
        )
        source = prior()
        child = original(d532(), d531(), old(), gaps(),
                         source["public_json"], source["matrix"])
        child["status"] = "GO"
        with patch(
            "scripts.p0_01_d5_33_proof_boundary.review_d532_crash_matrix",
            return_value=child,
        ):
            self.check("D533_PREVIOUS_STAGE_DENIED_NO_GO")

    def test_original_report_identity_remains_unknown(self):
        ev = old()
        self.assertEqual(ev["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(ev["positions_status"], "UNKNOWN")
        self.assertEqual(ev["pending_orders_status"], "UNKNOWN")
        self.check(
            "D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED",
            ev=ev)

    def test_original_report_forged_current_positions_rejected(self):
        ev = old()
        ev["positions_status"] = "ABSENT"
        self.check("D533_PREDECESSOR_BASELINE_REJECTED_FAIL_CLOSED", ev=ev)

    def test_original_report_forged_observation_time_rejected(self):
        ev = old()
        ev["evidence"][0]["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D533_PREDECESSOR_BASELINE_REJECTED_FAIL_CLOSED", ev=ev)

    def test_g6_resolved_claim_in_gap_matrix_rejected(self):
        gs = gaps()
        next(x for x in gs["gaps"] if x["id"] == "G6")[
            "real_world_verified"] = True
        self.check("D533_PREDECESSOR_BASELINE_REJECTED_FAIL_CLOSED", gs=gs)

    def test_contract_missing_witness_rejected(self):
        c = contract()
        c["g6"]["required_witnesses"].pop()
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_increased_mock_age_limit_rejected(self):
        c = contract()
        c["g6"]["max_synthetic_tick_age"] = 99
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_future_source_independence_claim_rejected(self):
        c = contract()
        c["g6"]["independent_boundary_implemented"] = True
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_real_signature_claim_rejected(self):
        c = contract()
        c["g6"]["real_signature_verified"] = True
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_real_clock_claim_rejected(self):
        c = contract()
        c["g6"]["real_clock_verified"] = True
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_real_recovery_claim_rejected(self):
        c = contract()
        c["g6"]["real_recovery_verified"] = True
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_private_export_approved_rejected(self):
        c = contract()
        c["g2"]["private_export_approved"] = True
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_git_hook_claim_rejected(self):
        c = contract()
        c["g2"]["git_hook_implemented"] = True
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_extra_public_field_rejected(self):
        c = contract()
        c["g2"]["public_fields"].append("notes")
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_runtime_go_rejected(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_verified_values_rejected(self):
        c = contract()
        c["verified_values"] = {}
        self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_real_approval_for_each_action_rejected(self):
        for key in contract()["approvals"]:
            with self.subTest(key=key):
                c = contract()
                c["approvals"][key] = True
                self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_case_extra_authorized_operation_rejected(self):
        sc = case()
        sc["order_authorized"] = True
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_case_invalid_top_level_types_rejected(self):
        for value in (None, [], {}, "LIVE", True):
            with self.subTest(value=repr(value)):
                self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=value)
                self.check("D533_CONTRACT_REJECTED_FAIL_CLOSED", c=value)

    def test_case_bool_schema_rejected(self):
        sc = case()
        sc["schema_version"] = True
        self.check("D533_CASE_REJECTED_FAIL_CLOSED", sc=sc)

    def test_proof_bool_generation_rejected(self):
        sc = case()
        sc["synthetic_proofs"][0]["generation"] = True
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_proof_invalid_digest_rejected(self):
        sc = case()
        sc["synthetic_proofs"][0]["head_hash"] = "not-a-hash"
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_proof_extra_private_key_rejected(self):
        sc = case()
        sc["synthetic_proofs"][0]["signing_private_key"] = "SYNTHETIC_SECRET"
        self.check("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", sc=sc)

    def test_no_actual_file_io_during_check(self):
        c, a, b, ev, gs, src, sc = (
            contract(), d532(), d531(), old(), gaps(), prior(), case())
        with patch("builtins.open", side_effect=AssertionError("No I/O")):
            r = review_d533_independent_proofs(c, a, b, ev, gs, src, sc)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_input_objects_not_mutated(self):
        args = (contract(), d532(), d531(), old(), gaps(), prior(), case())
        before = copy.deepcopy(args)
        review_d533_independent_proofs(*args)
        self.assertEqual(args, before)

    def test_repeat_calls_cannot_persist_permission(self):
        self.check("D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED")
        sc = case()
        sc["real_operation_claim"] = True
        self.check("D533_OPERATION_CLAIM_DENIED_NO_GO", sc=sc)
        self.check("D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED")

    def test_new_status_all_gates_unresolved(self):
        s = read("p0_01_d5_33_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "terminal_execution_approved",
                  "host_io_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)


# Additional parameterized checks registered as separate unittest methods.
def _test_0_stale(self):
    sc = case()
    sc["simulated_reference_tick"] = 106
    sc["synthetic_proofs"][0]["observed_tick"] = 98
    self.check("D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", sc=sc)

D533ProofBoundaryTests.test_0_stale = _test_0_stale

def _test_0_scope(self):
    sc = case()
    sc["synthetic_proofs"][0]["record_id"] = "SYNTHETIC_RECORD_OTHER"
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_0_scope = _test_0_scope

def _test_0_revocation(self):
    sc = case()
    sc["synthetic_proofs"][0]["revocation_tombstone"] = False
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_0_revocation = _test_0_revocation

def _test_0_boundary(self):
    sc = case()
    sc["synthetic_proofs"][0]["source_boundary"] = "SYNTHETIC_SHARED_INPUT"
    self.check("D533_G6_SHARED_TRUST_BOUNDARY_NO_GO", sc=sc)

D533ProofBoundaryTests.test_0_boundary = _test_0_boundary

def _test_1_stale(self):
    sc = case()
    sc["simulated_reference_tick"] = 106
    sc["synthetic_proofs"][1]["observed_tick"] = 98
    self.check("D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", sc=sc)

D533ProofBoundaryTests.test_1_stale = _test_1_stale

def _test_1_scope(self):
    sc = case()
    sc["synthetic_proofs"][1]["record_id"] = "SYNTHETIC_RECORD_OTHER"
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_1_scope = _test_1_scope

def _test_1_revocation(self):
    sc = case()
    sc["synthetic_proofs"][1]["revocation_tombstone"] = False
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_1_revocation = _test_1_revocation

def _test_1_boundary(self):
    sc = case()
    sc["synthetic_proofs"][1]["source_boundary"] = "SYNTHETIC_SHARED_INPUT"
    self.check("D533_G6_SHARED_TRUST_BOUNDARY_NO_GO", sc=sc)

D533ProofBoundaryTests.test_1_boundary = _test_1_boundary

def _test_2_stale(self):
    sc = case()
    sc["simulated_reference_tick"] = 106
    sc["synthetic_proofs"][2]["observed_tick"] = 98
    self.check("D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", sc=sc)

D533ProofBoundaryTests.test_2_stale = _test_2_stale

def _test_2_scope(self):
    sc = case()
    sc["synthetic_proofs"][2]["record_id"] = "SYNTHETIC_RECORD_OTHER"
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_2_scope = _test_2_scope

def _test_2_revocation(self):
    sc = case()
    sc["synthetic_proofs"][2]["revocation_tombstone"] = False
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_2_revocation = _test_2_revocation

def _test_2_boundary(self):
    sc = case()
    sc["synthetic_proofs"][2]["source_boundary"] = "SYNTHETIC_SHARED_INPUT"
    self.check("D533_G6_SHARED_TRUST_BOUNDARY_NO_GO", sc=sc)

D533ProofBoundaryTests.test_2_boundary = _test_2_boundary

def _test_3_stale(self):
    sc = case()
    sc["simulated_reference_tick"] = 106
    sc["synthetic_proofs"][3]["observed_tick"] = 98
    self.check("D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", sc=sc)

D533ProofBoundaryTests.test_3_stale = _test_3_stale

def _test_3_scope(self):
    sc = case()
    sc["synthetic_proofs"][3]["record_id"] = "SYNTHETIC_RECORD_OTHER"
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_3_scope = _test_3_scope

def _test_3_revocation(self):
    sc = case()
    sc["synthetic_proofs"][3]["revocation_tombstone"] = False
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_3_revocation = _test_3_revocation

def _test_3_boundary(self):
    sc = case()
    sc["synthetic_proofs"][3]["source_boundary"] = "SYNTHETIC_SHARED_INPUT"
    self.check("D533_G6_SHARED_TRUST_BOUNDARY_NO_GO", sc=sc)

D533ProofBoundaryTests.test_3_boundary = _test_3_boundary

def _test_4_stale(self):
    sc = case()
    sc["simulated_reference_tick"] = 106
    sc["synthetic_proofs"][4]["observed_tick"] = 98
    self.check("D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", sc=sc)

D533ProofBoundaryTests.test_4_stale = _test_4_stale

def _test_4_scope(self):
    sc = case()
    sc["synthetic_proofs"][4]["record_id"] = "SYNTHETIC_RECORD_OTHER"
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_4_scope = _test_4_scope

def _test_4_revocation(self):
    sc = case()
    sc["synthetic_proofs"][4]["revocation_tombstone"] = False
    self.check("D533_G6_WITNESS_CONTRADICTION_NO_GO", sc=sc)

D533ProofBoundaryTests.test_4_revocation = _test_4_revocation

def _test_4_boundary(self):
    sc = case()
    sc["synthetic_proofs"][4]["source_boundary"] = "SYNTHETIC_SHARED_INPUT"
    self.check("D533_G6_SHARED_TRUST_BOUNDARY_NO_GO", sc=sc)

D533ProofBoundaryTests.test_4_boundary = _test_4_boundary


if __name__ == "__main__":
    main()
