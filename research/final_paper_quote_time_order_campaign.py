"""Research-only full-span MT4 original quote clock-ordering campaign.

Reads original 3-pair CSVs; detects each invalid source without deleting,
mutating, normalizing, or silently promoting valid segments to trading GO.
Only fixed codes, derived seconds, file basenames and SHA fingerprints
leave the forensic boundary. No broker orders, paid API or live-state writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_engine as engine
from research import final_paper_quote_contract_forensics as forensic
from research import final_paper_multiday_quote_stress as multiday
from research.forward_risk_timeline import trading_day
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_quote_time_order_campaign_v1"
MAX_INVALID_EXAMPLES=25
MAX_SELECTED_FILES=10080


def _day(epoch:int)->str:
    dt=datetime.fromtimestamp(epoch,tz=timezone.utc)
    return trading_day(dt.isoformat().replace("+00:00","Z"))


def _future_leads(file:Path)->dict[str,int]:
    """Only seconds of clock inversion, never raw server timestamps."""
    _,rows,_=forensic._parse_raw(file)
    leads={}
    for row in rows:
        sym=row.get("pair")
        if sym not in engine.SYMS:
            continue
        try:
            tick=int(row["tick_time_broker_epoch_unattested"])
            broker=int(row["broker_time_epoch_unattested"])
        except (ValueError,TypeError,OverflowError,KeyError):
            continue
        if 0<tick-broker<=86400:
            leads[sym]=max(leads.get(sym,0),tick-broker)
        elif tick-broker>86400:
            leads[sym]=86401  # bounded over-24h invalid category
    return leads


def review(root:Path, *, max_files:int=MAX_SELECTED_FILES)->dict:
    forensic._valid_root(root)
    if type(max_files) is not int or not 2<=max_files<=MAX_SELECTED_FILES:
        raise InputError("TIME_CAMPAIGN_MAX_FILES_OUT_OF_RANGE")
    originals=forensic._inventory(root)
    selected=originals[-max_files:]
    if len(selected)<2:
        raise InputError("TIME_CAMPAIGN_MIN_TWO_ORIGINALS_REQUIRED")
    valid=0
    invalid=0
    by_day=defaultdict(lambda:{"source_count":0,"valid_count":0,
                               "invalid_count":0})
    violation_counts=Counter()
    pair_future_counts={sym:0 for sym in engine.SYMS}
    pair_max_future={sym:0 for sym in engine.SYMS}
    examples=[]
    max_valid_streak=streak=0
    valid_segments=0
    last_valid_epoch=None
    prior_epoch=None
    gap_gt_90=0
    gap_gt_600=0
    source_chain=b"\x00"*32
    for idx,file in enumerate(selected,1):
        epoch=forensic._epoch(file.name)
        if prior_epoch is not None:
            if epoch<=prior_epoch:
                raise InputError("TIME_CAMPAIGN_REVERSED_FILENAME_EPOCH")
            gap_gt_90+=int(epoch-prior_epoch>90)
            gap_gt_600+=int(epoch-prior_epoch>600)
        prior_epoch=epoch
        day=_day(epoch)
        by_day[day]["source_count"]+=1

        # Copy of an original is never synthesized. A malformed file is
        # preserved and counted as an anomaly, never accepted as valid.
        if (file.is_symlink() or not file.is_file()
                or not 0<file.stat().st_size<=4500):
            raise InputError("TIME_CAMPAIGN_ORIGINAL_UNSAFE")
        try:
            sample=engine.validate_quotes(
                file,now=datetime.fromtimestamp(epoch+1,tz=timezone.utc))
            source_sha=sample["source_sha256"]
            source_ok=True
            codes=[]
            leads={}
        except (InputError,ValueError,TypeError,ArithmeticError,
                OSError,UnicodeError,OverflowError):
            source_ok=False
            try:
                inspected=forensic._classify(file)
                source_sha=inspected["sha256_local_original"]
                issues=inspected["issues"]
                codes=sorted({i["code"] for i in issues})
                if not codes:
                    codes=["ENGINE_REJECTED_UNCLASSIFIED_SOURCE"]
                leads=_future_leads(file)
            except (InputError,ValueError,TypeError,ArithmeticError,
                    OSError,UnicodeError,OverflowError):
                # Safe fallback: do not bypass unreadable source.
                source_sha=hashlib.sha256(file.read_bytes()).hexdigest()
                codes=["UNCLASSIFIABLE_ORIGINAL_SOURCE"]
                leads={}
        source_chain=hashlib.sha256(
            source_chain+file.name.encode("ascii")+
            bytes.fromhex(source_sha)).digest()
        if source_ok:
            valid+=1
            by_day[day]["valid_count"]+=1
            if last_valid_epoch is None or epoch-last_valid_epoch>90:
                valid_segments+=1
                streak=0
            streak+=1
            max_valid_streak=max(max_valid_streak,streak)
            last_valid_epoch=epoch
        else:
            invalid+=1
            by_day[day]["invalid_count"]+=1
            violation_counts.update(codes)
            if len(examples)<MAX_INVALID_EXAMPLES:
                examples.append({
                    "source_ordinal":idx,
                    "source_basename":file.name,
                    "source_sha256_local_only":source_sha,
                    "issue_codes":codes,
                })
            for sym,lead in leads.items():
                pair_future_counts[sym]+=1
                pair_max_future[sym]=max(pair_max_future[sym],lead)
            last_valid_epoch=None
            streak=0
    return {
        "schema":SCHEMA,
        "status":"SOURCE_TIME_ORDER_ANOMALY_CAMPAIGN_RESEARCH_NO_GO",
        "observed_original_inventory_total":len(originals),
        "reviewed_original_count":len(selected),
        "strict_engine_valid_original_count":valid,
        "invalid_original_count":invalid,
        "all_originals_passed_strict_engine":invalid==0,
        "first_source_basename":selected[0].name,
        "last_source_basename":selected[-1].name,
        "original_sequence_sha256_local_only":source_chain.hex(),
        "per_ny17_day":dict(sorted(by_day.items())),
        "invalid_condition_occurrences":dict(sorted(violation_counts.items())),
        "future_tick_after_broker_count_by_pair":pair_future_counts,
        "future_tick_lead_seconds_max_by_pair":pair_max_future,
        "max_86401_means_future_delta_exceeded_24h":True,
        "first_invalid_originals_up_to_25":examples,
        "time_gaps_above_90s_between_all_source_files":gap_gt_90,
        "time_gaps_above_600s_between_all_source_files":gap_gt_600,
        "valid_segments_around_invalid_or_missing_minutes":valid_segments,
        "longest_valid_contiguous_sample_count":max_valid_streak,
        "invalid_csv_removed_or_repaired":False,
        "partial_valid_segments_can_enable_new_virtual_entries":False,
        "full_macro_calendar_consensus_and_clock_attested":False,
        "new_paid_ai_calls_permitted":False,
        "new_virtual_positions_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Read-only time-order exception campaign for original MT4 DEMO sources")
    p.add_argument("--mt4-files",required=True,type=Path)
    p.add_argument("--max-files",default=MAX_SELECTED_FILES,type=int)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        report=review(args.mt4_files,max_files=args.max_files)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("TIME_CAMPAIGN_OUTPUT_NOT_NEW")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,TypeError,ValueError,
            UnicodeError,OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"SOURCE_TIME_ORDER_CAMPAIGN_FAIL_CLOSED_NO_GO",
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
