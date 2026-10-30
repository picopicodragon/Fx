"""D5-34: G2 publication boundary + G6 synthetic issuer/lineage review.

All inputs are caller-supplied and UNTRUSTED. Identical issuer labels,
generations, ticks and hashes cannot establish independent witness identity.
Pure in-memory diagnostic: NO MT4, orders, IO, Git hooks, clocks, or signing.
"""
from __future__ import annotations

import re

from scripts.p0_01_d5_32_crash_matrix_privacy import _public_json_valid
from scripts.p0_01_d5_33_proof_boundary import (
    _FALSE as _D533_FALSE, review_d533_independent_proofs,
)

_ROLES = ("journal", "anchor", "revocation")
_PUBLIC = ("check_id", "design_state", "origin", "schema_version",
           "simulation_only")
_PLAN = frozenset(("origin", "schema_version", "scope", "g2",
                   "g6", "phase_1", "runtime_go_no_go", "verified_values"))
_G2_PLAN = frozenset(("allowed_public_fields", "real_private_export_allowed",
                       "real_git_hook_installed", "real_file_scan_performed"))
_G6_PLAN = frozenset(("lineage_roles", "synthetic_freshness_limit_ticks",
                       "issuer_rotation_requires_external_authority",
                       "actual_issuer_authentication_verified",
                       "real_anchor_independent", "actual_revocation_durable",
                       "actual_clock_validated", "real_rollback_protection"))
_CASE = frozenset(("origin", "schema_version", "simulated_only",
                   "public_export", "lineage", "real_operation_claim",
                   "stop_release_claim"))
_EXPORT = frozenset(("public_json", "private_reference_label",
                     "private_payload_attached", "private_export_requested",
                     "git_write_requested", "real_redaction_verified"))
_LINEAGE = frozenset(("origin", "schema_version", "simulated_reference_tick",
                      "journal", "anchor", "revocation",
                      "previous_issuer_id", "previous_issuer_epoch",
                      "rotation_claim", "real_handoff_verified",
                      "independent_witness_authenticated"))
_STATE = frozenset(("generation", "sequence", "observed_tick",
                    "issuer_id", "issuer_epoch", "stop_latched",
                    "revocation_tombstone"))
_ISSUER = re.compile(r"SYNTHETIC_ISSUER_[A-Z0-9_]{1,32}\Z")
_PRIVATE_LABEL = re.compile(r"SYNTHETIC_PRIVATE_REF_[A-Z0-9_]{1,32}\Z")
_AGE = 5
_FALSE = (*_D533_FALSE,
          "g2_actual_publication_scanned", "g2_private_export_approved",
          "g2_private_boundary_real_world_verified",
          "g2_git_write_authorized", "g6_issuer_authentication_real",
          "g6_issuer_handoff_approved", "g6_anchor_freshness_real",
          "g6_revocation_ordering_real", "g6_lineage_verified_real",
          "g6_actual_rollback_protection", "g6_independent_epoch_verified")


