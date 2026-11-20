"""Re-verify the six ORIGINAL, PC-timestamped public-source bytes offline.

A local hash match proves archive consistency, not third-party publication
time, full macro coverage, point-in-time consensus or publisher identity.
No network, no paid inference, no orders, no risk-state updates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_public_source_snapshot as snapshot
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_official_archive_integrity_v1"
MAX_MANIFEST=20_000


def _when(text:str)->datetime:
    if type(text) is not str:
        raise InputError("OFFICIAL_ARCHIVE_CAPTURE_TIMESTAMP_INVALID")
    try:
        parsed=datetime.fromisoformat(text.replace("Z","+00:00"))
    except ValueError as exc:
        raise InputError("OFFICIAL_ARCHIVE_CAPTURE_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds()!=0:
        raise InputError("OFFICIAL_ARCHIVE_TIMESTAMP_NOT_UTC")
    return parsed


def audit(archive:Path)->dict:
    if (not archive.is_dir() or archive.is_symlink()
            or any(p.is_symlink() for p in archive.parents)
            or not archive.name.startswith("official_public_capture_")):
        raise InputError("OFFICIAL_ARCHIVE_ROOT_UNSAFE")
    manifest=archive/"manifest.json"
    if (not manifest.is_file() or manifest.is_symlink()
            or not 0<manifest.stat().st_size<=MAX_MANIFEST):
        raise InputError("OFFICIAL_ARCHIVE_MANIFEST_MISSING")
    raw=manifest.read_bytes()
    try:
        obj=json.loads(raw.decode("utf-8-sig"))
    except (ValueError,UnicodeError) as exc:
        raise InputError("OFFICIAL_ARCHIVE_MANIFEST_INVALID") from exc
    required={
        "schema","status","source_count","archived_count",
        "failed_source_ids","sources","source_publication_time_independently_attested",
        "all_important_usd_eur_jpy_events_covered",
        "consensus_point_in_time_verified",
        "broker_clock_independently_verified",
        "real_transaction_costs_verified",
        "new_paid_ai_calls_allowed", "new_virtual_positions_allowed",
        "demo_orders_allowed", "real_orders_allowed", "runtime_go_no_go",
    }
    expected=set(snapshot.SOURCES)
    if (type(obj) is not dict or set(obj)!=required
            or obj["schema"]!=snapshot.SCHEMA
            or obj["status"]!="PUBLIC_OFFICIAL_BYTES_ARCHIVED_NOT_ATTESTED_NO_GO"
            or obj["source_count"]!=len(expected)
            or obj["archived_count"]!=len(expected)
            or obj["failed_source_ids"]!=[]
            or type(obj["sources"]) is not list
            or len(obj["sources"])!=len(expected)
            or any(obj[field] is not False for field in (
                "source_publication_time_independently_attested",
                "all_important_usd_eur_jpy_events_covered",
                "consensus_point_in_time_verified",
                "broker_clock_independently_verified",
                "real_transaction_costs_verified",
                "new_paid_ai_calls_allowed",
                "new_virtual_positions_allowed",
                "demo_orders_allowed","real_orders_allowed"))
            or obj["runtime_go_no_go"]!="NO_GO"):
        raise InputError("OFFICIAL_ARCHIVE_MANIFEST_NOT_RESEARCH_ONLY")
    ids=set()
    digest_list=[]
    for item in obj["sources"]:
        if type(item) is not dict:
            raise InputError("OFFICIAL_ARCHIVE_SOURCE_RECORD_INVALID")
        sid=item.get("source_id")
        if (type(sid) is not str or sid not in expected or sid in ids
                or item.get("url")!=snapshot.SOURCES[sid]):
            raise InputError("OFFICIAL_ARCHIVE_SOURCE_URL_OR_ID_UNSAFE")
        ids.add(sid)
        suffix=".ics" if sid.endswith("_ics") else ".html"
        name=sid+suffix
        if item.get("archive_file")!=name:
            raise InputError("OFFICIAL_ARCHIVE_SOURCE_FILENAME_MISMATCH")
        _when(item.get("captured_at_utc_pc_unattested"))
        if (item.get("publication_authenticity_independently_attested")
                is not False or
                item.get("calendar_semantics_extracted_or_verified")
                is not False):
            raise InputError("OFFICIAL_ARCHIVE_UNSUPPORTED_ATTESTATION")
        file=archive/name
        if (not file.is_file() or file.is_symlink()
                or not 0<file.stat().st_size<=snapshot.MAX_SOURCE_BYTES):
            raise InputError("OFFICIAL_ARCHIVE_ORIGINAL_BYTES_MISSING")
        original=file.read_bytes()
        sha=hashlib.sha256(original).hexdigest()
        if (type(item.get("bytes")) is not int
                or item["bytes"]!=len(original)
                or item.get("sha256_local_only")!=sha):
            raise InputError("OFFICIAL_ARCHIVE_SOURCE_HASH_TAMPERED")
        digest_list.append({"source_id":sid,"sha256_local_only":sha,
                            "bytes":len(original)})
    if ids!=expected:
        raise InputError("OFFICIAL_ARCHIVE_SIX_SOURCES_INCOMPLETE")
    # No extra untracked files: anyone silently adding an archive file
    # must create a new independently reviewed manifest version.
    files={p.name for p in archive.iterdir() if p.is_file() and
           not p.is_symlink()}
    if files!={x["source_id"]+
               (".ics" if x["source_id"].endswith("_ics") else ".html")
               for x in digest_list}|{"manifest.json"}:
        raise InputError("OFFICIAL_ARCHIVE_UNRECORDED_FILES")
    return {
        "schema":SCHEMA,
        "status":"SIX_LOCAL_OFFICIAL_ORIGINALS_HASH_MATCH_RESEARCH_NO_GO",
        "local_manifest_sha256":hashlib.sha256(raw).hexdigest(),
        "original_source_count":len(digest_list),
        "verified_local_sha256s":sorted(digest_list,key=lambda x:x["source_id"]),
        "all_saved_bytes_locally_consistent":True,
        "source_identity_independently_attested":False,
        "source_publication_time_independently_attested":False,
        "official_future_calendar_semantics_verified":False,
        "complete_usd_eur_jpy_high_impact_calendar_verified":False,
        "pre_release_consensus_independently_verified":False,
        "broker_clock_independently_attested":False,
        "full_transaction_costs_verified":False,
        "new_paid_ai_calls_permitted":False,
        "new_virtual_positions_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Offline manifest and exact official-source hash review")
    p.add_argument("--archive",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        report=audit(args.archive)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("OFFICIAL_ARCHIVE_REPORT_UNSAFE")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False))
        return 0
    except (InputError,OSError,ValueError,TypeError,UnicodeError,
            OverflowError,KeyError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"OFFICIAL_ARCHIVE_INTEGRITY_FAIL_CLOSED_NO_GO",
            "new_paid_ai_calls_permitted":False,
            "new_virtual_positions_permitted":False,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
