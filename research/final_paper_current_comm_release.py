"""FINAL-AUTO: approval for THIS observed communication interruption only.

No release is created automatically. An operator must stop the existing
supervisor, independently verify no other Python monitor is running,
preview the complete journal gap fingerprint, then stage a specific
signed-off single-use approval. The new supervisor consumes it ONLY on
a strictly fresh quote, preserving every other risk latch.

This never clears DD4, DD5, daily loss or permits broker orders.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_current_interruption_release_v1"
FILE_NAME="final_paper_current_comm_release_20261120.json"
APPROVAL="APPROVE_CURRENT_FX_PAPER_COMMUNICATION_LATCH_RELEASE_ONLY"
ID="PAPER_20261120_RUNTIME_38H_GAP_AND_ALL_JOURNAL_INTERRUPTS"
MAX_AGE=300
SHA=re.compile(r"^[a-f0-9]{64}$")


def _hash(data:dict)->str:
    return runtime._digest(data)


def gaps(root:Path)->dict:
    state,head=runtime._journal_load(root/"journal")
    count=state["cycle_number"]
    if (count<1 or type(state.get("last_quote_epoch")) is not int
            or state.get("communication_latched") is not True
            or state.get("positions")!=[]
            or state.get("pending_signals")!=[]
            or state.get("dd4_latched") is not False
            or state.get("dd5_latched") is not False
            or state.get("daily_loss_latched") is not False
            or state.get("broker_orders_permitted") is not False
            or state.get("virtual_only") is not True
            or state.get("paid_inference_calls")!=6):
        raise InputError("FINAL_COMM_EXISTING_RISK_UNSAFE")
    previous=None
    breaks=[]
    for number in range(1,count+1):
        src=root/"journal"/f"{number:08d}.json"
        if src.is_symlink() or not src.is_file():
            raise InputError("FINAL_COMM_JOURNAL_GAP_FILE_MISSING")
        record=json.loads(src.read_text("utf-8-sig"))
        when=record["state"]["last_quote_epoch"]
        if type(when) is not int or when<=0 or(
                previous is not None and when<=previous):
            raise InputError("FINAL_COMM_UNORDERED_JOURNAL_TIME")
        if previous is not None and when-previous>600:
            breaks.append({
                "cycle":number,
                "previous_capture_epoch":previous,
                "next_capture_epoch":when,
                "unobserved_seconds":when-previous,
            })
        previous=when
    if previous!=state["last_quote_epoch"]:
        raise InputError("FINAL_COMM_JOURNAL_LAST_QUOTE_INVALID")
    summary={
        "journal_cycles":count,
        "journal_head_sha256":head,
        "known_gaps_over_600_seconds":breaks,
        "current_communication_latched":True,
        "all_other_risk_latches_clear":True,
        "old_paid_calls_unchanged":6,
    }
    return {
        **summary,
        "all_historical_gaps_fingerprint_sha256":_hash(summary),
        "operator_has_approved":False,
        "journal_or_latch_modified":False,
        "new_virtual_entries_permitted":False,
        "broker_orders_permitted":False,
    }


def stage(root:Path,*,approval:str,gap_fingerprint:str,
          supervisor_absence_checked:bool,now:datetime|None=None)->dict:
    if (approval!=APPROVAL or not supervisor_absence_checked
            or type(gap_fingerprint) is not str
            or SHA.fullmatch(gap_fingerprint) is None):
        raise InputError("FINAL_COMM_EXPLICIT_CURRENT_INCIDENT_APPROVAL_REQUIRED")
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset().total_seconds()!=0:
        raise InputError("FINAL_COMM_CLOCK_NOT_UTC")
    lock=root/".single_operator.lock"
    permit=root/FILE_NAME
    if (lock.exists() or lock.is_symlink()
            or permit.exists() or permit.is_symlink()):
        raise InputError("FINAL_COMM_EXISTING_MONITOR_OR_PERMIT")
    snapshot=gaps(root)
    if (snapshot["all_historical_gaps_fingerprint_sha256"]!=gap_fingerprint
            or not snapshot["known_gaps_over_600_seconds"]):
        raise InputError("FINAL_COMM_GAP_FINGERPRINT_MISMATCH")
    record={
        "schema":SCHEMA,
        "incident_id":ID,
        "operator_approval":APPROVAL,
        "operator_independently_verified_no_python_monitor":True,
        "reviewed_gaps_fingerprint_sha256":gap_fingerprint,
        "journal_cycles":snapshot["journal_cycles"],
        "journal_head_sha256":snapshot["journal_head_sha256"],
        "last_quote_epoch":snapshot["known_gaps_over_600_seconds"][-1][
            "next_capture_epoch"],
        "created_epoch_utc_pc_unattested":int(now.timestamp()),
        "used_for_other_incidents":False,
    }
    # The permit binds to the exact final journal quote, not only the
    # most recent historically known long gap.
    state,_=runtime._journal_load(root/"journal")
    record["last_quote_epoch"]=state["last_quote_epoch"]
    record["permit_sha256"]=_hash(record)
    with permit.open("x",encoding="utf-8") as f:
        json.dump(record,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    return {
        "status":"FINAL_COMM_ONE_USE_PERMIT_STAGED_NOT_APPLIED_NO_GO",
        "permit_sha256":record["permit_sha256"],
        "latch_released":False,
        "new_virtual_entries_permitted":False,
        "broker_orders_permitted":False,
    }


def apply_if_valid(root:Path,state:dict,head:str,quote:dict,
                   now:datetime)->tuple[dict,bool]:
    if "auto_current_comm_release_sha256" in state:
        used=state["auto_current_comm_release_sha256"]
        if type(used) is not str or SHA.fullmatch(used) is None:
            raise InputError("FINAL_COMM_CONSUMED_MARKER_INVALID")
        return state,False
    permit=root/FILE_NAME
    if not permit.exists() and not permit.is_symlink():
        return state,False
    if (not permit.is_file() or permit.is_symlink()
            or not 0<permit.stat().st_size<=4096):
        raise InputError("FINAL_COMM_PERMIT_MISSING_OR_UNSAFE")
    try:
        data=json.loads(permit.read_text("utf-8-sig"))
    except (ValueError,UnicodeError) as exc:
        raise InputError("FINAL_COMM_PERMIT_JSON_UNREADABLE") from exc
    if (type(data) is not dict or set(data)!={
            "schema","incident_id","operator_approval",
            "operator_independently_verified_no_python_monitor",
            "reviewed_gaps_fingerprint_sha256","journal_cycles",
            "journal_head_sha256","last_quote_epoch",
            "created_epoch_utc_pc_unattested","used_for_other_incidents",
            "permit_sha256"}
            or data["schema"]!=SCHEMA or data["incident_id"]!=ID
            or data["operator_approval"]!=APPROVAL
            or data["operator_independently_verified_no_python_monitor"] is not True
            or data["used_for_other_incidents"] is not False
            or data["permit_sha256"]!=_hash({
                k:v for k,v in data.items() if k!="permit_sha256"})):
        raise InputError("FINAL_COMM_PERMIT_MODIFIED")
    if (now.tzinfo is None or
            not 0<=int(now.timestamp())-data["created_epoch_utc_pc_unattested"]
               <=MAX_AGE
            or data["journal_cycles"]!=state["cycle_number"]
            or data["journal_head_sha256"]!=head
            or data["last_quote_epoch"]!=state["last_quote_epoch"]
            or state.get("communication_latched") is not True
            or state.get("positions")!=[]
            or state.get("pending_signals")!=[]
            or any(state.get(x) is not False for x in (
                "dd4_latched","dd5_latched","daily_loss_latched"))
            or type(quote.get("capture_epoch")) is not int
            or not 0<quote["capture_epoch"]-state["last_quote_epoch"]<=600
            or not 0<=int(now.timestamp())-quote["capture_epoch"]<=120):
        raise InputError("FINAL_COMM_STALE_OR_RISK_UNSAFE")
    changed=dict(state)
    changed["communication_latched"]=False
    changed["auto_current_comm_release_sha256"]=data["permit_sha256"]
    return changed,True


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Manual current observed-gap approval; never automatic")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--preview",action="store_true")
    p.add_argument("--stage",action="store_true")
    p.add_argument("--operator-approval",default="")
    p.add_argument("--gap-fingerprint",default="")
    p.add_argument("--supervisor-absence-checked",action="store_true")
    args=p.parse_args(argv)
    try:
        if args.preview==args.stage:
            raise InputError("FINAL_COMM_SELECT_EXACTLY_ONE_MODE")
        result=(gaps(args.state_root) if args.preview else
                stage(args.state_root,approval=args.operator_approval,
                      gap_fingerprint=args.gap_fingerprint,
                      supervisor_absence_checked=args.supervisor_absence_checked))
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,OSError,KeyError,ValueError,TypeError,
            UnicodeError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"FINAL_COMM_REVIEW_OR_STAGING_FAIL_CLOSED_NO_GO",
            "latch_released":False,
            "new_virtual_entries_permitted":False,
            "broker_orders_permitted":False,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
