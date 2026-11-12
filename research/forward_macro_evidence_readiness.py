"""FWD-150..160: offline join of MT4 snapshots, macro journal and AI ledgers.

Reuses existing append-only observation hash-chain and two-model research
ledger. No network, paid API, broker, order, or unverifiable signal inference.
An approved review is self-reported research only, never trading authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research import forward_ai_shadow as ai
from research import forward_observation as obs
from research.forward_mt4_multisession_reliability import (
    _parse_labeled_entries, inspect as inspect_sessions
)
from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_macro_joined_evidence_v1"
MAX_LEDGER_BYTES = 200000
MAX_LEDGER_FILES = 48
MAX_RECORDS = 2000


def _validate_store_path(store: Path) -> None:
    if (not isinstance(store, Path) or not store.is_dir()
            or store.is_symlink()):
        raise InputError("missing or unsafe macro journal")
    for file in store.iterdir():
        if file.is_symlink() or not file.is_file():
            raise InputError("unsafe macro journal record")


def _load_records(store: Path, *, cutoff) -> tuple[dict, dict, dict]:
    _validate_store_path(store)
    journal = obs.audit(store)
    if journal["record_count"] > MAX_RECORDS:
        raise InputError("too many joined observation records")
    events = {}
    hypotheses = {}
    reviews = {}
    for n in range(1, journal["record_count"] + 1):
        file = store / f"{n:08d}.json"
        record = json.loads(file.read_text(encoding="utf-8"))
        receipt = timestamp(record["captured_at_utc"])
        snap = record["snapshot"]
        observed = timestamp(snap["observed_at_utc"])
        if receipt > cutoff or observed > receipt:
            raise InputError("future or inconsistent journal timestamps")
        pair = snap["payload"]["pair"]
        if snap["kind"] == "MACRO_EVENT":
            published = timestamp(snap["payload"]["published_at_utc"])
            if not published <= observed:
                raise InputError("macro source future publication")
            events[record["record_sha256"]] = {
                "sha256": record["record_sha256"], "pair": pair,
                "published_at_utc": snap["payload"]["published_at_utc"],
                "captured_at_utc": record["captured_at_utc"],
                "observed_at_utc": snap["observed_at_utc"],
                "has_consensus_value": bool(snap["payload"]["consensus"].strip()),
                "has_released_value":
                    bool(snap["payload"]["released_value"].strip()),
                "snapshot": snap,
            }
        elif snap["kind"] == "MACRO_HYPOTHESIS":
            basis = snap["payload"]["basis_sha256"]
            if (basis not in events or events[basis]["pair"] != pair
                    or timestamp(events[basis]["captured_at_utc"]) > receipt):
                raise InputError("unmatched or future macro hypothesis")
            hypotheses[record["record_sha256"]] = {
                "sha256": record["record_sha256"], "pair": pair,
                "event_sha256": basis, "captured_at_utc": record["captured_at_utc"],
                "direction": snap["payload"]["direction"],
                "model_id": snap["payload"]["model_id"],
            }
        elif snap["kind"] == "INDEPENDENT_REVIEW":
            link = snap["payload"]["review_of_sha256"]
            h = hypotheses.get(link)
            if (h is None or h["pair"] != pair
                    or timestamp(h["captured_at_utc"]) > receipt):
                raise InputError("future or cross-pair review")
            reviews[record["record_sha256"]] = {
                "sha256": record["record_sha256"],
                "pair": pair, "hypothesis_sha256": link,
                "captured_at_utc": record["captured_at_utc"],
                "model_id": snap["payload"]["model_id"],
                "verdict": snap["payload"]["verdict"],
            }
    return events, hypotheses, reviews


def inspect(sessions: list[tuple[str, Path]], *, asof_utc: str,
            store: Path | None = None,
            ai_ledgers: list[Path] | None = None) -> dict:
    cutoff = timestamp(asof_utc)
    base = inspect_sessions(sessions, asof_utc=asof_utc)
    ledgers = [] if ai_ledgers is None else ai_ledgers
    if type(ledgers) is not list or len(ledgers) > MAX_LEDGER_FILES:
        raise InputError("invalid AI ledger count")
    if store is None and ledgers:
        raise InputError("AI ledgers require observed macro journal")
    events, hypotheses, reviews = ({}, {}, {})
    if store is not None:
        events, hypotheses, reviews = _load_records(store, cutoff=cutoff)
    issues = set(base["issues_and_safety_holds"])
    if store is None:
        issues.add("MACRO_EVENT_OBSERVATION_JOURNAL_NOT_PROVIDED")
    if not events:
        issues.add("NO_OBSERVED_MACRO_EVENT")
    missing_consensus = sum(not e["has_consensus_value"] for e in events.values())
    missing_release = sum(not e["has_released_value"] for e in events.values())
    if missing_consensus:
        issues.add("PRE_RELEASE_CONSENSUS_NOT_PRESENT")
    if missing_release:
        issues.add("RELEASE_VALUE_NOT_PRESENT")
    if events:
        issues.add("CONSENSUS_POINT_IN_TIME_PROVENANCE_UNVERIFIED")
        issues.add("MACRO_SOURCE_AUTHENTICITY_UNVERIFIED")
    # For every recorded review, require the same pair and separate model ID.
    # Review status alone never implies execution authorization.
    candidate_records = []
    seen_hypotheses = set()
    independent_id_reviews = 0
    for key, r in sorted(reviews.items()):
        h = hypotheses[r["hypothesis_sha256"]]
        e = events[h["event_sha256"]]
        if h["sha256"] in seen_hypotheses:
            issues.add("MULTIPLE_RESEARCH_REVIEWS_FOR_ONE_HYPOTHESIS")
        seen_hypotheses.add(h["sha256"])
        separate = h["model_id"] != r["model_id"]
        if separate:
            independent_id_reviews += 1
        else:
            issues.add("REVIEWER_AND_BUILDER_MODEL_ID_MATCH")
        if r["verdict"] == "APPROVED" and h["direction"] in ("LONG", "SHORT"):
            # This still is only a structurally eligible hypothetical mark.
            # A source/journal ID does not certify AI independence or event.
            candidate_records.append({
                "event_record_sha256": e["sha256"],
                "hypothesis_record_sha256": h["sha256"],
                "review_record_sha256": r["sha256"],
                "pair": h["pair"],
                "direction": h["direction"],
                "event_published_at_utc": e["published_at_utc"],
                "event_captured_at_utc": e["captured_at_utc"],
                "hypothesis_captured_at_utc": h["captured_at_utc"],
                "review_captured_at_utc": r["captured_at_utc"],
                "model_ids_differ": separate,
                "has_consensus_value": e["has_consensus_value"],
            })
    if not candidate_records:
        issues.add("NO_REVIEWED_NON_HOLD_MACRO_CANDIDATE")
    # Verify detached AI ledgers against the exact recorded event packet.
    # Pending billed requests are NOT retried or silently reconciled.
    evidence_ledgers = []
    unique_events = set()
    for path in ledgers:
        if (not isinstance(path, Path) or path.is_symlink()
                or not path.is_file() or
                not 0 < path.stat().st_size <= MAX_LEDGER_BYTES):
            raise InputError("unsafe AI research ledger")
        state = json.loads(path.read_text(encoding="utf-8-sig"))
        if type(state) is not dict:
            raise InputError("invalid AI ledger")
        key = state.get("event_record_sha256")
        if key not in events or key in unique_events:
            raise InputError("duplicate or unmatched AI ledger")
        unique_events.add(key)
        packet = ai.packet(events[key]["snapshot"])
        baseline = ai._base(
            key, packet, state.get("analyst_model"), state.get("reviewer_model"))
        ai._valid(state, baseline)
        if state["pending_request"] is not None:
            issues.add("AMBIGUOUS_API_REQUEST_MANUAL_RECONCILIATION")
        if state["stage"] != "COMPLETE":
            issues.add("AI_REVIEW_NOT_YET_COMPLETE")
        if state["stage"] == "COMPLETE" and not state["published_to_observation"]:
            issues.add("AI_RESEARCH_NOT_PUBLISHED_TO_OBSERVATIONS")
        evidence_ledgers.append({
            "event_record_sha256": key,
            "stage": state["stage"],
            "pending_request": state["pending_request"],
            "analyst_model": state["analyst_model"],
            "reviewer_model": state["reviewer_model"],
            "review_disposition": (state["reviewer"]["verdict"]
                                   if state["reviewer"] else None),
            "published_to_observation": state["published_to_observation"],
            "ledger_source_independently_authenticated": False,
        })
    issues.add("MACRO_EVIDENCE_IS_NOT_ORDER_AUTHORIZATION")
    issues.add("MT4_AND_BROKER_NOT_INDEPENDENTLY_ATTESTED")
    return {
        "schema": SCHEMA,
        "status": "JOINED_MACRO_EVIDENCE_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "quote_session_count": base["session_count"],
        "quote_csv_count": base["csv_file_count"],
        "quote_complete_cycles": base["complete_cycle_count"],
        "macro_journal_supplied": store is not None,
        "macro_event_count": len(events),
        "macro_hypothesis_count": len(hypotheses),
        "macro_review_count": len(reviews),
        "macro_reviewed_distinct_model_id_count": independent_id_reviews,
        "macro_event_missing_consensus_count": missing_consensus,
        "macro_event_missing_release_count": missing_release,
        "research_only_candidate_count": len(candidate_records),
        "candidate_records": candidate_records,
        "ledger_count": len(evidence_ledgers),
        "ledger_evidence": evidence_ledgers,
        "source_holds_and_warnings": sorted(issues),
        "actual_ai_provider_called": False,
        "independent_review_proven": False,
        "macro_prediction_performance_proven": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Join offline MT4 quote sessions and local macro journal")
    p.add_argument("--session", action="append", required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--store", type=Path)
    p.add_argument("--ai-ledger", action="append", default=[], type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        sessions = list(_parse_labeled_entries(
            a.session, "--session").items())
        inputs = [folder.resolve() for _, folder in sessions]
        if a.store is not None:
            inputs.append(a.store.resolve())
        if (a.out.is_symlink() or a.out.exists()
                or not a.out.parent.is_dir()
                or any(source in a.out.resolve().parents
                       for source in inputs)):
            raise InputError("unsafe evidence report destination")
        result = inspect(sessions, asof_utc=a.asof_utc,
                         store=a.store, ai_ledgers=a.ai_ledger)
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "files": result["quote_csv_count"],
            "complete_cycles": result["quote_complete_cycles"],
            "macro_events": result["macro_event_count"],
            "research_only_candidates": result["research_only_candidate_count"],
            "ledger_count": result["ledger_count"],
            "source_holds_and_warnings": result["source_holds_and_warnings"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "JOINED_MACRO_EVIDENCE_UNTRUSTED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
