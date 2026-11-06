"""Read-only offline owner gate audit for batched FORM-03..07 review.

A clean result confirms only that draft records do not falsely claim approval.
Does not run MT4, verify monetary risk, modify files, or grant trade rights.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.phase1_three_pair_synthetic_stop_conversion import PAIRS


ROOT = Path(__file__).resolve().parents[1]
DRAFT = "specs/risk_3p_08_12_form03_07_batch_review_20261104.json"
SOURCE = "specs/p0_01_risk_formula_open_decisions.json"
GATES = "specs/p0_01_d5_25_gap_verification_matrix.json"
FORM_IDS = ("FORM-03", "FORM-04", "FORM-05", "FORM-06", "FORM-07")
RISK_IDS = ("RISK-3P-08", "RISK-3P-09", "RISK-3P-10",
            "RISK-3P-11", "RISK-3P-12")
CAPS = {"individual": "0.005", "aggregate": "0.010",
        "daily": "0.015", "max_drawdown": "0.05",
        "dd4_no_new_orders": True}
REQUIRED_UPSTREAM = ("RISK-3P-03", "RISK-3P-04", "RISK-3P-05",
                     "RISK-3P-06", "RISK-3P-07")
REQUIRED_DOWNSTREAM = ("G1", "FORM-01", "FORM-02",
                       "FORM-08", "FORM-09", "FORM-10",
                       "FX-SAF-001", "FX-SAF-002")


def _read(root: Path, filename: str) -> dict:
    return json.loads((root / filename).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, draft: object = None) -> list[str]:
    errors: list[str] = []
    try:
        d = _read(root, DRAFT) if draft is None else draft
        if type(d) is not dict:
            return ["INVALID_REGISTER"]
        if (type(d.get("schema_version")) is not int or
                d["schema_version"] != 1 or
                d.get("id") !=
                "RISK-3P-08-12-FORM03-07-BATCH-OWNER-REVIEW-20261104" or
                d.get("scope") !=
                "OFFLINE_SYNTHETIC_BATCH_AND_OWNER_REVIEW_ONLY"):
            errors.append("DRAFT_ID_OR_SCOPE_INVALID")
        if d.get("design_pairs") != list(PAIRS):
            errors.append("THREE_PAIR_SCOPE_DRIFT")
        if (d.get("upstream_drafts") != list(REQUIRED_UPSTREAM)
                or d.get("downstream_unresolved") != list(REQUIRED_DOWNSTREAM)):
            errors.append("UPSTREAM_OR_UNRESOLVED_GATES_DROPPED")
        if d.get("existing_caps") != CAPS:
            errors.append("FIXED_CAPS_CHANGED")
        for name in ("real_loss_bound_verified",
                     "form03_07_owner_approval_recorded",
                     "g1_scope_change_approved",
                     "fx_saf_implementation_approved",
                     "production_authorized",
                     "broker_connection_authorized",
                     "mt4_script_execution_authorized",
                     "order_allowed", "stop_release_allowed",
                     "allow_unreviewed_main_merge"):
            if d.get(name) is not False:
                errors.append("FALSE_AUTHORIZATION:" + name)
        if (d.get("runtime_go_no_go") != "NO_GO"
                or d.get("phase_1") != "BLOCKED"
                or d.get("safety_hold_latched") is not True
                or d.get("verified_values", "MISSING") is not None):
            errors.append("BLOCKED_STATUS_PROMOTED")
        if (d.get("simulated_fx_loss_conversion") !=
                "POSITIVE_USD_QUOTE_LOSS_MULTIPLIED_BY_SYNTHETIC_USDJPY_ASK_ONLY"
                or d.get("simulated_cost_modes") !=
                ["ADDITIONAL", "INCLUDED_IN_BASE"]
                or d.get("simulated_risk_segments") !=
                ["POSITION", "PENDING", "CANDIDATE", "RESERVED"]
                or d.get("simulated_partial_portions") !=
                ["WHOLE", "FILLED", "REMAINDER"]):
            errors.append("SYNTHETIC_ASSUMPTION_SCOPE_CHANGED")
        source = _read(root, SOURCE)
        src = {row["id"]: row for row in source["open_decisions"]}
        forms = d.get("forms")
        if (type(forms) is not list
                or [x.get("form_id") for x in forms if type(x) is dict]
                != list(FORM_IDS)
                or [x.get("risk_id") for x in forms if type(x) is dict]
                != list(RISK_IDS)):
            errors.append("FIVE_FORM_SCOPE_DRIFT")
        else:
            for entry in forms:
                form = entry["form_id"]
                if (src[form].get("owner_status") != "UNDECIDED_IMPLEMENTATION_DETAIL"
                        or src[form].get("blocking") is not True
                        or entry.get("source_form_status") != src[form]["owner_status"]):
                    errors.append("HISTORIC_FORM_GATE_MODIFIED:" + form)
                if (entry.get("owner_approval_recorded") is not False
                        or entry.get("implementation_approved") is not False
                        or entry.get("real_world_verified") is not False):
                    errors.append("FALSE_FORM_APPROVAL:" + form)
                if (type(entry.get("recommendation")) is not str
                        or not entry["recommendation"]
                        or type(entry.get("unresolved")) is not list
                        or len(entry["unresolved"]) < 3
                        or any(type(q) is not str or not q for q in entry["unresolved"])):
                    errors.append("MISSING_FORM_EVIDENCE_PLAN:" + form)
        decisions = d.get("owner_decisions")
        expected_ids = [
            f"FORM{i:02d}-{n}" for i in range(3, 8) for n in range(1, 5)
        ]
        if (type(decisions) is not list
                or [x.get("id") for x in decisions if type(x) is dict]
                != expected_ids):
            errors.append("OWNER_DECISION_SET_DRIFT")
        else:
            for row in decisions:
                if (row.get("owner_decision") != "NOT_RECORDED"
                        or row.get("approval_reference", "MISSING") is not None
                        or row.get("real_world_evidence_verified") is not False
                        or row.get("proposal_status") != "PROPOSED_NOT_APPROVED"
                        or type(row.get("question")) is not str
                        or not row["question"]):
                    errors.append("FALSE_OWNER_APPROVAL:" + row["id"])
        gaps = _read(root, GATES)
        if (gaps.get("phase_1") != "BLOCKED"
                or gaps.get("runtime_go_no_go") != "NO_GO"
                or not all(
                    row.get("implementation_status") == "UNRESOLVED"
                    and row.get("real_world_verified") is False
                    and row.get("release_blocker") is True
                    for row in gaps["gaps"])):
            errors.append("G1_G9_FALSELY_RESOLVED")
    except (OSError, ValueError, KeyError, TypeError,
            AttributeError, StopIteration):
        errors.append("DRAFT_OR_UPSTREAM_REGISTER_INVALID")
    return errors


def main() -> None:
    issues = audit()
    if issues:
        raise SystemExit("RISK-3P-08..12: FAIL\n" +
                         "\n".join("- " + i for i in issues))
    print("RISK-3P-08..12: PASS (OFFLINE FIVE-FORM REVIEW ONLY)")
    print("FORM-03..07: all 20 owner decisions NOT_RECORDED")
    print("G1..G9 UNRESOLVED | PHASE-1 BLOCKED | NO_GO")
    print("Batch PR does not authorize main merge, broker access or trading")


if __name__ == "__main__":
    main()
