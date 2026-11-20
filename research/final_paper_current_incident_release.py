"""Incident-specific, one-use 2026-11-20 communications release for PAPER.

No automatic stop or permission. An operator must separately inspect the
latest real >600s journal interruption, stop the existing Python supervisor,
verify no process remains and explicitly approve this exact incident.
The staged permit is SHA-bound to the append-only journal head; it expires
in 300s and can be applied only on the NEXT fresh DEMO quote. Does NOT
release AI-budget, event, clock, transaction-cost, DD or broker-order gates.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_ai_continuation_audit as ai_audit
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_current_incident_comm_release_v1"
NAME="manual_comm_release_20261120.json"
APPROVAL="APPROVE_20261120_INCIDENT_INTERNAL_VIRTUAL_COMMUNICATION_RELEASE_ONLY"
AGE_LIMIT=300
MAX_NEW_QUOTE_GAP=180
FIELDS=frozenset({
    "schema","event_identifier","operator_approval",
    "created_epoch_pc_unattested","bound_cycle_number","bound_journal_sha256",
    "bound_last_quote_epoch","incident_previous_cycle","incident_next_cycle",
    "incident_gap_seconds_pc_unattested","approval_record_sha256",
})


def most_recent_incident(root:Path,state:dict)->dict:
    folder=root/"journal"
    last_epoch=None
    found=[]
    for seq in range(1,state["cycle_number"]+1):
        path=folder/f"{seq:08d}.json"
        if not path.is_file() or path.is_symlink():
            raise InputError("CURRENT_INCIDENT_JOURNAL_RECORD_MISSING")
        try:
            item=json.loads(path.read_text("utf-8-sig"))
            epoch=item["state"]["last_quote_epoch"]
        except (OSError,ValueError,KeyError,TypeError,UnicodeError) as exc:
            raise InputError("CURRENT_INCIDENT_JOURNAL_RECORD_INVALID") from exc
        if type(epoch) is not int or epoch<=0:
            raise InputError("CURRENT_INCIDENT_JOURNAL_TIME_UNSAFE")
        if last_epoch is not None:
            gap=epoch-last_epoch
            if gap<=0:
                raise InputError("CURRENT_INCIDENT_NONMONOTONIC_TIMELINE")
            if gap>600:
                found.append({
                    "incident_previous_cycle":seq-1,
                    "incident_next_cycle":seq,
                    "incident_gap_seconds_pc_unattested":gap,
                })
        last_epoch=epoch
    if last_epoch!=state["last_quote_epoch"] or not found:
        raise InputError("CURRENT_INCIDENT_EXPECTED_INTERRUPTION_MISSING")
    last=found[-1]
    if last["incident_next_cycle"]<=107:
        raise InputError("CURRENT_INCIDENT_ONLY_20261118_OLD_GAP_FOUND")
    return last


def _risk_state(state:dict)->None:
    if (state.get("virtual_only") is not True
            or state.get("broker_orders_permitted") is not False
            or state.get("communication_latched") is not True
            or state.get("dd4_latched") is not False
            or state.get("dd5_latched") is not False
            or state.get("daily_loss_latched") is not False
            or state.get("positions")!=[] or state.get("pending_signals")!=[]
            or state.get("manual_comm_release_sha256") is not None
            or state.get("paid_inference_calls")!=6):
        raise InputError("CURRENT_INCIDENT_RISK_STATE_UNSAFE")


def stage(root:Path,mt4:Path,*,approval:str,now:datetime|None=None)->dict:
    if approval!=APPROVAL:
        raise InputError("CURRENT_INCIDENT_NEW_EXPLICIT_OPERATOR_APPROVAL_REQUIRED")
    now=now or datetime.now(timezone.utc)
    if (now.tzinfo is None or now.utcoffset().total_seconds()!=0
            or not root.is_dir() or root.is_symlink()
            or not mt4.is_dir() or mt4.is_symlink()
            or mt4.parent.name.lower()!="mql4"
            or mt4.name.lower()!="files"):
        raise InputError("CURRENT_INCIDENT_OPERATOR_HOST_OR_CLOCK_UNSAFE")
    # Never create a permit while another supervisor may still write.
    if (root/".single_operator.lock").exists() or (
            root/".single_operator.lock").is_symlink():
        raise InputError("CURRENT_INCIDENT_RUNNING_SUPERVISOR_MUST_STOP")
    for name in (NAME,"manual_comm_release_20261118.json"):
        path=root/name
        if path.exists() or path.is_symlink():
            raise InputError("CURRENT_INCIDENT_ALREADY_STAGED_OR_OLD_PERMIT_PRESENT")
    state,head=runtime._journal_load(root/"journal")
    _risk_state(state)
    incident=most_recent_incident(root,state)
    billed=ai_audit.audit(root)
    if (billed["paid_calls_recorded_in_journal"]!=6
            or billed["paid_calls_in_completed_ledgers"]!=6
            or billed["journal_head_sha256_local_only"]!=head):
        raise InputError("CURRENT_INCIDENT_BILLING_NOT_RECONCILED")
    quote=runtime._latest_quote(mt4,now)
    if quote is None:
        raise InputError("CURRENT_INCIDENT_NO_FRESH_DEMO_QUOTE")
    quote_epoch=quote["capture_epoch"]
    if (quote_epoch<state["last_quote_epoch"]
            or quote_epoch>state["last_quote_epoch"]+MAX_NEW_QUOTE_GAP
            or not 0<=int(now.timestamp())-quote_epoch<=120):
        raise InputError("CURRENT_INCIDENT_FRESH_QUOTE_GAP_INVALID")
    same,newhead=runtime._journal_load(root/"journal")
    if same!=state or newhead!=head or (
            root/".single_operator.lock").exists():
        raise InputError("CURRENT_INCIDENT_HEAD_MOVED_DURING_STAGING")
    record={
        "schema":SCHEMA,
        "event_identifier":"PAPER_CURRENT_POST_20261118_LAST_GAP",
        "operator_approval":APPROVAL,
        "created_epoch_pc_unattested":int(now.timestamp()),
        "bound_cycle_number":state["cycle_number"],
        "bound_journal_sha256":head,
        "bound_last_quote_epoch":state["last_quote_epoch"],
        **incident,
    }
    record["approval_record_sha256"]=runtime._digest(record)
    target=root/NAME
    with target.open("x",encoding="utf-8") as out:
        json.dump(record,out,ensure_ascii=False,indent=2,allow_nan=False)
        out.flush()
        import os
        os.fsync(out.fileno())
    return {
        "schema":SCHEMA,
        "status":"CURRENT_INCIDENT_MANUAL_COMM_RELEASE_STAGED_NOT_APPLIED_NO_GO",
        "bound_head_sha256":head,
        "incident":incident,
        "approved_operator_intent_recorded":True,
        "communication_latch_cleared":False,
        "new_virtual_entries_permitted":False,
        "new_paid_ai_calls_permitted":False,
        "broker_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
    }


def apply_if_valid(root:Path,state:dict,head:str,quote:dict,
                   now:datetime)->tuple[dict,bool]:
    # Only a 1-use release for this exact recorded incident is possible.
    permit=root/NAME
    if not permit.exists() and not permit.is_symlink():
        return state,False
    if (not permit.is_file() or permit.is_symlink()
            or not 0<permit.stat().st_size<=4096):
        raise InputError("CURRENT_INCIDENT_PERMIT_UNSAFE")
    try:
        obj=json.loads(permit.read_text("utf-8-sig"))
    except (OSError,ValueError,UnicodeError) as exc:
        raise InputError("CURRENT_INCIDENT_PERMIT_INVALID") from exc
    if (type(obj) is not dict or set(obj)!=FIELDS
            or obj.get("schema")!=SCHEMA
            or obj.get("operator_approval")!=APPROVAL
            or obj.get("event_identifier")!="PAPER_CURRENT_POST_20261118_LAST_GAP"
            or type(obj.get("created_epoch_pc_unattested")) is not int
            or type(obj.get("bound_cycle_number")) is not int
            or type(obj.get("bound_last_quote_epoch")) is not int
            or type(obj.get("incident_previous_cycle")) is not int
            or type(obj.get("incident_next_cycle")) is not int
            or type(obj.get("incident_gap_seconds_pc_unattested")) is not int
            or type(obj.get("bound_journal_sha256")) is not str
            or runtime.SHA.fullmatch(obj["bound_journal_sha256"]) is None
            or obj.get("approval_record_sha256")!=runtime._digest(
                {k:v for k,v in obj.items() if k!="approval_record_sha256"})):
        raise InputError("CURRENT_INCIDENT_PERMIT_TAMPERED_OR_STALE_HEAD")
    # A previously consumed head-bound permit remains on disk as an
    # immutable audit record. Never reapply it, and never honor a different
    # incident when an old marker is already present.
    marker=state.get("manual_comm_release_sha256")
    if marker is not None:
        if (type(marker) is not str or
                runtime.SHA.fullmatch(marker) is None or
                marker!=obj["approval_record_sha256"]):
            raise InputError("CURRENT_INCIDENT_ALREADY_RELEASED_DIFFERENT_EVENT")
        return state,False
    # A new journal head is NORMAL after the one permitted application
    # has already been durable-written. Bind the head only when first
    # consuming an unspent approval.
    if obj["bound_journal_sha256"]!=head:
        raise InputError("CURRENT_INCIDENT_PERMIT_STALE_JOURNAL_HEAD")
    age=int(now.timestamp())-obj["created_epoch_pc_unattested"]
    if not 0<=age<=AGE_LIMIT:
        raise InputError("CURRENT_INCIDENT_PERMIT_EXPIRED")
    _risk_state(state)
    if (obj["bound_cycle_number"]!=state["cycle_number"]
            or obj["bound_last_quote_epoch"]!=state["last_quote_epoch"]
            or obj["incident_next_cycle"]<=107
            or obj["incident_next_cycle"]>state["cycle_number"]
            or obj["incident_gap_seconds_pc_unattested"]<=600):
        raise InputError("CURRENT_INCIDENT_UNMATCHED_RISK_EVENT")
    observed=quote.get("capture_epoch")
    if (type(observed) is not int or not
            0<=int(now.timestamp())-observed<=120
            or observed>state["last_quote_epoch"]+MAX_NEW_QUOTE_GAP):
        raise InputError("CURRENT_INCIDENT_QUOTE_INVALID")
    if observed<=state["last_quote_epoch"]:
        return state,False
    changed=dict(state)
    changed["communication_latched"]=False
    changed["manual_comm_release_sha256"]=obj["approval_record_sha256"]
    return changed,True


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="One-use manual communications incident release for virtual PAPER")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--mt4-files",type=Path,required=True)
    p.add_argument("--operator-approval",default="")
    args=p.parse_args(argv)
    try:
        result=stage(args.state_root,args.mt4_files,
                     approval=args.operator_approval)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,OSError,TypeError,ValueError,KeyError,
            UnicodeError,OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"CURRENT_INCIDENT_COMM_RELEASE_FAIL_CLOSED_NO_GO",
            "communication_latch_cleared":False,
            "new_virtual_entries_permitted":False,
            "new_paid_ai_calls_permitted":False,
            "broker_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
