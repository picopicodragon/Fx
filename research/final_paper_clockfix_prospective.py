"""Read-only pre/post MT4 clock-fix quality evidence, never trade authority.

Recomputes the immutable 3020-file historical source chain and verifies
the user's previously recorded 4 anomaly baseline. Compares only originals
whose capture filename is AFTER an explicit, operator-supplied cutover time.
No speculative "cleaning" of original data; no proof that the new EA was
actually compiled, loaded, or exclusively attached to Rakuten MT4.

Even a perfect post-cutover result is only RESEARCH_NO_GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_engine as engine
from research import final_paper_quote_contract_forensics as forensic
from research.forward_risk_timeline import trading_day
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_clockfix_prospective_evidence_v1"
SOURCE_SCHEMA="fx_final_paper_quote_time_order_campaign_v1"
BASELINE={
    "observed_original_inventory_total":3020,
    "reviewed_original_count":3020,
    "strict_engine_valid_original_count":3016,
    "invalid_original_count":4,
    "invalid_condition_occurrences":{"TICK_TIME_AFTER_BROKER_TIME":4},
    "first_source_basename":"FxPaperQuote_20261118_022249.csv",
    "last_source_basename":"FxPaperQuote_20261120_050056.csv",
    "original_sequence_sha256_local_only":
        "759374e5043be39ebe14ba3c38512832900895a44921f52d29b859c3838e6ef5",
    "per_ny17_day":{
        "2026-11-17":{"source_count":1176,"valid_count":1176,"invalid_count":0},
        "2026-11-18":{"source_count":1424,"valid_count":1420,"invalid_count":4},
        "2026-11-19":{"source_count":420,"valid_count":420,"invalid_count":0},
    },
    "future_tick_after_broker_count_by_pair":{
        "USDJPY":4,"EURJPY":1,"EURUSD":0
    },
    "future_tick_lead_seconds_max_by_pair":{
        "USDJPY":1,"EURJPY":1,"EURUSD":0
    },
    "time_gaps_above_90s_between_all_source_files":14,
    "time_gaps_above_600s_between_all_source_files":0,
    "valid_segments_around_invalid_or_missing_minutes":19,
    "longest_valid_contiguous_sample_count":891,
    "first_invalid_originals_up_to_25":[
        {"source_ordinal":1513,"source_basename":"FxPaperQuote_20261119_035152.csv",
         "source_sha256_local_only":"3b272c81b794a12776319c8947d813f82540067b17049f022e33761833ca9505",
         "issue_codes":["TICK_TIME_AFTER_BROKER_TIME"]},
        {"source_ordinal":1584,"source_basename":"FxPaperQuote_20261119_050352.csv",
         "source_sha256_local_only":"5a738a666ca2188ef3cbb95b54d59c9a9dc4556a7c3669138209352ff73f601c",
         "issue_codes":["TICK_TIME_AFTER_BROKER_TIME"]},
        {"source_ordinal":2476,"source_basename":"FxPaperQuote_20261119_195555.csv",
         "source_sha256_local_only":"581530b324222a7bc4b6409fd4b30a024f8aaa92c79a47b9ed455eed869378ff",
         "issue_codes":["TICK_TIME_AFTER_BROKER_TIME"]},
        {"source_ordinal":2494,"source_basename":"FxPaperQuote_20261119_201355.csv",
         "source_sha256_local_only":"e3f6cc23cc5bff37eccb1a7224e2e29767a36ef3e5cec633d51e00edbb3748e0",
         "issue_codes":["TICK_TIME_AFTER_BROKER_TIME"]},
    ],
}
MAX_BYTES=45_000
MAX_POST=10080


def _read_baseline(path:Path)->dict:
    if (not path.is_file() or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
            or not 0<path.stat().st_size<=MAX_BYTES):
        raise InputError("CLOCKFIX_BASELINE_REPORT_UNSAFE")
    try:
        data=json.loads(path.read_text("utf-8-sig"))
    except (UnicodeError,ValueError) as exc:
        raise InputError("CLOCKFIX_BASELINE_REPORT_INVALID") from exc
    if (type(data) is not dict
            or data.get("schema")!=SOURCE_SCHEMA
            or data.get("status")!="SOURCE_TIME_ORDER_ANOMALY_CAMPAIGN_RESEARCH_NO_GO"
            or data.get("invalid_condition_occurrences")!=
               BASELINE["invalid_condition_occurrences"]
            or data.get("all_originals_passed_strict_engine") is not False
            or data.get("runtime_go_no_go")!="NO_GO"
            or data.get("new_virtual_positions_permitted") is not False
            or data.get("new_paid_ai_calls_permitted") is not False
            or data.get("demo_orders_permitted") is not False
            or data.get("real_orders_permitted") is not False
            or data.get("safety_hold_latched") is not True
            or any(data.get(key)!=value for key,value in BASELINE.items())):
        raise InputError("CLOCKFIX_BASELINE_EVIDENCE_NOT_MATCHING_OBSERVED")
    return data


def _cutover(value:str)->int:
    if type(value) is not str:
        raise InputError("CLOCKFIX_CUTOVER_UTC_REQUIRED")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise InputError("CLOCKFIX_CUTOVER_UTC_INVALID") from exc
    if dt.tzinfo is None or dt.utcoffset().total_seconds()!=0:
        raise InputError("CLOCKFIX_CUTOVER_NOT_UTC")
    return int(dt.timestamp())


def _hash(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def _source_sha(path:Path)->str:
    if (path.is_symlink() or not path.is_file()
            or not 0<path.stat().st_size<=4500):
        raise InputError("CLOCKFIX_ORIGINAL_SOURCE_UNSAFE")
    return _hash(path.read_bytes())


def audit(folder:Path,baseline_path:Path,cutover_utc:str,
          *,candidate_source:Path)->dict:
    forensic._valid_root(folder)
    baseline=_read_baseline(baseline_path)
    cutoff=_cutover(cutover_utc)
    historic_end=forensic._epoch(BASELINE["last_source_basename"])
    if cutoff<=historic_end:
        raise InputError("CLOCKFIX_CUTOVER_MUST_FOLLOW_BASELINE")
    if (not candidate_source.is_file() or candidate_source.is_symlink()
            or any(p.is_symlink() for p in candidate_source.parents)
            or not 0<candidate_source.stat().st_size<=20000):
        raise InputError("CLOCKFIX_CANDIDATE_SOURCE_UNSAFE")
    candidate_bytes=candidate_source.read_bytes()
    if (b'PAPER_BUILD_TAG "FXPAPER-CLOCKFREEZE-20261120-V2"'
            not in candidate_bytes
            or b"OrderSend(" in candidate_bytes
            or b"WebRequest(" in candidate_bytes
            or b"#import" in candidate_bytes):
        raise InputError("CLOCKFIX_SOURCE_VERSION_OR_NO_ORDER_UNSAFE")
    candidate_sha=_hash(candidate_bytes)
    originals=forensic._inventory(folder)
    historical=[p for p in originals if
                p.name<=BASELINE["last_source_basename"]]
    if (len(historical)!=BASELINE["reviewed_original_count"]
            or historical[0].name!=BASELINE["first_source_basename"]
            or historical[-1].name!=BASELINE["last_source_basename"]):
        raise InputError("CLOCKFIX_HISTORICAL_INVENTORY_CHANGED")
    chain=b"\x00"*32
    for f in historical:
        chain=hashlib.sha256(
            chain+f.name.encode("ascii")+bytes.fromhex(_source_sha(f))
        ).digest()
    if chain.hex()!=BASELINE["original_sequence_sha256_local_only"]:
        raise InputError("CLOCKFIX_ORIGINAL_BASELINE_HASH_CHANGED")
    selected=[p for p in originals if forensic._epoch(p.name)>=cutoff]
    if len(selected)>MAX_POST:
        raise InputError("CLOCKFIX_POSTCUTOVER_UNBOUNDED_INVENTORY")
    post_first=selected[0].name if selected else None
    post_last=selected[-1].name if selected else None
    valid=0
    invalid=0
    problems=[]
    future_counts={sym:0 for sym in engine.SYMS}
    future_max={sym:0 for sym in engine.SYMS}
    last_epoch=None
    gap90=0
    gap600=0
    day_counts={}
    for position,path in enumerate(selected,1):
        epoch=forensic._epoch(path.name)
        if last_epoch is not None:
            gap90+=int(epoch-last_epoch>90)
            gap600+=int(epoch-last_epoch>600)
        last_epoch=epoch
        key=trading_day(datetime.fromtimestamp(epoch,tz=timezone.utc)
                        .isoformat().replace("+00:00","Z"))
        day_counts[key]=day_counts.get(key,0)+1
        before_sha=_source_sha(path)
        try:
            item=engine.validate_quotes(
                path,now=datetime.fromtimestamp(epoch+1,tz=timezone.utc))
            good=(item["capture_epoch"]==epoch)
            codes=[] if good else ["CAPTURE_TIME_DIFFERS_FROM_FILENAME"]
        except (InputError,OSError,ValueError,TypeError,
                UnicodeError,OverflowError,ArithmeticError):
            good=False
            try:
                item=forensic._classify(path)
                codes=sorted({x["code"] for x in item["issues"]})
                if not codes:
                    codes=["ENGINE_REJECTED_UNCLASSIFIED_SOURCE"]
                _,rows,_=forensic._parse_raw(path)
                for row in rows:
                    sym=row.get("pair")
                    if sym not in future_counts:
                        continue
                    try:
                        ahead=int(row["tick_time_broker_epoch_unattested"])-int(
                            row["broker_time_epoch_unattested"])
                    except (ValueError,KeyError,TypeError,OverflowError):
                        continue
                    if ahead>0:
                        future_counts[sym]+=1
                        future_max[sym]=max(future_max[sym],min(ahead,86401))
            except (InputError,OSError,ValueError,TypeError,
                    UnicodeError,OverflowError,ArithmeticError):
                codes=["UNCLASSIFIABLE_POSTCUTOVER_ORIGINAL"]
        after_sha=_source_sha(path)
        if before_sha!=after_sha:
            raise InputError("CLOCKFIX_ORIGINAL_CHANGED_DURING_AUDIT")
        if good:
            valid+=1
        else:
            invalid+=1
            if len(problems)<25:
                problems.append({
                    "source_ordinal_after_cutover":position,
                    "source_basename":path.name,
                    "local_sha256":before_sha,
                    "reason_codes":codes,
                })
    count=len(selected)
    research_samples_sufficient=count>=120 and len(day_counts)>=2
    # A 120-sample clean run would be weak evidence against a historical
    # 4/3020 event rate: under a *hypothetical independent identically
    # distributed* model, it has ~85% probability of no errors even if the
    # old issue remains. Correlation/regime changes make this only a
    # descriptive heuristic, never an acceptance or trading gate.
    historical_rate=(BASELINE["invalid_original_count"]/
                     BASELINE["reviewed_original_count"])
    if not 0<historical_rate<1:
        raise InputError("CLOCKFIX_BASELINE_RATE_OUT_OF_RANGE")
    iid_detection_sample_target=math.ceil(
        math.log(0.05)/math.log1p(-historical_rate))
    iid_zero_chance=pow(1-historical_rate,count)
    return {
        "schema":SCHEMA,
        "status":"CLOCKFIX_CANDIDATE_PROSPECTIVE_RESEARCH_HOLD_NO_GO",
        "baseline_original_count":len(historical),
        "baseline_invalid_original_count":BASELINE["invalid_original_count"],
        "baseline_original_sequence_sha256":chain.hex(),
        "baseline_report_sha256_local_only":_source_sha_report(baseline_path),
        "baseline_still_byte_for_byte_preserved":True,
        "candidate_mq4_local_sha256":candidate_sha,
        "candidate_source_build_tag":"FXPAPER-CLOCKFREEZE-20261120-V2",
        "candidate_source_no_order_static_guard":True,
        "cutover_epoch_operator_claim_pc_unattested":cutoff,
        "new_ea_deployment_independently_confirmed":False,
        "candidate_metaeditor_compilation_confirmed":False,
        "new_ea_expert_log_and_old_ea_stop_verified":False,
        "post_cutover_quote_count":count,
        "post_cutover_valid_quote_count":valid,
        "post_cutover_invalid_quote_count":invalid,
        "post_cutover_future_tick_counts":future_counts,
        "post_cutover_max_future_lead_seconds":future_max,
        "post_cutover_first_source":post_first,
        "post_cutover_last_source":post_last,
        "post_cutover_observed_ny17_buckets":len(day_counts),
        "post_cutover_gaps_above_90s":gap90,
        "post_cutover_gaps_above_600s":gap600,
        "research_120_observations_two_ny17_days_reached":research_samples_sufficient,
        "historical_invalid_fraction":round(historical_rate,9),
        "iid_95pct_detect_at_least_one_if_rate_unchanged_sample_target":
            iid_detection_sample_target,
        "post_count_reaches_iid_95pct_detection_heuristic":
            count>=iid_detection_sample_target,
        "iid_probability_of_zero_if_legacy_rate_unchanged_illustrative":
            round(iid_zero_chance,6),
        "iid_assumption_independently_validated":False,
        "statistics_can_enable_new_virtual_entries":False,
        "post_cutover_observed_future_tick_anomaly":any(future_counts.values()),
        "post_cutover_issues_first_25":problems,
        "proof_clock_race_eliminated":False,
        "independent_broker_time_attested":False,
        "full_transaction_cost_attested":False,
        "macro_and_consensus_independently_attested":False,
        "communication_latch_cleared":False,
        "extra_paid_ai_permitted":False,
        "new_virtual_entries_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def _source_sha_report(path:Path)->str:
    return _hash(path.read_bytes())


def main(argv=None)->int:
    parser=argparse.ArgumentParser(
        description="Offline original 3020 baseline versus manually specified future MT4 EA cutover")
    parser.add_argument("--mt4-files",required=True,type=Path)
    parser.add_argument("--baseline-report",required=True,type=Path)
    parser.add_argument("--cutover-utc",required=True)
    parser.add_argument("--candidate-source",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        result=audit(args.mt4_files,args.baseline_report,
                     args.cutover_utc,candidate_source=args.candidate_source)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("CLOCKFIX_REPORT_OUTPUT_MUST_BE_NEW")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
        print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,TypeError,ValueError,UnicodeError,
            OverflowError,ArithmeticError,KeyError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"CLOCKFIX_PROSPECTIVE_AUDIT_FAIL_CLOSED_NO_GO",
            "communication_latch_cleared":False,
            "extra_paid_ai_permitted":False,
            "new_virtual_entries_permitted":False,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
