"""FWD-234..244: preflight and explicit opt-in two-model forward AI bridge.

Reuses the existing crash-safe paid-call ledger and explicit two-stage
OpenAI Responses research. In dry-run mode it performs NO API, network,
MT4 or journal modifications. It NEVER grants trading permission.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from research import forward_ai_shadow as ai
from research import forward_observation as obs
from research import ai_provider_comparison as providers
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_macro_two_model_research_gate_v1"
SHA = re.compile(r"^[a-f0-9]{64}$")
EVIDENCE_HASH_PATTERN = re.compile(
    r"\[RESEARCH_ONLY_UNATTESTED_SOURCE_HASHES\] "
    r"original_macro_event=([a-f0-9]{64}) "
    r"forecast_capture=([a-f0-9]{64}) "
    r"release_excerpt=([a-f0-9]{64})")
MAX_LEDGER_BYTES = 200_000


def inspect(store: Path, event_sha: str, ledger: Path, *,
            analyst_model: str, reviewer_model: str,
            asof_utc: str) -> dict:
    now = timestamp(asof_utc)
    # Basic role separation required by research architecture. Distinct
    # strings do not prove different vendors or truly independent decisions.
    providers.ResearchRoleRegistry(
        analyst_model=analyst_model, reviewer_model=reviewer_model)
    if (type(event_sha) is not str or not SHA.fullmatch(event_sha)
            or not isinstance(ledger, Path) or ledger.is_symlink()
            or not ledger.parent.is_dir()):
        raise InputError("unsafe AI research ledger/event")
    source = ai._event(store, event_sha)
    body = source["payload"]
    received = timestamp(source["observed_at_utc"])
    published = timestamp(body["published_at_utc"])
    if not published <= received <= now:
        raise InputError("unreliable forward event chronology")
    holds = {
        "EVENT_PUBLISHER_AND_CLOCK_NOT_INDEPENDENTLY_ATTESTED",
        "MODEL_ID_SEPARATION_NOT_PROOF_OF_INDEPENDENCE",
        "NO_AUTOMATIC_EXTERNAL_API_OR_TRADING_PERMISSION",
        "MACRO_REVIEW_IS_RESEARCH_NOT_ORDER_APPROVAL",
    }
    if now - received > timedelta(hours=24):
        holds.add("EVENT_OBSERVED_MORE_THAN_24H_AGO")
    scope = "UNSUPPORTED_UNVERIFIED_EVENT"
    if source["source_id"] == "macro_joined":
        match = EVIDENCE_HASH_PATTERN.search(body["content"])
        if (match is None or not body["consensus"].strip()
                or not body["released_value"].strip()):
            holds.add("LINKED_CONSENSUS_OR_RELEASE_EVIDENCE_ABSENT")
        else:
            scope = "QUANTITATIVE_MACRO_WITH_LOCAL_HASH_REFERENCES"
            holds.add("HASH_REFERENCES_NOT_INDEPENDENTLY_AUTHENTICATED")
            holds.add("ECONOMIC_CALENDAR_AND_MARKET_PRICING_UNVERIFIED")
    elif source["source_id"] == "fed_policy":
        scope = "QUALITATIVE_POLICY_ARTICLE_ONLY"
        if not body["consensus"].strip():
            holds.add("POLICY_MARKET_CONSENSUS_NOT_RECORDED")
        holds.add("NO_VERIFIED_NUMERIC_POLICY_SURPRISE")
    else:
        holds.add("RAW_EVENT_WITHOUT_PRE_RELEASE_FORECAST_LINK")
    base = ai._base(
        event_sha, ai.packet(source), analyst_model, reviewer_model)
    state = None
    if ledger.exists():
        if not ledger.is_file() or not 0 < ledger.stat().st_size <= MAX_LEDGER_BYTES:
            raise InputError("unsafe AI ledger size")
        state = json.loads(ledger.read_text("utf-8-sig"))
        ai._valid(state, base)
        if state["pending_request"] is not None:
            holds.add("PENDING_PAID_OR_PUBLICATION_STATE_REQUIRES_RECONCILIATION")
        if state["stage"] == "COMPLETE":
            holds.add("AI_RESEARCH_ALREADY_COMPLETED")
        if state["published_to_observation"]:
            holds.add("AI_RESEARCH_ALREADY_PUBLISHED")
    if scope == "UNSUPPORTED_UNVERIFIED_EVENT":
        holds.add("NO_AUTHORIZED_RESEARCH_PACKET")
    # Only this fixed packet readiness state is eligibility for *explicit,
    # bounded, potentially billable research*; NOT any trade authorization.
    may_call = (scope != "UNSUPPORTED_UNVERIFIED_EVENT"
                and "EVENT_OBSERVED_MORE_THAN_24H_AGO" not in holds
                and state is None or False)
    # Rewrite without precedence ambiguity and explicitly hold pending work.
    may_call = (
        scope != "UNSUPPORTED_UNVERIFIED_EVENT"
        and "EVENT_OBSERVED_MORE_THAN_24H_AGO" not in holds
        and (state is None or (
            state["pending_request"] is None and state["stage"] != "COMPLETE"
            and not state["published_to_observation"]))
        and "LINKED_CONSENSUS_OR_RELEASE_EVIDENCE_ABSENT" not in holds
    )
    return {
        "schema": SCHEMA,
        "status": "TWO_MODEL_MACRO_PREFLIGHT_RESEARCH_NO_GO",
        "event_record_sha256": event_sha,
        "event_observed_at_utc": source["observed_at_utc"],
        "analyst_model_research_only": analyst_model,
        "reviewer_model_research_only": reviewer_model,
        "research_scope": scope,
        "research_api_dispatch_eligible_if_explicit_opt_in": may_call,
        "ledger_present": state is not None,
        "ledger_stage": state["stage"] if state else None,
        "pending_request": state["pending_request"] if state else None,
        "research_holds": sorted(holds),
        "estimated_new_paid_calls_upper_bound_per_invocation": (
            2 if may_call and state is None
            else 1 if may_call and state["stage"] == "REVIEW_PENDING"
            else 0),
        "actual_api_called": False,
        "journal_modified": False,
        "live_model_approval_established": False,
        "independent_review_authenticated": False,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offline macro AI preflight or explicitly billed two-model study")
    p.add_argument("--store", type=Path, required=True)
    p.add_argument("--event-sha256", required=True)
    p.add_argument("--ledger", type=Path, required=True)
    p.add_argument("--analyst-model", required=True)
    p.add_argument("--reviewer-model", required=True)
    p.add_argument("--max-api-calls", type=int, default=0)
    p.add_argument("--allow-external-api", action="store_true")
    p.add_argument("--publish-offline", action="store_true")
    p.add_argument("--out", type=Path)
    args = p.parse_args(argv)
    try:
        if ((args.allow_external_api != (args.max_api_calls > 0))
                or not 0 <= args.max_api_calls <= 2
                or (args.publish_offline and
                    (args.allow_external_api or args.max_api_calls))
                or (args.out and (args.out.exists() or args.out.is_symlink()
                                  or not args.out.parent.is_dir()))):
            raise InputError("unsafe AI request mode/budget/report")
        asof = datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z")
        preflight = inspect(
            args.store, args.event_sha256, args.ledger,
            analyst_model=args.analyst_model,
            reviewer_model=args.reviewer_model,
            asof_utc=asof)
        result = preflight
        if args.publish_offline:
            if (not preflight["ledger_present"]
                    or preflight["pending_request"] is not None
                    or preflight["ledger_stage"] != "COMPLETE"):
                raise InputError("incomplete research cannot publish")
            result = ai.publish(
                args.store, args.event_sha256, args.ledger,
                analyst_model=args.analyst_model,
                reviewer_model=args.reviewer_model)
        elif args.allow_external_api:
            if not preflight[
                    "research_api_dispatch_eligible_if_explicit_opt_in"]:
                raise InputError("paid research preflight HOLD")
            result = ai.run(
                args.store, args.event_sha256, args.ledger,
                analyst_model=args.analyst_model,
                reviewer_model=args.reviewer_model,
                max_api_calls=args.max_api_calls,
                allow_external_api=True,
                api_key=os.environ.get("OPENAI_API_KEY", ""))
        if args.out:
            with args.out.open("x", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "research_scope": preflight["research_scope"],
            "api_calls_this_run": result.get("paid_calls_this_run", 0),
            "api_called": (result.get("paid_calls_this_run", 0) > 0),
            "pending_request": result.get("pending_request"),
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            KeyError, UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "TWO_MODEL_MACRO_RESEARCH_STOP_CHECK_LEDGER",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
