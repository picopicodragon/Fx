"""FX-FWD-004/005: strictly offline hypothesis/review audit and paper-only sandbox.

Explicit operator-authored scenario. These simulated fills are NOT broker
orders, broker risk limits, or proof of execution. No side-effects except
writing an absent report; no MT4 / network / AI API calls.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal as D, ROUND_FLOOR
from pathlib import Path

from research import forward_quality as quality
from research.offline_backtest import InputError, PAIRS, decimal, timestamp

SCHEMA = "fx_forward_paper_scenario_v1"
MAX_STORED_EVENTS = 100000
PIP = {"USD/JPY": D("0.01"), "EUR/JPY": D("0.01"),
       "EUR/USD": D("0.0001")}
CAPITAL = D("100000")


def _d(value: object, name: str, *, positive: bool = False) -> D:
    return decimal(value, name, positive=positive)


def scenario_validate(s: dict) -> dict:
    if (type(s) is not dict or
            set(s) != {"schema", "hypothetical_only", "starting_jpy",
                       "stop_pips", "reward_multiple",
                       "max_simulated_positions", "commission_jpy"} or
            s["schema"] != SCHEMA or
            s["hypothetical_only"] is not True or
            s["max_simulated_positions"] != 1 or
            type(s["max_simulated_positions"]) is not int):
        raise InputError("invalid scenario scope")
    capital = _d(s["starting_jpy"], "starting_jpy", positive=True)
    stop = _d(s["stop_pips"], "stop_pips", positive=True)
    reward = _d(s["reward_multiple"], "reward_multiple", positive=True)
    commission = _d(s["commission_jpy"], "commission_jpy")
    if (capital != CAPITAL or not D("5") <= stop <= D("200") or
            not D("1") <= reward <= D("3") or
            commission > D("50")):
        raise InputError("unsupported research assumptions")
    return s


def _fmt(v: D) -> str:
    return format(v.quantize(D("0.0001")), "f")


def _quote(row: dict) -> tuple[D, D, D]:
    data = row["snapshot"]["payload"]
    return (_d(data["bid"], "bid", positive=True),
            _d(data["ask"], "ask", positive=True),
            _d(data["quote_to_jpy"], "quote_to_jpy", positive=True))


def replay(store: Path, s: dict, *, asof_utc: str) -> dict:
    scenario_validate(s)
    cutoff = timestamp(asof_utc)
    rows = quality.records(store)
    if len(rows) > MAX_STORED_EVENTS:
        raise InputError("too many forward observations")
    # We are NOT using current/no-future economic calendar to approve trades.
    # Only simulate hypothetical fills once an independent review is linked.
    events = {}
    hypotheses = {}
    reviews = []
    quotes = []
    for row in rows:
        snap = row["snapshot"]
        if timestamp(row["captured_at_utc"]) > cutoff:
            raise InputError("future record present in replay snapshot")
        kind = snap["kind"]
        pair = snap["payload"]["pair"]
        if kind == "MACRO_EVENT":
            events[row["record_sha256"]] = (row, pair)
        elif kind == "MACRO_HYPOTHESIS":
            h = snap["payload"]
            if h["basis_sha256"] not in events or (
                    events[h["basis_sha256"]][1] != pair):
                raise InputError("cross pair/stale event hypothesis")
            hypotheses[row["record_sha256"]] = row
        elif kind == "INDEPENDENT_REVIEW":
            h = hypotheses.get(snap["payload"]["review_of_sha256"])
            if h is None or h["snapshot"]["payload"]["pair"] != pair:
                raise InputError("review not linked to same pair")
            if h["snapshot"]["payload"]["model_id"] == (
                    snap["payload"]["model_id"]):
                raise InputError("review not independently identified")
            reviews.append((row, h))
        elif kind == "PRICE_QUOTE":
            quotes.append(row)
    filled = None
    simulated_pnl = D("0")
    risk = D("0")
    skipped = []
    effective_reviews = []
    for review, hyp in reviews:
        if review["snapshot"]["payload"]["verdict"] != "APPROVED":
            skipped.append("REVIEW_NOT_APPROVED_RESEARCH_ONLY")
            continue
        direction = hyp["snapshot"]["payload"]["direction"]
        if direction not in ("LONG", "SHORT"):
            skipped.append("HOLD_NO_PAPER_POSITION")
            continue
        effective_reviews.append((review, hyp))
    # Do not allow multiple independently approved hypotheses to become
    # an implicit multi-position simulator.
    if len(effective_reviews) > 1:
        skipped.append("MULTIPLE_RESEARCH_HYPOTHESES_REQUIRE_REVIEW")
        effective_reviews = []
    if effective_reviews:
        review, hypothesis = effective_reviews[0]
        pair = hypothesis["snapshot"]["payload"]["pair"]
        direction = hypothesis["snapshot"]["payload"]["direction"]
        after_review = [
            q for q in quotes if q["snapshot"]["payload"]["pair"] == pair
            and timestamp(q["captured_at_utc"]) >
            timestamp(review["captured_at_utc"])]
        if len(after_review) < 2:
            skipped.append("INSUFFICIENT_QUOTES_AFTER_REVIEW")
        elif any(
                (timestamp(q["captured_at_utc"]) -
                 timestamp(q["snapshot"]["observed_at_utc"]))
                .total_seconds() > 90 for q in after_review):
            skipped.append("STALE_QUOTE_NO_PAPER_ENTRY")
        else:
            stop_pips = _d(s["stop_pips"], "stop", positive=True)
            stop_dist = stop_pips * PIP[pair]
            first = after_review[0]
            bid, ask, to_jpy = _quote(first)
            entry = ask if direction == "LONG" else bid
            # This is a hypothetical, not validated broker lot rounding.
            one_unit_risk = stop_dist * to_jpy
            quantity = int(((CAPITAL * D("0.005")) / one_unit_risk /
                            D("1000")).to_integral_value(
                                rounding=ROUND_FLOOR)) * 1000
            if quantity <= 0:
                skipped.append("SMALL_RISK_BUDGET")
            else:
                risk = D(quantity) * one_unit_risk
                if risk > CAPITAL * D("0.005"):
                    raise InputError("risk invariant violated")
                factor = 1 if direction == "LONG" else -1
                stop_price = entry - stop_dist * factor
                target_price = entry + (
                    stop_dist * _d(s["reward_multiple"], "reward")
                    * factor)
                close = None
                exit_reason = "MARK_TO_MARKET_RESEARCH_ONLY"
                exit_quote = after_review[-1]
                for next_quote in after_review[1:]:
                    qb, qa, _ = _quote(next_quote)
                    if direction == "LONG":
                        if qb <= stop_price:
                            close, exit_reason = qb, "HYPOTHETICAL_STOP"
                        elif qb >= target_price:
                            close, exit_reason = qb, "HYPOTHETICAL_TARGET"
                    else:
                        if qa >= stop_price:
                            close, exit_reason = qa, "HYPOTHETICAL_STOP"
                        elif qa <= target_price:
                            close, exit_reason = qa, "HYPOTHETICAL_TARGET"
                    if close is not None:
                        exit_quote = next_quote
                        break
                if close is None:
                    eb, ea, _ = _quote(exit_quote)
                    close = eb if direction == "LONG" else ea
                # Conservative reporting: use observed side for exit. Quote
                # conversion is a scenario assumption, not verified market FX.
                # Use the exit conversion in reporting; real fills may diverge.
                eb, ea, exit_to_jpy = _quote(exit_quote)
                simulated_pnl = ((close - entry) * D(quantity) *
                                 D(factor) * exit_to_jpy -
                                 _d(s["commission_jpy"], "commission"))
                filled = {
                    "pair": pair, "direction": direction,
                    "hypothesis_record_sha256": hypothesis["record_sha256"],
                    "review_record_sha256": review["record_sha256"],
                    "entry_record_sha256": first["record_sha256"],
                    "exit_record_sha256": exit_quote["record_sha256"],
                    "entry": _fmt(entry), "exit": _fmt(close),
                    "stop": _fmt(stop_price), "target": _fmt(target_price),
                    "simulated_units": quantity,
                    "initial_risk_jpy": _fmt(risk),
                    "hypothetical_pnl_jpy": _fmt(simulated_pnl),
                    "exit_reason": exit_reason,
                    "position_closed": exit_reason !=
                    "MARK_TO_MARKET_RESEARCH_ONLY",
                }
    return {
        "status": "FORWARD_HYPOTHETICAL_PAPER_REPLAY_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True, "real_orders_permitted": False,
        "demo_order_execution_enabled": False,
        "mt4_connected": False,
        "schema": SCHEMA, "asof_utc": asof_utc,
        "starting_capital_jpy": _fmt(CAPITAL),
        "observed_quote_count": len(quotes),
        "observed_review_count": len(reviews),
        "hypothetical_position": filled,
        "skipped_reasons": skipped,
        "hypothetical_pnl_jpy": _fmt(simulated_pnl),
        "broker_lot_size_verified": False,
        "broker_margin_verified": False,
        "broker_commission_or_slippage_verified": False,
        "all_future_macro_blackouts_verified": False,
        "daily_and_drawdown_risk_engine_certified": False,
        "ai_forecast_quality_established": False,
        "research_only_not_a_trading_decision": True,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Offline hypothetical replay; never places broker orders")
    p.add_argument("--store", required=True, type=Path)
    p.add_argument("--scenario", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        timestamp(args.asof_utc)
        if (args.out.exists() or not args.out.parent.is_dir() or
                args.scenario.stat().st_size > 3000):
            raise InputError("invalid report/scenario file")
        scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
        result = replay(args.store, scenario, asof_utc=args.asof_utc)
        with args.out.open("x", encoding="utf-8") as out:
            json.dump(result, out, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": result["status"],
            "hypothetical_position_present": result[
                "hypothetical_position"] is not None,
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, TypeError, ValueError,
            UnicodeError, ArithmeticError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "UNSAFE_PAPER_REPLAY_INPUT_OR_STATE",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
