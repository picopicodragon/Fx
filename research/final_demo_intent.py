"""Demo-only end-to-end bridge: verified local AI research -> short-lived intent.

This is an explicit one-cycle handoff, not an autonomous service. No MT4 or
broker login, no API calls and no actual order from Python. The separate
MQL4 EA must independently enforce demo-only and risk checks before any
DEMO order. Research evidence is not independently source-authenticated.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from research import forward_ai_shadow as ai
from research import forward_macro_two_model_gate as macro_gate
from research import forward_observation as obs
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_final_demo_intent_handoff_v1"
FILE_NAME = "FxDemoIntent_v1.csv"
PAIR_SYMBOLS = {"USD/JPY": "USDJPY", "EUR/JPY": "EURJPY", "EUR/USD": "EURUSD"}
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_EVENT_AGE = timedelta(hours=2)
EXPIRY_SECONDS = 90


def _utc(when: datetime) -> datetime:
    if not isinstance(when, datetime) or when.tzinfo is None:
        raise InputError("aware UTC clock required")
    return when.astimezone(timezone.utc).replace(microsecond=0)


def _approved_review_in_journal(store: Path, event_sha: str,
                                state: dict, pair: str) -> bool:
    """Require a linked hypothesis and review in the audited local log."""
    audited = obs.audit(store)
    count = audited["record_count"]
    if type(count) is not int or count < 2:
        return False
    hypotheses = set()
    for number in range(1, count + 1):
        row = json.loads((store / f"{number:08d}.json").read_text(
            encoding="utf-8-sig"))
        item = row["snapshot"]
        body = item["payload"]
        if item["kind"] == "MACRO_HYPOTHESIS":
            if (body["basis_sha256"] == event_sha and
                    body["pair"] == pair and
                    body["model_id"] == state["analyst_model"] and
                    body["direction"] == state["analyst"]["action"] and
                    body["thesis"] == state["analyst"]["hypothesis"] and
                    body["counterevidence"] == state["analyst"]["counterevidence"] and
                    body["research_only"] is True):
                hypotheses.add(row["record_sha256"])
        elif item["kind"] == "INDEPENDENT_REVIEW":
            if (body["review_of_sha256"] in hypotheses
                    and body["pair"] == pair
                    and body["model_id"] == state["reviewer_model"]
                    and body["verdict"] == "APPROVED"
                    and body["rationale"] == state["reviewer"]["rationale"]
                    and body["research_only"] is True):
                return True
    return False


def inspect(store: Path, event_sha: str, ledger_path: Path, *,
            account_number: int, now: datetime | None = None) -> dict:
    """Fail closed on stale, unsigned-local, missing or disagreeing AI evidence."""
    now = _utc(now if now is not None else datetime.now(timezone.utc))
    if (type(account_number) is not int or not 1 <= account_number <= 999999999
            or type(event_sha) is not str or not SHA.fullmatch(event_sha)
            or not isinstance(ledger_path, Path) or ledger_path.is_symlink()
            or any(p.is_symlink() for p in ledger_path.parents)
            or not ledger_path.is_file()
            or not 0 < ledger_path.stat().st_size <= 200_000):
        raise InputError("invalid demo account or ledger path")
    audited = obs.audit(store)
    if (audited["runtime_go_no_go"] != "NO_GO"
            or not audited["safety_hold_latched"]):
        raise InputError("observation safety controls changed")
    event = ai._event(store, event_sha)
    body = event["payload"]
    source = event["source_id"]
    if source == "macro_joined":
        if (not body["consensus"].strip()
                or not body["released_value"].strip()
                or macro_gate.EVIDENCE_HASH_PATTERN.search(
                    body["content"]) is None):
            raise InputError("joined macro source/consensus/actual absent")
    elif source == "fed_policy":
        # A policy news article is NOT a quantitative economic surprise.
        # This path is DEMO-only and requires an independent model review.
        link = urlsplit(body["source_url"])
        if (link.scheme != "https"
                or link.hostname != "www.federalreserve.gov"
                or link.username is not None or link.password is not None
                or link.port not in (None, 443)
                or not link.path.startswith("/")
                or link.path.startswith("//")
                or link.fragment):
            raise InputError("invalid official policy source link")
    else:
        raise InputError("news without reviewed macro source unsupported")
    observed = timestamp(event["observed_at_utc"])
    published = timestamp(body["published_at_utc"])
    if (not published <= observed <= now or now-observed > MAX_EVENT_AGE
            or (source == "fed_policy" and now - published > MAX_EVENT_AGE)):
        raise InputError("unusable or stale event chronology")
    if event["payload"]["pair"] not in PAIR_SYMBOLS:
        raise InputError("unsupported trade pair")
    state = json.loads(ledger_path.read_text(encoding="utf-8-sig"))
    if (type(state) is not dict or
            type(state.get("analyst_model")) is not str or
            type(state.get("reviewer_model")) is not str):
        raise InputError("missing model provenance")
    base = ai._base(event_sha, ai.packet(event),
                    state["analyst_model"], state["reviewer_model"])
    ai._valid(state, base)
    if (state["stage"] != "COMPLETE"
            or state["pending_request"] is not None
            or state["published_to_observation"] is not True
            or state["reviewer"]["verdict"] != "APPROVED"
            or state["analyst"]["action"] not in ("LONG", "SHORT")):
        raise InputError("macro AI analysis is not completed and approved")
    if not _approved_review_in_journal(
            store, event_sha, state, body["pair"]):
        raise InputError("approved AI review not linked in journal")
    # No automatic conversion of a trade opinion into a live permission.
    symbol = PAIR_SYMBOLS[body["pair"]]
    side = "BUY" if state["analyst"]["action"] == "LONG" else "SELL"
    issued = int(now.timestamp())
    return {
        "schema": SCHEMA,
        "status": "DEMO_INTENT_CANDIDATE_VALIDATED_NOT_EXECUTED",
        "event_sha256": event_sha,
        "symbol": symbol,
        "side": side,
        "issued_epoch_utc_local_clock_unattested": issued,
        "expires_epoch_utc_local_clock_unattested": issued + EXPIRY_SECONDS,
        "analyst_model": state["analyst_model"],
        "reviewer_model": state["reviewer_model"],
        "demo_only": True,
        "source_authenticity_independently_attested": False,
        "technical_gate_and_broker_risk_must_pass_inside_mt4": True,
        "orders_sent_this_run": 0,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def write_demo_intent(target_dir: Path, decision: dict, *,
                      account_number: int) -> Path:
    """Atomic single-file handoff to an EXPLICITLY selected MT4 Files folder."""
    if (not isinstance(target_dir, Path) or not target_dir.is_dir()
            or target_dir.is_symlink()
            or any(p.is_symlink() for p in target_dir.parents)):
        raise InputError("unsafe terminal Files folder")
    target = target_dir / FILE_NAME
    if target.is_symlink():
        raise InputError("symlink intent path prohibited")
    # All fields are bounded and plain ASCII. Full SHA ties replay to event.
    values = ["FXDEMO1", str(account_number), decision["event_sha256"],
              str(decision["issued_epoch_utc_local_clock_unattested"]),
              str(decision["expires_epoch_utc_local_clock_unattested"]),
              decision["symbol"], decision["side"], decision["event_sha256"]]
    if (not all(type(v) is str and len(v) <= 64 and
                re.fullmatch(r"[a-zA-Z0-9_]+", v) for v in values)):
        raise InputError("invalid demo file fields")
    buf = io.StringIO(newline="")
    csv.writer(buf, lineterminator="\n").writerow(values)
    data = buf.getvalue()
    if len(data) > 400:
        raise InputError("unsafe demo handoff size")
    temp = target_dir / (".FxDemoIntent_v1_" + secrets.token_hex(10) + ".tmp")
    try:
        with temp.open("x", encoding="ascii", newline="") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if target.is_symlink():
            raise InputError("intent path replaced with symlink")
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return target


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Explicit DEMO-only AI intent; no live orders")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--event-sha256", required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--expected-demo-account", type=int, required=True)
    p.add_argument("--terminal-files", type=Path)
    p.add_argument("--operator-enable-demo-intent", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.operator_enable_demo_intent != bool(args.terminal_files):
            raise InputError("explicit demo opt-in and target folder must agree")
        result = inspect(args.store, args.event_sha256, args.ledger,
                         account_number=args.expected_demo_account)
        if args.operator_enable_demo_intent:
            write_demo_intent(args.terminal_files, result,
                              account_number=args.expected_demo_account)
            result["status"] = "DEMO_INTENT_WRITTEN_LOCAL_ONLY"
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, ValueError, KeyError, TypeError, OSError,
            UnicodeError, OverflowError, ArithmeticError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "DEMO_INTENT_FAIL_CLOSED_NO_GO",
            "orders_sent_this_run": 0,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
