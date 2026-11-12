"""FX-FWD-007: opt-in official public RSS download to research journal.

No price feed, real-time guarantee, or trading. Source provenance is an
unverified URL observation, NOT authenticated official financial evidence.
RSS does not contain reliable pre-release consensus; never fabricate one.
"""
from __future__ import annotations

import argparse
import email.utils
import hashlib
import json
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from research import forward_observation as journal
from research.offline_backtest import InputError, PAIRS, timestamp

FEEDS = {
    "bls_empsit": "https://www.bls.gov/feed/empsit.rss",
    "bls_cpi": "https://www.bls.gov/feed/cpi.rss",
    "fed_policy": "https://www.federalreserve.gov/feeds/press_monetary.xml",
}
HOSTS = {"www.bls.gov", "www.federalreserve.gov"}
MAX_RESPONSE = 256_000
MAX_ITEMS = 30
TIMEOUT = 12


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise InputError("redirect prohibited; feed destination changed")


def _require_official_url(value: str) -> str:
    if type(value) is not str or len(value) > 1400:
        raise InputError("unrecognized feed item URL")
    parsed = urlparse(value)
    if (parsed.scheme != "https" or parsed.hostname not in HOSTS
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment or not parsed.path.startswith("/")):
        raise InputError("unverified feed item URL")
    return value


