"""FWD-441..488: explicit, one-shot BLS/Fed/ECB/BOJ news-feed evidence.

One capture only on --allow-network. Offline copies are possible.
Feeds are retrospective NEWS, never a release calendar or consensus source.
A completed immutable bundle has a manifest written last. No trading.
"""
from __future__ import annotations

import argparse
import email.utils
import hashlib
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_rss as old_rss
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_multi_official_feed_capture_v1"
FEEDS = {
    "bls_cpi": old_rss.FEEDS["bls_cpi"],
    "bls_empsit": old_rss.FEEDS["bls_empsit"],
    "fed_policy": old_rss.FEEDS["fed_policy"],
    "ecb_press": "https://www.ecb.europa.eu/rss/press.html",
    "boj_whatsnew": "https://www.boj.or.jp/en/rss/whatsnew.xml",
}
SOURCE_HOSTS = {
    "bls_cpi": "www.bls.gov",
    "bls_empsit": "www.bls.gov",
    "fed_policy": "www.federalreserve.gov",
    "ecb_press": "www.ecb.europa.eu",
    "boj_whatsnew": "www.boj.or.jp",
}
MAX_XML = 256_000
MAX_ENTRIES = 50
MAX_MANIFEST = 15_000
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
UTC_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _now():
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _time(value: str):
    if type(value) is not str or not UTC_FORMAT.fullmatch(value):
        raise InputError("UTC observation must be Z seconds")
    parsed = timestamp(value)
    if parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise InputError("UTC observation offset invalid")
    return parsed


def _published(s: str):
    if type(s) is not str or not 1 <= len(s) <= 100:
        raise InputError("publisher date missing")
    try:
        value = email.utils.parsedate_to_datetime(s)
    except (IndexError, ValueError, TypeError):
        value = None
    if value is None:
        try:
            value = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InputError("unsupported publisher date") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise InputError("publisher date has no timezone")
    return value.astimezone(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _link(url: str, feed: str):
    if type(url) is not str or not 1 <= len(url) <= 1400 or (
            any(c.isspace() for c in url)):
        raise InputError("item link invalid")
    try:
        parts = urlsplit(url)
        if (parts.scheme != "https"
                or parts.hostname != SOURCE_HOSTS[feed]
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443)
                or parts.fragment or not parts.path.startswith("/")
                or parts.path.startswith("//")):
            raise InputError("item link not same official source host")
    except ValueError as exc:
        raise InputError("malformed source link") from exc
    return url


def _parse_news(xml: bytes, feed: str, asof_utc: str):
    if type(xml) is not bytes or not 0 < len(xml) <= MAX_XML:
        raise InputError("feed bytes missing or oversized")
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise InputError("DTD/entity prohibited")
    observed = _time(asof_utc)
    if feed in old_rss.FEEDS:
        rows = old_rss.parse_feed(xml, feed, received_utc=asof_utc)
        return [
            {
                "link": _link(e["payload"]["source_url"], feed),
                "published_at_utc": e["payload"]["published_at_utc"],
                "title_sha256": hashlib.sha256(
                    e["payload"]["title"].encode("utf-8")).hexdigest(),
            }
            for e in rows
        ]
    if feed not in FEEDS:
        raise InputError("feed not allowlisted")
    root = ET.fromstring(xml)
    items = []
    if root.tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise InputError("missing RSS channel")
        for e in channel.findall("item"):
            items.append((
                (e.findtext("title") or "").strip(),
                (e.findtext("link") or "").strip(),
                (e.findtext("pubDate") or e.findtext(DC + "date") or "").strip(),
            ))
    elif root.tag == ATOM + "feed":
        for e in root.findall(ATOM + "entry"):
            links = [
                el.get("href") for el in e.findall(ATOM + "link")
                if el.get("rel", "alternate") == "alternate"
            ]
            if len(links) != 1:
                raise InputError("non-unique Atom news link")
            items.append((
                "".join(e.find(ATOM + "title").itertext()).strip()
                if e.find(ATOM + "title") is not None else "",
                links[0],
                (e.findtext(ATOM + "published") or "").strip(),
            ))
    else:
        raise InputError("unknown RSS/Atom root")
    if len(items) > MAX_ENTRIES:
        raise InputError("RSS news item limit")
    result = []
    seen = set()
    for title, link, published in items:
        if not 1 <= len(title) <= 250:
            raise InputError("invalid RSS title length")
        url = _link(link, feed)
        if url in seen:
            raise InputError("duplicate news item link")
        seen.add(url)
        t = _published(published)
        if _time(t) > observed:
            raise InputError("future news publication date")
        result.append({
            "link": url,
            "published_at_utc": t,
            "title_sha256": hashlib.sha256(
                title.encode("utf-8")).hexdigest(),
        })
    return result