def _deny(status: str, predecessor: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {k: False for k in _FALSE}
    result.update({
        "status": status, "d533_status": predecessor,
        "effective_approved_actions": [], "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN", "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _design_valid(p: object) -> bool:
    if (type(p) is not dict or set(p) != _PLAN
            or p.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(p.get("schema_version")) is not int
            or p["schema_version"] != 1
            or p.get("scope") != "D534_G2_G6_SYNTHETIC_LINEAGE_ONLY"
            or p.get("phase_1") != "BLOCKED"
            or p.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in p or p["verified_values"] is not None):
        return False
    g2, g6 = p.get("g2"), p.get("g6")
    return (
        type(g2) is dict and set(g2) == _G2_PLAN
        and g2.get("allowed_public_fields") == list(_PUBLIC)
        and all(g2.get(k) is False for k in (
            "real_private_export_allowed", "real_git_hook_installed",
            "real_file_scan_performed"))
        and type(g6) is dict and set(g6) == _G6_PLAN
        and g6.get("lineage_roles") == list(_ROLES)
        and type(g6.get("synthetic_freshness_limit_ticks")) is int
        and g6["synthetic_freshness_limit_ticks"] == _AGE
        and g6.get("issuer_rotation_requires_external_authority") is True
        and all(g6.get(k) is False for k in (
            "actual_issuer_authentication_verified",
            "real_anchor_independent", "actual_revocation_durable",
            "actual_clock_validated", "real_rollback_protection"))
    )


def _state_valid(s: object) -> bool:
    return (
        type(s) is dict and set(s) == _STATE
        and type(s.get("generation")) is int
        and 0 <= s["generation"] <= 1000000
        and type(s.get("sequence")) is int
        and 0 <= s["sequence"] <= 1000000
        and type(s.get("observed_tick")) is int
        and 0 <= s["observed_tick"] <= 1000000
        and type(s.get("issuer_id")) is str
        and _ISSUER.fullmatch(s["issuer_id"]) is not None
        and type(s.get("issuer_epoch")) is int
        and 1 <= s["issuer_epoch"] <= 1000000
        and type(s.get("stop_latched")) is bool
        and type(s.get("revocation_tombstone")) is bool
    )


def _valid_case(case: object) -> bool:
    if (type(case) is not dict or set(case) != _CASE
            or case.get("origin") != "SYNTHETIC_ONLY"
            or type(case.get("schema_version")) is not int
            or case["schema_version"] != 1
            or case.get("simulated_only") is not True
            or type(case.get("real_operation_claim")) is not bool
            or type(case.get("stop_release_claim")) is not bool):
        return False
    export = case.get("public_export")
    if (type(export) is not dict or set(export) != _EXPORT
            or not _public_json_valid(export.get("public_json"))
            or type(export.get("private_reference_label")) is not str
            or _PRIVATE_LABEL.fullmatch(export["private_reference_label"]) is None
            or any(type(export.get(k)) is not bool for k in (
                "private_payload_attached", "private_export_requested",
                "git_write_requested", "real_redaction_verified"))):
        return False
    l = case.get("lineage")
    if (type(l) is not dict or set(l) != _LINEAGE
            or l.get("origin") != "SYNTHETIC_ONLY"
            or type(l.get("schema_version")) is not int
            or l["schema_version"] != 1
            or type(l.get("simulated_reference_tick")) is not int
            or not 0 <= l["simulated_reference_tick"] <= 1000000
            or type(l.get("previous_issuer_id")) is not str
            or _ISSUER.fullmatch(l["previous_issuer_id"]) is None
            or type(l.get("previous_issuer_epoch")) is not int
            or not 1 <= l["previous_issuer_epoch"] <= 1000000
            or type(l.get("rotation_claim")) is not str
            or l["rotation_claim"] not in ("NONE", "SYNTHETIC_ROTATED")
            or type(l.get("real_handoff_verified")) is not bool
            or type(l.get("independent_witness_authenticated")) is not bool):
        return False
    return all(_state_valid(l.get(k)) for k in _ROLES)


def _child_safe(r: object) -> bool:
    return (
        type(r) is dict
        and type(r.get("status")) is str
        and type(r.get("d532_status")) is str
        and type(r.get("effective_approved_actions")) is list
        and r["effective_approved_actions"] == []
        and r.get("phase_1") == "BLOCKED"
        and r.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in r and r["verified_values"] is None
        and r.get("safety_hold_latched") is True
        and r.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(r.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(r.get(k) is False for k in _D533_FALSE)
        and set(r) == (set(_D533_FALSE) | {
            "status", "d532_status", "effective_approved_actions",
            "safety_hold_latched", "account_identity_consistency",
            "current_positions", "current_pending_orders",
            "current_ea_state", "phase_1", "runtime_go_no_go",
            "verified_values",
        })
    )


def review_d534_lineage(
    contract: object, d533_contract: object,
    d532_contract: object, d531_contract: object,
    original_evidence: object, gap_matrix: object,
    d532_fixture: object, d533_case: object,
    synthetic_case: object,
) -> dict[str, object]:
    """Check only synthetically named lineage; every outcome is a hard NO_GO."""
    try:
        if not _design_valid(contract):
            return _deny("D534_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _valid_case(synthetic_case):
            return _deny("D534_CASE_REJECTED_FAIL_CLOSED")
        child = review_d533_independent_proofs(
            d533_contract, d532_contract, d531_contract,
            original_evidence, gap_matrix, d532_fixture, d533_case,
        )
        if not _child_safe(child):
            return _deny("D534_CHILD_SAFETY_INVARIANT_REJECTED_FAIL_CLOSED")
        prior = child["status"]
        if prior != "D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED":
            return _deny("D534_PREDECESSOR_NOT_COHERENT_NO_GO", prior)
        if synthetic_case["real_operation_claim"] or synthetic_case["stop_release_claim"]:
            return _deny("D534_OPERATION_CLAIM_DENIED_NO_GO", prior)
        exp = synthetic_case["public_export"]
        if (exp["private_payload_attached"] or exp["private_export_requested"]
                or exp["git_write_requested"] or exp["real_redaction_verified"]):
            return _deny("D534_G2_EXPORT_BOUNDARY_DENIED_NO_GO", prior)
        if (type(d533_case) is not dict
                or exp["public_json"] != d533_case.get("public_json")
                or exp["private_reference_label"] in exp["public_json"]):
            return _deny("D534_G2_PUBLIC_PRIVATE_LINK_MISMATCH_NO_GO", prior)
        l = synthetic_case["lineage"]
        journal, anchor, revoked = (l[k] for k in _ROLES)
        if (l["real_handoff_verified"] or l["independent_witness_authenticated"]
                or l["rotation_claim"] != "NONE"
                or any(k["issuer_id"] != l["previous_issuer_id"]
                       or k["issuer_epoch"] != l["previous_issuer_epoch"]
                       for k in (journal, anchor, revoked))):
            return _deny("D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO", prior)
        if (anchor["generation"], anchor["sequence"]) < (
                journal["generation"], journal["sequence"]):
            return _deny("D534_G6_ANCHOR_BEHIND_NO_GO", prior)
        if (anchor["generation"], anchor["sequence"]) > (
                journal["generation"], journal["sequence"]):
            return _deny("D534_G6_ANCHOR_AHEAD_NO_GO", prior)
        if (revoked["generation"], revoked["sequence"]) > (
                journal["generation"], journal["sequence"]):
            return _deny("D534_G6_REVOCATION_AHEAD_NO_GO", prior)
        if (revoked["generation"], revoked["sequence"]) < (
                journal["generation"], journal["sequence"]):
            return _deny("D534_G6_REVOCATION_BEHIND_NO_GO", prior)
        if any(not s["stop_latched"] or not s["revocation_tombstone"]
               for s in (journal, anchor, revoked)):
            return _deny("D534_G6_STOP_OR_REVOCATION_LOST_NO_GO", prior)
        tick = l["simulated_reference_tick"]
        if (type(d533_case) is not dict
                or tick != d533_case.get("simulated_reference_tick")):
            return _deny("D534_G6_REFERENCE_TICK_SCOPE_MISMATCH_NO_GO", prior)
        if any(s["observed_tick"] > tick
               or tick - s["observed_tick"] > _AGE
               for s in (journal, anchor, revoked)):
            return _deny("D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO", prior)
        proofs = d533_case.get("synthetic_proofs")
        if (type(proofs) is not list or len(proofs) != 5
                or any(s["generation"] != proofs[i]["generation"]
                       or s["sequence"] != proofs[i]["sequence"]
                       or s["observed_tick"] != proofs[i]["observed_tick"]
                       for i, s in enumerate((journal, anchor, revoked)))):
            return _deny("D534_G6_PREDECESSOR_WITNESS_MISMATCH_NO_GO", prior)
        return _deny("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED", prior)
    except Exception:
        return _deny("D534_INPUT_EXCEPTION_FAIL_CLOSED")
