"""FWD-881..960: actual saved-page, point-in-time regional evidence intake.

Reads operator-chosen UTF-8/HTML text *files* and an explicit manifest.
Archives are not fetched, redated, enriched, or rewritten. Raw SHA256
and verbatim excerpts are checked against the bytes on disk. Publication
times and sources remain SELF-REPORTED, even for official hosts. The
generated observations are only for the existing offline macro research
contract; not for any trading/blackout execution controller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_global_macro_evidence as macro
from research.forward_macro_pre_release_capture import ALLOWED_UNITS
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_regional_original_source_manifest_v1"
REPORT = "fx_fwd_regional_original_source_intake_v1"
SOURCE_KEYS = frozenset({
    "source_id", "source_kind", "filename", "source_url", "sha256",
    "published_at_utc", "captured_at_utc",
})
EVENT_KEYS = frozenset({
    "event_id", "currency", "event_type", "title", "scheduled_at_utc",
    "calendar_source_id", "calendar_excerpt", "consensus",
})
CONSENSUS_KEYS = frozenset({"source_id", "excerpt", "value", "unit"})
ROOT_KEYS = frozenset({"schema", "observed_at_utc", "horizon_days",
                       "sources", "events"})
SOURCE_KINDS = frozenset({"OFFICIAL_SCHEDULE", "PRE_RELEASE_CONSENSUS"})
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_MANIFEST = 100_000
MAX_ORIGINAL_BYTES = 512_000
MAX_SOURCE_FILES = 64
MAX_EXCERPT = 2000
OFFICIAL_SCHEDULE_HOSTS = {
    "USD": frozenset({
        "www.bls.gov", "www.federalreserve.gov", "www.bea.gov",
        "www.census.gov",
    }),
    "EUR": frozenset({"www.ecb.europa.eu", "ec.europa.eu"}),
    "JPY": frozenset({
        "www.boj.or.jp", "www.stat.go.jp",
        "www.mhlw.go.jp", "www.esri.cao.go.jp", "www.mof.go.jp",
    }),
}


def _read(path: Path, max_bytes: int) -> bytes:
    if (not isinstance(path, Path) or path.is_symlink()
            or not path.is_file() or not 0 < path.stat().st_size <= max_bytes):
        raise InputError("missing, unsafe or oversized saved original")
    raw = path.read_bytes()
    if not 0 < len(raw) <= max_bytes:
        raise InputError("saved source size changed while reading")
    return raw


def _safe_folder(path: Path) -> None:
    if (not isinstance(path, Path) or not path.is_dir() or path.is_symlink()
            or any(p.is_symlink() for p in path.parents)):
        raise InputError("unsafe original source folder")


def _excerpt(text: str, excerpt: object) -> str:
    if (type(excerpt) is not str or not 1 <= len(excerpt) <= MAX_EXCERPT
            or "\x00" in excerpt or excerpt.strip() != excerpt
            or excerpt not in text):
        raise InputError("excerpt must exactly match saved original bytes")
    return excerpt


def _source(sources: dict, key: object, kind: str, excerpt: object,
            event_time, observed) -> tuple[dict, str]:
    if type(key) is not str or key not in sources:
        raise InputError("source id not found")
    meta, text = sources[key]
    if meta["source_kind"] != kind:
        raise InputError("wrong source kind for event evidence")
    chunk = _excerpt(text, excerpt)
    published = macro._utc(meta["published_at_utc"])
    captured = macro._utc(meta["captured_at_utc"])
    if (not published <= captured <= observed < event_time
            or (kind == "PRE_RELEASE_CONSENSUS"
                and not captured < event_time - __import__(
                    "datetime").timedelta(minutes=15))):
        raise InputError("source captured too late or invalid chronology")
    result = {
        "source_url": meta["source_url"],
        "source_text": chunk,
        "source_sha256": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
        "published_at_utc": meta["published_at_utc"],
        "captured_at_utc": meta["captured_at_utc"],
    }
    return result, urlsplit(meta["source_url"]).hostname


def load(manifest_file: Path, *, asof_utc: str) -> tuple[dict, dict]:
    now = macro._utc(asof_utc)
    if (not isinstance(manifest_file, Path) or manifest_file.is_symlink()):
        raise InputError("unsafe evidence manifest")
    _safe_folder(manifest_file.parent)
    raw_manifest = _read(manifest_file, MAX_MANIFEST)
    manifest = json.loads(raw_manifest.decode("utf-8-sig"))
    if (type(manifest) is not dict or set(manifest) != ROOT_KEYS
            or manifest["schema"] != SCHEMA
            or type(manifest["horizon_days"]) is not int
            or not 1 <= manifest["horizon_days"] <= 31
            or type(manifest["sources"]) is not list
            or not 0 <= len(manifest["sources"]) <= MAX_SOURCE_FILES
            or type(manifest["events"]) is not list
            or not 0 <= len(manifest["events"]) <= macro.MAX_EVENTS):
        raise InputError("regional original manifest shape invalid")
    observed = macro._utc(manifest["observed_at_utc"])
    if observed > now:
        raise InputError("manifest observation time is future")
    sources: dict[str, tuple[dict, str]] = {}
    filenames = set()
    for item in manifest["sources"]:
        if (type(item) is not dict or set(item) != SOURCE_KEYS
                or type(item["source_id"]) is not str
                or not IDENT.fullmatch(item["source_id"])
                or item["source_id"] in sources
                or item["source_kind"] not in SOURCE_KINDS
                or type(item["filename"]) is not str
                or not FILENAME.fullmatch(item["filename"])
                or item["filename"] in filenames
                or type(item["sha256"]) is not str
                or not SHA.fullmatch(item["sha256"])):
            raise InputError("unsafe or duplicate original source")
        if item["filename"] == manifest_file.name:
            raise InputError("manifest cannot reference itself as original")
        url = macro._url(item["source_url"]) if hasattr(macro, "_url") else None
        if not url:
            raise InputError("invalid original source URL")
        if (macro._utc(item["published_at_utc"]) >
                macro._utc(item["captured_at_utc"])
                or macro._utc(item["captured_at_utc"]) > observed):
            raise InputError("original has future/contradictory timestamps")
        content = _read(
            manifest_file.parent / item["filename"], MAX_ORIGINAL_BYTES)
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise InputError("original file SHA256 mismatch")
        if b"\x00" in content:
            raise InputError("binary original prohibited")
        try:
            text = content.decode("utf-8-sig")
        except UnicodeError as exc:
            raise InputError("original must be saved as UTF-8") from exc
        sources[item["source_id"]] = (item, text)
        filenames.add(item["filename"])

    events = []
    used_ids = set()
    used_sources = set()
    for item in manifest["events"]:
        if (type(item) is not dict or set(item) != EVENT_KEYS
                or type(item["event_id"]) is not str
                or not IDENT.fullmatch(item["event_id"])
                or item["event_id"] in used_ids
                or item["currency"] not in macro.CURRENCIES
                or item["event_type"] not in macro.CATEGORIES
                or type(item["title"]) is not str
                or not 1 <= len(item["title"]) <= 250
                or item["title"].strip() != item["title"]):
            raise InputError("invalid event in saved original")
        used_ids.add(item["event_id"])
        event_at = macro._utc(item["scheduled_at_utc"])
        if not observed < event_at:
            raise InputError("source claim for already-past event")
        cal, host = _source(
            sources, item["calendar_source_id"], "OFFICIAL_SCHEDULE",
            item["calendar_excerpt"], event_at, observed)
        if host not in OFFICIAL_SCHEDULE_HOSTS[item["currency"]]:
            raise InputError("schedule source is not allowlisted official region")
        used_sources.add(item["calendar_source_id"])
        consensus = None
        if item["consensus"] is not None:
            info = item["consensus"]
            if (type(info) is not dict or set(info) != CONSENSUS_KEYS
                    or info["unit"] not in ALLOWED_UNITS):
                raise InputError("invalid forecast entry")
            chunk, _ = _source(
                sources, info["source_id"], "PRE_RELEASE_CONSENSUS",
                info["excerpt"], event_at, observed)
            used_sources.add(info["source_id"])
            value = info["value"]
            macro._number(value)
            if (type(value) is not str or
                    re.search(r"(?<![0-9.])"+re.escape(value)+r"(?![0-9.])",
                              chunk["source_text"]) is None):
                raise InputError("forecast number not present in saved excerpt")
            consensus = {
                "value": value, "unit": info["unit"], "source": chunk,
            }
        events.append({
            "event_id": item["event_id"],
            "currency": item["currency"],
            "event_type": item["event_type"],
            "title": item["title"],
            "scheduled_at_utc": item["scheduled_at_utc"],
            "calendar_source": cal,
            "consensus": consensus,
        })
    if set(sources) != used_sources:
        raise InputError("unused original source in manifest")
    payload = {
        "schema": macro.SCHEMA,
        "observed_at_utc": manifest["observed_at_utc"],
        "horizon_days": manifest["horizon_days"],
        "events": events,
    }
    # Existing strict global-macro validator is authoritative for this
    # interchange contract. No new or fake validation standards.
    inspected = macro.inspect_observations(payload, asof_utc=asof_utc)
    if (inspected.get("runtime_go_no_go") != "NO_GO"
            or inspected.get("safety_hold_latched") is not True
            or inspected.get("demo_orders_permitted") is not False
            or inspected.get("real_orders_permitted") is not False):
        raise InputError("regional source unexpectedly permits orders")
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > macro.MAX_INPUT_BYTES:
        raise InputError("generated external macro envelope too large")
    summary = {
        "schema": REPORT,
        "status": "REGIONAL_ORIGINAL_SOURCE_INTAKE_HOLD_NO_GO",
        "source_file_count": len(sources),
        "event_observations_count": len(events),
        "pre_release_consensus_count": sum(e["consensus"] is not None for e in events),
        "missing_pre_release_consensus_count": sum(e["consensus"] is None for e in events),
        "source_manfiest_sha256_local_integrity_only":
            hashlib.sha256(raw_manifest).hexdigest(),
        "regional_event_observations_unattested":
            inspected["external_by_currency"],
        "verbatim_excerpts_match_saved_files": True,
        "raw_original_digests_match_manifest": True,
        "publication_and_capture_timestamps_independently_verified": False,
        "schedule_identity_and_consensus_semantics_independently_verified": False,
        "source_hosts_genuine_origin_authenticated": False,
        "complete_fx_calendar_coverage_verified": False,
        "market_consensus_independently_verified": False,
        "generated_interchange_usable_as_trading_signal": False,
        "unresolved_holds": sorted(set(inspected["unresolved_holds"]) | {
            "REGIONAL_SOURCE_FILES_SELF_REPORTED_NOT_INDEPENDENTLY_AUTHENTICATED",
            "SOURCE_PUBLICATION_CLOCK_NOT_INDEPENDENTLY_VERIFIED",
        }),
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }
    return payload, summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline raw regional source intake; no trading")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--emit-observations", type=Path)
    a = p.parse_args(argv)
    try:
        if a.emit_observations is not None:
            output = a.emit_observations
            if (output.exists() or output.is_symlink()
                    or not output.parent.is_dir() or output.parent.is_symlink()):
                raise InputError("new output path required")
            if (output.resolve() == a.manifest.resolve()
                    or a.manifest.parent.resolve() in output.resolve().parents):
                raise InputError("cannot write inside saved source bundle")
        observations, result = load(a.manifest, asof_utc=a.asof_utc)
        if a.emit_observations is not None:
            with a.emit_observations.open("x", encoding="utf-8") as f:
                json.dump(observations, f, ensure_ascii=False, indent=2,
                          allow_nan=False)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": REPORT,
            "status": "REGIONAL_ORIGINAL_SOURCE_INTAKE_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_OR_UNVERIFIABLE_SAVED_ORIGINALS",
            "network_calls_this_run": 0,
            "API_calls_this_run": 0,
            "orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
