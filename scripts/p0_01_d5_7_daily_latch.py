"""D5-7: pure synthetic NY17 daily-stop latch. Never authorizes orders.

An explicit prior halt persists through rollover. A hypothetical next-day
safety review may be recorded but cannot enable runtime trading.
"""
from __future__ import annotations
from scripts.p0_01_d5_4_synthetic_risk import evaluate_synthetic_limits
from scripts.p0_01_d5_6_ny17_boundary import label_synthetic_ny17, VALID

KEYS = frozenset(("origin", "utc_timestamp", "previous_day_label",
                  "previous_daily_stop", "next_day_safety_checked",
                  "risk_fixture"))
RISK_VALID = "SYNTHETIC_WITHIN_LIMITS_NEVER_AUTHORIZED"


def evaluate_daily_latch(payload: object) -> dict[str, object]:
    status = "REVIEW_REQUIRED"
    label = None
    latch = True  # fail closed even on invalid inputs
    try:
        if (type(payload) is dict and set(payload) == KEYS
                and payload["origin"] == "SYNTHETIC_ONLY"
                and type(payload["previous_daily_stop"]) is bool
                and type(payload["next_day_safety_checked"]) is bool
                and type(payload["previous_day_label"]) is str):
            time_result = label_synthetic_ny17(payload["utc_timestamp"])
            risk_result = evaluate_synthetic_limits(payload["risk_fixture"])
            label = time_result["trading_day_start_ny_date"]
            if time_result["status"] == VALID and risk_result["status"] != "REVIEW_REQUIRED":
                old = payload["previous_day_label"]
                # Comparison only; do not treat an arbitrary date as trustworthy.
                if len(old) == 10 and old <= label:
                    changed = old != label
                    daily_stop = risk_result["status"] == "DAILY_STOP"
                    hard_stop = risk_result["status"] == "HARD_STOP_DD5"
                    if hard_stop:
                        status = "HARD_STOP_DD5"
                    elif daily_stop:
                        status = "DAILY_STOP"
                    elif payload["previous_daily_stop"]:
                        if not changed:
                            status = "DAILY_STOP_LATCHED"
                        elif not payload["next_day_safety_checked"]:
                            status = "NEXT_DAY_REVIEW_PENDING"
                        elif risk_result["status"] != RISK_VALID:
                            status = "NEXT_DAY_REVIEW_REQUIRED"
                        else:
                            status = "OFFLINE_REVIEW_ONLY_NEVER_AUTO_RESUME"
                    else:
                        status = ("RISK_REVIEW_REQUIRED"
                                  if risk_result["status"] != RISK_VALID
                                  else "SYNTHETIC_MONITORING_ONLY")
                    latch = payload["previous_daily_stop"] or daily_stop or hard_stop
    except Exception:
        status = "REVIEW_REQUIRED"
    return {"status": status, "trading_day_start_ny_date": label,
            "daily_stop_latched": latch,
            "broker_verified": False, "production_usable": False,
            "orders_generated": False, "terminal_execution_approved": False,
            "forward_trading_enabled": False, "phase_1": "BLOCKED"}
