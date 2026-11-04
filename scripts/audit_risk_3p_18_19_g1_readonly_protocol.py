"""RISK-3P-18/19: static G1 observation SOP and provenance preflight.

The only output is a documentary consistency finding: it does not see MT4,
query an account, authorize future observation, verify actual contract facts,
or grant any order/SL/STOP permissions. Never writes files.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.review_mt4_manual_symbol_3p_v3 import PAIRS, FIVE
from scripts.audit_risk_3p_16_17_owner_g1_readiness import GATES, FORM01, V3


ROOT = Path(__file__).resolve().parents[1]
PLAN = "specs/risk_3p_18_19_g1_readonly_provenance_protocol_20261104.json"
PREVIOUS = "specs/risk_3p_16_17_owner_g1_readiness_preflight_20261104.json"
ABORTS = tuple(f"P18-{i:02d}" for i in range(1, 8))
STEPS = tuple(f"OBS-{i:02d}" for i in range(1, 7))
REQUIRED_PER_FIELD = (
    "account_environment_alias_consistent_without_real_identifier",
    "exact_mt4_terminal_symbol_name_from_observed_terminal",
    "captured_utc_timestamp_and_source_kind",
    "explicit_numeric_unit_and_broker_contract_definition",
    "second_independent_reference_or_documented_gap",
    "contract_change_or_staleness_recheck",
    "human_evidence_review_reference_with_no_sensitive_payload",
)
SAFE_ACTIONS = ("DOCUMENT_REVIEW", "OFFLINE_SYNTHETIC_TESTS", "PR_DIFF_AND_CI_REVIEW")
PROHIBITED = (
    "OPEN_OR_LOGIN_MT4", "START_OR_DISABLE_EA", "MODIFY_AUTOTRADING",
    "MODIFY_OPEN_POSITION", "MODIFY_STOP_LOSS", "SEND_ORDER",
    "CREATE_DEMO_ACCOUNT", "UPLOAD_PRIVATE_BROKER_VALUES",
    "DECLARE_G1_VERIFIED", "RELEASE_SAFETY_HOLD",
)
EMPTY_OBSERVATION = (
    "verified_value", "unit_provenance", "terminal_symbol",
    "account_environment_alias", "observation_at_utc",
    "broker_source_reference", "independent_source_reference",
)


def _read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, *, injected: dict | None = None) -> list[str]:
    """Fail closed when a documentary plan implies any proof or execution."""
    failures: list[str] = []
    try:
        paths = (PLAN, PREVIOUS, GATES, FORM01, V3)
        docs = {
            key: (injected[key] if injected is not None and key in injected
                  else _read(root, key)) for key in paths
        }
        doc = docs[PLAN]
        if type(doc) is not dict:
            return ["PLAN_NOT_A_DOCUMENT"]
        if (type(doc.get("schema_version")) is not int
                or doc.get("schema_version") != 1
                or doc.get("id") != "RISK-3P-18-19-G1-READONLY-PROVENANCE-PROTOCOL-20261104"
                or doc.get("scope") != "DOCUMENT_ONLY_NO_MT4_ACCESS_OR_EVIDENCE_COLLECTION"):
            failures.append("DOCUMENT_IDENTITY_OR_SCOPE_CHANGED")
        if (doc.get("g1_3x5_scope_approved") is not True
                or doc.get("g1_scope_decision_ref") !=
                "specs/risk_3p_28_g1_scope_owner_decision_20261104.json"):
            failures.append("G1_OWNER_APPROVED_SCOPE_REFERENCE_MISSING")
        if (doc.get("target_pairs") != list(PAIRS)
                or doc.get("expected_g1_items") != 15
                or doc.get("historical_scope_retained") != "LEGACY_4X5_UNRESOLVED"
                or doc.get("proposed_scope") != "FORMAL_OWNER_APPROVED_3X5_UNVERIFIED"):
            failures.append("PAIR_SCOPE_OR_G1_HISTORY_DRIFT")
        for key in (
            "evidence_collected", "owner_approved_real_read",
            "g1_real_world_verified",
            "fx_saf_implementation_approved", "production_authorized",
            "order_allowed", "stop_release_allowed", "auto_merge_authorized",
        ):
            if doc.get(key) is not False:
                failures.append("FALSE_AUTHORIZATION:" + key)
        if (doc.get("human_manual_merge_required") is not True
                or doc.get("allowed_actions_now") != list(SAFE_ACTIONS)
                or doc.get("forbidden_actions_now") != list(PROHIBITED)):
            failures.append("UNAUTHORIZED_OPERATION_OR_MERGE")
        if (doc.get("phase_1") != "BLOCKED"
                or doc.get("runtime_go_no_go") != "NO_GO"
                or doc.get("safety_hold_latched") is not True
                or "verified_values" not in doc or doc["verified_values"] is not None):
            failures.append("STOP_LATCH_OR_PHASE_PROMOTED")
        methods = doc.get("field_methodology")
        if (type(methods) is not list or len(methods) != len(FIVE)
                or [x.get("field") for x in methods if type(x) is dict]
                != list(FIVE)):
            failures.append("FIVE_CONTRACT_METHODS_INCOMPLETE")
        else:
            for row in methods:
                name = row["field"]
                if (row.get("ui_field_presence") != "UNKNOWN_NOT_VISUALLY_CONFIRMED"
                        or row.get("independent_source_available") is not False
                        or row.get("assumption_is_broker_verified") is not False
                        or row.get("cannot_use_digits_or_pip_proxy_without_unit_proof") is not True
                        or any(type(row.get(key)) is not str or not row[key]
                               for key in ("meaning", "manual_display_hint",
                                           "independent_evidence_type",
                                           "why_no_shortcut"))):
                    failures.append("FALSE_FIELD_SOURCE_ASSURANCE:" + name)
        records = doc.get("proposed_observations")
        expected = [(pair, field) for pair in PAIRS for field in FIVE]
        if (type(records) is not list or len(records) != 15
                or [(x.get("pair"), x.get("field")) for x in records
                    if type(x) is dict] != expected):
            failures.append("MISSING_OR_RELABELED_OBSERVATIONS")
        else:
            for item in records:
                ident = item["pair"] + ":" + item["field"]
                if (item.get("status") != "NOT_OBSERVED"
                        or any(key not in item or item[key] is not None
                               for key in EMPTY_OBSERVATION)
                        or item.get("independent_crosscheck") != "NOT_PERFORMED"
                        or item.get("real_world_verified") is not False):
                    failures.append("FALSELY_VERIFIED_CONTRACT_FIELD:" + ident)
        preflight = doc.get("preflight_checks")
        if (type(preflight) is not list or len(preflight) != len(ABORTS)
                or [r.get("id") for r in preflight if type(r) is dict]
                != list(ABORTS)):
            failures.append("PREOBSERVATION_ABORT_LIST_INCOMPLETE")
        else:
            for row in preflight:
                if (row.get("if_unverified") != "STOP_BEFORE_TERMINAL_ACTION"
                        or type(row.get("check")) is not str or not row["check"]
                        or type(row.get("current_status")) is not str
                        or not row["current_status"]):
                    failures.append("ABORT_GUARD_WEAKENED:" + row["id"])
        steps = doc.get("environment_readonly_steps")
        if (type(steps) is not list or len(steps) != len(STEPS)
                or [r.get("id") for r in steps if type(r) is dict]
                != list(STEPS)):
            failures.append("FUTURE_MANUAL_STEP_SET_INCOMPLETE")
        else:
            for step in steps:
                if (step.get("status") != "NOT_AUTHORIZED"
                        or type(step.get("description")) is not str
                        or not step["description"]):
                    failures.append("UNAUTHORIZED_TERMINAL_STEP:" + step["id"])
        if doc.get("evidence_required_for_each_field") != list(REQUIRED_PER_FIELD):
            failures.append("EVIDENCE_PROVENANCE_REQUIREMENTS_DROPPED")
        previous = docs[PREVIOUS]
        if (previous.get("g1_real_world_verified") is not False
                or previous.get("g1_scope_revision_approved") is not True
                or previous.get("phase_1") != "BLOCKED"
                or previous.get("runtime_go_no_go") != "NO_GO"
                or previous.get("current_readiness")
                != "BLOCKED_MISSING_ORIGINALS_AND_REAL_EVIDENCE"):
            failures.append("UPSTREAM_G1_PREFLIGHT_PROMOTED")
        g = docs[GATES]
        g1 = next(row for row in g["gaps"] if row["id"] == "G1")
        if (g1.get("implementation_status") != "UNRESOLVED"
                or g1.get("real_world_verified") is not False
                or g1.get("release_blocker") is not True
                or "3通貨ペア×5主要契約属性" not in g1.get("subject", "")
                or g.get("real_mt4_access_approved") is not False
                or g.get("phase_1") != "BLOCKED"
                or g.get("runtime_go_no_go") != "NO_GO"):
            failures.append("FORMAL_G1_OR_MT4_ACCESS_FALSIFIED")
        draft = docs[FORM01]
        if (draft.get("target_pairs") != list(PAIRS)
                or draft.get("required_g1_five_fields") != list(FIVE)
                or draft.get("form01_implementation_approved") is not False
                or draft.get("owner_decisions_to_resolve") is None
                or any(row.get("owner_status") != "UNDECIDED"
                       for row in draft["owner_decisions_to_resolve"])):
            failures.append("FORM01_UNRESOLVED_NOT_PRESERVED")
        template = docs[V3]
        if ([row["symbol"] for row in template["symbols"]] != list(PAIRS)
                or any(any(v is not None for v in row["observation"].values())
                       or any(v is not None for v in row["properties"].values())
                       for row in template["symbols"])):
            failures.append("V3_CONTRACT_TEMPLATE_PREMATURELY_FILLED")
    except (OSError, ValueError, TypeError, AttributeError, KeyError, StopIteration):
        failures.append("PLAN_OR_SOURCE_MALFORMED")
    return failures


def main() -> None:
    failures = audit()
    if failures:
        raise SystemExit("RISK-3P-18/19: FAIL\n" + "\n".join("- " + x for x in failures))
    print("RISK-3P-18/19: PASS (DOCUMENTARY ONLY, NO REAL OBSERVATION)")
    print("Three-pair G1 15/15 evidence NOT_OBSERVED, all sources unverified")
    print("Seven abort controls and six future observation steps NOT_AUTHORIZED")
    print("Existing account MACD Sample/orders unresolved; no MT4 action permitted")
    print("G1 UNRESOLVED | PHASE-1 BLOCKED | runtime NO_GO | safety_hold_latched=true")


if __name__ == "__main__":
    main()
