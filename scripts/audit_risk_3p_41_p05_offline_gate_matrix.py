"""Validate P05 source/report consistency without any MT4 or private file access.

Only public repository specification JSON is read. No automatic acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import risk_3p_40_synthetic_p05_interlock_matrix as sim

ROOT = Path(__file__).resolve().parents[1]
MATRIX = "specs/risk_3p_41_p05_offline_gate_matrix_20261106.json"
P05 = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
REVIEW = "specs/risk_3p_35_p05_08_human_review_packet_20261106.json"
G1 = "specs/risk_3p_33_p05_07_offline_provenance_readiness_20261106.json"
FILES = (MATRIX, P05, REVIEW, G1)
STATES = (
    ("OWNER_REPORTED_DEMO_ACCOUNT_COMMUNICATING_IDENTITY_UNVERIFIED",
     "OWNER_UI_DEMO_DOES_NOT_PROVE_ACCOUNT_IDENTITY"),
    ("OWNER_REPORTED_MACD_SAMPLE_VISIBLE_RUNTIME_UNVERIFIED",
     "MACD_SAD_FACE_AND_AUTOTRADING_OFF_NOT_EA_RUNTIME_PROOF"),
    ("OWNER_REPORTED_TRADE_TAB_BALANCE_ONLY_NO_ORDER_ROWS_VISIBLE",
     "BALANCE_ONLY_DOES_NOT_PROVE_SERVER_ORDERS_ZERO"),
    ("OWNER_REPORTS_THIS_MT4_ONLY_NO_PARALLEL_LOGIN_INDEPENDENTLY_UNVERIFIED",
     "OWNER_ONE_TERMINAL_REPORT_NOT_ACCOUNT_SESSION_AUDIT"),
    ("NOT_DEMONSTRATED_ON_CURRENT_ENVIRONMENT",
     "NO_REAL_TERMINAL_NONINTERFERENCE_TEST"),
    ("OWNER_ACCEPTED_LOCAL_FOLDER_AND_PARENTS_FOR_OFFLINE_PLANNING_ONLY",
     "OWNER_STORAGE_ACCEPTANCE_ONLY_NO_REAL_BROKER_EVIDENCE_UPLOAD"),
    ("ACTUAL_MT4_SYMBOL_AND_TIME_NOT_OBSERVED",
     "G1_3X5_REAL_BROKER_FIELDS_ZERO_VERIFIED"),
    ("NO_SEPARATE_P05_PASS_OR_OPERATOR_ATTESTATION",
     "HUMAN_P05_SIGNOFF_NOT_GRANTED"),
)
CONTROLS = {
    "required_p05_items": 8,
    "passed_p05_items": 0,
    "g1_broker_values_verified": 0,
    "fx_saf_originals_verified": 0,
    "form_implementation_approvals": 0,
    "real_account_identity_verified": False,
    "real_mt4_terminal_session_verified": False,
    "real_macd_ea_runtime_verified": False,
    "real_order_state_reconciled": False,
    "real_readonly_noninterference_verified": False,
    "real_g1_symbol_provenance_verified": False,
    "owner_storage_acceptance_offline_only": True,
    "human_p05_signoff": False,
    "real_mt4_access_authorized": False,
    "ea_or_order_action_authorized": False,
    "parallel_mt4_login_authorized": False,
    "main_auto_merge_authorized": False,
    "phase_1": "BLOCKED",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "verified_values": None,
}
META = {
    "schema_version": 1,
    "id": "RISK-3P-41-P05-OFFLINE-GATE-MATRIX-20261106",
    "created_on_jst_date": "2026-11-06",
    "scope": "OFFLINE_GATE_ALIGNMENT_AND_SYNTHETIC_TEST_ONLY",
    "source_p05": P05,
    "source_unsigned_review": REVIEW,
    "source_g1": G1,
    "next_step":
    "OFFLINE_CONTINUE_ONLY_P05_INDEPENDENT_EVIDENCE_AND_HUMAN_SIGNOFF_REQUIRED",
}
ROW_KEYS = ("check_id", "reported_state_expected", "blocker_code",
            "real_evidence_verified", "owner_p05_item_approved",
            "simulator_pass_means_real_clearance")


def _read(root: Path, path: str) -> object:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        docs = injected if injected is not None else {
            key: _read(root, key) for key in FILES
        }
        doc, source, review, g1 = (docs[key] for key in FILES)
        if any(type(item) is not dict for item in
               (doc, source, review, g1)):
            return ["P41_INVALID_OFFLINE_DOCUMENT"]
        if (set(doc) != set(META) | {"checks", "controls"}
                or any(doc.get(k) != v for k, v in META.items())):
            errors.append("P41_OWNER_EVIDENCE_SCOPE_DRIFT")
        if doc.get("controls") != CONTROLS:
            errors.append("P41_REAL_P05_OR_ORDER_PERMISSION_FORGED")
        rows = doc.get("checks")
        original = source.get("p05_checks")
        unsigned = review.get("items")
        if (type(rows) is not list or len(rows) != 8
                or type(original) is not list or len(original) != 8
                or type(unsigned) is not list or len(unsigned) != 8):
            errors.append("P41_P05_EIGHT_SOURCE_ROWS_REQUIRED")
        else:
            for i, ((current, blocker), row, old, item) in enumerate(
                    zip(STATES, rows, original, unsigned)):
                code = str(i + 1)
                if (type(row) is not dict or set(row) != set(ROW_KEYS)
                        or row.get("check_id") != f"P05-{i + 1:02d}"
                        or row.get("reported_state_expected") != current
                        or row.get("blocker_code") != blocker
                        or any(row.get(k) is not False for k in
                               ("real_evidence_verified",
                                "owner_p05_item_approved",
                                "simulator_pass_means_real_clearance"))):
                    errors.append("P41_OFFLINE_REVIEW_ROW_PROMOTED:" + code)
                if (type(old) is not dict
                        or old.get("check_id") != f"P05-{i + 1:02d}"
                        or old.get("current_status") != current
                        or old.get("safe_to_proceed") is not False
                        or old.get("p05_accepted") is not False
                        or old.get("evidence_reference") is not None):
                    errors.append("P41_P05_SOURCE_FALSE_ACCEPTANCE:" + code)
                if (type(item) is not dict
                        or item.get("check_id") != f"P05-{i + 1:02d}"
                        or item.get("item_accepted") is not False
                        or item.get("human_specific_acceptance") !=
                        "PENDING_NOT_REQUESTED"
                        or item.get("independent_environment_evidence") !=
                        "NOT_VERIFIED"):
                    errors.append("P41_REVIEW_HUMAN_SIGNATURE_FORGED:" + code)
        if (source.get("p05_passed_checks") != 0
                or source.get("p05_human_safety_signoff") is not False
                or source.get("p06_observation_authorized") is not False
                or source.get("runtime_go_no_go") != "NO_GO"
                or source.get("phase_1") != "BLOCKED"
                or source.get("safety_hold_latched") is not True
                or review.get("decision") !=
                "PENDING_SEPARATE_OWNER_APPROVAL_AFTER_INDEPENDENT_EVIDENCE"
                or review.get("safety", {}).get("p05_passed") != 0):
            errors.append("P41_GLOBAL_SAFE_STOP_UNVERIFIED")
        g1rows = g1.get("g1_entries")
        if (g1.get("required_items") != 15
                or type(g1rows) is not list or len(g1rows) != 15
                or g1.get("safety", {}).get(
                    "independently_verified_g1_items") != 0):
            errors.append("P41_G1_VERIFIED_DATA_NOT_AVAILABLE")
        elif any(type(row) is not dict
                 or row.get("value", "MISSING") is not None
                 or row.get("status") != "UNVERIFIED_NO_TERMINAL_EVIDENCE"
                 for row in g1rows):
            errors.append("P41_UNAUTHORIZED_G1_EVIDENCE_PROMOTION")
        for exposure in (False, True):
            result = sim.evaluate(
                sim.fixture(simulated_exposure=exposure))
            if (result["status"] != "PASS_SYNTHETIC_MATRIX_ONLY"
                    or result["real_p05_passed"] != 0
                    or result["runtime_go_no_go"] != "NO_GO"):
                errors.append("P41_SYNTHETIC_NOT_SAFE_AS_P05_EVIDENCE")
                break
    except (KeyError, TypeError, ValueError, OSError, IndexError,
            AttributeError):
        errors.append("P41_MISSING_OR_MALFORMED_INPUT")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_OFFLINE_MATRIX_ONLY" if not errors else "FAIL_CLOSED",
        "p05_checks_required": 8,
        "real_p05_checks_accepted": 0,
        "real_g1_verified": 0,
        "human_p05_signoff": False,
        "mt4_session_authorized": False,
        "trading_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))
