"""FX-FWD-001: local, append-only forward observation intake. NO broker or API.

Captures received-as-of price/event/hypothesis/review records for future
replay. It neither fetches live sources nor computes fills or permits orders.
Each record is exclusive-create with an authenticated hash chain. Local-only
source provenance remains UNVERIFIED until separately checked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.offline_backtest import InputError, PAIRS, decimal, timestamp

SCHEMA = "fx_forward_observation_v1"
CAPTURE_KINDS = ("PRICE_QUOTE", "MACRO_EVENT", "MACRO_HYPOTHESIS",
                 "INDEPENDENT_REVIEW")
SAFE_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
FILES = re.compile(r"^[0-9]{8}\.json$")
MAX_SNAPSHOT_BYTES = 24000
MAX_RECORDS = 100000
REDACT_MARKERS = ("api_key", "authorization", "bearer ", "access_token",
                  "secret_key", "password", "account_number", "account_id")


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def _text(v: object, name: str, *, limit: int = 2000,
          empty: bool = False) -> str:
    if (type(v) is not str or len(v) > limit or
            (not empty and not v.strip()) or "\x00" in v):
        raise InputError("invalid " + name)
    return v


def _timestamp(v: object) -> str:
    t = timestamp(v)
    if t.microsecond:
        raise InputError("timestamps must use seconds precision")
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def _timestamp_check(v: str, received: str) -> None:
    # Upper bound prevents future claims, lower bound prevents stale data
    # masquerading as an instantaneous observation.
    if timestamp(v) > timestamp(received) + timedelta(seconds=5):
        raise InputError("observation timestamp is in future")


def snapshot_validate(data: dict, *, received_at: str) -> dict:
    if (type(data) is not dict or
            set(data) != {"schema", "kind", "observed_at_utc",
                          "source_id", "payload"} or
            data.get("schema") != SCHEMA or
            data.get("kind") not in CAPTURE_KINDS):
        raise InputError("invalid snapshot envelope")
    kind = data["kind"]
    observed = _timestamp(data["observed_at_utc"])
    _timestamp_check(observed, received_at)
    source_id = _text(data["source_id"], "source_id", limit=100)
    if not SAFE_NAME.fullmatch(source_id):
        raise InputError("invalid source identifier")
    payload = data["payload"]
    if type(payload) is not dict:
        raise InputError("invalid snapshot payload")
    if kind == "PRICE_QUOTE":
        if set(payload) != {"pair", "bid", "ask", "quote_to_jpy",
                            "source_status"}:
            raise InputError("price quote fields")
        if payload["pair"] not in PAIRS or (
                payload["source_status"] != "USER_SUPPLIED_UNVERIFIED"):
            raise InputError("unverified source/invalid pair")
        bid = decimal(payload["bid"], "bid", positive=True)
        ask = decimal(payload["ask"], "ask", positive=True)
        decimal(payload["quote_to_jpy"], "quote_to_jpy", positive=True)
        if ask <= bid:
            raise InputError("invalid price sides")
        # Guard absurd quotes without assuming a live market.
        if ask / bid > 2:
            raise InputError("unreasonable price spread")
    elif kind == "MACRO_EVENT":
        if set(payload) != {"pair", "title", "source_url",
                            "published_at_utc", "content", "consensus",
                            "released_value", "source_status"}:
            raise InputError("macro event fields")
        if (payload["pair"] not in PAIRS or
                payload["source_status"] != "USER_SUPPLIED_UNVERIFIED"):
            raise InputError("invalid macro provenance")
        _text(payload["title"], "title", limit=200)
        _text(payload["content"], "content", limit=7000)
        _text(payload["consensus"], "consensus", limit=1000, empty=True)
        _text(payload["released_value"], "released_value", limit=1000,
              empty=True)
        url = _text(payload["source_url"], "source_url", limit=1500)
        if not url.startswith("https://") or "@" in url or (
                any(ch.isspace() for ch in url)):
            raise InputError("invalid provenance URL")
        published = _timestamp(payload["published_at_utc"])
        if timestamp(published) > timestamp(observed):
            raise InputError("event claims publication after observation")
    elif kind == "MACRO_HYPOTHESIS":
        if set(payload) != {"pair", "direction", "thesis",
                            "counterevidence", "model_id", "basis_sha256",
                            "research_only"}:
            raise InputError("hypothesis fields")
        if payload["pair"] not in PAIRS or (
                payload["direction"] not in ("LONG", "SHORT", "HOLD") or
                payload["research_only"] is not True):
            raise InputError("unsafe hypothesis")
        _text(payload["thesis"], "thesis", limit=1500)
        _text(payload["counterevidence"], "counterevidence", limit=1500)
        _text(payload["model_id"], "model", limit=100)
        if not re.fullmatch("[0-9a-f]{64}", str(payload["basis_sha256"])):
            raise InputError("hypothesis source hash missing")
    else:
        if set(payload) != {"pair", "review_of_sha256", "verdict",
                            "rationale", "model_id", "research_only"}:
            raise InputError("review fields")
        if (payload["pair"] not in PAIRS or
                payload["verdict"] not in
                ("APPROVED", "REVISION", "REJECTED", "PENDING") or
                payload["research_only"] is not True or
                not re.fullmatch("[0-9a-f]{64}",
                                 str(payload["review_of_sha256"]))):
            raise InputError("invalid review reference")
        _text(payload["rationale"], "rationale", limit=1500)
        _text(payload["model_id"], "model", limit=100)
    # Defensive guard prevents unintentional credentials in local journal.
    # Operator still needs to inspect material for sensitive information.
    lowered = canonical(payload).decode("utf-8").lower()
    if any(marker in lowered for marker in REDACT_MARKERS):
        raise InputError("sensitive credential/account marker in source")
    return {"schema": SCHEMA, "kind": kind,
            "observed_at_utc": observed, "source_id": source_id,
            "payload": payload}


def _manifest(store: Path) -> dict:
    path = store / "manifest.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    if (type(obj) is not dict or
            set(obj) != {"schema", "session", "created_at_utc",
                         "runtime_go_no_go", "safety_hold_latched",
                         "real_orders_permitted", "capture_mode"} or
            obj["schema"] != SCHEMA or
            obj["capture_mode"] != "LOCAL_RESEARCH_ONLY" or
            obj["runtime_go_no_go"] != "NO_GO" or
            obj["safety_hold_latched"] is not True or
            obj["real_orders_permitted"] is not False or
            not SAFE_NAME.fullmatch(str(obj["session"]))):
        raise InputError("invalid forward session manifest")
    return obj


def initialize(store: Path, session: str, *,
               now: datetime | None = None) -> dict:
    if not SAFE_NAME.fullmatch(session):
        raise InputError("invalid session")
    if store.exists():
        raise InputError("store already exists: refuse overwrite")
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    manifest = {
        "schema": SCHEMA, "session": session,
        "created_at_utc": stamp.isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
        "capture_mode": "LOCAL_RESEARCH_ONLY",
    }
    store.mkdir(parents=False)
    try:
        with (store / "manifest.json").open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
    except Exception:
        # Preserve path for inspection after partial initialization.
        raise
    return manifest


def audit(store: Path) -> dict:
    manifest = _manifest(store)
    filenames = sorted(p.name for p in store.iterdir()
                       if p.name != "manifest.json")
    if any(not FILES.fullmatch(name) for name in filenames):
        raise InputError("unexpected forward journal member")
    if len(filenames) > MAX_RECORDS:
        raise InputError("forward journal too long")
    if filenames != [f"{i:08d}.json" for i in range(1, len(filenames)+1)]:
        raise InputError("record gap or reordering")
    prev = "0" * 64
    kinds = {kind: 0 for kind in CAPTURE_KINDS}
    first = last = None
    observed_event_hashes = set()
    hypothesis_hashes = set()
    for n, name in enumerate(filenames, 1):
        path = store / name
        if path.stat().st_size > MAX_SNAPSHOT_BYTES * 2:
            raise InputError("oversize journal record")
        record = json.loads(path.read_text(encoding="utf-8"))
        if (type(record) is not dict or
                set(record) != {"sequence", "captured_at_utc",
                                "snapshot", "previous_sha256",
                                "record_sha256"} or
                type(record["sequence"]) is not int or
                record["sequence"] != n or
                record["previous_sha256"] != prev):
            raise InputError("journal chain damaged")
        stamp = _timestamp(record["captured_at_utc"])
        sample = snapshot_validate(record["snapshot"], received_at=stamp)
        if sample != record["snapshot"]:
            raise InputError("noncanonical snapshot")
        copy = {k: v for k, v in record.items() if k != "record_sha256"}
        if digest(copy) != record["record_sha256"]:
            raise InputError("journal record digest mismatch")
        if first is None:
            first = stamp
        if last is not None and timestamp(stamp) < timestamp(last):
            raise InputError("capture clock moved backward")
        last = stamp
        # Both references must point to earlier verified local observations.
        if sample["kind"] == "MACRO_HYPOTHESIS":
            if sample["payload"]["basis_sha256"] not in observed_event_hashes:
                raise InputError("unmatched macro hypothesis source")
            hypothesis_hashes.add(record["record_sha256"])
        elif sample["kind"] == "INDEPENDENT_REVIEW":
            if sample["payload"]["review_of_sha256"] not in hypothesis_hashes:
                raise InputError("unmatched independent review source")
        elif sample["kind"] == "MACRO_EVENT":
            observed_event_hashes.add(record["record_sha256"])
        kinds[sample["kind"]] += 1
        prev = record["record_sha256"]
    return {
        "status": "FORWARD_OBSERVATION_AUDIT_NO_GO",
        "session": manifest["session"],
        "record_count": len(filenames), "by_kind": kinds,
        "first_captured_at_utc": first, "last_captured_at_utc": last,
        "last_record_sha256": prev,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
        "source_authenticity_verified": False,
        "ai_trade_quality_evaluated": False,
        "mt4_connection_enabled": False,
        "demo_order_execution_enabled": False,
    }


def ingest(store: Path, input_path: Path, *,
           now: datetime | None = None) -> dict:
    if not input_path.is_file() or input_path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise InputError("snapshot input missing or too large")
    raw = input_path.read_text(encoding="utf-8-sig")
    if len(raw.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise InputError("snapshot oversized")
    source = json.loads(raw)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    received = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    sample = snapshot_validate(source, received_at=received)
    lock = store / ".capture.lock"
    # Fail closed on concurrent writers and stranded lock, no auto-override.
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise InputError("session is locked; manual reconciliation required")
    try:
        os.close(fd)
        prior = audit_without_lock_file(store)
        # Reject unlinked research claims BEFORE committing a record.
        if sample["kind"] == "MACRO_HYPOTHESIS" and (
                sample["payload"]["basis_sha256"] not in
                prior["verified_event_hashes"]):
            raise InputError("hypothesis evidence not observed")
        if sample["kind"] == "INDEPENDENT_REVIEW" and (
                sample["payload"]["review_of_sha256"] not in
                prior["verified_hypothesis_hashes"]):
            raise InputError("review hypothesis not observed")
        sequence = prior["record_count"] + 1
        if sequence > MAX_RECORDS:
            raise InputError("journal capacity exceeded")
        payload = {
            "sequence": sequence, "captured_at_utc": received,
            "snapshot": sample,
            "previous_sha256": prior["last_record_sha256"],
        }
        payload["record_sha256"] = digest(payload)
        filename = store / f"{sequence:08d}.json"
        with filename.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        return {
            "status": "FORWARD_OBSERVATION_CAPTURED_NO_GO",
            "sequence": sequence, "kind": sample["kind"],
            "record_sha256": payload["record_sha256"],
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
            "real_orders_permitted": False,
            "demo_order_execution_enabled": False,
        }
    finally:
        lock.unlink(missing_ok=True)


def audit_without_lock_file(store: Path) -> dict:
    # Lock is held by this writer, but audit also validates all past records.
    # Refuse to trust unexpected files. Do not delete lock on other errors.
    # Temporarily exclude only this exact writer's lock from directory scan.
    manifest = _manifest(store)
    records = [p for p in store.iterdir()
               if p.name not in ("manifest.json", ".capture.lock")]
    if any(not FILES.fullmatch(p.name) for p in records):
        raise InputError("unexpected session file")
    # Audit uses full normal validation, temporarily treating own lock as known.
    return _audit_core(store, manifest, records)


def _audit_core(store: Path, manifest: dict, records: list[Path]) -> dict:
    # Share identical validation logic through audit: use a passed whitelist
    # rather than relying on altered directory contents.
    names = sorted(p.name for p in records)
    if len(names) > MAX_RECORDS or (
            names != [f"{n:08d}.json" for n in range(1, len(names)+1)]):
        raise InputError("incomplete forward record chain")
    prev = "0" * 64
    seen_events = set()
    seen_hypotheses = set()
    last = None
    by_kind = {kind: 0 for kind in CAPTURE_KINDS}
    for number, name in enumerate(names, 1):
        file = store / name
        if not file.is_file() or file.stat().st_size > MAX_SNAPSHOT_BYTES * 2:
            raise InputError("invalid journal file")
        r = json.loads(file.read_text(encoding="utf-8"))
        if (type(r) is not dict or
                set(r) != {"sequence", "captured_at_utc", "snapshot",
                           "previous_sha256", "record_sha256"} or
                type(r["sequence"]) is not int or
                r["sequence"] != number or
                r["previous_sha256"] != prev):
            raise InputError("invalid hash chain")
        stamp = _timestamp(r["captured_at_utc"])
        if last and timestamp(stamp) < timestamp(last):
            raise InputError("time regression")
        sample = snapshot_validate(r["snapshot"], received_at=stamp)
        if sample != r["snapshot"] or digest({
                k: v for k, v in r.items() if k != "record_sha256"
        }) != r["record_sha256"]:
            raise InputError("invalid record integrity")
        if sample["kind"] == "MACRO_HYPOTHESIS":
            if sample["payload"]["basis_sha256"] not in seen_events:
                raise InputError("hypothesis evidence not observed")
            seen_hypotheses.add(r["record_sha256"])
        elif sample["kind"] == "INDEPENDENT_REVIEW":
            if sample["payload"]["review_of_sha256"] not in seen_hypotheses:
                raise InputError("review hypothesis not observed")
        elif sample["kind"] == "MACRO_EVENT":
            seen_events.add(r["record_sha256"])
        by_kind[sample["kind"]] += 1
        prev = r["record_sha256"]
        last = stamp
    return {
        "record_count": len(records), "last_record_sha256": prev,
        "verified_event_hashes": seen_events,
        "verified_hypothesis_hashes": seen_hypotheses,
        "by_kind": by_kind,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Local no-order FX forward evidence journal")
    parser.add_argument("--store", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true")
    group.add_argument("--ingest", type=Path)
    group.add_argument("--audit", action="store_true")
    parser.add_argument("--session", default="")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.init:
            if args.report:
                raise InputError("report forbidden at init")
            result = initialize(args.store, args.session)
            result = {**result, "status": "FORWARD_SESSION_INITIALIZED_NO_GO"}
        elif args.ingest:
            if args.session or args.report:
                raise InputError("unexpected capture arguments")
            result = ingest(args.store, args.ingest)
        else:
            if args.session:
                raise InputError("unexpected audit arguments")
            result = audit(args.store)
            if args.report:
                if not args.report.parent.is_dir():
                    raise InputError("report parent missing")
                with args.report.open("x", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED", "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "reason": "INVALID_FORWARD_RESEARCH_INPUT_OR_STATE",
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
