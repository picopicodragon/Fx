"""D5-21: offline audit of approval, evidence, and stop-state separation.

This deliberately contains NO approval-verification machinery, credentials,
broker/MT4 interface, file I/O, clock reads, order path, or release operation.
A caller-supplied claim of human approval is NOT authenticated authority.
"""
from __future__ import annotations

import re

from scripts.p0_01_d5_19_integrated_no_go import (
    evaluate_offline_integrated_no_go,
)

_ACTIONS = frozenset((
    "VISUAL_REVIEW", "MT4_LAUNCH", "ACCOUNT_LOGIN", "READ_ONLY_QUERY",
    "EA_EXECUTION", "ORDER_ACTION", "STOP_RELEASE", "LIVE_TRADING",
))
_CLAIM_KEYS = frozenset((
    "origin", "schema_version", "requested_action",
    "claimed_human_approval", "claimed_safety_review_passed",
    "claimed_stop_release", "approval_reference",
))
_REFERENCE = re.compile(r"SYNTHETIC_APPROVAL_[A-Z0-9_]{1,24}\Z")
_COHERENT = "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED"


def _closed(status: str, integrated_status: str = "NOT_EVALUATED") -> dict[str, object]:
    """All audit outcomes are denial, including apparently valid fixtures."""
    return {
        "status": status,
        "integrated_status": integrated_status,
        "approval_verified": False,
        "action_authorized": False,
        "ea_execution_authorized": False,
        "order_authorized": False,
        "stop_release_authorized": False,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
        "broker_verified": False,
        "production_usable": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "orders_generated": False,
        "forward_trading_enabled": False,
        "phase_1": "BLOCKED",
    }


def _claim_is_well_formed(claim: object) -> bool:
    if type(claim) is not dict or set(claim) != _CLAIM_KEYS:
        return False
    if (claim.get("origin") != "SYNTHETIC_ONLY"
            or type(claim.get("schema_version")) is not int
            or claim["schema_version"] != 1
            or type(claim.get("requested_action")) is not str
            or claim["requested_action"] not in _ACTIONS):
        return False
    for key in ("claimed_human_approval", "claimed_safety_review_passed",
                "claimed_stop_release"):
        if type(claim.get(key)) is not bool:
            return False
    reference = claim.get("approval_reference")
    return (reference is None
            or type(reference) is str
            and _REFERENCE.fullmatch(reference) is not None)


def _integrated_output_is_closed(value: object) -> bool:
    """Reject any unexpected change to the D5-19 safety-output contract."""
    if type(value) is not dict:
        return False
    required = {
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
        "phase_1": "BLOCKED",
        "safety_hold_latched": True,
        "broker_verified": False,
        "production_usable": False,
        "orders_generated": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "forward_trading_enabled": False,
    }
    if (any(key not in value or value[key] != expected
            for key, expected in required.items())
            or any(type(value[key]) is not bool
                   for key in required
                   if isinstance(required[key], bool))
            or type(value.get("daily_stop_latched")) is not bool
            or type(value.get("status")) is not str):
        return False
    return True


def audit_offline_authority_separation(
    integrated_fixture: object, approval_claim: object,
) -> dict[str, object]:
    """Recompute the integrated gate; never trust a caller's cached status.

    Claims are intentionally synthetic, neither authenticated nor binding.
    There is no capability to convert a claim into real authorization.
    """
    invalid = _closed("AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
    if not _claim_is_well_formed(approval_claim):
        return invalid
    try:
        integrated = evaluate_offline_integrated_no_go(integrated_fixture)
        if not _integrated_output_is_closed(integrated):
            return invalid
        stage = integrated["status"]
        if stage != _COHERENT:
            return _closed("EVIDENCE_OR_STOP_BLOCKED_NO_GO", stage)
        if approval_claim["requested_action"] == "STOP_RELEASE" or approval_claim[
                "claimed_stop_release"]:
            return _closed("STOP_RELEASE_CLAIM_DENIED_NO_GO", stage)
        if (approval_claim["claimed_human_approval"]
                or approval_claim["claimed_safety_review_passed"]
                or approval_claim["approval_reference"] is not None):
            return _closed("UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO", stage)
        return _closed("EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO", stage)
    except Exception:
        return invalid
