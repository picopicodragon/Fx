"""FWD-013: research-only time-series risk alarms on supplied shadow equity.

No automated execution, no MT4 account data and no certification of actual
broker equity. NY 17:00 boundary follows America/New_York DST transitions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from research.offline_backtest import InputError, timestamp

TZ = ZoneInfo("America/New_York")
MAX_POINTS = 50000
SCHEMA = "fx_forward_shadow_risk_timeline_v1"


def _amount(value, label, *, nonnegative=False):
    if type(value) is not str:
        raise InputError("invalid " + label)
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise InputError("invalid " + label) from exc
    if not d.is_finite() or (nonnegative and d < 0):
        raise InputError("invalid " + label)
    return d


def trading_day(timestamp_utc: str) -> str:
    local = timestamp(timestamp_utc).astimezone(TZ)
    # Before New York 17:00 the trading day belongs to previous calendar date.
    day = local.date() if local.hour >= 17 else (
        local.date() - timedelta(days=1))
    return day.isoformat()


def evaluate(samples: list[dict]) -> dict:
    if type(samples) is not list or not 1 <= len(samples) <= MAX_POINTS:
        raise InputError("nonempty bounded timeline required")
    previous_time = None
    peak = None
    day_initial = None
    current_day = None
    maximum_dd = Decimal("0")
    maximum_daily_loss = Decimal("0")
    maximum_risk = Decimal("0")
    held_level3 = False
    held_dd5 = False
    held_daily = False
    held_concurrent = False
    transitions = []
    days = set()
    for number, point in enumerate(samples, 1):
        if type(point) is not dict or set(point) != {
                "observed_at_utc", "equity_jpy", "open_risk_jpy",
                "source_status"} or (
                point["source_status"] != "HYPOTHETICAL_UNVERIFIED"):
            raise InputError("invalid risk snapshot")
        now = timestamp(point["observed_at_utc"])
        if previous_time is not None and now <= previous_time:
            raise InputError("non-monotonic risk timeline")
        previous_time = now
        equity = _amount(point["equity_jpy"], "equity", nonnegative=True)
        exposure = _amount(point["open_risk_jpy"], "open risk",
                           nonnegative=True)
        if equity == 0:
            raise InputError("zero hypothetical equity")
        if peak is None or equity > peak:
            peak = equity
        day = trading_day(point["observed_at_utc"])
        if day != current_day:
            current_day = day
            day_initial = equity
            days.add(day)
        dd = (peak - equity) / peak
        daily_loss = max(Decimal("0"), (day_initial - equity) / day_initial)
        exposure_fraction = exposure / equity
        maximum_dd = max(maximum_dd, dd)
        maximum_daily_loss = max(maximum_daily_loss, daily_loss)
        maximum_risk = max(maximum_risk, exposure_fraction)
        alarms = []
        if dd >= Decimal("0.02"):
            alarms.append("DD_LEVEL1_2_PERCENT")
        if dd >= Decimal("0.03"):
            alarms.append("DD_LEVEL2_3_PERCENT")
        if dd >= Decimal("0.04"):
            held_level3 = True
            alarms.append("DD_LEVEL3_4_PERCENT_LATCHED")
        if dd >= Decimal("0.05"):
            held_dd5 = True
            alarms.append("DD_HARD_STOP_5_PERCENT_LATCHED")
        if daily_loss >= Decimal("0.015"):
            held_daily = True
            alarms.append("DAILY_LOSS_1_5_PERCENT")
        if exposure_fraction > Decimal("0.01"):
            held_concurrent = True
            alarms.append("CONCURRENT_RISK_ABOVE_1_PERCENT")
        if alarms:
            transitions.append({
                "sample_number": number,
                "observed_at_utc": point["observed_at_utc"],
                "trading_day_ny17": day,
                "alarms": alarms,
            })
    return {
        "schema": SCHEMA,
        "status": "HYPOTHETICAL_RISK_MONITOR_NO_GO",
        "sample_count": len(samples),
        "trading_day_count": len(days),
        "last_ny17_trading_day": current_day,
        "maximum_hypothetical_drawdown_fraction": str(maximum_dd),
        "maximum_hypothetical_daily_loss_fraction": str(maximum_daily_loss),
        "maximum_hypothetical_concurrent_risk_fraction": str(maximum_risk),
        "hypothetical_dd_level3_latched": held_level3,
        "hypothetical_dd_hard_stop_latched": held_dd5,
        "hypothetical_daily_loss_latched": held_daily,
        "hypothetical_concurrent_risk_violated": held_concurrent,
        "alarm_points": transitions,
        "account_equity_authenticated": False,
        "price_source_verified": False,
        "trade_by_trade_risk_certified": False,
        "daily_restart_authorized": False,
        "level3_or_dd5_human_approval_obtained": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Research shadow equity risk audit; no orders")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if (args.out.exists() or not args.out.parent.is_dir()
                or not args.input.is_file()
                or args.input.stat().st_size > 6_000_000):
            raise InputError("unsafe input or output path")
        obj = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if type(obj) is not dict or set(obj) != {"schema", "samples"} or (
                obj["schema"] != SCHEMA):
            raise InputError("incorrect timeline schema")
        report = evaluate(obj["samples"])
        with args.out.open("x", encoding="utf-8") as out:
            json.dump(report, out, ensure_ascii=False, indent=2)
        print(json.dumps({"status": report["status"],
                          "hypothetical_dd_level3_latched":
                          report["hypothetical_dd_level3_latched"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_SHADOW_EQUITY_TIMELINE",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
