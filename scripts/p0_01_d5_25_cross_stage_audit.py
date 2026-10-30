"""D5-25: read-only synthetic cross-stage diagnostic, NEVER runtime authorization.

Recompute five historical denial-only gates independently, compare their
reported statuses and synthetic account scopes, and fail closed on contradictions.
No MT4/broker/network/filesystem/clock access, no order or approval operations.
"""
from __future__ import annotations

from scripts.p0_01_d5_19_integrated_no_go import evaluate_offline_integrated_no_go
from scripts.p0_01_d5_21_authority_audit import audit_offline_authority_separation
from scripts.p0_01_d5_22_approval_lifecycle import audit_synthetic_approval_lifecycle
from scripts.p0_01_d5_23_history_checkpoint import audit_synthetic_history_checkpoint
from scripts.p0_01_d5_24_reference_fault_gate import audit_synthetic_reference_and_failures

_KEYS = frozenset(("origin", "schema_version", "anchor_fixture"))
_ACTIONS = frozenset((
    "VISUAL_REVIEW", "MT4_LAUNCH", "ACCOUNT_LOGIN", "READ_ONLY_QUERY",
    "EA_EXECUTION", "ORDER_ACTION", "STOP_RELEASE", "LIVE_TRADING",
))
_STAGES = ("integrated", "authority", "lifecycle", "history", "anchor")
_ALLOWED = {
    "integrated": frozenset((
        "INTEGRATED_INPUT_REJECTED_FAIL_CLOSED",
        "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED",
        "INTEGRATED_STALE_STOP_RECORD_FAIL_CLOSED",
        "INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED",
        "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO",
        "INTEGRATED_EVIDENCE_BLOCKED_NO_GO",
        "INTEGRATED_EVIDENCE_TIME_MISMATCH_NO_GO",
        "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED",
    )),
    "authority": frozenset((
        "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED",
        "EVIDENCE_OR_STOP_BLOCKED_NO_GO",
        "STOP_RELEASE_CLAIM_DENIED_NO_GO",
        "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO",
        "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO",
    )),
    "lifecycle": frozenset((
        "LIFECYCLE_INPUT_REJECTED_FAIL_CLOSED",
        "LIFECYCLE_PROPOSED_NO_GO",
        "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO",
        "LIFECYCLE_REVOKED_NO_GO",
        "LIFECYCLE_EXPIRED_NO_GO",
        "LIFECYCLE_SCOPE_MISMATCH_NO_GO",
    )),
    "history": frozenset((
        "HISTORY_INPUT_REJECTED_FAIL_CLOSED",
        "HISTORY_LIFECYCLE_REJECTED_FAIL_CLOSED",
        "HISTORY_CHAIN_MISMATCH_NO_GO",
        "HISTORY_ROLLBACK_DETECTED_NO_GO",
        "HISTORY_CHECKPOINT_MISMATCH_NO_GO",
        "HISTORY_CHECKPOINT_STALE_NO_GO",
        "HISTORY_DOWNSTREAM_REJECTED_FAIL_CLOSED",
        "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO",
    )),
    "anchor": frozenset((
        "ANCHOR_INPUT_REJECTED_FAIL_CLOSED",
        "ANCHOR_STORAGE_UNCERTAIN_NO_GO",
        "ANCHOR_CONTINUITY_UNTRUSTED_NO_GO",
        "ANCHOR_REFERENCE_GENERATION_ROLLBACK_NO_GO",
        "ANCHOR_HISTORY_BLOCKED_NO_GO",
        "ANCHOR_RECORD_MISMATCH_NO_GO",
        "ANCHOR_HISTORY_ROLLBACK_NO_GO",
        "ANCHOR_REFERENCE_STALE_NO_GO",
        "ANCHOR_REVOCATION_MISMATCH_NO_GO",
        "ANCHOR_HEAD_MISMATCH_NO_GO",
        "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO",
    )),
}
_COMMON_BOOL_DENIED = (
    "broker_verified", "production_usable", "orders_generated",
    "read_only_ex4_execution_approved", "terminal_execution_approved",
    "forward_trading_enabled",
)
_AUTHORITY_BOOL_DENIED = (
    "approval_verified", "action_authorized", "ea_execution_authorized",
    "order_authorized", "stop_release_authorized",
)
_ANCHOR_BOOL_DENIED = (
    "reference_authentic", "revocation_persisted",
    "trusted_clock_verified", "actual_replay_protection",
)


def _result(status: str, statuses: dict[str, str] | None = None) -> dict[str, object]:
    stages = statuses or {}
    return {
        "status": status,
        "integrated_status": stages.get("integrated", "NOT_EVALUATED"),
        "authority_status": stages.get("authority", "NOT_EVALUATED"),
        "lifecycle_status": stages.get("lifecycle", "NOT_EVALUATED"),
        "history_status": stages.get("history", "NOT_EVALUATED"),
        "anchor_status": stages.get("anchor", "NOT_EVALUATED"),
        "account_scope_verified": False,
        "history_authentic": False,
        "trust_anchor_verified": False,
        "actual_replay_protection": False,
        "approval_verified": False,
        "action_authorized": False,
        "ea_execution_authorized": False,
        "order_authorized": False,
        "stop_release_authorized": False,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
        "broker_verified": False,
        "production_usable": False,
        "orders_generated": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "forward_trading_enabled": False,
    }


