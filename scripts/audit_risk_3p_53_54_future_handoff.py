"""Audit unsigned P05/G1 handoff contract using repo design files only.

This report cannot approve real observation, user consent, live/demo orders,
or cryptographic provenance. No private logs, MT4 or broker access.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import risk_3p_52_offline_provenance_gate as gate

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = "specs/risk_3p_53_54_future_evidence_handoff_20261106.json"
P05 = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
G1 = "specs/risk_3p_33_p05_07_offline_provenance_readiness_20261106.json"
DEBT = "specs/risk_3p_46_48_offline_acceptance_debt_20261106.json"
ORDERS = "specs/risk_3p_36_37_order_reconciliation_offline_contract_20261106.json"
PATHS = (HANDOFF, P05, G1, DEBT, ORDERS)
REFERENCES = {"p05": P05, "g1": G1, "p05_debt": DEBT,
              "order_protocol": ORDERS}
PREREQUISITES = (
    "INDEPENDENT_ACCOUNT_DEMO_IDENTITY_CHECK",
    "EXISTING_EA_STATE_AND_NON_INTERFERENCE",
    "FULL_ACCOUNT_POSITIONS_PENDING_ORDERS_RECONCILIATION",
    "SINGLE_TERMINAL_SESSION_NO_PARALLEL_LOGIN",
    "READ_ONLY_PLAN_SAFETY_AND_NO_CODE_EXECUTION",
    "PRIVATE_STORAGE_OWNER_ACCEPTED_OFFLINE_ONLY",
    "G1_THREE_PAIRS_FIFTEEN_FIELDS_PRIMARY_AND_INDEPENDENT_REAL_PROOF",
    "SEPARATE_EXPLICIT_HUMAN_P05_SIGNOFF",
)
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
FIELDS = ("min_lot", "lot_step", "point_quote", "tick_size_points",
          "tick_value_deposit_currency")
METADATA = {
    "schema_version": 1,
    "id": "RISK-3P-53-54-FUTURE-EVIDENCE-HANDOFF-20261106",
    "created_on_jst_date": "2026-11-06",
    "classification": "UNSIGNED_FUTURE_HANDOFF_DESIGN_ONLY",
    "references": REFERENCES,
    "required_before_real_observation": list(PREREQUISITES),
    "owner_storage_decision":
    "ACCEPTED_FOR_OFFLINE_ONLY_NO_REAL_BROKER_COLLECTION",
    "next_step":
    "REVIEW_FUTURE_REAL_REQUIREMENTS_WITHOUT_AUTOMATIC_ACTIVATION",
}
PERMISSION = {
    "real_mt4_session_read_authorized": False,
    "real_broker_login_authorized": False,
    "order_or_ea_action_authorized": False,
    "private_log_upload_authorized": False,
    "p05_human_signoff": False,
    "phase1_human_signoff": False,
    "g1_fifteen_fields_verified": 0,
    "p05_passed_checks": 0,
    "fx_saf_originals_verified": 0,
    "form_implementation_approvals": 0,
    "verified_values": None,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}
ROW_KEYS = ("pair", "field", "real_broker_value", "real_observation_utc",
            "real_primary_source_ref", "real_independent_source_ref",
            "unit", "verified")
NULL_KEYS = ("real_broker_value", "real_observation_utc",
             "real_primary_source_ref", "real_independent_source_ref", "unit")


def _read(root: Path, path: str) -> object:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors = []
    try:
        docs = injected if injected is not None else {
            path: _read(root, path) for path in PATHS
        }
        handoff, p05, g1, debt, orders = (docs[p] for p in PATHS)
        if any(type(obj) is not dict
               for obj in (handoff, p05, g1, debt, orders)):
            return ["P53_OFFLINE_SOURCE_MISSING_OR_INVALID"]
        if (set(handoff) != set(METADATA) | {"g1_rows", "permission"}
                or any(handoff.get(k) != v for k, v in METADATA.items())):
            errors.append("P53_REAL_EVIDENCE_HANDOFF_SCOPE_DRIFT")
        if handoff.get("permission") != PERMISSION:
            errors.append("P53_REAL_MT4_OR_P05_APPROVAL_FORGED")
        rows = handoff.get("g1_rows")
        if type(rows) is not list or len(rows) != 15:
            errors.append("P53_G1_FIFTEEN_NULL_ROWS_REQUIRED")
        else:
            for i, (pair, field) in enumerate(
                    (p, f) for p in PAIRS for f in FIELDS):
                row = rows[i]
                if (type(row) is not dict or set(row) != set(ROW_KEYS)
                        or row.get("pair") != pair
                        or row.get("field") != field
                        or row.get("verified") is not False
                        or any(row.get(k, "MISSING") is not None
                               for k in NULL_KEYS)):
                    errors.append("P53_REAL_OBSERVATION_FORGED:" + str(i + 1))
        if (p05.get("p05_passed_checks") != 0
                or p05.get("p05_human_safety_signoff") is not False
                or p05.get("p06_observation_authorized") is not False
                or p05.get("runtime_go_no_go") != "NO_GO"
                or p05.get("safety_hold_latched") is not True
                or type(p05.get("p05_checks")) is not list
                or len(p05["p05_checks"]) != 8):
            errors.append("P53_P05_SOURCE_NOT_IN_SAFETY_HOLD")
        if (g1.get("required_items") != 15
                or g1.get("safety", {}).get(
                    "independently_verified_g1_items") != 0
                or type(g1.get("g1_entries")) is not list
                or len(g1["g1_entries"]) != 15):
            errors.append("P53_G1_SOURCE_REAL_PROOF_MISSING_OR_FALSE")
        elif any(type(row) is not dict
                 or row.get("status") != "UNVERIFIED_NO_TERMINAL_EVIDENCE"
                 or row.get("value", "MISSING") is not None
                 for row in g1["g1_entries"]):
            errors.append("P53_G1_SOURCE_FAKE_REAL_EVIDENCE")
        if (debt.get("safety", {}).get("p05_passed") != 0
                or debt.get("safety", {}).get("g1_real_verified") != 0
                or debt.get("safety", {}).get("runtime_go_no_go") != "NO_GO"
                or debt.get("safety", {}).get("safety_hold_latched")
                is not True):
            errors.append("P53_HISTORICAL_APPROVAL_DEBT_NOT_PRESERVED")
        if (orders.get("environment", {}).get(
                "real_order_positions_verified") is not False
                or orders.get("environment", {}).get(
                    "runtime_go_no_go") != "NO_GO"):
            errors.append("P53_REAL_BROKER_ORDER_PROOF_MISREPRESENTED")
        if injected is None:
            checked = gate.evaluate(root)
            if (checked["status"] != "PASS_OFFLINE_PROVENANCE_QA_ONLY"
                    or checked["runtime_go_no_go"] != "NO_GO"):
                errors.append("P53_PRIOR_PROVENANCE_QA_NOT_SAFE")
    except (OSError, ValueError, TypeError, KeyError, IndexError,
            AttributeError):
        errors.append("P53_MALFORMED_OR_MISSING_SPEC")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_UNSIGNED_HANDOFF_SCHEMA_ONLY"
        if not errors else "FAIL_CLOSED",
        "p05_required": 8, "p05_passed": 0,
        "g1_required": 15, "g1_real_verified": 0,
        "actual_evidence_received": False,
        "real_broker_independence_verified": False,
        "human_p05_signoff": False,
        "real_mt4_access_authorized": False,
        "order_or_ea_action_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, ensure_ascii=False))
