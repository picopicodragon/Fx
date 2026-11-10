"""FWD-031/032: offline AI shadow evidence audit and synthetic fault campaign.

This only checks file metadata of completed local research; it never calls a
paid inference provider, submits orders, or initiates repeated monitoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from research.offline_backtest import InputError

SCHEMA = "fx_forward_shadow_campaign_v1"
MAX_AI = 1000


def audit(ai_ledgers: list[dict], watchdog: dict,
          intake: dict, receipt: dict) -> dict:
    if type(ai_ledgers) is not list or len(ai_ledgers) > MAX_AI:
        raise InputError("invalid AI ledger batch")
    if (type(watchdog) is not dict or
            watchdog.get("status") != "FORWARD_SHADOW_WATCH_HOLD_NO_GO" or
            watchdog.get("runtime_go_no_go") != "NO_GO" or
            watchdog.get("safety_hold_latched") is not True or
            watchdog.get("real_orders_permitted") is not False or
            type(intake) is not dict or
            intake.get("status") != "SOURCE_INTAKE_RESEARCH_HOLD_NO_GO" or
            intake.get("runtime_go_no_go") != "NO_GO" or
            intake.get("safety_hold_latched") is not True or
            intake.get("real_orders_permitted") is not False or
            type(receipt) is not dict):
        raise InputError("invalid evidence bundle")
    from research.forward_restart_receipts import verify_receipt
    verify_receipt(receipt)
    pending, complete, inconsistent = 0, 0, 0
    seen = set()
    for ledger in ai_ledgers:
        if (type(ledger) is not dict or
                ledger.get("schema") != "fx_forward_ai_shadow_v1" or
                ledger.get("runtime_go_no_go") != "NO_GO" or
                ledger.get("safety_hold_latched") is not True or
                ledger.get("real_orders_permitted") is not False or
                ledger.get("stage") not in ("ANALYST_PENDING",
                                            "REVIEW_PENDING", "COMPLETE") or
                type(ledger.get("event_record_sha256")) is not str or
                len(ledger["event_record_sha256"]) != 64):
            raise InputError("unsafe AI ledger")
        event = ledger["event_record_sha256"]
        if any(c not in "0123456789abcdef" for c in event) or event in seen:
            raise InputError("duplicate or malformed event")
        seen.add(event)
        stage = ledger["stage"]
        pending_request = ledger.get("pending_request")
        if pending_request is not None:
            pending += 1
        if stage == "COMPLETE":
            if (type(ledger.get("analyst")) is not dict or
                    type(ledger.get("reviewer")) is not dict or
                    pending_request is not None):
                inconsistent += 1
            else:
                complete += 1
        elif stage == "REVIEW_PENDING" and type(ledger.get("analyst")) is not dict:
            inconsistent += 1
        elif stage == "ANALYST_PENDING" and ledger.get("analyst") is not None:
            inconsistent += 1
    failures = []
    if not ai_ledgers:
        failures.append("NO_AI_SHADOW_EVIDENCE")
    if pending:
        failures.append("AMBIGUOUS_AI_REQUEST_REQUIRES_RECONCILIATION")
    if inconsistent:
        failures.append("AI_LEDGER_STATE_INCONSISTENT")
    if watchdog.get("watchdog_latched") is True:
        failures.append("WATCHDOG_STOP_LATCHED")
    if intake.get("blocking_reasons"):
        failures.append("SOURCE_INTAKE_UNCERTIFIED")
    # A completed model comparison cannot demonstrate profitability,
    # forecast quality or human approval.
    failures += ["MACRO_FORECAST_NOT_OUT_OF_SAMPLE_CERTIFIED",
                 "MODEL_RESPONSES_NOT_INDEPENDENTLY_VERIFIED",
                 "LIVE_AND_DEMO_ORDERS_NOT_AUTHORIZED"]
    return {
        "schema": SCHEMA, "status": "SHADOW_LONG_RUN_FAULT_CAMPAIGN_NO_GO",
        "ai_event_count": len(ai_ledgers), "ai_completed": complete,
        "ai_ambiguous_pending_count": pending,
        "ai_inconsistent_count": inconsistent,
        "cycle_sequence": receipt["sequence"],
        "blocking_reasons": sorted(set(failures)),
        "faults_tested_on_synthetic_inputs_only": True,
        "operational_long_duration_test_completed": False,
        "independent_heartbeat_verified": False,
        "broker_execution_verified": False,
        "automatic_restart_enabled": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _load(path: Path):
    if not path.is_file() or path.stat().st_size > 1000000:
        raise InputError("missing or oversized research input")
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(result) is not dict:
        raise InputError("invalid research input")
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline AI/event fault campaign, never trades")
    p.add_argument("--ai-ledger", type=Path, action="append", default=[])
    p.add_argument("--watchdog", type=Path, required=True)
    p.add_argument("--intake", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output exists")
        report = audit([_load(p) for p in a.ai_ledger], _load(a.watchdog),
                       _load(a.intake), _load(a.receipt))
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps({"status": report["status"],
                          "ai_completed": report["ai_completed"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, ValueError, TypeError, OSError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_SHADOW_FAULT_CAMPAIGN",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
