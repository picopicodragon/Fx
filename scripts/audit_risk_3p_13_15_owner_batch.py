"""RISK-3P-13..15: static owner-review audit, no operational authority."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRAFT = "specs/risk_3p_13_15_form08_10_owner_review_20261104.json"
SOURCE = "specs/p0_01_risk_formula_open_decisions.json"
GATES = "specs/p0_01_d5_25_gap_verification_matrix.json"
IDS = ("FORM-08", "FORM-09", "FORM-10")
RISK_IDS = ("RISK-3P-13", "RISK-3P-14", "RISK-3P-15")
CAPS = {"individual": "0.005", "aggregate": "0.010",
        "daily": "0.015", "max_drawdown": "0.05", "dd4_no_new_orders": True}
DEPENDENCIES = ("FORM-01", "FORM-02", "FORM-03", "FORM-04",
                "FORM-05", "FORM-06", "FORM-07", "G1", "G6",
                "FX-SAF-001", "FX-SAF-002")
EXAMPLES = ("NY17_DAY_ANCHOR_USING_SUPPLIED_UTC_AND_IANA_TZ",
            "SYNTHETIC_CASHFLOW_ADJUSTMENT_NOT_APPROVED",
            "SYNTHETIC_UNIT_VALUE_NOT_HWM_PROVENANCE",
            "ALL_SOURCES_CAUSAL_SHAPE_NO_APPROVED_TTL")


def read(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, draft: object = None) -> list[str]:
    errors: list[str] = []
    try:
        d = read(root, DRAFT) if draft is None else draft
        if type(d) is not dict:
            return ["INVALID_REGISTER"]
        if (type(d.get("schema_version")) is not int
                or d.get("schema_version") != 1
                or d.get("id") !=
                "RISK-3P-13-15-FORM08-10-BATCH-OWNER-REVIEW-20261104"
                or d.get("source_register") != SOURCE
                or d.get("scope") !=
                "SYNTHETIC_DAY_DD_TIME_AND_OWNER_REVIEW_ONLY"):
            errors.append("DRAFT_SCOPE_CHANGED")
        if d.get("existing_caps") != CAPS:
            errors.append("RISK_LIMITS_CHANGED")
        if d.get("unresolved_dependencies") != list(DEPENDENCIES):
            errors.append("DOWNSTREAM_DEPENDENCIES_DROPPED")
        if d.get("only_examples") != list(EXAMPLES):
            errors.append("FALSE_PRODUCTION_EXAMPLE_OR_TTL")
        for name in ("fx_saf_implementation_approved",
                     "g1_to_g9_real_world_verified",
                     "owner_approval_recorded", "production_authorized",
                     "broker_connection_authorized", "mt4_execution_authorized",
                     "order_allowed", "stop_release_allowed",
                     "auto_resume_authorized"):
            if d.get(name) is not False:
                errors.append("FALSE_OPERATIONAL_APPROVAL:" + name)
        if (d.get("phase_1") != "BLOCKED"
                or d.get("runtime_go_no_go") != "NO_GO"
                or d.get("safety_hold_latched") is not True
                or d.get("verified_values", "MISSING") is not None):
            errors.append("FALSE_STOP_RELEASE")
        original = read(root, SOURCE)
        src = {x["id"]: x for x in original["open_decisions"]}
        forms = d.get("forms")
        if (type(forms) is not list
                or [f.get("form_id") for f in forms if type(f) is dict] != list(IDS)
                or [f.get("risk_id") for f in forms if type(f) is dict] != list(RISK_IDS)):
            errors.append("FORM08_10_SCOPE_CHANGED")
        else:
            for row in forms:
                key = row["form_id"]
                if (src[key].get("owner_status") != "UNDECIDED_IMPLEMENTATION_DETAIL"
                        or src[key].get("blocking") is not True
                        or row.get("original_status") != src[key]["owner_status"]):
                    errors.append("ORIGINAL_FORM_GATE_ADVANCED:" + key)
                if (row.get("real_world_verified") is not False
                        or row.get("implementation_approved") is not False
                        or row.get("owner_approval_recorded") is not False):
                    errors.append("FALSE_FORM_APPROVAL:" + key)
                if (type(row.get("unresolved")) is not list
                        or len(row["unresolved"]) < 3
                        or type(row.get("recommendation")) is not str
                        or not row["recommendation"]):
                    errors.append("MISSING_FORM_REVIEW:" + key)
        decisions = d.get("owner_decisions")
        expected_ids = [
            f"FORM{i:02d}-{j}" for i in range(8, 11) for j in range(1, 5)
        ]
        if (type(decisions) is not list
                or [x.get("id") for x in decisions if type(x) is dict]
                != expected_ids):
            errors.append("DECISION_SET_INCOMPLETE")
        else:
            for row in decisions:
                if (row.get("owner_decision") != "NOT_RECORDED"
                        or row.get("approval_reference", "MISSING") is not None
                        or row.get("real_world_verified") is not False
                        or type(row.get("question")) is not str
                        or not row["question"]):
                    errors.append("FALSE_OWNER_DECISION:" + row["id"])
        gaps = read(root, GATES)
        if (gaps.get("phase_1") != "BLOCKED"
                or gaps.get("runtime_go_no_go") != "NO_GO"
                or not all(
                    g.get("implementation_status") == "UNRESOLVED"
                    and g.get("real_world_verified") is False
                    and g.get("release_blocker") is True
                    for g in gaps["gaps"])):
            errors.append("G1_G9_NOT_BLOCKED")
    except (OSError, ValueError, KeyError, TypeError,
            AttributeError, StopIteration):
        errors.append("DRAFT_OR_REFERENCE_INVALID")
    return errors


def main() -> None:
    issues = audit()
    if issues:
        raise SystemExit("RISK-3P-13..15: FAIL\n" +
                         "\n".join("- " + x for x in issues))
    print("RISK-3P-13..15: PASS (OFFLINE FORM-08..10 DOCUMENT ONLY)")
    print("12 owner decisions NOT_RECORDED; no approved universal TTL")
    print("G1..G9 UNRESOLVED | PHASE-1 BLOCKED | runtime NO_GO")


if __name__ == "__main__":
    main()
