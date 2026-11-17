"""Explicit bounded two-model AI review of MT4 CLOSED H1 + official news.

This is research only. No order intent, broker interaction, scheduler or
implicit API charges. Each potentially charged dispatch is persisted before
the request; ambiguous requests are NEVER retried automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from research import final_demo_periodic as period
from research import ai_provider_comparison as providers
from research import ai_provider_annual_audit as annual
from research import macro_ai_generate as provider_api
from research.offline_backtest import InputError

SCHEMA = "fx_final_demo_periodic_two_model_v1"


def _identity(report, analyst_model: str, reviewer_model: str)->dict:
    providers.ResearchRoleRegistry(analyst_model=analyst_model,
                                   reviewer_model=reviewer_model)
    packet=report["ai_input_packet_research_only"]
    raw=providers._packet_text(packet)
    return {
        "schema":SCHEMA,
        "packet_sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "analyst_model":analyst_model,
        "reviewer_model":reviewer_model,
        "stage":"ANALYST_PENDING","pending_role":None,
        "analyst":None,"reviewer":None,
        "execution_authorized":False,
        "real_orders_permitted":False}


def _valid(state: dict, identity: dict)->None:
    if (type(state) is not dict or set(state)!=set(identity)
            or any(state[k]!=identity[k] for k in (
                "schema","packet_sha256","analyst_model",
                "reviewer_model","execution_authorized",
                "real_orders_permitted"))
            or state["stage"] not in (
                "ANALYST_PENDING","REVIEW_PENDING","COMPLETE")
            or state["pending_role"] not in (None,"analyst","reviewer")):
        raise InputError("corrupted model handoff ledger")
    a=state["analyst"]
    v=state["reviewer"]
    if a is not None and (
            type(a) is not dict or set(a)!={
                "action","hypothesis","counterevidence"}
            or a["action"] not in ("LONG","SHORT","HOLD","FLAT")
            or any(type(a[k]) is not str or not 0<len(a[k])<=1500
                   for k in ("hypothesis","counterevidence"))):
        raise InputError("invalid saved analyst response")
    if v is not None and (
            type(v) is not dict or set(v)!={"verdict","rationale"}
            or v["verdict"] not in (
                "APPROVED","REVISION","REJECTED","PENDING")
            or type(v["rationale"]) is not str
            or not 0<len(v["rationale"])<=1500):
        raise InputError("invalid saved independent review")
    if ((state["stage"]=="ANALYST_PENDING" and (a or v))
            or (state["stage"]=="REVIEW_PENDING" and (a is None or v))
            or (state["stage"]=="COMPLETE" and (a is None or v is None))):
        raise InputError("invalid model stage transition")


def run(captures:Path,bundles:list[Path],pair:str,ledger:Path,*,
        analyst_model:str,reviewer_model:str,
        allow_external_api:bool=False,max_api_calls:int=0,
        now:datetime|None=None,inference=None)->dict:
    now=period._clock(now or datetime.now(timezone.utc))
    if (type(max_api_calls) is not int or not 0<=max_api_calls<=2
            or bool(max_api_calls)!=allow_external_api
            or ledger.is_symlink()
            or any(p.is_symlink() for p in ledger.parents)
            or not ledger.parent.is_dir()):
        raise InputError("invalid explicit AI call bound or ledger")
    report=period.run(captures,bundles,pair,ledger,now=now,
                      output_must_be_new=False)
    identity=_identity(report,analyst_model,reviewer_model)
    if not report["macro_coverage_complete_research_only"]:
        return {
            "schema":SCHEMA,
            "status":"PERIODIC_MACRO_COVERAGE_INCOMPLETE_NO_AI_NO_GO",
            "paid_calls_this_run":0,"orders_sent_this_run":0,
            "model_verdict":None,"demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO","safety_hold_latched":True}
    if not allow_external_api and not ledger.exists():
        return {
            "schema":SCHEMA,
            "status":"PERIODIC_AI_PREFLIGHT_ONLY_NO_GO",
            "paid_calls_this_run":0,"orders_sent_this_run":0,
            "packet_sha256_local_only":identity["packet_sha256"],
            "model_verdict":None,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO","safety_hold_latched":True}
    if ledger.exists():
        if not ledger.is_file() or not 0<ledger.stat().st_size<=30_000:
            raise InputError("untrusted model ledger")
        saved=json.loads(ledger.read_text("utf-8-sig"))
        _valid(saved,identity)
        state=saved
    else:
        if not allow_external_api:
            raise InputError("missing opt-in")
        with ledger.open("x",encoding="utf-8") as handle:
            json.dump(identity,handle,indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        state=identity
    if state["pending_role"] is not None:
        raise InputError("ambiguous billable dispatch; manual review required")
    calls=0
    if allow_external_api:
        key=os.environ.get("OPENAI_API_KEY","")
        if not key:
            raise InputError("explicit API key absent")
        registry=providers.ResearchRoleRegistry(
            analyst_model=analyst_model,reviewer_model=reviewer_model)
        packet=report["ai_input_packet_research_only"]
        while calls<max_api_calls and state["stage"]!="COMPLETE":
            role="analyst" if state["stage"]=="ANALYST_PENDING" else "reviewer"
            state["pending_role"]=role
            annual._atomic_json(ledger,state)
            if role=="analyst":
                if inference is None:
                    answer=registry.macro_hypothesis(
                        packet,api_key=key)["result"]
                else:
                    answer=registry.macro_hypothesis(
                        packet,api_key=key,inference=inference)["result"]
                state["analyst"]=answer
                state["stage"]="REVIEW_PENDING"
            else:
                if inference is None:
                    answer=registry.independent_review(
                        packet,state["analyst"],api_key=key)["result"]
                else:
                    answer=registry.independent_review(
                        packet,state["analyst"],api_key=key,
                        inference=inference)["result"]
                state["reviewer"]=answer
                state["stage"]="COMPLETE"
            state["pending_role"]=None
            annual._atomic_json(ledger,state)
            calls+=1
    _valid(state,identity)
    verdict=(state["reviewer"]["verdict"] if state["stage"]=="COMPLETE"
             else None)
    return {
        "schema":SCHEMA,
        "status":("PERIODIC_AI_TWO_MODELS_REVIEWED_RESEARCH_NO_GO"
                  if verdict is not None else
                  "PERIODIC_AI_PARTIAL_RESEARCH_NO_GO"),
        "pair":pair,
        "packet_sha256_local_only":identity["packet_sha256"],
        "stage":state["stage"],
        "model_verdict":verdict,
        "model_action_research_only":(
            state["analyst"]["action"] if verdict is not None else None),
        "paid_calls_this_run":calls,
        "orders_sent_this_run":0,
        "candidate_is_not_an_executable_order":True,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO","safety_hold_latched":True}



# Diagnostics are intentionally metadata-only. Never emit API credentials,
# prompt payloads, model text, HTTP response bodies, or local source paths.
SAFE_API_REASONS = frozenset({
    "HTTP_400_INVALID_REQUEST_OR_MODEL_OPTIONS",
    "HTTP_401_INVALID_API_KEY",
    "HTTP_403_PERMISSION_DENIED",
    "HTTP_404_MODEL_UNAVAILABLE_OR_NOT_FOUND",
    "HTTP_429_RATE_OR_QUOTA_LIMIT",
    "HTTP_5XX_PROVIDER_FAILURE",
    "HTTP_OTHER_API_FAILURE",
    "NETWORK_OR_TIMEOUT",
    "INPUT_TOO_LARGE_LOCAL",
    "AI_RESPONSE_TOO_LARGE",
    "INCOMPLETE_AI_RESPONSE",
    "MISSING_OR_MULTIPLE_OUTPUT_TEXT",
    "INVALID_OR_MALFORMED_RESPONSE",
})


def safe_failure_report(exc: Exception, ledger: Path)->dict:
    """Non-secret failure category and existing billing ledger state only."""
    result = {
        "schema":SCHEMA,
        "status":"PERIODIC_AI_FAIL_CLOSED_CHECK_LEDGER_NO_GO",
        "failure_category":"LOCAL_PREFLIGHT_OR_VALIDATION",
        "ledger_state":"ABSENT",
        "pending_role":"NONE",
        "api_dispatch_may_have_occurred":False,
        "retry_permitted":False,
        "orders_sent_this_run":0,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }
    if isinstance(exc, provider_api.MacroAPIError):
        reason=exc.reason
        result["failure_category"]=(
            reason if reason in SAFE_API_REASONS else "PROVIDER_ERROR")
        # A locally rejected request may fail before dispatch too.
        result["api_dispatch_may_have_occurred"]=True
        for key in ("api_param","api_code","message_category"):
            val=getattr(exc,key,"UNKNOWN")
            # Categories are generated by an existing closed allowlist.
            if type(val) is str and 1<=len(val)<=64 and all(
                    ch.isalnum() or ch=="_" or ch=="." for ch in val):
                result[key]=val
    try:
        if ledger.is_file() and not ledger.is_symlink():
            if ledger.stat().st_size > 30000:
                result["ledger_state"]="TOO_LARGE"
            else:
                data=json.loads(ledger.read_text("utf-8-sig"))
                if type(data) is dict:
                    stage=data.get("stage")
                    role=data.get("pending_role")
                    result["ledger_state"]=(
                        stage if stage in (
                            "ANALYST_PENDING","REVIEW_PENDING","COMPLETE")
                        else "UNRECOGNIZED")
                    result["pending_role"]=(
                        role if role in ("analyst","reviewer") else "NONE")
                    if role in ("analyst","reviewer"):
                        result["api_dispatch_may_have_occurred"]=True
                else:
                    result["ledger_state"]="UNRECOGNIZED"
    except (OSError,ValueError,TypeError,UnicodeError):
        result["ledger_state"]="UNREADABLE"
    return result


def main(argv=None)->int:
    p=argparse.ArgumentParser(
        description="One-shot real H1 and news AI research, no orders")
    p.add_argument("--captures",required=True,type=Path)
    p.add_argument("--news-bundle",action="append",required=True,type=Path)
    p.add_argument("--pair",required=True,choices=tuple(period.PAIRS))
    p.add_argument("--ledger",required=True,type=Path)
    p.add_argument("--analyst-model",required=True)
    p.add_argument("--reviewer-model",required=True)
    p.add_argument("--allow-external-api",action="store_true")
    p.add_argument("--max-api-calls",type=int,default=0)
    args=p.parse_args(argv)
    try:
        result=run(args.captures,args.news_bundle,args.pair,args.ledger,
                   analyst_model=args.analyst_model,
                   reviewer_model=args.reviewer_model,
                   allow_external_api=args.allow_external_api,
                   max_api_calls=args.max_api_calls)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,ValueError,KeyError,TypeError,OSError,
            UnicodeError,OverflowError,ArithmeticError,ET.ParseError) as exc:
        print(json.dumps(safe_failure_report(exc,args.ledger),
                         ensure_ascii=False))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
