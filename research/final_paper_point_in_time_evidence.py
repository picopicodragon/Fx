"""Offline point-in-time macro evidence archive with bounded source hashes.

This validator proves only LOCAL preservation of bytes and PC-claimed capture
chronology. It does not prove an authoritative publisher issued the bytes, a
third-party clock is correct, ALL USD/EUR/JPY events are covered, or a consensus
forecast was genuinely available when claimed. Those require independent
evidence and remain NO_GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_point_in_time_evidence_manifest_v1"
SHA = re.compile(r"^[0-9a-f]{64}$")
SAFE_PATH = re.compile(r"^[A-Za-z0-9._/-]{1,120}$")
CURRENCIES = {"USD", "EUR", "JPY"}
OFFICIAL = {
    "www.bls.gov", "www.federalreserve.gov",
    "www.ecb.europa.eu", "www.boj.or.jp", "www.bea.gov",
}
CONSENSUS = {"www.reuters.com", "www.bloomberg.com",
             "www.wsj.com", "www.investing.com"}
FIELDS = {"id", "currency", "release_at_utc",
          "official_source_url", "official_file", "official_sha256",
          "official_captured_at_utc_pc",
          "consensus_source_url", "consensus_file", "consensus_sha256",
          "consensus_captured_at_utc_pc"}


def _utc(value: str) -> datetime:
    if type(value) is not str:
        raise InputError("bad point-in-time timestamp")
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("bad point-in-time timestamp") from exc
    if d.tzinfo is None or d.utcoffset().total_seconds() != 0:
        raise InputError("point-in-time timestamp is not UTC")
    return d


def _url(value: str, allowed: set[str]) -> None:
    if type(value) is not str:
        raise InputError("source URL missing")
    url = urlparse(value)
    if (url.scheme != "https" or url.hostname not in allowed
            or url.username or url.password or url.port is not None
            or not url.path or url.path == "/"):
        raise InputError("unapproved publisher URL")


def _sha(root: Path, filename: str, expected: str) -> None:
    if (type(filename) is not str
            or SAFE_PATH.fullmatch(filename) is None
            or type(expected) is not str or SHA.fullmatch(expected) is None):
        raise InputError("unsafe offline source path or hash")
    rel = PurePosixPath(filename)
    if rel.is_absolute() or ".." in rel.parts or "." in rel.parts:
        raise InputError("source cannot escape evidence root")
    file = root / filename
    if (not file.is_file() or file.is_symlink()
            or any(p.is_symlink() for p in file.parents)
            or not 0 < file.stat().st_size <= 2_000_000):
        raise InputError("missing or unsafe source snapshot")
    hash = hashlib.sha256(file.read_bytes()).hexdigest()
    if hash != expected:
        raise InputError("source archive hash mismatch")


def audit(folder: Path, manifest: Path) -> dict:
    if (not folder.is_dir() or folder.is_symlink()
            or any(p.is_symlink() for p in folder.parents)
            or not manifest.is_file() or manifest.is_symlink()
            or not 0 < manifest.stat().st_size <= 64_000):
        raise InputError("unsafe archive or evidence manifest")
    raw = manifest.read_bytes()
    try:
        record = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise InputError("invalid source manifest") from exc
    if (type(record) is not dict
            or set(record) != {"schema", "events"}
            or record["schema"] != SCHEMA
            or type(record["events"]) is not list
            or not 1 <= len(record["events"]) <= 100):
        raise InputError("unsupported source manifest")
    currencies = set()
    ids = set()
    prior = None
    count = 0
    for event in record["events"]:
        if type(event) is not dict or set(event) != FIELDS:
            raise InputError("incomplete source event")
        ident = event["id"]
        if (type(ident) is not str or not 1 <= len(ident) <= 80
                or ident in ids):
            raise InputError("duplicate or malformed source event")
        ids.add(ident)
        cur = event["currency"]
        if cur not in CURRENCIES:
            raise InputError("unsupported currency")
        currencies.add(cur)
        release = _utc(event["release_at_utc"])
        scheduled = _utc(event["official_captured_at_utc_pc"])
        consensus = _utc(event["consensus_captured_at_utc_pc"])
        if scheduled >= release or consensus >= release:
            raise InputError("not a pre-release snapshot")
        if (release - scheduled).total_seconds() > 120*86400 or
                (release - consensus).total_seconds() > 30*86400):
            raise InputError("unreasonably old pre-release evidence")
        _url(event["official_source_url"], OFFICIAL)
        _url(event["consensus_source_url"], CONSENSUS)
        _sha(folder, event["official_file"], event["official_sha256"])
        _sha(folder, event["consensus_file"], event["consensus_sha256"])
        count += 1
    return {
        "schema": SCHEMA,
        "status": "LOCAL_PIT_BYTES_HASHED_NOT_INDEPENDENTLY_ATTESTED_NO_GO",
        "manifest_sha256_local_only": hashlib.sha256(raw).hexdigest(),
        "locally_matched_event_count": count,
        "locally_matched_snapshot_count": count*2,
        "source_currencies_with_local_records": sorted(currencies),
        "source_currencies_missing": sorted(CURRENCIES - currencies),
        "pc_claimed_pre_release_order_validated": True,
        "contents_independently_authenticated": False,
        "source_publication_time_independently_attested": False,
        "publisher_schedule_semantics_verified": False,
        "full_future_calendar_coverage_attested": False,
        "independent_market_consensus_attested": False,
        "live_virtual_entry_permitted": False,
        "paid_inference_permitted": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
    }


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="No-network FX pre-release source byte audit")
    p.add_argument("--archive-root", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args=p.parse_args(argv)
    try:
        result=audit(args.archive_root,args.manifest)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("unsafe new PIT report")
        with args.out.open("x",encoding="utf-8") as stream:
            json.dump(result,stream,ensure_ascii=False,indent=2,
                      allow_nan=False)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,OSError,ValueError,KeyError,TypeError,
            UnicodeError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"POINT_IN_TIME_EVIDENCE_FAIL_CLOSED_NO_GO",
            "live_virtual_entry_permitted":False,
            "paid_inference_permitted":False,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
