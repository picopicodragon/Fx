"""RISK-3P-05: read-only owner-review draft consistency audit.

This is a DOCUMENT audit, not a production risk model, an approval workflow,
or evidence of broker/cloud trust. It never grants approval or changes files.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRAFT = "specs/risk_3p_05_owner_review_draft_20261104.json"
SOURCE = "specs/p0_01_risk_formula_open_decisions.json"
from scripts.audit_risk_3p_02_migration import TARGET as PAIRS, HISTORY as HISTORIC
HARD_LIMITS = {"trade": "0.005", "aggregate": "0.010",
               "daily": "0.015", "drawdown": "0.05",
               "dd4_new_entries_stopped": True}
REQUIRED_IDS = tuple(f"FORM-{i:02d}" for i in range(1, 11))


def audit(root: Path = ROOT, draft: object = None, source: object = None) -> list[str]:
    errors: list[str] = []
    try:
        d = json.loads((root / DRAFT).read_text(encoding="utf-8")) if draft is None else draft
        s = json.loads((root / SOURCE).read_text(encoding="utf-8")) if source is None else source
        if type(d) is not dict or type(s) is not dict:
            return ["INVALID_REGISTER"]
        if (d.get("schema_version") != 1
                or d.get("id") != "RISK-3P-05-OWNER-REVIEW-20261104"
                or d.get("scope") != "OWNER_DECISION_PREPARATION_ONLY"
                or d.get("source_register") != SOURCE):
            errors.append("INVALID_DRAFT_IDENTITY")
        if (d.get("historic_pair_scope") != list(HISTORIC)
                or d.get("future_design_pair_scope") != list(PAIRS)):
            errors.append("PAIR_SCOPE_CHANGED")
        if (type(d.get("old_g1_attributes")) is not int
                or d["old_g1_attributes"] != 20
                or type(d.get("proposed_g1_attributes")) is not int
                or d["proposed_g1_attributes"] != 15):
            errors.append("G1_ATTRIBUTE_SCOPE_CHANGED")
        if d.get("hard_limits_unchanged") != HARD_LIMITS:
            errors.append("HARD_LIMIT_CHANGED")
        for key in ("g1_scope_change_approved", "g1_real_world_verified",
                    "owner_approval_recorded", "fx_saf_implementation_approved",
                    "production_authorized", "real_broker_or_cloud_actions_authorized",
                    "stop_release_authorized"):
            if d.get(key) is not False:
                errors.append("FALSE_APPROVAL_OR_REAL_EVIDENCE:" + key)
        if (d.get("phase_1") != "BLOCKED"
                or d.get("runtime_go_no_go") != "NO_GO"
                or d.get("safety_hold_latched") is not True
                or "verified_values" not in d or d["verified_values"] is not None):
            errors.append("PHASE_OR_SAFETY_HOLD_PROMOTED")
        if s.get("status") != "OPEN_DESIGN_DECISIONS_ONLY":
            errors.append("SOURCE_REGISTER_NOT_OPEN")
        accepted = s.get("adopted_fixed_controls", {})
        if (accepted.get("individual_risk_fraction_of_current_equity") != HARD_LIMITS["trade"]
                or accepted.get("combined_risk_fraction_of_current_equity") != HARD_LIMITS["aggregate"]
                or accepted.get("daily_loss_fraction_of_ny17_opening_equity") != HARD_LIMITS["daily"]
                or accepted.get("aggregate_include_existing_pending_candidate") is not True
                or accepted.get("reject_uncomputable_new_order") is not True):
            errors.append("FIXED_CONTROL_SOURCE_MISMATCH")
        source_rows = s.get("open_decisions")
        draft_rows = d.get("open_reviews")
        if type(source_rows) is not list or type(draft_rows) is not list:
            return errors + ["MISSING_OPEN_DECISIONS"]
        source_ids = [r.get("id") for r in source_rows if type(r) is dict]
        draft_ids = [r.get("id") for r in draft_rows if type(r) is dict]
        if source_ids != list(REQUIRED_IDS) or draft_ids != source_ids:
            errors.append("FORM_ID_SET_DRIFT")
        source_map = {r["id"]: r for r in source_rows if type(r) is dict and type(r.get("id")) is str}
        for record in draft_rows:
            if type(record) is not dict or type(record.get("id")) is not str:
                errors.append("MALFORMED_DRAFT_ROW")
                continue
            row_id = record["id"]
            original = source_map.get(row_id)
            if original is None:
                errors.append("UNEXPECTED_FORM_ID")
                continue
            if (record.get("original_owner_status") != original.get("owner_status")
                    or record.get("original_blocking") is not True
                    or original.get("blocking") is not True
                    or original.get("owner_status") != "UNDECIDED_IMPLEMENTATION_DETAIL"
                    or record.get("topic") != original.get("topic")):
                errors.append("FORM_ORIGINAL_SOURCE_DRIFT:" + row_id)
            expected = ("DIRECT_CHANGE_REVIEW_REQUIRED"
                        if row_id in REQUIRED_IDS[:7] else "RETAIN_EXISTING_GATE")
            if record.get("three_pair_impact") != expected:
                errors.append("FORM_IMPACT_SCOPE_DRIFT:" + row_id)
            if (record.get("owner_decision") != "NOT_RECORDED"
                    or record.get("approval_reference", "MISSING") is not None
                    or record.get("implementation_approved") is not False
                    or record.get("real_world_evidence_verified") is not False
                    or record.get("proposed_only") is not True):
                errors.append("FALSE_FORM_APPROVAL:" + row_id)
            if (type(record.get("recommendation")) is not str
                    or not record["recommendation"]
                    or type(record.get("required_evidence")) is not list
                    or not record["required_evidence"]
                    or any(type(item) is not str or not item
                           for item in record["required_evidence"])):
                errors.append("FORM_EVIDENCE_OR_RECOMMENDATION_MISSING:" + row_id)
        if d.get("previous_offline_test_scope") != [
                "RISK-3P-01", "RISK-3P-02", "RISK-3P-03", "RISK-3P-04"]:
            errors.append("SYNTHETIC_SCOPE_FALSELY_EXTENDED")
        if (type(d.get("decision_sequence")) is not list
                or len(d["decision_sequence"]) != 5):
            errors.append("DECISION_SEQUENCE_MISSING")
        return errors
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return errors + ["INVALID_DRAFT_OR_SOURCE_FILE"]


def main() -> None:
    errors = audit()
    if errors:
        raise SystemExit("RISK-3P-05 OWNER REVIEW: FAIL\n" +
                         "\n".join("- " + error for error in errors))
    print("RISK-3P-05 OWNER REVIEW: PASS (DOCUMENT-ONLY)")
    print("FORM-01..10: all UNDECIDED_IMPLEMENTATION_DETAIL")
    print("USD/JPY, EUR/JPY, EUR/USD: DESIGN SCOPE ONLY")
    print("G1 3x5: PROPOSED AND UNVERIFIED; HISTORIC 4x5: BLOCKED")
    print("PHASE-1 BLOCKED | runtime NO_GO | safety_hold_latched=true")


if __name__ == "__main__":
    main()
