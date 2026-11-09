"""FX-FWD-004A: opt-in TWO-STAGE macro AI shadow run, NO orders.

Calls named OpenAI models only after explicit local CLI opt-in. Paid calls
are ledgered BEFORE dispatch; ambiguous pending requests are NEVER retried.
AI output is recorded in the local research journal, with source linkage.
No production model approvals are implied. No broker connections.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from research import ai_provider_comparison as gateway
from research import ai_provider_annual_audit as annual
from research import forward_observation as obs
from research.offline_backtest import InputError

SCHEMA = "fx_forward_ai_shadow_v1"


def _event(store: Path, event_hash: str) -> dict:
    if (type(event_hash) is not str or len(event_hash) != 64 or
            any(c not in "0123456789abcdef" for c in event_hash)):
        raise InputError("invalid event record hash")
    verified = obs.audit(store)
    for n in range(1, verified["record_count"] + 1):
        row = json.loads((store / f"{n:08d}.json").read_text(
            encoding="utf-8"))
        if row["record_sha256"] == event_hash:
            snap = row["snapshot"]
            if snap["kind"] != "MACRO_EVENT":
                raise InputError("source is not macro event")
            return snap
    raise InputError("macro event source not found")


def packet(snap: dict) -> dict:
    p = snap["payload"]
    return {
        "pair": p["pair"], "asof_utc": snap["observed_at_utc"],
        "source_id": snap["source_id"],
        "source_url": p["source_url"],
        "published_evidence": p["title"] + "\n" + p["content"],
        "market_expectation": p["consensus"],
        "observed_result": p["released_value"],
        "scope": "RESEARCH_ONLY_NOT_A_TRADING_SIGNAL",
    }


def _base(event_sha: str, p: dict, analyst: str, reviewer: str) -> dict:
    gateway._packet_text(p)
    gateway.ResearchRoleRegistry(
        analyst_model=analyst, reviewer_model=reviewer)
    return {
        "schema": SCHEMA, "event_record_sha256": event_sha,
        "input_sha256": hashlib.sha256(
            gateway._packet_text(p).encode("utf-8")).hexdigest(),
        "analyst_model": analyst, "reviewer_model": reviewer,
        "stage": "ANALYST_PENDING", "pending_request": None,
        "analyst": None, "reviewer": None,
        "published_to_observation": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _valid(state: dict, base: dict) -> None:
    if type(state) is not dict or (
            set(state) != set(base) or
            any(state[k] != base[k] for k in
                ("schema", "event_record_sha256", "input_sha256",
                 "analyst_model", "reviewer_model", "runtime_go_no_go",
                 "safety_hold_latched", "real_orders_permitted"))
            or state["stage"] not in
            ("ANALYST_PENDING", "REVIEW_PENDING", "COMPLETE")
            or type(state["published_to_observation"]) is not bool):
        raise InputError("AI shadow ledger identity mismatch")
    if state["pending_request"] is not None:
        if state["pending_request"] not in ("analyst", "reviewer", "publish"):
            raise InputError("unknown pending call")
    a = state["analyst"]
    v = state["reviewer"]
    if a is not None and (
            type(a) is not dict or
            set(a) != {"action", "hypothesis", "counterevidence"} or
            a["action"] not in ("LONG", "SHORT", "HOLD", "FLAT") or
            not all(type(a[k]) is str and 0 < len(a[k]) <= 1500
                    for k in ("hypothesis", "counterevidence"))):
        raise InputError("invalid recorded analyst answer")
    if v is not None and (
            type(v) is not dict or
            set(v) != {"verdict", "rationale"} or
            v["verdict"] not in ("APPROVED", "REVISION", "REJECTED", "PENDING")
            or type(v["rationale"]) is not str or
            not 0 < len(v["rationale"]) <= 1500):
        raise InputError("invalid recorded review")
    if state["stage"] == "ANALYST_PENDING" and (a or v):
        raise InputError("invalid AI shadow phase")
    if state["stage"] == "REVIEW_PENDING" and (a is None or v is not None):
        raise InputError("review phase inconsistent")
    if state["stage"] == "COMPLETE" and (a is None or v is None):
        raise InputError("missing model answer")
    if state["published_to_observation"] and (
            state["stage"] != "COMPLETE"):
        raise InputError("premature observation flag")


def _append(store: Path, sample: dict) -> str:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        file = Path(d) / "research_ai.json"
        file.write_text(json.dumps(sample, ensure_ascii=False),
                        encoding="utf-8")
        return obs.ingest(store, file)["record_sha256"]


def run(store: Path, event_sha: str, ledger: Path, *,
        analyst_model: str, reviewer_model: str,
        max_api_calls: int, allow_external_api: bool,
        api_key: str, inference=None) -> dict:
    event = _event(store, event_sha)
    p = packet(event)
    base = _base(event_sha, p, analyst_model, reviewer_model)
    if ledger.exists():
        state = json.loads(ledger.read_text(encoding="utf-8"))
        _valid(state, base)
    else:
        if not ledger.parent.is_dir():
            raise InputError("shadow output directory missing")
        with ledger.open("x", encoding="utf-8") as stream:
            json.dump(base, stream, indent=2)
        state = base
    if state["pending_request"] is not None:
        raise InputError("ambiguous paid call: manual billing reconciliation")
    if (type(max_api_calls) is not int or max_api_calls < 0 or
            max_api_calls > 2 or
            (max_api_calls and (not allow_external_api or not api_key)) or
            (not max_api_calls and allow_external_api)):
        raise InputError("explicit AI opt-in and 1-2 call cap required")
    registry = gateway.ResearchRoleRegistry(
        analyst_model=analyst_model, reviewer_model=reviewer_model)
    if inference is None:
        from research.macro_ai_generate import response_json
        inference = response_json
    count = 0
    while count < max_api_calls and state["stage"] != "COMPLETE":
        role = ("analyst" if state["stage"] == "ANALYST_PENDING"
                else "reviewer")
        state["pending_request"] = role
        annual._atomic_json(ledger, state)
        if role == "analyst":
            answer = registry.macro_hypothesis(
                p, api_key=api_key, inference=inference)["result"]
            state["analyst"] = answer
            state["stage"] = "REVIEW_PENDING"
        else:
            answer = registry.independent_review(
                p, state["analyst"], api_key=api_key,
                inference=inference)["result"]
            state["reviewer"] = answer
            state["stage"] = "COMPLETE"
        state["pending_request"] = None
        annual._atomic_json(ledger, state)
        count += 1
    # Publication after completing calls is intentionally a separate local
    # operation; after a mid-publication crash the record may be duplicated.
    # Fail closed by prohibiting implicit retry on publication failure.
    return {
        "status": ("FORWARD_AI_SHADOW_COMPLETE_NO_GO"
                   if state["stage"] == "COMPLETE"
                   else "FORWARD_AI_SHADOW_PARTIAL_NO_GO"),
        "stage": state["stage"],
        "paid_calls_this_run": count,
        "pending_request": state["pending_request"],
        "event_record_sha256": event_sha,
        "research_only": True,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def publish(store: Path, event_sha: str, ledger: Path, *,
            analyst_model: str, reviewer_model: str) -> dict:
    event = _event(store, event_sha)
    p = packet(event)
    base = _base(event_sha, p, analyst_model, reviewer_model)
    state = json.loads(ledger.read_text(encoding="utf-8"))
    _valid(state, base)
    if (state["pending_request"] is not None or
            state["stage"] != "COMPLETE" or
            state["published_to_observation"]):
        raise InputError("publication already started or incomplete")
    # Fail closed before first file write; a partial publication is never
    # automatically retried and must be reconciled against local journal.
    state["pending_request"] = "publish"
    annual._atomic_json(ledger, state)
    from datetime import datetime, timezone
    def envelope(kind: str, fields: dict) -> dict:
        return {
            "schema": obs.SCHEMA,
            "kind": kind,
            "observed_at_utc": datetime.now(timezone.utc)
            .isoformat(timespec="seconds").replace("+00:00", "Z"),
            "source_id": "forward_ai_research",
            "payload": fields,
        }
    thesis = state["analyst"]
    hypothesis_hash = _append(store, envelope("MACRO_HYPOTHESIS", {
        "pair": event["payload"]["pair"],
        "direction": thesis["action"] if thesis["action"] in
        ("LONG", "SHORT") else "HOLD",
        "thesis": thesis["hypothesis"],
        "counterevidence": thesis["counterevidence"],
        "model_id": analyst_model,
        "basis_sha256": event_sha,
        "research_only": True,
    }))
    review = state["reviewer"]
    _append(store, envelope("INDEPENDENT_REVIEW", {
        "pair": event["payload"]["pair"],
        "review_of_sha256": hypothesis_hash,
        "verdict": review["verdict"],
        "rationale": review["rationale"],
        "model_id": reviewer_model,
        "research_only": True,
    }))
    state["pending_request"] = None
    state["published_to_observation"] = True
    annual._atomic_json(ledger, state)
    return {
        "status": "FORWARD_AI_SHADOW_PUBLISHED_RESEARCH_ONLY_NO_GO",
        "event_record_sha256": event_sha,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Opt-in forward AI shadow research")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--event-sha256", required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--analyst-model", required=True)
    p.add_argument("--reviewer-model", required=True)
    p.add_argument("--max-api-calls", type=int, default=0)
    p.add_argument("--allow-external-api", action="store_true")
    p.add_argument("--publish-offline", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.publish_offline and (args.max_api_calls or args.allow_external_api):
            raise InputError("publication cannot request paid calls")
        if args.publish_offline:
            result = publish(
                args.store, args.event_sha256, args.ledger,
                analyst_model=args.analyst_model,
                reviewer_model=args.reviewer_model)
        else:
            result = run(
                args.store, args.event_sha256, args.ledger,
                analyst_model=args.analyst_model,
                reviewer_model=args.reviewer_model,
                max_api_calls=args.max_api_calls,
                allow_external_api=args.allow_external_api,
                api_key=os.environ.get("OPENAI_API_KEY", ""))
        print(json.dumps(result))
        return 0
    except (InputError, ValueError, TypeError, OSError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "SHADOW_AI_FAILED_CHECK_LEDGER_BEFORE_ANY_RETRY",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
