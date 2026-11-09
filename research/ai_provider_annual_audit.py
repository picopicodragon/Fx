"""FX-AI-ARCH-003: audited 25-event bounded-provider comparison, research only.

No network by default. Opt-in supports explicit request caps and records a
pending-call marker BEFORE invoking a billed service. An ambiguous failure must
never trigger automatic re-issue. A valid historical one-event result may be
seeded, avoiding three redundant paid calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from research import ai_provider_comparison as gateway
from research import macro_ai_backtest as macro
from research.offline_backtest import InputError

PROVIDERS = ("responses", "jev", "decisions")
PAIR = "USD/JPY"
SCHEMA = "fx_ai_annual_provider_audit_v1"
MAX_EVENTS = 25


def ordered_events(evidence_path: Path) -> list[dict]:
    sources, _ = macro.evidence_file(evidence_path)
    result = sorted(sources.values(),
                    key=lambda e: (e["available_at_utc"], e["id"]))
    if len(result) != MAX_EVENTS or len({e["id"] for e in result}) != MAX_EVENTS:
        raise InputError("expected exactly 25 distinct events")
    return result


def _fingerprint(event: dict) -> str:
    return hashlib.sha256(gateway._packet_text(
        gateway.evidence_packet(event, PAIR)).encode("utf-8")).hexdigest()


def _request_keys(events: list[dict]) -> list[tuple[str, str]]:
    return [(event["id"], provider) for event in events for provider in PROVIDERS]


def _atomic_json(path: Path, obj: dict) -> None:
    """Durable atomic checkpoint, using a private sibling temp file."""
    if not path.parent.is_dir():
        raise InputError("journal parent missing")
    fd, staging = tempfile.mkstemp(
        dir=str(path.parent), prefix=".research-checkpoint-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(obj, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        if os.path.exists(staging):
            os.unlink(staging)


def _validate_row(row: dict, event: dict, provider: str) -> None:
    """Validate any existing or imported data BEFORE considering it paid work."""
    if type(row) is not dict or (
            row.get("event_id") != event["id"] or
            row.get("provider") != provider or
            row.get("pair") != PAIR or
            row.get("contract") != gateway.QUESTION_VERSION or
            row.get("evidence_sha256") != _fingerprint(event) or
            row.get("runtime_go_no_go") != "NO_GO" or
            row.get("safety_hold_latched") is not True or
            row.get("real_orders_permitted") is not False or
            row.get("outcome") != "BOUNDED_RESEARCH_ONLY"):
        raise InputError("row does not match frozen as-of evidence")
    result = row.get("result")
    if (type(result) is not dict or
            set(result) != {
                "priority", "reanalysis",
                "priority_confidence", "reanalysis_confidence"} or
            result["priority"] not in gateway.ACTIONS or
            result["reanalysis"] not in gateway.FOLLOW_UP):
        raise InputError("invalid recorded choice")
    for field in ("priority_confidence", "reanalysis_confidence"):
        value = result[field]
        if provider == "responses" and value is None:
            continue
        if type(value) not in (int, float) or not 0 <= value <= 1:
            raise InputError("invalid recorded confidence")
    duration = row.get("elapsed_ms")
    if type(duration) not in (int, float) or not 0 <= duration < 3600000:
        raise InputError("invalid recorded latency")
    if not isinstance(row.get("model"), str) or not row["model"]:
        raise InputError("invalid recorded model")


def _seed_rows(path: Path, events: list[dict]) -> list[dict]:
    if not path.is_file():
        raise InputError("seed file missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (type(payload) is not dict or
            payload.get("runtime_go_no_go") != "NO_GO" or
            payload.get("real_orders_permitted") is not False or
            payload.get("providers") != list(PROVIDERS) or
            payload.get("event_count") != 1 or
            payload.get("actual_api_requests") != 3):
        raise InputError("seed not a completed 3-provider single-event report")
    rows = payload.get("research_decisions")
    if type(rows) is not list or len(rows) != 3:
        raise InputError("seed rows invalid")
    first = events[0]
    result = {}
    for row in rows:
        provider = row.get("provider")
        if provider not in PROVIDERS or provider in result:
            raise InputError("duplicate/unknown seed provider")
        _validate_row(row, first, provider)
        result[provider] = row
    if set(result) != set(PROVIDERS):
        raise InputError("incomplete seed")
    return [result[p] for p in PROVIDERS]


def new_journal(events: list[dict], seed: list[dict] | None = None) -> dict:
    digest = hashlib.sha256(json.dumps(
        [{"id": e["id"], "sha256": _fingerprint(e)} for e in events],
        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    journal = {
        "schema": SCHEMA, "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True, "real_orders_permitted": False,
        "pair": PAIR, "providers": list(PROVIDERS),
        "question_version": gateway.QUESTION_VERSION,
        "event_fingerprint_sha256": digest,
        "total_slots": len(events) * len(PROVIDERS),
        "pending_request": None, "completed": seed or [],
        "request_attempts_started": 0,
        "seed_imported_requests": len(seed or []),
        "billing_total_jpy_verified": None,
    }
    validate_journal(journal, events)
    return journal


def validate_journal(journal: dict, events: list[dict]) -> None:
    reference = new_journal_digest(events)
    if (type(journal) is not dict or
            journal.get("schema") != SCHEMA or
            journal.get("runtime_go_no_go") != "NO_GO" or
            journal.get("safety_hold_latched") is not True or
            journal.get("real_orders_permitted") is not False or
            journal.get("pair") != PAIR or
            journal.get("providers") != list(PROVIDERS) or
            journal.get("question_version") != gateway.QUESTION_VERSION or
            journal.get("event_fingerprint_sha256") != reference or
            journal.get("total_slots") != len(events) * len(PROVIDERS)):
        raise InputError("journal identity mismatch")
    rows = journal.get("completed")
    if type(rows) is not list or len(rows) > len(events) * len(PROVIDERS):
        raise InputError("invalid journal row count")
    keys = _request_keys(events)
    for position, row in enumerate(rows):
        event_id, provider = keys[position]
        event = events[position // len(PROVIDERS)]
        if event_id != event["id"]:
            raise InputError("row order mismatch")
        _validate_row(row, event, provider)
    seed_count = journal.get("seed_imported_requests")
    attempted = journal.get("request_attempts_started")
    if (type(seed_count) is not int or type(attempted) is not int or
            seed_count not in (0, 3) or attempted < 0 or
            attempted > len(keys) - seed_count or
            len(rows) < seed_count or
            len(rows) - seed_count > attempted):
        raise InputError("invalid request ledger")
    pending = journal.get("pending_request")
    if pending is not None:
        if (type(pending) is not dict or
                set(pending) != {"event_id", "provider", "slot"} or
                pending["slot"] != len(rows) or
                len(rows) >= len(keys) or
                (pending["event_id"], pending["provider"])
                != keys[len(rows)]):
            raise InputError("invalid pending request")
    if journal.get("billing_total_jpy_verified") is not None:
        raise InputError("unverified billing must remain null")


def new_journal_digest(events: list[dict]) -> str:
    return hashlib.sha256(json.dumps(
        [{"id": e["id"], "sha256": _fingerprint(e)} for e in events],
        ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _candidate_flags(event: dict) -> list[str]:
    flags = []
    if not event["market_expectation"].strip():
        flags.append("MISSING_PRE_RELEASE_CONSENSUS")
    if event.get("source_type") not in ("economic_release", "central_bank"):
        flags.append("UNCLASSIFIED_SOURCE_CATEGORY")
    # All covered candidates are as-of official releases, not human labels.
    flags.append("NO_HUMAN_VERIFIED_TRIAGE_LABEL")
    return flags


def audit(journal: dict, events: list[dict]) -> dict:
    validate_journal(journal, events)
    rows = journal["completed"]
    groups = []
    counts = Counter()
    by_id = {e["id"]: e for e in events}
    for i in range(0, len(rows), len(PROVIDERS)):
        batch = rows[i:i + len(PROVIDERS)]
        if len(batch) < len(PROVIDERS):
            break
        event = by_id[batch[0]["event_id"]]
        choices = {r["provider"]: r["result"] for r in batch}
        priority = {r["priority"] for r in choices.values()}
        reanalysis = {r["reanalysis"] for r in choices.values()}
        kinds = []
        if len(priority) > 1:
            kinds.append("PRIORITY_DIFFERENCE")
            counts["PRIORITY_DIFFERENCE"] += 1
        if len(reanalysis) > 1:
            kinds.append("REANALYSIS_DIFFERENCE")
            counts["REANALYSIS_DIFFERENCE"] += 1
        if any("UNKNOWN" in (r["priority"], r["reanalysis"])
               for r in choices.values()):
            kinds.append("UNKNOWN_IN_ONE_OR_MORE_RESPONSES")
            counts["UNKNOWN_IN_ONE_OR_MORE_RESPONSES"] += 1
        flags = _candidate_flags(event)
        groups.append({
            "event_id": event["id"], "asof_utc": batch[0]["asof_utc"],
            "source_url": event["source_url"],
            "priority": {p: choices[p]["priority"] for p in PROVIDERS},
            "reanalysis": {p: choices[p]["reanalysis"] for p in PROVIDERS},
            "choice_confidence": {
                p: {"priority": choices[p]["priority_confidence"],
                    "reanalysis": choices[p]["reanalysis_confidence"]}
                for p in PROVIDERS},
            "disagreement_types": kinds,
            "candidate_evidence_quality_flags": flags,
            "verified_causal_explanation": None,
            "human_review_required": bool(kinds),
        })
    completed = len(groups)
    by_provider = {}
    for p in PROVIDERS:
        sub = [r for r in rows if r["provider"] == p]
        by_provider[p] = {
            "completed_requests": len(sub),
            "priority_distribution": dict(sorted(Counter(
                r["result"]["priority"] for r in sub).items())),
            "reanalysis_distribution": dict(sorted(Counter(
                r["result"]["reanalysis"] for r in sub).items())),
            "mean_latency_ms": (round(sum(r["elapsed_ms"] for r in sub)
                                       / len(sub), 2) if sub else None),
        }
    disagreement = [g for g in groups if g["disagreement_types"]]
    result = {
        "status": ("ANNUAL_PROVIDER_DISAGREEMENT_AUDIT_COMPLETE_NO_GO"
                   if completed == len(events)
                   else "ANNUAL_PROVIDER_DISAGREEMENT_AUDIT_PARTIAL_NO_GO"),
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
        "source_events": len(events), "completed_event_groups": completed,
        "completed_api_decisions": len(rows),
        "pending_request": journal["pending_request"],
        "unanimous_event_groups": completed - len(disagreement),
        "disagreement_event_groups": len(disagreement),
        "disagreement_type_counts": dict(sorted(counts.items())),
        "provider_summary": by_provider,
        "disagreement_details": disagreement,
        "event_level_triage": groups,
        "human_labeled_quality_verified": False,
        "causation_identified": False,
        "estimated_total_api_cost_jpy": None,
        "interpretation": (
            "Differences and missing-consensus flags are observed or candidate "
            "associations, NOT verified causes. No causal attribution, "
            "accuracy, or trading profitability has been established."),
    }
    return result


def run(events: list[dict], journal_path: Path, *, selected_budget: int,
        credentials: dict, registry: gateway.ProviderRegistry | None = None,
        responses_call=gateway.existing.response_json,
        http_call=gateway._safe_http) -> dict:
    """Spend up to selected_budget NEW calls, no implicit retries."""
    if type(selected_budget) is not int or not 1 <= selected_budget <= 75:
        raise InputError("invalid user request cap")
    if not journal_path.is_file():
        raise InputError("missing journal")
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    validate_journal(journal, events)
    if journal["pending_request"] is not None:
        raise InputError("AMBIGUOUS_PAID_CALL_NO_RETRY")
    keys = _request_keys(events)
    remaining = len(keys) - len(journal["completed"])
    if selected_budget > remaining:
        raise InputError("budget greater than remaining work")
    if not all(credentials.get(k) for k in
               ("OPENAI_API_KEY", "TYPESAFE_API_KEY")):
        raise InputError("missing provider credentials")
    registry = registry or gateway.ProviderRegistry()
    for _ in range(selected_budget):
        index = len(journal["completed"])
        eid, provider = keys[index]
        event = events[index // len(PROVIDERS)]
        journal["pending_request"] = {
            "event_id": eid, "provider": provider, "slot": index}
        journal["request_attempts_started"] += 1
        _atomic_json(journal_path, journal)
        # If this call fails or process dies, leave pending_request latched.
        packet = gateway.evidence_packet(event, PAIR)
        row = {
            "event_id": eid, "pair": PAIR,
            "asof_utc": packet["asof_utc"],
            **registry.evaluate(
                provider, packet, credentials=credentials,
                responses_call=responses_call, http_call=http_call),
        }
        _validate_row(row, event, provider)
        journal["completed"].append(row)
        journal["pending_request"] = None
        _atomic_json(journal_path, journal)
    validate_journal(journal, events)
    return journal


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="2025 provider comparison and non-causal disagreement audit")
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--allow-external-api", action="store_true")
    parser.add_argument("--max-api-calls", type=int, default=0)
    args = parser.parse_args(argv)
    stage = "PREFLIGHT"
    try:
        events = ordered_events(args.evidence)
        if not args.journal.parent.is_dir() or (
                args.report and (args.report.exists()
                                 or not args.report.parent.is_dir())):
            raise InputError("output path invalid")
        if args.audit_only and (args.seed or args.allow_external_api
                                or args.max_api_calls or args.resume):
            raise InputError("audit-only cannot invoke paid calls")
        if args.seed and args.resume:
            raise InputError("seed and resume conflict")
        if args.journal.exists():
            if not (args.resume or args.audit_only):
                raise InputError("journal exists; explicit resume required")
            journal = json.loads(args.journal.read_text(encoding="utf-8"))
            validate_journal(journal, events)
        else:
            if args.resume or args.audit_only:
                raise InputError("missing journal")
            seed_rows = _seed_rows(args.seed, events) if args.seed else []
            journal = new_journal(events, seed_rows)
            # Exclusive create, never overwrite prior paid evidence.
            with args.journal.open("x", encoding="utf-8") as output:
                json.dump(journal, output, ensure_ascii=False, indent=2)
        if args.allow_external_api:
            if not 1 <= args.max_api_calls <= 75:
                raise InputError("paid calls require hard nonzero per-run cap")
            stage = "PROVIDER_COMPARISON"
            journal = run(events, args.journal,
                          selected_budget=args.max_api_calls,
                          credentials=dict(os.environ))
        else:
            if args.max_api_calls:
                raise InputError("max-api-calls requires explicit opt-in")
        stage = "AUDIT"
        report = audit(journal, events)
        if args.report:
            with args.report.open("x", encoding="utf-8") as output:
                json.dump(report, output, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
            "source_events": len(events),
            "completed_event_groups": report["completed_event_groups"],
            "completed_api_decisions": report["completed_api_decisions"],
            "disagreement_event_groups": report["disagreement_event_groups"],
            "pending_request": report["pending_request"],
            "real_orders_permitted": False}, ensure_ascii=False))
        return 0
    except (InputError, ValueError, TypeError, OSError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED", "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True, "failure_stage": stage,
            "reason": "ANNUAL_PROVIDER_RESEARCH_FAILED",
            "pending_request_may_require_manual_reconciliation": (
                stage == "PROVIDER_COMPARISON")}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
