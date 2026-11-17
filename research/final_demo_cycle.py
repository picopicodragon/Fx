"""One explicit forward DEMO cycle: recent macro event -> two AI models ->
published review -> demo-only MT4 intent. Never sends orders itself.

Optional API calls require an explicit opt-in and a per-call cap. A
write-once research ledger blocks ambiguous retries. NY17 daily event cap.
No polling, scheduler, broker login, demo order or live account connection.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from research import final_demo_intent as intent
from research import forward_ai_shadow as ai
from research import forward_observation as observation
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_final_demo_cycle_v1"
MAX_EVENTS_PER_NY17_DAY = 3


def _ny17_key(now: datetime) -> str:
    local = now.astimezone(ZoneInfo("America/New_York"))
    day = local.date()
    if local.hour < 17:
        day = day - timedelta(days=1)
    return "ny17_" + day.isoformat()


def _latest_eligible(store: Path, now: datetime) -> str | None:
    audited = observation.audit(store)
    if (audited["runtime_go_no_go"] != "NO_GO"
            or audited["safety_hold_latched"] is not True):
        raise InputError("observation gate modified")
    for index in range(audited["record_count"], 0, -1):
        record = json.loads(
            (store / f"{index:08d}.json").read_text(encoding="utf-8-sig"))
        sample = record["snapshot"]
        if sample["kind"] != "MACRO_EVENT" or sample["source_id"] not in (
                "macro_joined", "fed_policy"):
            continue
        when = timestamp(sample["observed_at_utc"])
        published = timestamp(sample["payload"]["published_at_utc"])
        if not (published <= when <= now):
            continue
        if now - when > intent.MAX_EVENT_AGE:
            continue
        if sample["source_id"] == "fed_policy" and (
                now-published > intent.MAX_EVENT_AGE):
            continue
        return record["record_sha256"]
    return None


def run(store: Path, ledger_dir: Path, *, account: int,
        analyst_model: str, reviewer_model: str,
        max_api_calls: int = 0, allow_external_api: bool = False,
        terminal_files: Path | None = None,
        operator_enable_demo_intent: bool = False,
        now: datetime | None = None) -> dict:
    """Process at most 1 event and <=2 opt-in API calls, never broker calls."""
    now = intent._utc(now or datetime.now(timezone.utc))
    if (type(account) is not int or not 1 <= account <= 999999999
            or type(max_api_calls) is not int or not 0 <= max_api_calls <= 2
            or allow_external_api != bool(max_api_calls)
            or operator_enable_demo_intent != (terminal_files is not None)
            or not ledger_dir.is_dir() or ledger_dir.is_symlink()
            or any(p.is_symlink() for p in ledger_dir.parents)
            or not analyst_model or not reviewer_model
            or analyst_model == reviewer_model):
        raise InputError("invalid explicit demo cycle configuration")
    event = _latest_eligible(store, now)
    if event is None:
        return {
            "schema": SCHEMA,
            "status": "DEMO_CYCLE_NO_RECENT_ELIGIBLE_MACRO_EVENT",
            "api_calls_this_run": 0, "orders_sent_this_run": 0,
            "demo_intent_written": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True}
    day = ledger_dir / _ny17_key(now)
    day.mkdir(exist_ok=True)
    if day.is_symlink() or not day.is_dir():
        raise InputError("invalid NY17 daily ledger directory")
    ledger = day / (event + ".json")
    if (ledger.is_symlink() or any(p.is_symlink() for p in ledger.parents)
            or len(list(day.iterdir())) > MAX_EVENTS_PER_NY17_DAY + 1):
        raise InputError("unsafe ledger directory")
    lock = day / ".demo_cycle.lock"
    if lock.exists() or lock.is_symlink():
        raise InputError("ambiguous or concurrent cycle requires review")
    with lock.open("x", encoding="ascii") as handle:
        handle.write("exclusive demo cycle lock, do not bypass\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        if not ledger.exists():
            if sum(1 for p in day.glob("*.json")) >= MAX_EVENTS_PER_NY17_DAY:
                raise InputError("NY17 daily AI event cap reached")
        if not ledger.exists() and not allow_external_api:
            return {
                "schema": SCHEMA,
                "status": "DEMO_CYCLE_AI_NOT_OPTED_IN_HOLD",
                "api_calls_this_run": 0, "orders_sent_this_run": 0,
                "demo_intent_written": False,
                "real_orders_permitted": False,
                "runtime_go_no_go": "NO_GO", "safety_hold_latched": True}
        calls = 0
        if allow_external_api:
            if not os.environ.get("OPENAI_API_KEY"):
                raise InputError("explicit AI API key absent")
            result = ai.run(
                store, event, ledger, analyst_model=analyst_model,
                reviewer_model=reviewer_model,
                max_api_calls=max_api_calls, allow_external_api=True,
                api_key=os.environ["OPENAI_API_KEY"])
            calls = result["paid_calls_this_run"]
        if not ledger.exists():
            raise InputError("research AI ledger not present")
        state = json.loads(ledger.read_text("utf-8-sig"))
        if state.get("pending_request") is not None:
            raise InputError("unreconciled API or journal publication")
        if state.get("stage") != "COMPLETE":
            return {
                "schema": SCHEMA,
                "status": "DEMO_CYCLE_AI_INCOMPLETE_HOLD",
                "api_calls_this_run": calls, "orders_sent_this_run": 0,
                "demo_intent_written": False,
                "real_orders_permitted": False,
                "runtime_go_no_go": "NO_GO", "safety_hold_latched": True}
        if state["published_to_observation"] is False:
            ai.publish(
                store, event, ledger, analyst_model=analyst_model,
                reviewer_model=reviewer_model)
        try:
            candidate = intent.inspect(store, event, ledger,
                                       account_number=account, now=now)
        except InputError:
            return {
                "schema": SCHEMA,
                "status": "DEMO_CYCLE_AI_REVIEW_OR_MACRO_HOLD",
                "api_calls_this_run": calls, "orders_sent_this_run": 0,
                "demo_intent_written": False,
                "real_orders_permitted": False,
                "runtime_go_no_go": "NO_GO", "safety_hold_latched": True}
        written = False
        if operator_enable_demo_intent:
            intent.write_demo_intent(terminal_files, candidate,
                                     account_number=account)
            written = True
        return {
            "schema": SCHEMA,
            "status": ("DEMO_CYCLE_INTENT_LOCAL_ONLY"
                       if written else "DEMO_CYCLE_CANDIDATE_ONLY"),
            "event_sha256": event,
            "pair": candidate["symbol"],
            "api_calls_this_run": calls,
            "orders_sent_this_run": 0,
            "demo_intent_written": written,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Bounded one-cycle DEMO macro AI handoff")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--ledger-dir", type=Path, required=True)
    p.add_argument("--expected-demo-account", type=int, required=True)
    p.add_argument("--analyst-model", required=True)
    p.add_argument("--reviewer-model", required=True)
    p.add_argument("--max-api-calls", type=int, default=0)
    p.add_argument("--allow-external-api", action="store_true")
    p.add_argument("--terminal-files", type=Path)
    p.add_argument("--operator-enable-demo-intent", action="store_true")
    args = p.parse_args(argv)
    try:
        report = run(
            args.store, args.ledger_dir,
            account=args.expected_demo_account,
            analyst_model=args.analyst_model,
            reviewer_model=args.reviewer_model,
            max_api_calls=args.max_api_calls,
            allow_external_api=args.allow_external_api,
            terminal_files=args.terminal_files,
            operator_enable_demo_intent=args.operator_enable_demo_intent)
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception:
        # Never leak provider exception messages or secrets to a terminal log.
        print(json.dumps({
            "schema": SCHEMA,
            "status": "DEMO_CYCLE_FAIL_CLOSED_RECONCILE_LEDGER",
            "orders_sent_this_run": 0,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
