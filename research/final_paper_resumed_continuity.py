"""Two-point Windows recovery evidence to prove observation continuity, not trading.

Input: two independently saved local-machine-handoff JSONs made >= 60 seconds
apart. Checks same PID/start time, distinct fresh MT4 quotes, monotonic journal
growth, complete hash chain and paid AI ledger. PC timestamps remain PC-derived.
Does not authorize a communication-latch reset, inference, virtual entry or
broker orders.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_ai_continuation_audit as paid
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_two_point_continuity_v1"
HANDOFF="fx_final_paper_local_machine_handoff_v1"
QUOTE=re.compile(r"^FxPaperQuote_([0-9]{8}_[0-9]{6})\.csv$")
JOURNAL=re.compile(r"^([0-9]{8})\.json$")
MAX_INTERVAL=900
MIN_INTERVAL=60


def _read(path:Path)->dict:
    if (not path.is_file() or path.is_symlink()
            or any(p.is_symlink() for p in path.parents)
            or not 0<path.stat().st_size<=16000):
        raise InputError("RECOVERY_CONTINUITY_UNSAFE_SNAPSHOT")
    try:
        obj=json.loads(path.read_text("utf-8-sig"))
    except (ValueError,OSError,UnicodeError) as exc:
        raise InputError("RECOVERY_CONTINUITY_INVALID_JSON") from exc
    if type(obj) is not dict or obj.get("schema")!=HANDOFF:
        raise InputError("RECOVERY_CONTINUITY_UNKNOWN_SCHEMA")
    return obj


def _time(value:str)->datetime:
    if type(value) is not str:
        raise InputError("RECOVERY_CONTINUITY_TIME_INVALID")
    try:
        v=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise InputError("RECOVERY_CONTINUITY_TIME_INVALID") from exc
    if v.tzinfo is None or v.utcoffset().total_seconds()!=0:
        raise InputError("RECOVERY_CONTINUITY_TIME_NOT_UTC")
    return v


def _snap(obj:dict)->dict:
    if (type(obj.get("journal_file_count")) is not int
            or not 1<=obj["journal_file_count"]<=runtime.MAX_RECORDS
            or type(obj.get("paper_supervisor_process_count")) is not int
            or obj["paper_supervisor_process_count"]!=1
            or type(obj.get("mt4_terminal_process_count")) is not int
            or obj["mt4_terminal_process_count"]!=1
            or obj.get("runtime_lock_present_not_process_proof") is not True
            or obj.get("paper_supervisor_paid_ai_opt_in_cli_flag_present") is not False
            or obj.get("new_paid_ai_calls_authorized") is not False
            or obj.get("new_virtual_positions_permitted") is not False
            or obj.get("real_orders_permitted") is not False):
        raise InputError("RECOVERY_CONTINUITY_PROCESS_OR_SAFETY_INVALID")
    pid=obj.get("paper_supervisor_process_id")
    start=obj.get("paper_supervisor_created_utc_pc_unattested")
    if type(pid) is not int or pid<=0:
        raise InputError("RECOVERY_CONTINUITY_PID_MISSING")
    started=_time(start)
    captured=_time(obj.get("captured_utc_pc_unattested"))
    if started>=captured:
        raise InputError("RECOVERY_CONTINUITY_PROCESS_START_INVALID")
    expected_journal=f'{obj["journal_file_count"]:08d}.json'
    if obj.get("journal_last_file_name")!=expected_journal:
        raise InputError("RECOVERY_CONTINUITY_LAST_FILE_INVALID")
    hash_j=obj.get("journal_last_file_sha256")
    if type(hash_j) is not str or runtime.SHA.fullmatch(hash_j) is None:
        raise InputError("RECOVERY_CONTINUITY_LAST_HASH_INVALID")
    quote_files=obj.get("mt4_quote_source_files")
    if type(quote_files) is not list or not 1<=len(quote_files)<=3:
        raise InputError("RECOVERY_CONTINUITY_QUOTE_MISSING")
    first=quote_files[0]
    if type(first) is not dict:
        raise InputError("RECOVERY_CONTINUITY_QUOTE_INVALID")
    name=first.get("name")
    match=QUOTE.fullmatch(name) if type(name) is str else None
    if match is None:
        raise InputError("RECOVERY_CONTINUITY_QUOTE_INVALID")
    try:
        quote_dt=datetime.strptime(match.group(1),"%Y%m%d_%H%M%S").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise InputError("RECOVERY_CONTINUITY_QUOTE_TIME_INVALID") from exc
    age=(captured-quote_dt).total_seconds()
    if not 0<=age<=120:
        raise InputError("RECOVERY_CONTINUITY_QUOTE_STALE")
    sha=first.get("sha256")
    if type(sha) is not str or runtime.SHA.fullmatch(sha) is None:
        raise InputError("RECOVERY_CONTINUITY_QUOTE_HASH_INVALID")
    return {
        "captured_epoch":int(captured.timestamp()),
        "started_epoch":int(started.timestamp()),
        "pid":pid,
        "journal_count":obj["journal_file_count"],
        "journal_file_sha256":hash_j,
        "quote_epoch":int(quote_dt.timestamp()),
        "quote_sha256":sha,
        "quote_name":name,
    }


def verify(root:Path, first_path:Path, second_path:Path)->dict:
    if (not root.is_dir() or root.is_symlink()
            or any(p.is_symlink() for p in root.parents)
            or first_path.resolve()==second_path.resolve()):
        raise InputError("RECOVERY_CONTINUITY_PATH_UNSAFE")
    left=_snap(_read(first_path))
    right=_snap(_read(second_path))
    span=right["captured_epoch"]-left["captured_epoch"]
    if not MIN_INTERVAL<=span<=MAX_INTERVAL:
        raise InputError("RECOVERY_CONTINUITY_SAMPLE_SPAN_INVALID")
    if (left["pid"]!=right["pid"]
            or left["started_epoch"]!=right["started_epoch"]):
        raise InputError("RECOVERY_CONTINUITY_PROCESS_REPLACED")
    cycles=right["journal_count"]-left["journal_count"]
    if not 1<=cycles<=min(30,span//10+2):
        raise InputError("RECOVERY_CONTINUITY_JOURNAL_NOT_ADVANCING")
    if (left["journal_file_sha256"]==right["journal_file_sha256"]
            or left["quote_epoch"]>=right["quote_epoch"]
            or right["quote_sha256"]==left["quote_sha256"]
            or left["quote_name"]>=right["quote_name"]):
        raise InputError("RECOVERY_CONTINUITY_QUOTE_OR_JOURNAL_REPLAY")
    state,head=runtime._journal_load(root/"journal")
    billed=paid.audit(root)
    if (state["cycle_number"]<right["journal_count"]
            or state["last_quote_epoch"]<left["quote_epoch"]
            or billed["paid_calls_recorded_in_journal"]!=
               billed["paid_calls_in_completed_ledgers"]
            or billed.get("paid_calls_recorded_in_journal")!=
               state.get("paid_inference_calls")
            or billed.get("journal_head_sha256_local_only")!=head
            or billed.get("journal_cycles")!=state.get("cycle_number")
            or state["paid_inference_calls"]!=6
            or state.get("communication_latched") is not True
            or any(state.get(n) is not False for n in (
                "daily_loss_latched","dd4_latched","dd5_latched"))
            or state.get("positions")!=[]
            or state.get("pending_signals")!=[]):
        raise InputError("RECOVERY_CONTINUITY_RUNTIME_SAFETY_INVALID")
    # Re-check head, because a supervisor can be writing a new cycle while
    # this read-only report is being created.
    _, end=runtime._journal_load(root/"journal")
    if end!=head:
        raise InputError("RECOVERY_CONTINUITY_JOURNAL_MOVED_DURING_AUDIT")
    return {
        "schema":SCHEMA,
        "status":"PAPER_RESUMED_OBSERVATION_TWO_POINT_CONSISTENT_NO_GO",
        "first_snapshot_epoch_pc_unattested":left["captured_epoch"],
        "second_snapshot_epoch_pc_unattested":right["captured_epoch"],
        "interval_seconds_pc_derived":span,
        "same_python_pid_and_start_time":True,
        "same_session_journal_advanced_cycles":cycles,
        "latest_journal_cycles":state["cycle_number"],
        "latest_journal_head_sha256_local_only":head,
        "mt4_source_quote_advanced":True,
        "journal_hash_chain_valid":True,
        "paid_calls_reconciled_and_unchanged":True,
        "communication_latched":True,
        "other_risk_latches_absent":True,
        "one_shot_snapshots_prove_continuous_health_forever":False,
        "broker_clock_independently_verified":False,
        "complete_usd_eur_jpy_macro_events_attested":False,
        "provider_jpy_billing_attested":False,
        "new_paid_ai_calls_permitted":False,
        "new_virtual_positions_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description="Two Windows MT4/Python observation samples")
    parser.add_argument("--state-root",required=True,type=Path)
    parser.add_argument("--first",required=True,type=Path)
    parser.add_argument("--second",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        report=verify(args.state_root,args.first,args.second)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("RECOVERY_CONTINUITY_OUTPUT_UNSAFE")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False))
        return 0
    except (InputError,ValueError,KeyError,TypeError,UnicodeError,
            OSError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"PAPER_RESUMED_CONTINUITY_FAIL_CLOSED_NO_GO",
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
