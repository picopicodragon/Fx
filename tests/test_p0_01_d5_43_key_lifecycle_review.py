"""P0-01 D5-43 key custody/rotation/revocation design-only regression."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_43_key_lifecycle_review import (
    _FALSE, _CONTROLS, _TRANSITIONS, _THREATS,
    _CONTRACT_FALSE, _RECORD_FALSE, _PARENT_KEYS,
    review_d543_key_lifecycle,
)
from scripts.p0_01_d5_42_selection_policy_review import review_d542_selection_rules
from scripts.p0_01_d5_36_readiness_gate import _BUNDLE_FIELDS

ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as source:
        return json.load(source)


def contract(): return read("p0_01_d5_43_key_lifecycle_contract.json")
def matrix(): return read("p0_01_d5_43_synthetic_key_lifecycle.json")


def predecessor():
    p = {
        "d542_contract": read("p0_01_d5_42_selection_rules.json"),
        "d542_scenario": read("p0_01_d5_42_synthetic_selection_review.json"),
    }
    p41 = {
        "d541_contract": read("p0_01_d5_41_anchor_selection_contract.json"),
        "d541_matrix": read("p0_01_d5_41_candidate_evidence_matrix.json"),
    }
    p40 = {
        "d540_contract": read("p0_01_d5_40_trust_boundary_contract.json"),
        "d540_matrix": read("p0_01_d5_40_candidate_threat_matrix.json"),
    }
    p39 = {
        "d539_contract": read("p0_01_d5_39_egress_contract.json"),
        "d539_manifest": read("p0_01_d5_39_synthetic_manifest.json"),
        "d539_public_json": read("p0_01_d5_32_synthetic_fixture.json")["public_json"],
    }
    p38 = {
        "d538_design": read("p0_01_d5_38_private_vault_contract.json"),
        "d538_threat_matrix": read("p0_01_d5_38_threat_matrix.json"),
        "d537_workplan": read("p0_01_d5_37_workplan_contract.json"),
        "d537_tracking": read("p0_01_d5_37_synthetic_tracking.json"),
        "d536_contract": read("p0_01_d5_36_acceptance_contract.json"),
        "d536_readiness": read("p0_01_d5_36_readiness_register.json"),
        "d536_actions": read("p0_01_d5_36_synthetic_authorization.json"),
    }
    names = (
        "p0_01_d5_35_handoff_contract.json",
        "p0_01_d5_34_lineage_contract.json",
        "p0_01_d5_33_proof_boundary_contract.json",
        "p0_01_d5_32_crash_matrix_contract.json",
        "p0_01_d5_31_protocol_privacy_contract.json",
        "p0_01_d5_17_evidence_reconciliation_status.json",
        "p0_01_d5_25_gap_verification_matrix.json",
        "p0_01_d5_32_synthetic_fixture.json",
        "p0_01_d5_33_synthetic_fixture.json",
        "p0_01_d5_34_synthetic_fixture.json",
        "p0_01_d5_35_synthetic_fixture.json",
    )
    p38["d536_predecessors"] = dict(
        zip(_BUNDLE_FIELDS, (read(x) for x in names))
    )
    p39["d539_predecessors"] = p38
    p40["d540_predecessor_bundle"] = p39
    p41["d541_predecessor"] = p40
    p["d542_predecessor"] = p41
    return p


class D543KeyLifecycleTests(TestCase):
    def check(self, expected, c=_MISSING, m=_MISSING, p=_MISSING):
        out = review_d543_key_lifecycle(
            contract() if c is _MISSING else c,
            matrix() if m is _MISSING else m,
            predecessor() if p is _MISSING else p,
        )
        self.assertEqual(out["status"], expected)
        self.assertEqual(out["runtime_go_no_go"], "NO_GO")
        self.assertEqual(out["phase_1"], "BLOCKED")
        self.assertIsNone(out["verified_values"])
        self.assertIs(out["safety_hold_latched"], True)
        self.assertEqual(out["effective_approved_actions"], [])
        self.assertEqual(out["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(out["custody_requirements_documented"], 12)
        self.assertEqual(out["lifecycle_transitions_documented"], 10)
        self.assertEqual(out["threat_cases_documented"], 10)
        for k in (
            "real_keys_generated", "real_issuers_authenticated",
            "real_revocations_attested", "real_trust_anchors_implemented",
            "real_candidates_selected", "real_evidence_items_collected",
            "real_work_packages_executed", "real_acceptance_criteria_completed",
        ):
            self.assertEqual(out[k], 0, k)
        for k in ("current_positions", "current_pending_orders", "current_ea_state"):
            self.assertEqual(out[k], "UNKNOWN")
        for k in _FALSE:
            self.assertIs(out[k], False, k)
        self.assertEqual(set(out), set(_FALSE) | {
            "status", "d542_status", "custody_requirements_documented",
            "lifecycle_transitions_documented", "threat_cases_documented",
            "real_keys_generated", "real_issuers_authenticated",
            "real_revocations_attested", "real_trust_anchors_implemented",
            "real_candidates_selected", "real_evidence_items_collected",
            "real_work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return out

    def test_baseline_all_unimplemented(self):
        result = self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")
        self.assertEqual(result["d542_status"],
                         "D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION")

    def test_key_custody_twelve_requirements(self):
        self.assertEqual([r["control_id"] for r in matrix()["required_controls"]],
                         [name for name, _ in _CONTROLS])
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_required_all_ten_lifecycle_transitions(self):
        self.assertEqual([x["transition_id"] for x in matrix()["lifecycle_cases"]],
                         [x[0] for x in _TRANSITIONS])
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_required_all_ten_threats(self):
        self.assertEqual([x["threat_id"] for x in matrix()["threat_cases"]],
                         [x[0] for x in _THREATS])
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_issuer_epoch_is_only_design_label(self):
        chain = matrix()["issuer_chain"]
        self.assertEqual((chain["current_epoch"], chain["next_epoch"]), (1, 2))
        self.assertIsNone(chain["actual_issuer_id"])
        self.assertIsNone(chain["actual_signature"])
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_real_private_key_not_in_input(self):
        data = json.dumps(matrix(), ensure_ascii=False)
        for private_fragment in (
            "-----BEGIN PRIVATE KEY-----", "REAL_API_TOKEN",
            "actual_broker_account_number", "REAL_SECRET_SIGNING_KEY",
        ):
            self.assertNotIn(private_fragment, data)
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_revoked_issuer_never_active_by_design(self):
        self.assertEqual(
            contract()["lifecycle_rule"],
            "REVOKED_KEYS_AND_ISSUERS_NEVER_REENTER_ACTIVE_STATE",
        )
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_revocation_tombstone_not_persisted(self):
        self.assertEqual(matrix()["issuer_chain"]["revocation_tombstone"],
                         "DESIGN_ONLY_NOT_PERSISTED")
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_g8_approval_and_g2_boundary_required(self):
        self.assertEqual(contract()["external_gate_dependencies"], ["G8"])
        self.assertEqual(contract()["privacy_dependencies"], ["G2-06", "G2-07"])
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_design_and_operational_permissions_separate(self):
        self.assertEqual(contract()["approval_rule"],
                         "DESIGN_REVIEW_NOT_RUNTIME_OR_STOP_RELEASE_AUTHORITY")
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_atomic_rotation_never_partially_accepted(self):
        self.assertEqual(contract()["atomicity_rule"],
                         "NO_PARTIAL_ROTATION_OR_MIXED_ISSUER_ANCHOR_COMMIT")
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")

    def test_safe_synthetic_rotation_no_real_authority(self):
        m = matrix()
        m["lifecycle_cases"][2]["simulated_event"] = "SIMULATED_SAFE_PATH"
        self.check("D543_SYNTHETIC_SAFE_PATH_NOT_REAL_ATTESTATION", m=m)

    def test_unsafe_synthetic_replay_denied(self):
        m = matrix()
        m["lifecycle_cases"][7]["simulated_event"] = "SIMULATED_UNSAFE_PATH"
        self.check("D543_SYNTHETIC_REPLAY_REVOKE_OR_HANDOFF_DENIED", m=m)

    def test_revocation_loss_overrides_simulated_safe_path(self):
        m = matrix()
        m["lifecycle_cases"][2]["simulated_event"] = "SIMULATED_SAFE_PATH"
        m["threat_cases"][4]["simulated_outcome"] = "SIMULATED_ATTACK"
        self.check("D543_SYNTHETIC_REPLAY_REVOKE_OR_HANDOFF_DENIED", m=m)

    def test_simulated_all_safe_cannot_generate_a_key(self):
        m = matrix()
        for row in m["lifecycle_cases"]:
            row["simulated_event"] = "SIMULATED_SAFE_PATH"
        for row in m["threat_cases"]:
            row["simulated_outcome"] = "SIMULATED_MITIGATED"
        self.check("D543_SYNTHETIC_SAFE_PATH_NOT_REAL_ATTESTATION", m=m)

    def test_contract_wrong_scope_denied(self):
        c = contract()
        c["scope"] = "ACTUAL_KEY_CUSTODY"
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_wrong_target_denied(self):
        c = contract()
        c["target_criterion"] = "G6-02"
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_remove_independent_anchor_dependency_denied(self):
        c = contract()
        c["upstream_criteria"] = ["G6-01"]
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_remove_g8_denied(self):
        c = contract()
        c["external_gate_dependencies"] = []
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_make_revocation_reversible_denied(self):
        c = contract()
        c["lifecycle_rule"] = "REVOKED_ISSUER_CAN_REACTIVATE"
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_allow_partial_rotation_denied(self):
        c = contract()
        c["atomicity_rule"] = "PARTIAL_COMMIT_ALLOWED"
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_allow_expired_approval_denied(self):
        c = contract()
        c["approval_rule"] = "REUSE_OLD_APPROVAL"
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_allow_secret_export_denied(self):
        c = contract()
        c["private_key_rule"] = "EXPORT_SECRET_TO_GIT"
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_runtime_go_denied(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_schema_bool_denied(self):
        c = contract()
        c["schema_version"] = True
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_missing_control_denied(self):
        c = contract()
        c["required_controls"].pop()
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_contract_duplicate_transition_denied(self):
        c = contract()
        c["transition_ids"][1] = c["transition_ids"][0]
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_matrix_missing_control_denied(self):
        m = matrix()
        m["required_controls"].pop()
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_reordered_transition_denied(self):
        m = matrix()
        m["lifecycle_cases"].reverse()
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_duplicate_threat_denied(self):
        m = matrix()
        m["threat_cases"][1] = copy.deepcopy(m["threat_cases"][0])
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_add_actual_key_denied(self):
        m = matrix()
        m["actual_secret_key"] = "SYNTHETIC_SENTINEL"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_issuer_alias_rebind_denied(self):
        m = matrix()
        m["issuer_chain"]["current_alias"] = "SYNTHETIC_ISSUER_BETA"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_epoch_rollback_denied(self):
        m = matrix()
        m["issuer_chain"]["next_epoch"] = 0
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_boolean_as_epoch_denied(self):
        m = matrix()
        m["issuer_chain"]["next_epoch"] = True
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_forged_signature_denied(self):
        m = matrix()
        m["issuer_chain"]["actual_signature"] = "SYNTHETIC_SENTINEL"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_tombstone_forgery_denied(self):
        m = matrix()
        m["issuer_chain"]["revocation_tombstone"] = "PERSISTED"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_forged_time_denied(self):
        m = matrix()
        m["real_observation_utc"] = "2026-10-30T00:00:00Z"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_current_account_unknown_denied(self):
        m = matrix()
        m["current_positions"] = "ZERO"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_missing_gates_denied(self):
        m = matrix()
        m["unresolved_gates"] = ["G6"]
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_bad_transition_action_denied(self):
        m = matrix()
        m["lifecycle_cases"][0]["simulated_event"] = "REAL_ROTATED"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_bad_threat_action_denied(self):
        m = matrix()
        m["threat_cases"][0]["simulated_outcome"] = "VERIFIED"
        self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_actual_key_present_denied(self):
        m = matrix()
        m["real_keys_present"] = True
        self.check("D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO", m=m)

    def test_parent_false_key_approval_denied(self):
        p = predecessor()
        p["d542_contract"]["real_key_operation_approved"] = True
        self.check("D543_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_parent_false_g6_02_selection_denied(self):
        p = predecessor()
        p["d542_predecessor"]["d541_matrix"]["actual_candidate_selected"] = True
        self.check("D543_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_parent_fake_public_metadata_denied(self):
        p = predecessor()
        p["d542_predecessor"]["d541_predecessor"][
            "d540_predecessor_bundle"]["d539_manifest"]["items"][0][
            "private_data_attached"] = True
        self.check("D543_PREDECESSOR_NOT_COHERENT_NO_GO", p=p)

    def test_parent_bundle_missing_denied(self):
        self.check("D543_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED", p={})

    def test_parent_injected_go_denied(self):
        with patch(
            "scripts.p0_01_d5_43_key_lifecycle_review.review_d542_selection_rules",
            return_value={"status":
                "D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION",
                "runtime_go_no_go":"GO"},
        ):
            self.check("D543_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_parent_injected_real_anchor_denied(self):
        p = predecessor()
        v = review_d542_selection_rules(*(p[k] for k in _PARENT_KEYS))
        v["real_trust_anchors_implemented"] = 1
        with patch(
            "scripts.p0_01_d5_43_key_lifecycle_review.review_d542_selection_rules",
            return_value=v,
        ):
            self.check("D543_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")

    def test_parent_injected_status_denied(self):
        p = predecessor()
        v = review_d542_selection_rules(*(p[k] for k in _PARENT_KEYS))
        v["status"] = "APPROVED"
        with patch(
            "scripts.p0_01_d5_43_key_lifecycle_review.review_d542_selection_rules",
            return_value=v,
        ):
            self.check("D543_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_pure_review_has_no_real_file_io(self):
        args = (contract(), matrix(), predecessor())
        with patch("builtins.open", side_effect=AssertionError("HOST IO")):
            result = review_d543_key_lifecycle(*args)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_pure_review_never_modifies_inputs(self):
        args = (contract(), matrix(), predecessor())
        original = copy.deepcopy(args)
        review_d543_key_lifecycle(*args)
        self.assertEqual(args, original)

    def test_input_secrets_not_echoed(self):
        m = matrix()
        m["raw_private_key"] = "SYNTHETIC_SENTINEL"
        out = self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=m)
        self.assertNotIn("SYNTHETIC_SENTINEL", repr(out))

    def test_invalid_contract_types_denied(self):
        for value in (None, True, {}, [], "GO"):
            with self.subTest(value=repr(value)):
                self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=value)

    def test_invalid_matrix_types_denied(self):
        for value in (None, True, {}, [], "GO"):
            with self.subTest(value=repr(value)):
                self.check("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED", m=value)

    def test_status_never_approves_real_key(self):
        s = read("p0_01_d5_43_status.json")
        self.assertEqual(s["unresolved_gates"], [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        self.assertEqual(s["real_keys_generated"], 0)
        self.assertEqual(s["real_revocations_attested"], 0)
        self.assertEqual(s["real_acceptance_criteria_completed"], 0)
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "host_io_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)

    def test_repeated_review_never_latches_authority(self):
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")
        m = matrix()
        m["threat_cases"][0]["simulated_outcome"] = "SIMULATED_ATTACK"
        self.check("D543_SYNTHETIC_REPLAY_REVOKE_OR_HANDOFF_DENIED", m=m)
        self.check("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS")


def _control_false_test(index, flag):
    def test(self):
        m = matrix()
        m["required_controls"][index][flag] = True
        self.check("D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO", m=m)
    return test


def _lifecycle_test(index, field, value, expected):
    def test(self):
        m = matrix()
        m["lifecycle_cases"][index][field] = value
        self.check(expected, m=m)
    return test


def _threat_test(index, field, value, expected):
    def test(self):
        m = matrix()
        m["threat_cases"][index][field] = value
        self.check(expected, m=m)
    return test


def _contract_flag_test(field):
    def test(self):
        c = contract()
        c[field] = True
        self.check("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED", c=c)
    return test


def _record_flag_test(field):
    def test(self):
        m = matrix()
        m[field] = True
        self.check("D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO", m=m)
    return test


for _i in range(len(_CONTROLS)):
    for _field in ("real_attestation_verified", "human_signoff"):
        setattr(D543KeyLifecycleTests, f"test_control_{_i:02d}_{_field}",
                _control_false_test(_i, _field))

for _i in range(len(_TRANSITIONS)):
    for _field, _value, _expected in (
        ("simulated_event", "SIMULATED_SAFE_PATH",
         "D543_SYNTHETIC_SAFE_PATH_NOT_REAL_ATTESTATION"),
        ("simulated_event", "SIMULATED_UNSAFE_PATH",
         "D543_SYNTHETIC_REPLAY_REVOKE_OR_HANDOFF_DENIED"),
        ("real_key_operation", True,
         "D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO"),
        ("real_transition_committed", True,
         "D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO"),
        ("real_independent_proof", True,
         "D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO"),
        ("real_human_approval", True,
         "D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO"),
    ):
        setattr(D543KeyLifecycleTests,
                f"test_transition_{_i:02d}_{_field}_{_value}",
                _lifecycle_test(_i, _field, _value, _expected))

for _i in range(len(_THREATS)):
    for _field, _value, _expected in (
        ("simulated_outcome", "SIMULATED_ATTACK",
         "D543_SYNTHETIC_REPLAY_REVOKE_OR_HANDOFF_DENIED"),
        ("simulated_outcome", "SIMULATED_MITIGATED",
         "D543_SYNTHETIC_SAFE_PATH_NOT_REAL_ATTESTATION"),
        ("real_attack_performed", True,
         "D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO"),
        ("real_detection_verified", True,
         "D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO"),
        ("stop_release_authorized", True,
         "D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO"),
    ):
        setattr(D543KeyLifecycleTests,
                f"test_threat_{_i:02d}_{_field}_{_value}",
                _threat_test(_i, _field, _value, _expected))

for _flag in _CONTRACT_FALSE:
    setattr(D543KeyLifecycleTests, f"test_contract_no_{_flag}",
            _contract_flag_test(_flag))

for _flag in _RECORD_FALSE:
    setattr(D543KeyLifecycleTests, f"test_record_no_{_flag}",
            _record_flag_test(_flag))


if __name__ == "__main__":
    main()
