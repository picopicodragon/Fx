"""RISK-3P-20..22: audit only the G1 acceptance rubric and 43 owner choices.

A PASS is documentary source consistency, NOT a valid G1 value, approved
broker observation, implementation decision, release gate or order permission.
Reads versioned repository files only and never writes or connects anywhere.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.review_mt4_manual_symbol_3p_v3 import PAIRS, FIVE


ROOT = Path(__file__).resolve().parents[1]
RUBRIC = "specs/risk_3p_20_g1_acceptance_rubric_20261104.json"
DOCKET = "specs/risk_3p_22_form43_owner_review_docket_20261104.json"
PROTOCOL = "specs/risk_3p_18_19_g1_readonly_provenance_protocol_20261104.json"
FORM01 = "specs/risk_3p_06_form01_evidence_draft_20261104.json"
FORM02 = "specs/risk_3p_07_form02_stop_review_draft_20261104.json"
FORM0307 = "specs/risk_3p_08_12_form03_07_batch_review_20261104.json"
FORM0810 = "specs/risk_3p_13_15_form08_10_owner_review_20261104.json"
FORM_BASE = "specs/p0_01_risk_formula_open_decisions.json"
GATES = "specs/p0_01_d5_25_gap_verification_matrix.json"
V3 = "specs/mt4_manual_symbol_3p_v3_template.json"
FORM_IDS = tuple(f"FORM-{i:02d}" for i in range(1, 11))
REVIEW_ORDER = (1, 2, 5, 6, 3, 4, 7, 8, 9, 10)
COMMON_CHECKS = (
    "SEPARATELY_AUTHORIZED_READ_ONLY_OBSERVATION",
    "EXACT_TERMINAL_SYMBOL_AND_ACCOUNT_ENVIRONMENT_MATCH",
    "BROKER_ORIGINAL_SOURCE_AT_UTC",
    "UNITS_AND_LOT_BASIS_EXPLICIT",
    "INDEPENDENT_NON_DUPLICATED_CHECK",
    "SOURCE_AGE_AND_CONTRACT_CHANGE_RULE_APPROVED",
    "HUMAN_EVIDENCE_REVIEW_REFERENCE",
    "NO_OPEN_POSITION_OR_EA_SIDE_EFFECTS",
)
PER_FIELD_CHECKS = {
    "min_lot": (
        "LOT_MIN_BASE_UNITS_CONFIRMED", "ORDER_SIZE_LATTICE_CHECK",
        "CONTRACT_ACCOUNT_MATCH",
    ),
    "lot_step": (
        "LOT_INCREMENT_BROKER_RULE_CONFIRMED", "MIN_MAX_STEP_CONSISTENCY_CHECK",
        "NO_LOT_ROUND_UP_WITHOUT_RISK",
    ),
    "point_quote": (
        "POINT_QUOTE_UNIT_PROVEN", "DIGITS_AND_POINT_INDEPENDENT_CONSISTENCY",
        "NO_PIP_POINT_ALIAS_ASSUMPTION",
    ),
    "tick_size_points": (
        "TICK_SIZE_UNIT_PROVEN", "POINT_TO_TICK_SCALE_INDEPENDENTLY_CHECKED",
        "NO_IMPLICIT_TICK_EQUALS_POINT",
    ),
    "tick_value_deposit_currency": (
        "TICK_VALUE_LOT_BASIS_PROVEN",
        "DEPOSIT_CURRENCY_AND_QUOTE_CURRENCY_MATCHED",
        "EURUSD_DYNAMIC_USD_TO_JPY_REFERENCE_UNAPPROVED",
    ),
}
SOURCE_COUNTS = {FORM01: 5, FORM02: 6, FORM0307: 20, FORM0810: 12}
FORM_TOPICS = {
    "FORM-01": ("G1_CONTRACT_EVIDENCE", FORM01,
                "FULL_CONTRACT_G1_PROVENANCE_REQUIRED"),
    "FORM-02": ("ORDER_AND_STOP_EXECUTION", FORM02,
                "BROKER_STOP_AND_FILL_EVIDENCE_REQUIRED"),
    "FORM-03": ("USD_TO_JPY_CONVERSION", FORM0307,
                "CURRENCY_SIDE_RATE_AND_UNITS_REQUIRED"),
    "FORM-04": ("TRANSACTION_COST_BOUND", FORM0307,
                "ACTUAL_FEES_AND_GAP_SCENARIO_REQUIRED"),
    "FORM-05": ("ACCOUNT_ORDER_RECONCILIATION", FORM0307,
                "SINGLE_GENERATION_ORDER_ID_AND_RESERVATION_REQUIRED"),
    "FORM-06": ("AGGREGATE_GROSS_AND_PENDING", FORM0307,
                "PENDING_OCO_PARTIAL_FILL_STRESS_EVIDENCE_REQUIRED"),
    "FORM-07": ("LOT_AND_CURRENCY_PRECISION", FORM0307,
                "BROKER_LOT_GRID_AND_DECIMAL_BOUNDARY_REQUIRED"),
    "FORM-08": ("NY17_DAILY_LEDGER", FORM0810,
                "NY17_BOOKING_PNL_AND_CASHFLOW_POLICY_REQUIRED"),
    "FORM-09": ("DRAWNDOWN_HWM_LATCH", FORM0810,
                "UNITIZED_HWM_AND_STOP_RESTART_EVIDENCE_REQUIRED"),
    "FORM-10": ("CLOCK_PROVENANCE_AND_FRESHNESS", FORM0810,
                "SOURCE_SPECIFIC_TTL_AND_CLOCK_EVIDENCE_REQUIRED"),
}
SAFETY_DEPENDENCIES = [f"G{i}" for i in range(1, 10)] + [
    "FX-SAF-001", "FX-SAF-002", "Q109", "Q110", "Q112", "Q115",
]
EMPTY_FIELDS = (
    "verified_value", "recorded_unit", "account_environment_alias",
    "terminal_symbol", "primary_source_reference",
    "independent_source_reference", "observed_at_utc",
    "primary_issuer", "independent_issuer",
    "source_freshness_policy_reference", "change_control_reference",
    "human_evidence_review_reference",
)


def read(root: Path, filename: str) -> dict:
    return json.loads((root / filename).read_text(encoding="utf-8"))


def documents(root: Path = ROOT, injected: dict | None = None) -> dict:
    paths = (RUBRIC, DOCKET, PROTOCOL, FORM01, FORM02,
             FORM0307, FORM0810, FORM_BASE, GATES, V3)
    return {
        path: (injected[path] if injected is not None and path in injected
               else read(root, path)) for path in paths
    }


def _source_decisions(docs: dict) -> dict[str, dict]:
    source: dict[str, dict] = {}
    for filename in SOURCE_COUNTS:
        doc = docs[filename]
        original = (doc["owner_decisions_to_resolve"] if filename == FORM01
                    else doc["owner_decisions"])
        if type(original) is not list or len(original) != SOURCE_COUNTS[filename]:
            raise ValueError("source decision count mismatch")
        for row in original:
            item_id = row["id"]
            if item_id in source:
                raise ValueError("duplicate owner decision")
            source[item_id] = {
                "question": row["question"],
                "recommendation": row.get("recommendation", row.get("proposal")),
                "source": filename,
                "owner_status": row.get("owner_status", row.get("owner_decision")),
                "approval_reference": row.get("approval_reference"),
            }
    return source


def audit(root: Path = ROOT, *, injected: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        d = documents(root, injected)
        rubric, docket = d[RUBRIC], d[DOCKET]
        if type(rubric) is not dict or type(docket) is not dict:
            return ["INVALID_REVIEW_REGISTERS"]
        if (type(rubric.get("schema_version")) is not int
                or rubric["schema_version"] != 1
                or rubric.get("id") != "RISK-3P-20-G1-15-FIELD-ACCEPTANCE-RUBRIC-DRAFT-20261104"
                or rubric.get("scope") !=
                "DOCUMENTARY_ACCEPTANCE_CRITERIA_DRAFT_NO_REAL_EVIDENCE"
                or rubric.get("criteria_status") != "PROPOSED_FOR_OWNER_REVIEW_ONLY"):
            errors.append("RUBRIC_IDENTITY_OR_REVIEW_SCOPE_DRIFT")
        if (rubric.get("target_pairs") != list(PAIRS)
                or rubric.get("fields") != list(FIVE)
                or rubric.get("field_count_expected") != 15
                or type(rubric.get("verified_count")) is not int
                or rubric["verified_count"] != 0
                or rubric.get("historical_g1") != "4_PAIRS_X_5_FIELDS_UNRESOLVED_PRESERVED"
                or rubric.get("proposed_g1") != "3_PAIRS_X_5_FIELDS_OWNER_SCOPE_APPROVED_UNVERIFIED"
                or rubric.get("g1_formal_scope_approved") is not True
                or rubric.get("scope_decision_ref") !=
                "specs/risk_3p_28_g1_scope_owner_decision_20261104.json"):
            errors.append("G1_FIFTEEN_ITEM_SCOPE_DRIFT")
        if rubric.get("common_required_checks") != list(COMMON_CHECKS):
            errors.append("COMMON_EVIDENCE_CHECKS_DROPPED")
        if rubric.get("field_specific_checks") != {
                field: list(values) for field, values in PER_FIELD_CHECKS.items()}:
            errors.append("FIELD_UNIT_OR_RISK_CHECKS_DROPPED")
        rows = rubric.get("rows")
        expected_pairs = [(pair, field) for pair in PAIRS for field in FIVE]
        if (type(rows) is not list or len(rows) != 15
                or [(r.get("pair"), r.get("field")) for r in rows if type(r) is dict]
                != expected_pairs):
            errors.append("G1_RUBRIC_ROWS_MISSING")
        else:
            for row in rows:
                key = row["pair"] + ":" + row["field"]
                if (row.get("readiness") != "PENDING_REAL_WORLD_EVIDENCE"
                        or row.get("acceptance") != "NOT_EVALUATED"
                        or any(field not in row or row[field] is not None
                               for field in EMPTY_FIELDS)
                        or row.get("required_checks") != (
                            list(COMMON_CHECKS) +
                            list(PER_FIELD_CHECKS[row["field"]]))
                        or row.get("checks_passed") != []
                        or row.get("missing_evidence_expected") is not True
                        or row.get("real_world_verified") is not False
                        or row.get("form01_implementation_approved") is not False
                        or row.get("g1_release_authorized") is not False):
                    errors.append("G1_FIELD_FALSELY_ACCEPTED:" + key)
        if (rubric.get("pending_additional_requirements") != [
                "FORM01_10_ALL_PENDING", "FX_SAF_001_015_ORIGINALS_PENDING",
                "G1_G9_UNRESOLVED", "TRADE_AND_STOP_LOGIC_NOT_AUTHORIZED",
                "MT4_SINGLE_SESSION_OBSERVATION_NOT_APPROVED",
                "QUOTED_TICK_VALUE_IS_NOT_PROOF_OF_JPY_RISK"]):
            errors.append("DEPENDENT_GATES_DROPPED")
        expected_approvals = {
            "human_review_signoff": False,
            "market_watch_access_approved": False,
            "real_account_verification": False,
            "broker_contract_verified": False,
            "production_authorized": False, "live_order_allowed": False,
            "stop_release_allowed": False, "manual_main_merge_required": True,
        }
        if rubric.get("explicit_non_approvals") != expected_approvals:
            errors.append("RUBRIC_FALSE_AUTHORIZATION")
        if (rubric.get("phase_1") != "BLOCKED"
                or rubric.get("runtime_go_no_go") != "NO_GO"
                or rubric.get("safety_hold_latched") is not True
                or "verified_values" not in rubric
                or rubric["verified_values"] is not None):
            errors.append("RUBRIC_STOP_STATE_PROMOTED")
        protocol = d[PROTOCOL]
        actual = protocol["proposed_observations"]
        if (len(actual) != 15
                or [(r["pair"], r["field"]) for r in actual] != expected_pairs
                or any(r.get("status") != "NOT_OBSERVED"
                       or r.get("real_world_verified") is not False
                       or r.get("verified_value", "MISSING") is not None
                       for r in actual)
                or protocol.get("owner_approved_real_read") is not False):
            errors.append("OBSERVATION_PROTOCOL_FALSELY_ADVANCED")
        v3 = d[V3]
        if ([r["symbol"] for r in v3["symbols"]] != list(PAIRS)
                or any(any(value is not None for value in row["properties"].values())
                       or any(value is not None for value in row["observation"].values())
                       for row in v3["symbols"])):
            errors.append("MT4_V3_UNVERIFIED_VALUES_FILLED")

        if (docket.get("schema_version") != 1
                or docket.get("id") !=
                "RISK-3P-22-FORM-ALL-43-OWNER-REVIEW-DOCKET-20261104"
                or docket.get("scope") != "NO_DECISION_AUTOMATION_OFFLINE_REVIEW_ONLY"
                or docket.get("three_pair_design") != list(PAIRS)
                or docket.get("expected_total") != 43
                or docket.get("sort_order") !=
                "BY_FORM_AND_SOURCE_ROW_WITH_INDEPENDENT_REVIEW_PRIORITY"):
            errors.append("DOCKET_IDENTITY_OR_SCOPE_DRIFT")
        base = d[FORM_BASE]
        if (len(base["open_decisions"]) != 10
                or [r["id"] for r in base["open_decisions"]] != list(FORM_IDS)
                or any(r.get("owner_status") != "UNDECIDED_IMPLEMENTATION_DETAIL"
                       or r.get("blocking") is not True
                       for r in base["open_decisions"])):
            errors.append("FORM_SOURCE_NOT_ALL_UNDECIDED")
        sources = _source_decisions(d)
        if len(sources) != 43:
            errors.append("FORTY_THREE_SOURCE_DECISIONS_NOT_FOUND")
        groups = docket.get("form_groups")
        if (type(groups) is not list or len(groups) != 10
                or [r.get("form_id") for r in groups if type(r) is dict]
                != list(FORM_IDS)):
            errors.append("FORM_GROUP_SCOPE_CHANGED")
        else:
            for row in groups:
                form_id = row["form_id"]
                topic, source, requirement = FORM_TOPICS[form_id]
                idx = int(form_id[-2:])
                count = sum(x["source"] == source and
                            (x_id.startswith(f"F{idx:02d}-") or
                             x_id.startswith(f"FORM{idx:02d}-"))
                            for x_id, x in sources.items())
                if (row.get("topic") != topic or row.get("source") != source
                        or row.get("review_sequence") != REVIEW_ORDER[idx-1]
                        or row.get("required_evidence_gate") != requirement
                        or row.get("expected_decision_count") != count
                        or row.get("form_implementation_approved") is not False
                        or row.get("review_packet_ready") is not False
                        or row.get("status") != "UNDECIDED_IMPLEMENTATION_DETAIL"):
                    errors.append("FORM_GROUP_FALSELY_REVIEWED:" + form_id)
        decision_rows = docket.get("decisions")
        if (type(decision_rows) is not list
                or len(decision_rows) != 43
                or len({r.get("id") for r in decision_rows if type(r) is dict}) != 43
                or set(r.get("id") for r in decision_rows if type(r) is dict)
                != set(sources)):
            errors.append("DECISION_ROWS_MISSING_DUPLICATE_OR_UNEXPECTED")
        else:
            expected_ids = [item["id"] for item in d[FORM01]["owner_decisions_to_resolve"]]
            expected_ids += [item["id"] for item in d[FORM02]["owner_decisions"]]
            expected_ids += [item["id"] for item in d[FORM0307]["owner_decisions"]]
            expected_ids += [item["id"] for item in d[FORM0810]["owner_decisions"]]
            if [r["id"] for r in decision_rows] != expected_ids:
                errors.append("DECISION_SOURCE_ORDER_CHANGED")
            for item in decision_rows:
                ident = item["id"]
                match = sources[ident]
                part = ident.replace("FORM", "F")
                form_number = int(part[1:3])
                form_id = f"FORM-{form_number:02d}"
                topic, src, evidence = FORM_TOPICS[form_id]
                if (item.get("form_id") != form_id
                        or item.get("source") != src
                        or item.get("topic") != topic
                        or item.get("review_sequence") != REVIEW_ORDER[form_number-1]
                        or item.get("original_question") != match["question"]
                        or item.get("source_recommendation") != match["recommendation"]
                        or item.get("required_evidence_gate") != evidence):
                    errors.append("DECISION_SOURCE_PROVENANCE_DRIFT:" + ident)
                if (item.get("choice_classification") !=
                    "UNRESOLVED_SAFETY_IMPLEMENTATION"
                        or item.get("candidate_only") is not True
                        or item.get("owner_decision") != "NOT_RECORDED"
                        or item.get("human_approval_reference", "MISSING") is not None
                        or item.get("original_record_verified") is not False
                        or item.get("independent_real_world_evidence_verified") is not False
                        or item.get("implementation_approved") is not False
                        or item.get("ready_for_owner_signoff") is not False):
                    errors.append("DECISION_FALSELY_APPROVED:" + ident)
                if match["approval_reference"] is not None or match["owner_status"] not in (
                        "UNDECIDED", "NOT_RECORDED"):
                    errors.append("DECISION_UPSTREAM_FALSELY_APPROVED:" + ident)
        policy = docket.get("owner_review_policy")
        if (type(policy) is not dict
                or policy.get("allow_batch_questionnaire_preparation") is not True
                or any(policy.get(name) is not False for name in (
                    "allow_implicit_owner_approval",
                    "allow_unverified_original_as_approval",
                    "allow_ai_assumed_broker_values",
                    "allow_g1_release_on_form_review",
                    "allow_live_test_without_separate_authorization"))
                or policy.get("requires_explicit_spec_id_version_and_approval_reference") is not True
                or policy.get("requires_original_source_or_explicit_derived_requirement_resolution") is not True
                or policy.get("automated_review_outcome") != "BLOCKED_NOT_SIGNABLE"):
            errors.append("OWNER_REVIEW_POLICY_WEAKENED")
        if docket.get("gate_dependencies") != SAFETY_DEPENDENCIES:
            errors.append("REQUIRED_SAFETY_DEPENDENCY_MISSING")
        for key in (
            "real_world_evidence_collected", "owner_implementation_decisions_recorded",
            "form01_10_implementation_approved", "g1_3x5_accepted",
            "risk_model_approved", "production_authorized", "order_allowed",
            "stop_release_allowed", "main_automerge_authorized",
        ):
            if docket.get(key) is not False:
                errors.append("DOCKET_FALSE_AUTHORIZATION:" + key)
        if (docket.get("phase_1") != "BLOCKED"
                or docket.get("runtime_go_no_go") != "NO_GO"
                or docket.get("safety_hold_latched") is not True
                or docket.get("verified_values", "MISSING") is not None):
            errors.append("DOCKET_STOP_STATE_PROMOTED")
        gaps = d[GATES]
        if (len(gaps["gaps"]) != 9
                or any(g.get("implementation_status") != "UNRESOLVED"
                       or g.get("real_world_verified") is not False
                       or g.get("release_blocker") is not True
                       for g in gaps["gaps"])
                or gaps.get("runtime_go_no_go") != "NO_GO"
                or gaps.get("phase_1") != "BLOCKED"):
            errors.append("G1_G9_PREMATURELY_RELEASED")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        errors.append("MALFORMED_OR_MISSING_REVIEW_SOURCE")
    return errors


def main() -> None:
    errors = audit()
    if errors:
        raise SystemExit("RISK-3P-20..22 AUDIT: FAIL\n" +
                         "\n".join("- " + x for x in errors))
    print("RISK-3P-20..22: PASS (DOCUMENTARY CONSISTENCY ONLY)")
    print("G1 3x5: 15/15 PENDING; 11 checklist conditions per field, none completed")
    print("FORM-01..10: 43/43 decision rows NOT_RECORDED")
    print("G1..G9 UNRESOLVED | PHASE-1 BLOCKED | runtime NO_GO")
    print("No real broker proof, owner approval, order authorization or STOP release")


if __name__ == "__main__":
    main()
