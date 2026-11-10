"""FWD-105..111: offline DEMO capture microstructure/quality research.

Never equate copied CSV with authenticated broker prices; no signals,
positions, order APIs, or auto-resume. Every session audited separately.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from research.forward_mt4_multisession_reliability import inspect as audit
from research.forward_mt4_v2_quote import parse
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_quote_quality_research_v1"
PIP = {"USD/JPY": Decimal("0.01"), "EUR/JPY": Decimal("0.01"),
       "EUR/USD": Decimal("0.0001")}
MAX_SPREAD_PIPS_RESEARCH = Decimal("5")


def inspect(sessions: list[tuple[str, Path]], *, asof_utc: str) -> dict:
    base = audit(sessions, asof_utc=asof_utc)
    rows = {key: [] for key in PIP}
    anomalies = set(base["issues_and_safety_holds"])
    for label, folder in sessions:
        for file in sorted(folder.iterdir(), key=lambda f: f.name):
            if file.is_symlink() or not file.is_file():
                raise InputError("non-CSV entry")
            # The underlying audit has already checked filename/schema, but
            # parse again against each historic observation time for figures.
            import csv
            import io
            raw = file.read_bytes()
            try:
                table = list(csv.DictReader(
                    io.StringIO(raw.decode("utf-8-sig")), strict=True))
            except (UnicodeError, csv.Error) as exc:
                raise InputError("invalid quality CSV") from exc
            if len(table) != 1:
                raise InputError("incorrect record count")
            when = table[0]["observed_at_utc"]
            quote = parse(raw, asof_utc=when)
            pair = quote["pair"]
            bid = Decimal(quote["bid"])
            ask = Decimal(quote["ask"])
            spread = (ask - bid) / PIP[pair]
            if spread <= 0:
                raise InputError("invalid spread")
            if spread > MAX_SPREAD_PIPS_RESEARCH:
                anomalies.add("SPREAD_ABOVE_RESEARCH_REVIEW_THRESHOLD")
            rows[pair].append({
                "session": label, "utc": when, "bid": str(bid),
                "ask": str(ask), "spread_pips": spread,
                "broker_relative_tick_age_s":
                    quote["server_relative_tick_age_seconds"],
            })
    stats = {}
    for pair, records in rows.items():
        spreads = sorted(item["spread_pips"] for item in records)
        ages = [item["broker_relative_tick_age_s"] for item in records]
        # p95 is nearest-rank (conservative small sample statistic).
        n = len(spreads)
        p95 = spreads[((95*n+99)//100)-1] if n else None
        if not n:
            anomalies.add("NO_QUOTES_" + pair.replace("/", "_"))
        stats[pair] = {
            "quotes": n,
            "spread_min_pips": str(spreads[0]) if n else None,
            "spread_median_pips": str(spreads[(n-1)//2]) if n else None,
            "spread_p95_pips": str(p95) if p95 is not None else None,
            "spread_max_pips": str(spreads[-1]) if n else None,
            "server_relative_tick_age_max_seconds": max(ages) if ages else None,
            "spread_threshold_pips_research_only":
                str(MAX_SPREAD_PIPS_RESEARCH),
        }
    return {
        "schema": SCHEMA,
        "status": "SHADOW_DATA_QUALITY_RESEARCH_NO_GO",
        "asof_utc": asof_utc,
        "session_count": base["session_count"],
        "cycle_count": base["observed_cycle_count"],
        "files": base["csv_file_count"],
        "incomplete_cycles": base["incomplete_cycle_count"],
        "pair_statistics": stats,
        "data_quality_alerts_and_safety_holds": sorted(anomalies),
        "quote_freshness_independently_attested": False,
        "broker_identity_independently_attested": False,
        "paper_strategy_signals_present": False,
        "hypotheses_verified": False,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Copied CSV quality only, NO_GO")
    p.add_argument("--session", action="append", required=True,
                   help="LABEL=CSV_DIRECTORY")
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        from research.forward_mt4_multisession_reliability import _parse_labeled_entries
        sessions = list(_parse_labeled_entries(
            args.session, "--session").items())
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or
                any(folder.resolve() in args.out.resolve().parents
                    for _, folder in sessions)):
            raise InputError("unsafe report path")
        result = inspect(sessions, asof_utc=args.asof_utc)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"], "files": result["files"],
            "cycles": result["cycle_count"],
            "incomplete_cycles": result["incomplete_cycles"],
            "data_quality_alerts_and_safety_holds":
                result["data_quality_alerts_and_safety_holds"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "QUOTE_QUALITY_EVIDENCE_UNVERIFIED",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
