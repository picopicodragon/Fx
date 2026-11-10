"""FWD-133..140: one strictly hypothetical, causal bid/ask shadow replay.

Only user-supplied, chronologically consistent self-reported macro hypotheses.
A research ledger is NOT a trade, fill guarantee, execution authorization,
verified model prediction or tested profitability. Never contacts MT4/broker.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from research.forward_mt4_multisession_reliability import (
    inspect as inspect_sessions, _parse_labeled_entries
)
from research.forward_mt4_v2_quote import parse
from research.forward_shadow_macro_contract import inspect as inspect_hypothesis
from research.forward_shadow_quote_quality import PIP
from research.offline_backtest import InputError, decimal, timestamp

SCHEMA = "fx_fwd_macro_shadow_causal_single_scenario_v1"
MAX_SCENARIO_BYTES = 4096
MAX_HYPOTHESIS_BYTES = 16000
MAX_ENTRY_DELAY_SECONDS = 120
MAX_OBSERVATION_GAP_SECONDS = 75
SCENARIO_KEYS = frozenset({
    "scenario_label", "hypothesis_id", "session_label",
    "evaluation_end_at_utc", "equity_jpy", "units",
    "stop_distance_pips", "slippage_pips_each_side",
    "existing_open_risk_jpy", "daily_loss_jpy", "drawdown_percent",
})
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
DATA_VETO = frozenset({
    "INCOMPLETE_THREE_PAIR_CYCLE",
    "PARTIAL_THREE_PAIR_CYCLES",
    "CAPTURE_INTERVAL_NOT_60S",
    "TIMER_INTERVAL_OUT_OF_TOLERANCE",
    "MORE_THAN_30_CYCLES_IN_FOLDER",
    "SESSION_EXCEEDS_30_CAPTURE_CYCLES",
    "CSV_REPLAY_ACROSS_SESSIONS",
    "OVERLAPPING_SESSION_OBSERVATION_WINDOWS",
    "EURUSD_USDJPY_CONVERSION_INCONSISTENT",
    "SERVER_CLOCK_STALLED",
})


def _load_session_quotes(directory: Path) -> list[tuple]:
    grouped: dict[str, dict[str, dict]] = {}
    for file in sorted(directory.iterdir()):
        raw = file.read_bytes()
        try:
            rows = list(csv.DictReader(io.StringIO(
                raw.decode("utf-8-sig")), strict=True))
        except (UnicodeError, csv.Error) as exc:
            raise InputError("invalid shadow quote CSV") from exc
        if len(rows) != 1:
            raise InputError("invalid snapshot shape")
        obs = rows[0]["observed_at_utc"]
        sample = parse(raw, asof_utc=obs)
        by_pair = grouped.setdefault(obs, {})
        if sample["pair"] in by_pair:
            raise InputError("duplicate shadow timestamp/pair")
        by_pair[sample["pair"]] = sample
    ordered = []
    for obs, group in sorted(grouped.items()):
        if set(group) != set(PIP):
            raise InputError("missing three-pair tick group")
        ordered.append((timestamp(obs), group))
    return ordered


def inspect(sessions: list[tuple[str, Path]], *, hypothesis: dict,
            scenario: dict, asof_utc: str) -> dict:
    cutoff = timestamp(asof_utc)
    base = inspect_sessions(sessions, asof_utc=asof_utc)
    macro = inspect_hypothesis(hypothesis, asof_utc=asof_utc)
    if type(scenario) is not dict or set(scenario) != SCENARIO_KEYS:
        raise InputError("invalid shadow scenario shape")
    if (type(scenario["hypothesis_id"]) is not str
            or scenario["hypothesis_id"] != macro["hypothesis_id"]
            or type(scenario["session_label"]) is not str
            or not IDENT.fullmatch(scenario["session_label"])
            or type(scenario["scenario_label"]) is not str
            or not IDENT.fullmatch(scenario["scenario_label"])):
        raise InputError("scenario id mismatch")
    folders = dict(sessions)
    if scenario["session_label"] not in folders:
        raise InputError("unknown research session label")
    numeric = {}
    for key in ("equity_jpy", "units", "stop_distance_pips",
                "slippage_pips_each_side", "existing_open_risk_jpy",
                "daily_loss_jpy", "drawdown_percent"):
        numeric[key] = decimal(
            scenario[key], key,
            positive=key in ("equity_jpy", "units", "stop_distance_pips"))
    if (numeric["drawdown_percent"] > 100
            or numeric["slippage_pips_each_side"] > 10):
        raise InputError("invalid risk scenario range")
    end = timestamp(scenario["evaluation_end_at_utc"])
    decision = timestamp(macro["decision_at_utc"])
    if not decision < end <= cutoff:
        raise InputError("future or non-causal evaluation end")
    holds = set(base["issues_and_safety_holds"])
    blockers = []
    if not macro["hypothetical_replay_allowed_by_document_only"]:
        blockers.append("MACRO_SELF_REPORTED_APPROVAL_NOT_PRESENT")
    if any(reason in holds for reason in DATA_VETO):
        blockers.append("MULTISESSION_DATA_INTEGRITY_VETO")
    selected = next(
        s for s in base["sessions"] if s["label"] == scenario["session_label"])
    if selected["incomplete_cycles"]:
        blockers.append("INCOMPLETE_SELECTED_SESSION")
    if selected["cycles"] < 2:
        blockers.append("TOO_FEW_SNAPSHOTS")
    if any(delta > MAX_OBSERVATION_GAP_SECONDS
           for delta in selected["interval_seconds"]):
        blockers.append("SELECTED_SESSION_HAS_OBSERVATION_GAP")

    evaluation = None
    reserved_risk = None
    observed = _load_session_quotes(folders[scenario["session_label"]])
    first_after = [(ts, group) for ts, group in observed
                   if decision < ts <= decision + timedelta(
                       seconds=MAX_ENTRY_DELAY_SECONDS)]
    if not first_after:
        blockers.append("NO_NEXT_OBSERVATION_WITHIN_ENTRY_WINDOW")
    else:
        entry_time, entry_group = first_after[0]
        if entry_time >= end:
            blockers.append("NO_EVALUATION_WINDOW_AFTER_ENTRY")
        observations = [(ts, group) for ts, group in observed
                        if entry_time <= ts <= end]
        if len(observations) < 2:
            blockers.append("AT_LEAST_TWO_SNAPSHOTS_REQUIRED")
        if any((b[0]-a[0]).total_seconds() > MAX_OBSERVATION_GAP_SECONDS
               for a, b in zip(observations, observations[1:])):
            blockers.append("EVALUATION_CROSSES_MISSING_CYCLE")
        pair = macro["pair"]
        first = entry_group[pair]
        spread = ((Decimal(first["ask"]) - Decimal(first["bid"]))
                  / PIP[pair])
        usd = entry_group["USD/JPY"]
        conversion_reserve = (
            Decimal(usd["ask"]) if pair == "EUR/USD" else Decimal("1"))
        reserved_risk = (
            numeric["units"] *
            (numeric["stop_distance_pips"] + spread +
             2*numeric["slippage_pips_each_side"]) *
            PIP[pair] * conversion_reserve)
        equity = numeric["equity_jpy"]
        if reserved_risk > equity * Decimal("0.005"):
            blockers.append("RESERVED_SINGLE_RISK_GT_0_5_PERCENT")
        if (reserved_risk + numeric["existing_open_risk_jpy"]
                > equity * Decimal("0.01")):
            blockers.append("RESERVED_TOTAL_RISK_GT_1_PERCENT")
        if (numeric["daily_loss_jpy"] >= equity*Decimal("0.015")
                or numeric["daily_loss_jpy"] + reserved_risk
                > equity*Decimal("0.015")):
            blockers.append("DAILY_LOSS_BUDGET_EXHAUSTED")
        if numeric["drawdown_percent"] >= Decimal("4"):
            blockers.append("DD4_NEW_ENTRY_STOP")
        if numeric["drawdown_percent"] >= Decimal("5"):
            blockers.append("DD5_HUMAN_APPROVAL_REQUIRED")
        if not blockers:
            direction = 1 if macro["direction"] == "LONG" else -1
            slip = numeric["slippage_pips_each_side"] * PIP[pair]
            first_bid = Decimal(first["bid"])
            first_ask = Decimal(first["ask"])
            entry = (first_ask + slip if direction == 1
                     else first_bid - slip)
            stop = entry - direction * numeric["stop_distance_pips"] * PIP[pair]
            close_time = None
            close_side = None
            exit_reason = "HISTORICAL_LAST_SNAPSHOT_MARK"
            # Only future observation snapshots can trigger a stop check.
            # No inference about unobserved intraminute gaps.
            for ts, group in observations[1:]:
                q = group[pair]
                side = (Decimal(q["bid"]) if direction == 1
                        else Decimal(q["ask"]))
                close_time, close_side, exit_group = ts, side, group
                if (direction == 1 and side <= stop or
                        direction == -1 and side >= stop):
                    exit_reason = "STOP_LEVEL_CROSSED_AT_OBSERVED_SNAPSHOT"
                    break
            closing = (close_side - slip if direction == 1
                       else close_side + slip)
            quote_pnl = (closing-entry)*direction*numeric["units"]
            if pair == "EUR/USD":
                # Convert scenario gains with sampled USDJPY bid and
                # scenario losses with sampled USDJPY ask, not mid.
                conversion = Decimal(
                    exit_group["USD/JPY"]["bid" if quote_pnl >= 0 else "ask"])
            else:
                conversion = Decimal("1")
            marked_pnl = quote_pnl * conversion
            if marked_pnl < -reserved_risk:
                holds.add("SYNTHETIC_MARK_LOSS_EXCEEDS_RESERVED_RISK")
            evaluation = {
                "entry_observed_at_utc":
                    entry_time.isoformat().replace("+00:00", "Z"),
                "exit_observed_at_utc":
                    close_time.isoformat().replace("+00:00", "Z"),
                "entry_side_with_adverse_slippage": str(entry),
                "exit_side_with_adverse_slippage": str(closing),
                "hypothetical_stop_level": str(stop),
                "exit_reason_observations_only": exit_reason,
                "scenario_mark_pnl_jpy": str(marked_pnl),
                "loss_exceeded_reserved_risk":
                    marked_pnl < -reserved_risk,
                "scenario_quote_to_jpy_at_mark": str(conversion),
                "unknown_intraminute_paths": True,
                "broker_execution_or_fill_attested": False,
            }
    # NO_GO is always mandatory. Even a hypothetical favorable mark result
    # is not permission for a demo or real order, or strategy evidence.
    if numeric["drawdown_percent"] >= Decimal("2"):
        holds.add("DD2_WARNING_RESEARCH_ONLY")
    if numeric["drawdown_percent"] >= Decimal("3"):
        holds.add("DD3_REEVALUATION_RESEARCH_ONLY")
    holds.update((
        "HYPOTHESIS_SOURCE_AND_REVIEW_UNAUTHENTICATED",
        "OBSERVATION_PC_AND_BROKER_TIME_UNATTESTED",
        "SNAPSHOT_REPLAY_NOT_LIVE_EXECUTION",
        "EVENT_BLACKOUT_AND_REAL_MARGIN_RULES_NOT_AUTHENTICATED",
        "NO_TRADING_PERMISSION",
    ))
    return {
        "schema": SCHEMA,
        "status": "CAUSAL_SHADOW_SCENARIO_RESEARCH_NO_GO",
        "scenario_label": scenario["scenario_label"],
        "hypothesis_id": macro["hypothesis_id"],
        "source_chronology_checked": True,
        "review_disposition_self_reported":
            macro["review_disposition_self_reported"],
        "scenario_entry_considered": bool(first_after),
        "reserved_risk_jpy_research_only": (
            str(reserved_risk) if reserved_risk is not None else None),
        "hypothetical_mark_ledger": evaluation,
        "scenario_vetoes": sorted(set(blockers)),
        "unresolved_safety_holds": sorted(holds),
        "hypothesis_real_source_authenticated": False,
        "macro_ai_builder_called": False,
        "macro_ai_verifier_called": False,
        "strategy_profitability_validated": False,
        "actual_broker_trades": 0,
        "demo_order_calls": 0,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline causal hypothetical shadow replay")
    p.add_argument("--session", action="append", required=True)
    p.add_argument("--hypothesis", type=Path, required=True)
    p.add_argument("--scenario", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        sessions = list(_parse_labeled_entries(
            a.session, "--session").items())
        evidence_paths = (a.hypothesis, a.scenario)
        if (any(not pth.is_file() or pth.is_symlink() or not 0 <
                pth.stat().st_size <= 16000 for pth in evidence_paths)
                or a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()
                or any(folder.resolve() in a.out.resolve().parents
                       for _, folder in sessions)):
            raise InputError("invalid replay inputs")
        hypothesis = json.loads(a.hypothesis.read_text("utf-8-sig"))
        scenario = json.loads(a.scenario.read_text("utf-8-sig"),
                              parse_int=str, parse_float=str)
        result = inspect(
            sessions, hypothesis=hypothesis, scenario=scenario,
            asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": result["status"],
            "scenario_vetoes": result["scenario_vetoes"],
            "hypothetical_mark_present":
                result["hypothetical_mark_ledger"] is not None,
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "SHADOW_REPLAY_EVIDENCE_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
