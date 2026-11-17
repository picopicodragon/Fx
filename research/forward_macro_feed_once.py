"""FWD-1461: bounded official RSS capture and recent US macro journal intake.

Each listed official feed is fetched exactly once only with --allow-network.
All valid raw XML is archived in immutable, per-feed snapshot bundles before
the optional recent US MACRO_EVENT journal append. ECB/BOJ items are stored
as retrospective official-news evidence, NOT promoted to macro releases.
No pre-release consensus, realized economic value, AI verdict, order or
authenticated publisher timestamp may be inferred from RSS. No broker calls,
automatic retries, background monitoring or paid API usage.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from research import forward_multi_official_news_snapshot as news
from research import forward_rss as rss
from research import forward_observation as journal
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_explicit_official_feed_intake_v1"
CANDIDATE_FEEDS = tuple(sorted(news.FEEDS))
JOURNAL_FEEDS = frozenset(rss.FEEDS)
MAX_FEEDS = len(CANDIDATE_FEEDS)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _source_input(value: str) -> tuple[str, Path]:
    if type(value) is not str or len(value) > 1800 or "=" not in value:
        raise InputError("expected allowlisted feed=XML input path")
    name, path = value.split("=", 1)
    if name not in CANDIDATE_FEEDS or not path:
        raise InputError("unknown named feed file")
    return name, Path(path)


def _validate(store: Path, out_dir: Path, feeds: list[str], *,
              allow_network: bool, xml_files: dict[str, Path]) -> None:
    if (not isinstance(store, Path) or store.is_symlink()
            or any(p.is_symlink() for p in store.parents)
            or not store.is_dir()):
        raise InputError("real observation journal missing")
    journal.audit(store)
    if (not isinstance(out_dir, Path) or out_dir.exists()
            or out_dir.is_symlink()
            or any(p.is_symlink() for p in out_dir.parents)
            or not out_dir.parent.is_dir()):
        raise InputError("capture output must be a new directory")
    where = out_dir.resolve(strict=False)
    origin = store.resolve(strict=True)
    if where == origin or origin in where.parents or where in origin.parents:
        raise InputError("capture archive overlaps append-only journal")
    if (type(feeds) is not list or not 1 <= len(feeds) <= MAX_FEEDS
            or any(name not in CANDIDATE_FEEDS for name in feeds)
            or len(set(feeds)) != len(feeds)):
        raise InputError("invalid/duplicate official feed selection")
    if allow_network == bool(xml_files):
        raise InputError("explicit network OR named local XML files required")
    if xml_files and set(xml_files) != set(feeds):
        raise InputError("named local XML files must match requested feeds")


def _read(path: Path) -> bytes:
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not path.is_file()
            or not 0 < path.stat().st_size <= news.MAX_XML):
        raise InputError("unsafe original RSS XML file")
    content = path.read_bytes()
    if not 0 < len(content) <= news.MAX_XML:
        raise InputError("original RSS response too large")
    return content


def _failure_code(exc: Exception) -> str:
    """Stable, non-sensitive category; never expose server bodies or exception text."""
    if isinstance(exc, urllib.error.HTTPError):
        return "HTTP_STATUS_" + str(exc.code)
    if isinstance(exc, urllib.error.URLError):
        return "NETWORK_REQUEST_FAILURE"
    if isinstance(exc, ET.ParseError):
        return "XML_PARSE_FAILURE"
    if isinstance(exc, InputError):
        return "INPUT_OR_FORMAT_REJECTED"
    if isinstance(exc, (OSError, UnicodeError)):
        return "LOCAL_IO_OR_ENCODING_FAILURE"
    return "VALIDATION_FAILURE"


def run(store: Path, out_dir: Path, feeds: list[str], *,
        allow_network: bool = False, xml_files: dict[str, Path] | None = None,
        max_new: int = 3, downloader=None,
        clock=None) -> dict:
    """One explicit command, per-feed failure isolation, never automatic retry."""
    xml_files = {} if xml_files is None else xml_files
    if type(max_new) is not int or not 1 <= max_new <= 5:
        raise InputError("new MACRO_EVENT per-feed cap must be 1..5")
    _validate(store, out_dir, feeds,
              allow_network=allow_network, xml_files=xml_files)
    downloader = news._download if downloader is None else downloader
    clock = _utc_now if clock is None else clock
    out_dir.mkdir(exist_ok=False)
    records = []
    journal_new = 0
    validated_bundle_count = 0
    network_attempt_count = 0
    for name in feeds:
        result = {
            "feed": name,
            "official_url": news.FEEDS[name],
            "status": "SOURCE_UNAVAILABLE_OR_INVALID_HOLD_NO_GO",
            "archive_complete": False,
            "journal_records_added": 0,
            "fetched_news_items": 0,
            "pre_release_consensus_count": 0,
            "realized_economic_values_count": 0,
            "source_authenticity_independently_attested": False,
        }
        stage = "DOWNLOAD" if allow_network else "LOCAL_XML_READ"
        try:
            if allow_network:
                network_attempt_count += 1
                raw = downloader(name)
            else:
                raw = _read(xml_files[name])
            if type(raw) is not bytes or not 0 < len(raw) <= news.MAX_XML:
                raise InputError("unsafe official feed response")
            received = clock()
            if (not isinstance(received, datetime) or received.tzinfo is None
                    or received.utcoffset() is None):
                raise InputError("capture clock missing timezone")
            received = received.astimezone(timezone.utc).replace(microsecond=0)
            utc = _iso(received)
            mode = ("EXPLICIT_NETWORK_SINGLE_PASS" if allow_network
                    else "LOCAL_COPY")
            stage = "FORMAT_VALIDATION"
            manifest = news.prepare(
                {name: raw}, captured_at_utc=utc, collection_mode=mode)
            stage = "ARCHIVE_WRITE"
            archive = out_dir / name
            news.save(archive, {name: raw}, manifest)
            result["archive_complete"] = True
            result["source_sha256_local_integrity_only"] = (
                manifest["feeds"][name]["source_sha256"])
            result["captured_at_utc_local_clock_unattested"] = utc
            result["fetched_news_items"] = manifest["feeds"][name][
                "news_item_count"]
            validated_bundle_count += 1
            if name in JOURNAL_FEEDS:
                stage = "JOURNAL_APPEND"
                imported = rss.import_xml(
                    store, name, raw, now=received, max_new=max_new)
                result["journal_records_added"] = imported["new_recent_items"]
                result["recent_journal_record_sha256s"] = imported[
                    "record_sha256s"]
                journal_new += imported["new_recent_items"]
                result["status"] = (
                    "RECENT_US_RELEASES_JOURNALED_RESEARCH_HOLD_NO_GO"
                    if imported["new_recent_items"]
                    else "SOURCE_ARCHIVED_NO_RECENT_US_RELEASE_HOLD_NO_GO")
            else:
                result["status"] = (
                    "REGIONAL_NEWS_ARCHIVED_NOT_A_MACRO_RELEASE_HOLD_NO_GO")
                result["regional_feed_journal_intake_disabled"] = True
        except (InputError, OSError, ValueError, TypeError, UnicodeError,
                ArithmeticError, KeyError, ET.ParseError,
                urllib.error.URLError) as exc:
            result["failure_stage"] = stage
            result["failure_reason_code"] = _failure_code(exc)
            # Previously captured official source archives and journal writes
            # remain intact. Do not auto-retry a partially completed append.
            result["status"] = (
                "ARCHIVED_BUT_JOURNAL_INTAKE_FAILED_HOLD_NO_GO"
                if result["archive_complete"] else
                "SOURCE_UNAVAILABLE_OR_INVALID_HOLD_NO_GO")
            result["requires_operator_review_before_retry"] = True
        records.append(result)
    status = (
        "OFFICIAL_FEEDS_ALL_FAILED_HOLD_NO_GO"
        if validated_bundle_count == 0 else
        "OFFICIAL_FEEDS_PARTIAL_HOLD_NO_GO"
        if validated_bundle_count != len(feeds)
        or any(r["status"] == "ARCHIVED_BUT_JOURNAL_INTAKE_FAILED_HOLD_NO_GO"
               for r in records) else
        "OFFICIAL_FEEDS_ARCHIVED_HOLD_NO_GO")
    result = {
        "schema": SCHEMA,
        "status": status,
        "archive_dir": str(out_dir),
        "feeds_requested": len(feeds),
        "feed_bundles_verified_format": validated_bundle_count,
        "network_calls_attempted": network_attempt_count,
        "new_recent_us_journal_records": journal_new,
        "latest_event_captured_does_not_prove_release_consensus": True,
        "news_is_not_complete_future_us_eur_jpy_calendar": True,
        "ai_inference_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "feeds": records,
    }
    with (out_dir / "capture_report.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="One-shot explicit official macro RSS archival, no orders or AI API")
    p.add_argument("--store", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--feed", choices=CANDIDATE_FEEDS, action="append")
    p.add_argument("--feed-file", action="append", default=[])
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--max-new", type=int, default=3)
    args = p.parse_args(argv)
    try:
        named = dict([_source_input(v) for v in args.feed_file])
        if len(named) != len(args.feed_file):
            raise InputError("duplicate local feed file")
        feeds = args.feed or sorted(named or CANDIDATE_FEEDS)
        report = run(
            args.store, args.out_dir, feeds,
            allow_network=args.allow_network, xml_files=named,
            max_new=args.max_new)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0 if report["feed_bundles_verified_format"] > 0 and (
            not any(r["status"] ==
                    "ARCHIVED_BUT_JOURNAL_INTAKE_FAILED_HOLD_NO_GO"
                    for r in report["feeds"])) else 2
    except (InputError, OSError, ValueError, TypeError, UnicodeError,
            ArithmeticError, KeyError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "OFFICIAL_FEED_INTAKE_FAIL_CLOSED_NO_GO",
            "reason": "INVALID_JOURNAL_OR_CAPTURE_MODE",
            "network_calls_attempted": 0,
            "new_recent_us_journal_records": 0,
            "ai_inference_calls_this_run": 0,
            "orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
