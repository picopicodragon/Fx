"""Exact-value contracts for seven simulated P60 subreports.

Prevents unnoticed new approval flags, missing fields, integer/bool confusion,
and "PASS" labels paired with altered evidence counts. These are immutable
expectations for *offline snapshots only*, not MT4/broker certification.
"""
from __future__ import annotations

STATUS = "status"
STOP = "runtime_go_no_go"
LATCH = "safety_hold_latched"
ERRORS = "errors"


def _report(status: str, **values) -> dict:
    return {STATUS: status, **values, STOP: "NO_GO",
            LATCH: True, ERRORS: []}


EXPECTED = {
    "fictional_ingress": _report(
        "PASS_SYNTHETIC_INGRESS_FORMAT_ONLY",
        fake_event_count=3, fake_g1_field_count=15, real_observation_count=0,
        real_broker_origin_verified=False, human_p05_signoff=False,
        p05_passed=0, g1_real_verified=0,
        private_data_read_authorized=False, real_mt4_read_authorized=False,
        orders_or_ea_authorized=False),
    "static_boundary": _report(
        "PASS_NARROW_STATIC_REVIEW_ONLY",
        pure_synthetic_modules_scanned=6,
        full_runtime_isolation_proven=False,
        transitive_imports_or_reflection_proven_safe=False,
        p05_passed=0, g1_real_verified=0,
        real_mt4_access_authorized=False, order_execution_authorized=False),
    "fake_clocks": _report(
        "PASS_SIMULATED_CLOCK_CONSISTENCY_ONLY",
        synthetic_sample_pairs=3,
        real_timestamp_authenticity_verified=False,
        real_data_freshness_verified=False,
        real_clock_monotonicity_verified=False,
        p05_passed=0, g1_real_verified=0,
        real_mt4_session_authorized=False,
        order_or_ea_action_authorized=False),
    "safe_diagnostics": _report(
        "PASS_SAFE_FAKE_SUMMARY_ONLY",
        check_slots=4, synthetic_checks_consistent=4,
        submitted_values_echoed=False, real_evidence_authenticated=False,
        raw_evidence_collected=False, p05_passed=0,
        g1_real_verified=0, real_mt4_read_authorized=False,
        order_execution_authorized=False),
    "unsigned_dependency_dag": _report(
        "PASS_BLOCKED_DEPENDENCY_DAG_ONLY",
        p05_prerequisites=8, p05_real_accepted=0, g1_real_verified=0,
        owner_storage_accepted_for_offline_planning=True,
        real_mt4_observation_authorized=False,
        order_execution_authorized=False, human_p05_signoff=False),
    "previous_provenance_gate": _report(
        "PASS_OFFLINE_PROVENANCE_QA_ONLY",
        offline_modules_checked=4, real_broker_evidence_verified=False,
        independent_source_authenticity_verified=False,
        trusted_timestamp_verified=False, p05_passed=0,
        g1_real_verified=0, real_owner_authorization_recorded=False,
        real_mt4_read_authorized=False, real_order_execution_authorized=False),
    "unsigned_future_handoff": _report(
        "PASS_UNSIGNED_HANDOFF_SCHEMA_ONLY",
        p05_required=8, p05_passed=0, g1_required=15, g1_real_verified=0,
        actual_evidence_received=False, real_broker_independence_verified=False,
        human_p05_signoff=False, real_mt4_access_authorized=False,
        order_or_ea_action_authorized=False),
}
EXPECTED_NAMES = (
    "fictional_ingress", "static_boundary", "fake_clocks",
    "safe_diagnostics", "unsigned_dependency_dag",
    "previous_provenance_gate", "unsigned_future_handoff",
)


def _plain_text_keys(record: object, expected_keys: object) -> bool:
    """Reject user-defined hash/eq hooks before any key set or lookup."""
    if type(record) is not dict:
        return False
    if any(type(key) is not str for key in record):
        return False
    return set(record) == set(expected_keys)


def _strict_same(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (_plain_text_keys(actual, expected)
                and all(_strict_same(actual[key], value)
                        for key, value in expected.items()))
    if type(expected) is list:
        return (len(actual) == len(expected)
                and all(_strict_same(a, b) for a, b in zip(actual, expected)))
    # The expected contract contains only built-in primitives. No custom __eq__.
    if type(expected) not in (str, int, bool, type(None)):
        return False
    return actual == expected


def check(name: object, record: object) -> list[str]:
    """Fixed non-sensitive codes; never reflect input names or values."""
    if type(name) is not str or name not in EXPECTED_NAMES:
        return ["P61_UNKNOWN_REPORT_CLASS"]
    if not _strict_same(record, EXPECTED[name]):
        return ["P61_UNKNOWN_FIELD_TYPE_OR_VALUE_DRIFT:"
                + str(EXPECTED_NAMES.index(name) + 1)]
    return []


def snapshot(records: object) -> dict:
    errors = []
    if not _plain_text_keys(records, EXPECTED_NAMES):
        errors.append("P61_REQUIRED_SEVEN_REPORTS_OR_EXTRA_PAYLOAD")
    else:
        for name in EXPECTED_NAMES:
            errors.extend(check(name, records[name]))
    return {
        "status": "PASS_EXACT_OFFLINE_RESULTS_ONLY" if not errors
        else "FAIL_CLOSED",
        "offline_report_contracts": 7,
        "actual_broker_evidence_authenticated": False,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "real_mt4_read_authorized": False,
        "real_order_execution_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
