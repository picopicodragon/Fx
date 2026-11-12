"""FWD-183..190: read-only, fixed-category official RSS failure diagnostics.

No provider requests, broker APIs, API keys, raw response bodies or automatic
fallback. Network calls require --allow-network; --xml-file is offline. Audit
and preflight never write to the forward observation journal. The original
strict RSS importer remains unchanged and retains its fail-closed policy.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from research import forward_observation as observation
from research import forward_rss as rss
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_official_rss_diagnostic_v1"
SAFE_INPUT_ERRORS = {
    "feed not allowlisted": "FEED_NOT_ALLOWLISTED",
    "redirect prohibited; feed destination changed": "HTTP_REDIRECT_REJECTED",
    "non-success RSS response": "NON_200_HTTP_STATUS",
    "RSS exceeded response cap": "RSS_RESPONSE_SIZE_LIMIT",
    "unknown RSS feed": "FEED_NOT_ALLOWLISTED",
    "unsafe RSS XML": "UNSAFE_XML_OR_SIZE",
    "unexpected RSS root, fail closed": "UNEXPECTED_XML_ROOT",
    "missing RSS channel": "MISSING_RSS_CHANNEL",
    "excessive RSS items": "RSS_ITEM_COUNT_LIMIT",
    "unrecognized feed item URL": "ITEM_URL_INVALID",
    "unverified feed item URL": "ITEM_URL_NOT_ALLOWLISTED",
    "missing source publishing time": "PUBLISH_DATE_MISSING",
    "unreadable RSS publication timestamp": "PUBLISH_DATE_INVALID",
    "RSS timestamp has no timezone": "PUBLISH_DATE_UNZONED",
    "future-dated RSS release": "FUTURE_DATED_RSS_PUBLICATION",
    "invalid RSS entry size": "RSS_ITEM_SIZE_LIMIT",
    "duplicate item within RSS response": "DUPLICATE_RSS_LINK",
    "new RSS entries exceed explicit item cap": "NEW_RECENT_ITEMS_OVER_CAP",
}


def _code(exc: BaseException) -> str:
    # Never surface raw errors, HTTP bodies, URL details or credentials.
    if isinstance(exc, urllib.error.HTTPError):
        status = exc.code
        if status in (400, 401, 403, 404, 408, 409, 410, 429):
            return "HTTP_" + str(status)
        if 500 <= status <= 599:
            return "HTTP_5XX"
        return "HTTP_OTHER"
    if isinstance(exc, InputError):
        return SAFE_INPUT_ERRORS.get(str(exc), "UNCLASSIFIED_VALIDATION_FAILURE")
    if isinstance(exc, urllib.error.URLError):
        return "NETWORK_TLS_DNS_OR_TIMEOUT"
    if isinstance(exc, ET.ParseError):
        return "INVALID_RSS_XML"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "NETWORK_TLS_DNS_OR_TIMEOUT"
    return "LOCAL_IO_OR_UNKNOWN_FAILURE"


def _base(feed: str, *, network: bool, stage: str) -> dict:
    return {
        "schema": SCHEMA,
        "feed": feed,
        "status": "RSS_DIAGNOSTIC_FAIL_CLOSED_NO_GO",
        "stage": stage,
        "reason_code": None,
        "network_opted_in": network,
        "journal_modified": False,
        "api_calls_this_run": 0,
        "source_publisher_authenticated": False,
        "pre_release_consensus_available": False,
        "automatic_retry_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
        "demo_orders_permitted": False,
    }


def inspect(store: Path, feed: str, *, asof_utc: str,
            raw: bytes, max_new: int = 3) -> dict:
    """Validate a supplied feed without ever ingesting it.

    If the feed passes, return bounded counts distinguishing duplicate,
    stale, recent and over-cap items. Fail validation instead of permitting
    truncated or guessed economic events.
    """
    now = timestamp(asof_utc)
    if (not isinstance(store, Path) or store.is_symlink()
            or not store.is_dir() or feed not in rss.FEEDS
            or type(max_new) is not int or not 1 <= max_new <= 5):
        raise InputError("invalid feed/store/cap")
    # Existing journal must be intact, even if no items are recent.
    observation.audit(store)
    entries = rss.parse_feed(raw, feed, received_utc=asof_utc)
    prev = rss._prior_links(store, feed)
    new = [e for e in entries
           if e["payload"]["source_url"] not in prev]
    old = [e for e in new if (
        now - timestamp(e["payload"]["published_at_utc"])
    ).total_seconds() > 86400]
    recent = len(new) - len(old)
    result = _base(feed, network=False, stage="PREFLIGHT")
    result.update({
        "status": ("RSS_PREFLIGHT_HOLD_NO_GO" if recent > max_new
                   else "RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO"),
        "reason_code": ("NEW_RECENT_ITEMS_OVER_CAP" if recent > max_new
                        else None),
        "feed_items_parsed": len(entries),
        "already_seen_in_this_feed": len(entries) - len(new),
        "unseen_but_older_than_24h": len(old),
        "unseen_published_within_24h": recent,
        "maximum_new_items_per_import": max_new,
        "items_that_would_be_ingested_if_normal_import_ran":
            recent if recent <= max_new else 0,
        "no_automatic_import_performed": True,
    })
    return result


def diagnose(store: Path, feed: str, *, asof_utc: str,
             raw: bytes | None = None, allow_network: bool = False,
             max_new: int = 3) -> dict:
    """Categorized errors only; never alter the journal or leak raw XML."""
    result = _base(feed, network=allow_network, stage="INPUT")
    try:
        timestamp(asof_utc)
        if (type(feed) is not str or feed not in rss.FEEDS
                or type(max_new) is not int or not 1 <= max_new <= 5
                or not isinstance(store, Path) or store.is_symlink()
                or not store.is_dir()
                or (raw is None) == allow_network):
            raise InputError("invalid diagnostic inputs")
        result["stage"] = "JOURNAL_AUDIT"
        observation.audit(store)
        if raw is None:
            result["stage"] = "FETCH"
            raw = rss.get_feed(feed)
        result["stage"] = "PARSE_AND_PREFLIGHT"
        report = inspect(store, feed, asof_utc=asof_utc,
                         raw=raw, max_new=max_new)
        report["network_opted_in"] = allow_network
        return report
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ET.ParseError, ArithmeticError, OverflowError,
            urllib.error.URLError) as exc:
        result["reason_code"] = _code(exc)
        return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only RSS failure diagnosis; no feed import or orders")
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--feed", choices=sorted(rss.FEEDS), required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--allow-network", action="store_true")
    group.add_argument("--xml-file", type=Path)
    parser.add_argument("--max-new", type=int, default=3)
    args = parser.parse_args(argv)
    asof = datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")
    if args.xml_file is not None:
        try:
            if (args.xml_file.is_symlink() or not args.xml_file.is_file()
                    or not 0 < args.xml_file.stat().st_size <= rss.MAX_RESPONSE):
                raise InputError("invalid local XML file")
            raw = args.xml_file.read_bytes()
        except (OSError, ValueError, TypeError, InputError):
            result = _base(args.feed, network=False, stage="LOCAL_XML")
            result["reason_code"] = "UNREADABLE_OR_OVERSIZED_LOCAL_XML"
            print(json.dumps(result))
            return 2
    else:
        raw = None
    report = diagnose(
        args.store, args.feed, asof_utc=asof, raw=raw,
        allow_network=args.allow_network, max_new=args.max_new)
    print(json.dumps(report))
    return 0 if report["status"] == "RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
