"""Read-only MT4 DEMO quote-contract observation audit.

Collects bounded CSV evidence of observed spreads, quote time spacing and
broker-reported contract terms. Neither PC nor broker timestamps are
independently attested. Spread samples do NOT prove future execution cost,
commission, slippage, swaps, or the broker's margin/tickvalue correctness.

No broker orders, network, paid inference, state/latch updates or restarts.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from research import final_paper_engine as paper
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_mt4_quote_contract_evidence_v1"
NAME = re.compile(r"^FxPaperQuote_[0-9]{8}_[0-9]{6}\.csv$")
MAX_FILES = 10


def _sample(file: Path) -> dict:
    if (not file.is_file() or file.is_symlink()
            or any(p.is_symlink() for p in file.parents)
            or not 0 < file.stat().st_size <= 4500):
        raise InputError("unsafe quote evidence file")
    try:
        rows = list(csv.DictReader(
            file.read_text("utf-8-sig").splitlines(), strict=True))
        if len(rows) != 3 or any(
                set(row) != set(paper.QUOTE_FIELDS) or None in row
                for row in rows):
            raise InputError("unexpected three-pair quote CSV")
        captures = {int(row["capture_epoch_utc_pc"]) for row in rows}
        if len(captures) != 1:
            raise InputError("non-atomic capture epochs")
        capture = captures.pop()
        if capture <= 0:
            raise InputError("invalid quote epoch")
        data = paper.validate_quotes(
            file, now=datetime.fromtimestamp(capture+1, tz=timezone.utc))
    except (UnicodeError, csv.Error, ValueError, TypeError,
            OverflowError, OSError) as exc:
        raise InputError("invalid quoted contract observation") from exc
    return {"capture_epoch":capture,
            "sha256":data["source_sha256"],
            "quotes":data["quotes"]}


def audit(folder: Path, *, now: datetime | None = None,
          max_files: int = MAX_FILES) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("aware observation clock required")
    if type(max_files) is not int or not 1 <= max_files <= MAX_FILES:
        raise InputError("quote sample cap invalid")
    if (not folder.is_dir() or folder.is_symlink()
            or any(p.is_symlink() for p in folder.parents)
            or folder.name.lower() != "files"
            or folder.parent.name.lower() != "mql4"):
        raise InputError("expected exact MT4 MQL4/Files folder")
    files = sorted((file for file in folder.glob("FxPaperQuote_*.csv")
                   if NAME.fullmatch(file.name)))
    if not files:
        raise InputError("quote archive empty")
    sampled = [_sample(file) for file in files[-max_files:]]
    epochs = [item["capture_epoch"] for item in sampled]
    if any(b <= a for a, b in zip(epochs, epochs[1:])):
        raise InputError("non-monotonic archived quote sequence")
    if len({item["sha256"] for item in sampled}) != len(sampled):
        raise InputError("reused quote file evidence")
    latest_age = int(current.timestamp()) - epochs[-1]
    if latest_age < -10:
        raise InputError("future local quote observation")
    gaps = [b-a for a, b in zip(epochs, epochs[1:])]
    per_pair = {}
    for pair in paper.PAIRS:
        q = [item["quotes"][pair] for item in sampled]
        spreads = [
            (quote["ask"]-quote["bid"])/paper.PIP[pair]
            for quote in q
        ]
        tickvalues = {str(quote["tickvalue"]) for quote in q}
        ticksizes = {str(quote["ticksize"]) for quote in q}
        minlots = {str(quote["minlot"]) for quote in q}
        lotsteps = {str(quote["step"]) for quote in q}
        maxlots = {str(quote["maxlot"]) for quote in q}
        per_pair[pair] = {
            "sample_count":len(q),
            "spread_min_pips_observed":str(min(spreads)),
            "spread_max_pips_observed":str(max(spreads)),
            "spread_mean_pips_observed":str(
                sum(spreads, Decimal("0"))/Decimal(len(spreads))),
            "broker_reported_tickvalue_unique_count":len(tickvalues),
            "broker_reported_ticksize_unique_count":len(ticksizes),
            "broker_reported_minlot_unique_count":len(minlots),
            "broker_reported_lotstep_unique_count":len(lotsteps),
            "broker_reported_maxlot_unique_count":len(maxlots),
            "broker_contract_terms_independently_verified":False,
            "full_transaction_cost_verified":False,
        }
    return {
        "schema":SCHEMA,
        "status":"MT4_QUOTE_CONTRACT_SAMPLES_RESEARCH_ONLY_NO_GO",
        "sampled_complete_three_pair_cycles":len(sampled),
        "sampled_csv_source_hash_count":len(sampled),
        "latest_quote_age_seconds_pc_derived":latest_age,
        "latest_quote_fresh_pc_derived":0 <= latest_age <= 120,
        "sampled_quote_interval_min_seconds":min(gaps) if gaps else None,
        "sampled_quote_interval_max_seconds":max(gaps) if gaps else None,
        "sampled_intervals_all_30_to_90_seconds":
            bool(gaps) and all(30 <= value <= 90 for value in gaps),
        "per_pair":per_pair,
        "broker_clock_independently_attested":False,
        "trade_commissions_verified":False,
        "slippage_distribution_verified":False,
        "swap_and_overnight_costs_verified":False,
        "realized_execution_prices_verified":False,
        "full_transaction_costs_verified":False,
        "new_virtual_entries_permitted":False,
        "new_paid_ai_calls_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="Read-only DEMO MT4 quote freshness/spread/contract sampling")
    parser.add_argument("--mt4-files",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        result=audit(args.mt4_files)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("unsafe output path")
        with args.out.open("x",encoding="utf-8") as out:
            json.dump(result,out,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,UnicodeError,TypeError,KeyError,
            ValueError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"MT4_QUOTE_CONTRACT_AUDIT_FAIL_CLOSED_NO_GO",
            "full_transaction_costs_verified":False,
            "new_virtual_entries_permitted":False,
            "new_paid_ai_calls_permitted":False,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
