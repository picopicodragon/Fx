"""P05-02/05: offline EA posture and no-interference contract simulation.

This module does not inspect actual charts, invoke an EA or change AutoTrading.
"""
from __future__ import annotations

SCHEMA_KEYS = ("schema", "classification", "prior_owner_report",
               "simulation", "safety")
SIM_KEYS = ("ea_visible", "autotrading_display", "face_display",
            "ea_execution_proven", "unknown_ea_excluded",
            "positions_or_orders_reconciled", "proposed_interaction",
            "interaction_side_effect_proven_absent")
SAFETY = {
    "p05_passed": 0, "p05_02_accepted": False,
    "p05_05_accepted": False, "real_mt4_session_authorized": False,
    "ea_execution_or_stop_authorized": False,
    "autotrading_toggle_authorized": False,
    "script_execution_authorized": False,
    "position_or_order_change_authorized": False,
    "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
}


def fixture() -> dict:
    return {
        "schema": 1, "classification": "OFFLINE_EA_SIMULATION_ONLY",
        "prior_owner_report": "MACD_VISIBLE_SAD_FACE_AUTOTRADING_OFF_LIKE",
        "simulation": {
            "ea_visible": "SIM_MACD_SAMPLE_VISIBLE",
            "autotrading_display": "SIM_OFF_LIKE",
            "face_display": "SIM_SAD_FACE",
            "ea_execution_proven": False,
            "unknown_ea_excluded": False,
            "positions_or_orders_reconciled": False,
            "proposed_interaction": "SIM_NO_TERMINAL_INTERACTION",
            "interaction_side_effect_proven_absent": False,
        },
        "safety": dict(SAFETY),
    }


def evaluate(value: object) -> dict:
    errors = []
    if type(value) is not dict or set(value) != set(SCHEMA_KEYS):
        errors.append("P39_SCHEMA_OR_SECRET_FIELD_INVALID")
    else:
        if (type(value["schema"]) is not int or value["schema"] != 1
                or value["classification"] != "OFFLINE_EA_SIMULATION_ONLY"
                or value["prior_owner_report"] !=
                "MACD_VISIBLE_SAD_FACE_AUTOTRADING_OFF_LIKE"):
            errors.append("P39_OWNER_EA_UI_OVERCLAIMED")
        if value["safety"] != SAFETY:
            errors.append("P39_FORGED_EA_OR_ORDER_PERMISSION")
        data = value["simulation"]
        if type(data) is not dict or set(data) != set(SIM_KEYS):
            errors.append("P39_SIMULATION_MISSING_OR_EXTRA_FIELDS")
        elif (data["ea_visible"] != "SIM_MACD_SAMPLE_VISIBLE"
              or data["autotrading_display"] != "SIM_OFF_LIKE"
              or data["face_display"] != "SIM_SAD_FACE"
              or data["ea_execution_proven"] is not False
              or data["unknown_ea_excluded"] is not False
              or data["positions_or_orders_reconciled"] is not False):
            errors.append("P39_UNVERIFIED_EA_ACTIVITY_OR_ORDERS_CLAIMED")
        if type(data) is dict and set(data) == set(SIM_KEYS):
            if (data["proposed_interaction"] !=
                    "SIM_NO_TERMINAL_INTERACTION"
                    or data["interaction_side_effect_proven_absent"]
                    is not False):
                errors.append("P39_UNAUTHORIZED_INTERACTION_OR_FALSE_PROOF")
    return {
        "status": "PASS_OFFLINE_NON_INTERFERENCE_PLAN_ONLY"
        if not errors else "FAIL_CLOSED",
        "actual_ea_runtime_verified": False,
        "actual_autotrading_off_verified": False,
        "actual_order_absence_verified": False,
        "terminal_interaction_permitted": False,
        "p05_02_accepted": False, "p05_05_accepted": False,
        "p05_passed_checks": 0, "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True, "errors": errors,
    }
