"""FWD-028: restart-safe offline shadow-cycle receipt chain.

Operator runs each cycle once with a unique identifier. No service,
scheduler, broker, API, MT4 calls, trading, or automatic resumption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_cycle_receipt_v1"
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
ZERO = "0" * 64


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def make_receipt(cycle_id: str, asof_utc: str, report_sha256: str,
                 prior: dict | None = None) -> dict:
    timestamp(asof_utc)
    if (type(cycle_id) is not str or not ID.fullmatch(cycle_id) or
            type(report_sha256) is not str or
            not re.fullmatch(r"[0-9a-f]{64}", report_sha256)):
        raise InputError("invalid cycle evidence identity")
    previous_hash = ZERO
    sequence = 1
    if prior is not None:
        verify_receipt(prior)
        if timestamp(asof_utc) <= timestamp(prior["asof_utc"]):
            raise InputError("time regression or duplicate")
        if cycle_id == prior["cycle_id"]:
            raise InputError("duplicate cycle")
        previous_hash = prior["receipt_sha256"]
        sequence = prior["sequence"] + 1
        if sequence > 100000:
            raise InputError("receipt chain limit exceeded")
    body = {
        "schema": SCHEMA, "status": "FORWARD_RESTART_RECEIPT_NO_GO",
        "cycle_id": cycle_id, "asof_utc": asof_utc,
        "report_sha256": report_sha256, "previous_receipt_sha256": previous_hash,
        "sequence": sequence,
        "windows_monotonic_clock_attested": False,
        "restart_continuity_independently_attested": False,
        "automated_restart_permitted": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True, "real_orders_permitted": False,
    }
    return {**body, "receipt_sha256": hashlib.sha256(canonical(body)).hexdigest()}


def verify_receipt(receipt: dict) -> None:
    if (type(receipt) is not dict or
            receipt.get("schema") != SCHEMA or
            receipt.get("status") != "FORWARD_RESTART_RECEIPT_NO_GO" or
            receipt.get("runtime_go_no_go") != "NO_GO" or
            receipt.get("real_orders_permitted") is not False or
            receipt.get("safety_hold_latched") is not True or
            receipt.get("automated_restart_permitted") is not False or
            receipt.get("demo_order_execution_enabled") is not False or
            type(receipt.get("sequence")) is not int or
            not 1 <= receipt["sequence"] <= 100000 or
            type(receipt.get("cycle_id")) is not str or
            not ID.fullmatch(receipt["cycle_id"])):
        raise InputError("invalid receipt")
    timestamp(receipt.get("asof_utc"))
    hash_value = receipt.get("receipt_sha256")
    if type(hash_value) is not str or len(hash_value) != 64:
        raise InputError("invalid receipt hash")
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    if hashlib.sha256(canonical(body)).hexdigest() != hash_value:
        raise InputError("modified receipt")
    for field in ("report_sha256", "previous_receipt_sha256"):
        if (type(receipt.get(field)) is not str or
                not re.fullmatch(r"[0-9a-f]{64}", receipt[field])):
            raise InputError("invalid receipt parent")
    if receipt["sequence"] == 1 and receipt["previous_receipt_sha256"] != ZERO:
        raise InputError("first receipt has parent")
    if receipt["sequence"] > 1 and receipt["previous_receipt_sha256"] == ZERO:
        raise InputError("unanchored continuation")


def _load(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 20000:
        raise InputError("missing/oversized previous receipt")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(obj) is not dict:
        raise InputError("receipt not object")
    return obj


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline immutable cycle receipt, never resumes trading")
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--previous", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir()
                or not a.report.is_file() or
                a.report.stat().st_size > 1000000):
            raise InputError("invalid input/output")
        raw = a.report.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
        if (type(payload) is not dict or
                payload.get("runtime_go_no_go") != "NO_GO" or
                payload.get("safety_hold_latched") is not True or
                payload.get("real_orders_permitted") is not False):
            raise InputError("unsafe cycle report")
        item = make_receipt(
            a.cycle_id, a.asof_utc,
            hashlib.sha256(raw).hexdigest(),
            _load(a.previous) if a.previous else None)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)
        print(json.dumps({"status": item["status"],
                          "sequence": item["sequence"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (OSError, InputError, ValueError, TypeError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_RESTART_CYCLE_RECEIPT",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
