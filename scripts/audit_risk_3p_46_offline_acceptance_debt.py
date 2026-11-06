"""Cross-check unsigned P05/G1 safety debts using public repo specs only.

Never reads any private local evidence, broker account, MT4, or Windows ACL.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "specs/risk_3p_46_48_offline_acceptance_debt_20261106.json"
P05 = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
REVIEW = "specs/risk_3p_35_p05_08_human_review_packet_20261106.json"
MATRIX = "specs/risk_3p_41_p05_offline_gate_matrix_20261106.json"
G1 = "specs/risk_3p_33_p05_07_offline_provenance_readiness_20261106.json"
SOURCE_MAP = {"p05": P05, "unsigned_review": REVIEW,
              "p05_matrix": MATRIX, "g1": G1}
FILES = (MANIFEST, P05, REVIEW, MATRIX, G1)
SAFETY = {
    "p05_required": 8, "p05_passed": 0,
    "g1_required": 15, "g1_real_verified": 0,
    "fx_saf_originals_verified": 0, "form_decisions_approved": 0,
    "real_mt4_broker_evidence_collected": False,
    "real_account_session_verified": False,
    "real_ea_runtime_verified": False,
    "real_server_orders_verified": False,
    "real_broker_symbols_verified": False,
    "independent_acl_certified": False,
    "owner_local_storage_accepted_for_offline_planning_only": True,
    "p05_human_signoff": False, "phase1_human_signoff": False,
    "real_terminal_observation_authorized": False,
    "order_or_ea_actions_authorized": False,
    "auto_merge_authorized": False,
    "phase_1": "BLOCKED", "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True, "verified_values": None,
}
META = {
    "schema_version": 1,
    "id": "RISK-3P-46-48-P05-UNRESOLVED-ACCEPTANCE-DEBT-20261106",
    "date_jst": "2026-11-06",
    "scope": "OFFLINE_UNRESOLVED_SAFETY_REGISTER_ONLY",
    "sources": SOURCE_MAP,
    "report_classification":
    "SOURCE_STATE_CROSS_CHECK_NOT_REAL_SAFETY_ACCEPTANCE",
    "next_step":
    "CONTINUE_OFFLINE_SAFETY_TESTS_NO_EXTRA_OWNER_QUESTIONS_OR_AUTO_MERGE",
}
ROW_KEYS = ("check_id", "independent_evidence_verified",
            "human_acceptance_reference", "passed", "reason_code")
NULL_PROVENANCE_KEYS = ("value", "unit", "terminal_symbol", "observed_at_utc",
                        "primary_source_ref", "independent_source_ref",
                        "reviewer_ref")


def _read(root: Path, path: str) -> object:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors = []
    try:
        data = injected if injected is not None else {
            name: _read(root, name) for name in FILES
        }
        m, p05, review, matrix, g1 = (data[path] for path in FILES)
        if any(type(item) is not dict for item in
               (m, p05, review, matrix, g1)):
            return ["P46_MALFORMED_SPEC_OR_MANIFEST"]
        if (set(m) != set(META) | {"p05_items", "safety"}
                or any(m.get(k) != v for k, v in META.items())):
            errors.append("P46_MANIFEST_SCOPE_OR_PROVENANCE_CHANGED")
        if m.get("safety") != SAFETY:
            errors.append("P46_FAKE_HUMAN_APPROVAL_OR_RUNTIME_GO")
        pitems = p05.get("p05_checks")
        reviewitems = review.get("items")
        matrixitems = matrix.get("checks")
        mitems = m.get("p05_items")
        if any(type(x) is not list or len(x) != 8
               for x in (pitems, reviewitems, matrixitems, mitems)):
            errors.append("P46_P05_EIGHT_SOURCES_REQUIRED")
        else:
            for i, (row, p, r, g) in enumerate(
                    zip(mitems, pitems, reviewitems, matrixitems), 1):
                ident = f"P05-{i:02d}"
                if (type(row) is not dict or set(row) != set(ROW_KEYS)
                        or row.get("check_id") != ident
                        or row.get("reason_code") !=
                        f"P05_{i:02d}_NOT_INDEPENDENTLY_VERIFIED"
                        or row.get("independent_evidence_verified")
                        is not False
                        or row.get("human_acceptance_reference") is not None
                        or row.get("passed") is not False):
                    errors.append("P46_MANIFEST_ROW_WRONGLY_APPROVED:" + str(i))
                if (type(p) is not dict or p.get("check_id") != ident
                        or p.get("p05_accepted") is not False
                        or p.get("safe_to_proceed") is not False
                        or p.get("evidence_reference") is not None):
                    errors.append("P46_P05_SOURCE_WRONGLY_APPROVED:" + str(i))
                if (type(r) is not dict or r.get("check_id") != ident
                        or r.get("item_accepted") is not False
                        or r.get("independent_environment_evidence")
                        != "NOT_VERIFIED"
                        or r.get("human_specific_acceptance") !=
                        "PENDING_NOT_REQUESTED"):
                    errors.append("P46_REVIEW_OR_HUMAN_SIGNOFF_FALSE:" + str(i))
                if (type(g) is not dict or g.get("check_id") != ident
                        or g.get("real_evidence_verified") is not False
                        or g.get("owner_p05_item_approved") is not False):
                    errors.append("P46_OFFLINE_MATRIX_FALSE_APPROVAL:" + str(i))
        if (p05.get("p05_passed_checks") != 0
                or p05.get("p05_human_safety_signoff") is not False
                or p05.get("p06_observation_authorized") is not False
                or p05.get("runtime_go_no_go") != "NO_GO"
                or p05.get("safety_hold_latched") is not True
                or review.get("safety", {}).get("p05_passed") != 0
                or matrix.get("controls", {}).get("passed_p05_items") != 0):
            errors.append("P46_GLOBAL_P05_STOP_LOST")
        if type(pitems) is list and len(pitems) == 8:
            storage = pitems[5].get("owner_accepted_storage_security_scope", {})
            if (storage.get("accepted_for") !=
                    "OFFLINE_DESIGN_AND_SYNTHETIC_TEST_PLANNING_ONLY"
                    or storage.get("real_mt4_session_or_data_collection_authorized")
                    is not False):
                errors.append("P46_OWNER_STORAGE_ACCEPTANCE_OVEREXTENDED")
        entries = g1.get("g1_entries")
        if (g1.get("required_items") != 15
                or g1.get("safety", {}).get(
                    "independently_verified_g1_items") != 0
                or type(entries) is not list or len(entries) != 15):
            errors.append("P46_G1_EVIDENCE_COUNT_FALSE")
        else:
            for i, row in enumerate(entries, 1):
                if (type(row) is not dict
                        or row.get("status") !=
                        "UNVERIFIED_NO_TERMINAL_EVIDENCE"
                        or any(row.get(k, "MISSING") is not None
                               for k in NULL_PROVENANCE_KEYS)):
                    errors.append("P46_G1_UNVERIFIED_ROW_FILLED:" + str(i))
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            IndexError):
        errors.append("P46_INPUT_MISSING_OR_INVALID")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_OFFLINE_DEBT_CONSISTENCY_ONLY"
        if not errors else "FAIL_CLOSED",
        "p05_checks": 8, "p05_passed": 0,
        "g1_fields": 15, "g1_broker_verified": 0,
        "human_p05_signoff": False,
        "real_mt4_access_authorized": False,
        "real_trading_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
