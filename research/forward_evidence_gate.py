"""FWD-011/012: offline, fail-closed evidence gate for forward observation.

This report is never an authorization to trade, including on a demo account.
It only diagnoses missing evidence, BLS schedule age, quote freshness and
hypothetical risk. No broker, network, paid inference or MT4 access.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from research.forward_quality import quality_report
from research.offline_backtest import InputError, PAIRS, timestamp

SCHEMA = "fx_forward_evidence_gate_v1"
MAX_CALENDAR_AGE_SECONDS = 86400
MAX_QUOTE_AGE_SECONDS = 90
BLACKOUT_SECONDS = 900
CAPITAL_JPY = Decimal("100000")
TRADE_LIMIT = Decimal("0.005")
TOTAL_RISK_LIMIT = Decimal("0.01")
DAY_LOSS_LIMIT = Decimal("0.015")
DD_STOP_LEVEL = Decimal("0.04")
DD_HARD_LIMIT = Decimal("0.05")


def _load_bounded(path: Path, *, max_bytes: int = 500000) -> dict:
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise InputError("missing or oversized evidence")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(obj) is not dict:
        raise InputError("invalid evidence shape")
    return obj


def _money(value: object, label: str) -> Decimal:
    if type(value) is not str:
        raise InputError("invalid " + label)
    try:
        num = Decimal(value)
    except InvalidOperation as exc:
        raise InputError("invalid " + label) from exc
    if not num.is_finite():
        raise InputError("nonfinite " + label)
    return num


def gate(store: Path, *, asof_utc: str, calendar: dict | None = None,
         paper: dict | None = None) -> dict:
    now = timestamp(asof_utc)
    qa = quality_report(store, asof_utc=asof_utc)
    if qa["runtime_go_no_go"] != "NO_GO" or qa["real_orders_permitted"] is not False:
        raise InputError("unsafe source quality")
    reasons = set()
    per_pair = {}
    if qa["late_capture_sequences"]:
        reasons.add("CAPTURE_DELAY")
    if qa["out_of_order_source_sequences"]:
        reasons.add("SOURCE_CLOCK_REGRESSION")
    if not qa["capture_clock_independently_verified"]:
        reasons.add("CLOCK_NOT_ATTESTED")
    if not qa["source_authenticity_verified"]:
        reasons.add("SOURCE_UNVERIFIED")
    if not qa["data_license_verified"]:
        reasons.add("DATA_LICENSE_NOT_VERIFIED")
    if not qa["full_economic_calendar_coverage_verified"]:
        reasons.add("CALENDAR_COVERAGE_INCOMPLETE")
    for pair in PAIRS:
        info = qa["current_asof_quote_freshness"][pair]
        pair_reasons = []
        if not info["quote_fresh"]:
            pair_reasons.append("MISSING_OR_STALE_QUOTE")
        if info["event_blackout_observed"]:
            pair_reasons.append("OBSERVED_EVENT_BLACKOUT")
        per_pair[pair] = {
            "quote_age_seconds": info["quote_age_seconds"],
            "research_quote_fresh": info["quote_fresh"],
            "blocking_reasons": pair_reasons,
            "demo_order_eligible": False,
            "live_order_eligible": False,
        }
    if calendar is None:
        reasons.add("FUTURE_SCHEDULE_MISSING")
    else:
        if (calendar.get("status") != "BLS_CALENDAR_RESEARCH_ONLY_NO_GO"
                or calendar.get("runtime_go_no_go") != "NO_GO"
                or calendar.get("real_orders_permitted") is not False
                or calendar.get("source_authenticity_verified") is not False
                or calendar.get("calendar_covers_all_fx_events") is not False
                or type(calendar.get("events")) is not list):
            raise InputError("invalid BLS research snapshot")
        captured = timestamp(calendar.get("asof_utc"))
        delta = (now - captured).total_seconds()
        if delta < 0 or delta > MAX_CALENDAR_AGE_SECONDS:
            reasons.add("SCHEDULE_STALE_OR_FUTURE")
        if len(calendar["events"]) > 500:
            raise InputError("calendar list too large")
        for event in calendar["events"]:
            if (type(event) is not dict or
                    event.get("source_status") != "PUBLISHED_SCHEDULE_UNVERIFIED" or
                    type(event.get("title")) is not str or
                    type(event.get("source_url")) is not str or
                    not event["source_url"].startswith("https://www.bls.gov/")):
                raise InputError("invalid schedule event")
            at = timestamp(event.get("scheduled_at_utc"))
            if abs((at - now).total_seconds()) <= BLACKOUT_SECONDS:
                reasons.add("BLS_SCHEDULED_EVENT_BLACKOUT")
                # BLS data can influence all three pairs via USD exposure.
                for pair in PAIRS:
                    per_pair[pair]["blocking_reasons"].append(
                        "BLS_SCHEDULED_EVENT_BLACKOUT")
    risk = {
        "paper_evidence_present": paper is not None,
        "single_trade_limit_respected_in_paper": None,
        "portfolio_risk_certified": False,
        "daily_loss_limit_certified": False,
        "drawdown_limit_certified": False,
        "account_equity_verified": False,
    }
    if paper is None:
        reasons.add("PAPER_EVIDENCE_MISSING")
    else:
        if (paper.get("status") != "FORWARD_HYPOTHETICAL_PAPER_REPLAY_NO_GO"
                or paper.get("runtime_go_no_go") != "NO_GO"
                or paper.get("real_orders_permitted") is not False
                or paper.get("demo_order_execution_enabled") is not False
                or paper.get("asof_utc") != asof_utc):
            raise InputError("untrusted paper result or mismatched as-of")
        position = paper.get("hypothetical_position")
        if position is not None:
            if type(position) is not dict or position.get("pair") not in PAIRS:
                raise InputError("invalid paper position")
            initial = _money(position.get("initial_risk_jpy"), "paper risk")
            if initial < 0:
                raise InputError("negative risk")
            risk["single_trade_limit_respected_in_paper"] = (
                initial <= CAPITAL_JPY * TRADE_LIMIT)
            if not risk["single_trade_limit_respected_in_paper"]:
                reasons.add("HYPOTHETICAL_TRADE_RISK_EXCEEDED")
        else:
            reasons.add("PAPER_POSITION_ABSENT")
        # Single replay is not a true daily, DD or portfolio ledger.
        reasons.add("PORTFOLIO_DAILY_DD_NOT_CERTIFIED")
    return {
        "schema": SCHEMA,
        "status": "FORWARD_EVIDENCE_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "observation_record_count": qa["record_count"],
        "global_blocking_reasons": sorted(reasons),
        "by_pair": per_pair,
        "research_risk": risk,
        "risk_limits_reference": {
            "single_trade_fraction": str(TRADE_LIMIT),
            "concurrent_risk_fraction": str(TOTAL_RISK_LIMIT),
            "daily_loss_fraction": str(DAY_LOSS_LIMIT),
            "drawdown_level3_fraction": str(DD_STOP_LEVEL),
            "drawdown_hard_stop_fraction": str(DD_HARD_LIMIT),
        },
        "source_authenticity_verified": False,
        "economic_calendar_complete": False,
        "mt4_demo_authenticated": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline forward evidence gate, NO_GO only")
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--calendar", type=Path)
    parser.add_argument("--paper", type=Path)
    parser.add_argument("--asof-utc")
    args = parser.parse_args(argv)
    try:
        if args.out.exists() or not args.out.parent.is_dir():
            raise InputError("output exists or missing directory")
        asof = args.asof_utc or datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        result = gate(args.store, asof_utc=asof,
                      calendar=_load_bounded(args.calendar) if args.calendar else None,
                      paper=_load_bounded(args.paper) if args.paper else None)
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({"status": result["status"],
                          "blocking_reasons": result["global_blocking_reasons"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (OSError, InputError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "FWD_EVIDENCE_INCOMPLETE_OR_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
