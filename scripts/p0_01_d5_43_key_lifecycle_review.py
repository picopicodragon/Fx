"""D5-43 G6-03: synthetic key custody/rotation/revocation design gate.

No actual keys, cryptography, issuer signatures, OS/host/network access or
MT4 operations. All cases are labels. Even simulated safe transitions never
promote an issuer, release STOP or grant runtime permission.
"""
from __future__ import annotations

from scripts.p0_01_d5_42_selection_policy_review import (
    _FALSE as _D542_FALSE, review_d542_selection_rules,
)

_CONTROLS = (
    ("CUSTODIAN_ISOLATION", "KEY_CUSTODIAN_NOT_SOLE_APPROVER"),
    ("NON_EXPORTABILITY", "PROVE_SECRET_NOT_COPIED_TO_GIT_LOG_OR_ANCHOR"),
    ("ISSUER_AUTHENTICATION", "ISSUER_ORIGIN_VERIFIED_OUT_OF_BAND"),
    ("EPOCH_MONOTONICITY", "OLD_EPOCH_OR_FORK_NEVER_AUTO_ACCEPTED"),
    ("REVOCATION_TOMBSTONE", "REVOCATION_RECORDED_INDEPENDENTLY_AND_DURABLY"),
    ("RESTART_REVOCATION_MEMORY", "RESTORE_CANNOT_REENABLE_REVOKED_ISSUER"),
    ("REPLAY_PREVENTION", "REUSED_KEY_NONCE_AND_OLD_SIGNATURE_DENIED"),
    ("ATOMIC_HANDOVER", "OLD_NEW_ISSUER_AND_ANCHOR_COMMIT_COHERENCE"),
    ("INDEPENDENT_ROTATION_APPROVAL", "SEPARATE_HUMAN_AND_ANCHOR_AUTHORITIES"),
    ("APPROVAL_EXPIRY_AND_SCOPE", "SINGLE_SCOPED_REVOCABLE_APPROVAL_PROOF"),
    ("EMERGENCY_STOP_LATCH", "KEY_FAULT_NEVER_RELEASES_STOP"),
    ("PRIVATE_EVIDENCE_SEPARATION", "NO_REAL_KEYS_OR_ACCOUNT_IDENTIFIERS_IN_PUBLIC_RECORD"),
)
_TRANSITIONS = (
    ("NO_CHANGE", "PRESERVE_STOP_UNTIL_EXTERNALLY_PROVEN"),
    ("ROTATION_PREPARE", "NO_KEY_USE_OR_GO_DURING_PREPARATION"),
    ("ROTATION_COMMIT", "ATOMIC_ISSUER_EPOCH_HANDOVER_REQUIRED"),
    ("KEY_REVOCATION", "TOMBSTONE_MUST_SURVIVE_RESTART"),
    ("ISSUER_REVOCATION", "ALL_REVOKED_ISSUER_EPOCHS_DENIED"),
    ("EMERGENCY_FREEZE", "LATCH_STOP_AND_REQUIRE_SEPARATE_RELEASE"),
    ("RESTART_RECONCILE", "UNPROVEN_CONTINUITY_REMAINS_BLOCKED"),
    ("OLD_KEY_REPLAY", "NEVER_REAUTHORIZE_REVOKED_KEY"),
    ("TOMBSTONE_ROLLBACK", "NEVER_ACCEPT_MISSING_REVOCATION"),
    ("UNAPPROVED_ISSUER_REBIND", "NEVER_ACCEPT_UNVERIFIED_ISSUER"),
)
_THREATS = (
    ("SHARED_CUSTODIAN_AND_APPROVER", "SINGLE_PRINCIPAL_CAN_FORGE_ROTATION"),
    ("FAKE_ISSUER_CERTIFICATE", "UNVERIFIED_ISSUER_CLAIMS_AUTHORITY"),
    ("REVOKED_KEY_REPLAY", "OLD_SIGNATURE_CAN_REAPPEAR"),
    ("EPOCH_REWIND", "OLD_EPOCH_ACCEPTED_AS_NEW"),
    ("TOMBSTONE_LOSS", "REVOCATION_ERASED_AFTER_RESTORE"),
    ("DUAL_ACTIVE_ISSUERS", "OLD_AND_NEW_BOTH_AUTHORITATIVE"),
    ("PARTIAL_COMMIT", "ANCHOR_JOURNAL_AND_ISSUER_INCONSISTENT"),
    ("OUTAGE_AUTO_RELEASE", "MISSING_ANCHOR_CLEARS_STOP"),
    ("SECRET_EXPORT", "REAL_KEYS_EXPOSED_IN_PUBLIC_OR_LOCAL_LOG"),
    ("APPROVAL_REUSE", "STALE_HUMAN_APPROVAL_REPLAYED"),
)
_POLICIES = {
    "lifecycle_rule": "REVOKED_KEYS_AND_ISSUERS_NEVER_REENTER_ACTIVE_STATE",
    "epoch_rule": "STRICT_FUTURE_EPOCH_AND_INDEPENDENT_CUSTODY_PROOF_REQUIRED",
    "tombstone_rule": "NO_REVOCATION_ERASURE_ON_RESTART_ROLLBACK_OR_DISASTER_RECOVERY",
    "approval_rule": "DESIGN_REVIEW_NOT_RUNTIME_OR_STOP_RELEASE_AUTHORITY",
    "atomicity_rule": "NO_PARTIAL_ROTATION_OR_MIXED_ISSUER_ANCHOR_COMMIT",
    "private_key_rule": "NO_REAL_SECRET_OR_PRIVATE_KEY_MATERIAL_IN_SYNTHETIC_OR_GIT",
    "unknown_rule": "MISSING_OR_UNTRUSTED_EVIDENCE_MEANS_NO_GO",
}
_CONTRACT_FALSE = (
    "real_key_custodian_selected", "real_key_generated", "real_keys_rotated",
    "real_keys_revoked", "real_issuer_authenticated",
    "real_independent_anchor_verified", "real_tombstone_persisted",
    "real_human_design_approval", "real_runtime_approval",
    "real_stop_release_approval", "real_host_io_approved",
    "real_network_io_approved", "real_mt4_io_approved",
)
_RECORD_FALSE = (
    "real_keys_present", "real_issuer_present",
    "actual_key_operations_requested", "actual_anchor_network_requested",
    "actual_host_io_requested", "actual_mt4_requested",
    "actual_stop_release_requested",
)
_CONTRACT_KEYS = frozenset((
    "origin", "schema_version", "scope", "target_criterion",
    "upstream_criteria", "external_gate_dependencies",
    "privacy_dependencies", "required_controls", "transition_ids",
    "threat_ids", *_POLICIES, *_CONTRACT_FALSE,
    "phase_1", "runtime_go_no_go", "verified_values",
))
_MATRIX_KEYS = frozenset((
    "origin", "schema_version", "scope", "required_controls",
    "lifecycle_cases", "threat_cases", "issuer_chain", *_RECORD_FALSE,
    "real_observation_utc", "account_identity_consistency",
    "current_positions", "current_pending_orders", "current_ea_state",
    "unresolved_gates", "safety_hold_latched",
))
_CONTROL_KEYS = frozenset((
    "control_id", "future_proof", "verification_boundary",
    "design_state", "real_evidence", "real_attestation_verified",
    "human_signoff",
))
_LIFECYCLE_KEYS = frozenset((
    "transition_id", "expected_safety", "simulated_event",
    "simulated_issuer", "simulated_key", "simulated_epoch",
    "design_only", "real_key_operation", "real_transition_committed",
    "real_independent_proof", "real_human_approval",
))
_THREAT_KEYS = frozenset((
    "threat_id", "attack", "expected_reaction", "simulated_outcome",
    "real_attack_performed", "real_detection_verified",
    "stop_release_authorized",
))
_CHAIN = {
    "current_alias": "SYNTHETIC_ISSUER_ALPHA",
    "next_alias": "SYNTHETIC_ISSUER_BETA",
    "current_epoch": 1,
    "next_epoch": 2,
    "previous_key_alias": "SYNTHETIC_KEY_ALPHA",
    "proposed_key_alias": "SYNTHETIC_KEY_BETA",
    "revocation_tombstone": "DESIGN_ONLY_NOT_PERSISTED",
    "actual_issuer_id": None,
    "actual_key_id": None,
    "actual_signature": None,
    "actual_external_attestation": None,
    "real_atomic_commit_verified": False,
}
_PARENT_KEYS = ("d542_contract", "d542_scenario", "d542_predecessor")
_FALSE = (*_D542_FALSE, "g6_03_real_keys_provisioned",
          "g6_03_real_custody_separated", "g6_03_real_issuer_attested",
          "g6_03_real_signature_verified",
          "g6_03_real_revocation_tombstone_durable",
          "g6_03_real_atomic_rotation_verified",
          "g6_03_real_stop_release_allowed",
          "g6_03_real_old_key_replay_blocked",
          "g6_03_real_approval_verified",
          "g6_03_real_recovery_authorized")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {k: False for k in _FALSE}
    result.update({
        "status": status, "d542_status": upstream,
        "custody_requirements_documented": len(_CONTROLS),
        "lifecycle_transitions_documented": len(_TRANSITIONS),
        "threat_cases_documented": len(_THREATS),
        "real_keys_generated": 0,
        "real_issuers_authenticated": 0,
        "real_revocations_attested": 0,
        "real_trust_anchors_implemented": 0,
        "real_candidates_selected": 0,
        "real_evidence_items_collected": 0,
        "real_work_packages_executed": 0,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO", "verified_values": None,
    })
    return result


