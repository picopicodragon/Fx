"""Fail-closed offline P05-07 G1 template/provenance preflight; no MT4 access."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "specs/risk_3p_33_p05_07_offline_provenance_readiness_20261106.json"
TEMPLATE = "specs/mt4_manual_symbol_3p_v3_template.json"
SCOPE = "specs/risk_3p_28_g1_scope_owner_decision_20261104.json"
PROTOCOL = "specs/risk_3p_18_19_g1_readonly_provenance_protocol_20261104.json"
P05 = "specs/risk_3p_29_31_p02_p04_approval_p05_preflight_20261104.json"
PATHS = (LEDGER, TEMPLATE, SCOPE, PROTOCOL, P05)
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
FIELDS = ("min_lot", "lot_step", "point_quote", "tick_size_points",
          "tick_value_deposit_currency")
ROW_KEYS = ("pair", "field", "value", "unit", "terminal_symbol",
            "observed_at_utc", "primary_source_ref", "independent_source_ref",
            "reviewer_ref", "status")
OBS_KEYS = ("terminal_symbol", "observed_at_utc", "source_kind")
PROPERTY_KEYS = ("lot_size_base_units", "min_lot", "lot_step", "max_lot",
                 "point_quote", "digits", "tick_size_points",
                 "tick_value_deposit_currency", "stop_level_points",
                 "freeze_level_points", "spread_points")
DISPLAY_KEYS = ("spread_mode", "margin_currency",
                "profit_calculation_mode", "margin_calculation_mode",
                "hedged_margin_display", "margin_rate_display",
                "trade_mode_display", "execution_mode_display",
                "gtc_mode_display", "trading_hours_display")
WEEKDAYS = ("sunday", "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday")
EXPECTED_SAFETY = {
    "independently_verified_g1_items": 0,
    "p05_passed_checks": 0,
    "p05_human_signoff": False,
    "p05_actual_terminal_session_authorized": False,
    "p05_real_mt4_data_collection_authorized": False,
    "p05_06_owner_storage_acceptance_is_broker_or_acl_proof": False,
    "order_execution_authorized": False,
    "ea_script_or_chart_modification_authorized": False,
    "parallel_session_authorized": False,
    "cloud_or_github_private_evidence_upload_authorized": False,
    "actual_broker_identifiers_collected": False,
    "actual_values_collected": False,
    "form_implementation_approvals": 0,
    "fx_saf_originals_verified": 0,
    "phase_1": "BLOCKED",
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
    "verified_values": None,
}


def _load(root: Path, name: str) -> object:
    return json.loads((root / name).read_text(encoding="utf-8"))


def _keys_exact(obj: object, keys: tuple[str, ...]) -> bool:
    return type(obj) is dict and set(obj) == set(keys)


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    """Check existing *offline* templates only. Errors contain no secret data."""
    errors: list[str] = []
    try:
        docs = injected if injected is not None else {
            path: _load(root, path) for path in PATHS
        }
        ledger, template, scope, protocol, p05 = (docs[p] for p in PATHS)
        if not all(type(x) is dict for x in
                   (ledger, template, scope, protocol, p05)):
            return ["P05_07_INVALID_OFFLINE_DOCUMENT"]
        if (ledger.get("schema_version") != 1
                or ledger.get("id") !=
                "RISK-3P-33-P05-07-OFFLINE-PROVENANCE-READINESS-20261106"
                or ledger.get("stage") !=
                "OFFLINE_TEMPLATE_AND_PROVENANCE_PRECHECK_ONLY"
                or ledger.get("date_jst") != "2026-11-06"
                or ledger.get("source_scope") != SCOPE
                or ledger.get("source_mt4_blank_template") != TEMPLATE
                or ledger.get("source_readonly_method") != PROTOCOL
                or ledger.get("source_p05_owner_reports") != P05
                or ledger.get("owner_storage_decision") !=
                "FOLDER_AND_PARENTS_ACCEPTED_FOR_OFFLINE_PLANNING_ONLY"
                or ledger.get("next_step") !=
                "OFFLINE_SCHEMA_CHECK_ONLY_NO_BROKER_ACCESS"):
            errors.append("P05_07_SCOPE_OR_STORAGE_SCOPE_PROMOTED")
        if (ledger.get("target_pairs") != list(PAIRS)
                or ledger.get("required_fields") != list(FIELDS)
                or type(ledger.get("required_items")) is not int
                or ledger["required_items"] != 15):
            errors.append("P05_07_G1_3X5_SCOPE_DRIFT")
        if ledger.get("safety") != EXPECTED_SAFETY:
            errors.append("P05_07_G1_OR_MT4_AUTHORIZATION_FALSELY_GRANTED")
        rows = ledger.get("g1_entries")
        if type(rows) is not list or len(rows) != 15:
            errors.append("P05_07_G1_15_UNVERIFIED_ROWS_REQUIRED")
        else:
            for pos, (pair, field) in enumerate(
                    (p, f) for p in PAIRS for f in FIELDS):
                row = rows[pos]
                if (not _keys_exact(row, ROW_KEYS)
                        or row.get("pair") != pair
                        or row.get("field") != field
                        or row.get("status") !=
                        "UNVERIFIED_NO_TERMINAL_EVIDENCE"
                        or any(row.get(k, "MISSING") is not None for k in
                               ROW_KEYS if k not in ("pair", "field", "status"))):
                    errors.append("P05_07_UNVERIFIED_ROW_FILLED_OR_MISLABELED:"
                                  + str(pos + 1))
        if (scope.get("authorized_scope") != list(PAIRS)
                or scope.get("five_required_fields") != list(FIELDS)
                or scope.get("required_count") != 15
                or scope.get("real_verified_field_count") != 0
                or scope.get("live_mt4_read_approved") is not False):
            errors.append("P05_07_OWNER_SCOPE_MISTAKEN_FOR_EVIDENCE")
        if (protocol.get("target_pairs") != list(PAIRS)
                or [r.get("field") for r in
                    protocol.get("field_methodology", [])
                    if type(r) is dict] != list(FIELDS)
                or protocol.get("evidence_collected") is not False
                or protocol.get("owner_approved_real_read") is not False
                or protocol.get("p05_environment_precheck_status") !=
                "BLOCKED_SAFETY_CONDITIONS_UNKNOWN"
                or protocol.get("runtime_go_no_go") != "NO_GO"):
            errors.append("P05_07_READONLY_PROTOCOL_BROKER_PERMISSION_DRIFT")
        if (p05.get("p05_passed_checks") != 0
                or p05.get("p05_gate_status") !=
                "BLOCKED_AWAITING_INDEPENDENT_ENVIRONMENT_SAFETY_CHECK"
                or p05.get("p05_human_safety_signoff") is not False
                or p05.get("p06_observation_authorized") is not False
                or p05.get("runtime_go_no_go") != "NO_GO"
                or p05.get("safety_hold_latched") is not True
                or type(p05.get("p05_checks")) is not list
                or len(p05["p05_checks"]) != 8):
            errors.append("P05_07_P05_NOT_INDEPENDENTLY_CLEARED")
        else:
            row6 = p05["p05_checks"][5]
            decision = row6.get("owner_accepted_storage_security_scope", {})
            if (row6.get("check_id") != "P05-06"
                    or row6.get("p05_accepted") is not False
                    or row6.get("safe_to_proceed") is not False
                    or decision.get("accepted_for") !=
                    "OFFLINE_DESIGN_AND_SYNTHETIC_TEST_PLANNING_ONLY"
                    or decision.get("p05_independent_preflight_accepted")
                    is not False
                    or decision.get("real_mt4_session_or_data_collection_authorized")
                    is not False):
                errors.append("P05_07_STORAGE_ACCEPTANCE_NOT_MT4_SIGNOFF")
        if (template.get("schema_version") != 3
                or template.get("kind") !=
                "MT4_MANUAL_SYMBOL_PROPERTIES_3P_V3"
                or template.get("scope") != "OFFLINE_3P_DESIGN_INPUT_ONLY"
                or template.get("data_state") != "UNVERIFIED_LOCAL_VALUES"):
            errors.append("P05_07_BLANK_TEMPLATE_SOURCE_DRIFT")
        symbols = template.get("symbols")
        if type(symbols) is not list or len(symbols) != 3:
            errors.append("P05_07_BLANK_TEMPLATE_3_PAIRS_REQUIRED")
        else:
            for i, pair in enumerate(PAIRS):
                record = symbols[i]
                if (not _keys_exact(record,
                                    ("symbol", "observation", "properties",
                                     "display_properties"))
                        or record.get("symbol") != pair):
                    errors.append("P05_07_TEMPLATE_SYMBOL_DRIFT:" + str(i + 1))
                    continue
                obs, props, display = (record[k] for k in
                                       ("observation", "properties",
                                        "display_properties"))
                if (not _keys_exact(obs, OBS_KEYS)
                        or not all(obs[k] is None for k in OBS_KEYS)):
                    errors.append("P05_07_OBSERVATION_NOT_BLANK:" + str(i + 1))
                if (not _keys_exact(props, PROPERTY_KEYS)
                        or not all(props[k] is None for k in PROPERTY_KEYS)):
                    errors.append("P05_07_BROKER_PROPERTIES_NOT_BLANK:"
                                  + str(i + 1))
                if not _keys_exact(display, DISPLAY_KEYS):
                    errors.append("P05_07_DISPLAY_SCHEMA_CHANGED:" + str(i + 1))
                else:
                    for k in DISPLAY_KEYS:
                        if k == "trading_hours_display":
                            hours = display[k]
                            if (not _keys_exact(hours, WEEKDAYS)
                                    or not all(hours[day] is None for day in
                                               WEEKDAYS)):
                                errors.append("P05_07_HOURS_NOT_BLANK:"
                                              + str(i + 1))
                        elif display[k] is not None:
                            errors.append("P05_07_DISPLAY_DATA_NOT_BLANK:"
                                          + str(i + 1))
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            IndexError, StopIteration):
        errors.append("P05_07_MALFORMED_OR_MISSING_OFFLINE_INPUT")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_OFFLINE_SCHEMA_ONLY" if not errors else "FAIL_CLOSED",
        "pairs": 3,
        "required_g1_fields": 15,
        "real_g1_fields_verified": 0,
        "owner_storage_accepted_for_offline_planning_only": not errors,
        "p05_passed": 0,
        "actual_mt4_read_authorized": False,
        "real_broker_evidence_collected": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
