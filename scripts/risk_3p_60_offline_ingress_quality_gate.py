"""End-to-end offline evidence-ingress planning QA, never a trading gate.

Combines mock intake, AST import boundary, fictional clocks, privacy-safe
diagnostics, blocked P05 dependency DAG, and prior unsigned safety QA.
All sources remain synthetic or public repository specifications.
"""
from __future__ import annotations

from pathlib import Path

from scripts import risk_3p_55_synthetic_ingress_contract as ingress
from scripts import audit_risk_3p_56_static_offline_boundary as static
from scripts import risk_3p_57_synthetic_temporal_coherence as clocks
from scripts import risk_3p_58_safe_diagnostic_projection as diag
from scripts import audit_risk_3p_59_p05_dependency_dag as deps
from scripts import risk_3p_52_offline_provenance_gate as prior
from scripts import audit_risk_3p_53_54_future_handoff as handoff
from scripts import risk_3p_61_strict_offline_result_contract as strict

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("fictional_ingress", "static_boundary", "fake_clocks",
         "safe_diagnostics", "unsigned_dependency_dag",
         "previous_provenance_gate", "unsigned_future_handoff")
EXPECTED = ("PASS_SYNTHETIC_INGRESS_FORMAT_ONLY",
            "PASS_NARROW_STATIC_REVIEW_ONLY",
            "PASS_SIMULATED_CLOCK_CONSISTENCY_ONLY",
            "PASS_SAFE_FAKE_SUMMARY_ONLY",
            "PASS_BLOCKED_DEPENDENCY_DAG_ONLY",
            "PASS_OFFLINE_PROVENANCE_QA_ONLY",
            "PASS_UNSIGNED_HANDOFF_SCHEMA_ONLY")
DENIED_TRUE = (
    "real_mt4_read_authorized", "real_mt4_session_authorized",
    "real_mt4_access_authorized", "real_mt4_observation_authorized",
    "real_broker_evidence_verified", "real_broker_origin_verified",
    "real_evidence_authenticated", "broker_origin_verified",
    "real_timestamp_authenticity_verified", "real_data_freshness_verified",
    "real_clock_monotonicity_verified", "full_runtime_isolation_proven",
    "transitive_imports_or_reflection_proven_safe",
    "actual_evidence_received", "real_source_authenticated",
    "independent_source_authenticity_verified",
    "actual_source_independence_verified", "real_broker_independence_verified",
    "human_p05_signoff", "real_owner_authorization_recorded",
    "order_execution_authorized", "order_or_ea_action_authorized",
    "order_action_authorized", "real_order_execution_authorized",
    "trading_authorized", "real_trading_authorized",
)
ZERO_COUNTERS = (
    "p05_passed", "p05_real_accepted", "g1_real_verified",
    "real_g1_verified", "actual_broker_fields_verified",
    "real_observation_count",
)


def _outputs(root: Path = ROOT):
    return (
        ingress.evaluate(ingress.fixture()),
        static.snapshot(root),
        clocks.evaluate(clocks.fixture()),
        diag.summarize(diag.fixture()),
        deps.snapshot(root),
        prior.evaluate(root),
        handoff.snapshot(root),
    )


def evaluate(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = []
    try:
        outputs = _outputs(root)
        for i, (name, status, actual) in enumerate(
                zip(NAMES, EXPECTED, outputs), 1):
            result = injected.get(name, actual) if type(injected) is dict else actual
            if (type(result) is not dict
                    or result.get("status") != status
                    or result.get("errors") != []
                    or result.get("runtime_go_no_go") != "NO_GO"
                    or result.get("safety_hold_latched") is not True):
                errors.append("P60_OFFLINE_CASE_UNTRUSTED:" + str(i))
                continue
            if any(key in result and result[key] is not False
                   for key in DENIED_TRUE):
                errors.append("P60_REAL_WORLD_PERMISSION_FORGED:" + str(i))
            if any(key in result and
                   (type(result[key]) is not int or result[key] != 0)
                   for key in ZERO_COUNTERS):
                errors.append("P60_UNVERIFIED_COUNT_PROMOTED:" + str(i))
        selected = {name: injected.get(name, actual)
                    if type(injected) is dict else actual
                    for name, actual in zip(NAMES, outputs)}
        errors.extend(strict.snapshot(selected)["errors"])
        if injected is not None and (type(injected) is not dict
                                     or set(injected) - set(NAMES)):
            errors.append("P60_UNAUTHORIZED_OR_PRIVATE_CASE_INSERTION")
    except (OSError, TypeError, ValueError, KeyError, IndexError,
            AttributeError, RecursionError):
        errors.append("P60_MISSING_OR_INVALID_OFFLINE_INPUT")
    return {
        "status": "PASS_COMBINED_OFFLINE_DESIGN_QA_ONLY"
        if not errors else "FAIL_CLOSED",
        "offline_subchecks": len(NAMES),
        "synthetic_data_only": True,
        "real_broker_or_mt4_read_performed": False,
        "real_account_evidence_verified": False,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "human_p05_signoff": False,
        "real_mt4_access_authorized": False,
        "real_order_or_ea_action_authorized": False,
        "main_automatic_merge_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
