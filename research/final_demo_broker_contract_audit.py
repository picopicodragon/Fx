"""Read-only analysis of a single DEMO MT4 broker contract snapshot.

Collects terms required for risk gates, but NEVER authorizes trading or
treats broker-reported cash/times as independently verified. No inference,
network, order intents or terminal interaction. Account number is private.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from research.offline_backtest import InputError

SCHEMA = "fx_final_demo_broker_contract_snapshot_audit_v1"
PATTERN = re.compile(r"^FxDemoBrokerSafety_[0-9]{8}_[0-9]{6}\.csv$")
PAIRS = ("USDJPY", "EURJPY", "EURUSD")
FIELDS = (
    "account_type", "account_number", "account_currency",
    "balance_jpy_broker_reported", "equity_jpy_broker_reported",
    "open_or_pending_orders_all_eas", "pc_utc_epoch_unattested",
    "broker_time_epoch_unattested", "symbol", "bid", "ask",
    "tick_time_server_epoch_unattested",
    "tickvalue_jpy_broker_reported", "ticksize_points_broker_reported",
    "lot_step", "min_lot", "max_lot", "stop_level_points",
    "freeze_level_points", "point", "digits", "trade_allowed_broker",
)
SAFE_FAILURES = frozenset({
    "SNAPSHOT_MISSING_OR_UNSAFE",
    "SNAPSHOT_FORMAT_INVALID",
    "SNAPSHOT_NOT_THREE_PAIRS",
    "SNAPSHOT_NOT_DEMO_JPY",
    "SNAPSHOT_ACCOUNT_MISMATCH",
    "SNAPSHOT_CLOCK_OR_ORDER_MISMATCH",
    "SNAPSHOT_ACCOUNT_EQUITY_INVALID",
    "SNAPSHOT_PRICE_CONTRACT_INVALID",
    "SNAPSHOT_STALE_OR_PC_CLOCK_SKEW",
    "SNAPSHOT_BROKER_QUOTES_STALE",
    "SNAPSHOT_ORDER_PRESENT",
    "SNAPSHOT_TRADE_NOT_AVAILABLE",
    "OUTPUT_UNSAFE",
})


def audit(path: Path, *, now: datetime | None = None) -> dict:
    if (not path.is_file() or path.is_symlink() or
            any(part.is_symlink() for part in path.parents)
            or not PATTERN.fullmatch(path.name)
            or not 0 < path.stat().st_size <= 6000):
        raise InputError("SNAPSHOT_MISSING_OR_UNSAFE")
    data = path.read_bytes()
    if b"\x00" in data:
        raise InputError("SNAPSHOT_FORMAT_INVALID")
    try:
        reader = csv.DictReader(data.decode("utf-8-sig").splitlines(),
                                strict=True)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise InputError("SNAPSHOT_FORMAT_INVALID")
        rows = list(reader)
    except (csv.Error, UnicodeError) as exc:
        raise InputError("SNAPSHOT_FORMAT_INVALID") from exc
    if len(rows) != 3 or tuple(row["symbol"] for row in rows) != PAIRS:
        raise InputError("SNAPSHOT_NOT_THREE_PAIRS")
    same = (
        "account_number", "balance_jpy_broker_reported",
        "equity_jpy_broker_reported", "open_or_pending_orders_all_eas",
        "pc_utc_epoch_unattested", "broker_time_epoch_unattested",
    )
    if any(row.get(None) is not None or set(row) != set(FIELDS) for row in rows):
        raise InputError("SNAPSHOT_FORMAT_INVALID")
    if any(row["account_type"] != "DEMO" or
           row["account_currency"] != "JPY" for row in rows):
        raise InputError("SNAPSHOT_NOT_DEMO_JPY")
    if not rows[0]["account_number"].isdigit() or (
            not 1 <= int(rows[0]["account_number"]) <= 999999999):
        raise InputError("SNAPSHOT_ACCOUNT_MISMATCH")
    if any(row[k] != rows[0][k] for row in rows[1:] for k in same):
        raise InputError("SNAPSHOT_CLOCK_OR_ORDER_MISMATCH")
    try:
        equity = float(rows[0]["equity_jpy_broker_reported"])
        balance = float(rows[0]["balance_jpy_broker_reported"])
        orders = int(rows[0]["open_or_pending_orders_all_eas"])
        pc_epoch = int(rows[0]["pc_utc_epoch_unattested"])
        broker_epoch = int(rows[0]["broker_time_epoch_unattested"])
    except (ValueError, OverflowError) as exc:
        raise InputError("SNAPSHOT_FORMAT_INVALID") from exc
    if not all(math.isfinite(x) and x > 0 for x in (equity, balance)):
        raise InputError("SNAPSHOT_ACCOUNT_EQUITY_INVALID")
    if orders < 0 or pc_epoch <= 0 or broker_epoch <= 0:
        raise InputError("SNAPSHOT_CLOCK_OR_ORDER_MISMATCH")
    if orders != 0:
        raise InputError("SNAPSHOT_ORDER_PRESENT")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("SNAPSHOT_STALE_OR_PC_CLOCK_SKEW")
    age = current.timestamp() - pc_epoch
    if not -60 <= age <= 600:
        raise InputError("SNAPSHOT_STALE_OR_PC_CLOCK_SKEW")
    contracts = []
    for row in rows:
        try:
            bid = float(row["bid"])
            ask = float(row["ask"])
            tick_time = int(row["tick_time_server_epoch_unattested"])
            point = float(row["point"])
            tickvalue = float(row["tickvalue_jpy_broker_reported"])
            ticksize = float(row["ticksize_points_broker_reported"])
            step = float(row["lot_step"])
            low = float(row["min_lot"])
            high = float(row["max_lot"])
            stop = float(row["stop_level_points"])
            freeze = float(row["freeze_level_points"])
            digits = int(row["digits"])
            trade_allowed = int(row["trade_allowed_broker"])
        except (ValueError, OverflowError) as exc:
            raise InputError("SNAPSHOT_FORMAT_INVALID") from exc
        if not (all(math.isfinite(v) for v in (
                bid,ask,point,tickvalue,ticksize,step,low,high,stop,freeze))
                and bid > 0 and ask > bid and point > 0
                and tickvalue > 0 and ticksize > 0 and step > 0
                and low > 0 and high >= low and stop >= 0 and freeze >= 0
                and 2 <= digits <= 6 and trade_allowed in (0,1)):
            raise InputError("SNAPSHOT_PRICE_CONTRACT_INVALID")
        if not 0 <= broker_epoch - tick_time <= 30:
            raise InputError("SNAPSHOT_BROKER_QUOTES_STALE")
        if trade_allowed != 1:
            raise InputError("SNAPSHOT_TRADE_NOT_AVAILABLE")
        contracts.append({
            "pair": row["symbol"],
            "bid_broker_reported": bid,
            "ask_broker_reported": ask,
            "min_lot_broker_reported": low,
            "max_lot_broker_reported": high,
            "lot_step_broker_reported": step,
            "tickvalue_jpy_broker_reported": tickvalue,
            "ticksize_points_broker_reported": ticksize,
            "point": point,
            "stop_level_points": stop,
            "freeze_level_points": freeze,
            "broker_quoted_trade_allowed": True,
            "tick_age_broker_seconds_unattested": broker_epoch - tick_time,
        })
    return {
        "schema": SCHEMA,
        "status": "DEMO_BROKER_TERMS_OBSERVED_RESEARCH_HOLD_NO_GO",
        "pair_contracts": contracts,
        "contract_count": 3,
        "reported_equity_jpy": round(equity, 2),
        "reported_balance_jpy": round(balance, 2),
        "risk_budget_per_trade_jpy_0_5pct": round(equity * .005, 2),
        "risk_budget_open_positions_jpy_1pct": round(equity * .01, 2),
        "risk_budget_daily_loss_jpy_1_5pct": round(equity * .015, 2),
        "drawdown_5pct_jpy_reference_only": round(equity * .05, 2),
        "all_broker_orders_absent_observed": True,
        "account_number_redacted": True,
        "broker_identity_independently_attested": False,
        "broker_clock_independently_attested": False,
        "tickvalue_conversion_verified": False,
        "risk_stop_order_lifecycle_verified": False,
        "terminal_trade_execution_verified": False,
        "ai_inference_calls_this_run": 0,
        "demo_orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offline-only DEMO MT4 broker contract snapshot audit")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = audit(args.snapshot)
        if args.out.is_symlink() or args.out.exists() or (
                not args.out.parent.is_dir() or
                args.out.parent.is_symlink()):
            raise InputError("OUTPUT_UNSAFE")
        with args.out.open("x", encoding="utf-8") as fp:
            json.dump(result, fp, ensure_ascii=False, indent=2,
                      allow_nan=False)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, TypeError, ValueError, OSError, UnicodeError,
            OverflowError, csv.Error) as exc:
        reason = (exc.args[0] if isinstance(exc, InputError) and exc.args
                  and type(exc.args[0]) is str else "")
        print(json.dumps({
            "schema": SCHEMA,
            "status": "DEMO_BROKER_CONTRACT_FAIL_CLOSED_NO_GO",
            "reason": reason if reason in SAFE_FAILURES else
            "BROKER_SNAPSHOT_VALIDATION_FAILED",
            "ai_inference_calls_this_run": 0,
            "demo_orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
