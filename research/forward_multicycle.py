"""FWD-014/015/016: immutable multi-cycle offline paper evidence aggregation.

Each FWD-005 report independently replays an entire observation history.
Consequently cumulative PnL MUST NOT be a sum of those reports. Reconcile
as-of marks for a single hypothesis, keep gaps as holds, and issue NO_GO.
No networking, MT4, live prices, AI APIs or order operations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from research.forward_risk_timeline import SCHEMA as RISK_SCHEMA, evaluate
from research.offline_backtest import InputError, PAIRS, decimal, timestamp

SCHEMA = "fx_forward_multicycle_v1"
CYCLE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_CYCLES = 5000
MAX_REPORT = 300_000
MAX_GAP_SECONDS = 300
BASE_JPY = Decimal("100000")


def _json_report(path: Path) -> tuple[dict, str]:
    if not path.is_file() or path.stat().st_size > MAX_REPORT:
        raise InputError("missing or oversized local report")
    raw = path.read_bytes()
    try:
        obj = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise InputError("invalid report encoding") from exc
    if type(obj) is not dict:
        raise InputError("invalid report object")
    return obj, hashlib.sha256(raw).hexdigest()


def _safe(report: dict) -> None:
    if (report.get("runtime_go_no_go") != "NO_GO" or
            report.get("real_orders_permitted") is not False or
            report.get("safety_hold_latched") is not True):
        raise InputError("unsafe local research report")


def combine(rows: list[dict], *, max_gap_seconds: int = MAX_GAP_SECONDS) -> dict:
    if type(max_gap_seconds) is not int or not 1 <= max_gap_seconds <= 86400:
        raise InputError("invalid gap limit")
    if type(rows) is not list or not 1 <= len(rows) <= MAX_CYCLES:
        raise InputError("invalid cycle count")
    seen = set()
    previous_at = None
    previous_count = None
    previous_evidence = None
    hypothesis = None
    samples = []
    cycles = []
    blockers = set()
    for row in rows:
        if type(row) is not dict or set(row) != {
                "cycle_id", "quality", "paper", "quality_sha256",
                "paper_sha256"}:
            raise InputError("unexpected cycle format")
        cid = row["cycle_id"]
        if type(cid) is not str or not CYCLE.fullmatch(cid) or cid in seen:
            raise InputError("duplicate/invalid cycle ID")
        seen.add(cid)
        for field in ("quality_sha256", "paper_sha256"):
            if type(row[field]) is not str or not SHA.fullmatch(row[field]):
                raise InputError("missing evidence hash")
        qa, paper = row["quality"], row["paper"]
        if type(qa) is not dict or type(paper) is not dict:
            raise InputError("invalid cycle evidence")
        _safe(qa)
        _safe(paper)
        if (qa.get("status") != "FORWARD_QUALITY_RESEARCH_ONLY_NO_GO" or
                paper.get("status") != "FORWARD_HYPOTHETICAL_PAPER_REPLAY_NO_GO" or
                paper.get("demo_order_execution_enabled") is not False or
                paper.get("mt4_connected") is not False or
                paper.get("asof_utc") != qa.get("asof_utc") or
                type(qa.get("record_count")) is not int or
                qa["record_count"] < 0):
            raise InputError("mismatched research reports")
        at = timestamp(qa["asof_utc"])
        if previous_at is not None and at <= previous_at:
            raise InputError("out-of-order cycle")
        if previous_count is not None and qa["record_count"] < previous_count:
            raise InputError("journal evidence rollback")
        if previous_count is not None and qa["record_count"] == previous_count:
            blockers.add("NO_NEW_OBSERVATIONS")
        if previous_at is not None and (
                at - previous_at).total_seconds() > max_gap_seconds:
            blockers.add("CYCLE_GAP_EXCEEDED")
        previous_at, previous_count = at, qa["record_count"]
        if (qa.get("source_authenticity_verified") is not False or
                qa.get("capture_clock_independently_verified") is not False or
                qa.get("full_economic_calendar_coverage_verified") is not False):
            raise InputError("unsupported evidence certification")
        if qa.get("late_capture_sequences") or qa.get("out_of_order_source_sequences"):
            blockers.add("QUALITY_DEFECT")
        quotes = qa.get("current_asof_quote_freshness")
        if type(quotes) is not dict or set(quotes) != set(PAIRS):
            raise InputError("incomplete pair-quality matrix")
        if any(type(quotes[p]) is not dict or
               quotes[p].get("quote_fresh") is not True for p in PAIRS):
            blockers.add("UNFRESH_OR_MISSING_PAIR")
        position = paper.get("hypothetical_position")
        # Allow signed PnL but reject NaN, infinity and noncanonical strings.
        raw_pnl = paper.get("hypothetical_pnl_jpy")
        if (type(raw_pnl) is not str or not raw_pnl or
                raw_pnl.strip() != raw_pnl):
            raise InputError("invalid simulated PnL")
        try:
            pnl = Decimal(raw_pnl)
        except (ValueError, ArithmeticError) as exc:
            raise InputError("invalid simulated PnL") from exc
        if not pnl.is_finite() or abs(pnl) > Decimal("1000000000"):
            raise InputError("out-of-range simulated PnL")
        if position is None:
            if pnl != 0:
                raise InputError("nonzero PnL without paper position")
            blockers.add("NO_PAPER_POSITION")
            risk = Decimal("0")
        else:
            if (type(position) is not dict or
                    position.get("pair") not in PAIRS or
                    position.get("direction") not in ("LONG", "SHORT") or
                    type(position.get("hypothesis_record_sha256")) is not str or
                    not SHA.fullmatch(position["hypothesis_record_sha256"])):
                raise InputError("invalid paper position identity")
            if (hypothesis is not None and
                    hypothesis != position["hypothesis_record_sha256"]):
                raise InputError("multiple paper strategies cannot be netted")
            hypothesis = position["hypothesis_record_sha256"]
            risk = decimal(position.get("initial_risk_jpy"),
                           "initial_risk_jpy")
            if risk > BASE_JPY * Decimal("0.005"):
                blockers.add("PAPER_SINGLE_TRADE_RISK_EXCEEDED")
            if position.get("position_closed") is True:
                risk = Decimal("0")
            elif position.get("position_closed") is not False:
                raise InputError("unknown paper position state")
        equity = BASE_JPY + pnl
        if equity <= 0:
            raise InputError("invalid simulated equity")
        sample = {
            "observed_at_utc": qa["asof_utc"],
            "equity_jpy": str(equity),
            "open_risk_jpy": str(risk),
            "source_status": "HYPOTHETICAL_UNVERIFIED",
        }
        samples.append(sample)
        cycles.append({
            "cycle_id": cid, "asof_utc": qa["asof_utc"],
            "observation_count": qa["record_count"],
            "quality_sha256": row["quality_sha256"],
            "paper_sha256": row["paper_sha256"],
            "hypothetical_pnl_jpy": str(pnl),
            "hypothetical_equity_jpy": str(equity),
        })
    risk_result = evaluate(samples)
    if any((risk_result["hypothetical_dd_level3_latched"],
            risk_result["hypothetical_dd_hard_stop_latched"],
            risk_result["hypothetical_daily_loss_latched"],
            risk_result["hypothetical_concurrent_risk_violated"])):
        blockers.add("HYPOTHETICAL_RISK_ALARM")
    # No real broker equity or time/source attestation. Baseline mark is an
    # assumed 100000 JPY, not independently reconciled cash balance.
    blockers.update(("BROKER_EQUITY_NOT_AUTHENTICATED",
                     "SOURCE_AND_CLOCK_UNVERIFIED",
                     "ECONOMIC_CALENDAR_INCOMPLETE",
                     "PAPER_EXECUTION_NOT_A_BROKER_FILL"))
    return {
        "schema": SCHEMA, "status": "FORWARD_MULTICYCLE_RESEARCH_HOLD_NO_GO",
        "cycle_count": len(cycles), "cycles": cycles,
        "research_only_latest_hypothetical_pnl_jpy": cycles[-1]["hypothetical_pnl_jpy"],
        "research_only_latest_hypothetical_equity_jpy": cycles[-1]["hypothetical_equity_jpy"],
        "pnl_aggregation": "LATEST_INDEPENDENT_FULL_REPLAY_NOT_SUM",
        "risk_timeline": risk_result,
        "blocking_reasons": sorted(blockers),
        "price_stream_connected": False,
        "mt4_demo_authenticated": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def from_manifest(manifest: dict, directory: Path) -> list[dict]:
    if (type(manifest) is not dict or set(manifest) != {"schema", "cycles"} or
            manifest["schema"] != SCHEMA or
            type(manifest["cycles"]) is not list):
        raise InputError("invalid multi-cycle manifest")
    result = []
    for cid in manifest["cycles"]:
        if type(cid) is not str or not CYCLE.fullmatch(cid):
            raise InputError("unsafe cycle ID")
        qa, qsha = _json_report(directory / (cid + "_quality.json"))
        paper, psha = _json_report(directory / (cid + "_paper.json"))
        result.append({
            "cycle_id": cid, "quality": qa, "paper": paper,
            "quality_sha256": qsha, "paper_sha256": psha,
        })
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline multi-cycle paper monitor (never trades)")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--reports-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--max-gap-seconds", type=int, default=300)
    args = parser.parse_args(argv)
    try:
        if (args.out.exists() or not args.out.parent.is_dir()
                or not args.reports_dir.is_dir() or
                not args.manifest.is_file() or
                args.manifest.stat().st_size > 100000):
            raise InputError("unsafe file paths")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        report = combine(from_manifest(manifest, args.reports_dir),
                         max_gap_seconds=args.max_gap_seconds)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps({"status": report["status"],
                          "cycle_count": report["cycle_count"],
                          "blocking_reasons": report["blocking_reasons"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (OSError, InputError, TypeError, ValueError, KeyError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED", "reason": "INVALID_MULTICYCLE_EVIDENCE",
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
