"""Read-only forensic classification of an ORIGINAL invalid Rakuten DEMO quote.

The active paper engine and STRICT multi-day gate are intentionally untouched.
This module locates exactly one original quote and compares each observed field
with the current engine rules, without printing bid/ask, account identifiers
or complete local paths. Output is always RESEARCH_HOLD_NO_GO.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal as D, InvalidOperation
from pathlib import Path

from research import final_paper_engine as engine
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_quote_contract_forensics_v1"
NAME=re.compile(r"^FxPaperQuote_([0-9]{8}_[0-9]{6})\.csv$")
MAX_FILES=40000
MAX_SOURCE_BYTES=4500
DECIMAL_FIELDS=(
    "bid","ask","tickvalue_jpy_broker_reported",
    "ticksize_broker_reported","min_lot_broker_reported",
    "lot_step_broker_reported","max_lot_broker_reported",
    "point_broker_reported",
)
TIME_FIELDS=(
    "tick_time_broker_epoch_unattested",
    "broker_time_epoch_unattested","capture_epoch_utc_pc",
)


def _epoch(name:str)->int:
    m=NAME.fullmatch(name)
    if not m:
        raise InputError("FORENSIC_QUOTE_FILENAME_INVALID")
    try:
        return int(datetime.strptime(m.group(1),"%Y%m%d_%H%M%S").replace(
            tzinfo=timezone.utc).timestamp())
    except (ValueError,OverflowError) as exc:
        raise InputError("FORENSIC_QUOTE_FILENAME_INVALID") from exc


def _valid_root(root:Path)->None:
    if (not root.is_dir() or root.is_symlink()
            or any(p.is_symlink() for p in root.parents)
            or root.name.lower()!="files"
            or root.parent.name.lower()!="mql4"):
        raise InputError("FORENSIC_MQL4_FILES_ROOT_REQUIRED")


def _inventory(root:Path)->list[Path]:
    paths=[]
    for file in root.glob("FxPaperQuote_*.csv"):
        if (file.is_symlink() or not file.is_file()
                or NAME.fullmatch(file.name) is None):
            raise InputError("FORENSIC_UNEXPECTED_INVENTORY_FILE")
        paths.append(file)
        if len(paths)>MAX_FILES:
            raise InputError("FORENSIC_SOURCE_INVENTORY_LIMIT")
    paths.sort(key=lambda f:f.name)
    return paths


def _issue(items:list[dict],row:int,code:str,field:str|None=None,
           symbol:str|None=None)->None:
    if len(items)>=40:
        return
    entry={"row_ordinal":row,"code":code}
    if field is not None:
        entry["field"]=field
    if symbol in engine.SYMS:
        entry["symbol"]=symbol
    items.append(entry)


def _parse_raw(file:Path)->tuple[bytes,list[dict],bool]:
    if (not file.is_file() or file.is_symlink()
            or any(p.is_symlink() for p in file.parents)
            or not 0<file.stat().st_size<=MAX_SOURCE_BYTES):
        raise InputError("FORENSIC_TARGET_ORIGINAL_UNSAFE")
    raw=file.read_bytes()
    if b"\x00" in raw:
        raise InputError("FORENSIC_TARGET_BYTES_INVALID")
    try:
        reader=csv.DictReader(raw.decode("utf-8-sig").splitlines(),strict=True)
        names=tuple(reader.fieldnames or ())
        rows=list(reader)
    except (csv.Error,UnicodeError) as exc:
        raise InputError("FORENSIC_TARGET_CSV_MALFORMED") from exc
    if len(rows)>5:
        raise InputError("FORENSIC_TOO_MANY_CSV_ROWS")
    return raw,rows,names==engine.QUOTE_FIELDS


def _classify(file:Path)->dict:
    name_epoch=_epoch(file.name)
    raw,rows,header_match=_parse_raw(file)
    issues=[]
    if not header_match:
        _issue(issues,0,"ORIGINAL_HEADER_MISMATCH")
    if len(rows)!=3:
        _issue(issues,0,"REQUIRED_THREE_ROWS_MISSING_OR_EXTRA")
    captures=set()
    broker_epochs=set()
    for idx,row in enumerate(rows,1):
        sym=row.get("pair")
        if sym not in engine.SYMS:
            _issue(issues,idx,"UNSUPPORTED_CURRENCY_PAIR")
        elif idx<=3 and sym!=engine.SYMS[idx-1]:
            _issue(issues,idx,"CURRENCY_PAIR_ORDER_INVALID",symbol=sym)
        if (None in row or set(row)!=set(engine.QUOTE_FIELDS)):
            _issue(issues,idx,"ROW_HEADER_OR_FIELD_COUNT_MISMATCH",
                   symbol=sym)
            continue
        times={}
        for field in TIME_FIELDS:
            try:
                value=row[field]
                if not re.fullmatch(r"[0-9]+",value):
                    raise ValueError("integer expected")
                parsed=int(value)
                times[field]=parsed
                if parsed<=0:
                    _issue(issues,idx,"TIME_NONPOSITIVE",
                           field,sym)
            except (TypeError,ValueError,OverflowError):
                _issue(issues,idx,"TIME_NOT_POSITIVE_INTEGER",
                       field,sym)
        values={}
        for field in DECIMAL_FIELDS:
            value=row.get(field)
            try:
                if type(value) is not str:
                    raise InvalidOperation("missing")
                number=D(value)
                if not number.is_finite() or number<=0:
                    _issue(issues,idx,"NUMERIC_FIELD_NOT_POSITIVE_FINITE",
                           field,sym)
                else:
                    values[field]=number
            except (InvalidOperation,ValueError,TypeError):
                _issue(issues,idx,"NUMERIC_FIELD_NOT_VALID_DECIMAL",
                       field,sym)
        bid=values.get("bid")
        ask=values.get("ask")
        if bid is not None and ask is not None and ask<=bid:
            _issue(issues,idx,"ASK_NOT_GREATER_THAN_BID","ask",sym)
        low=values.get("min_lot_broker_reported")
        high=values.get("max_lot_broker_reported")
        step=values.get("lot_step_broker_reported")
        if low is not None and high is not None and low>high:
            _issue(issues,idx,"MIN_LOT_EXCEEDS_MAX_LOT",
                   "min_lot_broker_reported",sym)
        if step is not None and high is not None and step>high:
            _issue(issues,idx,"LOT_STEP_EXCEEDS_MAX_LOT",
                   "lot_step_broker_reported",sym)
        broker=times.get("broker_time_epoch_unattested")
        tick=times.get("tick_time_broker_epoch_unattested")
        if broker is not None and tick is not None:
            delta=broker-tick
            if delta<0:
                _issue(issues,idx,"TICK_TIME_AFTER_BROKER_TIME",
                       "tick_time_broker_epoch_unattested",sym)
            elif delta>30:
                _issue(issues,idx,"BROKER_RELATIVE_TICK_AGE_OVER_30S",
                       "tick_time_broker_epoch_unattested",sym)
        capture=times.get("capture_epoch_utc_pc")
        if capture is not None:
            captures.add(capture)
            if capture!=name_epoch:
                _issue(issues,idx,"CAPTURE_TIME_DIFFERS_FROM_FILENAME",
                       "capture_epoch_utc_pc",sym)
        if broker is not None:
            broker_epochs.add(broker)
    if len(captures)>1:
        _issue(issues,0,"THREE_PAIR_CAPTURE_NOT_ATOMIC")
    if len(broker_epochs)>1:
        _issue(issues,0,"BROKER_TIMES_NOT_ATOMIC")
    try:
        engine.validate_quotes(
            file,now=datetime.fromtimestamp(name_epoch+1,tz=timezone.utc))
        engine_pass=True
    except (InputError,ValueError,TypeError,OverflowError,ArithmeticError,
            OSError,UnicodeError):
        engine_pass=False
    # The multi-day reviewer adds an exact filename-vs-PC capture match
    # which the live engine only checks for freshness. Distinguish them:
    # both are research data checks, and neither authorizes trading.
    source_pass=engine_pass and not issues
    if not engine_pass and not issues:
        _issue(issues,0,"ENGINE_REJECTED_UNCLASSIFIED_SOURCE")
    if hashlib.sha256(file.read_bytes()).digest()!=hashlib.sha256(raw).digest():
        raise InputError("FORENSIC_SOURCE_CHANGED_DURING_INSPECTION")
    return {
        "sha256_local_original":hashlib.sha256(raw).hexdigest(),
        "byte_length":len(raw),
        "engine_quote_validator_passed":engine_pass,
        "strict_multiday_source_passed":source_pass,
        "issues":issues,
    }


def investigate(root:Path,name:str, *, neighbors:int=2)->dict:
    _valid_root(root)
    _epoch(name)
    if type(neighbors) is not int or not 0<=neighbors<=3:
        raise InputError("FORENSIC_NEIGHBOR_RANGE_INVALID")
    files=_inventory(root)
    names=[f.name for f in files]
    if name not in names:
        raise InputError("FORENSIC_TARGET_NOT_IN_ORIGINAL_INVENTORY")
    target=root/name
    inspected=_classify(target)
    pos=names.index(name)
    adjacent=[]
    for i in range(max(0,pos-neighbors),min(len(names),pos+neighbors+1)):
        if i==pos:
            continue
        file=files[i]
        # No quote contents leave the local source folder.
        item=_classify(file)
        adjacent.append({
            "source_basename":file.name,
            "source_sha256_local_only":item["sha256_local_original"],
            "engine_quote_validator_passed":item["engine_quote_validator_passed"],
            "strict_multiday_source_passed":item["strict_multiday_source_passed"],
            "issue_codes":[entry["code"] for entry in item["issues"][:8]],
        })
    return {
        "schema":SCHEMA,
        "status":"TARGET_SOURCE_FIELD_FORENSICS_RESEARCH_HOLD_NO_GO",
        "target_basename":name,
        "original_sha256_local_only":inspected["sha256_local_original"],
        "original_byte_length":inspected["byte_length"],
        "engine_quote_validator_passed":inspected["engine_quote_validator_passed"],
        "strict_multiday_source_passed":inspected["strict_multiday_source_passed"],
        "issue_count":len(inspected["issues"]),
        "issues_without_source_values":inspected["issues"],
        "nearby_original_sources":adjacent,
        "original_csv_modified":False,
        "original_broker_quote_contents_exposed":False,
        "historical_source_can_be_silently_skipped":False,
        "overall_multiday_gate_passed":False,
        "original_1513_error_repaired":False,
        "market_time_independently_attested":False,
        "broker_execution_costs_verified":False,
        "new_paid_ai_calls_permitted":False,
        "new_virtual_positions_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Source-preserving exact-pair quote contract forensics")
    p.add_argument("--mt4-files",type=Path,required=True)
    p.add_argument("--target",type=str,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        report=investigate(args.mt4_files,args.target)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("FORENSIC_OUTPUT_MUST_BE_NEW")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,TypeError,ValueError,UnicodeError,
            OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"TARGET_SOURCE_FORENSICS_FAIL_CLOSED_NO_GO",
            "original_csv_modified":False,
            "original_broker_quote_contents_exposed":False,
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
