"""D5-26: pure offline G1-G9 sequencing and *non-authorizing* review gate.

This validates a proposed design backlog against a caller-supplied D5-25 matrix.
Neither input is signed/trusted. No file, clock, network, MT4, broker, approval,
stop-release or order execution capability exists. Every output remains NO_GO.
"""
from __future__ import annotations

_PRIORITIES = ("G2", "G6", "G8", "G7", "G3", "G1", "G5", "G9", "G4")
_DEPENDENCIES = {
    # Proposed sequencing of future *verification* only; not an approved spec.
    "G2": (), "G6": (), "G8": ("G6",), "G7": ("G6",),
    "G3": ("G2", "G6", "G8", "G7"), "G1": ("G2",),
    "G5": ("G1", "G7"), "G9": ("G1", "G7"),
    "G4": ("G3", "G5", "G9"),
}
_PLAN_KEYS = frozenset((
    "origin", "schema_version", "phase_1", "runtime_go_no_go",
    "verified_values", "environment_policy", "rakuten_inquiry",
    "additional_demo_account", "account_identity_consistency",
    "approval_state", "gates", "transition_proposals", "next_offline_focus",
))
_GATE_KEYS = frozenset((
    "id", "rank", "severity", "depends_on", "offline_next",
    "external_evidence_required", "readiness", "release_blocker",
    "real_world_verified",
))
_TRANSITION_KEYS = frozenset((
    "id", "status", "requires_explicit_approval",
    "prior_transition", "requires_verified_gates", "target_gaps",
    "scope_rule",
))
_TRANSITION_POLICY = (
    # id, prior, required verified gates, target gaps, scope description
    ("OFFLINE_SPEC_REVIEW", None, (), tuple(_PRIORITIES),
     "DOCUMENTATION_ONLY_NO_RUNTIME"),
    ("SINGLE_ENV_VISUAL_REVIEW", "OFFLINE_SPEC_REVIEW", (), ("G2",),
     "SEPARATE_APPROVAL_NO_MT4_ACTION_IMPLIED"),
    ("MT4_READ_ONLY_PREFLIGHT", "SINGLE_ENV_VISUAL_REVIEW", (),
     ("G1", "G2", "G9"), "SEPARATE_APPROVAL_NO_EA_OR_ORDERS"),
    ("OFFLINE_PERSISTENCE_LAB", "OFFLINE_SPEC_REVIEW", (),
     ("G6", "G7"), "SEPARATE_APPROVAL_FOR_HOST_IO_NO_BROKER"),
    ("DEMO_EXECUTION_EVALUATION", "MT4_READ_ONLY_PREFLIGHT",
     ("G1", "G2", "G6", "G7", "G8"), ("G3", "G4", "G5"),
     "FUTURE_DESIGN_ONLY_SEPARATE_APPROVAL"),
    ("LIVE_ACTIVATION", "DEMO_EXECUTION_EVALUATION", tuple(_PRIORITIES),
     tuple(_PRIORITIES), "FUTURE_DESIGN_ONLY_SEPARATE_ACTIVATION_APPROVAL"),
)
_BASELINE_ID = "P0-01-D5-25-GAP-VERIFICATION-MATRIX"


def _deny(status: str) -> dict[str, object]:
    return {
        "status": status,
        "proposed_review_priority": list(_PRIORITIES),
        "next_offline_design_focus": ["G2", "G6"],
        "gaps_real_world_resolved": [],
        "real_transition_authorized": False,
        "visual_review_approved": False,
        "mt4_read_only_approved": False,
        "host_io_approved": False,
        "demo_execution_approved": False,
        "live_activation_approved": False,
        "approval_verified": False,
        "action_authorized": False,
        "stop_release_authorized": False,
        "effective_approved_actions": [],
        "safety_hold_latched": True,
        "runtime_go_no_go": "NO_GO",
        "phase_1": "BLOCKED",
        "verified_values": None,
        "broker_verified": False,
        "production_usable": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "orders_generated": False,
        "forward_trading_enabled": False,
    }


def _nonempty_strings(value: object) -> bool:
    return (
        type(value) is list and 1 <= len(value) <= 8
        and all(type(item) is str and 1 <= len(item.strip()) <= 400
                for item in value)
    )


def _baseline_valid(base: object) -> bool:
    if (type(base) is not dict
            or base.get("id") != _BASELINE_ID
            or base.get("origin") != "OFFLINE_SYNTHETIC_ONLY"
            or type(base.get("schema_version")) is not int
            or base["schema_version"] != 1
            or base.get("phase_1") != "BLOCKED"
            or base.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in base
            or base["verified_values"] is not None
            or base.get("environment_policy") != "SINGLE_MT4_ENVIRONMENT_ONLY"
            or base.get("rakuten_inquiry") != "CANCELLED_DO_NOT_SEND"
            or base.get("additional_demo_account") != "OUT_OF_SCOPE"
            or base.get("real_mt4_access_approved") is not False
            or base.get("real_order_execution_approved") is not False
            or base.get("broker_verified") is not False
            or base.get("terminal_execution_approved") is not False
            or base.get("forward_trading_enabled") is not False):
        return False
    items = base.get("gaps")
    if type(items) is not list or len(items) != 9:
        return False
    seen: set[str] = set()
    for item in items:
        if type(item) is not dict:
            return False
        gid = item.get("id")
        if (type(gid) is not str or gid not in _PRIORITIES or gid in seen
                or item.get("implementation_status") != "UNRESOLVED"
                or item.get("real_world_verified") is not False
                or item.get("release_blocker") is not True
                or item.get("severity") !=
                    ("CRITICAL" if gid in ("G1", "G2", "G3", "G4") else "HIGH")
                or not _nonempty_strings(item.get("offline_synthetic_coverage"))
                or not _nonempty_strings(item.get("external_or_real_evidence_required"))):
            return False
        seen.add(gid)
    return seen == set(_PRIORITIES)


