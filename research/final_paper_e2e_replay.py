"""Source-linked offline FX E2E replay: H1+news+completed AI+real DEMO CSV.

This is an ISOLATED hypothetical replay, never the continuously running paper
journal. Engine synthetic-approval gate is enabled ONLY in a fresh in-memory
simulation. The result does not independently attest broker time, macro event
completeness or total transaction costs, and it authorizes no live entry.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from research import final_paper_engine as paper
from research import final_paper_completed_decision as decision
from research import final_paper_event_blackout as blackout
from research import final_demo_periodic as period
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_source_linked_e2e_replay_v1"
NAME = re.compile(r"^FxPaperQuote_[0-9]{8}_[0-9]{6}\.csv$")
MAX_QUOTES = 240
MAX_WINDOW_SECONDS = 4 * 3600


def _files(folder: Path, start: int) -> list[Path]:
    if (not folder.is_dir() or folder.is_symlink()
            or any(p.is_symlink() for p in folder.parents)
            or folder.name.lower() != "files"
            or folder.parent.name.lower() != "mql4"):
        raise InputError("original DEMO MQL4/Files path required")
    accepted = []
    for file in folder.glob("FxPaperQuote_*.csv"):
        if not NAME.fullmatch(file.name):
            raise InputError("unexpected quote snapshot name")
        try:
            t = datetime.strptime(file.name[13:-4],
                                  "%Y%m%d_%H%M%S").replace(
                                      tzinfo=timezone.utc)
        except ValueError as exc:
            raise InputError("invalid DEMO quote file stamp") from exc
        epoch = int(t.timestamp())
        if start - 120 <= epoch <= start + MAX_WINDOW_SECONDS:
            accepted.append(file)
    accepted.sort(key=lambda f: f.name)
    if not 2 <= len(accepted) <= MAX_QUOTES:
        raise InputError("two to 240 real source quotes are required")
    return accepted


def replay_captures(captures: list[dict], signal: dict, *,
                    event_blackout_file: Path | None = None) -> dict:
    """Deterministic counterfactual run from external captures; no file writes."""
    if (not paper._valid_signal(signal)
            or not captures or len(captures) > MAX_QUOTES):
        raise InputError("invalid approved replay input")
    previous = None
    for quote in captures:
        epoch = quote.get("capture_epoch")
        if (type(epoch) is not int
                or (previous is not None and
                    not 30 <= epoch - previous <= 90)):
            raise InputError("missing, reversed or irregular recorded quotes")
        previous = epoch
    signal_first = next((i for i,q in enumerate(captures)
                         if q["capture_epoch"] >= signal["reviewed_epoch"]),
                        None)
    if signal_first is None or signal_first + 1 >= len(captures):
        raise InputError("no subsequent fresh quote after AI review")
    state = paper.initial_state()
    events = []
    first_epoch = captures[signal_first]["capture_epoch"]
    for i, quote in enumerate(captures[signal_first:]):
        epoch = quote["capture_epoch"]
        blackout_active = blackout.check(
            event_blackout_file, epoch,
            now=datetime.fromtimestamp(epoch, tz=timezone.utc)
        )["active_known_blackout"]
        # Explicit what-if model. This is never called from live supervisor.
        state, result = paper.step(
            state, quote, signals=[signal] if i == 0 else [],
            known_event_blackout=blackout_active,
            entry_evidence_ready=True,
        )
        events.extend(result["events"])
    return {
        "schema": SCHEMA,
        "status": "SOURCE_LINKED_OFFLINE_VIRTUAL_E2E_RESEARCH_ONLY_NO_GO",
        "source_quote_cycles": len(captures),
        "cycles_after_model_review": state["cycle_number"],
        "reviewed_signal_action": signal["action"],
        "reviewed_signal_verdict": signal["verdict"],
        "signal_id_sha256": signal["id"],
        "model_review_pc_epoch_unattested": signal["reviewed_epoch"],
        "virtual_portfolio_initial_jpy": state["start_capital_jpy"],
        "virtual_equity_jpy": state["equity_jpy"],
        "virtual_cash_jpy": state["cash_jpy"],
        "virtual_position_count": len(state["positions"]),
        "virtual_closed_trade_count": len(state["trade_log"]),
        "virtual_position_opened": "VIRTUAL_POSITION_OPENED" in events,
        "virtual_stop_or_target_seen": any(
            e in ("VIRTUAL_STOP", "VIRTUAL_TARGET") for e in events),
        "no_lookahead_next_quote_requirement_met":
            captures[signal_first+1]["capture_epoch"] >
            signal["reviewed_epoch"],
        "journal_in_prod_modified": False,
        "market_events_independently_complete": False,
        "broker_clock_independently_attested": False,
        "real_transaction_costs_verified": False,
        "known_event_file_supplied": event_blackout_file is not None,
        "simulated_fills_are_not_broker_executions": True,
        "isolated_counterfactual_only": True,
        "broker_orders_this_run": 0,
        "api_calls_this_run": 0,
        "live_virtual_entries_authorized": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def run(root: Path, mt4: Path, h1: Path, bundles: list[Path], pair: str,
        *, event_blackout_file: Path | None = None) -> dict:
    if (not root.is_dir() or root.is_symlink()
            or any(p.is_symlink() for p in root.parents)
            or pair not in paper.PAIRS or not bundles):
        raise InputError("missing source-linked research inputs")
    if (not (root / "ai_research").is_dir()
            or root.resolve() == mt4.resolve()):
        raise InputError("invalid source linked AI root")
    # Determine decision bar from ORIGINAL H1 rather than arbitrary new bars.
    latest_raw = period._read_h1(h1, datetime.fromtimestamp(
        max((f.stat().st_mtime for f in h1.iterdir()), default=0),
        tz=timezone.utc))
    bar = latest_raw["captures"][period.PAIRS[pair]]["candles"][-1][
        "server_epoch"]
    pattern = re.compile(
        r"^ai_" + paper.SYMS[paper.PAIRS.index(pair)] + r"_" +
        str(bar) + r"_[0-9]{8}_[0-9]{6}\.json$")
    files = list((root / "ai_research").glob("ai_*.json"))
    selected = [file for file in files if pattern.fullmatch(file.name)]
    if len(selected) != 1:
        raise InputError("exactly one finished H1-matched AI ledger required")
    finished = selected[0].stat().st_mtime
    checked_at = datetime.fromtimestamp(
        finished + 1, tz=timezone.utc)
    signal = decision.load_completed(
        root, h1, bundles, pair, bar, checked_at)
    if signal is None:
        raise InputError("saved independent AI review not found")
    raw = _files(mt4, signal["reviewed_epoch"])
    quotes = []
    for file in raw:
        # Historic DEMO captures are revalidated at the recorded time.
        try:
            stamp = datetime.strptime(file.name[13:-4],
                                      "%Y%m%d_%H%M%S").replace(
                                          tzinfo=timezone.utc)
        except ValueError as exc:
            raise InputError("invalid historic quote file name") from exc
        item = paper.validate_quotes(
            file, now=stamp + timedelta(seconds=1))
        if item["capture_epoch"] != int(stamp.timestamp()):
            raise InputError("quote name and source capture time disagree")
        quotes.append(item)
    return replay_captures(quotes, signal,
                           event_blackout_file=event_blackout_file)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="No-order/no-API source-linked paper E2E")
    p.add_argument("--state-root", required=True, type=Path)
    p.add_argument("--mt4-files", required=True, type=Path)
    p.add_argument("--h1-snapshot", required=True, type=Path)
    p.add_argument("--news-bundle", required=True, action="append", type=Path)
    p.add_argument("--pair", choices=paper.PAIRS, required=True)
    p.add_argument("--event-blackout-file", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = run(args.state_root, args.mt4_files,
                     args.h1_snapshot, args.news_bundle, args.pair,
                     event_blackout_file=args.event_blackout_file)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("unsafe replay output")
        with args.out.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False,
                      allow_nan=False, indent=2)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, ValueError, TypeError, KeyError, OSError,
            OverflowError, UnicodeError, ArithmeticError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "SOURCE_LINKED_E2E_REPLAY_FAIL_CLOSED_NO_GO",
            "api_calls_this_run": 0,
            "broker_orders_this_run": 0,
            "live_virtual_entries_authorized": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