def _when(value: str) -> str:
    if not value:
        raise InputError("missing source publishing time")
    try:
        date = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError) as exc:
        raise InputError("unreadable RSS publication timestamp") from exc
    if date is None or date.tzinfo is None:
        raise InputError("RSS timestamp has no timezone")
    return date.astimezone(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


ATOM = "{http://www.w3.org/2005/Atom}"
BLS_ATOM_FEEDS = frozenset(("bls_cpi", "bls_empsit"))


def _atom_when(value: str) -> str:
    """RFC3339 timestamp converted to UTC; no naive or future guess."""
    if type(value) is not str or not value or len(value) > 80:
        raise InputError("ATOM_PUBLISHED_MISSING_OR_INVALID")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("ATOM_PUBLISHED_MISSING_OR_INVALID") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise InputError("ATOM_PUBLICATION_TIMEZONE_MISSING")
    return dt.astimezone(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _atom_text(entry: ET.Element, tag: str) -> str:
    el = entry.find(ATOM + tag)
    return ("".join(el.itertext()).strip() if el is not None else "")


def _atom_link(entry: ET.Element) -> str:
    """Require exactly one canonical 'alternate' news link, never feed/self."""
    possible = []
    for link in entry.findall(ATOM + "link"):
        if link.get("rel", "alternate") in ("alternate", ""):
            possible.append(link.get("href"))
    if len(possible) != 1:
        raise InputError("ATOM_ALTERNATE_LINK_NOT_UNIQUE")
    url = _require_official_url(possible[0])
    if urlparse(url).hostname != "www.bls.gov":
        raise InputError("ATOM_NEWS_LINK_NOT_BLS")
    return url


def _parse_atom(root: ET.Element, feed: str, received: str) -> list[dict]:
    if feed not in BLS_ATOM_FEEDS or root.tag != ATOM + "feed":
        raise InputError("unexpected RSS root, fail closed")
    entries = root.findall(ATOM + "entry")
    if len(entries) > MAX_ITEMS:
        raise InputError("excessive RSS items")
    result = []
    seen = set()
    for entry in entries:
        title = _atom_text(entry, "title")
        link = _atom_link(entry)
        # Atom 'updated' is NOT the original release time. Never silently
        # substitute it for missing 'published' or backdate old news.
        published = _atom_when(_atom_text(entry, "published"))
        if timestamp(published) > timestamp(received):
            raise InputError("future-dated RSS release")
        summary = _atom_text(entry, "summary") or _atom_text(entry, "content")
        if not title or len(title) > 200 or len(summary) > 5500:
            raise InputError("invalid RSS entry size")
        if link in seen:
            raise InputError("duplicate item within RSS response")
        seen.add(link)
        result.append({
            "schema": journal.SCHEMA, "kind": "MACRO_EVENT",
            "observed_at_utc": received,
            "source_id": feed,
            "payload": {
                "pair": "USD/JPY",
                "title": title,
                "source_url": link,
                "published_at_utc": published,
                "content": summary or title,
                "consensus": "",
                "released_value": "",
                "source_status": "USER_SUPPLIED_UNVERIFIED",
            },
        })
    return result


def parse_feed(xml: bytes, feed: str, *, received_utc: str) -> list[dict]:
    if feed not in FEEDS or not isinstance(xml, bytes):
        raise InputError("unknown RSS feed")
    if len(xml) > MAX_RESPONSE or b"<!DOCTYPE" in xml.upper() or (
            b"<!ENTITY" in xml.upper()):
        raise InputError("unsafe RSS XML")
    timestamp(received_utc)
    root = ET.fromstring(xml)
    if root.tag == ATOM + "feed":
        return _parse_atom(root, feed, received_utc)
    if root.tag != "rss":
        raise InputError("unexpected RSS root, fail closed")
    channel = root.find("channel")
    if channel is None:
        raise InputError("missing RSS channel")
    items = channel.findall("item")
    if len(items) > MAX_ITEMS:
        raise InputError("excessive RSS items")
    result = []
    seen = set()
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = _require_official_url((item.findtext("link") or "").strip())
        published = _when((item.findtext("pubDate") or "").strip())
        if timestamp(published) > timestamp(received_utc):
            raise InputError("future-dated RSS release")
        description = (item.findtext("description") or "").strip()
        if not title or len(title) > 200 or len(description) > 5500:
            raise InputError("invalid RSS entry size")
        if link in seen:
            raise InputError("duplicate item within RSS response")
        seen.add(link)
        source_id = feed
        result.append({
            "schema": journal.SCHEMA, "kind": "MACRO_EVENT",
            "observed_at_utc": received_utc,
            "source_id": source_id,
            "payload": {
                "pair": "USD/JPY" if feed != "fed_policy" else "USD/JPY",
                "title": title,
                "source_url": link,
                "published_at_utc": published,
                "content": description or title,
                "consensus": "",
                "released_value": "",
                "source_status": "USER_SUPPLIED_UNVERIFIED",
            },
        })
    return result


def get_feed(feed: str, *, opener=None) -> bytes:
    if feed not in FEEDS:
        raise InputError("feed not allowlisted")
    request = urllib.request.Request(
        FEEDS[feed],
        headers={"User-Agent": "FxResearchForwardObserver/0.1",
                 "Accept": "application/rss+xml, application/atom+xml, application/xml"})
    opener = opener or urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise InputError("non-success RSS response")
        data = response.read(MAX_RESPONSE + 1)
        if len(data) > MAX_RESPONSE:
            raise InputError("RSS exceeded response cap")
        return data


def _prior_links(store: Path, source: str) -> set[str]:
    validated = journal.audit(store)
    links = set()
    for i in range(1, validated["record_count"] + 1):
        obj = json.loads(
            (store / f"{i:08d}.json").read_text(encoding="utf-8"))
        sample = obj["snapshot"]
        if (sample["kind"] == "MACRO_EVENT"
                and sample["source_id"] == source):
            links.add(sample["payload"]["source_url"])
    return links


def import_xml(store: Path, feed: str, xml: bytes, *,
               now: datetime | None = None, max_new: int = 3) -> dict:
    if type(max_new) is not int or not 1 <= max_new <= 5:
        raise InputError("explicit small per-run item cap required")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    received = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    entries = parse_feed(xml, feed, received_utc=received)
    prev = _prior_links(store, feed)
    fresh = [entry for entry in entries
             if entry["payload"]["source_url"] not in prev]
    # Old already-published RSS records are not live signals. Observe all
    # release ages, retaining only recent records within a 24h window.
    fresh = [e for e in fresh if (
        timestamp(received) - timestamp(e["payload"]["published_at_utc"])
    ).total_seconds() <= 86400]
    if len(fresh) > max_new:
        raise InputError("new RSS entries exceed explicit item cap")
    captured = []
    for entry in fresh:
        # Local temporary staging is outside the journal, removed after use.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rss_snapshot.json"
            path.write_text(json.dumps(entry, ensure_ascii=False),
                            encoding="utf-8")
            result = journal.ingest(store, path, now=now)
        captured.append(result["record_sha256"])
    return {
        "status": "OFFICIAL_RSS_OBSERVATION_NO_GO",
        "feed": feed, "fetched_items": len(entries),
        "new_recent_items": len(captured),
        "record_sha256s": captured,
        "source_authenticity_verified": False,
        "published_at_used_not_fetch_timestamp": True,
        "pre_release_consensus_available": False,
        "price_stream_connected": False,
        "economic_calendar_complete": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Explicit official RSS poll, research only, no trading")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--feed", choices=sorted(FEEDS), required=True)
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--xml-file", type=Path)
    p.add_argument("--max-new", type=int, default=3)
    args = p.parse_args(argv)
    try:
        if bool(args.allow_network) == bool(args.xml_file):
            raise InputError("exactly one of explicit network or offline XML")
        if args.xml_file:
            if args.xml_file.stat().st_size > MAX_RESPONSE:
                raise InputError("RSS file too large")
            xml = args.xml_file.read_bytes()
        else:
            xml = get_feed(args.feed)
        result = import_xml(args.store, args.feed, xml,
                            max_new=args.max_new)
        print(json.dumps(result))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            UnicodeError, ET.ParseError, urllib.error.URLError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "RSS_INGEST_UNSAFE_OR_UNAVAILABLE",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
