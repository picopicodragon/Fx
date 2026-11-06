"""G1 scope-only owner decision integrity gate.

This verifier never authenticates actual MT4 evidence, authorizes observation,
accepts G1, changes account state, or releases any stop. It distinguishes
OWNER_APPROVED_REVIEW_SCOPE from REAL_WORLD_VERIFIED/G1_ACCEPTED.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_risk_3p_02_migration import TARGET, HISTORY
from scripts.review_mt4_manual_symbol_3p_v3 import FIVE


ROOT = Path(__file__).resolve().parents[1]
FORMAL = "specs/p0_01_d5_25_gap_verification_matrix.json"
HISTORY_FILE = "specs/p0_01_d5_25_g1_legacy_scope_snapshot_20261104.json"
DECISION = "specs/risk_3p_28_g1_scope_owner_decision_20261104.json"


def load(root: Path, name: str) -> dict:
    return json.loads((root / name).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, *, formal: object = None,
          history: object = None, decision: object = None) -> list[str]:
    """Fail on corrupted scope approvals, rewritten history, or false G1 GO."""
    issues: list[str] = []
    try:
        m = load(root, FORMAL) if formal is None else formal
        h = load(root, HISTORY_FILE) if history is None else history
        d = load(root, DECISION) if decision is None else decision
        if type(m) is not dict or type(h) is not dict or type(d) is not dict:
            return ["INVALID_G1_SCOPE_RECORD"]
        if (d.get("schema_version") != 1
                or d.get("id") != "RISK-3P-28-G1-3X5-OWNER-SCOPE-DECISION-20261104"
                or d.get("decision_kind") != "EXPLICIT_OWNER_SCOPE_APPROVAL_ONLY"
                or d.get("decision_status") != "OWNER_APPROVED_SCOPE_ONLY"
                or d.get("owner_decision_origin")
                != "DIRECT_USER_IN_CURRENT_CHAT_TURN_NOT_ARCHIVED_ORIGINAL_SOURCE"
                or d.get("date_jst") != "2026-11-04"):
            issues.append("SCOPE_OWNER_DECISION_INVALID")
        if (d.get("authorized_scope") != list(TARGET)
                or d.get("five_required_fields") != list(FIVE)
                or d.get("required_count") != 15
                or d.get("historical_scope") != list(HISTORY)
                or d.get("historical_required_count") != 20
                or d.get("historical_snapshot_ref") != HISTORY_FILE):
            issues.append("SCOPE_TARGET_OR_HISTORY_CHANGED")
        if (h.get("schema_version") != 1
                or h.get("id") != "LEGACY-G1-FOUR-PAIR-SCOPE-20261030"
                or h.get("original_matrix_id") != m.get("id")
                or h.get("original_matrix_date") != "2026-10-30"
                or h.get("role") !=
                "IMMUTABLE_HISTORICAL_PRE_SCOPE_APPROVAL_REFERENCE"
                or h.get("superseded_by_owner_scope_decision_ref") != DECISION
                or h.get("historical_pairs") != list(HISTORY)
                or h.get("historical_major_field_count") != 20
                or h.get("original_verification_status") != "UNRESOLVED"
                or h.get("prior_real_world_evidence_verified") is not False
                or h.get("has_no_release_authority") is not True):
            issues.append("LEGACY_SCOPE_ARCHIVE_CHANGED")
        old = h.get("g1_before_scope_approval")
        if (type(old) is not dict or old.get("id") != "G1"
                or old.get("subject") !=
                "4通貨ペア×5項目のブローカー契約属性"
                or old.get("implementation_status") != "UNRESOLVED"
                or old.get("release_blocker") is not True
                or old.get("real_world_verified") is not False
                or old.get("external_or_real_evidence_required") != [
                    ("、".join(HISTORY) + "の20項目について実口座側から出典・時刻を付した契約値を将来別途許可された方法で確認")
                ]):
            issues.append("LEGACY_G1_ORIGINAL_SCOPE_CORRUPTED")
        # All existing history source strings stay in a JSON snapshot; the
        # runtime modules only import the expected historical tuple.
        if (m.get("g1_scope_record_kind") !=
            "OWNER_APPROVED_REVIEW_TARGET_ONLY"
                or m.get("g1_scope_decision_ref") != DECISION
                or m.get("g1_historical_legacy_scope_ref") != HISTORY_FILE
                or m.get("g1_scope_approved") is not True
                or m.get("g1_evidence_verified") is not False
                or m.get("g1_real_mt4_observation_authorized") is not False):
            issues.append("FORMAL_SCOPE_APPROVAL_RECORD_MISMATCH")
        g1 = next(row for row in m["gaps"] if row["id"] == "G1")
        if (g1.get("subject") !=
            "3通貨ペア×5主要契約属性のブローカー実証（正式審査対象15項目、実証未了）"
                or g1.get("scope_revision_status") !=
                "OWNER_APPROVED_THREE_PAIR_FIVE_FIELD_REVIEW_SCOPE_ONLY"
                or g1.get("scope_decision_ref") != DECISION
                or g1.get("historical_g1_snapshot_ref") != HISTORY_FILE
                or g1.get("approved_target_pairs") != list(TARGET)
                or g1.get("approved_major_attributes") != list(FIVE)
                or g1.get("approved_major_attribute_count") != 15
                or type(g1.get("verified_major_attribute_count")) is not int
                or g1["verified_major_attribute_count"] != 0
                or g1.get("owner_scope_approved") is not True):
            issues.append("FORMAL_G1_NEW_SCOPE_MISMATCH")
        required = g1.get("external_or_real_evidence_required")
        if (type(required) is not list or len(required) != 2
                or any(type(x) is not str or not x for x in required)
                or not all(pair in required[0] for pair in TARGET)
                or not all(field in required[1] for field in
                           ("1lot", "口座入金通貨", "stop/freeze"))):
            issues.append("G1_BROKER_EVIDENCE_REQUIREMENTS_MISSING")
        if (g1.get("implementation_status") != "UNRESOLVED"
                or g1.get("release_blocker") is not True
                or g1.get("real_world_verified") is not False
                or g1.get("broker_contract_verified") is not False):
            issues.append("G1_FALSELY_ACCEPTED")
        if (m.get("phase_1") != "BLOCKED"
                or m.get("runtime_go_no_go") != "NO_GO"
                or m.get("real_mt4_access_approved") is not False
                or m.get("real_order_execution_approved") is not False
                or m.get("forward_trading_enabled") is not False
                or m.get("terminal_execution_approved") is not False
                or m.get("broker_verified") is not False
                or "verified_values" not in m or m["verified_values"] is not None):
            issues.append("STOP_OR_BROKER_PERMISSION_FALSELY_PROMOTED")
        gaps = m.get("gaps")
        if (type(gaps) is not list or len(gaps) != 9
                or {g["id"] for g in gaps} != {f"G{i}" for i in range(1, 10)}
                or any(g.get("implementation_status") != "UNRESOLVED"
                       or g.get("release_blocker") is not True
                       or g.get("real_world_verified") is not False
                       for g in gaps)):
            issues.append("G1_TO_G9_GATE_FALSELY_RESOLVED")
        if (d.get("g1_live_evidence_status") != "UNRESOLVED"
                or d.get("real_verified_field_count") != 0
                or d.get("other_gates") != "G2_TO_G9_UNRESOLVED"
                or d.get("additional_attributes_remain_required") is not True):
            issues.append("SCOPE_DECISION_MISREPRESENTS_REAL_EVIDENCE")
        for name in ("source_original_fx_saf_verified",
                     "form01_10_implementation_approved",
                     "live_mt4_read_approved",
                     "ea_or_script_execution_approved",
                     "order_execution_approved",
                     "stop_release_approved",
                     "production_authorized",
                     "independent_broker_account_verified"):
            if d.get(name) is not False:
                issues.append("UNAUTHORIZED_SCOPE_EFFECT:" + name)
        state = d.get("status_after_change")
        if (type(state) is not dict
                or state.get("phase_1") != "BLOCKED"
                or state.get("runtime_go_no_go") != "NO_GO"
                or state.get("safety_hold_latched") is not True
                or state.get("verified_values", "MISSING") is not None):
            issues.append("OWNER_SCOPE_DECISION_FALSELY_RELEASED_STOP")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        issues.append("G1_SCOPE_FILE_INVALID_OR_MISSING")
    return issues


def main() -> None:
    errors = audit()
    if errors:
        raise SystemExit("RISK-3P-28 SCOPE INTEGRITY FAIL\n"
                         + "\n".join("- " + x for x in errors))
    print("G1 REVIEW SCOPE: OWNER APPROVED 3 PAIRS x 5 = 15 FIELDS")
    print("HISTORIC OLD 4x5 SCOPE: ARCHIVED AS UNRESOLVED (NOT REUSED)")
    print("CONTRACT VALUES: 0/15 VERIFIED | G1 AND G2..G9 UNRESOLVED")
    print("MT4 ACCESS: NOT APPROVED | PHASE-1 BLOCKED | runtime NO_GO")


if __name__ == "__main__":
    main()