def _denial_contract(stage: str, obj: object) -> bool:
    if type(obj) is not dict or obj.get("status") not in _ALLOWED[stage]:
        return False
    expected: dict[str, object] = {
        "safety_hold_latched": True, "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO", "verified_values": None,
    }
    expected.update({key: False for key in _COMMON_BOOL_DENIED})
    if stage != "integrated":
        expected.update({key: False for key in _AUTHORITY_BOOL_DENIED})
        expected["effective_approved_actions"] = []
    if stage == "anchor":
        expected.update({key: False for key in _ANCHOR_BOOL_DENIED})
    for key, value in expected.items():
        if key not in obj or obj[key] != value:
            return False
        if type(value) is bool and type(obj[key]) is not bool:
            return False
        if type(value) is list and type(obj[key]) is not list:
            return False
    if stage == "integrated" and type(obj.get("daily_stop_latched")) is not bool:
        return False
    return True


def _synthetic_claim(lifecycle: object) -> dict[str, object] | None:
    if type(lifecycle) is not dict or type(lifecycle.get("request")) is not dict:
        return None
    action = lifecycle["request"].get("action")
    if type(action) is not str or action not in _ACTIONS:
        return None
    events = lifecycle.get("events")
    if type(events) is not list:
        return None
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "requested_action": action,
        "claimed_human_approval": any(
            type(e) is dict and e.get("event_type") == "APPROVAL_CLAIMED"
            for e in events
        ),
        "claimed_safety_review_passed": False,
        "claimed_stop_release": False,
        "approval_reference": None,
    }


def audit_synthetic_cross_stage_no_go(payload: object) -> dict[str, object]:
    """Audit synthetic evidence, stops, approvals, history and reference.

    Stage status agreement and account scope agreement are ONLY classifications,
    never evidence of real-world authenticity, human approval or trade permission.
    """
    rejected = _result("CROSS_STAGE_INPUT_REJECTED_FAIL_CLOSED")
    if (type(payload) is not dict or set(payload) != _KEYS
            or payload.get("origin") != "SYNTHETIC_ONLY"
            or type(payload.get("schema_version")) is not int
            or payload["schema_version"] != 1):
        return rejected
    try:
        anchor_fixture = payload["anchor_fixture"]
        if type(anchor_fixture) is not dict:
            return rejected
        history_bundle = anchor_fixture["history_bundle"]
        if type(history_bundle) is not dict:
            return rejected
        lifecycle = history_bundle["lifecycle"]
        integrated_fixture = history_bundle["integrated_fixture"]
        if type(lifecycle) is not dict or type(integrated_fixture) is not dict:
            return rejected
        integrated = evaluate_offline_integrated_no_go(integrated_fixture)
        authority = audit_offline_authority_separation(
            integrated_fixture, _synthetic_claim(lifecycle)
        )
        lifecycle_result = audit_synthetic_approval_lifecycle(lifecycle)
        history = audit_synthetic_history_checkpoint(history_bundle)
        anchor = audit_synthetic_reference_and_failures(anchor_fixture)
        outputs = {
            "integrated": integrated,
            "authority": authority,
            "lifecycle": lifecycle_result,
            "history": history,
            "anchor": anchor,
        }
        statuses = {
            name: obj["status"] if type(obj) is dict
            and type(obj.get("status")) is str else "INVALID"
            for name, obj in outputs.items()
        }
        if not all(_denial_contract(name, outputs[name]) for name in _STAGES):
            return _result("CROSS_STAGE_CHILD_CONTRACT_REJECTED_FAIL_CLOSED",
                           statuses)

        # Detect contradictory "coherent" summaries without relying on any
        # child report of real authentication or runtime permission.
        if (authority["status"] != "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED"
                and authority.get("integrated_status") != integrated["status"]):
            return _result("CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO", statuses)
        if (history["status"] == "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO"
                and history.get("lifecycle_status") != lifecycle_result["status"]):
            return _result("CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO", statuses)
        if (anchor["status"] == "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO"
                and anchor.get("history_status") != history["status"]):
            return _result("CROSS_STAGE_STATUS_DISAGREEMENT_NO_GO", statuses)

        # The D5-22 record/terminal labels are synthetic, and D5-19 snapshots
        # do not bind a real account or terminal. Only reject obvious clashes.
        if integrated_fixture.get("evidence_mode") != "SYNTHETIC_RECORDS":
            return _result("CROSS_STAGE_SCOPE_UNVERIFIED_NO_GO", statuses)
        evidence = integrated_fixture.get("evidence")
        record = lifecycle.get("record")
        if type(evidence) is not dict or type(record) is not dict:
            return _result("CROSS_STAGE_SCOPE_UNVERIFIED_NO_GO", statuses)
        if (type(evidence.get("account_scope")) is not str
                or type(record.get("account_scope")) is not str):
            return _result("CROSS_STAGE_SCOPE_UNVERIFIED_NO_GO", statuses)
        if evidence["account_scope"] != record["account_scope"]:
            return _result("CROSS_STAGE_SCOPE_MISMATCH_NO_GO", statuses)

        coherent = (
            integrated["status"] == "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED"
            and lifecycle_result["status"] in (
                "LIFECYCLE_PROPOSED_NO_GO",
                "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO",
                "LIFECYCLE_REVOKED_NO_GO",
                "LIFECYCLE_EXPIRED_NO_GO",
            )
            and history["status"] == "HISTORY_SYNTHETIC_CHAIN_CONSISTENT_NO_GO"
            and anchor["status"] == "ANCHOR_SYNTHETIC_REFERENCE_MATCH_NO_GO"
            and authority["status"] in (
                "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO",
                "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO",
                "STOP_RELEASE_CLAIM_DENIED_NO_GO",
            )
        )
        return _result(
            "CROSS_STAGE_SYNTHETIC_COHERENT_NEVER_AUTHORIZED"
            if coherent else "CROSS_STAGE_BLOCKED_NO_GO",
            statuses,
        )
    except Exception:
        return rejected
