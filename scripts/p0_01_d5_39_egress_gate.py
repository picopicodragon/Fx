"""P0-01 D5-39: G2-07 synthetic Git/PR/CI egress boundary, deny-only.

This is NOT a Git hook, CI secret scanner, real egress filter, vault, or
security certification. All caller-supplied objects are untrusted; this
module never reads files, uses network/OS APIs, or exposes submitted payloads.
"""
from __future__ import annotations

from scripts.p0_01_d5_32_crash_matrix_privacy import _public_json_valid
from scripts.p0_01_d5_38_private_vault_review import (
    _FALSE as _D538_FALSE, review_d538_private_vault,
)

_CHANNELS = (
    "GIT_STAGE", "COMMIT_DIFF", "PULL_REQUEST_BODY",
    "PULL_REQUEST_COMMENT", "CI_JOB_LOG", "CI_ARTIFACT",
    "RELEASE_ASSET", "GIT_HISTORY",
)
_PLAN_KEYS = frozenset((
    "origin", "schema_version", "scope", "target_criterion",
    "depends_on", "external_gate_dependencies", "channels",
    "allowed_candidate_kind", "allowed_data_class", "review_mode",
    "real_guard_implemented", "real_git_hook_installed",
    "real_ci_scan_installed", "real_history_scanned",
    "real_public_export_approved", "real_private_export_approved",
    "actual_leakage_ruled_out", "phase_1", "runtime_go_no_go",
    "verified_values",
))
_MANIFEST_KEYS = frozenset((
    "origin", "schema_version", "scope", "public_json", "items",
    "simulation_only", "real_host_io_requested",
    "real_mt4_access_requested", "real_private_evidence_collection_requested",
    "real_stop_release_requested", "real_trade_requested",
    "account_identity_consistency", "current_positions",
    "current_pending_orders", "current_ea_state", "unresolved_gates",
    "safety_hold_latched",
))
_ITEM_KEYS = frozenset((
    "channel", "data_class", "candidate_kind", "review_state",
    "actual_egress_requested", "private_data_attached",
    "scanner_claim_verified", "hook_claim_installed",
    "real_publication_verified", "destination", "observed_at_utc",
))
_ALLOWED_CLASS = "SYNTHETIC_PUBLIC_METADATA"
_CLASSES = ("SYNTHETIC_PUBLIC_METADATA", "ACCOUNT_TERMINAL_IDENTIFIERS",
            "BROKER_SESSION_AND_SERVER", "EA_POSITION_ORDER_EVIDENCE",
            "RAW_LOG_AND_SCREENSHOT", "SECRET_MATERIAL",
            "OBSERVATION_PROVENANCE")
_KINDS = ("FIXED_CANONICAL_JSON", "RAW_TEXT", "SCREENSHOT",
          "LOG_CHUNK", "BINARY_ARTIFACT", "METADATA_WITH_EXTRA_FIELDS")
_DESTINATIONS = ("DENY_REAL_EGRESS", "GIT_REPOSITORY", "PR_PUBLIC",
                 "CI_LOG_PUBLIC", "CI_ARTIFACT_PUBLIC", "RELEASE_PUBLIC")
_PARENT_KEYS = (
    "d538_design", "d538_threat_matrix", "d537_workplan", "d537_tracking",
    "d536_contract", "d536_readiness", "d536_actions", "d536_predecessors",
)
_FALSE = (*_D538_FALSE,
          "g2_07_real_git_hook_enforced",
          "g2_07_real_pr_metadata_scanned",
          "g2_07_real_ci_artifact_scanned",
          "g2_07_real_history_scanned",
          "g2_07_real_secret_leak_absence_proven",
          "g2_07_actual_public_export_authorized",
          "g2_07_real_private_export_authorized",
          "g2_07_actual_release_guard_verified")


