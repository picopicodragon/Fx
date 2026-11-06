"""A single offline safety test orchestrator, never a trading readiness GO.

RISK-3P-47: enumerates simulated fault/state transitions.
RISK-3P-48: cross-checks P05 and G1 public-spec acceptance debt.
No broker, file outside repository, EA, order, login or private data access.
"""
from __future__ import annotations

from pathlib import Path

from scripts import risk_3p_40_synthetic_p05_interlock_matrix as interlock
from scripts import risk_3p_42_synthetic_fault_campaign as fault16
from scripts import risk_3p_43_synthetic_state_transition as transitions
from scripts import risk_3p_44_synthetic_safety_latch as latch
from scripts import risk_3p_45_synthetic_schema_mutation_campaign as mutant42
from scripts import audit_risk_3p_46_offline_acceptance_debt as debt

ROOT = Path(__file__).resolve().parents[1]
FALSE_FLAGS = (
    "real_mt4_access_authorized", "real_mt4_session_authorized",
    "real_mt4_read_authorized", "trading_or_ea_action_authorized",
    "real_stop_release_granted", "real_exit_or_order_action_performed",
    "real_trading_authorized", "order_authorized",
    "broker_order_or_ea_action_authorized", "real_broker_order_state_reconciled",
    "real_broker_safety_verified", "human_approval_recorded",
    "real_close_event_verified", "real_order_absence_verified",
    "real_positions_or_orders_absent_verified",
    "real_broker_state_reconciled", "real_account_identity_verified",
    "real_single_session_verified", "real_trading_authorized",
    "human_p05_signoff", "human_p05_08_signoff",
    "p05_03_accepted", "order_or_ea_action_authorized",
)
ZERO_FLAGS = ("p05_passed", "real_p05_passed", "actual_p05_items_passed",
              "real_p05_checks_passed", "real_g1_fields_verified",
              "g1_broker_verified")
EXPECTED_CASES = 2 + 2 + len(latch.EVENTS) + 1 + 1 + 1
# two interlock cases, two order history cases, all latch events,
# 16-fault suite, 42-mutation suite and P05/G1 debt audit


def _cases(root: Path):
    yield ("interlock_zero",
           interlock.evaluate(interlock.fixture()),
           "PASS_SYNTHETIC_MATRIX_ONLY")
    yield ("interlock_exposure",
           interlock.evaluate(interlock.fixture(simulated_exposure=True)),
           "PASS_SYNTHETIC_MATRIX_ONLY")
    yield ("timeline_unchanged",
           transitions.evaluate(transitions.fixture()),
           "PASS_SYNTHETIC_TIMELINE_ONLY")
    yield ("timeline_close",
           transitions.evaluate(transitions.fixture(closing=True)),
           "PASS_SYNTHETIC_TIMELINE_ONLY")
    for event in latch.EVENTS:
        yield ("latch_" + event, latch.evaluate(latch.fixture(event)),
               "PASS_SYNTHETIC_LATCH_ONLY")
    yield ("fault16", fault16.campaign(),
           "PASS_SYNTHETIC_FAULT_CAMPAIGN_ONLY")
    yield ("mutation42", mutant42.campaign(),
           "PASS_OFFLINE_MUTATION_CAMPAIGN_ONLY")
    yield ("p05_acceptance_debt", debt.snapshot(root),
           "PASS_OFFLINE_DEBT_CONSISTENCY_ONLY")


def evaluate(root: Path = ROOT, *, injected: dict | None = None) -> dict:
    errors = []
    completed = 0
    try:
        for case_id, original, expected in _cases(root):
            result = injected.get(case_id, original) if injected else original
            completed += 1
            if (type(result) is not dict
                    or result.get("status") != expected
                    or result.get("runtime_go_no_go") != "NO_GO"
                    or result.get("safety_hold_latched") is not True
                    or result.get("errors") != []):
                errors.append("P47_CASE_INVALID_OR_UNVERIFIED:" + case_id)
                continue
            if any(flag in result and result[flag] is not False
                   for flag in FALSE_FLAGS):
                errors.append("P48_REAL_WORLD_PERMISSION_PROMOTED:" + case_id)
            if any(flag in result and
                   (type(result[flag]) is not int or result[flag] != 0)
                   for flag in ZERO_FLAGS):
                errors.append("P48_P05_OR_G1_ACCEPTANCE_FORGED:" + case_id)
            if (case_id == "mutation42"
                    and result.get("synthetic_cases") != 42):
                errors.append("P47_MUTATION_COVERAGE_MISSING")
            if (case_id == "fault16"
                    and result.get("simulated_faults_exercised") != 16):
                errors.append("P47_FAULT_COVERAGE_MISSING")
            if (case_id == "p05_acceptance_debt"
                    and (result.get("p05_checks") != 8
                         or result.get("g1_fields") != 15)):
                errors.append("P48_SAFETY_DEBT_COUNTS_DRIFT")
        if completed != EXPECTED_CASES:
            errors.append("P47_INCOMPLETE_CROSS_SCENARIO_CAMPAIGN")
    except (TypeError, KeyError, ValueError, IndexError, AttributeError,
            OSError, OverflowError):
        errors.append("P47_QUALITY_GATE_INPUT_OR_EXECUTION_FAILURE")
    return {
        "status": "PASS_OFFLINE_QUALITY_GATE_ONLY" if not errors else "FAIL_CLOSED",
        "simulated_check_cases": completed,
        "expected_simulated_cases": EXPECTED_CASES,
        "nested_fault_campaign_cases": 16,
        "nested_mutation_cases": 42,
        "real_p05_passed": 0,
        "real_g1_verified": 0,
        "human_p05_signoff": False,
        "actual_broker_or_mt4_contacted": False,
        "real_mt4_read_authorized": False,
        "real_order_execution_authorized": False,
        "main_auto_merge_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
