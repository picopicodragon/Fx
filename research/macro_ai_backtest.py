"""Point-in-time evidence contract and offline AI-macro decisions research.

No news scraper, broker API, trade order, model inference, or network use here.
AI text decisions must be traceable to evidence available at each AS-OF time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from research import historical_replay as hist
from research.offline_backtest import InputError, timestamp, simulate

MAX_JSON_BYTES = 4_000_000
MAX_EVENTS = 2_000
KIND = ("central_bank", "economic_release", "news", "other")
DECISIONS = ("APPROVED", "REVISION", "REJECTED", "PENDING")
ACTIONS = ("LONG", "SHORT", "FLAT", "HOLD")


def _json(path: Path):
    try:
        if path.stat().st_size > MAX_JSON_BYTES:
            raise InputError("evidence size limit")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError, OverflowError) as exc:
        raise InputError("invalid evidence file") from exc
    return data


def canonical_hash(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def evidence_file(path: Path) -> tuple[dict, dict]:
    raw = _json(path)
    if (type(raw) is not dict or set(raw) != {"schema", "events"}
            or raw["schema"] != "fx_macro_evidence_v1"
            or type(raw["events"]) is not list
            or not 1 <= len(raw["events"]) <= MAX_EVENTS):
        raise InputError("invalid evidence manifest")
    events = {}
    for row in raw["events"]:
        if (type(row) is not dict or set(row) != {
            "id", "source_url", "source_type", "published_at_utc",
            "available_at_utc", "text", "market_expectation", "observed_result"
        } or any(type(row[k]) is not str for k in row)
                or not row["id"].isascii() or not row["id"].isalnum()
                or not 1 <= len(row["id"]) <= 64 or row["id"] in events
                or row["source_type"] not in KIND
                or not row["source_url"].startswith(("https://", "http://"))
                or not 1 <= len(row["source_url"]) <= 500
                or not 1 <= len(row["text"]) <= 6000
                or len(row["market_expectation"]) > 300
                or len(row["observed_result"]) > 300):
            raise InputError("invalid source record")
        published = timestamp(row["published_at_utc"])
        available = timestamp(row["available_at_utc"])
        if published > available:
            raise InputError("published after availability")
        # A source cannot claim to be earlier than the modern baseline.
        if published.year < 2000 or available.year > 2100:
            raise InputError("source date outside supported range")
        events[row["id"]] = row
    return events, {"evidence_manifest_sha256": canonical_hash(raw),
                    "evidence_event_count": len(events)}


def validate_decision(raw: dict, evidence: dict, *,
                      require_distinct_models: bool = True) -> tuple:
    """Return (asof, pair, action), fail closed for invalid provenance or review."""
    if type(raw) is not dict or set(raw) != {
        "id", "asof_utc", "pair", "evidence_ids",
        "evidence_sha256", "analyst", "reviewer"
    }:
        raise InputError("invalid AI decision record")
    if (type(raw["id"]) is not str or not raw["id"].isascii()
            or not raw["id"].isalnum() or not 1 <= len(raw["id"]) <= 64
            or raw["pair"] not in hist.PAIRS
            or type(raw["evidence_ids"]) is not list
            or not 1 <= len(raw["evidence_ids"]) <= 30
            or any(type(x) is not str or x not in evidence
                   for x in raw["evidence_ids"])
            or len(set(raw["evidence_ids"])) != len(raw["evidence_ids"])
            or type(raw["evidence_sha256"]) is not str):
        raise InputError("invalid decision provenance")
    asof = timestamp(raw["asof_utc"])
    if asof.minute or asof.second or asof.microsecond:
        raise InputError("decision must align to exact H1 bar close")
    # As-of evidence snapshot is exactly the cited evidence, in canonical order.
    cited = [evidence[x] for x in sorted(raw["evidence_ids"])]
    if canonical_hash(cited) != raw["evidence_sha256"]:
        raise InputError("decision evidence hash mismatch")
    for item in cited:
        if timestamp(item["available_at_utc"]) > asof:
            raise InputError("future evidence contamination")
    analyst, reviewer = raw["analyst"], raw["reviewer"]
    if (type(analyst) is not dict
            or set(analyst) != {"model", "action", "hypothesis", "counterevidence"}
            or type(reviewer) is not dict
            or set(reviewer) != {"model", "verdict", "rationale"}
            or any(type(v) is not str for v in analyst.values())
            or any(type(v) is not str for v in reviewer.values())
            or not 1 <= len(analyst["model"]) <= 100
            or not 1 <= len(reviewer["model"]) <= 100
            or (require_distinct_models
                and analyst["model"] == reviewer["model"])
            or analyst["action"] not in ACTIONS
            or reviewer["verdict"] not in DECISIONS
            or not 1 <= len(analyst["hypothesis"]) <= 1500
            or not 1 <= len(analyst["counterevidence"]) <= 1500
            or not 1 <= len(reviewer["rationale"]) <= 1500):
        raise InputError("invalid dual AI review")
    return asof, raw["pair"], (analyst["action"]
                              if reviewer["verdict"] == "APPROVED" else "HOLD")


def decision_file(path: Path, evidence: dict) -> tuple[dict, dict]:
    raw = _json(path)
    if (type(raw) is not dict or set(raw) != {"schema", "decisions"}
            or raw["schema"] != "fx_macro_decisions_v1"
            or type(raw["decisions"]) is not list
            or not 1 <= len(raw["decisions"]) <= MAX_EVENTS):
        raise InputError("invalid AI decision journal")
    ids = set()
    actions = {}
    verdicts = {k: 0 for k in DECISIONS}
    for row in raw["decisions"]:
        key = validate_decision(row, evidence)
        if row["id"] in ids or key[:2] in actions:
            raise InputError("duplicate decision id or pair/asof")
        ids.add(row["id"])
        actions[key[:2]] = key[2]
        verdicts[row["reviewer"]["verdict"]] += 1
    return actions, {"ai_decision_journal_sha256": canonical_hash(raw),
                     "decision_count": len(raw["decisions"]),
                     "review_verdict_counts": verdicts,
                     "approved_nonhold_count": sum(a != "HOLD" for a in actions.values())}


def run(files, evidence_path: Path, decisions_path: Path, **kwargs) -> dict:
    sources, e_meta = evidence_file(evidence_path)
    actions, d_meta = decision_file(decisions_path, sources)
    bars, market_meta = hist.prepare(files)
    bar_close_keys = {(b.time + timedelta(hours=1), b.pair) for b in bars}
    if any(key not in bar_close_keys for key in actions):
        raise InputError("AI decision has no matching closed H1 bar")
    # IMPORTANT: SMA generated by hist.prepare is always discarded.
    # No AI decision or reviewer rejected -> HOLD, never fall back to SMA.
    replaced = [replace(b, signal=actions.get(
        (b.time + timedelta(hours=1), b.pair), "HOLD")) for b in bars]
    result = simulate(replaced, **kwargs)
    market_meta["strategy"] = "POINT_IN_TIME_TEXT_AI_DUAL_REVIEW_REPLAY"
    market_meta["sma_signal_counts"] = market_meta.pop("signal_counts", {})
    market_meta["sma_signals_executed"] = False
    market_meta["historical_market_data_authenticity_independently_verified"] = False
    result["historical_research"] = market_meta
    result["macro_ai_research"] = {
        **e_meta, **d_meta,
        "ai_decisions_are_user_supplied_and_not_cryptographically_authenticated": True,
        "review_independence": "two_distinct_model_IDs_not_proof_of_independence",
        "point_in_time_assurance": "source_timestamps_self_declared_and_checked",
        "future_knowledge_pretraining_not_excludable": True,
        "actual_point_in_time_AI_forecasts_proven": False,
        "real_orders_permitted": False,
    }
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline dual-AI macro research replay; NO_GO")
    for symbol in hist.SYMBOLS:
        ap.add_argument("--" + symbol + "-bid", type=Path, required=True)
        ap.add_argument("--" + symbol + "-ask", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--decisions", type=Path, required=True)
    ap.add_argument("--stop-pips", default="20")
    ap.add_argument("--reward-r", default="2")
    ap.add_argument("--commission-jpy-per-1000-roundtrip", default="0")
    args = ap.parse_args(argv)
    files = {symbol: (getattr(args, symbol + "_bid"),
                      getattr(args, symbol + "_ask")) for symbol in hist.SYMBOLS}
    try:
        output = run(files, args.evidence, args.decisions,
                     stop_pips=args.stop_pips, reward_r=args.reward_r,
                     commission_jpy_per_1000_roundtrip=
                     args.commission_jpy_per_1000_roundtrip)
    except (InputError, ValueError, OSError, ArithmeticError, TypeError):
        print(json.dumps({"status": "FAIL_CLOSED", "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "error": "INVALID_MACRO_REPLAY_INPUT"}))
        return 2
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
