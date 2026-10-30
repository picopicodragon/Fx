"""P0-01 D5-41: G6-02 synthetic hardware/remote witness evidence-gap review.

Pure in-memory; NOT a trust-anchor verifier, price estimator, independent
attestor, operating-system scanner, actual cryptographic checker or approval.
No candidate may be selected on the basis of these synthetic requirements.
"""
from __future__ import annotations

from scripts.p0_01_d5_40_trust_boundary_review import (
    _FALSE as _D540_FALSE,
    _TESTS as _D540_TESTS,
    review_d540_trust_boundary,
)

_CANDIDATES = (
    ("LOCAL_HARDWARE_ROOT_CANDIDATE", "HW", "LOCAL_HARDWARE",
     "NO_PROVIDER_OR_HARDWARE_SELECTED", "LOCAL_ADMIN_AND_ROLLBACK_UNRESOLVED"),
    ("REMOTE_SEPARATE_WITNESS_CANDIDATE", "RW", "SEPARATE_REMOTE_DOMAIN",
     "NO_REMOTE_PROVIDER_SELECTED", "REMOTE_OPERATOR_OUTAGE_AND_FORK_UNRESOLVED"),
)
_AXES = (
    ("ADMIN_BOUNDARY", "INDEPENDENT_ADMINISTRATOR_AUTHORITY"),
    ("WRITE_BOUNDARY", "NON_SHARED_WRITE_CONTROL"),
    ("CREDENTIAL_BOUNDARY", "NON_SHARED_CREDENTIAL_AND_KEY_CUSTODY"),
    ("ROLLBACK_RESISTANCE", "MONOTONIC_STATE_AFTER_RESTORE"),
    ("FRESHNESS_SOURCE", "INDEPENDENT_TIMELINE_AND_STALENESS"),
    ("REVOCATION_DURABILITY", "IRREVERSIBLE_REVOCATION_PROOF"),
    ("KEY_ROTATION_AUTHORITY", "OLD_AND_NEW_ISSUER_TRANSITION"),
    ("SPLIT_BRAIN_DETECTION", "CONFLICTING_FORK_IDENTIFICATION"),
    ("STOP_LATCH_CONTINUITY", "STOP_PRESERVED_ON_FAILURE"),
    ("PRIVACY_NON_EXPOSURE", "NO_PRIVATE_PAYLOAD_OR_METADATA_LEAK"),
    ("LIFECYCLE_COST", "VERIFIABLE_SETUP_RECURRING_EXIT_COST"),
    ("OPERATIONAL_BURDEN", "HUMAN_OPERATOR_AND_UPDATE_BOUNDARIES"),
    ("FAILURE_RECOVERY", "RESTART_OUTAGE_REPLACEMENT_AND_DISASTER_RESTORE"),
    ("DATA_RESIDENCY", "DATA_LOCATION_POLICY_EXPORT_COMPLIANCE"),
)
_FAULTS = (
    "COMMON_ADMIN", "OLD_STATE_REPLAY", "MISSING_WITNESS",
    "FORKED_HEAD", "REVOKED_ISSUER", "STOP_LATCH_GAP",
    "PRIVATE_PAYLOAD", "DISASTER_RESTORE",
)
_CONTRACT_KEYS = frozenset((
    "origin", "schema_version", "scope", "target_criterion", "depends_on",
    "privacy_dependencies", "external_approval_gate", "candidate_ids",
    "comparison_axes", "fault_ids", "selection_policy",
    "cost_evidence_policy", "real_acceptance_evidence_policy",
    "human_design_selection_required", "chosen_architecture",
    "actual_cost_quotes_collected", "real_evidence_verified",
    "real_vendor_selected", "real_hardware_selected",
    "real_remote_witness_connected", "real_key_generated",
    "real_anchor_deployed", "real_human_approval_granted",
    "real_host_io_approved", "real_network_approved",
    "real_mt4_access_approved", "runtime_go_no_go", "phase_1",
    "verified_values",
))
_MATRIX_KEYS = frozenset((
    "origin", "schema_version", "scope", "candidates",
    "evidence_requirements", "failure_scenarios",
    "external_owner_verified", "external_g8_approval_verified",
    "real_signed_attestation_verified", "actual_candidate_selected",
    "actual_evidence_collected", "observed_at_utc",
    "account_identity_consistency", "current_positions",
    "current_pending_orders", "current_ea_state",
    "unresolved_gates", "safety_hold_latched",
))
_CANDIDATE_KEYS = frozenset((
    "candidate_id", "short_id", "domain", "procurement_state",
    "unresolved_failure", "real_provider_id", "real_cost_quote",
    "real_anchor_endpoint", "independent_operator_verified",
    "real_root_attested", "actual_candidate_selected",
))
_REQUIREMENT_KEYS = frozenset((
    "criterion_id", "candidate_id", "axis", "required_evidence",
    "verification_provenance", "real_evidence_status",
    "human_review_status", "synthetic_design_status",
    "actual_evidence", "real_cost_amount", "actual_acceptance",
))
_FAULT_KEYS = frozenset((
    "scenario_id", "candidate_id", "fault_id", "expected_reaction",
    "simulation_only", "real_fault_executed", "real_recovery_verified",
    "stop_release_authorized", "test_state",
))
_PARENT_KEYS = (
    "d540_contract", "d540_matrix", "d540_predecessor_bundle",
)
_NO_CLAIM = (
    "actual_cost_quotes_collected", "real_evidence_verified",
    "real_vendor_selected", "real_hardware_selected",
    "real_remote_witness_connected", "real_key_generated",
    "real_anchor_deployed", "real_human_approval_granted",
    "real_host_io_approved", "real_network_approved",
    "real_mt4_access_approved",
)
_MATRIX_FLAGS = (
    "external_owner_verified", "external_g8_approval_verified",
    "real_signed_attestation_verified", "actual_candidate_selected",
    "actual_evidence_collected",
)
_FALSE = (*_D540_FALSE,
          "g6_02_candidate_selected",
          "g6_02_independent_anchor_real",
          "g6_02_hardware_attested",
          "g6_02_remote_witness_attested",
          "g6_02_real_cost_quotes_verified",
          "g6_02_real_issuer_verified",
          "g6_02_actual_candidate_approved",
          "g6_02_real_outage_recovery_verified",
          "g6_02_real_fork_detection_verified",
          "g6_02_actual_evidence_collected")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {k: False for k in _FALSE}
    result.update({
        "status": status, "d540_status": upstream,
        "candidate_comparison_count": len(_CANDIDATES),
        "design_evidence_requirements": len(_AXES) * len(_CANDIDATES),
        "design_fault_cases": len(_FAULTS) * len(_CANDIDATES),
        "real_candidates_selected": 0,
        "real_independent_evidence_verified": 0,
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
    return result


def _valid_contract(c: object) -> bool:
    return (
        type(c) is dict and set(c) == _CONTRACT_KEYS
        and c.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(c.get("schema_version")) is int and c["schema_version"] == 1
        and c.get("scope") == "D541_G6_02_ANCHOR_SELECTION_REQUIREMENTS_ONLY"
        and c.get("target_criterion") == "G6-02"
        and c.get("depends_on") == ["G6-01"]
        and c.get("privacy_dependencies") == ["G2-06", "G2-07"]
        and c.get("external_approval_gate") == "G8"
        and c.get("candidate_ids") == [v[0] for v in _CANDIDATES]
        and c.get("comparison_axes") == [v[0] for v in _AXES]
        and tuple(c["comparison_axes"][:len(_D540_TESTS)]) == _D540_TESTS
        and c.get("fault_ids") == list(_FAULTS)
        and c.get("selection_policy") == "NO_WEIGHTED_SCORE_OR_AUTO_WINNER"
        and c.get("cost_evidence_policy") ==
            "NO_UNVERIFIED_CURRENCY_PRICE_OR_PROVIDER_SLA"
        and c.get("real_acceptance_evidence_policy") ==
            "OUT_OF_BAND_AND_INDEPENDENT_REQUIRED"
        and c.get("human_design_selection_required") is True
        and "chosen_architecture" in c and c["chosen_architecture"] is None
        and all(c.get(k) is False for k in _NO_CLAIM)
        and c.get("runtime_go_no_go") == "NO_GO"
        and c.get("phase_1") == "BLOCKED"
        and "verified_values" in c and c["verified_values"] is None
    )


def _matrix_shape_valid(m: object) -> bool:
    if not (
        type(m) is dict and set(m) == _MATRIX_KEYS
        and m.get("origin") == "SYNTHETIC_ONLY"
        and type(m.get("schema_version")) is int and m["schema_version"] == 1
        and m.get("scope") == "D541_CANDIDATE_EVIDENCE_GAPS_ONLY"
        and m.get("unresolved_gates") == [f"G{i}" for i in range(1, 10)]
        and m.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(m.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and m.get("safety_hold_latched") is True
        and "observed_at_utc" in m and m["observed_at_utc"] is None
        and all(type(m.get(k)) is bool for k in _MATRIX_FLAGS)
    ):
        return False
    candidates = m.get("candidates")
    if type(candidates) is not list or len(candidates) != len(_CANDIDATES):
        return False
    for row, expected in zip(candidates, _CANDIDATES):
        if (
            type(row) is not dict or set(row) != _CANDIDATE_KEYS
            or any(row.get(k) != v for k, v in zip((
                "candidate_id", "short_id", "domain",
                "procurement_state", "unresolved_failure"), expected))
            or any(row.get(k) is not None for k in (
                "real_provider_id", "real_cost_quote", "real_anchor_endpoint"))
            or any(type(row.get(k)) is not bool for k in (
                "independent_operator_verified", "real_root_attested",
                "actual_candidate_selected"))
        ):
            return False
    rows = m.get("evidence_requirements")
    if type(rows) is not list or len(rows) != len(_CANDIDATES) * len(_AXES):
        return False
    for row, cand, (axis, evidence) in zip(
        rows, (c for c in _CANDIDATES for _ in _AXES),
        _AXES * len(_CANDIDATES)
    ):
        if (
            type(row) is not dict or set(row) != _REQUIREMENT_KEYS
            or row.get("criterion_id") != f"G6-02-{cand[1]}-{axis}"
            or row.get("candidate_id") != cand[0]
            or row.get("axis") != axis
            or row.get("required_evidence") != evidence
            or row.get("verification_provenance") !=
                "FUTURE_INDEPENDENT_PROOF_REQUIRED"
            or type(row.get("real_evidence_status")) is not str
            or type(row.get("human_review_status")) is not str
            or row.get("synthetic_design_status") != "REQUIREMENT_ONLY"
            or "actual_evidence" not in row or row["actual_evidence"] is not None
            or "real_cost_amount" not in row or row["real_cost_amount"] is not None
            or type(row.get("actual_acceptance")) is not bool
        ):
            return False
    faults = m.get("failure_scenarios")
    if type(faults) is not list or len(faults) != len(_CANDIDATES) * len(_FAULTS):
        return False
    for row, cand, ident in zip(
        faults, (c for c in _CANDIDATES for _ in _FAULTS),
        _FAULTS * len(_CANDIDATES)
    ):
        if (
            type(row) is not dict or set(row) != _FAULT_KEYS
            or row.get("scenario_id") != f"G6-02-{cand[1]}-{ident}"
            or row.get("candidate_id") != cand[0]
            or row.get("fault_id") != ident
            or row.get("expected_reaction") != "DENY_AND_HOLD_STOP"
            or row.get("simulation_only") is not True
            or type(row.get("real_fault_executed")) is not bool
            or type(row.get("real_recovery_verified")) is not bool
            or type(row.get("stop_release_authorized")) is not bool
            or type(row.get("test_state")) is not str
        ):
            return False
    return True


def _false_claims(m: dict[str, object]) -> bool:
    return (
        any(m[k] for k in _MATRIX_FLAGS)
        or any(
            c["independent_operator_verified"] or c["real_root_attested"]
            or c["actual_candidate_selected"] for c in m["candidates"]
        )
        or any(
            row["real_evidence_status"] != "NOT_COLLECTED"
            or row["human_review_status"] != "NOT_GRANTED"
            or row["actual_acceptance"]
            for row in m["evidence_requirements"]
        )
        or any(
            s["real_fault_executed"] or s["real_recovery_verified"]
            or s["stop_release_authorized"] or s["test_state"] != "NOT_RUN"
            for s in m["failure_scenarios"]
        )
    )


def _parent_safe(child: object) -> bool:
    return (
        type(child) is dict
        and type(child.get("status")) is str
        and type(child.get("d539_status")) is str
        and all(type(child.get(k)) is int and child[k] == n for k, n in (
            ("design_candidate_count", 4), ("design_threat_count", 12),
            ("real_trust_anchors_implemented", 0),
            ("real_evidence_items_collected", 0),
            ("real_work_packages_executed", 0),
            ("real_acceptance_criteria_completed", 0)))
        and type(child.get("effective_approved_actions")) is list
        and child["effective_approved_actions"] == []
        and child.get("safety_hold_latched") is True
        and child.get("phase_1") == "BLOCKED"
        and child.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in child and child["verified_values"] is None
        and child.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(child.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(child.get(k) is False for k in _D540_FALSE)
        and set(child) == set(_D540_FALSE) | {
            "status", "d539_status", "design_candidate_count",
            "design_threat_count", "real_trust_anchors_implemented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d541_anchor_candidates(
    contract: object, matrix: object, predecessor_bundle: object,
) -> dict[str, object]:
    """Compare future requirements only; no ranking, selection or permissions."""
    try:
        if not _valid_contract(contract):
            return _deny("D541_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _matrix_shape_valid(matrix):
            return _deny("D541_EVIDENCE_MATRIX_SCHEMA_REJECTED_FAIL_CLOSED")
        if _false_claims(matrix):
            return _deny("D541_FALSE_EVIDENCE_OR_SELECTION_NO_GO")
        if (type(predecessor_bundle) is not dict
                or set(predecessor_bundle) != set(_PARENT_KEYS)):
            return _deny("D541_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED")
        child = review_d540_trust_boundary(
            *(predecessor_bundle[k] for k in _PARENT_KEYS)
        )
        if not _parent_safe(child):
            return _deny("D541_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != "D540_TRUST_BOUNDARY_CANDIDATES_DOCUMENTED_NO_REAL_ANCHOR":
            return _deny("D541_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        return _deny(
            "D541_EVIDENCE_MATRIX_COMPLETE_NO_SELECTION_OR_REAL_PROOF",
            child["status"],
        )
    except Exception:
        return _deny("D541_INPUT_EXCEPTION_FAIL_CLOSED")
