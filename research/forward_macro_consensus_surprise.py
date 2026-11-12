"""FWD-141..149: point-in-time economic consensus/release surprise contract.

Both inputs are operator-supplied local excerpts. Checks chronological order,
content hashes and exact decimal arithmetic, NOT publisher authenticity,
consensus quality or currency direction. No network, provider or broker calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_macro_release_surprise_v1"
PAIR_SET = frozenset(("USD/JPY", "EUR/JPY", "EUR/USD"))
EVENT_TYPES = frozenset(("CPI", "EMPLOYMENT", "POLICY_RATE", "GDP", "PMI", "OTHER"))
UNITS = frozenset(("percent", "percentage_points", "index", "persons",
                  "thousands", "millions", "basis_points", "other"))
SOURCE_KEYS = frozenset(("value", "source_text", "source_sha256",
                         "source_url", "published_at_utc", "captured_at_utc"))
FIELDS = frozenset(("schema", "event_id", "pair", "event_type", "unit",
                    "scheduled_at_utc", "forecast", "release"))
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_DOCUMENT = 16000


def _number(value: object) -> Decimal:
    if (type(value) is not str or len(value) > 40
            or not value or value.strip() != value):
        raise InputError("invalid economic decimal")
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise InputError("invalid economic decimal") from exc
    if not d.is_finite() or abs(d) > Decimal("1000000000"):
        raise InputError("economic value out of range")
    return d


def _source(obj: object, *, before: bool, scheduled, cutoff) -> dict | None:
    if obj is None:
        return None
    if type(obj) is not dict or set(obj) != SOURCE_KEYS:
        raise InputError("invalid release/forecast source record")
    text = obj["source_text"]
    if (type(text) is not str or not 1 <= len(text) <= 2000
            or "\x00" in text):
        raise InputError("invalid evidence excerpt")
    sha = obj["source_sha256"]
    if (type(sha) is not str or not DIGEST.fullmatch(sha)
            or hashlib.sha256(text.encode("utf-8")).hexdigest() != sha):
        raise InputError("evidence excerpt hash mismatch")
    url = obj["source_url"]
    if (type(url) is not str or not 1 <= len(url) <= 1000
            or any(c.isspace() for c in url)):
        raise InputError("invalid source URL")
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.port
                or not parsed.netloc.isascii()):
            raise InputError("unsafe source URL")
    except ValueError as exc:
        raise InputError("bad source URL") from exc
    published = timestamp(obj["published_at_utc"])
    captured = timestamp(obj["captured_at_utc"])
    if not published <= captured <= cutoff:
        raise InputError("source not available at capture/asof")
    if before:
        if not captured < scheduled:
            raise InputError("forecast was not captured before release")
    elif published < scheduled or captured < scheduled:
        raise InputError("released value predates scheduled release")
    value = _number(obj["value"])
    return {
        "value": value, "published_at_utc": obj["published_at_utc"],
        "captured_at_utc": obj["captured_at_utc"],
        "source_sha256": sha, "source_host": parsed.hostname.lower(),
    }


def inspect(document: dict, *, asof_utc: str) -> dict:
    cutoff = timestamp(asof_utc)
    if (type(document) is not dict or set(document) != FIELDS
            or document["schema"] != SCHEMA
            or type(document["event_id"]) is not str
            or not IDENT.fullmatch(document["event_id"])
            or document["pair"] not in PAIR_SET
            or document["event_type"] not in EVENT_TYPES
            or document["unit"] not in UNITS):
        raise InputError("invalid economic-release document")
    scheduled = timestamp(document["scheduled_at_utc"])
    consensus = _source(document["forecast"], before=True,
                        scheduled=scheduled, cutoff=cutoff)
    outcome = _source(document["release"], before=False,
                      scheduled=scheduled, cutoff=cutoff)
    holds = [
        "PRE_RELEASE_CONSENSUS_UNAUTHENTICATED",
        "SOURCE_PUBLISHER_AND_CLOCK_UNATTESTED",
        "CURRENCY_DIRECTION_NOT_DERIVED_FROM_SURPRISE",
        "TRADING_PROHIBITED",
    ]
    if consensus is None:
        holds.append("NO_POINT_IN_TIME_CONSENSUS")
    if outcome is None:
        holds.append("OFFICIAL_RELEASE_VALUE_NOT_RECORDED")
    if scheduled - timedelta(minutes=15) <= cutoff < scheduled + timedelta(minutes=15):
        holds.append("MACRO_15_MINUTE_BLACKOUT_RESEARCH_ONLY")
    delta = (outcome["value"] - consensus["value"]
             if outcome is not None and consensus is not None else None)
    return {
        "schema": SCHEMA,
        "status": "POINT_IN_TIME_MACRO_SURPRISE_RESEARCH_NO_GO",
        "event_id": document["event_id"],
        "pair": document["pair"],
        "event_type": document["event_type"],
        "unit": document["unit"],
        "scheduled_at_utc_unattested": document["scheduled_at_utc"],
        "forecast_value_self_reported": (
            str(consensus["value"]) if consensus else None),
        "released_value_self_reported": (
            str(outcome["value"]) if outcome else None),
        "released_minus_forecast_same_unit": (
            str(delta) if delta is not None else None),
        "signed_surprise_is_not_a_trade_signal": True,
        "forecast_provenance_sha256": (
            consensus["source_sha256"] if consensus else None),
        "release_provenance_sha256": (
            outcome["source_sha256"] if outcome else None),
        "forecast_published_before_release": consensus is not None,
        "release_published_at_or_after_scheduled": outcome is not None,
        "evidence_integrity_checked_not_source_authenticated": True,
        "data_holds": sorted(holds),
        "ai_model_called": False,
        "actual_order_count": 0,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Research macro surprise, NEVER orders")
    p.add_argument("--event", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if (not a.event.is_file() or a.event.is_symlink()
                or not 0 < a.event.stat().st_size <= MAX_DOCUMENT
                or a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()
                or a.out.resolve() == a.event.resolve()):
            raise InputError("unsafe input/output")
        data = json.loads(a.event.read_text(encoding="utf-8-sig"))
        report = inspect(data, asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "surprise": report["released_minus_forecast_same_unit"],
            "data_holds": report["data_holds"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError,
            TypeError, KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MACRO_RELEASE_RESEARCH_INPUT_INVALID",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
