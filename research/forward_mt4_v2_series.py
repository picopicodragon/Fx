"""FWD-065/066: offline three-pair v2 CSV sequence diagnostics.

Checks local snapshots, UTC capture order, reuse, server-clock consistency
and gaps. Server-local time is NOT UTC. No MT4 polling or live operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path

from research.forward_mt4_v2_quote import (
    parse, PAIRS_V2, MAX_BYTES, server_time)
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_mt4_v2_series_audit_v1"
MAX_INPUTS = 1000


def inspect(files: list[Path], *, asof_utc: str,
            max_gap_seconds: int = 300) -> dict:
    now = timestamp(asof_utc)
    if (type(files) is not list or not 1 <= len(files) <= MAX_INPUTS or
            type(max_gap_seconds) is not int or
            not 1 <= max_gap_seconds <= 86400):
        raise InputError("invalid series bounds")
    by_pair = {pair: [] for pair in PAIRS_V2}
    paths, hashes = set(), set()
    for path in files:
        if (not isinstance(path, Path) or path.is_symlink() or
                not path.is_file() or
                not 0 < path.stat().st_size <= MAX_BYTES):
            raise InputError("missing or unsafe CSV")
        identity = path.resolve(strict=True)
        if identity in paths:
            raise InputError("duplicate file")
        paths.add(identity)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest in hashes:
            raise InputError("replayed identical CSV bytes")
        hashes.add(digest)
        # Validate historical snapshots at their own declared capture time;
        # the aggregate cutoff is checked separately for age/future evidence.
        import csv
        import io
        from research.forward_mt4_v2_quote import COLUMNS
        head = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        if tuple(head.fieldnames or ()) != COLUMNS:
            raise InputError("incorrect historical v2 header")
        historical_rows = list(head)
        if len(historical_rows) != 1:
            raise InputError("incorrect historical v2 row count")
        observed_raw = historical_rows[0].get("observed_at_utc")
        obs = timestamp(observed_raw)
        if obs > now:
            raise InputError("future snapshot")
        sample = parse(raw, asof_utc=observed_raw)
        by_pair[sample["pair"]].append((
            obs,
            server_time(sample["server_tick_time_unverified"]),
            server_time(sample["server_now_time_unverified"]),
            sample["server_relative_tick_age_seconds"],
            digest
        ))
    blockers = []
    details = {}
    for pair in PAIRS_V2:
        observations = sorted(by_pair[pair], key=lambda item: item[0])
        gaps, anomalies = [], []
        for previous, current in zip(observations, observations[1:]):
            wall_elapsed = (current[0] - previous[0]).total_seconds()
            server_elapsed = (current[2] - previous[2]).total_seconds()
            if wall_elapsed <= 0:
                anomalies.append("REPEATED_OR_REVERSED_CLIENT_TIMESTAMP")
            elif wall_elapsed > max_gap_seconds:
                gaps.append(wall_elapsed)
            if server_elapsed < 0:
                anomalies.append("SERVER_CLOCK_REGRESSED_OR_DST_AMBIGUOUS")
            # A stationary broker clock while PC time advances may indicate
            # disconnected/stale market feed even when tick_age=0.
            if wall_elapsed >= 60 and server_elapsed == 0:
                anomalies.append("SERVER_CLOCK_STALLED")
            # Server vs PC rates must not be interpreted as absolute sync:
            # gross differences are diagnostics, not a proof of a good clock.
            if abs(server_elapsed - wall_elapsed) > 120:
                anomalies.append("SERVER_AND_CLIENT_CLOCK_RATE_DIVERGED")
            if current[1] < previous[1]:
                anomalies.append("SERVER_TICK_TIME_REGRESSED")
        last_age = ((now - observations[-1][0]).total_seconds()
                    if observations else None)
        if not observations:
            blockers.append("MISSING_" + pair.replace("/", "_"))
        elif last_age is not None and last_age > 90:
            blockers.append("STALE_" + pair.replace("/", "_"))
        if gaps:
            blockers.append("OBSERVATION_GAP_" + pair.replace("/", "_"))
        if anomalies:
            blockers.append("CLOCK_OR_REPLAY_ANOMALY_" + pair.replace("/", "_"))
        details[pair] = {
            "observations": len(observations),
            "gap_seconds": gaps[:100],
            "anomalies": sorted(set(anomalies)),
            "last_observed_age_seconds": last_age,
            "server_time_utc_authenticated": False,
            "real_price_freshness_verified": False,
        }
    blockers += ["BROKER_TIME_NOT_INDEPENDENTLY_ATTESTED",
                 "DEMO_ACCOUNT_NOT_INDEPENDENTLY_VERIFIED",
                 "HISTORICAL_CSV_CANNOT_AUTHORIZE_NEW_ORDERS"]
    return {
        "schema": SCHEMA, "status": "MT4_V2_SERIES_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc, "capture_count": len(files),
        "by_pair": details,
        "blocking_reasons": sorted(set(blockers)),
        "server_timezone_is_known": False,
        "user_pc_mt4_session_accessed": False,
        "long_duration_live_collection_verified": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline 3-pair MT4 v2 CSV series diagnostics")
    p.add_argument("--csv", action="append", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output exists")
        result = inspect(a.csv, asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": result["status"],
            "blocking_reasons": result["blocking_reasons"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0
    except (InputError, ValueError, TypeError, OSError,
            UnicodeError, KeyError, ArithmeticError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "MT4_V2_SERIES_UNVERIFIED",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