def _download(feed: str, *, opener=None):
    if feed in old_rss.FEEDS:
        return old_rss.get_feed(feed)
    if feed not in FEEDS:
        raise InputError("feed not allowlisted")
    opener = opener or urllib.request.build_opener(old_rss.NoRedirect())
    request = urllib.request.Request(
        FEEDS[feed], headers={
            "User-Agent": "FxResearchMultiRegionSnapshot/0.1",
            "Accept": "application/rss+xml, application/atom+xml, application/xml"})
    with opener.open(request, timeout=12) as response:
        if response.status != 200:
            raise InputError("RSS status not successful")
        raw = response.read(MAX_XML + 1)
    if not 0 < len(raw) <= MAX_XML:
        raise InputError("RSS response size invalid")
    return raw


def prepare(raw_by_feed: dict, *, captured_at_utc: str,
            collection_mode: str):
    _time(captured_at_utc)
    if collection_mode not in ("EXPLICIT_NETWORK_SINGLE_PASS", "LOCAL_COPY"):
        raise InputError("observation mode invalid")
    if (type(raw_by_feed) is not dict or not 1 <= len(raw_by_feed) <= len(FEEDS)
            or any(name not in FEEDS for name in raw_by_feed)):
        raise InputError("invalid official feed set")
    details = {}
    for name in sorted(raw_by_feed):
        raw = raw_by_feed[name]
        items = _parse_news(raw, name, captured_at_utc)
        details[name] = {
            "filename": name + ".xml",
            "source_url": FEEDS[name],
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "source_bytes": len(raw),
            "news_item_count": len(items),
            "news_published_within_24h_count": sum(
                ( _time(captured_at_utc) - _time(item["published_at_utc"])
                ).total_seconds() <= 86400 for item in items),
            "news_items_unverified": items[:MAX_ENTRIES],
        }
    return {
        "schema": SCHEMA,
        "status": "MULTI_OFFICIAL_NEWS_SNAPSHOT_RESEARCH_HOLD_NO_GO",
        "collection_mode": collection_mode,
        "captured_at_utc_local_clock_unattested": captured_at_utc,
        "feeds": details,
        "publisher_publication_clock_attested": False,
        "source_authenticity_independently_verified": False,
        "is_future_release_schedule": False,
        "scheduled_event_count": 0,
        "pre_release_consensus_count": 0,
        "no_background_retry_or_polling": True,
        "network_calls_expected": (
            len(details) if collection_mode == "EXPLICIT_NETWORK_SINGLE_PASS"
            else 0),
        "files_complete_marker_written_last": True,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def _bytes(path: Path, *, limit=MAX_XML):
    if (not path.is_file() or path.is_symlink()
            or not 0 < path.stat().st_size <= limit):
        raise InputError("unsafe raw feed file")
    result = path.read_bytes()
    if not 0 < len(result) <= limit:
        raise InputError("raw file changed size")
    return result


def save(out: Path, raw_by_feed: dict, manifest: dict):
    if (not isinstance(out, Path) or out.exists() or out.is_symlink()
            or not out.parent.is_dir() or out.parent.is_symlink()):
        raise InputError("new output folder required")
    out.mkdir(exist_ok=False)
    for feed, raw in sorted(raw_by_feed.items()):
        with (out / (feed + ".xml")).open("xb") as stream:
            stream.write(raw)
    # Only this final file marks a complete valid local observation.
    with (out / "manifest.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False,
                  indent=2, allow_nan=False)


def verify(out: Path):
    if not isinstance(out, Path) or not out.is_dir() or out.is_symlink():
        raise InputError("missing/unsafe completed feed bundle")
    recorded = json.loads(_bytes(
        out / "manifest.json", limit=MAX_MANIFEST))
    if (type(recorded) is not dict or recorded.get("schema") != SCHEMA
            or recorded.get("status")
            != "MULTI_OFFICIAL_NEWS_SNAPSHOT_RESEARCH_HOLD_NO_GO"
            or recorded.get("runtime_go_no_go") != "NO_GO"
            or recorded.get("safety_hold_latched") is not True
            or recorded.get("demo_orders_permitted") is not False
            or recorded.get("real_orders_permitted") is not False
            or recorded.get("files_complete_marker_written_last") is not True
            or type(recorded.get("feeds")) is not dict):
        raise InputError("invalid or incomplete feed bundle manifest")
    raw = {
        feed: _bytes(out / (feed + ".xml"))
        for feed in recorded["feeds"]
        if feed in FEEDS}
    if len(raw) != len(recorded["feeds"]):
        raise InputError("unrecognized feed in snapshot")
    reconstructed = prepare(
        raw, captured_at_utc=recorded[
            "captured_at_utc_local_clock_unattested"],
        collection_mode=recorded["collection_mode"])
    if reconstructed != recorded:
        raise InputError("news snapshot source or manifest modified")
    return {
        "schema": SCHEMA,
        "status": "MULTI_OFFICIAL_NEWS_SNAPSHOT_VERIFIED_HOLD_NO_GO",
        "feed_count": len(raw),
        "news_items_count": sum(
            x["news_item_count"] for x in recorded["feeds"].values()),
        "observed_regions": {
            "USD": sum(x in raw for x in ("bls_cpi", "bls_empsit", "fed_policy")),
            "EUR": int("ecb_press" in raw),
            "JPY": int("boj_whatsnew" in raw),
        },
        "historical_news_does_not_prove_upcoming_calendar": True,
        "consensus_evidence_missing": True,
        "source_authenticity_independently_verified": False,
        "files_written_this_run": 0,
        "network_calls_this_run": 0,
        "actual_orders_sent": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def _name_file(value: str):
    parts = value.split("=", 1)
    if len(parts) != 2 or parts[0] not in FEEDS or not parts[1]:
        raise InputError("feed-file must be allowlisted name=path")
    return parts[0], Path(parts[1])


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Opt-in BLS/Fed/ECB/BOJ RSS snapshot, NEVER orders")
    p.add_argument("--out-dir", type=Path)
    p.add_argument("--verify-bundle", type=Path)
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--feed", action="append", choices=sorted(FEEDS), default=[])
    p.add_argument("--feed-file", action="append", default=[])
    a = p.parse_args(argv)
    phase = "INPUT"
    try:
        if a.verify_bundle is not None:
            if a.out_dir or a.feed or a.feed_file or a.allow_network:
                raise InputError("verify mode takes only bundle directory")
            report = verify(a.verify_bundle)
        else:
            if (not a.out_dir or a.out_dir.exists() or a.out_dir.is_symlink()
                    or not a.out_dir.parent.is_dir()
                    or a.out_dir.parent.is_symlink()
                    or bool(a.allow_network) == bool(a.feed_file)
                    or (a.allow_network and a.feed_file)
                    or (a.feed and not a.allow_network)):
                raise InputError("one explicit capture mode and new output folder")
            if a.allow_network:
                names = a.feed or sorted(FEEDS)
                if len(names) != len(set(names)):
                    raise InputError("duplicate feed choice")
                phase = "NETWORK"
                raw = {name: _download(name) for name in names}
                mode = "EXPLICIT_NETWORK_SINGLE_PASS"
            else:
                chosen = [_name_file(v) for v in a.feed_file]
                if len({name for name, _ in chosen}) != len(chosen):
                    raise InputError("duplicate offline feed ID")
                phase = "LOCAL_COPY"
                raw = {name: _bytes(path) for name, path in chosen}
                mode = "LOCAL_COPY"
            phase = "VALIDATE"
            manifest = prepare(raw, captured_at_utc=_now(),
                               collection_mode=mode)
            phase = "WRITE"
            save(a.out_dir, raw, manifest)
            report = {
                "schema": SCHEMA,
                "status": manifest["status"],
                "feed_count": len(raw),
                "news_items_count": sum(
                    x["news_item_count"] for x in manifest["feeds"].values()),
                "snapshot_dir_created": True,
                "scheduled_event_count": 0,
                "pre_release_consensus_count": 0,
                "independent_publisher_authentication": False,
                "real_orders_permitted": False,
                "demo_orders_permitted": False,
                "runtime_go_no_go": "NO_GO",
                "safety_hold_latched": True,
            }
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, UnicodeError, KeyError,
            TypeError, ArithmeticError, ET.ParseError, urllib.error.URLError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "MULTI_OFFICIAL_NEWS_SNAPSHOT_FAIL_CLOSED_NO_GO",
            "stage": phase,
            "possibly_incomplete_folder_requires_no_manifest": phase == "WRITE",
            "automatic_retries": False,
            "actual_orders_sent": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
