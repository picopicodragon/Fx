"""FWD-038/039: bounded offline verification of an entire cycle receipt chain.

An isolated last receipt cannot prove continuity. Require every consecutive
receipt from sequence 1, validate linkage and monotonic UTC timestamps.
No external clock, scheduler, MT4, API, broker access or trading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from research.forward_restart_receipts import verify_receipt, ZERO
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_receipt_chain_audit_v1"
MAX_RECEIPTS = 10000
MAX_FILE_BYTES = 20000


def verify_chain(receipts: list[dict], *, max_gap_seconds: int = 300) -> dict:
    if (type(receipts) is not list or not 1 <= len(receipts) <= MAX_RECEIPTS or
            type(max_gap_seconds) is not int or not 1 <= max_gap_seconds <= 86400):
        raise InputError("invalid chain scope")
    prev = None
    identities = set()
    gaps = []
    for index, receipt in enumerate(receipts, 1):
        verify_receipt(receipt)
        if receipt["sequence"] != index or receipt["cycle_id"] in identities:
            raise InputError("receipt restart, deletion or duplicate identity")
        identities.add(receipt["cycle_id"])
        if prev is not None:
            if receipt["previous_receipt_sha256"] != prev["receipt_sha256"]:
                raise InputError("receipt chain broken")
            difference = (timestamp(receipt["asof_utc"]) -
                          timestamp(prev["asof_utc"])).total_seconds()
            if difference <= 0:
                raise InputError("nonmonotonic receipt timestamps")
            if difference > max_gap_seconds:
                gaps.append({
                    "sequence": index, "gap_seconds": difference,
                    "previous_cycle_id": prev["cycle_id"],
                    "current_cycle_id": receipt["cycle_id"],
                })
        elif receipt["previous_receipt_sha256"] != ZERO:
            raise InputError("first receipt must begin at genesis")
        prev = receipt
    return {
        "schema": SCHEMA, "status": "RECEIPT_CHAIN_RESEARCH_HOLD_NO_GO",
        "receipt_count": len(receipts),
        "first_asof_utc": receipts[0]["asof_utc"],
        "last_asof_utc": prev["asof_utc"],
        "chain_tip_sha256": prev["receipt_sha256"],
        "oversized_gap_count": len(gaps),
        "gaps": gaps,
        "chain_restart_detected": False,
        "local_hash_consistency_verified": True,
        "missing_history_outside_supplied_bundle_excluded": False,
        "independent_clock_attested": False,
        "external_market_data_authenticated": False,
        "automatic_resume_permitted": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def from_manifest(manifest: dict, folder: Path) -> list[dict]:
    if (type(manifest) is not dict or
            set(manifest) != {"schema", "receipts"} or
            manifest["schema"] != SCHEMA or
            type(manifest["receipts"]) is not list or
            not 1 <= len(manifest["receipts"]) <= MAX_RECEIPTS):
        raise InputError("invalid chain manifest")
    out = []
    names = set()
    for item in manifest["receipts"]:
        if (type(item) is not dict or
                set(item) != {"filename", "sha256"} or
                type(item["filename"]) is not str or
                not __import__("re").fullmatch(
                    r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\\.json", item["filename"]) or
                type(item["sha256"]) is not str or
                not __import__("re").fullmatch(
                    r"[0-9a-f]{64}", item["sha256"]) or
                item["filename"] in names):
            raise InputError("invalid or repeated receipt manifest entry")
        names.add(item["filename"])
        path = folder / item["filename"]
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_BYTES:
            raise InputError("missing or oversized receipt")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise InputError("receipt file hash mismatched")
        data = json.loads(raw.decode("utf-8-sig"))
        if type(data) is not dict:
            raise InputError("receipt must be JSON object")
        out.append(data)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Audit entire offline receipt history, never GO")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--receipts-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--max-gap-seconds", type=int, default=300)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir() or
                not a.receipts_dir.is_dir() or
                not a.manifest.is_file() or a.manifest.stat().st_size > 2_000_000):
            raise InputError("invalid file paths")
        manifest = json.loads(a.manifest.read_text(encoding="utf-8-sig"))
        report = verify_chain(from_manifest(manifest, a.receipts_dir),
                              max_gap_seconds=a.max_gap_seconds)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": report["status"],
                          "receipt_count": report["receipt_count"],
                          "oversized_gap_count": report["oversized_gap_count"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "RECEIPT_CHAIN_UNVERIFIED_OR_BROKEN",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
