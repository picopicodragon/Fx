"""FWD-023: offline batch validation of manually exported DEMO MT4 quote files.

No account access, terminal commands or orders. The DEMO column is a
self-report and never independent broker authentication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.forward_mt4_quote_import import parse_quote_csv, MAX_BYTES
from research.offline_backtest import InputError, PAIRS, timestamp

SCHEMA = "fx_forward_mt4_readonly_batch_v1"
MAX_FILES = 1000


def inspect_exports(files: list[Path], *, asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES:
        raise InputError("bounded nonempty export list required")
    seen_paths = set()
    last_time = {}
    records = []
    for path in files:
        if not isinstance(path, Path) or path in seen_paths or (
                not path.is_file() or path.stat().st_size > MAX_BYTES):
            raise InputError("missing, repeated or oversized export")
        seen_paths.add(path)
        raw = path.read_bytes()
        sample = parse_quote_csv(raw.decode("utf-8-sig"), now=now)
        pair = sample["payload"]["pair"]
        at = timestamp(sample["observed_at_utc"])
        if pair in last_time and at <= last_time[pair]:
            raise InputError("nonmonotonic per-pair quotes")
        last_time[pair] = at
        records.append({
            "pair": pair, "observed_at_utc": sample["observed_at_utc"],
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_status": "USER_SUPPLIED_UNVERIFIED",
        })
    missing = sorted(set(PAIRS) - set(last_time))
    return {
        "schema": SCHEMA,
        "status": "MT4_READONLY_EXPORT_RESEARCH_NO_GO",
        "asof_utc": asof_utc,
        "export_count": len(records),
        "file_evidence": records,
        "missing_pairs": missing,
        "terminal_account_type_independently_verified": False,
        "tick_server_time_independently_verified": False,
        "quote_to_jpy_conversion_verified": False,
        "metaeditor_script_compilation_verified": False,
        "mt4_connected": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline MT4 CSV export series audit only")
    p.add_argument("--csv", type=Path, action="append", required=True)
    p.add_argument("--asof-utc")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output collision")
        now = a.asof_utc or datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        result = inspect_exports(a.csv, asof_utc=now)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": result["status"],
                          "missing_pairs": result["missing_pairs"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "MT4_CSV_EVIDENCE_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
