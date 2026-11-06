"""Audit unsigned, non-authorizing P05-08 review packet without real MT4 data."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import audit_risk_3p_33_p05_07_offline_preflight as g1_check
from scripts import validate_risk_3p_34_synthetic_provenance as synthetic

ROOT = Path(__file__).resolve().parents[1]
PACKET = "specs/risk_3p_35_p05_08_human_review_packet_20261106.json"
P05 = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
G1 = "specs/risk_3p_33_p05_07_offline_provenance_readiness_20261106.json"
PATHS = (PACKET, P05, G1)
CODES = (
    "DEMO_ACCOUNT_UI_ONLY_SERVER_IDENTITY_UNVERIFIED",
    "MACD_VISIBLE_AUTOTRADING_OFF_SAD_FACE_NO_EA_EXECUTION_PROOF",
    "BALANCE_ONLY_TRADE_TAB_SERVER_ORDERS_UNRECONCILED",
    "SINGLE_MT4_SESSION_OWNER_REPORT_BROKER_SESSIONS_UNVERIFIED",
    "READ_ONLY_TERMINAL_INTERFERENCE_NOT_INDEPENDENTLY_TESTED",
    "PRIVATE_STORAGE_AND_ANCESTORS_OWNER_ACCEPTED_OFFLINE_ONLY",
    "THREE_PAIRS_FIFTEEN_ATTRIBUTES_ZERO_BROKER_EVIDENCE",
    "SEPARATE_HUMAN_P05_ACCEPTANCE_NOT_GRANTED",
)
LABELS = (
    "Existing demo account and environment identity",
    "MACD Sample and other EA state",
    "Open positions and pending orders",
    "Single session and no second demo account",
    "Read-only no-execution interaction boundary",
    "Private evidence storage and minimization",
    "Observation provenance and source consistency",
    "Human P05 safety review and execution boundary",
)
ITEM_KEYS = (
    "check_id", "criterion", "current_summary_code",
    "independent_environment_evidence", "human_specific_acceptance",
    "item_accepted", "private_log_or_account_id_collected",
)
SAFETY = {
    "required_checks": 8,
    "p05_passed": 0,
    "real_broker_g1_items_verified": 0,
    "real_mt4_account_session_authorized": False,
    "observation_or_script_authorized": False,
    "sensitive_data_read_or_upload_authorized": False,
    "ea_or_order_changes_authorized": False,
    "p06_authorized": False,
    "broker_order_or_position_absence_verified": False,
    "human_p05_signoff_reference": None,
    "human_phase_1_signoff_reference": None,
    "form_implementation_approvals": 0,
    "fx_saf_originals_verified": 0,
    "main_auto_merge_allowed": False,
    "main_manual_merge_owner_review_required": True,
    "phase_1": "BLOCKED",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "verified_values": None,
}
META = {
    "schema_version": 1,
    "id": "RISK-3P-35-P05-08-UNSIGNED-REVIEW-PACKET-20261106",
    "created_on_jst_date": "2026-11-06",
    "scope": "OFFLINE_HUMAN_REVIEW_CHECKLIST_DRAFT_ONLY",
    "source_p05": P05,
    "source_g1": G1,
    "source_p05_07_audit":
    "scripts/audit_risk_3p_33_p05_07_offline_preflight.py",
    "source_synthetic_validator":
    "scripts/validate_risk_3p_34_synthetic_provenance.py",
    "decision": "PENDING_SEPARATE_OWNER_APPROVAL_AFTER_INDEPENDENT_EVIDENCE",
    "next_step": "REVIEW_OPEN_BLOCKERS_OFFLINE_NO_MT4_OPERATION",
}


def _read(root: Path, filename: str) -> object:
    return json.loads((root / filename).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        data = injected if injected is not None else {
            file: _read(root, file) for file in PATHS
        }
        packet, p05, g1 = (data[key] for key in PATHS)
        if any(type(item) is not dict for item in (packet, p05, g1)):
            return ["P35_INVALID_REVIEW_PACKET_INPUT"]
        if (set(packet) != set(META) | {"items", "safety"}
                or any(packet.get(k) != v for k, v in META.items())):
            errors.append("P35_UNAUTHORIZED_PACKET_METADATA_OR_FIELDS")
        if packet.get("safety") != SAFETY:
            errors.append("P35_SIGNOFF_OR_RUNTIME_PERMISSION_FORGED")
        items = packet.get("items")
        if type(items) is not list or len(items) != 8:
            errors.append("P35_EIGHT_UNSIGNED_CHECKS_REQUIRED")
        else:
            for i, item in enumerate(items):
                if (type(item) is not dict or set(item) != set(ITEM_KEYS)
                        or item.get("check_id") != f"P05-{i + 1:02d}"
                        or item.get("criterion") != LABELS[i]
                        or item.get("current_summary_code") != CODES[i]
                        or item.get("independent_environment_evidence") !=
                        "NOT_VERIFIED"
                        or item.get("human_specific_acceptance") !=
                        "PENDING_NOT_REQUESTED"
                        or item.get("item_accepted") is not False
                        or item.get("private_log_or_account_id_collected")
                        is not False):
                    errors.append("P35_ITEM_FALSELY_VERIFIED_OR_SIGNED:"
                                  + str(i + 1))
        checks = p05.get("p05_checks")
        if (p05.get("p05_total_checks") != 8
                or p05.get("p05_passed_checks") != 0
                or p05.get("p05_human_safety_signoff") is not False
                or p05.get("p06_observation_authorized") is not False
                or p05.get("p05_gate_status") !=
                "BLOCKED_AWAITING_INDEPENDENT_ENVIRONMENT_SAFETY_CHECK"
                or p05.get("phase_1") != "BLOCKED"
                or p05.get("runtime_go_no_go") != "NO_GO"
                or p05.get("safety_hold_latched") is not True
                or type(checks) is not list or len(checks) != 8):
            errors.append("P35_P05_INDEPENDENT_SIGNOFF_STILL_REQUIRED")
        else:
            for i, item in enumerate(checks):
                if (type(item) is not dict or item.get("check_id") !=
                        f"P05-{i + 1:02d}"
                        or item.get("p05_accepted") is not False
                        or item.get("safe_to_proceed") is not False):
                    errors.append("P35_P05_SOURCE_ITEM_UNJUSTIFIABLY_PASSED:"
                                  + str(i + 1))
            if checks[5].get("owner_accepted_storage_security_scope", {}).get(
                    "accepted_for") != (
                    "OFFLINE_DESIGN_AND_SYNTHETIC_TEST_PLANNING_ONLY"):
                errors.append("P35_OWNER_STORAGE_ACCEPTANCE_OUT_OF_SCOPE")
        rows = g1.get("g1_entries")
        if (g1.get("required_items") != 15
                or g1.get("target_pairs") != list(g1_check.PAIRS)
                or g1.get("required_fields") != list(g1_check.FIELDS)
                or type(rows) is not list or len(rows) != 15
                or g1.get("safety") != g1_check.EXPECTED_SAFETY):
            errors.append("P35_NO_VERIFIED_G1_EVIDENCE_ALLOWED")
        else:
            for i, row in enumerate(rows):
                if (type(row) is not dict
                        or row.get("status") !=
                        "UNVERIFIED_NO_TERMINAL_EVIDENCE"
                        or any(row.get(k, "MISSING") is not None for k in
                               ("value", "unit", "terminal_symbol",
                                "observed_at_utc", "primary_source_ref",
                                "independent_source_ref", "reviewer_ref"))):
                    errors.append("P35_G1_PROVENANCE_NOT_EMPTY:"
                                  + str(i + 1))
        # The synthetic contract has no broker access and cannot grant P05.
        synthetic_state = synthetic.check_synthetic_package(
            synthetic.make_synthetic_fixture())
        if synthetic_state["status"] != "PASS_SYNTHETIC_CONTRACT_ONLY":
            errors.append("P35_OFFLINE_SYNTHETIC_VALIDATOR_FAILED")
    except (OSError, KeyError, TypeError, ValueError, IndexError,
            AttributeError):
        errors.append("P35_MALFORMED_OR_MISSING_REVIEW_INPUT")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_UNSIGNED_REVIEW_DRAFT_ONLY" if not errors
        else "FAIL_CLOSED",
        "required_p05_items": 8,
        "accepted_p05_items": 0,
        "real_g1_fields_verified": 0,
        "human_p05_signoff_recorded": False,
        "p06_observation_authorized": False,
        "real_mt4_session_authorized": False,
        "order_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
