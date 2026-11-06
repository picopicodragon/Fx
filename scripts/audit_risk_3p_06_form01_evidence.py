"""RISK-3P-06 FORM-01 documentary evidence-plan audit, never an MT4 probe.

No broker, credential, price or account I/O. Never accepts real values or
promotes G1 / FORM / FX-SAF. Deliberately rejects filled observations.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.review_mt4_manual_symbol_3p_v3 import PAIRS, FIVE


ROOT = Path(__file__).resolve().parents[1]
DRAFT = "specs/risk_3p_06_form01_evidence_draft_20261104.json"
FORM = "specs/p0_01_risk_formula_open_decisions.json"
G1 = "specs/p0_01_d5_25_gap_verification_matrix.json"
PREVIOUS = "specs/risk_3p_05_owner_review_draft_20261104.json"
SCHEMA = "specs/mt4_manual_symbol_3p_v3_template.json"
SUPPLEMENTARY = (
    "terminal_symbol", "account_environment_identity",
    "account_deposit_currency", "base_units_per_lot", "max_lot", "digits",
    "stop_level_points", "freeze_level_points", "trade_mode",
    "execution_mode", "server_stop_visibility", "evidence_timestamp_utc",
    "specification_source", "contract_change_recheck",
)
REJECTIONS = (
    "UNKNOWN_CONTRACT_FIELD", "MISSING_SYMBOL_IDENTITY",
    "MISSING_ACCOUNT_ENVIRONMENT_IDENTITY",
    "UNVERIFIABLE_DEPOSIT_CURRENCY_OR_TICK_UNIT",
    "STALE_OR_MIXED_PROVENANCE", "INCONSISTENT_LOT_GRID",
    "UNKNOWN_STOP_OR_TRADE_MODE", "CONTRACT_VALUE_CHANGED_WITHOUT_RECHECK",
    "UNRECONCILED_ACCOUNT_OR_PENDING_ORDERS",
    "OWNER_APPROVAL_NOT_RECORDED", "G1_GATES_UNRESOLVED",
)
DECISIONS = tuple(f"F01-{i}" for i in range(1, 6))
CAPS = {"single_trade_fraction": "0.005", "combined_fraction": "0.010",
        "daily_fraction": "0.015", "max_drawdown_fraction": "0.05"}


def _read(root: Path, path: str) -> dict:
    return json.loads((root / path).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, draft: object = None) -> list[str]:
    """Compare proposed evidence slots to historical source/gate without approving."""
    errors: list[str] = []
    try:
        d = _read(root, DRAFT) if draft is None else draft
        if type(d) is not dict:
            return ["DRAFT_SCHEMA_INVALID"]
        if (d.get("schema_version") != 1
                or d.get("id") != "RISK-3P-06-FORM01-CONTRACT-EVIDENCE-DRAFT"
                or d.get("scope") != "OFFLINE_OWNER_REVIEW_AND_EVIDENCE_PLAN_ONLY"
                or d.get("source_form_id") != "FORM-01"
                or d.get("proposed_only") is not True):
            errors.append("DRAFT_SCOPE_OR_ID_INVALID")
        if (d.get("target_pairs") != list(PAIRS)
                or d.get("required_g1_five_fields") != list(FIVE)
                or d.get("historical_g1_attribute_count") != 20
                or d.get("target_g1_attribute_count") != len(PAIRS) * len(FIVE)
                or d.get("legacy_g1_gate_scope_unchanged") is not False
                or d.get("g1_scope_revision_approved") is not True
                or d.get("g1_scope_decision_ref") !=
                "specs/risk_3p_28_g1_scope_owner_decision_20261104.json"):
            errors.append("G1_DESIGN_SCOPE_DRIFT")
        if d.get("risk_caps_unmodified") != CAPS:
            errors.append("HARD_RISK_CAP_CHANGED")
        for field in (
            "form01_implementation_approved",
            "fx_saf_implementation_approved", "real_world_verified",
            "production_authorized", "broker_connection_authorized",
            "terminal_execution_approved", "stop_release_authorized",
        ):
            if d.get(field) is not False:
                errors.append("FALSE_APPROVAL:" + field)
        if (d.get("form01_owner_decision") != "NOT_RECORDED"
                or d.get("phase_1") != "BLOCKED"
                or d.get("runtime_go_no_go") != "NO_GO"
                or d.get("safety_hold_latched") is not True
                or "verified_values" not in d or d["verified_values"] is not None):
            errors.append("FALSE_OWNER_ACCEPTANCE_OR_STOP_RELEASE")
        if d.get("mandatory_reject_conditions") != list(REJECTIONS):
            errors.append("FAIL_CLOSED_REJECTION_SCOPE_DRIFT")
        records = d.get("proposed_evidence_records")
        if type(records) is not list or len(records) != len(PAIRS):
            return errors + ["THREE_PAIR_EVIDENCE_MATRIX_MISSING"]
        if [r.get("pair") for r in records if type(r) is dict] != list(PAIRS):
            errors.append("EVIDENCE_SYMBOL_SET_INVALID")
        for row in records:
            if type(row) is not dict or row.get("pair") not in PAIRS:
                errors.append("EVIDENCE_ROW_INVALID")
                continue
            pair = row["pair"]
            if (row.get("owner_verified") is not False
                    or row.get("real_symbol_identity_confirmed") is not False
                    or row.get("account_identity_confirmed") is not False):
                errors.append("FALSE_REAL_EVIDENCE:" + pair)
            fields = row.get("required_five")
            if type(fields) is not list or len(fields) != len(FIVE):
                errors.append("REQUIRED_FIVE_INVALID:" + pair)
            elif [v.get("field") for v in fields if type(v) is dict] != list(FIVE):
                errors.append("REQUIRED_FIVE_INVALID:" + pair)
            else:
                for value in fields:
                    if (value.get("status") != "PENDING_REAL_WORLD_EVIDENCE"
                            or value.get("verified_value", "ABSENT") is not None
                            or value.get("provenance_reference", "ABSENT") is not None
                            or value.get("observed_at_utc", "ABSENT") is not None
                            or value.get("independent_crosscheck") != "NOT_PERFORMED"):
                        errors.append("FALSE_FIVE_FIELD_EVIDENCE:" + pair + ":" + value["field"])
            extras = row.get("supplementary_checks")
            if (type(extras) is not list or len(extras) != len(SUPPLEMENTARY)
                    or [v.get("field") for v in extras if type(v) is dict]
                    != list(SUPPLEMENTARY)):
                errors.append("SUPPLEMENTARY_EVIDENCE_INVALID:" + pair)
            else:
                for value in extras:
                    if (value.get("status") != "PENDING_REVIEW"
                            or value.get("verified_value", "ABSENT") is not None
                            or value.get("provenance_reference", "ABSENT") is not None):
                        errors.append("FALSE_SUPPLEMENTARY_EVIDENCE:" + pair + ":" + value["field"])
        decisions = d.get("owner_decisions_to_resolve")
        if (type(decisions) is not list or len(decisions) != len(DECISIONS)
                or [v.get("id") for v in decisions if type(v) is dict] != list(DECISIONS)):
            errors.append("OWNER_DECISION_SET_INVALID")
        else:
            for row in decisions:
                if (row.get("owner_status") != "UNDECIDED"
                        or row.get("approval_reference", "ABSENT") is not None
                        or type(row.get("question")) is not str
                        or not row["question"]
                        or type(row.get("proposal")) is not str
                        or not row["proposal"]):
                    errors.append("OWNER_DECISION_PREMATURELY_FINAL:" + row["id"])
        orig = _read(root, FORM)
        form = next(x for x in orig["open_decisions"] if x["id"] == "FORM-01")
        if (form.get("owner_status") != "UNDECIDED_IMPLEMENTATION_DETAIL"
                or form.get("blocking") is not True):
            errors.append("FORM01_ORIGINAL_SOURCE_PROMOTED")
        prev = _read(root, PREVIOUS)
        original_prev = next(x for x in prev["open_reviews"] if x["id"] == "FORM-01")
        if (original_prev["implementation_approved"] is not False
                or original_prev["owner_decision"] != "NOT_RECORDED"):
            errors.append("RISK_3P_05_SOURCE_PREMATURELY_ACCEPTED")
        gap = _read(root, G1)
        g1 = next(x for x in gap["gaps"] if x["id"] == "G1")
        if (g1["implementation_status"] != "UNRESOLVED"
                or g1["real_world_verified"] is not False
                or g1["release_blocker"] is not True):
            errors.append("G1_FORMAL_GATE_FALSELY_RESOLVED")
        template = _read(root, SCHEMA)
        if ([r["symbol"] for r in template["symbols"]] != list(PAIRS)
                or any(any(value is not None for value in row["properties"].values())
                       for row in template["symbols"])):
            errors.append("UNVERIFIED_V3_TEMPLATE_WAS_FILLED")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        errors.append("MALFORMED_OR_MISSING_REGISTER")
    return errors


def main() -> None:
    errors = audit()
    if errors:
        raise SystemExit("RISK-3P-06 FORM-01 EVIDENCE DRAFT: FAIL\n" +
                         "\n".join("- " + error for error in errors))
    print("RISK-3P-06 FORM-01: PASS (offline evidence plan ONLY)")
    print("Three pairs / 15 fields: all actual evidence PENDING")
    print("FORM-01 UNDECIDED | G1 UNRESOLVED | FX-SAF NOT APPROVED")
    print("PHASE-1 BLOCKED | runtime NO_GO | safety_hold_latched=true")


if __name__ == "__main__":
    main()
