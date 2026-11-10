"""FWD-027: immutable research-level go/no-go evidence board.

Inputs are offline research audits only. Never issues a positive go decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.offline_backtest import InputError

SCHEMA = "fx_forward_demo_gate_board_v1"
EXPECTED = {
    "demo": "FWD_DEMO_READINESS_RESEARCH_NO_GO",
    "watch": "FORWARD_SHADOW_WATCH_HOLD_NO_GO",
    "mt4": "MT4_READONLY_EXPORT_RESEARCH_NO_GO",
    "calendar": "CALENDAR_REVISION_RESEARCH_NO_GO",
}


def board(reports: dict) -> dict:
    if type(reports) is not dict:
        raise InputError("invalid reports")
    reasons = []
    for key, status in EXPECTED.items():
        value = reports.get(key)
        if value is None:
            reasons.append("MISSING_" + key.upper())
            continue
        if (type(value) is not dict or value.get("status") != status or
                value.get("runtime_go_no_go") != "NO_GO" or
                value.get("safety_hold_latched") is not True or
                value.get("real_orders_permitted") is not False or
                value.get("demo_order_execution_enabled") is not False):
            raise InputError("unsafe " + key + " report")
        if key == "watch" and value.get("watchdog_latched") is True:
            reasons.append("WATCHDOG_LATCHED")
        if key == "mt4" and value.get("missing_pairs"):
            reasons.append("MT4_QUOTES_INCOMPLETE")
        if key == "calendar" and value.get("change_count"):
            reasons.append("EVENT_SCHEDULE_REVISED")
        if key == "demo" and value.get("blocking_reasons"):
            reasons.append("DEMO_PREP_NOT_CERTIFIED")
    reasons += ["INDEPENDENT_BROKER_ATTESTATION_MISSING",
                "ORDER_SAFETY_ACCEPTANCE_NOT_GRANTED",
                "MARKET_DATA_LICENSE_NOT_VERIFIED",
                "FORWARD_REAL_EXECUTION_FORBIDDEN"]
    return {
        "schema": SCHEMA, "status": "FWD_DEMO_GATE_BOARD_NO_GO",
        "evidence_keys_present": sorted(reports),
        "blocking_reasons": sorted(set(reasons)),
        "research_evidence_sufficient_to_enable_orders": False,
        "approval_request_generated": False,
        "mt4_access_performed": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 1_000_000:
        raise InputError("invalid report file")
    v = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(v) is not dict:
        raise InputError("report is not object")
    return v


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline read-only demo safety board")
    for key in EXPECTED:
        p.add_argument("--"+key, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if args.out.exists() or not args.out.parent.is_dir():
            raise InputError("output path exists")
        result = board({key: _read(getattr(args, key))
                        for key in EXPECTED if getattr(args, key) is not None})
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps({"status": result["status"],
                          "blocking_reasons": result["blocking_reasons"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, ValueError, TypeError, KeyError, OSError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_FWD_DEMO_GATE_EVIDENCE",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
