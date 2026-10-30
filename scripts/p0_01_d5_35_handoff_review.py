"""D5-35: synthetic key lifecycle, issuer handoff and G2 publication boundaries.

This is intentionally a deny-only in-memory requirements review.
It NEVER checks a real key/signature, reads Git, writes storage, calls MT4,
touches a broker, retrieves time, or authorizes activation or stop release.
"""
from __future__ import annotations
import re

from scripts.p0_01_d5_32_crash_matrix_privacy import _public_json_valid
from scripts.p0_01_d5_34_lineage_privacy import (
    _FALSE as _D534_FALSE, review_d534_lineage,
)

_SURFACES = ("DESIGN_RECORD", "STATUS_SUMMARY", "REVIEW_SUMMARY")
_KEYS = frozenset(("origin", "schema_version", "scope", "g2", "g6",
                   "phase_1", "runtime_go_no_go", "verified_values"))
_G2 = frozenset(("synthetic_public_surfaces", "real_secret_scan_implemented",
                 "real_git_hook_implemented", "private_export_authorized"))
_G6 = frozenset(("handoff_states", "key_states",
                 "independent_key_authority_implemented",
                 "actual_revocation_proof_verified",
                 "actual_issuer_handoff_verified", "actual_epoch_pin_verified",
                 "real_storage_replay_checked", "real_clock_approved",
                 "actual_signature_verified", "actual_anchor_available"))
_CASE = frozenset(("origin", "schema_version", "simulated_only",
                   "publication_surfaces", "transition",
                   "real_operation_claim", "stop_release_claim"))
_SURFACE = frozenset(("surface", "public_json", "private_payload_present",
                      "private_export_requested", "real_scan_claim"))
_TRANSITION = frozenset(("origin", "schema_version", "event", "prior_issuer",
                          "next_issuer", "prior_epoch", "next_epoch",
                          "prior_generation", "next_generation",
                          "prior_sequence", "next_sequence", "prior_key_state",
                          "next_key_state", "revocation_before",
                          "revocation_after", "stop_latched",
                          "simulated_reference_tick", "observed_tick",
                          "independent_handoff_attested",
                          "independent_revocation_attested",
                          "signature_verified", "epoch_pinned",
                          "durable_tombstone_verified", "human_approved"))
_EVENTS = ("NO_CHANGE", "ROTATION", "KEY_REVOCATION", "EMERGENCY_STOP")
_KEY_STATES = ("SYNTHETIC_UNVERIFIED", "SYNTHETIC_ACTIVE_CLAIM",
               "SYNTHETIC_REVOKED_CLAIM", "SYNTHETIC_UNKNOWN")
_ISSUER = re.compile(r"SYNTHETIC_ISSUER_[A-Z0-9_]{1,32}\Z")
_REAL_CLAIMS = ("independent_handoff_attested", "independent_revocation_attested",
                "signature_verified", "epoch_pinned",
                "durable_tombstone_verified", "human_approved")
