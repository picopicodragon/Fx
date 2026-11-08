"""Single offline gate for source inventory, import boundaries and P05 hold.

Its PASS only concerns synthetic test software and public repository specs.
It never grants MT4/broker access, trading, human signoff or main merge.
"""
from __future__ import annotations

from pathlib import Path

from scripts import risk_3p_65_integrated_offline_audit as old
from scripts import audit_risk_3p_62_offline_traceability_graph as trace
from scripts import audit_risk_3p_63_g1_ledger_alignment as g1
from scripts import audit_risk_3p_67_source_index as index
from scripts import audit_risk_3p_56_static_offline_boundary as syntax
from scripts import audit_risk_3p_69_import_time_safety as import_time
from scripts import risk_3p_70_fail_closed_campaign as adversarial
from scripts import risk_3p_61_strict_offline_result_contract as exact

ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    "previous_governance",
    "traceability",
    "g1_source_alignment",
    "pinned_offline_inventory",
    "explicit_import_allowlist",
    "no_unreviewed_import_time_calls",
    "twenty_nine_mock_attacks",
)
STATUS = (
    "PASS_GOVERNANCE_DESIGN_ONLY",
    "PASS_OFFLINE_Q109_LINKS_ONLY",
    "PASS_BLANK_G1_LEDGER_ALIGNMENT_ONLY",
    "PASS_PINNED_OFFLINE_INVENTORY_ONLY",
    "PASS_NARROW_STATIC_REVIEW_ONLY",
    "PASS_NARROW_IMPORT_TIME_AST_ONLY",
    "PASS_TWENTY_NINE_OFFLINE_ATTACKS_ONLY",
)
FALSE_FLAGS = (
    "actual_broker_evidence_verified", "real_mt4_observation_authorized",
    "ea_or_order_execution_authorized", "automatic_main_merge_authorized",
    "real_mt4_read_authorized", "real_mt4_access_authorized",
    "order_execution_authorized", "main_auto_merge_authorized",
    "runtime_dependency_closure_verified", "real_evidence_or_signoff_verified",
    "real_broker_sources_confirmed", "real_source_authenticity_verified",
    "production_approval_recorded", "full_runtime_isolation_proven",
    "transitive_imports_or_reflection_proven_safe",
    "runtime_side_effect_freedom_proven", "transitive_dependencies_verified",
    "actual_mt4_access_performed", "real_source_security_proven",
    "real_broker_evidence_verified", "all_sources_production_authorized",
)
ZERO_FLAGS = ("p05_passed", "p05_real_accepted", "g1_real_verified",
              "real_g1_verified")
COUNT_FIELDS = (
    ("offline_governance_subchecks", 6),
    ("minimum_tracked_synthetic_sources", 41),
    ("required_real_g1_rows", 15),
    ("expected_offline_sources", 45),
    ("pure_synthetic_modules_scanned", 6),
    ("mock_source_modules_reviewed", 6),
    ("mock_failures_exercised", 29),
)


