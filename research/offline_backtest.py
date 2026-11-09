"""Offline OHLC research backtest. No broker, MT4, EA, networking or orders.

Supplied signals only; never infers macro hypotheses or authenticates prices.
Results are NOT approvals, trading signals or reliable profitability forecasts.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal as D, InvalidOperation, ROUND_FLOOR
from pathlib import Path
from zoneinfo import ZoneInfo

PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
SIGNALS = ("LONG", "SHORT", "HOLD", "FLAT")
COLUMNS = ("time_utc", "pair", "open", "high", "low", "close",
           "spread_pips", "quote_to_jpy", "signal")
NY = ZoneInfo("America/New_York")


class InputError(ValueError):
    """Invalid or unverifiable simulation input."""


def decimal(value: object, name: str, *, positive: bool = False) -> D:
    if type(value) is not str or not value or value.strip() != value:
        raise InputError("invalid " + name)
    try:
        result = D(value)
    except InvalidOperation as exc:
        raise InputError("invalid " + name) from exc
    if (not result.is_finite() or result > D("1000000000")
            or (result <= 0 if positive else result < 0)):
        raise InputError("invalid " + name)
    return result


def timestamp(value: object) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise InputError("time_utc requires ISO 8601 UTC Z")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise InputError("invalid time_utc") from exc
    if result.utcoffset() != timedelta(0):
        raise InputError("time_utc must be UTC")
    return result


@dataclass(frozen=True)
class Bar:
    time: datetime
    pair: str
    open: D
    high: D
    low: D
    close: D
    spread: D
    quote_to_jpy: D
    signal: str
    # Optional actual bid/ask H1 candle sides for historical research replay.
    # None preserves the v1 mid+fixed-spread standalone CSV interface.
    bid: tuple[D, D, D, D] | None = None
    ask: tuple[D, D, D, D] | None = None


@dataclass
class Position:
    pair: str
    direction: int
    units: int
    entry: D
    stop: D
    target: D
    initial_risk: D
    entry_time: datetime


def parse_csv(source: str) -> list[Bar]:
    if type(source) is not str or not source or len(source) > 4_000_000:
        raise InputError("missing or excessive CSV")
    reader = csv.DictReader(io.StringIO(source, newline=""), strict=True)
    if reader.fieldnames != list(COLUMNS):
        raise InputError("exact CSV columns and ordering required")
    result = []
    seen = set()
    previous = {}
    all_times = set()
    for n, row in enumerate(reader, 2):
        if n > 100_001:
            raise InputError("too many bars")
        if None in row or any(type(v) is not str for v in row.values()):
            raise InputError("malformed CSV record")
        pair = row["pair"]
        if pair not in PAIRS:
            raise InputError("unsupported pair")
        time = timestamp(row["time_utc"])
        if (pair, time) in seen or (pair in previous and time <= previous[pair]):
            raise InputError("duplicate or unordered bars within pair")
        seen.add((pair, time))
        previous[pair] = time
        all_times.add(time)
        o, h, l, c = [decimal(row[k], k, positive=True)
                      for k in ("open", "high", "low", "close")]
        if l > min(o, c) or h < max(o, c) or h < l:
            raise InputError("inconsistent OHLC")
        spread = decimal(row["spread_pips"], "spread_pips")
        fx = decimal(row["quote_to_jpy"], "quote_to_jpy", positive=True)
        if pair.endswith("/JPY") and fx != 1:
            raise InputError("JPY quote_to_jpy must be 1")
        signal = row["signal"]
        if signal not in SIGNALS:
            raise InputError("unknown signal")
        result.append(Bar(time, pair, o, h, l, c, spread, fx, signal))
    if not result:
        raise InputError("no bars")
    all_pairs = {b.pair for b in result}
    if any({b.time for b in result if b.pair == p} != all_times
           for p in all_pairs):
        raise InputError("all pairs require identical timestamp grids")
    return sorted(result, key=lambda b: (b.time, PAIRS.index(b.pair)))


def pip(pair: str) -> D:
    return D("0.01") if pair.endswith("/JPY") else D("0.0001")


def session_day(t: datetime) -> str:
    return (t.astimezone(NY) - timedelta(hours=17)).date().isoformat()


def _mark(pos: Position, bar: Bar, *, opening: bool = False) -> D:
    half = bar.spread * pip(bar.pair) / 2
    mid = bar.open if opening else bar.close
    if bar.bid is not None and bar.ask is not None:
        idx = 0 if opening else 3
        price = bar.bid[idx] if pos.direction == 1 else bar.ask[idx]
    else:
        price = mid - half if pos.direction == 1 else mid + half
    return D(pos.direction * pos.units) * (price - pos.entry) * bar.quote_to_jpy


def _exit_price(pos: Position, bar: Bar):
    half = bar.spread * pip(bar.pair) / 2
    if bar.bid is not None and bar.ask is not None:
        # LONG closes at BID, SHORT closes at ASK. Intrabar stop wins ties.
        exit_side = bar.bid if pos.direction == 1 else bar.ask
        opening, high, low, _ = exit_side
    else:
        opening = bar.open - half if pos.direction == 1 else bar.open + half
        high = bar.high - half if pos.direction == 1 else bar.high + half
        low = bar.low - half if pos.direction == 1 else bar.low + half
    if pos.direction == 1:
        if opening <= pos.stop:
            return opening, "STOP_GAP"
        if low <= pos.stop:
            return pos.stop, "STOP"
        if high >= pos.target:
            return pos.target, "TARGET"
    else:
        if opening >= pos.stop:
            return opening, "STOP_GAP"
        if high >= pos.stop:
            return pos.stop, "STOP"
        if low <= pos.target:
            return pos.target, "TARGET"
    return None, None


def simulate(bars: list[Bar], *, starting_jpy: str = "100000",
             stop_pips: str = "20", reward_r: str = "2",
             lot_step_units: int = 1000, min_units: int = 1000,
             commission_jpy_per_1000_roundtrip: str = "0") -> dict:
    """OHLC research only. Stop-first ambiguity; no margin or execution model."""
    cash = decimal(starting_jpy, "starting_jpy", positive=True)
    initial = cash
    distance = decimal(stop_pips, "stop_pips", positive=True)
    reward = decimal(reward_r, "reward_r", positive=True)
    commission = decimal(commission_jpy_per_1000_roundtrip, "commission")
    if type(lot_step_units) is not int or lot_step_units <= 0:
        raise InputError("invalid lot step")
    if type(min_units) is not int or min_units <= 0 or min_units % lot_step_units:
        raise InputError("invalid minimum units")
    if type(bars) is not list or not bars or len(bars) > 100_000:
        raise InputError("invalid bar collection")
    if any(type(b) is not Bar for b in bars):
        raise InputError("invalid bar type")
    if len({(b.time, b.pair) for b in bars}) != len(bars):
        raise InputError("duplicate bar")
    all_times = {b.time for b in bars}
    if any({b.time for b in bars if b.pair == pair} != all_times
           for pair in {b.pair for b in bars}):
        raise InputError("unequal pair grids")
    for b in bars:
        if (b.pair not in PAIRS or b.signal not in SIGNALS
                or type(b.time) is not datetime
                or b.time.tzinfo is None or b.time.utcoffset() != timedelta(0)
                or any(type(x) is not D or not x.is_finite()
                       for x in (b.open, b.high, b.low, b.close,
                                 b.spread, b.quote_to_jpy))
                or min(b.open, b.high, b.low, b.close, b.quote_to_jpy) <= 0
                or b.spread < 0 or b.low > min(b.open, b.close)
                or b.high < max(b.open, b.close)
                or (b.pair.endswith("/JPY") and b.quote_to_jpy != 1)
                or ((b.bid is None) != (b.ask is None))
                or (b.bid is not None and (
                    type(b.bid) is not tuple or type(b.ask) is not tuple
                    or len(b.bid) != 4 or len(b.ask) != 4
                    or any(type(v) is not D or not v.is_finite() or v <= 0
                           for v in b.bid + b.ask)
                    or any(side[2] > min(side[0], side[3])
                           or side[1] < max(side[0], side[3])
                           for side in (b.bid, b.ask))
                    or any(b.ask[k] < b.bid[k] for k in (0, 3))
                    or b.low != (b.bid[2] + b.ask[2]) / 2
                    or b.high != (b.bid[1] + b.ask[1]) / 2
                    or b.open != (b.bid[0] + b.ask[0]) / 2
                    or b.close != (b.bid[3] + b.ask[3]) / 2))):
            raise InputError("invalid direct bar")
    grouped = {}
    for bar in bars:
        grouped.setdefault(bar.time, {})[bar.pair] = bar
    current = {}
    previous_signal = {}
    trades = []
    peak = cash
    day_start = cash
    trading_day = None
    day_halt = False
    dd_halt = False
    max_dd = D(0)
    rejected = 0
    gap_breaches = 0
    max_positions = 0
    rejected_reasons = {"dd_halt": 0, "daily_halt": 0,
                        "spread_too_wide": 0, "insufficient_risk_budget": 0}
    gap_signal_suppressed = 0
    previous_time = None
    last_group = {}

    def close(pos: Position, bar: Bar, price: D, why: str):
        nonlocal cash, gap_breaches
        gross = D(pos.direction * pos.units) * (price - pos.entry) * bar.quote_to_jpy
        fee = commission * D(pos.units) / 1000
        pnl = gross - fee
        cash += pnl
        if why == "STOP_GAP" and -pnl > pos.initial_risk:
            gap_breaches += 1
        trades.append({
            "pair": pos.pair, "entry_time_utc": pos.entry_time.isoformat(),
            "exit_time_utc": bar.time.isoformat(),
            "side": "LONG" if pos.direction == 1 else "SHORT",
            "units": pos.units, "reason": why, "pnl_jpy": str(pnl)})
        del current[pos.pair]

    for t in sorted(grouped):
        group = grouped[t]
        # A signal from Friday cannot be executed as a fresh Sunday entry.
        # Existing positions still get next observed opening gap enforcement.
        if previous_time is not None and t - previous_time > timedelta(hours=1):
            gap_signal_suppressed += sum(
                previous_signal.get(p) in ("LONG", "SHORT") for p in group)
            previous_signal.clear()
        previous_time = t
        day = session_day(t)
        if day != trading_day:
            trading_day = day
            day_halt = False
            day_start = cash + sum(_mark(p, group[k], opening=True)
                                   for k, p in current.items())

        # First close positions on opening stop gaps or the prior FLAT signal.
        exited = set()
        for pair in sorted(tuple(current), key=PAIRS.index):
            pos, bar = current[pair], group[pair]
            half = bar.spread * pip(pair) / 2
            opening = ((bar.bid[0] if pos.direction == 1 else bar.ask[0])
                       if bar.bid is not None else
                       (bar.open - half if pos.direction == 1 else bar.open + half))
            if ((pos.direction == 1 and opening <= pos.stop)
                    or (pos.direction == -1 and opening >= pos.stop)):
                close(pos, bar, opening, "STOP_GAP")
                exited.add(pair)
            elif previous_signal.get(pair) == "FLAT":
                close(pos, bar, opening, "SIGNAL_FLAT")
                exited.add(pair)

        # Entry decisions have access only to previous-bar signal, not current
        # high/low/close; risk is rounded down in units, never rounded up.
        for pair in sorted(group, key=PAIRS.index):
            bar = group[pair]
            signal = previous_signal.get(pair, "HOLD")
            if signal not in ("LONG", "SHORT") or pair in current or pair in exited:
                continue
            if dd_halt or day_halt or bar.spread >= distance:
                reason = ("dd_halt" if dd_halt else
                          "daily_halt" if day_halt else "spread_too_wide")
                rejected_reasons[reason] += 1
                rejected += 1
                continue
            direction = 1 if signal == "LONG" else -1
            half = bar.spread * pip(pair) / 2
            entry = ((bar.ask[0] if direction == 1 else bar.bid[0])
                     if bar.bid is not None else
                     (bar.open + half if direction == 1 else bar.open - half))
            loss_per_unit = distance * pip(pair) * bar.quote_to_jpy + commission / 1000
            equity_open = cash + sum(_mark(p, group[k], opening=True)
                                     for k, p in current.items())
            remaining = equity_open * D("0.01") - sum(
                p.initial_risk for p in current.values())
            budget = min(equity_open * D("0.005"), remaining)
            steps = int((budget / loss_per_unit / lot_step_units).to_integral_value(
                rounding=ROUND_FLOOR)) if budget > 0 else 0
            units = steps * lot_step_units
            if units < min_units:
                rejected_reasons["insufficient_risk_budget"] += 1
                rejected += 1
                continue
            stop_range = distance * pip(pair)
            current[pair] = Position(pair, direction, units, entry,
                                     entry - D(direction) * stop_range,
                                     entry + D(direction) * stop_range * reward,
                                     loss_per_unit * units, t)
        max_positions = max(max_positions, len(current))
        # OHLC cannot determine stop-vs-target ordering: stop wins ties.
        for pair in sorted(tuple(current), key=PAIRS.index):
            pos = current[pair]
            price, why = _exit_price(pos, group[pair])
            if why:
                close(pos, group[pair], price, why)
        equity_close = cash + sum(_mark(pos, group[p]) for p, pos in current.items())
        peak = max(peak, equity_close)
        dd = (peak - equity_close) / peak
        max_dd = max(max_dd, dd)
        if dd >= D("0.04"):
            dd_halt = True  # Never auto-unlatched without separate authority.
        if equity_close <= day_start * D("0.985"):
            day_halt = True
        if dd >= D("0.05") or day_halt:
            for pair in sorted(tuple(current), key=PAIRS.index):
                pos, bar = current[pair], group[pair]
                half = bar.spread * pip(pair) / 2
                price = ((bar.bid[3] if pos.direction == 1 else bar.ask[3])
                         if bar.bid is not None else
                         (bar.close - half if pos.direction == 1 else bar.close + half))
                close(pos, bar, price, "DD5_EXIT" if dd >= D("0.05") else "DAILY_EXIT")
            if dd >= D("0.05"):
                dd_halt = True
        for pair, bar in group.items():
            previous_signal[pair] = bar.signal
        last_group = group

    for pair in sorted(tuple(current), key=PAIRS.index):
        pos, bar = current[pair], last_group[pair]
        half = bar.spread * pip(pair) / 2
        price = ((bar.bid[3] if pos.direction == 1 else bar.ask[3])
                 if bar.bid is not None else
                 (bar.close - half if pos.direction == 1 else bar.close + half))
        close(pos, bar, price, "END_OF_DATA")
    return {
        "status": "RESEARCH_ONLY_NO_GO", "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True, "trade_count": len(trades),
        "starting_jpy": str(initial), "ending_jpy": str(cash),
        "net_pnl_jpy": str(cash - initial),
        "max_drawdown_observed_pct": str(max_dd * 100),
        "daily_stop_last_day": day_halt, "dd_stop_latched": dd_halt,
        "gap_risk_budget_breaches": gap_breaches,
        "signals_rejected": rejected, "signals_rejected_by_reason": rejected_reasons,
        "stale_gap_signals_suppressed": gap_signal_suppressed,
        "max_open_positions": max_positions,
        "commission_jpy_per_1000_roundtrip": str(commission),
        "synthetic_or_input_data_not_authenticated": True,
        "real_mt4_read_authorized": False,
        "real_order_execution_authorized": False,
        "human_p05_signoff": False, "trades": trades}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline research; never trades")
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--starting-jpy", default="100000")
    parser.add_argument("--stop-pips", default="20")
    parser.add_argument("--reward-r", default="2")
    parser.add_argument("--commission-jpy-per-1000-roundtrip", default="0")
    args = parser.parse_args(argv)
    try:
        if args.csv.stat().st_size > 4_000_000:
            raise InputError("CSV size limit")
        bars = parse_csv(args.csv.read_text(encoding="utf-8-sig"))
        output = simulate(
            bars, starting_jpy=args.starting_jpy,
            stop_pips=args.stop_pips, reward_r=args.reward_r,
            commission_jpy_per_1000_roundtrip=
            args.commission_jpy_per_1000_roundtrip)
    except (InputError, OSError, UnicodeError, csv.Error, ValueError):
        print(json.dumps({"status": "FAIL_CLOSED", "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "error": "INVALID_OFFLINE_INPUT"}))
        return 2
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
