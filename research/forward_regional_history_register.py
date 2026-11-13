"""FWD-1281..1320: one-shot history registration without manual SHA typing.

Only explicitly named, existing regional original manifests are accepted.
The old history is *read-only*; extending it writes a new history filename,
never overwriting old evidence. No file-system discovery, scheduling, HTTP,
inference, broker, MT4 or order path is present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research import forward_regional_evidence_history as history
from research import forward_regional_source_intake as region
from research import forward_fullstack_noorder_hub as hub
from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

SCHEMA = "fx_fwd_history_registration_v1"


def prepare(manifests: list[Path], *, asof_utc: str,
            previous_history: Path | None = None) -> tuple[dict, dict, list[Path]]:
    macro._utc(asof_utc)
    if (type(manifests) is not list or len(manifests) > history.MAX_MANIFESTS
            or any(not isinstance(p, Path) for p in manifests)):
        raise InputError("invalid explicit manifest collection")
    old = []
    original_paths = []
    if previous_history is not None:
        if not isinstance(previous_history, Path):
            raise InputError("invalid prior history")
        old_report = history.inspect(previous_history, asof_utc=asof_utc)
        if (old_report["status"] != "REGIONAL_EVIDENCE_HISTORY_RESEARCH_HOLD_NO_GO"
                or old_report["runtime_go_no_go"] != "NO_GO"
                or old_report["demo_orders_permitted"] is not False
                or old_report["real_orders_permitted"] is not False
                or old_report["safety_hold_latched"] is not True):
            raise InputError("previous research history unsafe")
        old_raw = history._verified_file(
            previous_history, history.MAX_HISTORY_BYTES)
        prior = json.loads(old_raw.decode("utf-8-sig"))
        for entry in prior["entries"]:
            path = history._entry_path(
                previous_history, entry["manifest_path"]).resolve(strict=True)
            old.append({
                "manifest_path": str(path),
                "manifest_sha256": entry["manifest_sha256"],
            })
            original_paths.append(path)
    if not old and not manifests:
        raise InputError("empty history cannot be registered")
    if len(old) + len(manifests) > history.MAX_MANIFESTS:
        raise InputError("exceeds history registration limit")
    seen = {p.resolve(strict=True) for p in original_paths}
    entries = list(old)
    for selected in manifests:
        path = selected.absolute()
        raw = history._verified_file(path, region.MAX_MANIFEST)
        resolved = path.resolve(strict=True)
        if resolved in seen or (
                previous_history is not None
                and resolved == previous_history.resolve(strict=True)):
            raise InputError("repeated or circular original manifest")
        seen.add(resolved)
        _, validation = region.load(path, asof_utc=asof_utc)
        if (validation["status"] != "REGIONAL_ORIGINAL_SOURCE_INTAKE_HOLD_NO_GO"
                or validation["runtime_go_no_go"] != "NO_GO"
                or validation["safety_hold_latched"] is not True
                or validation["demo_orders_permitted"] is not False
                or validation["real_orders_permitted"] is not False):
            raise InputError("raw source validation unsafe")
        entries.append({
            "manifest_path": str(resolved),
            "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        })
        original_paths.append(resolved)
    result = {"schema": history.SCHEMA, "entries": entries}
    serialized = json.dumps(
        result, ensure_ascii=False, indent=2,
        allow_nan=False).encode("utf-8")
    if len(serialized) > history.MAX_HISTORY_BYTES:
        raise InputError("registered file list too large")
    preview = {
        "schema": SCHEMA,
        "status": "REGIONAL_HISTORY_REGISTRATION_PRECHECK_HOLD_NO_GO",
        "registered_sources": len(entries),
        "newly_added_regional_original_manifests": len(manifests),
        "prior_history_included": previous_history is not None,
        "history_sha256_local_pin":
            hashlib.sha256(serialized).hexdigest(),
        "verified_saved_sources_only": True,
        "registered_provenance_independently_authenticated": False,
        "network_calls_this_run": 0, "API_calls_this_run": 0,
        "orders_sent_this_run": 0, "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
    }
    return result, preview, original_paths


def register(manifests: list[Path], *, asof_utc: str,
             out: Path, previous_history: Path | None = None) -> dict:
    if not isinstance(out, Path):
        raise InputError("invalid output")
    result, preview, originals = prepare(
        manifests, asof_utc=asof_utc, previous_history=previous_history)
    if out.exists() or out.is_symlink():
        raise InputError("new output file only")
    # Cannot save a new history inside any immutable original source folder.
    hub._checked_new_output(
        out, [*originals, previous_history, *(
            p.parent for p in originals)])
    # Validate strictly ordered UTC before producing the output file.
    previous_time = None
    known = {}
    for entry in result["entries"]:
        source = Path(entry["manifest_path"])
        raw = history._verified_file(source, region.MAX_MANIFEST)
        if hashlib.sha256(raw).hexdigest() != entry["manifest_sha256"]:
            raise InputError("original changed during history registration")
        payload, _ = region.load(source, asof_utc=asof_utc)
        time = macro._utc(payload["observed_at_utc"])
        if previous_time is not None and time < previous_time:
            raise InputError("history captures are out of order")
        previous_time = time
        for e in payload["events"]:
            ident = (e["currency"], e["event_id"])
            if ident in known and known[ident][0] == time and (
                    history._changes(known[ident][1], e)):
                raise InputError("conflicting same-second event revision")
            known[ident] = (time, e)
    with out.open("x", encoding="utf-8") as target:
        json.dump(result, target, ensure_ascii=False, indent=2,
                  allow_nan=False)
    try:
        audited = history.inspect(out, asof_utc=asof_utc)
    except (InputError, OSError, TypeError, ValueError,
            KeyError, UnicodeError, ArithmeticError, OverflowError):
        out.unlink()
        raise
    return {
        **preview,
        "status": "REGIONAL_HISTORY_REGISTERED_AND_RECHECKED_HOLD_NO_GO",
        "read_only_recheck_snapshot_count":
            audited["registered_snapshot_count"],
        "read_only_recheck_revision_occurrences":
            audited["recorded_revision_occurrence_count"],
        "new_history_file_written_once": True,
        "registered_source_originals_modified": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Build SHA-pinned regional history from named saved originals")
    p.add_argument("--manifest", action="append", type=Path, default=[])
    p.add_argument("--previous-history", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--asof-utc")
    a = p.parse_args(argv)
    try:
        asof = a.asof_utc or hub._now()
        if a.out is None:
            _, result, _ = prepare(
                a.manifest, asof_utc=asof,
                previous_history=a.previous_history)
            result["files_written_this_run"] = 0
        else:
            result = register(
                a.manifest, asof_utc=asof, out=a.out,
                previous_history=a.previous_history)
            result["files_written_this_run"] = 1
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "REGIONAL_HISTORY_REGISTRATION_FAIL_CLOSED_NO_GO",
            "reason_code": "INVALID_HISTORY_REGISTRATION_OR_SOURCE",
            "network_calls_this_run": 0, "API_calls_this_run": 0,
            "orders_sent_this_run": 0, "files_written_this_run": 0,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
