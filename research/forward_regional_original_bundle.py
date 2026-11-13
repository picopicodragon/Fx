"""FWD-1041..1120: one-shot, write-once packaging of genuine local originals.

The human must explicitly provide each original path, URL, alleged publish
and capture time, release time, quotation and any consensus value. We only
copy the already-saved bytes, generate checksums and strictly validate with
the existing regional validator. No scraping, guessing, live MT4, API or orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research import forward_regional_source_intake as intake
from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_original_package_request_v1"
REPORT = "fx_fwd_original_package_readiness_v1"
ROOT = frozenset({"schema", "observed_at_utc", "horizon_days",
                  "sources", "events"})
SOURCE = frozenset({"source_id", "source_kind", "source_file", "source_url",
                    "published_at_utc", "captured_at_utc"})
MAX_SPEC = 100_000
MAX_PATH_LENGTH = 1024
MAX_TOTAL_BYTES = 8_000_000
MANIFEST = "original_manifest.json"


def _file_path(spec_file: Path, raw_path: object) -> Path:
    if (type(raw_path) is not str or not 1 <= len(raw_path) <= MAX_PATH_LENGTH
            or raw_path != raw_path.strip()
            or any(x in raw_path for x in ("\x00", "\r", "\n", "*", "?"))):
        raise InputError("invalid or wildcard source filepath")
    path = Path(raw_path)
    if not path.is_absolute():
        path = spec_file.parent / path
    path = path.absolute()
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise InputError("source symlink paths forbidden")
    return path


def prepare(spec_file: Path, *, asof_utc: str) -> tuple[dict, dict, list[bytes]]:
    now = macro._utc(asof_utc)
    if not isinstance(spec_file, Path) or spec_file.is_symlink():
        raise InputError("invalid package request file")
    intake._safe_folder(spec_file.parent)
    raw_spec = intake._read(spec_file, MAX_SPEC)
    request = json.loads(raw_spec.decode("utf-8-sig"))
    if (type(request) is not dict or set(request) != ROOT
            or request["schema"] != SCHEMA
            or type(request["horizon_days"]) is not int
            or not 1 <= request["horizon_days"] <= 31
            or type(request["sources"]) is not list
            or not 1 <= len(request["sources"]) <= intake.MAX_SOURCE_FILES
            or type(request["events"]) is not list
            or not 1 <= len(request["events"]) <= macro.MAX_EVENTS):
        raise InputError("invalid input request shape")
    observed = macro._utc(request["observed_at_utc"])
    if observed > now:
        raise InputError("source observation time is future")
    sources = {}
    filenames = []
    rawfiles = []
    manifest_sources = []
    seen_paths = set()
    total_size = 0
    for n, entry in enumerate(request["sources"], 1):
        if (type(entry) is not dict or set(entry) != SOURCE
                or type(entry["source_id"]) is not str
                or not intake.IDENT.fullmatch(entry["source_id"])
                or entry["source_id"] in sources
                or entry["source_kind"] not in intake.SOURCE_KINDS):
            raise InputError("unsafe source registration")
        source_path = _file_path(spec_file, entry["source_file"])
        resolved = source_path.resolve(strict=True)
        if resolved == spec_file.resolve(strict=True) or resolved in seen_paths:
            raise InputError("original source repeated or points to request")
        seen_paths.add(resolved)
        raw = intake._read(source_path, intake.MAX_ORIGINAL_BYTES)
        total_size += len(raw)
        if total_size > MAX_TOTAL_BYTES or b"\x00" in raw:
            raise InputError("originals exceed bound or are binary")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError as exc:
            raise InputError("original must be UTF-8 text") from exc
        url = macro._url(entry["source_url"])
        published = macro._utc(entry["published_at_utc"])
        captured = macro._utc(entry["captured_at_utc"])
        if not published <= captured <= observed:
            raise InputError("invalid publication/capture chronology")
        # Fixed neutral filenames, independent of user path, and no path
        # disclosure in portable manifest.
        filename = f"original_{n:03d}.txt"
        metadata = {
            "source_id": entry["source_id"],
            "source_kind": entry["source_kind"],
            "filename": filename,
            "source_url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "published_at_utc": entry["published_at_utc"],
            "captured_at_utc": entry["captured_at_utc"],
        }
        sources[entry["source_id"]] = (metadata, text)
        filenames.append(filename)
        rawfiles.append(raw)
        manifest_sources.append(metadata)

    event_sources = set()
    projected = []
    used_ids = set()
    for entry in request["events"]:
        if (type(entry) is not dict or set(entry) != intake.EVENT_KEYS
                or type(entry["event_id"]) is not str
                or not intake.IDENT.fullmatch(entry["event_id"])
                or entry["event_id"] in used_ids
                or entry["currency"] not in macro.CURRENCIES
                or entry["event_type"] not in macro.CATEGORIES
                or type(entry["title"]) is not str
                or not 1 <= len(entry["title"]) <= 250
                or entry["title"].strip() != entry["title"]):
            raise InputError("invalid event evidence")
        used_ids.add(entry["event_id"])
        event_at = macro._utc(entry["scheduled_at_utc"])
        if not observed < event_at:
            raise InputError("event not future at claimed observation time")
        cal, host = intake._source(
            sources, entry["calendar_source_id"], "OFFICIAL_SCHEDULE",
            entry["calendar_excerpt"], event_at, observed)
        if host not in intake.OFFICIAL_SCHEDULE_HOSTS[entry["currency"]]:
            raise InputError("official schedule host outside currency allowlist")
        event_sources.add(entry["calendar_source_id"])
        forecast = None
        if entry["consensus"] is not None:
            claim = entry["consensus"]
            if (type(claim) is not dict
                    or set(claim) != intake.CONSENSUS_KEYS
                    or claim["unit"] not in intake.ALLOWED_UNITS
                    or type(claim["value"]) is not str):
                raise InputError("invalid consensus evidence")
            fc, _ = intake._source(
                sources, claim["source_id"], "PRE_RELEASE_CONSENSUS",
                claim["excerpt"], event_at, observed)
            value = claim["value"]
            macro._number(value)
            if re.search(
                r"(?<![0-9.])"+re.escape(value)+r"(?![0-9.])",
                fc["source_text"]) is None:
                raise InputError("consensus value missing in actual excerpt")
            event_sources.add(claim["source_id"])
            forecast = {"value": value, "unit": claim["unit"],
                        "source": fc}
        projected.append({
            "event_id": entry["event_id"], "currency": entry["currency"],
            "event_type": entry["event_type"], "title": entry["title"],
            "scheduled_at_utc": entry["scheduled_at_utc"],
            "calendar_source": cal, "consensus": forecast,
        })
    if set(sources) != event_sources:
        raise InputError("unreferenced raw source in package")
    observations = {
        "schema": macro.SCHEMA,
        "observed_at_utc": request["observed_at_utc"],
        "horizon_days": request["horizon_days"],
        "events": projected,
    }
    review = macro.inspect_observations(observations, asof_utc=asof_utc)
    if (review["runtime_go_no_go"] != "NO_GO"
            or review["safety_hold_latched"] is not True
            or review["demo_orders_permitted"] is not False
            or review["real_orders_permitted"] is not False):
        raise InputError("macro research contract violated NO_GO")
    manifest = {
        "schema": intake.SCHEMA,
        "observed_at_utc": request["observed_at_utc"],
        "horizon_days": request["horizon_days"],
        "sources": manifest_sources,
        "events": request["events"],
    }
    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, indent=2,
        allow_nan=False).encode("utf-8")
    if len(manifest_bytes) > intake.MAX_MANIFEST:
        raise InputError("generated manifest exceeds size cap")
    summary = {
        "schema": REPORT,
        "status": "ORIGINAL_PACKAGE_PRECHECK_HOLD_NO_GO",
        "source_file_count": len(rawfiles),
        "event_evidence_count": len(projected),
        "pre_release_consensus_evidence_count":
            sum(event["consensus"] is not None for event in projected),
        "raw_source_total_bytes": total_size,
        "request_sha256_local_integrity_only":
            hashlib.sha256(raw_spec).hexdigest(),
        "all_source_hashes_computed_from_saved_bytes": True,
        "timestamps_unverified_self_reports_only": True,
        "original_publisher_and_clock_independently_attested": False,
        "complete_fx_event_calendar_coverage_proven": False,
        "auto_filled_event_or_forecast_count": 0,
        "network_calls_this_run": 0,
        "API_calls_this_run": 0,
        "orders_sent_this_run": 0,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }
    return manifest, summary, rawfiles


def _safe_destination(spec_file: Path, out_dir: Path,
                      raw_file_paths: list[Path]) -> None:
    if (not isinstance(out_dir, Path) or out_dir.exists() or
            out_dir.is_symlink() or not out_dir.parent.is_dir()
            or out_dir.parent.is_symlink()):
        raise InputError("new output directory required")
    target = out_dir.resolve()
    roots = {spec_file.parent.resolve()}
    roots.update(p.parent.resolve() for p in raw_file_paths)
    for root in roots:
        if target == root or root in target.parents:
            raise InputError("output cannot be nested inside source directory")


def save(spec_file: Path, out_dir: Path, *, asof_utc: str) -> dict:
    manifest, summary, rawfiles = prepare(spec_file, asof_utc=asof_utc)
    spec_raw = intake._read(spec_file, MAX_SPEC)
    if (hashlib.sha256(spec_raw).hexdigest()
            != summary["request_sha256_local_integrity_only"]):
        raise InputError("package request changed during preflight")
    spec = json.loads(spec_raw.decode("utf-8-sig"))
    paths = [_file_path(spec_file, entry["source_file"])
             for entry in spec["sources"]]
    _safe_destination(spec_file, out_dir, paths)
    # User originals must not change between pre-validation and copy.
    for path, raw in zip(paths, rawfiles):
        if intake._read(path, intake.MAX_ORIGINAL_BYTES) != raw:
            raise InputError("source changed during verified packaging")
    out_dir.mkdir(exist_ok=False)
    for n, raw in enumerate(rawfiles, 1):
        with (out_dir / f"original_{n:03d}.txt").open("xb") as out:
            out.write(raw)
    # Manifest written last: an interrupted bundle has no completion marker.
    with (out_dir / MANIFEST).open("x", encoding="utf-8") as out:
        json.dump(manifest, out, ensure_ascii=False,
                  indent=2, allow_nan=False)
    _, verified = intake.load(out_dir / MANIFEST, asof_utc=asof_utc)
    if verified["source_file_count"] != summary["source_file_count"]:
        raise InputError("saved original count changed after packaging")
    return {
        **summary, "status": "ORIGINAL_PACKAGE_SAVED_AND_RECHECKED_HOLD_NO_GO",
        "output_original_count": len(rawfiles),
        "output_manifest_written_last": True,
        "source_authenticity_independently_verified": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Package explicit pre-saved regional originals; NO_GO")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--asof-utc", required=True)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.out_dir is None:
            _, report, _ = prepare(args.request, asof_utc=args.asof_utc)
            report["files_written_this_run"] = 0
        else:
            report = save(args.request, args.out_dir, asof_utc=args.asof_utc)
            report["files_written_this_run"] = (
                report["output_original_count"] + 1)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, ValueError, KeyError, TypeError, OSError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": REPORT,
            "status": "ORIGINAL_PACKAGE_FAIL_CLOSED_NO_GO",
            "reason_code": "UNSAFE_OR_UNVERIFIABLE_PACKAGE_REQUEST",
            "files_written_this_run": 0, "network_calls_this_run": 0,
            "API_calls_this_run": 0, "orders_sent_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
