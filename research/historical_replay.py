"""User-supplied historical Dukascopy bid/ask CSV -> offline research replay.

NO download, network, broker/MT4 integration, trading or approval. Files remain
on the user's own machine. Research-only SMA crossover is NOT the AI strategy.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

from research.offline_backtest import (
    Bar, InputError, PAIRS, decimal, parse_csv, simulate,
)

SOURCE_ID = "DUKASCOPY_NODE_CANDLE_EXPORT_USER_SUPPLIED"
SYMBOLS = ("usdjpy", "eurjpy", "eurusd")
REQUIRED = ("timestamp", "open", "high", "low", "close")
MAX_BYTES = 8_000_000
MAX_ROWS = 35_000
INTERVAL_MS = 3_600_000  # v2 accepts H1 only
FAST = 10
SLOW = 30


def load_side(path: Path) -> tuple[dict[int, dict[str, D]], str]:
    """Strictly validate supplied H1 candle CSV; no raw content in errors."""
    try:
        if path.stat().st_size > MAX_BYTES:
            raise InputError("oversize history")
        raw = path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        source = raw.decode("utf-8-sig")
        rows = csv.DictReader(source.splitlines(), strict=True)
        if rows.fieldnames not in (list(REQUIRED),
                                   list(REQUIRED) + ["volume"]):
            raise InputError("unexpected historic CSV schema")
        out: dict[int, dict[str, D]] = {}
        last = None
        for count, row in enumerate(rows, 1):
            if count > MAX_ROWS or None in row or any(v is None for v in row.values()):
                raise InputError("too many or malformed candles")
            tick = row["timestamp"]
            if not tick.isdecimal() or len(tick) != 13:
                raise InputError("timestamp must be UTC epoch milliseconds")
            t = int(tick)
            if not 946684800000 <= t <= 2051222400000 or t % INTERVAL_MS:
                raise InputError("H1 UTC aligned timestamp required")
            if last is not None and t <= last:
                raise InputError("unsorted or duplicated history")
            last = t
            values = {k: decimal(row[k], k, positive=True)
                      for k in REQUIRED if k != "timestamp"}
            if (values["low"] > min(values["open"], values["close"])
                    or values["high"] < max(values["open"], values["close"])):
                raise InputError("invalid history OHLC")
            out[t] = values
        if len(out) < SLOW + 3:
            raise InputError("insufficient H1 candles")
        return out, checksum
    except (OSError, UnicodeError, csv.Error, ValueError, OverflowError) as exc:
        raise InputError("invalid historic CSV") from exc


def prepare(files: dict[str, tuple[Path, Path]], *,
            fast: int = FAST, slow: int = SLOW,
            max_missing_pct: str = "2") -> tuple[list[Bar], dict]:
    """Align 3 pair/2 side H1 histories, excluding only disclosed gaps.

    Conversion for EUR/USD uses previous aligned USD/JPY close to avoid same
    candle future conversion. Bid/ask OHLC compression is approximate.
    """
    if type(files) is not dict or set(files) != set(SYMBOLS):
        raise InputError("exact three pairs required")
    if (type(fast) is not int or type(slow) is not int
            or fast < 2 or slow <= fast or slow > 500):
        raise InputError("invalid SMA windows")
    missing_limit = decimal(max_missing_pct, "max_missing_pct")
    if missing_limit > 10:
        raise InputError("excessive alignment allowance")
    series: dict[str, tuple[dict[int, dict[str, D]],
                            dict[int, dict[str, D]]]] = {}
    hashes: dict[str, str] = {}
    for symbol in SYMBOLS:
        paths = files[symbol]
        if (type(paths) is not tuple or len(paths) != 2
                or any(not isinstance(p, Path) for p in paths)
                or paths[0] == paths[1]):
            raise InputError("bid and ask files must differ")
        bid, bid_hash = load_side(paths[0])
        ask, ask_hash = load_side(paths[1])
        series[symbol] = bid, ask
        hashes[symbol + "_bid_sha256"] = bid_hash
        hashes[symbol + "_ask_sha256"] = ask_hash

    timesets = [set(side) for pair in series.values() for side in pair]
    common = sorted(set.intersection(*timesets))
    total = len(set.union(*timesets))
    excluded = total - len(common)
    if (len(common) < slow + 3 or not total
            or D(excluded) * 100 > D(total) * missing_limit):
        raise InputError("insufficient aligned candles or excessive gaps")

    # Reject side mismatches or crossed open/close quotes on every aligned bar.
    mids: dict[str, dict[int, dict[str, D]]] = {}
    spreads: dict[str, dict[int, D]] = {}
    for symbol in SYMBOLS:
        pair_name = PAIRS[SYMBOLS.index(symbol)]
        bid, ask = series[symbol]
        mids[symbol], spreads[symbol] = {}, {}
        for t in common:
            b, a = bid[t], ask[t]
            if any(a[k] < b[k] for k in ("open", "close")):
                raise InputError("crossed bid/ask quote")
            mid = {k: (a[k] + b[k]) / 2
                   for k in ("open", "high", "low", "close")}
            if (mid["low"] > min(mid["open"], mid["close"])
                    or mid["high"] < max(mid["open"], mid["close"])):
                raise InputError("inconsistent mid OHLC")
            pip = D("0.01") if pair_name.endswith("/JPY") else D("0.0001")
            spread = max(a["open"] - b["open"],
                         a["close"] - b["close"]) / pip
            if spread < 0 or spread > 100:
                raise InputError("unusable spread estimate")
            mids[symbol][t] = mid
            spreads[symbol][t] = spread

    # All calculations use only already-completed bars. Signal at candle t
    # is consumed by offline_backtest on the NEXT candle.
    signals: dict[str, dict[int, str]] = {}
    signal_counts = {symbol: 0 for symbol in SYMBOLS}
    for symbol in SYMBOLS:
        signals[symbol] = {}
        closes = [mids[symbol][t]["close"] for t in common]
        prev_sign = None
        for i, t in enumerate(common):
            action = "HOLD"
            if i >= slow - 1:
                short_ma = sum(closes[i-fast+1:i+1], D(0)) / fast
                long_ma = sum(closes[i-slow+1:i+1], D(0)) / slow
                sign = 1 if short_ma > long_ma else (-1 if short_ma < long_ma else 0)
                if prev_sign is not None and sign != prev_sign and sign != 0:
                    action = "LONG" if sign == 1 else "SHORT"
                    signal_counts[symbol] += 1
                prev_sign = sign
            signals[symbol][t] = action

    rows: list[Bar] = []
    for i, t in enumerate(common):
        if i == 0:
            continue  # no historical USDJPY conversion before first bar
        for symbol in SYMBOLS:
            pair = PAIRS[SYMBOLS.index(symbol)]
            mid = mids[symbol][t]
            # Explicit lag; do not use same-bar close to size an entry at open.
            conversion = (mids["usdjpy"][common[i-1]]["close"]
                          if symbol == "eurusd" else D(1))
            rows.append(Bar(datetime.fromtimestamp(t / 1000, timezone.utc),
                            pair, mid["open"], mid["high"], mid["low"],
                            mid["close"], spreads[symbol][t], conversion,
                            signals[symbol][t]))
    metadata = {
        "data_source": SOURCE_ID,
        "historical_market_data_authenticity_independently_verified": False,
        "original_data_committed_or_uploaded": False,
        "timeframe": "h1_utc", "paired_bid_ask": True,
        "fill_model": "mid_OHLC_and_max_open_close_spread_estimate",
        "conversion_model": "EURUSD_uses_previous_aligned_USDJPY_close",
        "strategy": "RESEARCH_SMA_CROSSOVER_NOT_AI_MACRO_STRATEGY",
        "sma_fast": fast, "sma_slow": slow,
        "aligned_bars_per_pair": len(common) - 1,
        "timestamps_removed_to_align": excluded,
        "total_unique_timestamps": total,
        "first_utc": rows[0].time.isoformat(),
        "last_utc": rows[-1].time.isoformat(),
        "signal_counts": signal_counts, "input_checksums": hashes,
        "known_limitations": [
            "OHLC intrabar execution cannot reconstruct tick ordering",
            "Bid/ask OHLC does not model exact executable bid/ask tick spreads",
            "No swaps, margin calls, slippage, market impact or broker contract validation",
            "External data licensing and history provenance not certified",
            "SMA strategy is only a research baseline, not AI macro hypothesis",
        ],
    }
    return rows, metadata


def run(files: dict[str, tuple[Path, Path]], **options) -> dict:
    fast = options.pop("fast", FAST)
    slow = options.pop("slow", SLOW)
    bars, meta = prepare(files, fast=fast, slow=slow)
    report = simulate(bars, **options)
    report["historical_research"] = meta
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline real-history research; NO broker/EA/orders")
    for symbol in SYMBOLS:
        parser.add_argument("--" + symbol + "-bid", required=True, type=Path)
        parser.add_argument("--" + symbol + "-ask", required=True, type=Path)
    parser.add_argument("--fast", type=int, default=FAST)
    parser.add_argument("--slow", type=int, default=SLOW)
    parser.add_argument("--stop-pips", default="20")
    parser.add_argument("--reward-r", default="2")
    parser.add_argument("--commission-jpy-per-1000-roundtrip", default="0")
    args = parser.parse_args(argv)
    files = {symbol: (getattr(args, symbol + "_bid"),
                      getattr(args, symbol + "_ask")) for symbol in SYMBOLS}
    try:
        report = run(files, fast=args.fast, slow=args.slow,
                     stop_pips=args.stop_pips, reward_r=args.reward_r,
                     commission_jpy_per_1000_roundtrip=
                     args.commission_jpy_per_1000_roundtrip)
    except (InputError, OSError, UnicodeError, ValueError, ArithmeticError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "error": "INVALID_OR_UNVERIFIED_HISTORICAL_INPUT"}))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
