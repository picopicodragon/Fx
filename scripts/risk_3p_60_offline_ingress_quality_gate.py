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


def _plain_keys(record: object) -> bool:
    """Check exact plain-string keys before hashing, membership or lookup."""
    return (type(record) is dict
            and all(type(key) is str for key in record))


def evaluate(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors: list[str] = []
    # Do not call dict.get on a user-controlled dictionary before validating
    # its keys. A custom __hash__/__eq__ could otherwise run at lookup time.
    valid_injection = injected is None or _plain_keys(injected)
    if not valid_injection:
        errors.append("P60_UNAUTHORIZED_OR_PRIVATE_CASE_INSERTION")
    elif injected is not None and set(injected) - set(NAMES):
        errors.append("P60_UNAUTHORIZED_OR_PRIVATE_CASE_INSERTION")

    if not errors:
        try:
            outputs = _outputs(root)
            selected = {}
            for i, (name, status, actual) in enumerate(
                    zip(NAMES, EXPECTED, outputs), 1):
                row = injected.get(name, actual) if injected is not None else actual
                if not _plain_keys(row):
                    errors.append("P60_OFFLINE_CASE_UNTRUSTED:" + str(i))
                    continue
                status_value = row.get("status")
                err_value = row.get("errors")
                runtime_value = row.get("runtime_go_no_go")
                if (type(status_value) is not str or status_value != status
                        or type(err_value) is not list or err_value != []
                        or type(runtime_value) is not str
                        or runtime_value != "NO_GO"
                        or row.get("safety_hold_latched") is not True):
                    errors.append("P60_OFFLINE_CASE_UNTRUSTED:" + str(i))
                    continue
                if any(key in row and row[key] is not False
                       for key in DENIED_TRUE):
                    errors.append("P60_REAL_WORLD_PERMISSION_FORGED:" + str(i))
                if any(key in row and
                       (type(row[key]) is not int or row[key] != 0)
                       for key in ZERO_COUNTERS):
                    errors.append("P60_UNVERIFIED_COUNT_PROMOTED:" + str(i))
                selected[name] = row
            # No potentially untrusted nested record reaches the strict
            # contract verifier after an earlier shape or authority error.
            if not errors:
                errors.extend(strict.snapshot(selected)["errors"])
        except Exception:
            # Offline child exceptions are untrusted: never expose text,
            # partial reports or a successful status.
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
