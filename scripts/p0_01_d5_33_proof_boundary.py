"""D5-33: G2 private/public separation and G6 hypothetical proof requirements.

Pure Python analysis of caller-controlled SYNTHETIC structures. Neither a
separate label nor internally matching hashes establishes independent trust.
No OS clocks, files, brokers, terminals, Git hooks, signatures or live actions.
"""
from __future__ import annotations

import re

from scripts.p0_01_d5_27_g2_g6_offline_preflight import (
    _gaps_are_unresolved, _original_evidence_is_unverified,
)
from scripts.p0_01_d5_31_protocol_privacy_gate import _APPROVED_NONE
from scripts.p0_01_d5_32_crash_matrix_privacy import (
    _OUTPUT_FALSE as _D532_FALSE, _public_json_valid,
    review_d532_crash_matrix,
)

_WITNESSES = (
    "LOCAL_JOURNAL", "INDEPENDENT_ANCHOR", "REVOCATION_REGISTER",
    "SIGNATURE_KEY_VERIFIER", "MONOTONIC_CLOCK_WITNESS",
)
_PRIVATE_CATEGORIES = (
    "ACCOUNT_NUMBER", "SERVER_IDENTITY", "TERMINAL_PATH",
    "SCREENSHOT_BYTES", "RAW_MT4_LOG", "IP_OR_DEVICE_IDENTIFIER",
    "API_KEY_OR_SECRET", "REAL_ORDER_OR_POSITION_DETAILS",
    "REAL_OBSERVATION_TIMESTAMP",
)
_PUBLIC_KEYS = ("check_id", "design_state", "origin",
                "schema_version", "simulation_only")
_TOP = frozenset(("origin", "schema_version", "scope", "g2", "g6",
                  "approvals", "phase_1", "runtime_go_no_go",
                  "verified_values"))
_G2 = frozenset(("public_fields", "private_categories",
                 "private_export_approved", "git_hook_implemented",
                 "real_evidence_collected"))
_G6 = frozenset(("required_witnesses", "max_synthetic_tick_age",
                 "independent_boundary_implemented", "actual_anchor_verified",
                 "real_signature_verified", "real_clock_verified",
                 "actual_persistence_verified", "real_recovery_verified",
                 "acceptance_rule"))
_APPROVALS = frozenset(("visual_review", "mt4_launch", "account_login",
                        "mt4_read_only", "host_io", "ea_ex4",
                        "orders", "stop_release", "live_trading"))
_CASE = frozenset(("origin", "schema_version", "public_json",
                   "private_envelope", "synthetic_proofs",
                   "simulated_reference_tick", "stop_release_claim",
                   "real_operation_claim"))
_PRIVATE = frozenset(("origin", "schema_version", "account_token",
                      "source_ids", "raw_payload_present",
                      "private_export_requested", "provenance_authenticated",
                      "account_identity_verified", "observed_at_verified",
                      "simulated_only"))
