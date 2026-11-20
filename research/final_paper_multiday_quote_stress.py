"""Read-only multi-NY17-day real MT4 spread stress and quote coverage.

Bounded inventory; each sampled CSV is validated as 3 original quote rows.
Detects >2x normal median bid/ask spread, quote gaps and concentrated hours.
Historical distribution cannot prove next fill, swap, independent clock or
completeness of the macro calendar. Never authorizes entries or orders.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as paper
from research.forward_risk_timeline import trading_day
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_multiday_quote_stress_v1"
NAME=re.compile(r"^FxPaperQuote_([0-9]{8}_[0-9]{6})\.csv$")
MAX_FILES=10080
MAX_INVENTORY=40000
PERCENTILE=(50,95,99)


def _p(items:list[D],percent:int)->D:
    ordered=sorted(items)
    return ordered[max(0,math.ceil(len(ordered)*percent/100)-1)]


def _fmt(value:D)->str:
    return format(value.quantize(D("0.01")),"f")


def review(folder:Path, *, max_files:int=MAX_FILES)->dict:
    if (type(max_files) is not int or not 2<=max_files<=MAX_FILES
            or not folder.is_dir() or folder.is_symlink()
            or any(p.is_symlink() for p in folder.parents)
            or folder.name.lower()!="files" or
            folder.parent.name.lower()!="mql4"):
        raise InputError("MULTIDAY_SOURCE_ROOT_UNSAFE")
    sources=[]
    for f in folder.glob("FxPaperQuote_*.csv"):
        if f.is_symlink() or f.is_dir() or NAME.fullmatch(f.name) is None:
            raise InputError("MULTIDAY_UNEXPECTED_QUOTE_SOURCE")
        sources.append(f)
        if len(sources)>MAX_INVENTORY:
            raise InputError("MULTIDAY_SOURCE_INVENTORY_LIMIT")
    sources.sort(key=lambda p:p.name)
    files=sources[-max_files:]
    if len(files)<2:
        raise InputError("MULTIDAY_NOT_ENOUGH_ORIGINAL_QUOTES")
    samples={pair:[] for pair in paper.PAIRS}
    per_day=defaultdict(lambda:{pair:[] for pair in paper.PAIRS})
    hours=set()
    epochs=[]
    delta_seconds=[]
    offsets=[]
    max_tick={pair:0 for pair in paper.PAIRS}
    day_first_last={}
    for file in files:
        stamp=NAME.fullmatch(file.name).group(1)
        try:
            epoch=int(datetime.strptime(stamp,"%Y%m%d_%H%M%S").replace(
                tzinfo=timezone.utc).timestamp())
        except (ValueError,OverflowError) as exc:
            raise InputError("MULTIDAY_FILENAME_TIMESTAMP_INVALID") from exc
        if epochs and epoch<=epochs[-1]:
            raise InputError("MULTIDAY_DUPLICATED_OR_REVERSED_TIMESTAMP")
        # Every file must pass original quote validation including independent
        # pair completeness, broker-reported contract and atomic PC epoch.
        parsed=paper.validate_quotes(
            file,now=datetime.fromtimestamp(epoch+1,tz=timezone.utc))
        if parsed["capture_epoch"]!=epoch:
            raise InputError("MULTIDAY_FILENAME_AND_CAPTURE_DISAGREE")
        try:
            rows=list(csv.DictReader(file.read_text("utf-8-sig").splitlines(),
                                     strict=True))
            if (len(rows)!=3
                    or tuple(row["pair"] for row in rows)!=paper.SYMS):
                raise InputError("MULTIDAY_QUOTE_SYMBOLS_MISMATCH")
            broker_times={int(row["broker_time_epoch_unattested"])
                          for row in rows}
            if len(broker_times)!=1:
                raise InputError("MULTIDAY_BROKER_TIME_NOT_ATOMIC")
            broker=broker_times.pop()
            offsets.append(broker-epoch)
            local=datetime.fromtimestamp(epoch,tz=timezone.utc)
            day=trading_day(local.isoformat().replace("+00:00","Z"))
            day_first_last.setdefault(day,[epoch,epoch])[1]=epoch
            hours.add(local.hour)
            for row in rows:
                pair=paper.SYMBOL_TO_PAIR[row["pair"]]
                bid=D(row["bid"])
                ask=D(row["ask"])
                spread=(ask-bid)/paper.PIP[pair]
                if not spread.is_finite() or spread<=0:
                    raise InputError("MULTIDAY_SPREAD_INVALID")
                samples[pair].append(spread)
                per_day[day][pair].append(spread)
                age=broker-int(row["tick_time_broker_epoch_unattested"])
                if not 0<=age<=30:
                    raise InputError("MULTIDAY_TICKTIME_INVALID")
                max_tick[pair]=max(max_tick[pair],age)
        except (ValueError,TypeError,csv.Error,ArithmeticError,
                UnicodeError,OverflowError) as exc:
            raise InputError("MULTIDAY_QUOTE_PARSE_INVALID") from exc
        if epochs:
            delta_seconds.append(epoch-epochs[-1])
        epochs.append(epoch)
    daily={}
    baseline={pair:_p(samples[pair],50) for pair in paper.PAIRS}
    for day,bucket in sorted(per_day.items()):
        daily[day]={
            "captured_complete_cycles":len(bucket[paper.PAIRS[0]]),
            "first_epoch_pc_unattested":day_first_last[day][0],
            "last_epoch_pc_unattested":day_first_last[day][1],
            "spread":{
                pair:{
                    "median_pips":_fmt(_p(v,50)),
                    "max_pips":_fmt(max(v)),
                    "at_least_twice_global_median_count":
                        sum(x>=baseline[pair]*2 for x in v)
                } for pair,v in bucket.items()
            },
        }
    summary={}
    for pair in paper.PAIRS:
        v=samples[pair]
        med=baseline[pair]
        run=best=0
        for x in v:
            run=run+1 if x>=med*2 else 0
            best=max(best,run)
        summary[pair]={
            "samples":len(v),
            "observed_min_spread_pips":_fmt(min(v)),
            "observed_median_spread_pips":_fmt(med),
            "observed_p95_spread_pips":_fmt(_p(v,95)),
            "observed_p99_spread_pips":_fmt(_p(v,99)),
            "observed_max_spread_pips":_fmt(max(v)),
            "observed_widest_to_median_ratio":
                _fmt(max(v)/med),
            "at_least_twice_observed_median_count":
                sum(x>=med*2 for x in v),
            "longest_consecutive_twice_median_samples":best,
            "broker_relative_tick_age_max_seconds":max_tick[pair],
            "execution_slippage_or_swap_proven":False,
        }
    count=len(files)
    # "research coverage" is a count of observed source time buckets only,
    # not an assertion about hours the exchange should have been active.
    distinct_days=len(daily)
    observed_hours=len(hours)
    return {
        "schema":SCHEMA,
        "status":"MULTIDAY_REAL_QUOTE_STRESS_RESEARCH_HOLD_NO_GO",
        "source_files_in_inventory":len(sources),
        "original_complete_quote_cycles_scanned":count,
        "first_quote_epoch_pc_unattested":epochs[0],
        "last_quote_epoch_pc_unattested":epochs[-1],
        "distinct_ny17_observed_day_buckets":distinct_days,
        "distinct_utc_observed_hour_buckets":observed_hours,
        "total_minutes_observed_approx":count,
        "quote_intervals_above_90_seconds":
            sum(g>90 for g in delta_seconds),
        "quote_intervals_above_600_seconds":
            sum(g>600 for g in delta_seconds),
        "longest_quote_gap_seconds":max(delta_seconds),
        "broker_pc_offset_min_seconds":min(offsets),
        "broker_pc_offset_max_seconds":max(offsets),
        "broker_pc_offset_jitter_seconds":max(offsets)-min(offsets),
        "observed_three_pairs":summary,
        "per_ny17_day":daily,
        "minimum_three_ny17_days_observed_research_only":distinct_days>=3,
        "at_least_12_utc_hours_observed_research_only":observed_hours>=12,
        "full_trading_day_coverage_proven":False,
        "independently_attested_broker_clock":False,
        "complete_official_macro_events_and_consensus_proven":False,
        "full_execution_spread_slippage_swap_cost_proven":False,
        "model_profitability_proven":False,
        "new_paid_ai_calls_permitted":False,
        "new_virtual_positions_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="No-order original MT4 DEMO quote multiday stress")
    p.add_argument("--mt4-files",required=True,type=Path)
    p.add_argument("--max-files",type=int,default=MAX_FILES)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        report=review(args.mt4_files,max_files=args.max_files)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("MULTIDAY_REPORT_PATH_UNSAFE")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False))
        return 0
    except (InputError,OSError,ValueError,TypeError,KeyError,
            OverflowError,UnicodeError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"MULTIDAY_QUOTE_STRESS_FAIL_CLOSED_NO_GO",
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
