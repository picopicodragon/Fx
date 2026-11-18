"""FINAL-PAPER: forensic reconstruction of a paper quote-consumer interruption.

Local read-only investigation. Never changes chain, latches or AI spending.
Quote times are recorded PC epochs, not independently verified UTC/broker time.
Does NOT establish the cause of a historical Windows/Python process stop.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_interruption_forensics_v1"
MAX_SCAN = 1024
MIN_L2_GAP_SECONDS = 600


def analyze(root: Path, *, now: datetime|None=None) -> dict:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("invalid forensic clock")
    if (not root.is_dir() or root.is_symlink()
            or any(parent.is_symlink() for parent in root.parents)):
        raise InputError("unsafe paper evidence directory")
    state,head = runtime._journal_load(root/"journal")
    count=state["cycle_number"]
    if type(count) is not int or count<0 or count>runtime.MAX_RECORDS:
        raise InputError("invalid paper journal sequence")
    previous_epoch = None
    previous_cycle = None
    found = None
    start=max(1,count-MAX_SCAN+1)
    # One earlier record provides the predecessor for the first scanned cycle.
    for seq in range(max(1,start-1),count+1):
        file=root/"journal"/f"{seq:08d}.json"
        if not file.is_file() or file.is_symlink():
            raise InputError("missing forensic journal record")
        payload=json.loads(file.read_text("utf-8-sig"))
        record=payload["state"]
        epoch=record.get("last_quote_epoch")
        if (record.get("cycle_number")!=seq or type(epoch) is not int
                or epoch<=0 or
                record.get("virtual_only") is not True or
                record.get("broker_orders_permitted") is not False):
            raise InputError("invalid forensic journal state")
        if previous_epoch is not None:
            interval=epoch-previous_epoch
            if interval<=0:
                raise InputError("non-monotonic paper quote evidence")
            if interval>MIN_L2_GAP_SECONDS:
                found={
                    "previous_cycle":previous_cycle,
                    "first_cycle_after_gap":seq,
                    "previous_quote_epoch_pc_unattested":previous_epoch,
                    "first_quote_after_gap_epoch_pc_unattested":epoch,
                    "observation_gap_seconds_pc_derived":interval,
                    "first_after_gap_communication_latched":
                        record.get("communication_latched") is True,
                }
        previous_epoch=epoch
        previous_cycle=seq
    if count>0 and previous_epoch!=state.get("last_quote_epoch"):
        raise InputError("forensic journal changed during read")
    newest_epoch=state.get("last_quote_epoch",0)
    age=int(current.timestamp())-newest_epoch if newest_epoch else None
    if age is not None and age < -10:
        raise InputError("future paper quote evidence")
    return {
        "schema":SCHEMA,
        "status":"PAPER_INTERRUPTION_FORENSIC_TIMELINE_ONLY_NO_GO",
        "journal_cycles":count,
        "journal_head_sha256_local_only":head,
        "scanned_cycle_count":count-start+1 if count else 0,
        "latest_level2_gap_in_scanned_window":found,
        "cycles_recorded_since_latest_level2_gap":
            count-found["first_cycle_after_gap"]+1 if found else None,
        "latest_processed_quote_age_seconds_pc_derived":age,
        "latest_state_communication_latched":
            state.get("communication_latched") is True,
        "current_paid_ai_calls_lifetime":state.get("paid_inference_calls"),
        "root_cause_classification":"UNKNOWN_REQUIRES_WINDOWS_AND_OPERATOR_EVIDENCE",
        "windows_event_logs_examined":False,
        "full_console_exit_log_available_from_journal":False,
        "process_exit_reason_verified":False,
        "communication_latch_cleared":False,
        "new_virtual_entries_permitted":False,
        "new_paid_ai_calls_permitted":False,
        "broker_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="Read-only historic gap timeline from chained paper journal")
    parser.add_argument("--state-root",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        report=analyze(args.state_root)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("forensic report must be new")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,ValueError,KeyError,TypeError,OverflowError,
            UnicodeError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"PAPER_INTERRUPTION_FORENSIC_FAIL_CLOSED_NO_GO",
            "root_cause_classification":"UNKNOWN",
            "communication_latch_cleared":False,
            "new_paid_ai_calls_permitted":False,
            "broker_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
