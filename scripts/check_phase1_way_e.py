"""Cross-check the offline Way E gate snapshot against existing registries.

This is a structural audit. It does not verify original decisions, real-world
evidence, broker state, storage durability, or human identity/approval.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


SOURCES = {
    "gap": "specs/p0_01_d5_25_gap_verification_matrix.json",
    "plan": "specs/p0_01_d5_26_transition_priority_plan.json",
    "work": "specs/p0_01_d5_37_workplan_contract.json",
    "readiness": "specs/p0_01_d5_36_readiness_register.json",
    "source": "specs/source_review_priority.json",
    "recon": "specs/reconciliation_registry.json",
    "evidence": "specs/source_evidence.json",
    "fault": "specs/p1_04_fault_matrix.json",
    "broker": "specs/p1_05_mock_broker_scenarios.json",
    "acceptance": "specs/acceptance_registry.json",
}
REGISTER = "specs/phase1_way_e_gate_register.json"
BASE_MAIN = "44433ecda3201745d673984c283bb6f330db914c"


def _read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def derive_register(root: Path) -> dict:
    d = {key: _read(root, path) for key, path in SOURCES.items()}
    gaps = {row["id"]: row for row in d["gap"]["gaps"]}
    recon = {row["requirement_id"]: row for row in d["recon"]["items"]}
    evidence = {row["question_id"]: row for row in d["evidence"]["records"]}
    module = next(row for row in d["acceptance"]["modules"]
                  if row["id"] == "M-P1-FOUNDATION-DESIGN")
    phase = next(row for row in d["acceptance"]["phases"]
                 if row["id"] == "PHASE-1")
    return {
        "schema_version": 1,
        "origin": "OFFLINE_SOURCE_DERIVED_NO_REAL_EVIDENCE",
        "base_main_sha": BASE_MAIN,
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "verified_values": None,
        "gates": [{
            "id": row["id"],
            "subject": gaps[row["id"]]["subject"],
            "severity": row["severity"],
            "depends_on": row["depends_on"],
            "rank": row["rank"],
            "external_or_real_evidence_required":
                gaps[row["id"]]["external_or_real_evidence_required"],
            "implementation_status": gaps[row["id"]]["implementation_status"],
            "release_blocker": gaps[row["id"]]["release_blocker"],
            "real_world_verified": gaps[row["id"]]["real_world_verified"],
            "source_definition": SOURCES["gap"],
            "source_dependency": SOURCES["plan"],
        } for row in d["plan"]["gates"]],
        "work_packages": [{
            "task_id": row["task_id"],
            "criterion_id": row["criterion_id"],
            "depends_on": row["depends_on"],
            "external_gate_dependencies": row["external_gate_dependencies"],
            "future_acceptance_evidence": row["future_acceptance_evidence"],
            "implementation_allowed": row["implementation_allowed"],
            "real_evidence_collected": row["real_evidence_collected"],
            "review_approved": row["review_approved"],
            "acceptance_allowed": row["acceptance_allowed"],
            "execution_allowed": row["execution_allowed"],
            "separate_human_approval_required": row["separate_human_approval_required"],
            "source": SOURCES["work"],
        } for row in d["work"]["work_packages"]],
        "safety_requirements": [{
            "requirement_id": row["requirement_id"],
            "question_ids": row["question_ids"],
            "source_review": row["source_review"],
            "source_kind": recon[row["requirement_id"]]["source_kind"],
            "comparison_status": recon[row["requirement_id"]]["comparison_status"],
            "implementation_approved":
                recon[row["requirement_id"]]["implementation_approved"],
            "human_safety_approval": row["human_safety_approval"],
            "owner_approval": recon[row["requirement_id"]]["owner_approval"],
            "source_review_register": SOURCES["source"],
            "source_reconciliation": SOURCES["recon"],
        } for row in d["source"]["items"]],
        "q109_q115_evidence": [{
            "question_id": question,
            "registered_original_excerpt": question in evidence,
            "source_kind": evidence[question]["source_kind"]
                if question in evidence else "UNREGISTERED",
            "archive_locator_status": evidence[question]["archive_locator_status"]
                if question in evidence else None,
            "owner_approved_for_safety": evidence[question]["owner_approved_for_safety"]
                if question in evidence else False,
        } for question in (f"Q{i}" for i in range(109, 116))],
        "planned_case_status": {
            "p1_04": {
                "count": len(d["fault"]["test_cases"]),
                "not_executed": sum(row["execution_status"] == "NOT_EXECUTED"
                                    for row in d["fault"]["test_cases"]),
                "source": SOURCES["fault"],
            },
            "p1_05": {
                "count": len(d["broker"]["test_cases"]),
                "not_executed": sum(row["status"] == "NOT_EXECUTED"
                                    for row in d["broker"]["test_cases"]),
                "source": SOURCES["broker"],
            },
        },
        "acceptance": {
            "module": module["status"],
            "phase": phase["status"],
            "source": SOURCES["acceptance"],
        },
    }


def audit(root: Path, register: object) -> list[str]:
    """Return only generic diagnostics, never raw source or account values."""
    try:
        expected = derive_register(root)
        d = {key: _read(root, path) for key, path in SOURCES.items()}
        errors = []
        if register != expected:
            errors.append("SNAPSHOT_MISMATCH")
        gates = expected["gates"]
        if (len(gates) != 9 or {x["id"] for x in gates}
                != {f"G{i}" for i in range(1, 10)}):
            errors.append("GATE_SET_CHANGED")
        if any(x["implementation_status"] != "UNRESOLVED"
               or x["release_blocker"] is not True
               or x["real_world_verified"] is not False for x in gates):
            errors.append("GATE_STATE_PROMOTED")
        if any(not set(x["depends_on"]).issubset({y["id"] for y in gates})
               for x in gates):
            errors.append("UNKNOWN_DEPENDENCY")
        rank = {x["id"]: x["rank"] for x in gates}
        if (sorted(rank.values()) != list(range(1, 10))
                or any(rank[prior] >= x["rank"] for x in gates
                       for prior in x["depends_on"] if prior in rank)):
            errors.append("DEPENDENCY_ORDER_INVALID")
        packages = expected["work_packages"]
        criteria = {x["criterion_id"] for x in packages}
        if (len(criteria) != 15
                or {x["task_id"] for x in packages}
                    != {f"D537-WP-{i:02}" for i in range(1, 16)}
                or criteria != {x["criterion_id"] for x in d["readiness"]["criteria"]}
                or any(not set(x["depends_on"]).issubset(criteria)
                       for x in packages)):
            errors.append("WORK_PACKAGE_SET_INVALID")
        if len(expected["work_packages"]) != 15 or any(
            x["implementation_allowed"] is not False
            or x["real_evidence_collected"] is not False
            or x["review_approved"] is not False
            or x["acceptance_allowed"] is not False
            or x["execution_allowed"] is not False
            or x["separate_human_approval_required"] is not True
            for x in expected["work_packages"]
        ):
            errors.append("WORK_PACKAGE_PROMOTED")
        readiness = d["readiness"]["criteria"]
        if len(readiness) != 15 or any(
            x["implementation_state"] != "NOT_IMPLEMENTED"
            or x["real_evidence_state"] != "NOT_COLLECTED"
            or x["human_approval_state"] != "NOT_GRANTED"
            or x["acceptance_state"] != "BLOCKED" for x in readiness
        ):
            errors.append("READINESS_PROMOTED")
        safety = expected["safety_requirements"]
        if {x["requirement_id"] for x in safety} != {
            f"FX-SAF-{i:03}" for i in range(1, 16)
        }:
            errors.append("SAFETY_REQUIREMENT_SET_INVALID")
        if len(safety) != 15 or any(
            x["source_review"] != "PENDING_ORIGINAL"
            or x["source_kind"] != "SUMMARY_ONLY"
            or x["comparison_status"] not in
                {"SOURCE_UNAVAILABLE", "NEEDS_CLARIFICATION"}
            or x["implementation_approved"] is not False
            or x["human_safety_approval"] is not False
            or x["owner_approval"] is not None for x in safety
        ):
            errors.append("SAFETY_SOURCE_PROMOTED")
        if expected["q109_q115_evidence"][:4] != [
            {"question_id": f"Q{i}", "registered_original_excerpt": False,
             "source_kind": "UNREGISTERED", "archive_locator_status": None,
             "owner_approved_for_safety": False}
            for i in range(109, 113)
        ] or any(x["source_kind"] != "ORIGINAL"
                 or x["archive_locator_status"] != "PENDING_LOCAL_ARCHIVE"
                 or x["owner_approved_for_safety"] is not False
                 for x in expected["q109_q115_evidence"][4:]):
            errors.append("SOURCE_EVIDENCE_CHANGED")
        cases = expected["planned_case_status"]
        if (cases["p1_04"]["count"] != 26
                or cases["p1_04"]["not_executed"] != 26
                or cases["p1_05"]["count"] != 27
                or cases["p1_05"]["not_executed"] != 27):
            errors.append("PLANNED_CASES_MISSTATED")
        if expected["acceptance"]["module"] != "BLOCKED" or expected["acceptance"]["phase"] != "BLOCKED":
            errors.append("ACCEPTANCE_PROMOTED")
        if (d["gap"]["phase_1"] != "BLOCKED"
                or d["gap"]["runtime_go_no_go"] != "NO_GO"
                or d["gap"]["verified_values"] is not None
                or d["gap"]["forward_trading_enabled"] is not False):
            errors.append("RUNTIME_GATE_PROMOTED")
        if (d["plan"]["phase_1"] != "BLOCKED"
                or d["plan"]["runtime_go_no_go"] != "NO_GO"
                or d["plan"]["verified_values"] is not None):
            errors.append("PRIORITY_PLAN_PROMOTED")
        return errors
    except (KeyError, TypeError, ValueError, StopIteration, OSError, json.JSONDecodeError):
        return ["SOURCE_OR_REGISTER_INVALID"]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if len(sys.argv) == 2 and sys.argv[1] == "--print-derived":
        print(json.dumps(derive_register(root), ensure_ascii=False, indent=2))
        return 0
    if len(sys.argv) != 1:
        print("usage: check_phase1_way_e.py [--print-derived]", file=sys.stderr)
        return 2
    try:
        register = _read(root, REGISTER)
    except (OSError, ValueError):
        print("Way E gate audit: SOURCE_OR_REGISTER_INVALID", file=sys.stderr)
        return 1
    errors = audit(root, register)
    if errors:
        print("Way E gate audit: " + ", ".join(errors), file=sys.stderr)
        return 1
    print("Way E gate audit: PASS (offline structure only; all real gates blocked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