def _expected(status: str, **facts) -> dict:
    """Explicitly reviewed P71 child output. Not a runtime authority token."""
    return {"status": status, **facts, "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True, "errors": []}


# Unlike a list of known danger flags, these complete records also block
# newly inserted fields and altered benign-looking numeric or Boolean claims.
EXPECTED_CHILD_REPORTS = (
    _expected(
        "PASS_GOVERNANCE_DESIGN_ONLY",
        offline_governance_subchecks=6, synthetic_corruption_cases_included=70,
        actual_broker_evidence_verified=False, p05_passed=0,
        g1_real_verified=0, real_mt4_observation_authorized=False,
        ea_or_order_execution_authorized=False,
        automatic_main_merge_authorized=False),
    _expected(
        "PASS_OFFLINE_Q109_LINKS_ONLY",
        minimum_tracked_synthetic_sources=41,
        all_sources_production_authorized=False,
        runtime_dependency_closure_verified=False,
        real_evidence_or_signoff_verified=False,
        p05_passed=0, g1_real_verified=0,
        real_mt4_read_authorized=False, order_execution_authorized=False,
        main_auto_merge_authorized=False),
    _expected(
        "PASS_BLANK_G1_LEDGER_ALIGNMENT_ONLY",
        required_real_g1_rows=15, real_g1_verified=0, p05_real_accepted=0,
        real_broker_sources_confirmed=False, human_p05_signoff=False,
        real_mt4_access_authorized=False,
        real_order_or_ea_action_authorized=False),
    _expected(
        "PASS_PINNED_OFFLINE_INVENTORY_ONLY",
        expected_offline_sources=45, real_source_authenticity_verified=False,
        production_approval_recorded=False, p05_passed=0,
        g1_real_verified=0, real_mt4_access_authorized=False,
        main_auto_merge_authorized=False),
    _expected(
        "PASS_NARROW_STATIC_REVIEW_ONLY",
        pure_synthetic_modules_scanned=6, full_runtime_isolation_proven=False,
        transitive_imports_or_reflection_proven_safe=False,
        p05_passed=0, g1_real_verified=0,
        real_mt4_access_authorized=False, order_execution_authorized=False),
    _expected(
        "PASS_NARROW_IMPORT_TIME_AST_ONLY",
        mock_source_modules_reviewed=6, runtime_side_effect_freedom_proven=False,
        transitive_dependencies_verified=False, actual_mt4_access_performed=False,
        p05_passed=0, g1_real_verified=0,
        real_mt4_read_authorized=False, order_execution_authorized=False),
    _expected(
        "PASS_TWENTY_NINE_OFFLINE_ATTACKS_ONLY",
        mock_failures_exercised=29, pure_modules_reviewed=6,
        real_source_security_proven=False, real_broker_evidence_verified=False,
        p05_passed=0, g1_real_verified=0,
        real_mt4_access_authorized=False, order_execution_authorized=False,
        main_auto_merge_authorized=False),
)


def _outputs(root: Path = ROOT) -> tuple[dict, ...]:
    return (
        old.evaluate(root),
        trace.snapshot(root),
        g1.snapshot(root),
        index.snapshot(root),
        syntax.snapshot(root),
        import_time.snapshot(root),
        adversarial.campaign(),
    )


def _plain_keys(record: object) -> bool:
    """Reject custom hash/equality hooks before set(), get() or membership."""
    return type(record) is dict and all(type(key) is str for key in record)


def evaluate(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors: list[str] = []
    # Unknown injected root data is never needed for ordinary offline checks.
    # Verify it before any set arithmetic, dict lookup or child evaluation.
    if injected is not None:
        if not _plain_keys(injected) or set(injected) - set(NAMES):
            errors.append("P71_UNKNOWN_OR_PRIVATE_RESULT_NAME")

    if not errors:
        try:
            records = _outputs(root)
            if type(records) not in (list, tuple) or len(records) != len(NAMES):
                errors.append("P71_INCOMPLETE_SEVEN_GATE_CHAIN")
            else:
                for n, (name, status, row) in enumerate(
                        zip(NAMES, STATUS, records), 1):
                    code = str(n)
                    if injected is not None:
                        row = injected.get(name, row)
                    if not _plain_keys(row):
                        errors.append("P71_CHILD_REPORT_MISSING_OR_INVALID:" + code)
                        continue
                    actual_status = row.get("status")
                    actual_errors = row.get("errors")
                    actual_runtime = row.get("runtime_go_no_go")
                    if (type(actual_status) is not str
                            or actual_status != status
                            or type(actual_errors) is not list
                            or actual_errors != []
                            or type(actual_runtime) is not str
                            or actual_runtime != "NO_GO"
                            or row.get("safety_hold_latched") is not True):
                        errors.append("P71_CHILD_REPORT_MISSING_OR_INVALID:" + code)
                        continue
                    if not exact._strict_same(row, EXPECTED_CHILD_REPORTS[n - 1]):
                        errors.append("P71_UNREVIEWED_CHILD_FIELD_OR_TYPE:" + code)
                    if any(k in row and row[k] is not False for k in FALSE_FLAGS):
                        errors.append("P71_REAL_PERMISSION_OR_FALSE_PROOF:" + code)
                    if any(k in row and
                           (type(row[k]) is not int or row[k] != 0)
                           for k in ZERO_FLAGS):
                        errors.append("P71_P05_G1_FAKE_PASS:" + code)
                    if any(k in row and
                           (type(row[k]) is not int or row[k] != value)
                           for k, value in COUNT_FIELDS):
                        errors.append("P71_COVERAGE_COUNTER_CHANGED:" + code)
        except Exception:
            # A child may raise an unexpected exception; never echo its text.
            errors.append("P71_OFFLINE_EVALUATOR_FAILURE")
    return {
        "status": "PASS_OFFLINE_INTEGRITY_ONLY" if not errors else "FAIL_CLOSED",
        "offline_subchecks": len(NAMES),
        "simulated_faults_in_nested_campaign": 29,
        "pinned_offline_sources": 45,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "real_mt4_observation_authorized": False,
        "real_order_execution_authorized": False,
        "human_p05_signoff": False,
        "main_auto_merge_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
