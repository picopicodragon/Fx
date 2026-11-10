"""FWD-017: bind saved multi-cycle reports to a verified local journal prefix.

Integrity hashes do not authenticate underlying quotes or prove execution.
The chain is audited offline. Never connects to MT4, API or broker.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.forward_multicycle import (
    SCHEMA as MULTICYCLE_SCHEMA, from_manifest, combine)
from research.forward_quality import records
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_cycle_chain_audit_v1"


def verify(store: Path, cycles: list[dict]) -> dict:
    journal = records(store)
    if not cycles:
        raise InputError("empty cycles")
    anchored = []
    for cycle in cycles:
        qa, paper = cycle["quality"], cycle["paper"]
        count = qa["record_count"]
        if type(count) is not int or not 0 <= count <= len(journal):
            raise InputError("invalid journal prefix")
        asof = timestamp(qa["asof_utc"])
        if count and timestamp(journal[count - 1]["captured_at_utc"]) > asof:
            raise InputError("journal evidence captured after cycle")
        if count < len(journal) and timestamp(journal[count]["captured_at_utc"]) <= asof:
            raise InputError("unaccounted observation before cycle")
        prefix_hashes = {item["record_sha256"] for item in journal[:count]}
        pos = paper["hypothetical_position"]
        if pos is not None:
            if type(pos) is not dict:
                raise InputError("invalid paper position")
            for key in ("hypothesis_record_sha256", "review_record_sha256",
                        "entry_record_sha256", "exit_record_sha256"):
                if pos.get(key) not in prefix_hashes:
                    raise InputError("paper position evidence not in journal")
        anchored.append({
            "cycle_id": cycle["cycle_id"],
            "record_count": count,
            "last_observation_record_sha256": (
                journal[count - 1]["record_sha256"] if count else "0" * 64),
            "asof_utc": qa["asof_utc"],
        })
    report = combine(cycles)
    return {
        "schema": SCHEMA, "status": "FORWARD_CYCLE_CHAIN_VERIFIED_NO_GO",
        "journal_records_at_verification": len(journal),
        "cycle_count": len(anchored), "anchored_cycles": anchored,
        "research_replay_summary": report,
        "local_hash_chain_integrity_verified": True,
        "source_authenticity_verified": False,
        "broker_prices_authenticated": False,
        "broker_order_execution_enabled": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline cycle-to-journal proof of local integrity")
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if (args.out.exists() or not args.out.parent.is_dir()
                or not args.reports_dir.is_dir()
                or not args.manifest.is_file()
                or args.manifest.stat().st_size > 100000):
            raise InputError("unsafe file paths")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        cycles = from_manifest(manifest, args.reports_dir)
        report = verify(args.store, cycles)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": report["status"],
                          "cycle_count": report["cycle_count"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (OSError, InputError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "UNVERIFIED_FORWARD_JOURNAL_PREFIX",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