def _plan_valid(plan: object) -> str | None:
    if (type(plan) is not dict or set(plan) != _PLAN_KEYS
            or plan.get("origin") != "OFFLINE_DESIGN_ONLY"
            or type(plan.get("schema_version")) is not int
            or plan["schema_version"] != 1
            or plan.get("phase_1") != "BLOCKED"
            or plan.get("runtime_go_no_go") != "NO_GO"
            or "verified_values" not in plan
            or plan["verified_values"] is not None
            or plan.get("environment_policy") != "SINGLE_MT4_ENVIRONMENT_ONLY"
            or plan.get("rakuten_inquiry") != "CANCELLED_DO_NOT_SEND"
            or plan.get("additional_demo_account") != "OUT_OF_SCOPE"
            or plan.get("account_identity_consistency") != "NOT_RECONCILED"
            or plan.get("approval_state") != "NO_REAL_ACTION_APPROVED"
            or plan.get("next_offline_focus") != ["G2", "G6"]):
        return "PLAN_INPUT_REJECTED_FAIL_CLOSED"
    gates = plan.get("gates")
    if type(gates) is not list or len(gates) != 9:
        return "PLAN_GAPS_REJECTED_FAIL_CLOSED"
    for rank, (gid, gate) in enumerate(zip(_PRIORITIES, gates), 1):
        if type(gate) is not dict or set(gate) != _GATE_KEYS:
            return "PLAN_GAPS_REJECTED_FAIL_CLOSED"
        if (gate.get("id") != gid
                or type(gate.get("rank")) is not int or gate["rank"] != rank
                or gate.get("severity") !=
                   ("CRITICAL" if gid in ("G1", "G2", "G3", "G4") else "HIGH")
                or gate.get("readiness") != "UNRESOLVED"
                or gate.get("release_blocker") is not True
                or gate.get("real_world_verified") is not False
                or not _nonempty_strings(gate.get("offline_next"))
                or not _nonempty_strings(gate.get("external_evidence_required"))):
            return "PLAN_GAPS_REJECTED_FAIL_CLOSED"
        if type(gate.get("depends_on")) is not list:
            return "PLAN_DEPENDENCIES_REJECTED_FAIL_CLOSED"
        if gate["depends_on"] != list(_DEPENDENCIES[gid]):
            return "PLAN_DEPENDENCIES_REJECTED_FAIL_CLOSED"
        if any(_PRIORITIES.index(dep) >= rank - 1
               for dep in gate["depends_on"]):
            return "PLAN_DEPENDENCIES_REJECTED_FAIL_CLOSED"
    transitions = plan.get("transition_proposals")
    if type(transitions) is not list or len(transitions) != len(_TRANSITION_POLICY):
        return "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED"
    for idx, (item, rule) in enumerate(zip(transitions, _TRANSITION_POLICY)):
        ident, prior, required, targets, scope = rule
        if type(item) is not dict or set(item) != _TRANSITION_KEYS:
            return "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED"
        if (item.get("id") != ident
                or item.get("status") !=
                   ("DESIGN_ONLY" if idx == 0 else "NOT_APPROVED")
                or item.get("requires_explicit_approval") is not (idx != 0)
                or item.get("prior_transition") != prior
                or item.get("requires_verified_gates") != list(required)
                or item.get("target_gaps") != list(targets)
                or item.get("scope_rule") != scope):
            return "PLAN_TRANSITIONS_REJECTED_FAIL_CLOSED"
    return None


def evaluate_offline_transition_plan(
    plan: object, baseline: object,
) -> dict[str, object]:
    """Review static proposed sequencing, with NO path to execution approval.

    G1-G9 verification remains blocked; passing here only means a documentation
    plan matches an untrusted D5-25 baseline. Never unlocks even read-only MT4.
    """
    try:
        if not _baseline_valid(baseline):
            return _deny("PLAN_BASELINE_REJECTED_FAIL_CLOSED")
        issue = _plan_valid(plan)
        if issue is not None:
            return _deny(issue)
        # A self-consistent but rewritten plan is not proof that its claimed
        # real-evidence requirements match the original D5-25 gap inventory.
        by_id = {item["id"]: item for item in baseline["gaps"]}
        for item in plan["gates"]:
            if item["external_evidence_required"] != by_id[item["id"]][
                    "external_or_real_evidence_required"]:
                return _deny("PLAN_BASELINE_ALIGNMENT_REJECTED_FAIL_CLOSED")
        return _deny("PLAN_DESIGN_VALIDATED_REAL_TRANSITIONS_BLOCKED_NO_GO")
    except Exception:
        return _deny("PLAN_INPUT_REJECTED_FAIL_CLOSED")
