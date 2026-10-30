"""D5-29: G2 evidence pre-acceptance + G6 restoration checkpoint comparison.

Pure synthetic design audit. All input references, clocks, receipts and status
flags are UNTRUSTED caller claims; none are real proof. No disk, MT4, broker,
network, OS clock, signatures, approvals, or order execution.
"""
from __future__ import annotations

import re
from scripts.p0_01_d5_27_g2_g6_offline_preflight import _original_evidence_is_unverified
from scripts.p0_01_d5_28_acceptance_criteria import audit_d528_acceptance_design

_TOP = frozenset(("origin", "schema_version", "acceptance_case",
                  "evidence_envelopes", "restoration"))
_CONTRACT = frozenset(("origin", "schema_version", "g2_source_ids",
                      "g6_acceptance_ids", "scope", "no_real_verification",
                      "phase_1", "runtime_go_no_go", "verified_values"))
_ENV = frozenset(("report_id", "source_kind", "account_token", "terminal_token",
                  "observed_at_utc", "recorded_at_utc", "provenance_attested",
                  "account_attested", "real_world_verified", "synthetic_only"))
_RESTORE = frozenset(("origin", "schema_version", "baseline", "restored",
                      "write_state", "read_state", "clock_state",
                      "writer_state", "revocation_index_state",
                      "fault_injected", "simulated_stop_release_claim",
                      "simulated_only"))
_SNAPSHOT = frozenset(("record_id", "generation", "sequence",
                       "head_hash", "revocation_tombstone", "stop_latched"))
_SOURCE_TYPES = ("PRIOR_USER_VISUAL_REPORT", "LATEST_USER_REPORTED")
_G6_THREATS = (
    "ATOMIC_COMMIT_TORN", "POWER_LOSS_MID_WRITE", "REFERENCE_ROLLBACK",
    "CO_EDIT_ALL_REFERENCES", "REVOCATION_ERASURE", "CONCURRENT_WRITER",
    "CLOCK_RESTART_OR_ANOMALY", "SIGNATURE_KEY_TAMPER",
    "STORAGE_UNAVAILABLE", "STALE_BACKUP_RESTORE",
)
_CHILD_ALLOWED = frozenset((
    "D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO",
    "D528_G2_SYNTHETIC_SCOPE_MISMATCH_NO_GO",
    "D528_G2_SYNTHETIC_TIME_MISMATCH_NO_GO",
    "D528_G2_SYNTHETIC_REPORT_CONFLICT_NO_GO",
    "D528_G2_SYNTHETIC_UNKNOWN_NO_GO",
    "D528_G6_UNTRUSTED_OR_FAULT_NO_GO",
    "D528_RELEASE_CLAIM_DENIED_NO_GO",
    "D528_CASE_REJECTED_FAIL_CLOSED",
))
_CHILD_FALSE = (
    "g2_real_world_resolved", "g6_real_world_resolved",
    "evidence_provenance_authenticated", "account_identity_verified",
    "positions_verified", "pending_orders_verified", "ea_state_verified",
    "trusted_clock_verified", "trusted_anchor_verified",
    "atomic_persistence_verified", "revocation_durable_verified",
    "real_transition_authorized", "visual_review_approved",
    "mt4_launch_approved", "mt4_read_only_approved", "host_io_approved",
    "approval_verified", "action_authorized", "ea_execution_authorized",
    "order_authorized", "stop_release_authorized", "broker_verified",
    "production_usable", "read_only_ex4_execution_approved",
    "terminal_execution_approved", "orders_generated",
    "forward_trading_enabled",
)
_GOOD = "SYNTHETIC_CONFIRMED"
_STATE_SET = (_GOOD, "SYNTHETIC_FAILED", "SYNTHETIC_UNKNOWN")
_CLOCK_SET = ("SYNTHETIC_CLOCK_STABLE", "SYNTHETIC_CLOCK_ANOMALY",
              "SYNTHETIC_UNKNOWN")
_WRITER_SET = ("SYNTHETIC_SINGLE_WRITER", "SYNTHETIC_CONFLICT",
               "SYNTHETIC_UNKNOWN")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"SYNTHETIC_RECORD_[A-Z0-9_]{1,32}\Z")


