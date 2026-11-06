"""RISK-3P-16/17: one OFFLINE FORM/G1 evidence-readiness preflight.

Reads local repository JSON only, reports DOCUMENTARY consistency.
A PASS never means G1 accepted, evidence proven, owner approval granted,
MT4 connected or live orders safe. Does not modify anything.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_risk_3p_02_migration import TARGET as PAIRS
from scripts.review_mt4_manual_symbol_3p_v3 import FIVE


ROOT = Path(__file__).resolve().parents[1]
DRAFT = "specs/risk_3p_16_17_owner_g1_readiness_preflight_20261104.json"
FORM = "specs/p0_01_risk_formula_open_decisions.json"
OWNER = "specs/risk_3p_05_owner_review_draft_20261104.json"
FORM01 = "specs/risk_3p_06_form01_evidence_draft_20261104.json"
FORM02 = "specs/risk_3p_07_form02_stop_review_draft_20261104.json"
FORM0307 = "specs/risk_3p_08_12_form03_07_batch_review_20261104.json"
FORM0810 = "specs/risk_3p_13_15_form08_10_owner_review_20261104.json"
GATES = "specs/p0_01_d5_25_gap_verification_matrix.json"
SAFETY = "specs/source_review_priority.json"
ACCEPT = "specs/acceptance_registry.json"
V3 = "specs/mt4_manual_symbol_3p_v3_template.json"
TRACE = "specs/traceability.json"
FORM_IDS = tuple(f"FORM-{i:02d}" for i in range(1, 11))
DECISION_SOURCES = ((FORM01, 5), (FORM02, 6), (FORM0307, 20), (FORM0810, 12))
CAPS = {"individual_fraction": "0.005",
        "aggregate_fraction": "0.010", "daily_fraction": "0.015",
        "dd4_new_entry_stop": True,
        "dd5_all_close_and_human_approval": True}
KNOWN_BLOCKERS = (
    "BLOCKED_MISSING_ORIGINALS_AND_REAL_EVIDENCE",
    "PENDING_OWNER_DECISIONS", "PENDING_SCOPE_APPROVAL",
    "PENDING_SEPARATE_REAL_ENVIRONMENT_AUTHORIZATION",
    "PENDING_REAL_WORLD_EVIDENCE", "PENDING_IMPL_SPEC_APPROVAL",
    "PENDING_INDEPENDENT_ACCEPTANCE",
)


def _load(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _docs(root: Path, injected: dict | None) -> dict:
    keys = (DRAFT, FORM, OWNER, FORM01, FORM02, FORM0307, FORM0810,
            GATES, SAFETY, ACCEPT, V3, TRACE)
    return {key: (injected[key] if injected is not None and key in injected
                  else _load(root, key)) for key in keys}


def audit(root: Path = ROOT, documents: dict | None = None) -> list[str]:
    """Check an owner evidence-preparation packet without validating actual data."""
    failures: list[str] = []
    try:
        data = _docs(root, documents)
        d = data[DRAFT]
        if type(d) is not dict:
            return ["INVALID_PREFLIGHT_REGISTER"]
        if (type(d.get("schema_version")) is not int
                or d["schema_version"] != 1
                or d.get("id") != "RISK-3P-16-17-OWNER-G1-READINESS-PREFLIGHT-20261104"
                or d.get("scope") != "OFFLINE_DOCUMENTARY_PRECHECK_ONLY"):
            failures.append("PREFLIGHT_ID_OR_SCOPE")
        if (d.get("p02_reconciliation_method_owner_approved") is not True
                or d.get("p04_readonly_protocol_method_owner_approved") is not True
                or d.get("p02_p04_method_decision_ref") !=
                "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
                or d.get("p05_environment_precheck_status") != "BLOCKED_NOT_PERFORMED"):
            failures.append("P02_P04_PROCEDURAL_APPROVAL_NOT_P05_EXECUTION")
        if (d.get("g1_scope_revision_approved") is not True
                or d.get("g1_scope_decision_ref") !=
                "specs/risk_3p_28_g1_scope_owner_decision_20261104.json"):
            failures.append("SCOPE_APPROVAL_RECORD_MISSING")
        if (d.get("target_pairs") != list(PAIRS)
                or d.get("g1_fields") != list(FIVE)
                or d.get("historic_g1_attributes") != 20
                or d.get("proposed_g1_attributes") != 15
                or d.get("form_ids") != list(FORM_IDS)):
            failures.append("TARGET_FORM_G1_SCOPE")
        if d.get("unchanged_limits") != CAPS:
            failures.append("HARD_LIMITS_CHANGED")
        if (d.get("expected_form_status") != "UNDECIDED_IMPLEMENTATION_DETAIL"
                or d.get("expected_fx_saf_original") != "PENDING_ORIGINAL"
                or d.get("expected_acceptance") != "BLOCKED"
                or d.get("current_readiness") != KNOWN_BLOCKERS[0]):
            failures.append("FALSE_READINESS_DECLARATION")
        for key in ("unreviewed_auto_merge_authorized", "owner_approval_recorded",
                    "g1_real_world_verified",
                    "fx_saf_implementation_approved", "module_acceptance_approved",
                    "phase_acceptance_approved", "production_authorized",
                    "real_market_data_verified", "order_allowed",
                    "stop_release_allowed"):
            if d.get(key) is not False:
                failures.append("FALSE_AUTHORIZATION:" + key)
        if d.get("manual_main_merge_required") is not True:
            failures.append("MANUAL_MAIN_MERGE_POLICY_CHANGED")
        if (d.get("phase_1") != "BLOCKED"
                or d.get("runtime_go_no_go") != "NO_GO"
                or d.get("safety_hold_latched") is not True
                or "verified_values" not in d or d["verified_values"] is not None):
            failures.append("BLOCKED_STATE_PROMOTED")
        privacy = d.get("privacy_and_operation")
        if (type(privacy) is not dict or len(privacy) != 7
                or any(value is not False for value in privacy.values())):
            failures.append("UNAUTHORIZED_REAL_ENVIRONMENT_ACTION")
        stages = d.get("evidence_lifecycle")
        if (type(stages) is not list or len(stages) != 6
                or [v.get("status") for v in stages if type(v) is dict]
                != list(KNOWN_BLOCKERS[1:])
                or any(type(v) is not dict or v.get("authorized") is not False
                       or type(v.get("stage")) is not str
                       or type(v.get("requirement")) is not str
                       for v in stages)):
            failures.append("EVIDENCE_LIFECYCLE_FALSELY_COMPLETE")
        counts = d.get("pending_owner_decisions_by_source")
        if counts != dict(DECISION_SOURCES):
            failures.append("DECISION_SOURCE_COUNTS_CHANGED")

        form = data[FORM]
        current = {r["id"]: r for r in form["open_decisions"]}
        if (set(current) != set(FORM_IDS)
                or any(current[i].get("blocking") is not True
                       or current[i].get("owner_status")
                       != "UNDECIDED_IMPLEMENTATION_DETAIL" for i in FORM_IDS)):
            failures.append("FORM01_10_ORIGINAL_NOT_UNRESOLVED")
        fixed = form.get("adopted_fixed_controls", {})
        if (fixed.get("individual_risk_fraction_of_current_equity") != "0.005"
                or fixed.get("combined_risk_fraction_of_current_equity") != "0.010"
                or fixed.get("daily_loss_fraction_of_ny17_opening_equity") != "0.015"
                or fixed.get("aggregate_include_existing_pending_candidate") is not True
                or fixed.get("reject_uncomputable_new_order") is not True):
            failures.append("FIXED_LIMIT_SOURCE_DRIFT")
        master = data[OWNER]
        master_rows = {r["id"]: r for r in master["open_reviews"]}
        if (set(master_rows) != set(FORM_IDS)
                or any(master_rows[i].get("owner_decision") != "NOT_RECORDED"
                       or master_rows[i].get("implementation_approved") is not False
                       or master_rows[i].get("real_world_evidence_verified") is not False
                       for i in FORM_IDS)):
            failures.append("TEN_FORM_OWNER_DRAFT_FALSELY_APPROVED")
        if (master.get("phase_1") != "BLOCKED"
                or master.get("runtime_go_no_go") != "NO_GO"):
            failures.append("TEN_FORM_OWNER_DRAFT_PROMOTED")

        form01 = data[FORM01]
        if (form01.get("target_pairs") != list(PAIRS)
                or form01.get("required_g1_five_fields") != list(FIVE)
                or form01.get("target_g1_attribute_count") != 15
                or form01.get("historical_g1_attribute_count") != 20
                or form01.get("form01_implementation_approved") is not False):
            failures.append("G1_PROPOSED_3X5_SCOPE_DRIFT")
        rows = form01.get("proposed_evidence_records")
        if (type(rows) is not list or len(rows) != 3
                or [r.get("pair") for r in rows if type(r) is dict] != list(PAIRS)):
            failures.append("THREE_PAIR_EVIDENCE_ROWS_MISSING")
        else:
            for row in rows:
                pair = row["pair"]
                main = row.get("required_five")
                if (type(main) is not list or len(main) != 5
                        or [r.get("field") for r in main if type(r) is dict]
                        != list(FIVE)):
                    failures.append("G1_FIVE_FIELDS_MISSING:" + pair)
                    continue
                for item in main:
                    if (item.get("status") != "PENDING_REAL_WORLD_EVIDENCE"
                            or item.get("verified_value", "MISSING") is not None
                            or item.get("provenance_reference", "MISSING") is not None
                            or item.get("observed_at_utc", "MISSING") is not None
                            or item.get("independent_crosscheck") != "NOT_PERFORMED"):
                        failures.append("G1_FIELD_FALSELY_VERIFIED:" + pair + ":"
                                        + item["field"])
                if (row.get("owner_verified") is not False
                        or row.get("real_symbol_identity_confirmed") is not False
                        or row.get("account_identity_confirmed") is not False):
                    failures.append("G1_ACCOUNT_OR_OWNER_FALSELY_VERIFIED:" + pair)
                supplements = row.get("supplementary_checks")
                if (type(supplements) is not list or len(supplements) != 14
                        or any(type(r) is not dict
                               or r.get("status") != "PENDING_REVIEW"
                               or r.get("verified_value", "MISSING") is not None
                               or r.get("provenance_reference", "MISSING") is not None
                               for r in supplements)):
                    failures.append("G1_SUPPLEMENTAL_EVIDENCE_FALSELY_VERIFIED:" + pair)
        sources = data[FORM02], data[FORM0307], data[FORM0810]
        if ([len(form01.get("owner_decisions_to_resolve", [])),
             len(sources[0].get("owner_decisions", [])),
             len(sources[1].get("owner_decisions", [])),
             len(sources[2].get("owner_decisions", []))] != [5, 6, 20, 12]):
            failures.append("FORTY_THREE_OWNER_DECISIONS_INCOMPLETE")
        if any(x.get("owner_status") != "UNDECIDED"
               or x.get("approval_reference", "MISSING") is not None
               for x in form01["owner_decisions_to_resolve"]):
            failures.append("FORM01_OWNER_DECISION_FALSELY_APPROVED")
        if any(x.get("owner_status") != "UNDECIDED"
               or x.get("approval_reference", "MISSING") is not None
               for x in sources[0]["owner_decisions"]):
            failures.append("FORM02_OWNER_DECISION_FALSELY_APPROVED")
        for src in sources[1:]:
            if any(x.get("owner_decision") != "NOT_RECORDED"
                   or x.get("approval_reference", "MISSING") is not None
                   for x in src["owner_decisions"]):
                failures.append("FORM03_10_OWNER_DECISION_FALSELY_APPROVED")

        gates = data[GATES]
        g1 = next(g for g in gates["gaps"] if g["id"] == "G1")
        if (g1.get("implementation_status") != "UNRESOLVED"
                or g1.get("real_world_verified") is not False
                or g1.get("release_blocker") is not True
                or "3通貨ペア×5主要契約属性" not in g1.get("subject", "")):
            failures.append("FORMAL_G1_SCOPE_OR_G1_STATUS_DRIFT")
        if (len(gates["gaps"]) != 9
                or set(g["id"] for g in gates["gaps"])
                != {f"G{i}" for i in range(1, 10)}
                or any(g.get("implementation_status") != "UNRESOLVED"
                       or g.get("real_world_verified") is not False
                       or g.get("release_blocker") is not True
                       for g in gates["gaps"])):
            failures.append("ONE_OR_MORE_G1_G9_GATES_RELEASED")
        if (gates.get("phase_1") != "BLOCKED"
                or gates.get("runtime_go_no_go") != "NO_GO"
                or gates.get("verified_values", "MISSING") is not None):
            failures.append("FORMAL_RELEASE_GATE_FALSELY_ADVANCED")
        safety = data[SAFETY]
        items = safety.get("items")
        if (type(items) is not list or len(items) != 15
                or {x.get("requirement_id") for x in items if type(x) is dict}
                != {f"FX-SAF-{i:03d}" for i in range(1, 16)}
                or any(x.get("source_review") != "PENDING_ORIGINAL"
                       or x.get("human_safety_approval") is not False
                       for x in items)):
            failures.append("ORIGINAL_SAFETY_EVIDENCE_UNVERIFIED")
        acceptance = data[ACCEPT]
        phase = next(x for x in acceptance["phases"] if x["id"] == "PHASE-1")
        module = next(x for x in acceptance["modules"]
                      if x["id"] == "M-P1-FOUNDATION-DESIGN")
        if (phase.get("status") != "BLOCKED" or phase.get("approval") is not None
                or module.get("status") != "BLOCKED"
                or module.get("approval") is not None):
            failures.append("MODULE_OR_PHASE_FALSELY_ACCEPTED")
        template = data[V3]
        if ([x.get("symbol") for x in template["symbols"]] != list(PAIRS)
                or any(any(v is not None for v in row["properties"].values())
                       or any(v is not None for v in row["observation"].values())
                       for row in template["symbols"])):
            failures.append("THREE_PAIR_V3_TEMPLATE_FILLED_WITH_UNVERIFIED_VALUES")
        trace = data[TRACE]
        if any(entry.get("production_authorized") is not False
               for entry in trace["offline_synthetic_mappings"]):
            failures.append("OFFLINE_TRACEABILITY_PROMOTED")
    except (OSError, ValueError, KeyError, TypeError, AttributeError,
            StopIteration):
        failures.append("UPSTREAM_REGISTER_MALFORMED_OR_UNAVAILABLE")
    return failures


def main() -> None:
    issues = audit()
    if issues:
        raise SystemExit("RISK-3P-16/17 DOCUMENTARY PREFLIGHT FAILED:\n"
                         + "\n".join("- " + x for x in issues))
    print("RISK-3P-16/17: DOCUMENTARY CONSISTENCY PASS")
    print("READINESS: BLOCKED | FORM-01..10 UNDECIDED | 43 owner choices NOT APPROVED")
    print("G1 owner-approved 3x5: 15/15 evidence PENDING | historical 4x5 ARCHIVED")
    print("FX-SAF-001..015 PENDING_ORIGINAL | G1..G9 UNRESOLVED")
    print("PHASE-1 BLOCKED | runtime NO_GO | safety_hold_latched=true")
    print("This program never grants a broker probe, trade, merge or stop release.")


if __name__ == "__main__":
    main()