def _deny(status: str, upstream: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {k: False for k in _FALSE}
    result.update({
        "status": status, "d538_status": upstream,
        "synthetic_egress_surfaces": len(_CHANNELS),
        "real_egress_surfaces_scanned": 0,
        "real_evidence_items_collected": 0,
        "real_work_packages_executed": 0,
        "real_acceptance_criteria_completed": 0,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "account_identity_consistency": "NOT_RECONCILED",
        "current_positions": "UNKNOWN", "current_pending_orders": "UNKNOWN",
        "current_ea_state": "UNKNOWN",
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _valid_policy(p: object) -> bool:
    return (
        type(p) is dict and set(p) == _PLAN_KEYS
        and p.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(p.get("schema_version")) is int and p["schema_version"] == 1
        and p.get("scope") == "D539_G2_07_EGRESS_MANIFEST_DESIGN_ONLY"
        and p.get("target_criterion") == "G2-07"
        and p.get("depends_on") == ["G2-06"]
        and p.get("external_gate_dependencies") == ["G8"]
        and p.get("channels") == list(_CHANNELS)
        and p.get("allowed_candidate_kind") == "FIXED_CANONICAL_JSON"
        and p.get("allowed_data_class") == _ALLOWED_CLASS
        and p.get("review_mode") == "NO_REAL_EGRESS"
        and all(p.get(k) is False for k in (
            "real_guard_implemented", "real_git_hook_installed",
            "real_ci_scan_installed", "real_history_scanned",
            "real_public_export_approved", "real_private_export_approved",
            "actual_leakage_ruled_out"))
        and p.get("phase_1") == "BLOCKED"
        and p.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in p and p["verified_values"] is None
    )


def _manifest_shape_valid(m: object) -> bool:
    if not (
        type(m) is dict and set(m) == _MANIFEST_KEYS
        and m.get("origin") == "SYNTHETIC_ONLY"
        and type(m.get("schema_version")) is int and m["schema_version"] == 1
        and m.get("scope") == "D539_SYNTHETIC_MANIFEST_NOT_ACTUAL_GIT_CONTENT"
        and _public_json_valid(m.get("public_json"))
        and m.get("simulation_only") is True
        and m.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(m.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and m.get("unresolved_gates") == [f"G{i}" for i in range(1, 10)]
        and m.get("safety_hold_latched") is True
        and all(type(m.get(k)) is bool for k in (
            "real_host_io_requested", "real_mt4_access_requested",
            "real_private_evidence_collection_requested",
            "real_stop_release_requested", "real_trade_requested"))
    ):
        return False
    items = m.get("items")
    if type(items) is not list or len(items) != len(_CHANNELS):
        return False
    for item, channel in zip(items, _CHANNELS):
        if not (
            type(item) is dict and set(item) == _ITEM_KEYS
            and item.get("channel") == channel
            and type(item.get("data_class")) is str
            and item["data_class"] in _CLASSES
            and type(item.get("candidate_kind")) is str
            and item["candidate_kind"] in _KINDS
            and item.get("review_state") == "DESIGN_PENDING"
            and type(item.get("destination")) is str
            and item["destination"] in _DESTINATIONS
            and all(type(item.get(k)) is bool for k in (
                "actual_egress_requested", "private_data_attached",
                "scanner_claim_verified", "hook_claim_installed",
                "real_publication_verified"))
            and "observed_at_utc" in item and item["observed_at_utc"] is None
        ):
            return False
    return True


def _parent_safe(child: object) -> bool:
    return (
        type(child) is dict
        and type(child.get("status")) is str
        and type(child.get("d537_status")) is str
        and type(child.get("g2_06_design_threats_documented")) is int
        and child["g2_06_design_threats_documented"] == 12
        and all(type(child.get(k)) is int and child[k] == 0 for k in (
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed"))
        and type(child.get("effective_approved_actions")) is list
        and child["effective_approved_actions"] == []
        and child.get("safety_hold_latched") is True
        and child.get("phase_1") == "BLOCKED"
        and child.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in child and child["verified_values"] is None
        and child.get("account_identity_consistency") == "NOT_RECONCILED"
        and all(child.get(k) == "UNKNOWN" for k in (
            "current_positions", "current_pending_orders", "current_ea_state"))
        and all(child.get(k) is False for k in _D538_FALSE)
        and set(child) == set(_D538_FALSE) | {
            "status", "d537_status", "g2_06_design_threats_documented",
            "real_evidence_items_collected", "real_work_packages_executed",
            "real_acceptance_criteria_completed",
            "effective_approved_actions", "safety_hold_latched",
            "account_identity_consistency", "current_positions",
            "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        }
    )


def review_d539_egress(
    contract: object, manifest: object,
    expected_public_json: object, predecessor_bundle: object,
) -> dict[str, object]:
    """Review synthetic egress descriptions; NEVER publish even clean metadata."""
    try:
        if not _valid_policy(contract):
            return _deny("D539_POLICY_REJECTED_FAIL_CLOSED")
        if not _manifest_shape_valid(manifest):
            return _deny("D539_MANIFEST_SCHEMA_REJECTED_FAIL_CLOSED")
        if any(manifest[k] for k in (
            "real_host_io_requested", "real_mt4_access_requested",
            "real_private_evidence_collection_requested",
            "real_stop_release_requested", "real_trade_requested")):
            return _deny("D539_REAL_OPERATION_REQUEST_DENIED_NO_GO")
        for item in manifest["items"]:
            if item["data_class"] != _ALLOWED_CLASS or item["private_data_attached"]:
                return _deny("D539_PRIVATE_CLASS_OR_ATTACHMENT_DENIED_NO_GO")
            if item["candidate_kind"] != "FIXED_CANONICAL_JSON":
                return _deny("D539_NON_CANONICAL_CONTENT_TYPE_DENIED_NO_GO")
            if item["actual_egress_requested"] or item["destination"] != "DENY_REAL_EGRESS":
                return _deny("D539_REAL_EGRESS_REQUEST_DENIED_NO_GO")
            if (item["scanner_claim_verified"] or item["hook_claim_installed"]
                    or item["real_publication_verified"]):
                return _deny("D539_FALSE_REAL_GUARD_CLAIM_NO_GO")
        if not _public_json_valid(expected_public_json):
            return _deny("D539_REFERENCE_PUBLIC_JSON_REJECTED_FAIL_CLOSED")
        if manifest["public_json"] != expected_public_json:
            return _deny("D539_PUBLIC_METADATA_SCOPE_MISMATCH_NO_GO")
        if type(predecessor_bundle) is not dict or set(predecessor_bundle) != set(_PARENT_KEYS):
            return _deny("D539_PREDECESSOR_BUNDLE_REJECTED_FAIL_CLOSED")
        child = review_d538_private_vault(
            *(predecessor_bundle[k] for k in _PARENT_KEYS)
        )
        if not _parent_safe(child):
            return _deny("D539_PREDECESSOR_SAFETY_INVARIANT_FAIL_CLOSED")
        if child["status"] != "D538_VAULT_REQUIREMENTS_DESIGNED_NO_REAL_STORAGE_OR_ERASURE":
            return _deny("D539_PREDECESSOR_NOT_COHERENT_NO_GO", child["status"])
        return _deny("D539_SYNTHETIC_EGRESS_MANIFEST_COHERENT_NO_REAL_EGRESS",
                     child["status"])
    except Exception:
        return _deny("D539_INPUT_EXCEPTION_FAIL_CLOSED")