def _deny(status: str, child: str = "NOT_EVALUATED") -> dict[str, object]:
    result = {key: False for key in _CHILD_FALSE}
    result.update({
        "status": status, "d528_status": child,
        "g2_preacceptance_authenticated": False,
        "g6_restoration_verified": False,
        "g6_real_rollback_detected": False,
        "g6_real_revocation_persisted": False,
        "real_identity_reconciled": False,
        "restoration_authorized": False,
        "effective_approved_actions": [], "safety_hold_latched": True,
        "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    })
    return result


def _child_denied(value: object) -> bool:
    if type(value) is not dict or value.get("status") not in _CHILD_ALLOWED:
        return False
    for field in _CHILD_FALSE:
        if value.get(field) is not False:
            return False
    return (value.get("safety_hold_latched") is True
            and value.get("phase_1") == "BLOCKED"
            and value.get("runtime_go_no_go") == "NO_GO"
            and "verified_values" in value and value["verified_values"] is None
            and value.get("effective_approved_actions") == []
            and type(value["effective_approved_actions"]) is list)


def _design_valid(contract: object) -> bool:
    return (
        type(contract) is dict and set(contract) == _CONTRACT
        and contract.get("origin") == "OFFLINE_DESIGN_ONLY"
        and type(contract.get("schema_version")) is int
        and contract["schema_version"] == 1
        and contract.get("scope") == "G2_G6_SYNTHETIC_PREACCEPTANCE_ONLY"
        and contract.get("g2_source_ids") == ["EV-OLD", "EV-NEW"]
        and contract.get("g6_acceptance_ids") ==
            [f"G6-AC-{i:02d}" for i in range(1, 11)]
        and contract.get("no_real_verification") is True
        and contract.get("phase_1") == "BLOCKED"
        and contract.get("runtime_go_no_go") == "NO_GO"
        and "verified_values" in contract and contract["verified_values"] is None
    )


def _envelopes_valid(envs: object, records: object) -> bool:
    if (type(envs) is not list or len(envs) != 2 or
            type(records) is not list or len(records) != 2):
        return False
    for idx, (env, rec) in enumerate(zip(envs, records)):
        if (type(env) is not dict or set(env) != _ENV
                or type(rec) is not dict
                or env.get("report_id") != ("EV-OLD", "EV-NEW")[idx]
                or env.get("source_kind") != _SOURCE_TYPES[idx]
                or env.get("provenance_attested") is not False
                or env.get("account_attested") is not False
                or env.get("real_world_verified") is not False
                or env.get("synthetic_only") is not True):
            return False
        # Require schema provenance fields to agree with underlying mock record;
        # matching fields never provides *real* source authentication.
        for k in ("report_id", "account_token", "terminal_token",
                  "observed_at_utc", "recorded_at_utc"):
            if type(env.get(k)) is not str:
                return False
            if env[k] != rec.get(k):
                return False
    return True


def _snapshot_valid(snapshot: object) -> bool:
    return (
        type(snapshot) is dict and set(snapshot) == _SNAPSHOT
        and type(snapshot.get("record_id")) is str
        and _ID.fullmatch(snapshot["record_id"]) is not None
        and type(snapshot.get("generation")) is int
        and 1 <= snapshot["generation"] <= 1000000
        and type(snapshot.get("sequence")) is int
        and 0 <= snapshot["sequence"] <= 1000000
        and type(snapshot.get("head_hash")) is str
        and _HASH.fullmatch(snapshot["head_hash"]) is not None
        and type(snapshot.get("revocation_tombstone")) is bool
        and type(snapshot.get("stop_latched")) is bool
    )


def _restoration_valid(data: object) -> bool:
    return (
        type(data) is dict and set(data) == _RESTORE
        and data.get("origin") == "SYNTHETIC_ONLY"
        and type(data.get("schema_version")) is int
        and data["schema_version"] == 1
        and _snapshot_valid(data.get("baseline"))
        and _snapshot_valid(data.get("restored"))
        and all(type(data.get(k)) is str and data[k] in _STATE_SET
                for k in ("write_state", "read_state", "revocation_index_state"))
        and type(data.get("clock_state")) is str
        and data["clock_state"] in _CLOCK_SET
        and type(data.get("writer_state")) is str
        and data["writer_state"] in _WRITER_SET
        and type(data.get("fault_injected")) is str
        and data["fault_injected"] in ("NONE", *_G6_THREATS)
        and type(data.get("simulated_stop_release_claim")) is bool
        and data.get("simulated_only") is True
    )


def evaluate_d529_evidence_restore(
    contract: object, source_ledger: object, d528_contract: object,
    payload: object,
) -> dict[str, object]:
    """Fail-closed cross-stage checker. All values are mock/untrusted."""
    try:
        if not _design_valid(contract):
            return _deny("D529_DESIGN_REJECTED_FAIL_CLOSED")
        if not _original_evidence_is_unverified(source_ledger):
            return _deny("D529_SOURCE_BASELINE_REJECTED_FAIL_CLOSED")
        if (type(payload) is not dict or set(payload) != _TOP
                or payload.get("origin") != "SYNTHETIC_ONLY"
                or type(payload.get("schema_version")) is not int
                or payload["schema_version"] != 1):
            return _deny("D529_INPUT_REJECTED_FAIL_CLOSED")
        case = payload["acceptance_case"]
        child = audit_d528_acceptance_design(d528_contract, case)
        if not _child_denied(child):
            return _deny("D529_CHILD_CONTRACT_REJECTED_FAIL_CLOSED")
        status = child["status"]
        if status == "D528_CASE_REJECTED_FAIL_CLOSED":
            return _deny("D529_EVIDENCE_CASE_REJECTED_FAIL_CLOSED", status)
        if not _envelopes_valid(payload["evidence_envelopes"],
                                case["g2_records"]):
            return _deny("D529_PROVENANCE_LINK_REJECTED_FAIL_CLOSED", status)
        restore = payload["restoration"]
        if not _restoration_valid(restore):
            return _deny("D529_RESTORE_INPUT_REJECTED_FAIL_CLOSED", status)
        if restore["simulated_stop_release_claim"]:
            return _deny("D529_STOP_RELEASE_CLAIM_DENIED_NO_GO", status)
        if (restore["fault_injected"] != "NONE"
                or any(restore[k] != _GOOD for k in
                       ("write_state", "read_state", "revocation_index_state"))
                or restore["clock_state"] != "SYNTHETIC_CLOCK_STABLE"
                or restore["writer_state"] != "SYNTHETIC_SINGLE_WRITER"):
            return _deny("D529_RESTORE_UNCERTAIN_NO_GO", status)
        a, b = restore["baseline"], restore["restored"]
        if a["stop_latched"] is not True or b["stop_latched"] is not True:
            return _deny("D529_STOP_LATCH_LOSS_NO_GO", status)
        if a["record_id"] != b["record_id"]:
            return _deny("D529_RESTORE_SCOPE_MISMATCH_NO_GO", status)
        if (b["generation"] < a["generation"]
                or b["sequence"] < a["sequence"]):
            return _deny("D529_RESTORE_ROLLBACK_NO_GO", status)
        if (a["revocation_tombstone"] is True
                and b["revocation_tombstone"] is False):
            return _deny("D529_REVOCATION_ERASURE_NO_GO", status)
        if a["revocation_tombstone"] != b["revocation_tombstone"]:
            return _deny("D529_REVOCATION_CHANGE_NO_GO", status)
        if (a["generation"] != b["generation"]
                or a["sequence"] != b["sequence"]):
            return _deny("D529_RESTORE_UNPINNED_ADVANCE_NO_GO", status)
        if a["head_hash"] != b["head_hash"]:
            return _deny("D529_RESTORE_HEAD_MISMATCH_NO_GO", status)
        if status != "D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO":
            return _deny("D529_EVIDENCE_NOT_PREACCEPTABLE_NO_GO", status)
        # Even exact matches are not authenticated, persisted or approved.
        return _deny("D529_SYNTHETIC_PREACCEPTANCE_MATCH_NEVER_AUTHORIZED", status)
    except Exception:
        return _deny("D529_INPUT_EXCEPTION_FAIL_CLOSED")
