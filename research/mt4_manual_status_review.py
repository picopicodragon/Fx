"""FX-FWD-006: offline review of manually exported MT4 demo status.

Never opens a socket, reads terminal memory, logs into broker, or invokes an EA.
The data is self-reported and MUST NOT be considered account attestation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_mt4_observer_status_v1"


def inspect_status(obj: dict) -> dict:
    if (type(obj) is not dict or
            set(obj) != {"schema", "sampled_at_utc", "account_type",
                         "connection_display", "autotrading_display",
                         "scripts_or_eas_present", "open_positions",
                         "pending_orders", "source"} or
            obj["schema"] != SCHEMA or
            obj["account_type"] not in ("DEMO", "LIVE", "UNKNOWN") or
            obj["connection_display"] not in
            ("CONNECTED_LIKE", "DISCONNECTED_LIKE", "UNKNOWN") or
            obj["autotrading_display"] not in
            ("ON_LIKE", "OFF_LIKE", "UNKNOWN") or
            type(obj["scripts_or_eas_present"]) is not bool or
            type(obj["open_positions"]) is not int or
            type(obj["pending_orders"]) is not int or
            not 0 <= obj["open_positions"] <= 100000 or
            not 0 <= obj["pending_orders"] <= 100000 or
            obj["source"] != "MANUAL_UNVERIFIED_STATUS"):
        raise InputError("invalid MT4 status summary")
    stamp = timestamp(obj["sampled_at_utc"])
    conflicts = []
    if obj["account_type"] != "DEMO":
        conflicts.append("ACCOUNT_NOT_CONFIRMED_DEMO")
    if obj["connection_display"] != "CONNECTED_LIKE":
        conflicts.append("CONNECTION_NOT_RELIABLY_CONNECTED")
    if obj["autotrading_display"] != "OFF_LIKE":
        conflicts.append("AUTOTRADING_DISPLAY_NOT_OFF")
    if obj["scripts_or_eas_present"]:
        conflicts.append("UNREVIEWED_EA_OR_SCRIPT_PRESENT")
    if obj["open_positions"] or obj["pending_orders"]:
        conflicts.append("EXISTING_ORDERS_OR_POSITIONS")
    # This is still NOT sufficient to authorize any MT4 commands.
    return {
        "status": "MT4_MANUAL_STATUS_RESEARCH_NO_GO",
        "sampled_at_utc": obj["sampled_at_utc"],
        "input_self_reported": True,
        "mt4_terminal_queried": False,
        "mt4_account_identity_verified": False,
        "mt4_broker_or_session_verified": False,
        "account_type_claimed": obj["account_type"],
        "read_only_review_flags": conflicts,
        "connection_enabled": False,
        "demo_order_execution_enabled": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Inspect manually supplied MT4 DEMO status; no MT4 link")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if (args.input.stat().st_size > 3000 or args.out.exists()
                or not args.out.parent.is_dir()):
            raise InputError("invalid MT4 snapshot size or output path")
        obj = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = inspect_status(obj)
        with args.out.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": result["status"],
            "read_only_review_flags": result["read_only_review_flags"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0
    except (InputError, ValueError, TypeError,
            OSError, UnicodeError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MT4_MANUAL_STATUS_UNVERIFIED_OR_INVALID",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
