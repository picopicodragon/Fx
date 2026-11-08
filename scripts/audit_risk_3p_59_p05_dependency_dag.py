"""Audit the static P05 dependency DAG and fail-closed owner approval state.

No broker account, private folder, MT4, live API or network access. This DAG
expresses *planning dependencies*, not authorization to observe or execute.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = "specs/risk_3p_59_p05_dependency_dag_20261106.json"
P05 = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
IDS = tuple(f"P05-{i:02d}" for i in range(1, 9))
CRITERIA = (
    "DEMO_ACCOUNT_IDENTITY_REAL_INDEPENDENT_CONFIRMATION",
    "MACD_EA_RUNTIME_STATE_REAL_NONINTERFERING_CONFIRMATION",
    "ACCOUNT_WIDE_BROKER_POSITIONS_AND_PENDING_ORDERS_RECONCILIATION",
    "SINGLE_MT4_SESSION_REAL_STATE_CONFIRMATION",
    "READ_ONLY_NO_INTERFERENCE_REAL_PLAN",
    "OWNER_ACCEPTED_FOLDER_OFFLINE_ONLY_NO_REAL_DATA_COLLECTION",
    "G1_REAL_3X5_BROKER_PROPERTIES_AND_INDEPENDENT_PROVENANCE",
    "EXPLICIT_OWNER_P05_SIGNOFF_AFTER_ALL_PREVIOUS_GATES",
)
EDGES = (
    (), ("P05-01",), ("P05-01", "P05-04"), ("P05-01",),
    ("P05-02", "P05-03", "P05-04"), (),
    ("P05-01", "P05-03", "P05-04", "P05-05", "P05-06"),
    ("P05-01", "P05-02", "P05-03", "P05-04",
     "P05-05", "P05-06", "P05-07"),
)
ROW_KEYS = ("check_id", "criterion", "depends_on",
            "independent_evidence_verified", "owner_signed", "status")
STATE = {
    "owner_offline_folder_accepted": True, "real_acl_verified": False,
    "p05_passed": 0, "g1_real_verified": 0,
    "real_mt4_observation_authorized": False,
    "real_order_or_ea_action_authorized": False,
    "owner_p05_signoff": False,
    "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True, "main_auto_merge_authorized": False,
}
META = {
    "schema_version": 1,
    "id": "RISK-3P-59-P05-SAFE-DEPENDENCY-DAG-20261106",
    "created_jst": "2026-11-06",
    "scope": "OFFLINE_PREREQUISITES_ONLY_NOT_REAL_BROKER_ACCEPTANCE",
    "source_p05": P05,
    "next_step":
    "NO_AUTO_TRANSITION_REQUIRE_INDEPENDENT_PROOF_AND_SEPARATE_HUMAN_ACCEPTANCE",
}


def _plain_keys(value: object) -> bool:
    return type(value) is dict and all(type(k) is str for k in value)


def _same(value: object, expected: object) -> bool:
    """Compare only exact builtin types, never arbitrary user __eq__ hooks."""
    if type(value) is not type(expected):
        return False
    if type(expected) is dict:
        return (_plain_keys(value) and set(value) == set(expected)
                and all(_same(value[k], v) for k, v in expected.items()))
    if type(expected) in (list, tuple):
        return (len(value) == len(expected)
                and all(_same(a, b) for a, b in zip(value, expected)))
    if type(expected) not in (str, int, bool, type(None)):
        return False
    return value == expected


def check_acyclic(items: object) -> list[str]:
    """Independent graph checks, no reflection or dynamic source execution."""
    if type(items) is not list or len(items) != 8:
        return ["P59_EXACTLY_EIGHT_GATES"]
    known = set(IDS)
    mapping = {}
    errors = []
    for i, row in enumerate(items):
        if not _plain_keys(row) or set(row) != set(ROW_KEYS):
            errors.append("P59_ROW_SCHEMA:" + str(i + 1))
            continue
        name, depends = row.get("check_id"), row.get("depends_on")
        if (type(name) is not str or name not in known
                or type(depends) is not list
                or any(type(d) is not str or d not in known for d in depends)
                or len(depends) != len(set(depends))):
            errors.append("P59_UNKNOWN_OR_DUPLICATE_DEPENDENCY:"
                          + str(i + 1))
            continue
        if name in mapping:
            errors.append("P59_DUPLICATE_GATE_ID:" + str(i + 1))
        mapping[name] = depends
    if errors:
        return errors
    visiting, visited = set(), set()

    def dfs(name):
        if name in visiting:
            return False
        if name in visited:
            return True
        visiting.add(name)
        if not all(dfs(dep) for dep in mapping[name]):
            return False
        visiting.remove(name)
        visited.add(name)
        return True

    if not all(dfs(name) for name in IDS):
        errors.append("P59_CYCLE_OR_SELF_DEPENDENCY")
    return errors


def _read(root: Path, path: str) -> object:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors = []
    try:
        sources = injected if injected is not None else {
            path: _read(root, path) for path in (GRAPH, P05)
        }
        if not _plain_keys(sources) or set(sources) != {GRAPH, P05}:
            return ["P59_MALFORMED_OR_MISSING_SOURCE"]
        doc, p05 = (sources[key] for key in (GRAPH, P05))
        if not _plain_keys(doc) or not _plain_keys(p05):
            return ["P59_MALFORMED_OR_MISSING_SOURCE"]
        if (set(doc) != set(META) | {"checks", "state"}
                or any(not _same(doc.get(k), v) for k, v in META.items())):
            errors.append("P59_DEPENDENCY_PLAN_SCOPE_DRIFT")
        if not _same(doc.get("state"), STATE):
            errors.append("P59_REAL_BROKER_OR_OWNER_APPROVAL_FORGED")
        rows = doc.get("checks")
        errors.extend(check_acyclic(rows))
        if type(rows) is list and len(rows) == 8:
            for i, row in enumerate(rows):
                if (not _plain_keys(row) or set(row) != set(ROW_KEYS)
                        or not _same(row.get("check_id"), IDS[i])
                        or not _same(row.get("criterion"), CRITERIA[i])
                        or not _same(row.get("depends_on"), list(EDGES[i]))
                        or row.get("independent_evidence_verified") is not False
                        or row.get("owner_signed") is not False
                        or not _same(row.get("status"),
                                     "BLOCKED_NOT_INDEPENDENTLY_VERIFIED")):
                    errors.append("P59_GATE_ORDER_OR_AUTHORIZATION_PROMOTED:"
                                  + str(i + 1))
        original = p05.get("p05_checks")
        if (type(original) is not list or len(original) != 8
                or not _same(p05.get("p05_passed_checks"), 0)
                or p05.get("p05_human_safety_signoff") is not False
                or p05.get("p06_observation_authorized") is not False
                or not _same(p05.get("runtime_go_no_go"), "NO_GO")
                or p05.get("safety_hold_latched") is not True):
            errors.append("P59_SOURCE_P05_STILL_UNACCEPTED_REQUIRED")
        else:
            for i, row in enumerate(original):
                if (not _plain_keys(row)
                        or not _same(row.get("check_id"), IDS[i])
                        or row.get("p05_accepted") is not False
                        or row.get("safe_to_proceed") is not False):
                    errors.append("P59_SOURCE_HUMAN_SIGNOFF_FALSE:"
                                  + str(i + 1))
    except Exception:
        errors.append("P59_INVALID_OR_MISSING_OFFLINE_SPEC")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_BLOCKED_DEPENDENCY_DAG_ONLY"
        if not errors else "FAIL_CLOSED",
        "p05_prerequisites": 8,
        "p05_real_accepted": 0,
        "g1_real_verified": 0,
        "owner_storage_accepted_for_offline_planning": True,
        "real_mt4_observation_authorized": False,
        "order_execution_authorized": False,
        "human_p05_signoff": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