_FALSE = (*_D534_FALSE, "g2_real_publication_scanned",
          "g2_actual_secret_exposure_ruled_out", "g2_private_export_allowed",
          "g6_actual_key_revocation_verified", "g6_real_key_issuer_authenticated",
          "g6_real_issuer_rotation_authorized", "g6_epoch_handoff_verified",
          "g6_real_key_store_verified", "g6_actual_signature_validated",
          "g6_real_tombstone_durable", "g6_replay_prevention_verified",
          "g6_real_human_approval_verified", "real_recovery_authorized")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {key: False for key in _FALSE}
    result.update({
        "status": status, "d534_status": upstream,
        "safety_hold_latched": True, "effective_approved_actions": [],
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN", "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _valid_contract(p: object) -> bool:
    if (type(p) is not dict or set(p) != _KEYS
            or p.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(p.get("schema_version")) is not int or p["schema_version"] != 1
            or p.get("scope") != "D535_G2_G6_KEY_HANDOFF_SYNTHETIC_ONLY"
            or p.get("phase_1") != "BLOCKED"
            or p.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in p or p["verified_values"] is not None):
        return False
    g2, g6 = p.get("g2"), p.get("g6")
    return (
        type(g2) is dict and set(g2) == _G2
        and g2.get("synthetic_public_surfaces") == list(_SURFACES)
        and all(g2.get(k) is False for k in (
            "real_secret_scan_implemented", "real_git_hook_implemented",
            "private_export_authorized"))
        and type(g6) is dict and set(g6) == _G6
        and g6.get("handoff_states") == list(_EVENTS)
        and g6.get("key_states") == list(_KEY_STATES)
        and all(g6.get(k) is False for k in (
            "independent_key_authority_implemented",
            "actual_revocation_proof_verified",
            "actual_issuer_handoff_verified", "actual_epoch_pin_verified",
            "real_storage_replay_checked", "real_clock_approved",
            "actual_signature_verified", "actual_anchor_available"))
    )


def _valid_case(c: object) -> bool:
    if (type(c) is not dict or set(c) != _CASE
            or c.get("origin") != "SYNTHETIC_ONLY"
            or type(c.get("schema_version")) is not int or c["schema_version"] != 1
            or c.get("simulated_only") is not True
            or type(c.get("real_operation_claim")) is not bool
            or type(c.get("stop_release_claim")) is not bool):
        return False
    surfaces = c.get("publication_surfaces")
    if type(surfaces) is not list or len(surfaces) != len(_SURFACES):
        return False
    for i, s in enumerate(surfaces):
        if (type(s) is not dict or set(s) != _SURFACE
                or s.get("surface") != _SURFACES[i]
                or not _public_json_valid(s.get("public_json"))
                or any(type(s.get(k)) is not bool for k in (
                    "private_payload_present", "private_export_requested",
                    "real_scan_claim"))):
            return False
    t = c.get("transition")
    if (type(t) is not dict or set(t) != _TRANSITION
            or t.get("origin") != "SYNTHETIC_ONLY"
            or type(t.get("schema_version")) is not int or t["schema_version"] != 1
            or type(t.get("event")) is not str or t["event"] not in _EVENTS
            or any(type(t.get(k)) is not str or _ISSUER.fullmatch(t[k]) is None
                   for k in ("prior_issuer", "next_issuer"))
            or type(t.get("prior_key_state")) is not str
            or t["prior_key_state"] not in _KEY_STATES
            or type(t.get("next_key_state")) is not str
            or t["next_key_state"] not in _KEY_STATES
            or any(type(t.get(k)) is not int or not 0 <= t[k] <= 1000000
                   for k in ("prior_generation", "next_generation",
                             "prior_sequence", "next_sequence",
                             "simulated_reference_tick", "observed_tick"))
            or any(type(t.get(k)) is not int or not 1 <= t[k] <= 1000000
                   for k in ("prior_epoch", "next_epoch"))
            or any(type(t.get(k)) is not bool for k in (
                "revocation_before", "revocation_after", "stop_latched",
                *_REAL_CLAIMS))):
        return False
    return True


def _child_safe(r: object) -> bool:
    return (
        type(r) is dict
        and type(r.get("status")) is str and type(r.get("d533_status")) is str
        and type(r.get("effective_approved_actions")) is list
        and r["effective_approved_actions"] == []
        and r.get("safety_hold_latched") is True
        and r.get("phase_1") == "BLOCKED"
        and r.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in r and r["verified_values"] is None
        and r.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(r.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(r.get(k) is False for k in _D534_FALSE)
        and set(r) == set(_D534_FALSE) | {
            "status", "d533_status", "safety_hold_latched",
            "effective_approved_actions", "account_identity_consistency",
            "current_positions", "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d535_handoff(
    contract: object, d534_contract: object, d533_contract: object,
    d532_contract: object, d531_contract: object,
    old_evidence: object, gap_matrix: object,
    d532_fixture: object, d533_case: object,
    d534_case: object, synthetic_case: object,
) -> dict[str, object]:
    """Validate mock evidence requirements, never release a stop or authorize I/O."""
    try:
        if not _valid_contract(contract):
            return _deny("D535_CONTRACT_REJECTED_FAIL_CLOSED")
        if not _valid_case(synthetic_case):
            return _deny("D535_CASE_REJECTED_FAIL_CLOSED")
        upstream = review_d534_lineage(
            d534_contract, d533_contract, d532_contract, d531_contract,
            old_evidence, gap_matrix, d532_fixture, d533_case, d534_case,
        )
        if not _child_safe(upstream):
            return _deny("D535_CHILD_SAFETY_INVARIANT_REJECTED_FAIL_CLOSED")
        prior = upstream["status"]
        if prior != "D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED":
            return _deny("D535_PREDECESSOR_NOT_COHERENT_NO_GO", prior)
        if synthetic_case["real_operation_claim"] or synthetic_case["stop_release_claim"]:
            return _deny("D535_OPERATION_CLAIM_DENIED_NO_GO", prior)
        surfaces = synthetic_case["publication_surfaces"]
        if any(s["private_payload_present"] or s["private_export_requested"]
               or s["real_scan_claim"] for s in surfaces):
            return _deny("D535_G2_PRIVATE_PUBLICATION_DENIED_NO_GO", prior)
        if (type(d534_case) is not dict or type(d533_case) is not dict
                or any(s["public_json"] != d534_case["public_export"]["public_json"]
                       or s["public_json"] != d533_case["public_json"] for s in surfaces)):
            return _deny("D535_G2_PUBLIC_SURFACE_MISMATCH_NO_GO", prior)
        t = synthetic_case["transition"]
        if any(t[k] for k in _REAL_CLAIMS):
            return _deny("D535_G6_FALSE_REAL_PROOF_CLAIM_NO_GO", prior)
        if not t["stop_latched"]:
            return _deny("D535_G6_STOP_LATCH_LOST_NO_GO", prior)
        if t["revocation_before"] and not t["revocation_after"]:
            return _deny("D535_G6_REVOCATION_ERASURE_NO_GO", prior)
        lineage = d534_case["lineage"]
        journal = lineage["journal"]
        if (t["prior_issuer"] != lineage["previous_issuer_id"]
                or t["prior_epoch"] != lineage["previous_issuer_epoch"]
                or t["prior_generation"] != journal["generation"]
                or t["prior_sequence"] != journal["sequence"]
                or t["revocation_before"] != journal["revocation_tombstone"]):
            return _deny("D535_G6_PREDECESSOR_SCOPE_MISMATCH_NO_GO", prior)
        if (t["next_epoch"] < t["prior_epoch"]
                or t["next_generation"] < t["prior_generation"]
                or t["next_sequence"] < t["prior_sequence"]):
            return _deny("D535_G6_EPOCH_OR_SEQUENCE_ROLLBACK_NO_GO", prior)
        if t["event"] == "ROTATION":
            return _deny("D535_G6_UNVERIFIED_ISSUER_ROTATION_NO_GO", prior)
        if t["event"] in ("KEY_REVOCATION", "EMERGENCY_STOP"):
            return _deny("D535_G6_REVOCATION_EVENT_UNVERIFIED_NO_GO", prior)
        if (t["prior_issuer"] != t["next_issuer"]
                or t["prior_epoch"] != t["next_epoch"]):
            return _deny("D535_G6_UNDECLARED_ISSUER_CHANGE_NO_GO", prior)
        if t["prior_key_state"] != "SYNTHETIC_UNVERIFIED":
            return _deny("D535_G6_PRIOR_KEY_STATE_UNTRUSTED_NO_GO", prior)
        if t["next_key_state"] != t["prior_key_state"]:
            return _deny("D535_G6_KEY_STATE_CHANGE_UNVERIFIED_NO_GO", prior)
        if (t["next_generation"] != t["prior_generation"]
                or t["next_sequence"] != t["prior_sequence"]
                or t["revocation_after"] != t["revocation_before"]):
            return _deny("D535_G6_UNPINNED_LINEAGE_ADVANCE_NO_GO", prior)
        tick = lineage["simulated_reference_tick"]
        if t["simulated_reference_tick"] != tick:
            return _deny("D535_G6_SYNTHETIC_TICK_SCOPE_MISMATCH_NO_GO", prior)
        if (t["observed_tick"] > tick
                or tick - t["observed_tick"] > 5):
            return _deny("D535_G6_SYNTHETIC_TICK_UNTRUSTED_NO_GO", prior)
        return _deny("D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED", prior)
    except Exception:
        return _deny("D535_INPUT_EXCEPTION_FAIL_CLOSED")
