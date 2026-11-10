"""FWD-056: four-pair offline completeness of v2 manually supplied quote reports.

Rejects duplicate pair identities, reused source evidence and mismatched
timestamps. Remains NO_GO even when all four reports are present/fresh.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.forward_mt4_v2_quote import PAIRS_V2, SCHEMA as QUOTE_SCHEMA
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_forward_mt4_v2_four_pair_review_v1"


def review(reports: list[dict], *, asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    if type(reports) is not list or not 1 <= len(reports) <= 4:
        raise InputError("need one to four reports")
    pairs = {}
    hashes = set()
    for report in reports:
        if (type(report) is not dict or
                report.get("schema") != QUOTE_SCHEMA or
                report.get("status") != "MT4_V2_MANUAL_QUOTE_RESEARCH_NO_GO" or
                report.get("runtime_go_no_go") != "NO_GO" or
                report.get("safety_hold_latched") is not True or
                report.get("real_orders_permitted") is not False or
                report.get("demo_order_execution_enabled") is not False or
                report.get("server_timestamp_authenticated") is not False or
                report.get("broker_quote_authenticity_verified") is not False or
                report.get("pair") not in PAIRS_V2 or
                type(report.get("csv_sha256")) is not str or
                not __import__("re").fullmatch(r"[a-f0-9]{64}", report["csv_sha256"])):
            raise InputError("untrusted v2 report")
        pair = report["pair"]
        if pair in pairs or report["csv_sha256"] in hashes:
            raise InputError("duplicate pair or CSV evidence")
        hashes.add(report["csv_sha256"])
        obs = timestamp(report["observed_at_utc"])
        cutoff = timestamp(report["asof_utc"])
        if cutoff > now or obs > cutoff:
            raise InputError("future report evidence")
        age = (now - obs).total_seconds()
        if age < 0:
            raise InputError("future tick")
        pairs[pair] = {
            "quote_age_seconds": age,
            "source_sha256": report["csv_sha256"],
            "research_fresh": age <= 90,
            "source_authenticated": False,
        }
    blockers = ["BROKER_QUOTE_AUTHENTICATION_MISSING",
                "SERVER_CLOCK_TIMEZONE_NOT_ATTESTED",
                "CONVERSION_PRICE_SOURCE_NOT_ATTESTED",
                "FORMAL_RISK_ENGINE_NOT_VERIFIED",
                "DEMO_EXECUTION_NOT_AUTHORIZED"]
    for pair in PAIRS_V2:
        if pair not in pairs:
            blockers.append("MISSING_" + pair.replace("/", "_"))
        elif not pairs[pair]["research_fresh"]:
            blockers.append("STALE_" + pair.replace("/", "_"))
    return {
        "schema": SCHEMA,
        "status": "MT4_V2_FOUR_PAIR_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "pairs_present": sorted(pairs),
        "by_pair": pairs,
        "legacy_three_pair_pipeline_migrated": False,
        "blocking_reasons": sorted(blockers),
        "mt4_compilation_verified": False,
        "mt4_terminal_execution_verified": False,
        "external_price_source_authenticated": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _read(path: Path) -> dict:
    if not path.is_file() or not 0 < path.stat().st_size <= 10000:
        raise InputError("invalid report size")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(obj) is not dict:
        raise InputError("invalid report JSON")
    return obj


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline four-pair research readiness, not GO")
    p.add_argument("--report", type=Path, action="append", required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output already exists")
        result = review([_read(x) for x in a.report], asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({"status": result["status"],
                          "blocking_reasons": result["blocking_reasons"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError, UnicodeError, KeyError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "FOUR_PAIR_RESEARCH_DATA_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
