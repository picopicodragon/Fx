"""D5-28: offline-only evidence format and G6 fault acceptance contract.

All fields are caller-supplied SYNTHETIC fixtures. Neither the schema nor
synthetic agreement authenticates an account, person, clock, disk or signature.
No filesystem, OS clock, network, MT4, broker or order access.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

_TOP = frozenset(("origin", "schema_version", "g2", "g6", "approvals",
                  "phase_1", "runtime_go_no_go", "verified_values"))
_G2_DESIGN = frozenset(("required_fields", "required_checks", "provenance_policy",
                        "identity_policy", "no_current_state_verified"))
_G6_DESIGN = frozenset(("acceptance", "no_real_storage", "independent_anchor_verified"))
_G6_ROW = frozenset(("id", "threat", "expected_status", "acceptance_id",
                     "future_real_test_required", "real_world_verified"))
_APPROVALS = frozenset(("visual_review", "mt4_launch", "account_login",
                        "mt4_read_only_query", "ea_execution", "order_action",
                        "stop_release", "host_io", "live_trading"))
_EVIDENCE_FIELDS = ("report_id", "provenance_class", "account_token",
                    "terminal_token", "observed_at_utc", "recorded_at_utc",
                    "positions", "pending_orders", "ea_attachment", "autotrading")
_TOP_CASE = frozenset(("origin", "schema_version", "g2_records",
                       "g6_scenario", "simulated_stop_release_claim"))
_RECORD = frozenset(_EVIDENCE_FIELDS)
_G6_CASE = frozenset(("threat", "persist_state", "anchor_state",
                      "revocation_state", "clock_state", "simulated_io_only"))
_G6_THREATS = (
    "ATOMIC_COMMIT_TORN", "POWER_LOSS_MID_WRITE", "REFERENCE_ROLLBACK",
    "CO_EDIT_ALL_REFERENCES", "REVOCATION_ERASURE", "CONCURRENT_WRITER",
    "CLOCK_RESTART_OR_ANOMALY", "SIGNATURE_KEY_TAMPER",
    "STORAGE_UNAVAILABLE", "STALE_BACKUP_RESTORE",
)
_EVIDENCE_STATES = frozenset(("ABSENT", "PRESENT", "UNKNOWN"))
_PERSIST = frozenset(("SYNTHETIC_CONSISTENT", "SYNTHETIC_FAULT", "SYNTHETIC_UNKNOWN"))
_ANCHOR = frozenset(("SYNTHETIC_MATCH", "SYNTHETIC_MISMATCH", "SYNTHETIC_UNKNOWN"))
_REVOCATION = frozenset(("SYNTHETIC_NO_REVOCATION", "SYNTHETIC_REVOKED",
                         "SYNTHETIC_ERASURE", "SYNTHETIC_UNKNOWN"))
_CLOCK = frozenset(("SYNTHETIC_STABLE", "SYNTHETIC_ANOMALY", "SYNTHETIC_UNKNOWN"))
_SYN_ID = re.compile(r"SYNTHETIC_[A-Z0-9_]{1,32}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def _deny(status: str) -> dict[str, object]:
    return {
        "status": status,
        "g2_real_world_resolved": False,
        "g6_real_world_resolved": False,
        "evidence_provenance_authenticated": False,
        "account_identity_verified": False,
        "positions_verified": False,
        "pending_orders_verified": False,
        "ea_state_verified": False,
        "trusted_clock_verified": False,
        "trusted_anchor_verified": False,
        "atomic_persistence_verified": False,
        "revocation_durable_verified": False,
        "real_transition_authorized": False,
        "visual_review_approved": False,
        "mt4_launch_approved": False,
        "mt4_read_only_approved": False,
        "host_io_approved": False,
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
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "orders_generated": False,
        "forward_trading_enabled": False,
    }


def _utc(value: object) -> datetime | None:
    if type(value) is not str or _TIME.fullmatch(value) is None:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc,
        )
        if dt.year < 2000 or dt.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
            return None
        return dt
    except (ValueError, OverflowError):
        return None


def _valid_design(design: object) -> bool:
    if (type(design) is not dict or set(design) != _TOP
            or design.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(design.get("schema_version")) is not int
            or design["schema_version"] != 1
            or design.get("phase_1") != "BLOCKED"
            or design.get("runtime_go_no_go") != "NO_GO"
            or design.get("verified_values", "MISSING") is not None):
        return False
    approvals = design.get("approvals")
    if (type(approvals) is not dict or set(approvals) != _APPROVALS
            or any(v is not False for v in approvals.values())):
        return False
    g2 = design.get("g2")
    if (type(g2) is not dict or set(g2) != _G2_DESIGN
            or g2.get("required_fields") != list(_EVIDENCE_FIELDS)
            or g2.get("required_checks") != [
                "PROVENANCE", "SCOPE", "CHRONOLOGY", "POSITIONS",
                "PENDING_ORDERS", "EA_ATTACHMENT", "AUTOTRADING",
            ]
            or g2.get("provenance_policy") != "UNTRUSTED_SYNTHETIC_ONLY"
            or g2.get("identity_policy") != "NO_REAL_ACCOUNT_IDENTIFIER_IN_GIT"
            or g2.get("no_current_state_verified") is not True):
        return False
    g6 = design.get("g6")
    if (type(g6) is not dict or set(g6) != _G6_DESIGN
            or g6.get("no_real_storage") is not True
            or g6.get("independent_anchor_verified") is not False):
        return False
    rows = g6.get("acceptance")
    if type(rows) is not list or len(rows) != len(_G6_THREATS):
        return False
    for idx, row in enumerate(rows):
        if (type(row) is not dict or set(row) != _G6_ROW
                or row.get("id") != f"P28-G6-{idx+1:02d}"
                or row.get("acceptance_id") != f"G6-AC-{idx+1:02d}"
                or row.get("threat") != _G6_THREATS[idx]
                or row.get("expected_status") != "SAFETY_HOLD_LATCHED_NO_GO"
                or row.get("future_real_test_required") is not True
                or row.get("real_world_verified") is not False):
            return False
    return True


def _valid_case(case: object) -> bool:
    if (type(case) is not dict or set(case) != _TOP_CASE
            or case.get("origin") != "SYNTHETIC_ONLY"
            or type(case.get("schema_version")) is not int
            or case["schema_version"] != 1
            or type(case.get("simulated_stop_release_claim")) is not bool):
        return False
    records = case.get("g2_records")
    if type(records) is not list or len(records) != 2:
        return False
    for i, item in enumerate(records):
        if (type(item) is not dict or set(item) != _RECORD
                or item.get("report_id") != ("EV-OLD" if i == 0 else "EV-NEW")
                or item.get("provenance_class") != "UNVERIFIED_SYNTHETIC_REPORT"
                or any(type(item.get(k)) is not str
                       or _SYN_ID.fullmatch(item[k]) is None
                       for k in ("account_token", "terminal_token"))
                or any(item.get(k) not in _EVIDENCE_STATES
                       or type(item.get(k)) is not str
                       for k in ("positions", "pending_orders",
                                 "ea_attachment", "autotrading"))):
            return False
        observed, recorded = _utc(item["observed_at_utc"]), _utc(item["recorded_at_utc"])
        if observed is None or recorded is None or observed > recorded:
            return False
    g6 = case.get("g6_scenario")
    if (type(g6) is not dict or set(g6) != _G6_CASE
            or g6.get("threat") not in ("NONE", *_G6_THREATS)
            or type(g6.get("threat")) is not str
            or g6.get("persist_state") not in _PERSIST
            or type(g6.get("persist_state")) is not str
            or g6.get("anchor_state") not in _ANCHOR
            or type(g6.get("anchor_state")) is not str
            or g6.get("revocation_state") not in _REVOCATION
            or type(g6.get("revocation_state")) is not str
            or g6.get("clock_state") not in _CLOCK
            or type(g6.get("clock_state")) is not str
            or g6.get("simulated_io_only") is not True):
        return False
    return True


def audit_d528_acceptance_design(design: object, case: object) -> dict[str, object]:
    """Return a denial-only diagnostic. Even fully matching fixtures are NO_GO."""
    try:
        if not _valid_design(design):
            return _deny("D528_DESIGN_REJECTED_FAIL_CLOSED")
        if not _valid_case(case):
            return _deny("D528_CASE_REJECTED_FAIL_CLOSED")
        if case["simulated_stop_release_claim"]:
            return _deny("D528_RELEASE_CLAIM_DENIED_NO_GO")
        g6 = case["g6_scenario"]
        if (g6["threat"] != "NONE"
                or g6["persist_state"] != "SYNTHETIC_CONSISTENT"
                or g6["anchor_state"] != "SYNTHETIC_MATCH"
                or g6["revocation_state"] != "SYNTHETIC_NO_REVOCATION"
                or g6["clock_state"] != "SYNTHETIC_STABLE"):
            return _deny("D528_G6_UNTRUSTED_OR_FAULT_NO_GO")
        a, b = case["g2_records"]
        if (a["account_token"] != b["account_token"]
                or a["terminal_token"] != b["terminal_token"]):
            return _deny("D528_G2_SYNTHETIC_SCOPE_MISMATCH_NO_GO")
        # A newer-looking timestamp is supplied by the caller, not a live clock.
        if (_utc(a["observed_at_utc"]) != _utc(b["observed_at_utc"])):
            return _deny("D528_G2_SYNTHETIC_TIME_MISMATCH_NO_GO")
        if any(a[key] != b[key] for key in
               ("positions", "pending_orders", "ea_attachment", "autotrading")):
            return _deny("D528_G2_SYNTHETIC_REPORT_CONFLICT_NO_GO")
        if any(a[key] == "UNKNOWN" for key in
               ("positions", "pending_orders", "ea_attachment", "autotrading")):
            return _deny("D528_G2_SYNTHETIC_UNKNOWN_NO_GO")
        # The same attacker could create both records; no external identity proof.
        return _deny("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO")
    except Exception:
        return _deny("D528_INPUT_EXCEPTION_FAIL_CLOSED")
