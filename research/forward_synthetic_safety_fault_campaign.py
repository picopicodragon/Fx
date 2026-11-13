"""FWD-721..800: deterministic offline safety fault campaign.

Exercises existing shadow-risk, observation watchdog and research blackout
logic without observing prices, modifying MT4, clearing latches, or sending
orders. All fixtures are deliberately SYNTHETIC. This can detect regressions,
but success is NEVER evidence that broker/EA runtime protections work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from research import forward_risk_timeline as risk
from research import forward_shadow_watch as watch
from research import forward_macro_event_windows as windows
from research.forward_bls_calendar import URL as BLS_URL
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_synthetic_safety_fault_campaign_v1"
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
BASE = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)
RISK_BASE = datetime(2026, 11, 10, 22, 0, tzinfo=timezone.utc)
EVENT = "2026-11-20T15:00:00Z"
HARD_REQUIREMENTS = (
    "SYNTHETIC_RESULTS_NOT_PROOF_OF_BROKER_RISK_CONTROLS",
    "BROKER_CLOCK_NOT_INDEPENDENTLY_ATTESTED",
    "LIVE_BIDIRECTIONAL_HEARTBEAT_NOT_VERIFIED",
    "AUTOTRADING_AND_ORDER_DISABLE_NOT_INDEPENDENTLY_VERIFIED",
    "REAL_DD4_DD5_APPROVAL_INTERLOCK_NOT_VERIFIED",
    "REAL_ECONOMIC_RELEASE_BLACKOUT_NOT_VERIFIED",
    "HUMAN_REAUTHORIZATION_NOT_PRESENT",
)


def _utc(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _point(minute: int, equity: str, exposure: str = "0") -> dict:
    return {
        "observed_at_utc": _utc(RISK_BASE + timedelta(minutes=minute)),
        "equity_jpy": equity,
        "open_risk_jpy": exposure,
        "source_status": "HYPOTHETICAL_UNVERIFIED",
    }


def _observed(at: datetime) -> tuple[dict, dict]:
    time = _utc(at)
    observability = {
        "status": "FORWARD_OBSERVABILITY_HOLD_NO_GO",
        "asof_utc": time,
        "latest_cycle_age_seconds": 0,
        "blocking_reasons": [],
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }
    quote = {
        "status": "QUOTE_CONTINUITY_RESEARCH_NO_GO",
        "asof_utc": time,
        "by_pair": {
            pair: {
                "latest_quote_age_seconds": 0,
                "blocking_reasons": [],
            } for pair in PAIRS
        },
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }
    return observability, quote


def _calendar() -> dict:
    return {
        "status": "BLS_CALENDAR_RESEARCH_ONLY_NO_GO",
        "asof_utc": "2026-11-13T00:00:00Z",
        "horizon_days": 14,
        "source_url": BLS_URL,
        "source_authenticity_verified": False,
        "calendar_covers_all_fx_events": False,
        "calendar_sha256": "a" * 64,
        "events": [{
            "title": "SYNTHETIC_EVENT_NOT_REAL",
            "scheduled_at_utc": EVENT,
            "source_url": BLS_URL,
            "source_status": "PUBLISHED_SCHEDULE_UNVERIFIED",
        }],
        "event_count": 1,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _check_safe(report: dict, *, expected_status: str,
                execution_key: str | None = None) -> None:
    if (type(report) is not dict
            or report.get("status") != expected_status
            or report.get("runtime_go_no_go") != "NO_GO"
            or report.get("safety_hold_latched") is not True
            or report.get("real_orders_permitted") is not False):
        raise InputError("synthetic child research report violated NO_GO")
    if execution_key and report.get(execution_key) is not False:
        raise InputError("synthetic child could permit demo or live execution")
    if ("demo_orders_permitted" in report
            and report["demo_orders_permitted"] is not False):
        raise InputError("synthetic child has unsafe demo permission")


def _assert(condition: bool, case: str) -> None:
    if condition is not True:
        raise InputError("synthetic safety scenario failed: " + case)


def _reject(operation, case: str) -> None:
    try:
        operation()
    except (InputError, ValueError, TypeError, KeyError, OverflowError):
        return
    raise InputError("unsafe simulated input was not rejected: " + case)


def inspect() -> dict:
    cases = []

    def run(case: str, condition: bool):
        _assert(condition, case)
        cases.append({"case": case, "synthetic_contract_passed": True})

    def checked_risk(samples):
        report = risk.evaluate(samples)
        _check_safe(report, expected_status="HYPOTHETICAL_RISK_MONITOR_NO_GO",
                    execution_key="demo_order_execution_enabled")
        return report

    base = _point(0, "100000")

    # Drawdown threshold boundaries and persistent human-approval interlock.
    for label, equity, key, expected in (
        ("dd_below_2", "98001", "hypothetical_dd_level3_latched", False),
        ("dd_exact_2", "98000", "hypothetical_dd_level3_latched", False),
        ("dd_exact_3", "97000", "hypothetical_dd_level3_latched", False),
        ("dd_exact_4_latched", "96000", "hypothetical_dd_level3_latched", True),
        ("dd_exact_5_hard_latched", "95000", "hypothetical_dd_hard_stop_latched", True),
    ):
        result = checked_risk([base, _point(1, equity)])
        run(label, result.get(key) is expected)
    r2 = checked_risk([base, _point(1, "98000")])
    r3 = checked_risk([base, _point(1, "97000")])
    run("dd_level1_exact_alarm",
        "DD_LEVEL1_2_PERCENT" in r2["alarm_points"][-1]["alarms"])
    run("dd_level2_exact_alarm",
        "DD_LEVEL2_3_PERCENT" in r3["alarm_points"][-1]["alarms"])
    r_below4 = checked_risk([base, _point(1, "96001")])
    run("dd_below4_no_level3_latch",
        r_below4["hypothetical_dd_level3_latched"] is False)
    r_below5 = checked_risk([base, _point(1, "95001")])
    run("dd_below5_no_hard_latch",
        r_below5["hypothetical_dd_hard_stop_latched"] is False)
    recovery = checked_risk([
        base, _point(1, "94900"), _point(2, "104000")])
    run("dd5_recovery_does_not_clear_level3",
        recovery["hypothetical_dd_level3_latched"] is True)
    run("dd5_recovery_does_not_clear_dd5",
        recovery["hypothetical_dd_hard_stop_latched"] is True)
    run("dd5_never_claims_human_approval",
        recovery["level3_or_dd5_human_approval_obtained"] is False)

    r_daily = checked_risk([base, _point(1, "98500")])
    run("daily_loss_exact_1_5_percent",
        r_daily["hypothetical_daily_loss_latched"] is True)
    r_daily_below = checked_risk([base, _point(1, "98501")])
    run("daily_loss_below_1_5_percent",
        r_daily_below["hypothetical_daily_loss_latched"] is False)
    r_total = checked_risk([base, _point(1, "100000", "1000")])
    run("concurrent_risk_exact_1_percent_not_above",
        r_total["hypothetical_concurrent_risk_violated"] is False)
    r_total_hi = checked_risk([base, _point(1, "100000", "1001")])
    run("concurrent_risk_above_1_percent",
        r_total_hi["hypothetical_concurrent_risk_violated"] is True)
    run("single_trade_0_5_percent_arithmetic_only",
        Decimal("500") / Decimal("100000") == Decimal("0.005")
        and Decimal("501") / Decimal("100000") > Decimal("0.005"))
    run("ny17_summer_boundary",
        risk.trading_day("2026-07-01T20:59:59Z") == "2026-06-30"
        and risk.trading_day("2026-07-01T21:00:00Z") == "2026-07-01")
    run("ny17_winter_boundary",
        risk.trading_day("2026-11-10T21:59:59Z") == "2026-11-09"
        and risk.trading_day("2026-11-10T22:00:00Z") == "2026-11-10")

    _reject(lambda: checked_risk([
        _point(1, "100000"), _point(0, "99000")]),
        "reverse_equity_time")
    cases.append({"case": "reverse_equity_time_rejected",
                  "synthetic_contract_passed": True})
    _reject(lambda: checked_risk([_point(0, "NaN")]),
            "nonfinite_hypothetical_equity")
    cases.append({"case": "nonfinite_hypothetical_equity_rejected",
                  "synthetic_contract_passed": True})

    obs, quotes = _observed(BASE)
    def evaluated(second: int, *, prior=None, fresh_at=None):
        o, q = _observed(fresh_at or BASE)
        result = watch.evaluate(
            o, q, asof_utc=_utc(BASE + timedelta(seconds=second)),
            prior=prior)
        _check_safe(result,
                    expected_status="FORWARD_SHADOW_WATCH_HOLD_NO_GO",
                    execution_key="demo_order_execution_enabled")
        _assert(result.get("resume_automatically_permitted") is False,
                "watchdog_no_auto_resume")
        return result

    for seconds, expected in (
        (59, "NONE"), (60, "LEVEL1"),
        (599, "LEVEL1"), (600, "LEVEL2")):
        report = evaluated(seconds)
        run("outage_threshold_" + str(seconds) + "_" + expected.lower(),
            report["interruption_level"] == expected)
    level2 = evaluated(600)
    recovered = evaluated(
        601, prior=level2, fresh_at=BASE+timedelta(seconds=601))
    run("watchdog_latch_persists_after_quotes_recover",
        recovered["interruption_level"] == "NONE"
        and recovered["watchdog_latched"] is True
        and "PREVIOUS_WATCHDOG_LATCH_NOT_CLEARED"
        in recovered["blocking_reasons"])
    run("watchdog_never_claims_independent_heartbeat",
        level2["bidirectional_mt4_heartbeat_verified"] is False
        and level2["independent_watchdog_running"] is False)
    run("watchdog_recovery_requires_external_safety_check",
        recovered["human_approval_recorded"] is False
        and recovered["resume_automatically_permitted"] is False)

    for field in ("latest_cycle_age_seconds",):
        o, q = _observed(BASE)
        o[field] = float("nan")
        _reject(lambda o=o, q=q: watch.evaluate(
            o, q, asof_utc=_utc(BASE)), "nan_cycle_age")
        cases.append({"case": "nan_cycle_age_rejected",
                      "synthetic_contract_passed": True})
    o, q = _observed(BASE)
    q["by_pair"]["USD/JPY"]["latest_quote_age_seconds"] = float("inf")
    _reject(lambda: watch.evaluate(o, q, asof_utc=_utc(BASE)),
            "infinite_quote_age")
    cases.append({"case": "infinite_quote_age_rejected",
                  "synthetic_contract_passed": True})
    o, q = _observed(BASE)
    forged = dict(level2, watchdog_latched=1)
    _reject(lambda: watch.evaluate(
        o, q, asof_utc=_utc(BASE+timedelta(seconds=601)), prior=forged),
        "forged_numeric_watchdog_latch")
    cases.append({"case": "numeric_watchdog_latch_rejected",
                  "synthetic_contract_passed": True})

    calendar = _calendar()
    for title, clock, expected_state in (
        ("before_blackout", "2026-11-20T14:44:59Z",
         "BEFORE_RESEARCH_BLACKOUT"),
        ("blackout_exact_minus15", "2026-11-20T14:45:00Z",
         "WITHIN_RESEARCH_BLACKOUT"),
        ("blackout_one_second_before_plus15", "2026-11-20T15:14:59Z",
         "WITHIN_RESEARCH_BLACKOUT"),
        ("after_plus15_requires_reassessment", "2026-11-20T15:15:00Z",
         "AFTER_EVENT_REQUIRES_INDEPENDENT_REASSESSMENT"),
    ):
        result = windows.inspect(calendar, asof_utc=clock)
        _check_safe(result, expected_status="BLS_MACRO_WINDOWS_RESEARCH_HOLD_NO_GO",
                    execution_key="demo_orders_permitted")
        case = result["windows"][0]
        run(title, case["research_state"] == expected_state
            and case["new_orders_permitted"] is False
            and case["automatic_resume_authorized"] is False)
    _reject(lambda: windows.inspect(
        dict(calendar, calendar_sha256="NOT_A_HASH"),
        asof_utc="2026-11-20T14:45:00Z"),
        "forged_calendar_hash")
    cases.append({"case": "forged_calendar_hash_rejected",
                  "synthetic_contract_passed": True})

    payload = json.dumps(cases, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {
        "schema": SCHEMA,
        "status": "SYNTHETIC_SAFETY_FAULT_CAMPAIGN_HOLD_NO_GO",
        "synthetic_scenario_count": len(cases),
        "synthetic_passed_count": len(cases),
        "synthetic_failed_count": 0,
        "synthetic_cases_sha256": hashlib.sha256(payload).hexdigest(),
        "synthetic_scenarios": cases,
        "real_source_events_or_broker_evidence_used": False,
        "live_mt4_connection_ever_attempted": False,
        "synthetic_green_is_operational_acceptance": False,
        "unresolved_operational_holds": list(HARD_REQUIREMENTS),
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Bounded deterministic synthetic safety drill; NO_GO only")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)
    try:
        report = inspect()
        if args.out is not None:
            from pathlib import Path
            path = Path(args.out)
            if (path.exists() or path.is_symlink()
                    or not path.parent.is_dir() or path.parent.is_symlink()):
                raise InputError("unsafe synthetic drill output")
            with path.open("x", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False,
                          allow_nan=False)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, ValueError, TypeError, KeyError,
            OSError, OverflowError, ArithmeticError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "SYNTHETIC_SAFETY_FAULT_CAMPAIGN_FAIL_CLOSED_NO_GO",
            "reason_code": "SAFETY_DRILL_UNVERIFIED_OR_FAILED",
            "network_calls_this_run": 0, "API_calls_this_run": 0,
            "actual_orders_sent": 0,
            "demo_orders_permitted": False, "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