_PROOF = frozenset(("witness", "record_id", "generation", "sequence",
                    "head_hash", "observed_tick", "source_boundary",
                    "revocation_tombstone", "stop_latched",
                    "real_independence_verified",
                    "real_signature_verified", "simulated_only"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SYN = re.compile(r"SYNTHETIC_[A-Z0-9_]{1,32}\Z")
_RECORD = re.compile(r"SYNTHETIC_RECORD_[A-Z0-9_]{1,32}\Z")
_MAX_TICK_AGE = 5
_FALSE = (*_APPROVED_NONE,
          "g2_private_public_boundary_implemented",
          "g2_actual_private_data_scanned", "g2_real_evidence_collected",
          "g2_export_authorized", "g2_actual_redaction_verified",
          "g6_witness_independence_authenticated", "g6_proof_freshness_real",
          "g6_real_signature_verified", "g6_real_anchor_verified",
          "g6_revocation_durable_verified", "g6_real_clock_verified",
          "g6_actual_crash_recovery_verified", "g6_proof_validated_real_world",
          "real_transition_authorized_by_proofs")


def _deny(status: str, prior: str = "NOT_EVALUATED") -> dict[str, object]:
    r = {k: False for k in _FALSE}
    r.update({
        "status": status, "d532_status": prior,
        "effective_approved_actions": [], "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN",
        "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return r


def _design_valid(c: object) -> bool:
    if (type(c) is not dict or set(c) != _TOP
            or c.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(c.get("schema_version")) is not int
            or c["schema_version"] != 1
            or c.get("scope") != "D533_INDEPENDENT_PROOF_REQUIREMENTS_SYNTHETIC"
            or c.get("phase_1") != "BLOCKED"
            or c.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in c or c["verified_values"] is not None):
        return False
    approvals = c.get("approvals")
    if (type(approvals) is not dict or set(approvals) != _APPROVALS
            or any(approvals[k] is not False for k in _APPROVALS)):
        return False
    g2 = c.get("g2")
    if (type(g2) is not dict or set(g2) != _G2
            or g2.get("public_fields") != list(_PUBLIC_KEYS)
            or g2.get("private_categories") != list(_PRIVATE_CATEGORIES)
            or any(g2.get(k) is not False for k in (
                "private_export_approved", "git_hook_implemented",
                "real_evidence_collected"))):
        return False
    g6 = c.get("g6")
    return (
        type(g6) is dict and set(g6) == _G6
        and g6.get("required_witnesses") == list(_WITNESSES)
        and type(g6.get("max_synthetic_tick_age")) is int
        and g6["max_synthetic_tick_age"] == _MAX_TICK_AGE
        and g6.get("acceptance_rule") ==
            "SYNTHETIC_COHERENCE_IS_NEVER_REAL_AUTHORIZATION"
        and all(g6.get(k) is False for k in (
            "independent_boundary_implemented", "actual_anchor_verified",
            "real_signature_verified", "real_clock_verified",
            "actual_persistence_verified", "real_recovery_verified"))
    )


def _private_valid(p: object) -> bool:
    return (
        type(p) is dict and set(p) == _PRIVATE
        and p.get("origin") == "SYNTHETIC_ONLY"
        and type(p.get("schema_version")) is int
        and p["schema_version"] == 1
        and type(p.get("account_token")) is str
        and _SYN.fullmatch(p["account_token"]) is not None
        and p.get("source_ids") == ["EV-OLD", "EV-NEW"]
        and all(type(p.get(k)) is bool for k in (
            "raw_payload_present", "private_export_requested",
            "provenance_authenticated", "account_identity_verified",
            "observed_at_verified", "simulated_only"))
        and p["simulated_only"] is True
    )


def _proof_valid(p: object) -> bool:
    return (
        type(p) is dict and set(p) == _PROOF
        and type(p.get("witness")) is str
        and p["witness"] in _WITNESSES
        and type(p.get("record_id")) is str
        and _RECORD.fullmatch(p["record_id"]) is not None
        and type(p.get("generation")) is int
        and 1 <= p["generation"] <= 1000000
        and type(p.get("sequence")) is int
        and 0 <= p["sequence"] <= 1000000
        and type(p.get("head_hash")) is str
        and _HASH.fullmatch(p["head_hash"]) is not None
        and type(p.get("observed_tick")) is int
        and 0 <= p["observed_tick"] <= 1000000
        and p.get("source_boundary") in (
            "SYNTHETIC_SEPARATE_LABEL_ONLY", "SYNTHETIC_SHARED_INPUT")
        and type(p.get("source_boundary")) is str
        and type(p.get("revocation_tombstone")) is bool
        and type(p.get("stop_latched")) is bool
        and type(p.get("real_independence_verified")) is bool
        and type(p.get("real_signature_verified")) is bool
        and p.get("simulated_only") is True
    )


def _child_safely_denied(child: object) -> bool:
    if (type(child) is not dict
            or type(child.get("status")) is not str
            or type(child.get("synthetic_cutpoint_statuses")) is not list
            or child.get("safety_hold_latched") is not True
            or child.get("phase_1") != "BLOCKED"
            or child.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in child
            or child["verified_values"] is not None
            or type(child.get("effective_approved_actions")) is not list
            or child["effective_approved_actions"] != []
            or child.get("account_identity_consistency") != "NOT_RECONCILED"
            or any(child.get(k) != "UNKNOWN" for k in (
                "current_positions", "current_pending_orders", "current_ea_state"))):
        return False
    return (all(child.get(k) is False for k in _D532_FALSE)
            and set(child) == (set(_D532_FALSE) | {
                "status", "synthetic_cutpoint_statuses",
                "effective_approved_actions", "safety_hold_latched",
                "account_identity_consistency", "current_positions",
                "current_pending_orders", "current_ea_state",
                "phase_1", "runtime_go_no_go", "verified_values",
            }))


def review_d533_independent_proofs(
    contract: object, d532_contract: object, d531_contract: object,
    old_evidence: object, gap_matrix: object,
    d532_fixture: object, synthetic_case: object,
) -> dict[str, object]:
    """Refuse actual authority, including on internally coherent mock proofs."""
    try:
        if not _design_valid(contract):
            return _deny("D533_CONTRACT_REJECTED_FAIL_CLOSED")
        # Never promote historical reports, including EV-OLD vs EV-NEW.
        if type(synthetic_case) is not dict or set(synthetic_case) != _CASE:
            return _deny("D533_CASE_REJECTED_FAIL_CLOSED")
        if (synthetic_case.get("origin") != "SYNTHETIC_ONLY"
                or type(synthetic_case.get("schema_version")) is not int
                or synthetic_case["schema_version"] != 1
                or type(synthetic_case.get("stop_release_claim")) is not bool
                or type(synthetic_case.get("real_operation_claim")) is not bool
                or type(synthetic_case.get("simulated_reference_tick")) is not int
                or not 0 <= synthetic_case["simulated_reference_tick"] <= 1000000
                or not _public_json_valid(synthetic_case.get("public_json"))
                or not _private_valid(synthetic_case.get("private_envelope"))):
            return _deny("D533_CASE_REJECTED_FAIL_CLOSED")
        if (type(d532_fixture) is not dict
                or set(d532_fixture) != {"public_json", "matrix"}
                or synthetic_case["public_json"] != d532_fixture["public_json"]):
            return _deny("D533_G2_PUBLIC_PRIVATE_MISMATCH_NO_GO")
        if (not _original_evidence_is_unverified(old_evidence)
                or not _gaps_are_unresolved(gap_matrix)):
            return _deny("D533_PREDECESSOR_BASELINE_REJECTED_FAIL_CLOSED")
        child = review_d532_crash_matrix(
            d532_contract, d531_contract, old_evidence, gap_matrix,
            d532_fixture["public_json"], d532_fixture["matrix"],
        )
        if not _child_safely_denied(child):
            return _deny("D533_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED")
        prior = child["status"]
        if prior != "D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED":
            return _deny("D533_PREVIOUS_STAGE_DENIED_NO_GO", prior)
        if (synthetic_case["stop_release_claim"]
                or synthetic_case["real_operation_claim"]):
            return _deny("D533_OPERATION_CLAIM_DENIED_NO_GO", prior)
        private = synthetic_case["private_envelope"]
        if private["private_export_requested"]:
            return _deny("D533_G2_PRIVATE_EXPORT_DENIED_NO_GO", prior)
        if (private["raw_payload_present"] or
                private["provenance_authenticated"] or
                private["account_identity_verified"] or
                private["observed_at_verified"]):
            return _deny("D533_G2_PRIVATE_EVIDENCE_UNTRUSTED_NO_GO", prior)
        proofs = synthetic_case.get("synthetic_proofs")
        if (type(proofs) is not list or len(proofs) != len(_WITNESSES)
                or any(not _proof_valid(p) for p in proofs)):
            return _deny("D533_G6_PROOF_SET_REJECTED_FAIL_CLOSED", prior)
        if [p["witness"] for p in proofs] != list(_WITNESSES):
            return _deny("D533_G6_PROOF_SCOPE_REJECTED_FAIL_CLOSED", prior)
        if any(p["real_independence_verified"] or
               p["real_signature_verified"] for p in proofs):
            return _deny("D533_G6_FALSE_AUTHENTICATION_CLAIM_NO_GO", prior)
        if any(p["source_boundary"] != "SYNTHETIC_SEPARATE_LABEL_ONLY"
               for p in proofs):
            return _deny("D533_G6_SHARED_TRUST_BOUNDARY_NO_GO", prior)
        tick = synthetic_case["simulated_reference_tick"]
        if any(p["observed_tick"] > tick or
               tick - p["observed_tick"] > _MAX_TICK_AGE for p in proofs):
            return _deny("D533_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", prior)
        baseline = d532_fixture["matrix"][0]["recovery"]["before"]
        if any(
            p["record_id"] != baseline["record_id"]
            or p["generation"] != baseline["generation"]
            or p["sequence"] != baseline["sequence"]
            or p["head_hash"] != baseline["head_hash"]
            or p["revocation_tombstone"] != baseline["revocation_tombstone"]
            or p["stop_latched"] is not True
            for p in proofs
        ):
            return _deny("D533_G6_WITNESS_CONTRADICTION_NO_GO", prior)
        return _deny("D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED",
                     prior)
    except Exception:
        return _deny("D533_INPUT_EXCEPTION_FAIL_CLOSED")
