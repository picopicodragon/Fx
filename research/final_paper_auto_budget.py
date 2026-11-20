"""FINAL-AUTO: separately approved, JPY-reserved, crash-safe paid AI budget.

Old historical 6/6 AI calls are NEVER reset or rewritten. Incremental
research has an independent human-approved, per-month JPY ceiling <=3000,
model-specific conservative token reservation and append-only hash ledger.

A reservation is DURABLE before any chargeable API dispatch. Unknown results
are NOT retried; a RESERVE without a SETTLE is a permanent automatic halt
until independent manual incident reconciliation. The external provider
invoice may exceed estimates despite the reserve; the JPY bound is a
CONSERVATIVE PROJECTION, not a provider-side spending limit.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime,timezone
from decimal import Decimal as D, InvalidOperation, ROUND_CEILING
from pathlib import Path

from research import final_paper_engine as paper
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_auto_budget_authorization_v1"
LEDGER_SCHEMA="fx_final_paper_auto_budget_ledger_v1"
APPROVAL="APPROVE_SEPARATE_FINAL_PAPER_PAID_AI_BUDGET_WITH_JPY_RESERVES"
SCOPE="PAID_TWO_MODEL_RESEARCH_INTERNAL_VIRTUAL_ONLY"
MAX_JPY=3000
MAX_CALLS=120
MAX_LEDGER_EVENTS=MAX_CALLS
HEX=re.compile(r"^[a-f0-9]{64}$")
FN=re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,100}$")


def _utc(value:str)->int:
    if type(value) is not str:
        raise InputError("FINAL_BUDGET_TIME_INVALID")
    try:
        d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise InputError("FINAL_BUDGET_TIME_INVALID") from exc
    if d.tzinfo is None or d.utcoffset().total_seconds()!=0:
        raise InputError("FINAL_BUDGET_TIME_NOT_UTC")
    return int(d.timestamp())


def _amount(value:object,*,maximum:int=3000000)->D:
    try:
        if type(value) is not str:
            raise ValueError
        x=D(value)
        if not x.is_finite() or not D(0)<x<=D(maximum):
            raise ValueError
        return x
    except (ValueError,InvalidOperation):
        raise InputError("FINAL_BUDGET_COST_RATE_INVALID") from None


def _hash(data:dict)->str:
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True,
                        separators=(",",":"),allow_nan=False
                      ).encode("utf-8")).hexdigest()


def policy(path:Path,*,now:datetime,session_binding_sha:str,
           analyst_model:str,reviewer_model:str)->dict:
    if (not path.is_file() or path.is_symlink()
            or any(p.is_symlink() for p in path.parents)
            or not 0<path.stat().st_size<=20000
            or not HEX.fullmatch(session_binding_sha)):
        raise InputError("FINAL_BUDGET_APPROVAL_FILE_UNSAFE")
    raw=path.read_bytes()
    try:
        p=json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError,ValueError) as exc:
        raise InputError("FINAL_BUDGET_APPROVAL_JSON_INVALID") from exc
    expected={
        "schema","scope","operator_approval","approved_at_utc",
        "expires_at_utc","month_utc","bound_journal_sha256",
        "previous_paid_calls_acknowledged","analyst_model","reviewer_model",
        "max_incremental_calls","max_incremental_jpy",
        "reserve_jpy_per_two_model_decision","model_rates_jpy_per_million",
        "pricing_original_basename","pricing_original_sha256",
        "previous_provider_billing_reviewed_by_operator",
        "cost_projection_not_provider_spend_cap_acknowledged"}
    if (type(p) is not dict or set(p)!=expected
            or p["schema"]!=SCHEMA or p["scope"]!=SCOPE
            or p["operator_approval"]!=APPROVAL
            or p["bound_journal_sha256"]!=session_binding_sha
            or p["previous_paid_calls_acknowledged"]!=6
            or p["previous_provider_billing_reviewed_by_operator"] is not True
            or p["cost_projection_not_provider_spend_cap_acknowledged"] is not True):
        raise InputError("FINAL_BUDGET_EXPLICIT_NEW_APPROVAL_REQUIRED")
    if (analyst_model==reviewer_model
            or type(analyst_model) is not str
            or type(reviewer_model) is not str
            or not all(re.fullmatch("[A-Za-z0-9_.:-]{2,100}",s)
                       for s in (analyst_model,reviewer_model))
            or (p["analyst_model"],p["reviewer_model"])!=
               (analyst_model,reviewer_model)):
        raise InputError("FINAL_BUDGET_INDEPENDENT_MODEL_IDENTITY_INVALID")
    if now.tzinfo is None or now.utcoffset().total_seconds()!=0:
        raise InputError("FINAL_BUDGET_PC_CLOCK_INVALID")
    current=int(now.timestamp())
    approved=_utc(p["approved_at_utc"])
    expires=_utc(p["expires_at_utc"])
    if (not 0<=current-approved<=31*86400 or
            not approved<expires<=approved+31*86400 or current>expires
            or p["month_utc"]!=now.strftime("%Y-%m")):
        raise InputError("FINAL_BUDGET_APPROVAL_EXPIRED_OR_WRONG_MONTH")
    max_calls=p["max_incremental_calls"]
    max_jpy=p["max_incremental_jpy"]
    per=p["reserve_jpy_per_two_model_decision"]
    if (type(max_calls) is not int or not 2<=max_calls<=MAX_CALLS
            or max_calls%2 or type(max_jpy) is not int
            or not 1<=max_jpy<=MAX_JPY
            or type(per) is not int or not 1<=per<=max_jpy):
        raise InputError("FINAL_BUDGET_CAP_INVALID")
    costs=p["model_rates_jpy_per_million"]
    if type(costs) is not dict or set(costs)!={analyst_model,reviewer_model}:
        raise InputError("FINAL_BUDGET_PRICE_MODELS_MISMATCH")
    # A response request has a bounded <=50k-byte evidence packet and at
    # most 1800 generated tokens. 60k input tokens is a conservative upper
    # bound for this fixed small text-only template; extra 2x margin.
    # This is NOT an unconditional guarantee about provider charges.
    projected=D(0)
    for model in (analyst_model,reviewer_model):
        rates=costs[model]
        if type(rates) is not dict or set(rates)!={"input","output"}:
            raise InputError("FINAL_BUDGET_RATE_FIELDS_MISSING")
        inbound=_amount(rates["input"])
        outbound=_amount(rates["output"])
        projected+=(inbound*D(60000)+outbound*D(1800))/D(1000000)
    conservative=int((projected*D(2)).to_integral_value(
        rounding=ROUND_CEILING))
    if per<conservative:
        raise InputError("FINAL_BUDGET_RESERVE_NOT_CONSERVATIVE")
    name=p["pricing_original_basename"]
    sha=p["pricing_original_sha256"]
    if (type(name) is not str or FN.fullmatch(name) is None
            or type(sha) is not str or HEX.fullmatch(sha) is None):
        raise InputError("FINAL_BUDGET_PRICE_SOURCE_UNSAFE")
    evidence=path.parent/name
    if (not evidence.is_file() or evidence.is_symlink()
            or any(x.is_symlink() for x in evidence.parents)
            or not 0<evidence.stat().st_size<=500000
            or hashlib.sha256(evidence.read_bytes()).hexdigest()!=sha):
        raise InputError("FINAL_BUDGET_PRICE_SOURCE_UNVERIFIED")
    return {
        "policy_sha256_local_only":hashlib.sha256(raw).hexdigest(),
        "session_binding_sha256":session_binding_sha,
        "max_calls":max_calls,
        "max_jpy":max_jpy,
        "reserve_per_pair_jpy":per,
        "minimum_computed_conservative_reserve_jpy":conservative,
        "approved_models":[analyst_model,reviewer_model],
        "authorized_month":p["month_utc"],
        "provider_invoice_yen_amount_independently_verified_by_code":False,
        "new_paid_dispatch_requires_explicit_cli_opt_in":True,
    }


def _load(folder:Path)->dict:
    if (not folder.is_dir() or folder.is_symlink()
            or any(x.is_symlink() for x in folder.parents)):
        raise InputError("FINAL_BUDGET_LEDGER_DIRECTORY_UNSAFE")
    files=sorted(folder.glob("*.json"))
    if len(files)>MAX_LEDGER_EVENTS:
        raise InputError("FINAL_BUDGET_LEDGER_TOO_MANY_ENTRIES")
    prev="0"*64
    pending={}
    settled=[]
    reservations={}
    used_jpy=0
    used_calls=0
    for seq,file in enumerate(files,1):
        if (file.name!=f"{seq:08d}.json" or file.is_symlink()
                or not file.is_file()
                or not 0<file.stat().st_size<=8000):
            raise InputError("FINAL_BUDGET_LEDGER_SEQUENCE_INVALID")
        try:
            data=json.loads(file.read_text("utf-8-sig"))
        except (UnicodeError,ValueError) as exc:
            raise InputError("FINAL_BUDGET_LEDGER_JSON_INVALID") from exc
        if (type(data) is not dict or set(data)!={
                "schema","sequence","previous_sha256","action","pair",
                "packet_sha256","reserve_jpy","linked_reserve_sha256",
                "model_calls","ai_ledger_sha256","recorded_at_utc","event_sha256"}
                or data["schema"]!=LEDGER_SCHEMA or data["sequence"]!=seq
                or data["previous_sha256"]!=prev
                or data["action"] not in ("RESERVED","SETTLED")
                or data["pair"] not in paper.PAIRS
                or type(data["packet_sha256"]) is not str
                or HEX.fullmatch(data["packet_sha256"]) is None
                or type(data["reserve_jpy"]) is not int
                or data["reserve_jpy"]<=0
                or data["reserve_jpy"]>MAX_JPY
                or _hash({k:v for k,v in data.items()
                          if k!="event_sha256"})!=data["event_sha256"]):
            raise InputError("FINAL_BUDGET_LEDGER_HASH_OR_STATE_INVALID")
        _utc(data["recorded_at_utc"])
        sha=data["event_sha256"]
        if data["action"]=="RESERVED":
            if (data["linked_reserve_sha256"] is not None
                    or data["model_calls"]!=2
                    or data["ai_ledger_sha256"] is not None
                    or sha in reservations
                    or any(item["packet_sha256"]==data["packet_sha256"]
                           for item in reservations.values())):
                raise InputError("FINAL_BUDGET_DUPLICATE_OR_UNSAFE_RESERVATION")
            reservations[sha]=data
            pending[sha]=data
            used_calls+=2
            used_jpy+=data["reserve_jpy"]
        else:
            parent=data["linked_reserve_sha256"]
            if (type(parent) is not str or parent not in pending
                    or data["packet_sha256"]!=pending[parent]["packet_sha256"]
                    or data["pair"]!=pending[parent]["pair"]
                    or data["reserve_jpy"]!=pending[parent]["reserve_jpy"]
                    or data["model_calls"]!=2
                    or type(data["ai_ledger_sha256"]) is not str
                    or HEX.fullmatch(data["ai_ledger_sha256"]) is None):
                raise InputError("FINAL_BUDGET_SETTLEMENT_NOT_MATCHED")
            settled.append(parent)
            del pending[parent]
        prev=sha
    return {
        "head_sha256":prev,
        "sequence":len(files),
        "pending_reservations":pending,
        "settled_reserve_shas":settled,
        "spent_or_reserved_calls":used_calls,
        "spent_or_reserved_jpy":used_jpy,
        "all_reserved_packet_shas":{v["packet_sha256"]
                                    for v in reservations.values()},
    }


def check(policy_info:dict,folder:Path,*,journal_reserve_shas:list[str])->dict:
    if (type(journal_reserve_shas) is not list
            or any(type(s) is not str or HEX.fullmatch(s) is None
                   for s in journal_reserve_shas)
            or len(set(journal_reserve_shas))!=len(journal_reserve_shas)):
        raise InputError("FINAL_BUDGET_PAPER_RECEIPTS_INVALID")
    state=_load(folder)
    if (state["pending_reservations"]
            or state["settled_reserve_shas"]!=journal_reserve_shas
            or state["spent_or_reserved_calls"]>policy_info["max_calls"]
            or state["spent_or_reserved_jpy"]>policy_info["max_jpy"]):
        raise InputError("FINAL_BUDGET_LEDGER_PAPER_UNRECONCILED_OR_OVER_CAP")
    return state


def _record(folder:Path,state:dict,*,action:str,pair:str,packet_sha:str,
            reserve_jpy:int,linked_reserve_sha:str|None,model_calls:int,
            ai_ledger_sha:str|None,now:datetime)->str:
    if now.tzinfo is None or now.utcoffset().total_seconds()!=0:
        raise InputError("FINAL_BUDGET_TIME_NOT_UTC")
    seq=state["sequence"]+1
    if seq>MAX_LEDGER_EVENTS:
        raise InputError("FINAL_BUDGET_LEDGER_FULL")
    entry={
        "schema":LEDGER_SCHEMA,
        "sequence":seq,
        "previous_sha256":state["head_sha256"],
        "action":action,"pair":pair,"packet_sha256":packet_sha,
        "reserve_jpy":reserve_jpy,
        "linked_reserve_sha256":linked_reserve_sha,
        "model_calls":model_calls,
        "ai_ledger_sha256":ai_ledger_sha,
        "recorded_at_utc":now.isoformat().replace("+00:00","Z"),
    }
    entry["event_sha256"]=_hash(entry)
    name=folder/f"{seq:08d}.json"
    with name.open("x",encoding="utf-8") as f:
        json.dump(entry,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    return entry["event_sha256"]


def reserve(policy_info:dict,folder:Path,*,journal_reserve_shas:list[str],
            pair:str,packet_sha:str,now:datetime)->str:
    state=check(policy_info,folder,journal_reserve_shas=journal_reserve_shas)
    if (pair not in paper.PAIRS or type(packet_sha) is not str
            or HEX.fullmatch(packet_sha) is None
            or packet_sha in state["all_reserved_packet_shas"]
            or state["spent_or_reserved_calls"]+2>policy_info["max_calls"]
            or state["spent_or_reserved_jpy"]+
               policy_info["reserve_per_pair_jpy"]>policy_info["max_jpy"]):
        raise InputError("FINAL_BUDGET_LIMIT_OR_REPEAT_REACHED")
    return _record(folder,state,action="RESERVED",pair=pair,
                   packet_sha=packet_sha,
                   reserve_jpy=policy_info["reserve_per_pair_jpy"],
                   linked_reserve_sha=None,model_calls=2,
                   ai_ledger_sha=None,now=now)


def settle(folder:Path,*,reserve_sha:str,ledger:Path,now:datetime)->None:
    state=_load(folder)
    item=state["pending_reservations"].get(reserve_sha)
    if item is None or len(state["pending_reservations"])!=1:
        raise InputError("FINAL_BUDGET_UNKNOWN_OUTSTANDING_RESERVATION")
    if (not ledger.is_file() or ledger.is_symlink()
            or not 0<ledger.stat().st_size<=30000):
        raise InputError("FINAL_BUDGET_COMPLETE_LEDGER_MISSING")
    from research import final_demo_http401_recovery as reader
    valid,sha=reader._read_ledger(ledger)
    if (valid["stage"]!="COMPLETE" or valid["pending_role"] is not None
            or valid["analyst"] is None or valid["reviewer"] is None):
        raise InputError("FINAL_BUDGET_LEDGER_UNFINISHED")
    _record(folder,state,action="SETTLED",pair=item["pair"],
            packet_sha=item["packet_sha256"],
            reserve_jpy=item["reserve_jpy"],
            linked_reserve_sha=reserve_sha,model_calls=2,
            ai_ledger_sha=sha,now=now)


def reserve_status(policy_info:dict,folder:Path)->dict:
    state=_load(folder)
    return {
        "status":"FINAL_PAPER_CONSERVATIVE_BUDGET_ACCOUNTING_NO_BROKER",
        "old_historical_paid_calls_preserved":6,
        "new_ai_calls_reserved_or_used":state["spent_or_reserved_calls"],
        "new_jpy_worst_case_reserved":state["spent_or_reserved_jpy"],
        "pending_unknown_billed_dispatch_count":
            len(state["pending_reservations"]),
        "human_approved_jpy_ceiling":policy_info["max_jpy"],
        "provider_actual_invoice_independently_reconciled":False,
        "broker_orders_permitted":False,
    }
