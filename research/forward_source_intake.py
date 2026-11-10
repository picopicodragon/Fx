"""FWD-029/030: independent offline intake contracts for MT4 and macro provenance.

No broker, MetaEditor, web traffic, DNS, API, credentials or trading.
Checks are *not* independent authentication of a source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from research.offline_backtest import InputError, PAIRS, timestamp

SCHEMA = "fx_forward_source_intake_v1"
DOMAINS = {"US_BLS": "www.bls.gov", "US_FED": "www.federalreserve.gov",
           "EU_ECB": "www.ecb.europa.eu", "JP_BOJ": "www.boj.or.jp"}


def _official_url(url: str, host: str) -> bool:
    if type(url) is not str or len(url) > 2048:
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and parts.hostname == host and
                parts.username is None and parts.password is None and
                parts.port is None and not parts.fragment and
                parts.path.startswith("/") and not any(
                    ord(c) < 32 for c in url))
    except ValueError:
        return False


def evaluate(mt4: dict, calendars: list[dict]) -> dict:
    if (type(mt4) is not dict or
            mt4.get("status") != "MT4_READONLY_EXPORT_RESEARCH_NO_GO" or
            mt4.get("runtime_go_no_go") != "NO_GO" or
            mt4.get("safety_hold_latched") is not True or
            mt4.get("real_orders_permitted") is not False or
            mt4.get("mt4_connected") is not False):
        raise InputError("untrusted MT4 export")
    timestamp(mt4.get("asof_utc"))
    files = mt4.get("file_evidence")
    if type(files) is not list or len(files) > 1000:
        raise InputError("invalid MT4 export evidence")
    seen = set()
    for item in files:
        if (type(item) is not dict or
                item.get("pair") not in PAIRS or
                item.get("source_status") != "USER_SUPPLIED_UNVERIFIED" or
                type(item.get("source_sha256")) is not str or
                len(item["source_sha256"]) != 64):
            raise InputError("invalid export record")
        if any(c not in "0123456789abcdef" for c in item["source_sha256"]):
            raise InputError("invalid export hash")
        timestamp(item.get("observed_at_utc"))
        identity = (item["pair"], item["observed_at_utc"])
        if identity in seen:
            raise InputError("duplicate pair timestamp")
        seen.add(identity)
    if (type(calendars) is not list or len(calendars) > 4):
        raise InputError("invalid source calendar list")
    present = set()
    observed_events = 0
    for snapshot in calendars:
        if (type(snapshot) is not dict or
                snapshot.get("schema") != "fx_forward_schedule_snapshot_v1" or
                snapshot.get("source_key") not in DOMAINS or
                snapshot.get("source_key") in present or
                snapshot.get("source_status") != "PUBLISHED_SCHEDULE_UNVERIFIED" or
                snapshot.get("runtime_go_no_go") != "NO_GO" or
                snapshot.get("real_orders_permitted") is not False or
                snapshot.get("source_authenticity_verified") is not False or
                type(snapshot.get("events")) is not list or
                len(snapshot["events"]) > 500):
            raise InputError("untrusted calendar")
        key = snapshot["source_key"]
        present.add(key)
        timestamp(snapshot.get("retrieved_at_utc"))
        for item in snapshot["events"]:
            if (type(item) is not dict or
                    item.get("source_status") != "PUBLISHED_SCHEDULE_UNVERIFIED" or
                    not _official_url(item.get("source_url"), DOMAINS[key])):
                raise InputError("calendar URL outside expected authority")
            timestamp(item.get("scheduled_at_utc"))
            observed_events += 1
    blockers = []
    if set(mt4.get("missing_pairs", [])) or len({i["pair"] for i in files}) < len(PAIRS):
        blockers.append("MT4_THREE_PAIR_EVIDENCE_MISSING")
    if len(present) != len(DOMAINS):
        blockers.append("CALENDAR_AUTHORITIES_INCOMPLETE")
    blockers += ["OFFICIAL_SITE_CONTENT_NOT_AUTHENTICATED",
                 "MT4_TERMINAL_NOT_OBSERVED",
                 "BROKER_AND_DATA_LICENSE_NOT_VERIFIED"]
    return {
        "schema": SCHEMA, "status": "SOURCE_INTAKE_RESEARCH_HOLD_NO_GO",
        "mt4_export_count": len(files),
        "calendar_source_count": len(present),
        "unverified_calendar_event_count": observed_events,
        "blocking_reasons": sorted(blockers),
        "mt4_account_authenticated": False,
        "url_origin_cryptographically_verified": False,
        "schedule_coverage_certified": False,
        "external_network_access_performed": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 1_000_000:
        raise InputError("invalid file")
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(result) is not dict:
        raise InputError("invalid object")
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline MT4 and economic-source boundary review")
    p.add_argument("--mt4", type=Path, required=True)
    p.add_argument("--calendar", action="append", type=Path, default=[])
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output collision")
        report = evaluate(_read(a.mt4), [_read(p) for p in a.calendar])
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": report["status"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, TypeError, ValueError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "UNSAFE_SOURCE_INTAKE",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
