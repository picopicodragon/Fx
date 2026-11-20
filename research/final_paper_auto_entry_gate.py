"""FINAL-AUTO: operator-attested, source-hash-checked, expiring entry gate.

This validator cannot independently certify that a human's source review is
true. It requires EXPLICIT human-signed assertions backed by original files,
six official byte hashes, dated NTP/broker observations, an event inventory,
and pre-release consensus. It NEVER creates the permit.

No file/permission => no signals and no external paid inference. Broker
orders are forbidden regardless of permit. An operator must review genuine
source content before approving. "attested" != cryptographically verified.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime,timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from research import final_paper_engine as paper
from research import final_paper_official_archive_integrity as official
from research import final_paper_public_source_snapshot as archive_source
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_auto_entry_evidence_v1"
APPROVAL="APPROVE_FINAL_PAPER_VIRTUAL_ENTRY_EVIDENCE_FOR_THIS_JOURNAL"
SCOPE="RAKUTEN_MT4_DEMO_INTERNAL_VIRTUAL_ONLY"
CLOCK_MAX_AGE_SECONDS=86400  # daily independent UTC proof + per-quote broker offset check
PERMIT_MAX_LIFETIME_SECONDS=86400
MAX_SOURCE_BYTES=1_000_000
SOURCES=("official_us","official_eur","official_jpy",
         "independent_utc_clock","broker_clock","pre_release_consensus",
         "cost_model","mt4_v2_experts_log")
SOURCE_IDS={
    "official_us":"us_bls_calendar_ics",
    "official_eur":"eur_ecb_calendar",
    "official_jpy":"jpy_boj_calendar",
}
HEX=re.compile(r"^[0-9a-f]{64}$")
FILENAME=re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,110}$")
CURRENCIES=("USD","EUR","JPY")
HOSTS=frozenset({
    "www.bls.gov","www.federalreserve.gov","www.bea.gov",
    "www.ecb.europa.eu","www.boj.or.jp",
})


def _utc(value:str)->int:
    if type(value) is not str:
        raise InputError("FINAL_GATE_UTC_INVALID")
    try:
        t=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise InputError("FINAL_GATE_UTC_INVALID") from exc
    if t.tzinfo is None or t.utcoffset().total_seconds()!=0:
        raise InputError("FINAL_GATE_UTC_NOT_Z")
    return int(t.timestamp())


def _positive(x:object,max_allowed:str)->Decimal:
    try:
        if type(x) is not str:
            raise ValueError
        d=Decimal(x)
        if not d.is_finite() or not Decimal("0")<d<=Decimal(max_allowed):
            raise ValueError
        return d
    except (ValueError,InvalidOperation):
        raise InputError("FINAL_GATE_CONSERVATIVE_COST_INVALID") from None


def _original(file:Path, expected_sha:str, *, max_bytes:int=MAX_SOURCE_BYTES)->None:
    if (type(expected_sha) is not str or HEX.fullmatch(expected_sha) is None
            or not file.is_file() or file.is_symlink()
            or any(parent.is_symlink() for parent in file.parents)
            or not 0<file.stat().st_size<=max_bytes):
        raise InputError("FINAL_GATE_SOURCE_MISSING_OR_UNSAFE")
    if hashlib.sha256(file.read_bytes()).hexdigest()!=expected_sha:
        raise InputError("FINAL_GATE_ORIGINAL_SHA_MISMATCH")


def _manifest(permit:Path)->tuple[dict,str]:
    if (not permit.is_file() or permit.is_symlink()
            or any(p.is_symlink() for p in permit.parents)
            or not 0<permit.stat().st_size<=30000):
        raise InputError("FINAL_GATE_PERMIT_ABSENT")
    raw=permit.read_bytes()
    try:
        data=json.loads(raw.decode("utf-8-sig"))
    except (ValueError,UnicodeError) as exc:
        raise InputError("FINAL_GATE_PERMIT_JSON_INVALID") from exc
    if (type(data) is not dict or set(data)!={
            "schema","scope","operator_approval","approved_at_utc",
            "expires_at_utc","bound_journal_sha256","official_archive_manifest_sha256",
            "sources","clock","calendar","consensus","cost","mt4","human_evidence_review"}
            or data["schema"]!=SCHEMA or data["scope"]!=SCOPE
            or data["operator_approval"]!=APPROVAL
            or data["human_evidence_review"] is not True):
        raise InputError("FINAL_GATE_OPERATOR_REVIEW_REQUIRED")
    return data,hashlib.sha256(raw).hexdigest()


def evaluate(permit:Path,official_archive:Path,quote:dict,
             *,now:datetime,entry_binding_sha:str)->dict:
    if (now.tzinfo is None or now.utcoffset().total_seconds()!=0
            or type(entry_binding_sha) is not str
            or HEX.fullmatch(entry_binding_sha) is None):
        raise InputError("FINAL_GATE_CLOCK_OR_SESSION_BINDING_INVALID")
    data,sha=_manifest(permit)
    current=int(now.timestamp())
    approved=_utc(data["approved_at_utc"])
    expires=_utc(data["expires_at_utc"])
    if (not 0<=current-approved<=PERMIT_MAX_LIFETIME_SECONDS
            or not approved<expires<=approved+PERMIT_MAX_LIFETIME_SECONDS
            or current>expires
            or data["bound_journal_sha256"]!=entry_binding_sha):
        raise InputError("FINAL_GATE_PERMIT_EXPIRED_OR_WRONG_SESSION")
    verified=official.audit(official_archive)
    if (verified["original_source_count"]!=6
            or verified["local_manifest_sha256"]!=
                data["official_archive_manifest_sha256"]):
        raise InputError("FINAL_GATE_OFFICIAL_ORIGINALS_CHANGED")
    original_by_id={s["source_id"]:s["sha256_local_only"]
                    for s in verified["verified_local_sha256s"]}
    files=data["sources"]
    if (type(files) is not dict or set(files)!=set(SOURCES)):
        raise InputError("FINAL_GATE_SOURCE_SET_INCOMPLETE")
    if len({x.get("filename") for x in files.values() if type(x) is dict})!=len(SOURCES):
        raise InputError("FINAL_GATE_DISTINCT_SOURCE_FILES_REQUIRED")
    for name,meta in files.items():
        if (type(meta) is not dict or set(meta)!={"filename","sha256"}
                or type(meta["filename"]) is not str
                or not FILENAME.fullmatch(meta["filename"])):
            raise InputError("FINAL_GATE_SOURCE_PATH_UNSAFE")
        if name in SOURCE_IDS:
            source_id=SOURCE_IDS[name]
            ext=".ics" if source_id.endswith("_ics") else ".html"
            expected_name=source_id+ext
            if (meta["filename"]!=expected_name
                    or meta["sha256"]!=original_by_id.get(source_id)):
                raise InputError("FINAL_GATE_OFFICIAL_SOURCE_REF_MISMATCH")
            original=official_archive/expected_name
        else:
            # No absolute paths or ..; permit-local evidence must already
            # exist, remain immutable and carry a pinned original SHA.
            original=permit.parent/meta["filename"]
        _original(original,meta["sha256"])
    mt4_proof=data["mt4"]
    if (type(mt4_proof) is not dict or set(mt4_proof)!={
            "build_tag","demo_account_verified","single_observer_verified",
            "metaeditor_zero_compile_errors_verified"}
            or mt4_proof["build_tag"]!=
                "FXPAPER-CLOCKFREEZE-20261120-V2"
            or any(mt4_proof[name] is not True for name in (
                "demo_account_verified","single_observer_verified",
                "metaeditor_zero_compile_errors_verified"))):
        raise InputError("FINAL_GATE_MT4_V2_COMPILATION_OR_SINGLE_EA_UNATTESTED")
    logfile=permit.parent/files["mt4_v2_experts_log"]["filename"]
    if b"FXPAPER-CLOCKFREEZE-20261120-V2" not in logfile.read_bytes():
        raise InputError("FINAL_GATE_MT4_BUILD_LOG_MARKER_MISSING")
    clock=data["clock"]
    if (type(clock) is not dict or set(clock)!={
            "independent_utc_checked_at","broker_utc_checked_at",
            "pc_utc_offset_seconds","broker_utc_offset_seconds",
            "expected_broker_minus_pc_seconds",
            "external_utc_source_checked","broker_time_independently_reviewed"}
            or clock["external_utc_source_checked"] is not True
            or clock["broker_time_independently_reviewed"] is not True):
        raise InputError("FINAL_GATE_CLOCK_ATTESTATION_ABSENT")
    checked_utc=_utc(clock["independent_utc_checked_at"])
    checked_broker=_utc(clock["broker_utc_checked_at"])
    if not all(0<=current-stamp<=CLOCK_MAX_AGE_SECONDS
               for stamp in (checked_utc,checked_broker)):
        raise InputError("FINAL_GATE_CLOCK_EVIDENCE_STALE")
    try:
        pc_offset=Decimal(str(clock["pc_utc_offset_seconds"]))
        broker_offset=Decimal(str(clock["broker_utc_offset_seconds"]))
    except (InvalidOperation,TypeError,ValueError):
        raise InputError("FINAL_GATE_CLOCK_OFFSET_INVALID") from None
    if (not pc_offset.is_finite() or not broker_offset.is_finite()
            or abs(pc_offset)>Decimal("2")
            or abs(broker_offset)>Decimal("2")
            or type(clock["expected_broker_minus_pc_seconds"]) is not int
            or clock["expected_broker_minus_pc_seconds"] not in (
                -18000,-14400,-10800,-7200,-3600,0,3600,7200,10800,14400,18000)):
        raise InputError("FINAL_GATE_CLOCK_OFFSET_TOO_LARGE")
    # A daily NTP check alone cannot guard a subsequent 60s quote;
    # the observed MT4-PC offset is also verified on every fresh source.
    # MetaQuotes server clock is NOT independently authenticated by this.
    csv_path=quote.get("source_original_file")
    if csv_path is None:
        raise InputError("FINAL_GATE_ORIGINAL_QUOTE_REQUIRED")
    if csv_path is not None:
        from research import final_paper_engine as engine
        if not isinstance(csv_path,Path) or not csv_path.is_file():
            raise InputError("FINAL_GATE_QUOTE_FILE_MISSING")
        import csv
        try:
            raw=csv.DictReader(csv_path.read_text("utf-8-sig").splitlines())
            rows=list(raw)
            expected=clock["expected_broker_minus_pc_seconds"]
            if len(rows)!=3 or any(
                    abs(int(row["broker_time_epoch_unattested"])-
                        int(row["capture_epoch_utc_pc"])-expected)>2
                    for row in rows):
                raise InputError("FINAL_GATE_BROKER_PC_OFFSET_CHANGED")
        except (OSError,UnicodeError,ValueError,TypeError,KeyError):
            raise InputError("FINAL_GATE_BROKER_PC_OFFSET_UNREADABLE") from None
    calendar=data["calendar"]
    if (type(calendar) is not dict or set(calendar)!={
            "coverage_start_utc","coverage_until_utc","covered_currencies",
            "events","reviewed_no_missing_high_impact_events"}
            or calendar["reviewed_no_missing_high_impact_events"] is not True
            or calendar["covered_currencies"]!=list(CURRENCIES)):
        raise InputError("FINAL_GATE_CALENDAR_COVERAGE_UNATTESTED")
    start=_utc(calendar["coverage_start_utc"])
    end=_utc(calendar["coverage_until_utc"])
    if not (start<=current<=end-3600 and end-start<=7*86400):
        raise InputError("FINAL_GATE_CALENDAR_NOT_COVERING_NEXT_HOUR")
    events=calendar["events"]
    if type(events) is not list or len(events)>100:
        raise InputError("FINAL_GATE_EVENT_INVENTORY_INVALID")
    blackout=False
    ids=set()
    qepoch=quote.get("capture_epoch")
    if type(qepoch) is not int or not 0<=current-qepoch<=120:
        raise InputError("FINAL_GATE_QUOTE_NOT_FRESH")
    for event in events:
        if (type(event) is not dict or set(event)!={
                "id","currency","release_utc","importance","source_url",
                "original_source_id"}
                or type(event["id"]) is not str
                or not 1<=len(event["id"])<=100
                or event["id"] in ids
                or event["currency"] not in CURRENCIES
                or event["importance"] not in ("HIGH","CRITICAL")
                or event["original_source_id"] not in SOURCE_IDS.values()):
            raise InputError("FINAL_GATE_EVENT_INVALID")
        ids.add(event["id"])
        url=event["source_url"]
        if type(url) is not str:
            raise InputError("FINAL_GATE_EVENT_URL_UNSAFE")
        parsed=urlparse(url)
        if (parsed.scheme!="https" or parsed.hostname not in HOSTS
                or parsed.username or parsed.password or parsed.port is not None):
            raise InputError("FINAL_GATE_EVENT_URL_NOT_OFFICIAL")
        epoch=_utc(event["release_utc"])
        expected_by_currency={
            "USD":{"us_bls_calendar_ics"},
            "EUR":{"eur_ecb_calendar"},
            "JPY":{"jpy_boj_calendar"},
        }
        if event["original_source_id"] not in expected_by_currency[
                event["currency"]]:
            raise InputError("FINAL_GATE_EVENT_ORIGINAL_CURRENCY_MISMATCH")
        if not start<=epoch<=end:
            raise InputError("FINAL_GATE_EVENT_OUTSIDE_CALENDAR")
        if abs(qepoch-epoch)<=900:
            blackout=True
    consensus=data["consensus"]
    if (type(consensus) is not dict or set(consensus)!={
            "source_captured_at_utc","forecast_available_before_release",
            "source_originals_reviewed"}
            or consensus["forecast_available_before_release"] is not True
            or consensus["source_originals_reviewed"] is not True
            or not 0<=current-_utc(consensus["source_captured_at_utc"])<=72*3600):
        raise InputError("FINAL_GATE_POINT_IN_TIME_CONSENSUS_UNVERIFIED")
    costs=data["cost"]
    if (type(costs) is not dict or set(costs)!={
            "max_spread_pips","worst_case_swap_jpy_per_lot_per_day",
            "model_exit_slippage_pips_per_side",
            "swap_and_slippage_research_reviewed"}
            or costs["swap_and_slippage_research_reviewed"] is not True
            or costs["model_exit_slippage_pips_per_side"]!="1.0"):
        raise InputError("FINAL_GATE_TRANSACTION_MODEL_UNVERIFIED")
    spread={}
    carries={}
    if (type(costs["max_spread_pips"]) is not dict
            or set(costs["max_spread_pips"])!=set(paper.PAIRS)
            or type(costs["worst_case_swap_jpy_per_lot_per_day"]) is not dict
            or set(costs["worst_case_swap_jpy_per_lot_per_day"])!=set(paper.PAIRS)):
        raise InputError("FINAL_GATE_COST_PAIR_SET_INCOMPLETE")
    for pair in paper.PAIRS:
        max_spread=_positive(costs["max_spread_pips"][pair],"25")
        q=quote["quotes"][pair]
        observed=(q["ask"]-q["bid"])/paper.PIP[pair]
        if observed>max_spread:
            raise InputError("FINAL_GATE_OBSERVED_SPREAD_ABOVE_LIMIT")
        per=costs["worst_case_swap_jpy_per_lot_per_day"][pair]
        if type(per) is not dict or set(per)!={"LONG","SHORT"}:
            raise InputError("FINAL_GATE_SWAP_DIRECTION_MISSING")
        carries[pair]={direction:str(_positive(per[direction],"100000"))
                       for direction in ("LONG","SHORT")}
        spread[pair]=str(max_spread)
    return {
        "status":"FINAL_PAPER_OPERATOR_ATTESTED_SOURCES_REVIEWED",
        "permit_sha256_local_only":sha,
        "session_bound_journal_head_sha256":entry_binding_sha,
        "known_event_blackout_active":blackout,
        "entry_evidence_ready_by_operator_attestation":not blackout,
        "carry_costs_jpy_per_lot_day":carries,
        "observed_spread_within_operator_ceiling":True,
        "full_independent_publication_authenticity_proven_by_code":False,
        "publisher_calendar_completeness_proven_by_code":False,
        "broker_orders_permitted":False,
    }
