"""Fail-closed policy audit for *offline* P05-03 reconciliation work only."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import risk_3p_36_synthetic_order_reconciliation as sim

ROOT = Path(__file__).resolve().parents[1]
POLICY = "specs/risk_3p_36_37_order_reconciliation_offline_contract_20261106.json"
P05 = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
REVIEW = "specs/risk_3p_35_p05_08_human_review_packet_20261106.json"
G1 = "specs/risk_3p_33_p05_07_offline_provenance_readiness_20261106.json"
PATHS = (POLICY, P05, REVIEW, G1)
EXPECTED_ENVIRONMENT = {
    "real_mt4_data_collected": False,
    "real_order_positions_verified": False,
    "p05_03_accepted": False,
    "p05_checks_passed": 0,
    "p05_human_signoff": False,
    "p06_observation_authorized": False,
    "real_mt4_access_authorized": False,
    "order_execution_authorized": False,
    "auto_trading_change_authorized": False,
    "parallel_mt4_session_authorized": False,
    "uploaded_private_broker_log": False,
    "fx_saf_originals_verified": 0,
    "form_implementation_approvals": 0,
    "g1_independently_verified_fields": 0,
    "phase_1": "BLOCKED",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "verified_values": None,
}
EXPECTED_REQUIREMENTS = (
    "EXPLICIT_HUMAN_P05_SAFETY_APPROVAL_BEFORE_ANY_TERMINAL_OBSERVATION",
    "SAME_BROKER_ACCOUNT_SCOPE_WITHOUT_EXPOSING_ACCOUNT_ID",
    "TERMINAL_AND_BROKER_INDEPENDENTLY_CONFIRMED_SOURCE_AUTHENTICITY",
    "ACCOUNT_WIDE_COVERAGE_INCLUDING_NON_TARGET_SYMBOLS",
    "EXPLICIT_POSITION_AND_PENDING_ORDER_COUNTS_NOT_BALANCE_ONLY",
    "UTC_TIME_AND_STALENESS_BOTH_SOURCES_VERIFIED",
    "SERVER_STATUS_AND_CONNECTION_STATE_RECONCILED",
    "EXISTING_EA_PRESERVED_AND_NO_ORDER_CHANGES",
    "SOURCE_CONFLICTS_AND_UNKNOWN_VALUES_FORCE_STOP",
)
EXPECTED_META = {
    "schema_version": 1,
    "id": "RISK-3P-36-37-P05-03-OFFLINE-RECONCILIATION-20261106",
    "created_on_jst_date": "2026-11-06",
    "scope": "OFFLINE_SYNTHETIC_CONTRACT_ONLY_NO_MT4_ACCESS",
    "source_p05": P05,
    "source_unsigned_p05_review": REVIEW,
    "source_g1": G1,
    "observed_owner_ui": "BALANCE_ONLY_NO_POSITION_OR_PENDING_ORDER_ROWS_VISIBLE",
    "known_history": "PRIOR_POSITIONS_OR_PENDING_ORDERS_YES",
    "observed_zero_is_not_verified_zero": True,
    "categories": list(sim.CATEGORIES),
    "totals_required": ["open_positions", "pending_orders"],
    "unknown_counts_must_not_be_normalized_to_zero": True,
    "broker_side_must_be_independent_and_account_wide": True,
    "source_utc_format": "SYNTHETIC_UTC_ONLY_NO_REAL_WALL_CLOCK_PROOF",
    "max_simulated_time_skew_seconds": 30,
    "no_live_session_or_order_manipulation": True,
    "acceptance_paths": {
        "synthetic_zero_match": "SIMULATED_ZERO_MATCH_ONLY_NOT_REAL_PROOF",
        "synthetic_nonzero_match":
        "SIMULATED_EXPOSURE_PRESENT_ONLY_NOT_REAL_PROOF",
        "mismatch": "FAIL_CLOSED",
        "incomplete_or_unreliable": "FAIL_CLOSED",
    },
    "future_real_evidence_requirements": list(EXPECTED_REQUIREMENTS),
}


def _read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors = []
    try:
        docs = injected if injected is not None else {
            path: _read(root, path) for path in PATHS
        }
        policy, p05, review, g1 = [docs[p] for p in PATHS]
        if any(type(x) is not dict for x in (policy, p05, review, g1)):
            return ["P37_DOCUMENT_MALFORMED"]
        expected_keys = set(EXPECTED_META) | {"environment"}
        if (set(policy) != expected_keys
                or any(policy.get(key) != value for key, value in
                       EXPECTED_META.items())):
            errors.append("P37_RECONCILIATION_POLICY_DRIFT")
        if policy.get("environment") != EXPECTED_ENVIRONMENT:
            errors.append("P37_REAL_ACCOUNT_OR_TRADE_PERMISSION_PROMOTED")

        checks = p05.get("p05_checks")
        if (type(checks) is not list or len(checks) != 8
                or p05.get("p05_passed_checks") != 0
                or p05.get("p05_human_safety_signoff") is not False
                or p05.get("p06_observation_authorized") is not False
                or p05.get("runtime_go_no_go") != "NO_GO"
                or p05.get("phase_1") != "BLOCKED"
                or p05.get("safety_hold_latched") is not True):
            errors.append("P37_P05_STILL_REQUIRES_REAL_SAFETY_REVIEW")
        else:
            row = checks[2]
            if (type(row) is not dict or row.get("check_id") != "P05-03"
                    or row.get("current_status") !=
                    "OWNER_REPORTED_TRADE_TAB_BALANCE_ONLY_NO_ORDER_ROWS_VISIBLE"
                    or row.get("p05_accepted") is not False
                    or row.get("safe_to_proceed") is not False
                    or row.get("evidence_reference") is not None
                    or row.get("owner_reported_ui_observation", {}).get(
                        "server_order_state_reconciled") is not False):
                errors.append("P37_TRADE_TAB_UI_MISTAKEN_FOR_SERVER_PROOF")
        items = review.get("items")
        if (type(items) is not list or len(items) != 8
                or review.get("safety", {}).get("p05_passed") != 0
                or review.get("safety", {}).get("p06_authorized")
                is not False
                or review.get("decision") !=
                "PENDING_SEPARATE_OWNER_APPROVAL_AFTER_INDEPENDENT_EVIDENCE"):
            errors.append("P37_UNSIGNED_HUMAN_REVIEW_REQUIRED")
        else:
            item = items[2]
            if (type(item) is not dict or item.get("check_id") != "P05-03"
                    or item.get("current_summary_code") !=
                    "BALANCE_ONLY_TRADE_TAB_SERVER_ORDERS_UNRECONCILED"
                    or item.get("item_accepted") is not False
                    or item.get("independent_environment_evidence") !=
                    "NOT_VERIFIED"
                    or item.get("human_specific_acceptance") !=
                    "PENDING_NOT_REQUESTED"):
                errors.append("P37_P05_03_HUMAN_SIGNOFF_NOT_GRANTED")
        rows = g1.get("g1_entries")
        if (g1.get("required_items") != 15
                or g1.get("safety", {}).get(
                    "independently_verified_g1_items") != 0
                or type(rows) is not list or len(rows) != 15):
            errors.append("P37_REAL_BROKER_G1_ZERO_PROOF_REQUIRED")
        else:
            if any(type(row) is not dict
                   or row.get("status") !=
                   "UNVERIFIED_NO_TERMINAL_EVIDENCE"
                   or row.get("value", "MISSING") is not None
                   for row in rows):
                errors.append("P37_G1_REAL_VALUE_INJECTED")
        for exposed in (False, True):
            result = sim.evaluate_synthetic_reconciliation(
                sim.make_fixture(exposure=exposed))
            if (result["status"] != "PASS_OFFLINE_SYNTHETIC_ONLY"
                    or result["real_broker_state_reconciled"] is not False
                    or result["p05_03_accepted"] is not False
                    or result["runtime_go_no_go"] != "NO_GO"):
                errors.append("P37_SYNTHETIC_RECONCILIATION_NOT_FAIL_CLOSED")
                break
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            IndexError):
        errors.append("P37_MISSING_OR_MALFORMED_OFFLINE_INPUT")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_OFFLINE_POLICY_ONLY" if not errors else "FAIL_CLOSED",
        "p05_03_observed_balance_only": not errors,
        "p05_03_real_server_reconciled": False,
        "p05_passed": 0,
        "real_g1_fields_verified": 0,
        "human_p05_signoff": False,
        "real_mt4_read_authorized": False,
        "order_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