def _valid_contract(c: object) -> bool:
    return (
        type(c) is dict and set(c) == _CONTRACT_KEYS
        and c.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(c.get("schema_version")) is int and c["schema_version"] == 1
        and c.get("scope") == "D543_G6_03_KEY_LIFECYCLE_REQUIREMENTS_ONLY"
        and c.get("target_criterion") == "G6-03"
        and c.get("upstream_criteria") == ["G6-01", "G6-02"]
        and c.get("external_gate_dependencies") == ["G8"]
        and c.get("privacy_dependencies") == ["G2-06", "G2-07"]
        and c.get("required_controls") == [x[0] for x in _CONTROLS]
        and c.get("transition_ids") == [x[0] for x in _TRANSITIONS]
        and c.get("threat_ids") == [x[0] for x in _THREATS]
        and all(c.get(k) == val for k, val in _POLICIES.items())
        and all(c.get(k) is False for k in _CONTRACT_FALSE)
        and c.get("phase_1") == "BLOCKED"
        and c.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in c and c["verified_values"] is None
    )


def _valid_matrix(m: object) -> bool:
    if not (
        type(m) is dict and set(m) == _MATRIX_KEYS
        and m.get("origin") == "SYNTHETIC_ONLY"
        and type(m.get("schema_version")) is int and m["schema_version"] == 1
        and m.get("scope") == "D543_KEY_CUSTODY_ROTATION_REVOCATION_DESIGN_ONLY"
        and m.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(m.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and m.get("unresolved_gates") == [f"G{i}" for i in range(1, 10)]
        and m.get("safety_hold_latched") is True
        and "real_observation_utc" in m and m["real_observation_utc"] is None
        and all(type(m.get(k)) is bool for k in _RECORD_FALSE)
        and type(m.get("issuer_chain")) is dict
        and set(m["issuer_chain"]) == set(_CHAIN)
        and all(type(m["issuer_chain"].get(k)) is type(val)
                and m["issuer_chain"][k] == val
                for k, val in _CHAIN.items())
    ):
        return False
    controls = m.get("required_controls")
    if type(controls) is not list or len(controls) != len(_CONTROLS):
        return False
    for row, (ident, proof) in zip(controls, _CONTROLS):
        if not (
            type(row) is dict and set(row) == _CONTROL_KEYS
            and row.get("control_id") == ident
            and row.get("future_proof") == proof
            and row.get("verification_boundary") ==
                "FUTURE_INDEPENDENT_PRIVATE_ATTESTATION"
            and row.get("design_state") == "REQUIREMENT_ONLY"
            and "real_evidence" in row and row["real_evidence"] is None
            and type(row.get("real_attestation_verified")) is bool
            and type(row.get("human_signoff")) is bool
        ):
            return False
    cases = m.get("lifecycle_cases")
    if type(cases) is not list or len(cases) != len(_TRANSITIONS):
        return False
    for row, (ident, safety) in zip(cases, _TRANSITIONS):
        if not (
            type(row) is dict and set(row) == _LIFECYCLE_KEYS
            and row.get("transition_id") == ident
            and row.get("expected_safety") == safety
            and row.get("simulated_event") in (
                "NOT_RUN", "SIMULATED_SAFE_PATH", "SIMULATED_UNSAFE_PATH")
            and row.get("simulated_issuer") == "SYNTHETIC_ISSUER_ALPHA"
            and row.get("simulated_key") == "SYNTHETIC_KEY_ALPHA"
            and type(row.get("simulated_epoch")) is int
            and row["simulated_epoch"] == 1
            and row.get("design_only") is True
            and all(type(row.get(k)) is bool for k in (
                "real_key_operation", "real_transition_committed",
                "real_independent_proof", "real_human_approval"))
        ):
            return False
    threats = m.get("threat_cases")
    if type(threats) is not list or len(threats) != len(_THREATS):
        return False
    return all(
        type(row) is dict and set(row) == _THREAT_KEYS
        and row.get("threat_id") == ident
        and row.get("attack") == attack
        and row.get("expected_reaction") == "DENY_AND_HOLD_STOP"
        and row.get("simulated_outcome") in (
            "UNTESTED", "SIMULATED_ATTACK", "SIMULATED_MITIGATED")
        and all(type(row.get(k)) is bool for k in (
            "real_attack_performed", "real_detection_verified",
            "stop_release_authorized"))
        for row, (ident, attack) in zip(threats, _THREATS)
    )


def _real_claims(m: dict[str, object]) -> bool:
    return (
        any(m[k] for k in _RECORD_FALSE)
        or any(row["real_attestation_verified"] or row["human_signoff"]
               for row in m["required_controls"])
        or any(any(row[k] for k in (
            "real_key_operation", "real_transition_committed",
            "real_independent_proof", "real_human_approval"))
            for row in m["lifecycle_cases"])
        or any(any(row[k] for k in (
            "real_attack_performed", "real_detection_verified",
            "stop_release_authorized"))
            for row in m["threat_cases"])
    )


def _parent_safe(v: object) -> bool:
    return (
        type(v) is dict and type(v.get("status")) is str
        and type(v.get("d541_status")) is str
        and all(type(v.get(k)) is int and v[k] == n for k, n in (
            ("comparison_candidates", 2),
            ("noncompensable_requirements", 24),
            ("secondary_requirements", 4),
            ("knockout_scenarios", 16),
            ("approval_stages_pending", 6),
            ("real_candidates_selected", 0),
            ("real_independent_evidence_verified", 0),
            ("real_fault_cases_executed", 0),
            ("real_trust_anchors_implemented", 0),
            ("real_evidence_items_collected", 0),
            ("real_work_packages_executed", 0),
            ("real_acceptance_criteria_completed", 0)))
        and type(v.get("effective_approved_actions")) is list
        and v["effective_approved_actions"] == []
        and v.get("safety_hold_latched") is True
        and v.get("phase_1") == "BLOCKED"
        and v.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in v and v["verified_values"] is None
        and v.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(v.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(v.get(k) is False for k in _D542_FALSE)
        and set(v) == set(_D542_FALSE) | {
            "status", "d541_status", "comparison_candidates",
            "noncompensable_requirements", "secondary_requirements",
            "knockout_scenarios", "approval_stages_pending",
            "real_candidates_selected", "real_independent_evidence_verified",
            "real_fault_cases_executed", "real_trust_anchors_implemented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d543_key_lifecycle(
    contract: object, matrix: object, predecessor: object,
) -> dict[str, object]:
    """Audit synthetic labels, without authorizing or implementing anything."""
    try:
        if not _valid_contract(contract):
            return _deny("D543_LIFECYCLE_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _valid_matrix(matrix):
            return _deny("D543_LIFECYCLE_MATRIX_REJECTED_FAIL_CLOSED")
        if _real_claims(matrix):
            return _deny("D543_FALSE_REAL_KEY_OR_APPROVAL_CLAIM_NO_GO")
        if type(predecessor) is not dict or set(predecessor) != set(_PARENT_KEYS):
            return _deny("D543_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED")
        child = review_d542_selection_rules(
            *(predecessor[k] for k in _PARENT_KEYS)
        )
        if not _parent_safe(child):
            return _deny("D543_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != "D542_HARD_KNOCKOUT_POLICY_DOCUMENTED_NO_SELECTION":
            return _deny("D543_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        upstream = child["status"]
        if any(row["simulated_event"] == "SIMULATED_UNSAFE_PATH"
               for row in matrix["lifecycle_cases"]) or any(
               row["simulated_outcome"] == "SIMULATED_ATTACK"
               for row in matrix["threat_cases"]):
            return _deny("D543_SYNTHETIC_REPLAY_REVOKE_OR_HANDOFF_DENIED",
                         upstream)
        if any(row["simulated_event"] == "SIMULATED_SAFE_PATH"
               for row in matrix["lifecycle_cases"]) or any(
               row["simulated_outcome"] == "SIMULATED_MITIGATED"
               for row in matrix["threat_cases"]):
            return _deny("D543_SYNTHETIC_SAFE_PATH_NOT_REAL_ATTESTATION",
                         upstream)
        return _deny("D543_KEY_LIFECYCLE_REQUIREMENTS_ONLY_NO_REAL_KEYS",
                     upstream)
    except Exception:
        return _deny("D543_INPUT_EXCEPTION_FAIL_CLOSED")
