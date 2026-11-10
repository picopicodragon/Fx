"""FWD-112..118: candidate-only offline shadow risk veto. NEVER PLACES ORDERS.

This is NOT a trading engine, paper execution, AI macro hypothesis generator,
broker execution simulator, or permission for live/demo trades. Candidate is
externally provided JSON research input and always rejected for execution.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from research.forward_shadow_quote_quality import inspect as quality_inspect
from research.offline_backtest import InputError, decimal, timestamp

SCHEMA = "fx_fwd_shadow_candidate_risk_v1"
PIP = {"USD/JPY": Decimal("0.01"), "EUR/JPY": Decimal("0.01"),
       "EUR/USD": Decimal("0.0001")}
REQUIRED = frozenset({
    "pair", "side", "equity_jpy", "units", "stop_distance_pips",
    "current_total_risk_jpy", "daily_loss_jpy",
    "drawdown_percent", "scenario_label",
})
MAX_BYTES = 4096


def inspect(sessions: list[tuple[str, Path]], *, asof_utc: str,
            candidate: dict) -> dict:
    if type(candidate) is not dict or set(candidate) != REQUIRED:
        raise InputError("invalid candidate schema")
    if (type(candidate["pair"]) is not str or
            candidate["pair"] not in PIP or
            candidate["side"] not in ("LONG", "SHORT") or
            type(candidate["scenario_label"]) is not str or
            not 1 <= len(candidate["scenario_label"]) <= 80 or
            not candidate["scenario_label"].isascii()):
        raise InputError("invalid scenario identifier/pair/side")
    fields = ("equity_jpy", "units", "stop_distance_pips",
              "current_total_risk_jpy", "daily_loss_jpy", "drawdown_percent")
    numeric = {
        key: decimal(candidate[key], key,
                     positive=key in ("equity_jpy","units","stop_distance_pips"))
        for key in fields
    }
    if numeric["drawdown_percent"] > 100:
        raise InputError("invalid drawdown")
    result = quality_inspect(sessions, asof_utc=asof_utc)
    # This uses the most conservative last-observed ask as EURUSD conversion
    # only in a what-if calculation, without pretending the quoted price is
    # current or authentic. Use maximum USDJPY BID? Conservative loss value
    # uses historical MAX USDJPY ASK to avoid understating scenario risk.
    from research.forward_mt4_v2_quote import parse
    import csv
    import io
    conversion = Decimal("1")
    if candidate["pair"] == "EUR/USD":
        usd_asks = []
        for _, folder in sessions:
            for file in folder.iterdir():
                if not file.name.startswith("FxFwdV3_USDJPY_"):
                    continue
                raw = file.read_bytes()
                row = list(csv.DictReader(
                    io.StringIO(raw.decode("utf-8-sig"))))
                sample = parse(raw, asof_utc=row[0]["observed_at_utc"])
                usd_asks.append(Decimal(sample["ask"]))
        if not usd_asks:
            raise InputError("missing conversion observations")
        conversion = max(usd_asks)
    max_loss = (numeric["units"] * numeric["stop_distance_pips"] *
                PIP[candidate["pair"]] * conversion)
    equity = numeric["equity_jpy"]
    violations = []
    if max_loss > equity * Decimal("0.005"):
        violations.append("PER_CANDIDATE_RISK_ABOVE_0_5_PERCENT")
    if max_loss + numeric["current_total_risk_jpy"] > equity * Decimal("0.01"):
        violations.append("AGGREGATE_RISK_ABOVE_1_PERCENT")
    if numeric["daily_loss_jpy"] >= equity * Decimal("0.015"):
        violations.append("DAILY_LOSS_1_5_PERCENT_HALT")
    if numeric["drawdown_percent"] >= Decimal("4"):
        violations.append("DD_4_PERCENT_NEW_ENTRIES_HALTED")
    if numeric["drawdown_percent"] >= Decimal("5"):
        violations.append("DD_5_PERCENT_HUMAN_APPROVAL_REQUIRED")
    # A synthetic input with no actual risk/hypothesis attestation cannot
    # qualify for entry, even if all toy budget inequalities hold.
    violations.extend((
        "NO_VERIFIED_MACRO_HYPOTHESIS",
        "NOT_AUTHENTICATED_BROKER_PRICES",
        "CANDIDATE_IS_NOT_AN_EXECUTABLE_ORDER",
        "HUMAN_APPROVAL_OR_REAL_TRADE_NOT_GRANTED",
    ))
    return {
        "schema": SCHEMA,
        "status": "SHADOW_CANDIDATE_RESEARCH_VETO_NO_GO",
        "asof_utc": asof_utc,
        "scenario_label": candidate["scenario_label"],
        "pair": candidate["pair"],
        "side": candidate["side"],
        "units_scenario_only": str(numeric["units"]),
        "notional_risk_conversion_research_only": str(conversion),
        "scenario_stop_loss_risk_jpy": str(max_loss),
        "scenario_risk_pct_of_equity":
            str(max_loss / equity * Decimal("100")),
        "scenario_violations_and_holds": sorted(set(violations)),
        "data_quality": {
            "files": result["files"],
            "cycles": result["cycle_count"],
            "incomplete_cycles": result["incomplete_cycles"],
            "alerts_and_holds": result["data_quality_alerts_and_safety_holds"],
        },
        "scenario_only_not_paper_fills": True,
        "broker_or_mt4_accessed": False,
        "actual_positions_created": 0,
        "simulated_fills_created": 0,
        "demo_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline shadow candidate risk veto")
    p.add_argument("--session", action="append", required=True)
    p.add_argument("--candidate", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        from research.forward_mt4_multisession_reliability import _parse_labeled_entries
        sessions = list(_parse_labeled_entries(
            a.session, "--session").items())
        if (not a.candidate.is_file() or a.candidate.is_symlink() or
                not 0 < a.candidate.stat().st_size <= MAX_BYTES or
                a.out.exists() or a.out.is_symlink() or
                not a.out.parent.is_dir() or
                any(folder.resolve() in a.out.resolve().parents
                    for _, folder in sessions)):
            raise InputError("unsafe evidence paths")
        proposal = json.loads(a.candidate.read_text(encoding="utf-8-sig"),
                              parse_float=str, parse_int=str)
        result = inspect(sessions, asof_utc=a.asof_utc, candidate=proposal)
        with a.out.open("x", encoding="utf-8") as out:
            json.dump(result, out, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "scenario_stop_loss_risk_jpy":
                result["scenario_stop_loss_risk_jpy"],
            "scenario_violations_and_holds":
                result["scenario_violations_and_holds"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, ArithmeticError, OverflowError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "SHADOW_CANDIDATE_INPUT_UNVERIFIED",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
