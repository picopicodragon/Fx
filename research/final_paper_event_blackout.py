"""FINAL-PAPER-19: no-network, paper-only known macro-event blackout guard.

An operator-provided official-source event list can ADD ±15min holds; it
NEVER claims complete future event coverage or independent time attestation.
No missing-file fallback to invented future events. A supplied invalid file
stops the paper supervisor rather than silently ignoring a safety signal.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_known_macro_blackout_v1"
CURRENCIES = {"USD", "EUR", "JPY"}
OFFICIAL_HOSTS = frozenset({
    "www.bls.gov", "www.federalreserve.gov", "www.ecb.europa.eu",
    "www.boj.or.jp", "www.bea.gov",
})
WINDOW_SECONDS = 900
MAX_AGE_SECONDS = 86400


def _epoch_utc(value: str) -> int:
    if type(value) is not str:
        raise InputError("invalid scheduled event time")
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise InputError("invalid scheduled event time") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds()!=0:
        raise InputError("scheduled time must be UTC")
    return int(parsed.timestamp())


def check(path: Path|None, quote_epoch: int, *,
          now: datetime|None=None) -> dict:
    if type(quote_epoch) is not int or quote_epoch<=0:
        raise InputError("invalid quote epoch")
    if path is None:
        return {
            "active_known_blackout": False,
            "official_source_event_count": 0,
            "calendar_supplied": False,
            "independent_calendar_coverage_attested": False,
            "pc_clock_independently_attested": False,
        }
    if (not path.is_file() or path.is_symlink()
            or any(x.is_symlink() for x in path.parents)
            or not 0<path.stat().st_size<=32000):
        raise InputError("unsafe event calendar")
    try:
        obj=json.loads(path.read_text("utf-8-sig"))
    except (ValueError,UnicodeError,OSError) as exc:
        raise InputError("invalid event calendar JSON") from exc
    if (type(obj) is not dict or set(obj)!={
            "schema","captured_at_utc_pc","events","scope"}
            or obj["schema"]!=SCHEMA
            or obj["scope"]!="OPERATOR_SAVED_RESEARCH_ONLY"
            or type(obj["events"]) is not list
            or len(obj["events"])>100):
        raise InputError("invalid event calendar structure")
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("invalid current clock")
    captured=_epoch_utc(obj["captured_at_utc_pc"])
    current_epoch=int(current.timestamp())
    if not -60<=current_epoch-captured<=MAX_AGE_SECONDS:
        raise InputError("outdated event calendar")
    active=False
    ids=set()
    for item in obj["events"]:
        if (type(item) is not dict or set(item)!={
                "id","currency","scheduled_at_utc","source_url",
                "importance"}):
            raise InputError("invalid calendar event")
        ident=item["id"]
        if (type(ident) is not str or not 1<=len(ident)<=120
                or ident in ids or item["currency"] not in CURRENCIES
                or item["importance"] not in ("HIGH","CRITICAL")
                or type(item["source_url"]) is not str):
            raise InputError("invalid calendar event metadata")
        ids.add(ident)
        url=urlparse(item["source_url"])
        if (url.scheme!="https" or url.hostname not in OFFICIAL_HOSTS
                or url.username or url.password or url.port is not None):
            raise InputError("event source not allowlisted")
        event_epoch=_epoch_utc(item["scheduled_at_utc"])
        if event_epoch<captured-86400 or event_epoch>captured+120*86400:
            raise InputError("event time out of range")
        if abs(quote_epoch-event_epoch)<=WINDOW_SECONDS:
            active=True
    return {
        "active_known_blackout": active,
        "official_source_event_count": len(obj["events"]),
        "calendar_supplied": True,
        "independent_calendar_coverage_attested": False,
        "pc_clock_independently_attested": False,
    }
