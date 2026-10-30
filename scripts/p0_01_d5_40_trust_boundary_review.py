"""P0-01 D5-40: synthetic G6-01 trust-domain threat model, deny only.

There is no trust anchor, real issuer, key, signature, witness, clock,
storage, broker connection or actual human authorization in this module.
The candidate labels are not product security claims or verified roots.
"""
from __future__ import annotations

from scripts.p0_01_d5_39_egress_gate import (
    _FALSE as _D539_FALSE, review_d539_egress,
)

_ROLES = (
    "EVIDENCE_PRODUCER", "TRUST_ANCHOR_CUSTODIAN",
    "INDEPENDENT_VERIFIER", "REVOCATION_AUTHORITY", "HUMAN_APPROVER",
)
_CANDIDATES = (
    ("SAME_PROCESS_MIRROR", "SAME_PROCESS", "SAME_PRINCIPAL",
     "LOCAL_MUTABLE", "NOT_INDEPENDENT",
     "SHARED_WRITER_CAN_REWRITE_BOTH"),
    ("SAME_HOST_DIFFERENT_USER", "SAME_HOST",
     "SEPARATE_OS_PRINCIPAL_UNVERIFIED", "LOCAL_MUTABLE",
     "INSUFFICIENT_EXTERNAL_INDEPENDENCE",
     "HOST_ADMIN_OR_DISK_ROLLBACK"),
    ("LOCAL_HARDWARE_ROOT_CANDIDATE", "LOCAL_HARDWARE",
     "HARDWARE_POLICY_UNVERIFIED", "HARDWARE_PLUS_LOCAL",
     "CONDITIONAL_DESIGN_ONLY",
     "ROLLBACK_CLOCK_AND_RECOVERY_REQUIRE_EXTERNAL_PROOF"),
    ("REMOTE_SEPARATE_WITNESS_CANDIDATE", "SEPARATE_REMOTE_DOMAIN",
     "INDEPENDENT_ADMIN_UNVERIFIED", "REMOTE_APPEND_ONLY_UNVERIFIED",
     "CONDITIONAL_DESIGN_ONLY",
     "REMOTE_ADMIN_COLLUSION_SPLIT_BRAIN_AND_OUTAGE"),
)
_THREATS = (
    ("SHARED_ADMIN_AUTHORITY", "COMMON_CONTROL_OF_BOTH_ROOTS"),
    ("JOURNAL_ANCHOR_COORDINATED_FORGERY",
     "SAME_ACTOR_CAN_REWRITE_ALL_RECORDS"),
    ("LOCAL_ROLLBACK_AND_REPLAY", "OLD_SIGNED_STATE_REPLAY"),
    ("ISSUER_EPOCH_REBINDING", "UNTRUSTED_ROTATION_OR_KEY_CHANGE"),
    ("REVOCATION_TOMBSTONE_ERASURE", "LOST_REVOCATION_AFTER_RESTART"),
    ("SPLIT_BRAIN_WITNESS", "CONFLICTING_FORKS_BOTH_CLAIM_HEAD"),
    ("ANCHOR_TIMEOUT_OR_OUTAGE", "INDEPENDENT_REFERENCE_UNAVAILABLE"),
    ("FALSE_TIME_FRESHNESS", "FAKE_CLOCK_OR_STALE_TICK"),
    ("PRIVATE_DATA_IN_ANCHOR", "SECRET_OR_ACCOUNT_IDENTIFIER_EXPORTED"),
    ("SINGLE_WRITER_FENCE_BYPASS", "MULTIPLE_WRITERS_SAME_EPOCH"),
    ("HOST_REBOOT_WITHOUT_PROOF",
     "UNPROVEN_CLOCK_OR_STORAGE_CONTINUITY"),
    ("APPROVAL_OR_KEY_REVOCATION_SPOOF",
     "UNAUTHENTICATED_HUMAN_APPROVAL"),
)
_TESTS = (
    "ADMIN_BOUNDARY", "WRITE_BOUNDARY", "CREDENTIAL_BOUNDARY",
    "ROLLBACK_RESISTANCE", "FRESHNESS_SOURCE", "REVOCATION_DURABILITY",
    "KEY_ROTATION_AUTHORITY", "SPLIT_BRAIN_DETECTION",
    "STOP_LATCH_CONTINUITY", "PRIVACY_NON_EXPOSURE",
)
_CONTRACT_KEYS = frozenset((
    "origin", "schema_version", "scope", "target_criterion",
    "next_criterion", "privacy_dependencies", "authority_roles",
    "candidate_ids", "threat_ids", "mandatory_independence_tests",
    "chosen_architecture", "external_provider_selected",
    "independent_anchor_implemented", "real_key_generated",
    "real_signature_verified", "real_issuer_authenticated",
    "actual_human_approved", "host_io_approved",
    "mt4_access_approved", "phase_1", "runtime_go_no_go",
    "verified_values",
))
_MATRIX_KEYS = frozenset((
    "origin", "schema_version", "scope", "candidates", "threats",
    "observed_at_utc", "broker_verified", "external_anchor_verified",
    "real_host_io_requested", "real_mt4_access_requested",
    "real_signature_operation_requested", "real_stop_release_requested",
    "real_trade_requested", "account_identity_consistency",
    "current_positions", "current_pending_orders", "current_ea_state",
    "unresolved_gates", "safety_hold_latched",
))
_CANDIDATE_KEYS = frozenset((
    "candidate_id", "domain", "principal", "storage", "assessment",
    "limitation", "real_operator_identity", "real_anchor_address",
    "actual_trust_boundary_proven", "real_crypto_attested",
    "real_rollback_prevention_attested", "human_selection_approved",
))
_THREAT_KEYS = frozenset((
    "threat_id", "attack", "denial", "mitigation_state",
    "real_fault_injection_performed", "independent_detection_verified",
    "stop_release_requested", "actual_leakage_justified",
))
_ACTION_FLAGS = (
    "real_host_io_requested", "real_mt4_access_requested",
    "real_signature_operation_requested", "real_stop_release_requested",
    "real_trade_requested",
)
_PARENT_KEYS = (
    "d539_contract", "d539_manifest", "d539_public_json",
    "d539_predecessors",
)
_FALSE = (*_D539_FALSE, "g6_01_real_authority_established",
          "g6_01_actual_independent_trust_root",
          "g6_01_real_issuer_authenticated",
          "g6_01_real_private_key_attested",
          "g6_01_real_witness_available",
          "g6_01_real_revocation_durable",
          "g6_01_real_epoch_pin_verified",
          "g6_01_real_rollback_resistance_verified",
          "g6_01_real_human_selection_approved",
          "g6_01_real_stop_release_authorized")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    out = {name: False for name in _FALSE}
    out.update({
        "status": status, "d539_status": upstream,
        "design_candidate_count": len(_CANDIDATES),
        "design_threat_count": len(_THREATS),
        "real_trust_anchors_implemented": 0,
        "real_evidence_items_collected": 0,
        "real_work_packages_executed": 0,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return out


def _valid_contract(c: object) -> bool:
    return (
        type(c) is dict and set(c) == _CONTRACT_KEYS
        and c.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(c.get("schema_version")) is int and c["schema_version"] == 1
        and c.get("scope") == "D540_G6_01_TRUST_AUTHORITY_THREAT_MODEL_ONLY"
        and c.get("target_criterion") == "G6-01"
        and c.get("next_criterion") == "G6-02"
        and c.get("privacy_dependencies") == ["G2-06", "G2-07"]
        and c.get("authority_roles") == list(_ROLES)
        and c.get("candidate_ids") == [x[0] for x in _CANDIDATES]
        and c.get("threat_ids") == [x[0] for x in _THREATS]
        and c.get("mandatory_independence_tests") == list(_TESTS)
        and "chosen_architecture" in c and c["chosen_architecture"] is None
        and all(c.get(k) is False for k in (
            "external_provider_selected", "independent_anchor_implemented",
            "real_key_generated", "real_signature_verified",
            "real_issuer_authenticated", "actual_human_approved",
            "host_io_approved", "mt4_access_approved"))
        and c.get("phase_1") == "BLOCKED"
        and c.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in c and c["verified_values"] is None
    )


def _valid_matrix(m: object) -> bool:
    if not (
        type(m) is dict and set(m) == _MATRIX_KEYS
        and m.get("origin") == "SYNTHETIC_ONLY"
        and type(m.get("schema_version")) is int and m["schema_version"] == 1
        and m.get("scope") == "D540_CANDIDATE_COMPARE_NO_REAL_AUTHORITY"
        and m.get("unresolved_gates") == [f"G{i}" for i in range(1, 10)]
        and m.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(m.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and "observed_at_utc" in m and m["observed_at_utc"] is None
        and m.get("safety_hold_latched") is True
        and all(type(m.get(k)) is bool for k in (
            "broker_verified", "external_anchor_verified", *_ACTION_FLAGS))
    ):
        return False
    candidates = m.get("candidates")
    if type(candidates) is not list or len(candidates) != len(_CANDIDATES):
        return False
    for candidate, expected in zip(candidates, _CANDIDATES):
        if (
            type(candidate) is not dict
            or set(candidate) != _CANDIDATE_KEYS
            or any(candidate.get(k) != v for k, v in zip(
                ("candidate_id", "domain", "principal", "storage",
                 "assessment", "limitation"), expected))
            or "real_operator_identity" not in candidate
            or candidate["real_operator_identity"] is not None
            or "real_anchor_address" not in candidate
            or candidate["real_anchor_address"] is not None
            or any(type(candidate.get(k)) is not bool for k in (
                "actual_trust_boundary_proven", "real_crypto_attested",
                "real_rollback_prevention_attested", "human_selection_approved"))
        ):
            return False
    threats = m.get("threats")
    if type(threats) is not list or len(threats) != len(_THREATS):
        return False
    for item, (ident, attack) in zip(threats, _THREATS):
        if (
            type(item) is not dict or set(item) != _THREAT_KEYS
            or item.get("threat_id") != ident or item.get("attack") != attack
            or item.get("denial") != "DENY_AND_HOLD_STOP"
            or type(item.get("mitigation_state")) is not str
            or any(type(item.get(k)) is not bool for k in (
                "real_fault_injection_performed",
                "independent_detection_verified", "stop_release_requested",
                "actual_leakage_justified"))
        ):
            return False
    return True


def _parent_safe(c: object) -> bool:
    return (
        type(c) is dict and type(c.get("status")) is str
        and type(c.get("d538_status")) is str
        and all(type(c.get(k)) is int and c[k] == n for k, n in (
            ("synthetic_egress_surfaces", 8),
            ("real_egress_surfaces_scanned", 0),
            ("real_evidence_items_collected", 0),
            ("real_work_packages_executed", 0),
            ("real_acceptance_criteria_completed", 0)))
        and type(c.get("effective_approved_actions")) is list
        and c["effective_approved_actions"] == []
        and c.get("safety_hold_latched") is True
        and c.get("phase_1") == "BLOCKED"
        and c.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in c and c["verified_values"] is None
        and c.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(c.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(c.get(k) is False for k in _D539_FALSE)
        and set(c) == set(_D539_FALSE) | {
            "status", "d538_status", "synthetic_egress_surfaces",
            "real_egress_surfaces_scanned", "real_evidence_items_collected",
            "real_work_packages_executed", "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d540_trust_boundary(
    contract: object, matrix: object, predecessor_bundle: object,
) -> dict[str, object]:
    """Check only design labels; never mint keys, select an owner or GO."""
    try:
        if not _valid_contract(contract):
            return _deny("D540_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _valid_matrix(matrix):
            return _deny("D540_CANDIDATE_THREAT_SCHEMA_REJECTED_FAIL_CLOSED")
        if (matrix["broker_verified"] or matrix["external_anchor_verified"]
                or any(matrix[k] for k in _ACTION_FLAGS)):
            return _deny("D540_UNAUTHORIZED_REAL_OPERATION_OR_ANCHOR_NO_GO")
        for candidate in matrix["candidates"]:
            if any(candidate[k] for k in (
                "actual_trust_boundary_proven", "real_crypto_attested",
                "real_rollback_prevention_attested", "human_selection_approved")):
                return _deny("D540_FALSE_REAL_CANDIDATE_PROOF_NO_GO")
        for threat in matrix["threats"]:
            if (threat["real_fault_injection_performed"]
                    or threat["independent_detection_verified"]
                    or threat["stop_release_requested"]
                    or threat["actual_leakage_justified"]
                    or threat["mitigation_state"] != "REQUIRES_DESIGN_AND_INDEPENDENT_PROOF"):
                return _deny("D540_FALSE_THREAT_MITIGATION_OR_RELEASE_NO_GO")
        if (type(predecessor_bundle) is not dict
                or set(predecessor_bundle) != set(_PARENT_KEYS)):
            return _deny("D540_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED")
        child = review_d539_egress(
            *(predecessor_bundle[k] for k in _PARENT_KEYS)
        )
        if not _parent_safe(child):
            return _deny("D540_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != "D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS":
            return _deny("D540_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        return _deny("D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR",
                     child["status"])
    except Exception:
        return _deny("D540_INPUT_EXCEPTION_FAIL_CLOSED")
