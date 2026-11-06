"""RISK-3P-65/66: final mock-only governance cross-check for this branch.

Combines the existing offline QA with exact result schemas, Q109 mapping,
ordered 3x5 blank-ledger verification and seventy adversarial injections.
No MT4 access, broker data, real account authorization, or automatic merge.
"""
from __future__ import annotations

from pathlib import Path

from scripts import risk_3p_60_offline_ingress_quality_gate as old
from scripts import risk_3p_61_strict_offline_result_contract as strict
from scripts import audit_risk_3p_62_offline_traceability_graph as trace
from scripts import audit_risk_3p_63_g1_ledger_alignment as ledger
from scripts import risk_3p_64_adversarial_consistency_campaign as adversarial
from scripts import audit_risk_3p_59_p05_dependency_dag as deps

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "existing_mock_quality", "exact_subreport_contracts",
    "offline_q109_traces", "blank_g1_cross_ledgers",
    "seventy_adversarial_inputs", "blocked_p05_dependencies",
)
STATUS = (
    "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY",
    "PASS_EXACT_OFFLINE_RESULTS_ONLY",
    "PASS_OFFLINE_Q109_LINKS_ONLY",
    "PASS_BLANK_G1_LEDGER_ALIGNMENT_ONLY",
    "PASS_SEVENTY_MOCK_CORRUPTIONS_ONLY",
    "PASS_BLOCKED_DEPENDENCY_DAG_ONLY",
)
EXPECTED_FIELDS = (
    ("status", "offline_subchecks", "synthetic_data_only",
     "real_broker_or_mt4_read_performed", "real_account_evidence_verified",
     "p05_passed", "g1_real_verified", "human_p05_signoff",
     "real_mt4_access_authorized", "real_order_or_ea_action_authorized",
     "main_automatic_merge_authorized", "runtime_go_no_go",
     "safety_hold_latched", "errors"),
    ("status", "offline_report_contracts",
     "actual_broker_evidence_authenticated", "p05_passed",
     "g1_real_verified", "real_mt4_read_authorized",
     "real_order_execution_authorized", "runtime_go_no_go",
     "safety_hold_latched", "errors"),
    ("status", "minimum_tracked_synthetic_sources",
     "all_sources_production_authorized",
     "runtime_dependency_closure_verified",
     "real_evidence_or_signoff_verified", "p05_passed",
     "g1_real_verified", "real_mt4_read_authorized",
     "order_execution_authorized", "main_auto_merge_authorized",
     "runtime_go_no_go", "safety_hold_latched", "errors"),
    ("status", "required_real_g1_rows", "real_g1_verified",
     "p05_real_accepted", "real_broker_sources_confirmed",
     "human_p05_signoff", "real_mt4_access_authorized",
     "real_order_or_ea_action_authorized", "runtime_go_no_go",
     "safety_hold_latched", "errors"),
    ("status", "offline_baseline_classes", "synthetic_mutation_types",
     "synthetic_corruptions_checked", "composite_integration_cases_checked",
     "p05_passed", "g1_real_verified",
     "actual_broker_evidence_received", "human_signoff_verified",
     "real_mt4_access_authorized", "order_execution_authorized",
     "runtime_go_no_go", "safety_hold_latched", "errors"),
    ("status", "p05_prerequisites", "p05_real_accepted", "g1_real_verified",
     "owner_storage_accepted_for_offline_planning",
     "real_mt4_observation_authorized", "order_execution_authorized",
     "human_p05_signoff", "runtime_go_no_go", "safety_hold_latched",
     "errors"),
)
REQUIRE_FALSE = (
    "real_broker_or_mt4_read_performed", "real_account_evidence_verified",
    "human_p05_signoff", "real_mt4_access_authorized",
    "real_order_or_ea_action_authorized", "main_automatic_merge_authorized",
    "actual_broker_evidence_authenticated",
    "real_mt4_read_authorized", "real_order_execution_authorized",
    "runtime_dependency_closure_verified",
    "real_evidence_or_signoff_verified", "all_sources_production_authorized",
    "order_execution_authorized", "main_auto_merge_authorized",
    "real_broker_sources_confirmed",
    "actual_broker_evidence_received", "human_signoff_verified",
    "real_mt4_observation_authorized",
)
ZERO = ("p05_passed", "g1_real_verified", "real_g1_verified",
        "p05_real_accepted")
COUNTS = (
    ("offline_subchecks", 7), ("offline_report_contracts", 7),
    ("minimum_tracked_synthetic_sources", 41), ("required_real_g1_rows", 15),
    ("offline_baseline_classes", 7), ("synthetic_mutation_types", 10),
    ("synthetic_corruptions_checked", 70),
    ("composite_integration_cases_checked", 7), ("p05_prerequisites", 8),
)


def _outputs(root: Path = ROOT) -> tuple[dict, ...]:
    return (
        old.evaluate(root),
        strict.snapshot(dict(zip(old.NAMES, old._outputs(root)))),
        trace.snapshot(root),
        ledger.snapshot(root),
        adversarial.campaign(),
        deps.snapshot(root),
    )


def evaluate(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors: list[str] = []
    try:
        records = _outputs(root)
        for i, (name, status, allowed, current) in enumerate(
                zip(NAMES, STATUS, EXPECTED_FIELDS, records), 1):
            row = injected.get(name, current) if type(injected) is dict else current
            code = str(i)
            if (type(row) is not dict or set(row) != set(allowed)
                    or row.get("status") != status
                    or row.get("errors") != []
                    or row.get("runtime_go_no_go") != "NO_GO"
                    or row.get("safety_hold_latched") is not True):
                errors.append("P65_INVALID_INTEGRATION_RESULT:" + code)
                continue
            if any(key in row and row[key] is not False
                   for key in REQUIRE_FALSE):
                errors.append("P65_FORGED_REAL_WORLD_AUTHORITY:" + code)
            if any(key in row and
                   (type(row[key]) is not int or row[key] != 0)
                   for key in ZERO):
                errors.append("P65_FALSE_ACCEPTANCE_COUNTER:" + code)
            if any(key in row and
                   (type(row[key]) is not int or row[key] != num)
                   for key, num in COUNTS):
                errors.append("P65_TEST_COVERAGE_COUNT_DRIFT:" + code)
            if name == "existing_mock_quality" and row.get(
                    "synthetic_data_only") is not True:
                errors.append("P65_NOT_SYNTHETIC_ONLY")
            if name == "blocked_p05_dependencies" and row.get(
                    "owner_storage_accepted_for_offline_planning") is not True:
                errors.append("P65_OWNER_OFFLINE_STORAGE_SCOPE_DRIFT")
        if injected is not None and (
                type(injected) is not dict or set(injected) - set(NAMES)):
            errors.append("P65_UNKNOWN_OR_PRIVATE_RESULT_INJECTION")
    except (OSError, TypeError, KeyError, ValueError,
            AttributeError, IndexError, RecursionError):
        errors.append("P65_OFFLINE_QUALITY_INPUT_INVALID")
    return {
        "status": "PASS_GOVERNANCE_DESIGN_ONLY" if not errors
        else "FAIL_CLOSED",
        "offline_governance_subchecks": 6,
        "synthetic_corruption_cases_included": 70,
        "actual_broker_evidence_verified": False,
        "p05_passed": 0, "g1_real_verified": 0,
        "real_mt4_observation_authorized": False,
        "ea_or_order_execution_authorized": False,
        "automatic_main_merge_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
