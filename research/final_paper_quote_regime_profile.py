"""No-trade, real DEMO MT4 time/spread regime evidence across three FX pairs.

Uses bounded original quote CSVs, never artificial market data. PC and broker
clocks are not independently verified. Spread is not guaranteed executable
and excludes commission, slippage, spread widening and swap costs.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as paper
from research.forward_risk_timeline import trading_day
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_quote_regime_profile_v1"
NAME=re.compile(r"^FxPaperQuote_([0-9]{8}_[0-9]{6})\.csv$")
MAX_FILES=240


def _percentile(items:list[D], pct:int)->D:
    values=sorted(items)
    return values[max(0,math.ceil(len(values)*pct/100)-1)]


def summarize(folder:Path, *, max_files:int=MAX_FILES)->dict:
    if (type(max_files) is not int or not 2<=max_files<=MAX_FILES
            or not folder.is_dir() or folder.is_symlink()
            or any(p.is_symlink() for p in folder.parents)
            or folder.name.lower()!="files"
            or folder.parent.name.lower()!="mql4"):
        raise InputError("QUOTE_REGIME_SOURCE_UNSAFE")
    matched=[]
    for file in folder.glob("FxPaperQuote_*.csv"):
        if NAME.fullmatch(file.name) is None or file.is_symlink():
            raise InputError("QUOTE_REGIME_FILE_UNSAFE")
        matched.append(file)
        if len(matched)>20000:
            raise InputError("QUOTE_REGIME_SOURCE_EXCESSIVE")
    matched.sort(key=lambda f:f.name)
    files=matched[-max_files:]
    if len(files)<2:
        raise InputError("QUOTE_REGIME_TOO_FEW_REAL_QUOTES")
    spreads={pair:[] for pair in paper.PAIRS}
    tick_age={pair:[] for pair in paper.PAIRS}
    pc_offset=[]
    epochs=[]
    regime_hours=set()
    ny_buckets=set()
    for f in files:
        match=NAME.fullmatch(f.name)
        try:
            name_epoch=int(datetime.strptime(
                match.group(1),"%Y%m%d_%H%M%S").replace(
                    tzinfo=timezone.utc).timestamp())
        except ValueError as exc:
            raise InputError("QUOTE_REGIME_FILENAME_TIME_INVALID") from exc
        # validate_quotes verifies all 3 symbols / contract / quote age.
        source=paper.validate_quotes(
            f,now=datetime.fromtimestamp(name_epoch+1,tz=timezone.utc))
        if source["capture_epoch"]!=name_epoch:
            raise InputError("QUOTE_REGIME_FILE_CLOCK_MISMATCH")
        if epochs and name_epoch<=epochs[-1]:
            raise InputError("QUOTE_REGIME_REVERSED_CAPTURE")
        epochs.append(name_epoch)
        if not 0<f.stat().st_size<=4500:
            raise InputError("QUOTE_REGIME_UNSAFE_SIZE")
        try:
            rows=list(csv.DictReader(f.read_text("utf-8-sig").splitlines(),
                                     strict=True))
            if len(rows)!=3 or tuple(r["pair"] for r in rows)!=paper.SYMS:
                raise InputError("QUOTE_REGIME_BAD_PAIR_ROWS")
            broker_times={int(r["broker_time_epoch_unattested"]) for r in rows}
            if len(broker_times)!=1:
                raise InputError("QUOTE_REGIME_NONATOMIC_BROKER_TIME")
            broker=broker_times.pop()
            pc_offset.append(broker-name_epoch)
            for row in rows:
                pair=paper.SYMBOL_TO_PAIR[row["pair"]]
                spread=(D(row["ask"])-D(row["bid"]))/paper.PIP[pair]
                if spread<=0:
                    raise InputError("QUOTE_REGIME_NONPOSITIVE_SPREAD")
                spreads[pair].append(spread)
                delta=broker-int(row["tick_time_broker_epoch_unattested"])
                if not 0<=delta<=30:
                    raise InputError("QUOTE_REGIME_TICK_AGE_INVALID")
                tick_age[pair].append(delta)
        except (csv.Error,ValueError,ArithmeticError,UnicodeError,
                OverflowError) as exc:
            raise InputError("QUOTE_REGIME_MALFORMED_DATA") from exc
        dt=datetime.fromtimestamp(name_epoch,tz=timezone.utc)
        regime_hours.add(dt.hour)
        ny_buckets.add(trading_day(dt.isoformat().replace("+00:00","Z")))
    gaps=[b-a for a,b in zip(epochs,epochs[1:])]
    regimes={}
    for pair in paper.PAIRS:
        v=spreads[pair]
        regimes[pair]={
            "sample_count":len(v),
            "observed_spread_min_pips":format(min(v),".2f"),
            "observed_spread_median_pips":format(_percentile(v,50),".2f"),
            "observed_spread_p95_pips":format(_percentile(v,95),".2f"),
            "observed_spread_max_pips":format(max(v),".2f"),
            "broker_relative_tick_age_max_seconds":max(tick_age[pair]),
            "observed_spread_and_ticktime_independently_attested":False,
        }
    return {
        "schema":SCHEMA,
        "status":"THREE_PAIR_REAL_QUOTE_REGIME_RESEARCH_ONLY_NO_GO",
        "observed_complete_cycles":len(files),
        "first_quote_epoch_pc_unattested":epochs[0],
        "last_quote_epoch_pc_unattested":epochs[-1],
        "quote_interval_min_seconds":min(gaps),
        "quote_interval_max_seconds":max(gaps),
        "quote_intervals_above_90_seconds":sum(g>90 for g in gaps),
        "unique_utc_hours":sorted(regime_hours),
        "distinct_ny17_trading_day_buckets":len(ny_buckets),
        "brokertime_minus_pc_capture_seconds_min":min(pc_offset),
        "brokertime_minus_pc_capture_seconds_max":max(pc_offset),
        "brokertime_minus_pc_capture_seconds_jitter":
            max(pc_offset)-min(pc_offset),
        "three_pair_spread_and_tick_age":regimes,
        "commission_independently_verified":False,
        "slippage_independently_verified":False,
        "swap_independently_verified":False,
        "full_executable_transaction_cost_verified":False,
        "broker_clock_independently_attested":False,
        "future_market_regime_representativeness_proven":False,
        "new_paid_ai_calls_permitted":False,
        "new_virtual_positions_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Three-pair real MT4 DEMO quote regime, offline")
    p.add_argument("--mt4-files",required=True,type=Path)
    p.add_argument("--max-files",type=int,default=MAX_FILES)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        result=summarize(args.mt4_files,max_files=args.max_files)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("QUOTE_REGIME_OUTPUT_UNSAFE")
        with args.out.open("x",encoding="utf-8") as file:
            json.dump(result,file,ensure_ascii=False,indent=2)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,UnicodeError,ValueError,TypeError,KeyError,
            OSError,ArithmeticError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"QUOTE_REGIME_FAIL_CLOSED_NO_GO",
            "new_paid_ai_calls_permitted":False,
            "new_virtual_positions_permitted":False,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
