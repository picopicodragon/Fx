"""RISK-3P-23..26: read-only, non-authorizing decision-dependency audit.

The proposed graph identifies the *next questions* for a human to review.
Neither graph reachability nor a passing CI run grants MT4 observation,
order placement, implementation acceptance, manual-merge bypass, or STOP release.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_risk_3p_20_22_owner_evidence import audit as prior_audit


ROOT = Path(__file__).resolve().parents[1]
PLAN = "specs/risk_3p_23_26_owner_decision_critical_path_20261104.json"
DOCKET = "specs/risk_3p_22_form43_owner_review_docket_20261104.json"
G1 = "specs/risk_3p_20_g1_acceptance_rubric_20261104.json"
SOURCE = "specs/source_review_priority.json"
GATES = "specs/p0_01_d5_25_gap_verification_matrix.json"
ACCEPT = "specs/acceptance_registry.json"
EXPECTED_FORMS = tuple(f"FORM-{i:02d}" for i in range(1, 11))
COHORTS = (
    ("D1_CONTRACT_SCOPE_AND_EVIDENCE", ("FORM-01",)),
    ("D2_PROTECTION_RECONCILIATION_AND_GROSS",
     ("FORM-02", "FORM-05", "FORM-06")),
    ("D3_CONVERSION_COST_AND_LOT_PRECISION",
     ("FORM-03", "FORM-04", "FORM-07")),
    ("D4_NY17_DD_TIME_LEDGER",
     ("FORM-08", "FORM-09", "FORM-10")),
)
NODES = (
    ("P01_DOCUMENTARY_REVIEW_PACKET", (), "DOCUMENTATION_COMPLETE_NOT_APPROVAL"),
    ("P02_OWNER_VERIFY_SOURCE_ORIGINALS",
     ("P01_DOCUMENTARY_REVIEW_PACKET",), "PENDING_ORIGINAL_SOURCE_REVIEW"),
    ("P03_OWNER_G1_SCOPE_DECISION",
     ("P01_DOCUMENTARY_REVIEW_PACKET",), "PENDING_EXPLICIT_SCOPE_DECISION"),
    ("P04_OWNER_READONLY_PROTOCOL_DECISION",
     ("P01_DOCUMENTARY_REVIEW_PACKET",), "PENDING_SEPARATE_OBSERVATION_APPROVAL"),
    ("P05_SAFE_ENVIRONMENT_PRECHECK",
     ("P03_OWNER_G1_SCOPE_DECISION",
      "P04_OWNER_READONLY_PROTOCOL_DECISION"), "PENDING_ENVIRONMENT_PRECHECK"),
    ("P06_G1_PRIMARY_OBSERVATION",
     ("P05_SAFE_ENVIRONMENT_PRECHECK",), "PENDING_REAL_MT4_EVIDENCE"),
    ("P07_G1_INDEPENDENT_VERIFICATION",
     ("P06_G1_PRIMARY_OBSERVATION",), "PENDING_15_FIELD_INDEPENDENT_CHECK"),
    ("P08_OWNER_FORM_POLICY_DECISIONS",
     ("P02_OWNER_VERIFY_SOURCE_ORIGINALS",), "PENDING_43_OWNER_DECISIONS"),
    ("P09_FORM_EVIDENCE_RECONCILIATION",
     ("P07_G1_INDEPENDENT_VERIFICATION",
      "P08_OWNER_FORM_POLICY_DECISIONS"), "PENDING_FORM_EVIDENCE_REVIEW"),
    ("P10_SAFETY_IMPLEMENTATION_SIGNOFF",
     ("P09_FORM_EVIDENCE_RECONCILIATION",),
     "PENDING_FX_SAF_IMPLEMENTATION_APPROVAL"),
    ("P11_G2_G9_INDEPENDENT_GATE_REVIEWS",
     ("P10_SAFETY_IMPLEMENTATION_SIGNOFF",),
     "PENDING_FORMAL_G2_G9_GATE_EVIDENCE"),
    ("P12_MODULE_PHASE_ACCEPTANCE",
     ("P11_G2_G9_INDEPENDENT_GATE_REVIEWS",),
     "PENDING_Q110_INDEPENDENT_OWNER_ACCEPTANCE"),
)
CAPS = {"individual_risk": "0.005",
        "combined_risk": "0.010",
        "daily_loss": "0.015",
        "dd_level3_new_entries_halt": "0.04",
        "max_dd": "0.05"}
HUMAN_FIRST = (
    "P02_OWNER_VERIFY_SOURCE_ORIGINALS",
    "P03_OWNER_G1_SCOPE_DECISION",
    "P04_OWNER_READONLY_PROTOCOL_DECISION",
)


def _read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _data(root: Path, injected: dict | None) -> dict:
    return {
        path: (injected[path] if injected is not None and path in injected
               else _read(root, path))
        for path in (PLAN, DOCKET, G1, SOURCE, GATES, ACCEPT)
    }


def topological_nodes(nodes: object) -> tuple[str, ...]:
    """Raises on duplicate/missing dependencies and cycles, never grants GO."""
    if type(nodes) is not list:
        raise ValueError("invalid graph")
    graph: dict[str, tuple[str, ...]] = {}
    for node in nodes:
        if type(node) is not dict:
            raise ValueError("invalid graph item")
        ident, requires = node.get("id"), node.get("requires")
        if type(ident) is not str or not ident or ident in graph:
            raise ValueError("duplicate or invalid stage id")
        if type(requires) is not list or any(type(s) is not str for s in requires):
            raise ValueError("malformed dependency list")
        if len(requires) != len(set(requires)):
            raise ValueError("duplicate dependency")
        graph[ident] = tuple(requires)
    if any(d not in graph for values in graph.values() for d in values):
        raise ValueError("dangling prerequisite")
    seen: set[str] = set()
    visiting: set[str] = set()
    result: list[str] = []

    def visit(ident: str) -> None:
        if ident in visiting:
            raise ValueError("cyclic prerequisite")
        if ident in seen:
            return
        visiting.add(ident)
        for parent in graph[ident]:
            visit(parent)
        visiting.remove(ident)
        seen.add(ident)
        result.append(ident)

    for ident in graph:
        visit(ident)
    return tuple(result)


def audit(root: Path = ROOT, *, injected: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        data = _data(root, injected)
        plan, docket, rubric = data[PLAN], data[DOCKET], data[G1]
        if type(plan) is not dict:
            return ["INVALID_CRITICAL_PATH_PLAN"]
        if (type(plan.get("schema_version")) is not int
                or plan.get("schema_version") != 1
                or plan.get("id") !=
                "RISK-3P-23-26-OWNER-DECISION-CRITICAL-PATH-20261104"
                or plan.get("scope") !=
                "PROPOSED_PLANNING_DEPENDENCIES_NOT_APPROVED_EXECUTION_SEQUENCE"
                or plan.get("source_docket") != DOCKET
                or plan.get("source_g1_rubric") != G1
                or plan.get("source_acceptance_registry") != ACCEPT):
            errors.append("PLAN_ID_OR_SOURCE_INVALID")
        if (plan.get("form_ids") != list(EXPECTED_FORMS)
                or plan.get("total_owner_choices") != 43
                or plan.get("source_original_safety_requirements") != 15
                or plan.get("g1_target_field_count") != 15
                or plan.get("g1_fields_proved") != 0
                or plan.get("existing_g1_scope_status") !=
                "LEGACY_4x5_UNRESOLVED"
                or plan.get("proposed_g1_scope_status") !=
                "3x5_NOT_APPROVED"):
            errors.append("FORM_OR_G1_COUNTS_PROMOTED")
        if plan.get("safety_caps") != CAPS:
            errors.append("HARD_CAPS_DRIFT")
        cohorts = plan.get("cohorts")
        if (type(cohorts) is not list
                or [(row.get("cohort_id"), tuple(row.get("forms", ())))
                    for row in cohorts if type(row) is dict] != list(COHORTS)):
            errors.append("FOUR_COHORT_SCOPE_DRIFT")
        else:
            all_forms = [form for row in cohorts for form in row["forms"]]
            if sorted(all_forms) != sorted(EXPECTED_FORMS):
                errors.append("COHORT_FORM_COVERAGE_INCOMPLETE")
            group_order = {group["form_id"]: group["review_sequence"]
                           for group in docket["form_groups"]}
            for i, group in enumerate(cohorts, 1):
                if (type(group.get("sequence")) is not int
                        or group["sequence"] != i
                        or group.get("requires_human_spec_decision") is not True
                        or group.get("requires_real_broker_evidence_for_final_acceptance")
                        is not True
                        or group.get("may_prepare_offline") is not True
                        or any(type(group.get(k)) is not str or not group[k]
                               for k in ("topic", "decision_type", "proposal",
                                         "evidence_gap"))
                        or (i > 1 and min(group_order[f] for f in group["forms"])
                            <= max(group_order[f] for f in cohorts[i - 2]["forms"]))):
                    errors.append("COHORT_FALSELY_REVIEWED_OR_OUT_OF_ORDER:"
                                  + group["cohort_id"])
        nodes = plan.get("proposed_dependency_nodes")
        try:
            order = topological_nodes(nodes)
        except ValueError:
            errors.append("INVALID_OR_CYCLIC_DEPENDENCIES")
            order = ()
        if (type(nodes) is not list or len(nodes) != len(NODES)
                or plan.get("proposed_topological_stage_count") != len(NODES)
                or [r.get("id") for r in nodes if type(r) is dict]
                != [row[0] for row in NODES]):
            errors.append("STAGE_SET_DRIFT")
        elif order:
            for i, node in enumerate(nodes):
                name, prereq, status = NODES[i]
                if (node.get("requires") != list(prereq)
                        or node.get("status") != status
                        or type(node.get("name")) is not str or not node["name"]
                        or node.get("needs_owner") is not (i != 0)
                        or node.get("needs_real_env") is not (i >= 4 and i != 7)
                        or node.get("execution_permitted") is not False):
                    errors.append("DEPENDENCY_OR_AUTHORITY_DRIFT:" + name)
            if order != tuple(n[0] for n in NODES):
                errors.append("STAGE_ORDER_DRIFT")
        for name in (
            "independent_human_go_decision_required",
            "topological_plan_is_only_proposal",
            "pr_merge_is_not_form_approval",
        ):
            if plan.get(name) is not True:
                errors.append("FALSE_POLICY_RELAXATION:" + name)
        for name in (
            "potential_subsequent_branch_release_prohibited",
            "real_mt4_observation_authorized", "customer_account_data_ingested",
            "automated_owner_approval_authorized", "production_authorized",
            "orders_authorized", "stop_release_authorized",
            "safety_gate_overrides_authorized",
        ):
            expected = name == "potential_subsequent_branch_release_prohibited"
            if plan.get(name) is not expected:
                errors.append("FALSE_OPERATIONAL_AUTHORITY:" + name)
        if (plan.get("owner_review_status") !=
                "NO_SPECIFICATION_DECISIONS_RECORDED"
                or plan.get("phase_1") != "BLOCKED"
                or plan.get("runtime_go_no_go") != "NO_GO"
                or plan.get("safety_hold_latched") is not True
                or plan.get("verified_values", "MISSING") is not None):
            errors.append("STOP_OR_APPROVAL_STATUS_PROMOTED")
        if (type(docket["decisions"]) is not list
                or len(docket["decisions"]) != 43
                or any(x.get("owner_decision") != "NOT_RECORDED"
                       or x.get("implementation_approved") is not False
                       for x in docket["decisions"])):
            errors.append("UPSTREAM_OWNER_DECISIONS_NOT_PENDING")
        if (rubric.get("verified_count") != 0
                or len(rubric["rows"]) != 15
                or any(x.get("real_world_verified") is not False
                       for x in rubric["rows"])):
            errors.append("UPSTREAM_G1_NOT_PENDING")
        safety = data[SOURCE]
        if (len(safety["items"]) != 15
                or any(x.get("source_review") != "PENDING_ORIGINAL"
                       or x.get("human_safety_approval") is not False
                       for x in safety["items"])):
            errors.append("ORIGINAL_SAFETY_SOURCES_NOT_UNRESOLVED")
        gates = data[GATES]
        if (len(gates["gaps"]) != 9
                or any(x.get("implementation_status") != "UNRESOLVED"
                       or x.get("real_world_verified") is not False
                       or x.get("release_blocker") is not True
                       for x in gates["gaps"])):
            errors.append("FORMAL_GATES_NOT_ALL_BLOCKED")
        accept = data[ACCEPT]
        module = next(x for x in accept["modules"]
                      if x["id"] == "M-P1-FOUNDATION-DESIGN")
        phase = next(x for x in accept["phases"] if x["id"] == "PHASE-1")
        if (module.get("status") != "BLOCKED" or module.get("approval") is not None
                or phase.get("status") != "BLOCKED" or phase.get("approval") is not None):
            errors.append("Q110_MODULE_OR_PHASE_FALSELY_ACCEPTED")
        if injected is None and prior_audit(root):
            errors.append("PRIOR_FORM_AND_G1_AUDIT_FAILED")
    except (OSError, KeyError, ValueError, TypeError,
            AttributeError, StopIteration):
        errors.append("MALFORMED_OR_MISSING_PRIOR_REGISTER")
    return errors


def snapshot(root: Path = ROOT) -> dict:
    """Fixed fail-closed readiness report, not a mutable workflow engine."""
    errors = audit(root)
    if errors:
        return {
            "readiness": "BLOCKED_INVALID_REVIEW_SOURCES",
            "errors": errors,
            "order_allowed": False,
            "stop_release_allowed": False,
            "phase_1": "BLOCKED",
            "runtime_go_no_go": "NO_GO",
        }
    plan = _read(root, PLAN)
    return {
        "readiness": "BLOCKED_OWNER_ORIGINALS_AND_G1_REAL_EVIDENCE",
        "documentary_preparation_complete": ["P01_DOCUMENTARY_REVIEW_PACKET"],
        "proposed_next_human_review_entries": list(HUMAN_FIRST),
        "remaining_unapproved": [row["id"]
                                 for row in plan["proposed_dependency_nodes"][1:]],
        "owner_decisions_pending": 43,
        "g1_real_fields_verified": 0,
        "fx_saf_originals_reviewed": 0,
        "order_allowed": False,
        "stop_release_allowed": False,
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
    }


def main() -> None:
    report = snapshot()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["readiness"] == "BLOCKED_INVALID_REVIEW_SOURCES":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
