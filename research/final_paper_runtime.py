"""FINAL-PAPER-07: local Windows continuous virtual FX portfolio supervisor.

Reads only DEMO MT4 MQL4/Files CSV snapshots from read-only observer.
No broker/client/executor imports, orders, order intents, or Jev provider.
Optional TWO-MODEL paid research is an explicit bounded test, not an
unlimited unattended paid API service. Evidence is append-only hash chained.
On errors ambiguous AI ledger/portfolio events are NOT retried automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from research import final_demo_http401_recovery as review401
from research import final_demo_periodic as period
from research import final_demo_periodic_ai as ai
from research import final_paper_engine as paper
from research import final_paper_event_blackout as blackout
from research import final_paper_completed_decision as completed_decision
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_runtime_journal_v1"
PAPER_QUOTE = re.compile(r"^FxPaperQuote_[0-9]{8}_[0-9]{6}\.csv$")
PAPER_H1 = re.compile(r"^FxDemoH1_USDJPY_([0-9]{8}_[0-9]{6})\.csv$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_RECORDS = 100000
MAX_PAID_LIFETIME = 6


def _digest(item: dict) -> str:
    return hashlib.sha256(json.dumps(item,ensure_ascii=False,
        sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode("utf-8")).hexdigest()


def _journal_load(folder: Path) -> tuple[dict,str]:
    if not folder.is_dir() or folder.is_symlink():
        raise InputError("paper journal folder missing")
    names=sorted(folder.glob("*.json"))
    # Reject extra files and gaps; no automatic repair of interrupted writes.
    if len(names)>MAX_RECORDS:
        raise InputError("paper journal size cap")
    prior="0"*64
    state=paper.initial_state()
    for index,file in enumerate(names,1):
        if (file.name!=f"{index:08d}.json" or file.is_symlink()
                or not 0<file.stat().st_size<500_000):
            raise InputError("corrupt paper journal filenames")
        record=json.loads(file.read_text("utf-8-sig"))
        if (type(record) is not dict or set(record)!={
                "schema","previous_sha256","state","event_sha256",
                "quote_sha256","recorded_at_utc"}
                or record["schema"]!=SCHEMA
                or record["previous_sha256"]!=prior
                or type(record["state"]) is not dict
                or record["state"].get("cycle_number")!=index):
            raise InputError("paper journal chain broken")
        digest=record["event_sha256"]
        if type(digest) is not str or not SHA.fullmatch(digest):
            raise InputError("bad journal hash")
        content={k:v for k,v in record.items() if k!="event_sha256"}
        if _digest(content)!=digest:
            raise InputError("paper journal altered")
        state=record["state"]
        if (state.get("virtual_only") is not True
                or state.get("broker_orders_permitted") is not False
                or state.get("jev_required") is not False):
            raise InputError("paper journal contains unsafe state")
        prior=digest
    return state,prior


def _journal_append(folder:Path,state:dict,previous:str,
                    quote_sha:str,now:datetime)->str:
    seq=state["cycle_number"]
    target=folder/f"{seq:08d}.json"
    if target.exists() or target.is_symlink():
        raise InputError("paper journal overwrite refused")
    content={
        "schema":SCHEMA,"previous_sha256":previous,
        "state":state,"quote_sha256":quote_sha,
        "recorded_at_utc":now.isoformat().replace("+00:00","Z")}
    content["event_sha256"]=_digest(content)
    with target.open("x",encoding="utf-8") as f:
        json.dump(content,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    return content["event_sha256"]


def _latest_quote(mt4: Path, now:datetime)->dict|None:
    files=sorted(
        (p for p in mt4.glob("FxPaperQuote_*.csv")
         if PAPER_QUOTE.fullmatch(p.name)),key=lambda p:p.name,
        reverse=True)
    if not files:
        return None
    # Do not inspect a quote while MT4 still has it open for writing.
    if now.timestamp()-files[0].stat().st_mtime<2:
        return None
    return paper.validate_quotes(files[0],now=now)


def _latest_h1_copy(mt4:Path,archive:Path,now:datetime)->Path|None:
    # A new closed-H1 export creates 3 files with an identical shared stamp.
    recent=sorted(
        (p for p in mt4.glob("FxDemoH1_USDJPY_*.csv")
         if PAPER_H1.fullmatch(p.name)),key=lambda p:p.name,reverse=True)
    if not recent:
        return None
    stamp=PAPER_H1.fullmatch(recent[0].name).group(1)
    dst=archive/("h1_"+stamp)
    if dst.is_dir() and not dst.is_symlink():
        return dst
    if dst.exists() or dst.is_symlink():
        raise InputError("unsafe capture archive")
    filepaths=[mt4/f"FxDemoH1_{sym}_{stamp}.csv" for sym in paper.SYMS]
    if any(not f.is_file() or f.is_symlink() for f in filepaths):
        return None
    # MT4 writes one CSV at a time. Delay until all three are closed.
    if any(now.timestamp()-f.stat().st_mtime<2 for f in filepaths):
        return None
    staging=archive/("staging_"+stamp)
    if staging.exists() or staging.is_symlink():
        raise InputError("unreviewed paper capture staging folder")
    staging.mkdir()
    try:
        for source in filepaths:
            shutil.copyfile(source,staging/source.name)
        # This checks atomic same-stamp 3-pair capture and all 120 bars.
        period._read_h1(staging,now)
        staging.rename(dst)
    except InputError:
        # Remove only an unpublished local temporary copy, not source data.
        for copied in staging.glob("*.csv"):
            copied.unlink()
        staging.rmdir()
        return None
    return dst


def _signals_for_new_h1(
        state:dict,captures:Path|None,bundles:list[Path],root:Path,
        now:datetime,*,allow_paid:bool,analyst_model:str,
        reviewer_model:str,max_paid_calls:int)->tuple[list[dict],list[str],int]:
    if captures is None:
        return [],[],0
    # Some stored snapshots are still valid price observations, but AI
    # may use them only during the current 10-minute H1 freshness window.
    try:
        data=period._read_h1(captures,now)
    except InputError:
        return [],[],0
    freshbar=data["captures"]
    signals=[]
    considered=[]
    used=0
    for pair in paper.PAIRS:
        bar=freshbar[period.PAIRS[pair]]["candles"][-1]["server_epoch"]
        key=f"{pair}:{bar}"
        if key in state["processed_h1_keys"]:
            continue
        # A PREEXISTING complete two-model ledger may supply a fresh signal
        # without a new paid request. It must match the exact archived
        # H1/official-news packet. Never replay a handled H1 decision.
        if bundles:
            saved = completed_decision.load_completed(
                root, captures, bundles, pair, bar, now)
            if saved is not None:
                legacy_id=hashlib.sha256((
                    pair+":"+str(bar)+":"+saved["packet_sha256"]
                ).encode("utf-8")).hexdigest()
                prior_ids=set(state["used_signal_ids"])
                prior_ids.update(x["id"] for x in state["pending_signals"])
                if saved["id"] not in prior_ids and legacy_id not in prior_ids:
                    signals.append(saved)
                considered.append(key)
                continue
        if not allow_paid or not bundles:
            considered.append(key)
            continue
        if state["paid_inference_calls"]+used+2>max_paid_calls:
            considered.append(key)
            continue
        packet=period.run(captures,bundles,pair,root/"unused.json",
                          now=now,output_must_be_new=False)
        if not packet["macro_coverage_complete_research_only"]:
            considered.append(key)
            continue
        ai_folder=root/"ai_research"
        # Before any billable API request, make sure all older dispatches
        # have a clear terminal result; unknown requests always halt.
        review401.check_directory(ai_folder)
        stamp=now.strftime("%Y%m%d_%H%M%S")
        ledger=ai_folder/(
            f"ai_{paper.SYMS[paper.PAIRS.index(pair)]}_{bar}_{stamp}.json")
        if ledger.exists() or ledger.is_symlink():
            raise InputError("existing AI paper ledger requires manual review")
        output=ai.run(
            captures,bundles,pair,ledger,
            analyst_model=analyst_model,reviewer_model=reviewer_model,
            allow_external_api=True,max_api_calls=2,now=now)
        if output["stage"]!="COMPLETE":
            raise InputError("incomplete two-model research")
        used+=output["paid_calls_this_run"]
        identity=output["packet_sha256_local_only"]
        reviewed=int(datetime.now(timezone.utc).timestamp())
        sig={
            "id":hashlib.sha256((
                pair+":"+str(bar)+":"+identity).encode()).hexdigest(),
            "pair":pair,"action":output["model_action_research_only"],
            "verdict":output["model_verdict"],
            "reviewed_epoch":reviewed,
            "atr14":str(packet["technical"]["atr14"]),
            "packet_sha256":identity,
        }
        signals.append(sig)
        considered.append(key)
    return signals,considered,used


def run_one_cycle(mt4:Path,root:Path,bundles:list[Path], *,
                  allow_paid:bool,analyst_model:str,reviewer_model:str,
                  paid_limit:int,now:datetime|None=None,
                  event_blackout_file:Path|None=None,
                  final_auto_evidence:Path|None=None,
                  final_auto_official_archive:Path|None=None,
                  final_auto_budget_authorization:Path|None=None,
                  allow_final_paid:bool=False)->dict:
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise InputError("invalid current clock")
    journal=root/"journal"
    state,prior=_journal_load(journal)
    quote=_latest_quote(mt4,now)
    if quote is None:
        return {"status":"PAPER_WAITING_FOR_FIRST_DEMO_QUOTE",
                "broker_orders_sent_this_run":0,
                "real_orders_permitted":False}
    if quote["capture_epoch"]<=state["last_quote_epoch"]:
        gap=max(0,int(now.timestamp())-state["last_quote_epoch"])
        level="LEVEL2" if gap>=600 else "LEVEL1" if gap>=60 else "NONE"
        return {"status":"PAPER_WAITING_FOR_NEXT_QUOTE",
                "last_quote_elapsed_seconds":gap,
                "interruption_warning":level,
                "new_virtual_positions_allowed":False,
                "broker_orders_sent_this_run":0,
                "real_orders_permitted":False}
    known_blackout=blackout.check(event_blackout_file,
                                  quote["capture_epoch"],now=now)
    # Consume a single operator-staged permission only on a new fresh quote.
    # This never relaxes independent calendar/clock/AI/transaction gates.
    from research import final_paper_manual_comm_release as comm_release
    working_state, manual_comm_release_applied = comm_release.apply_if_valid(
        root, state, prior, quote, now)
    # Integration is opt-in only on a separately operator-started process.
    # The existing Windows monitor runs WITHOUT these arguments and remains
    # in immutable historical 6/6 paid/quote-only mode.
    from research import final_paper_auto_entry_gate as final_gate
    from research import final_paper_auto_budget as final_budget
    from research import final_paper_current_comm_release as current_comm
    from research import final_paper_auto_pipeline as final_pipeline
    if allow_final_paid and (final_auto_evidence is None or
                             final_auto_official_archive is None or
                             final_auto_budget_authorization is None or
                             allow_paid):
        raise InputError("FINAL_AUTO_PAID_REQUIRES_SEPARATE_APPROVAL")
    if (final_auto_evidence is None)!=(final_auto_official_archive is None):
        raise InputError("FINAL_AUTO_EVIDENCE_PATHS_INCOMPLETE")
    integrated=final_auto_evidence is not None
    current_release_applied=False
    if integrated:
        working_state,current_release_applied=current_comm.apply_if_valid(
            root,working_state,prior,quote,now)
    session_binding=state.get("auto_entry_session_binding_sha256",prior)
    gate_report=None
    gate_blocked_reason="NO_ATTESTED_ENTRY_BUNDLE"
    carry_costs=(state.get("auto_carry_costs_jpy_per_lot_day")
                 if integrated else None)
    budget_info=None
    if integrated:
        if (state.get("paid_inference_calls")!=6
                or state.get("broker_orders_permitted") is not False):
            raise InputError("FINAL_AUTO_OLD_AI_LEDGER_OR_BROKER_STATE_UNSAFE")
        try:
            original_path=mt4/("FxPaperQuote_"+
                datetime.fromtimestamp(quote["capture_epoch"],tz=timezone.utc)
                .strftime("%Y%m%d_%H%M%S")+".csv")
            gate_report=final_gate.evaluate(
                final_auto_evidence,final_auto_official_archive,
                {**quote,"source_original_file":original_path},
                now=now,entry_binding_sha=session_binding)
            if (state.get("auto_entry_permit_sha256") not in (
                    None,gate_report["permit_sha256_local_only"])):
                raise InputError("FINAL_AUTO_ENTRY_PERMIT_CHANGED_MID_SESSION")
            carry_costs=gate_report["carry_costs_jpy_per_lot_day"]
            gate_blocked_reason="NONE"
        except (InputError,OSError,KeyError,ValueError,TypeError,
                UnicodeError,ArithmeticError):
            # Fail CLOSED for new entries, but still value/stop already
            # open virtual positions with their last conservative carry.
            gate_report=None
            gate_blocked_reason="ENTRY_EVIDENCE_INCOMPLETE_OR_EXPIRED"
        if allow_final_paid and gate_report is not None:
            try:
                budget_info=final_budget.policy(
                    final_auto_budget_authorization,
                    now=now,session_binding_sha=session_binding,
                    analyst_model=analyst_model,
                    reviewer_model=reviewer_model)
                if state.get("auto_budget_policy_sha256") not in (
                        None,budget_info["policy_sha256_local_only"]):
                    raise InputError("FINAL_AUTO_PAID_POLICY_CHANGED_IN_SESSION")
                final_budget.check(
                    budget_info,root/"auto_budget_journal",
                    journal_reserve_shas=state.get(
                        "auto_budget_reservation_receipts",[]))
                from research import final_paper_ai_continuation_audit as old_paid_audit
                old_paid=old_paid_audit.audit(root)
                if (old_paid["journal_head_sha256_local_only"]!=prior
                        or old_paid["paid_calls_in_completed_ledgers"]!=6
                        or old_paid["paid_calls_recorded_in_journal"]!=6):
                    raise InputError("FINAL_AUTO_HISTORICAL_PAID_SIX_UNRECONCILED")
            except (InputError,OSError,KeyError,ValueError,TypeError,
                    UnicodeError,ArithmeticError):
                budget_info=None
                gate_blocked_reason="PAID_BUDGET_PENDING_UNRECONCILED_OR_EXPIRED"
    # The local known-event list is NOT an independently verified complete
    # three-currency calendar, and the broker clock is also unattested.
    # The runnable paper supervisor must not convert either absence into
    # permission to incur further AI bills or open a new virtual position.
    evidence_ready=(
        (gate_report is not None and
         gate_report["entry_evidence_ready_by_operator_attestation"] is True)
        if integrated else (
            known_blackout["independent_calendar_coverage_attested"] is True
            and known_blackout["pc_clock_independently_attested"] is True
        )
    )
    combined_blackout=(known_blackout["active_known_blackout"] or
                       bool(gate_report and
                            gate_report["known_event_blackout_active"]))
    if integrated and allow_final_paid and budget_info is None:
        evidence_ready=False
    risk_stop=any(working_state.get(name) is True for name in (
        "communication_latched","dd4_latched","dd5_latched",
        "daily_loss_latched"))
    quote_gap_safe=(
        state["last_quote_epoch"]==0 or
        quote["capture_epoch"]-state["last_quote_epoch"]<=600
    )
    # Critical isolation: a communications latch, unverified economic
    # calendar/clock or a >600s capture gap blocks BOTH paid and saved AI
    # signal evaluation. Otherwise a malformed or expired research ledger
    # could halt quote observation despite virtual entry being prohibited.
    signal_path_safe=(
        evidence_ready and not risk_stop and quote_gap_safe
        and not combined_blackout
    )
    # A healthy quote and an (eventually) approved macro clock are not
    # enough to reopen the historical paid-API ledger. The 6-call lifetime
    # ceiling is immutable without separate reviewed budget/release work.
    paid_safe=(
        allow_paid and signal_path_safe
        and type(paid_limit) is int and 0<=paid_limit<=MAX_PAID_LIFETIME
        and type(working_state.get("paid_inference_calls")) is int
        and working_state["paid_inference_calls"]+2<=paid_limit
    )
    copies=root/"captures"
    captures=_latest_h1_copy(mt4,copies,now)
    final_paid=0
    final_receipts=[]
    if signal_path_safe and integrated and allow_final_paid:
        if budget_info is None:
            raise InputError("FINAL_AUTO_PAID_BUDGET_NOT_RECONCILED")
        signals,seen,final_receipts,final_paid=final_pipeline.decisions(
            working_state,captures,bundles,root,now,policy=budget_info,
            analyst_model=analyst_model,reviewer_model=reviewer_model)
        paid=0  # Historical 6/6 lifetime is NEVER reset or incremented.
    elif signal_path_safe:
        signals,seen,paid=_signals_for_new_h1(
            working_state,captures,bundles,root,now,
            allow_paid=paid_safe,
            analyst_model=analyst_model,reviewer_model=reviewer_model,
            max_paid_calls=paid_limit)
    else:
        # Fail-closed quote-only mode still runs existing virtual exits/DD.
        signals,seen,paid=[],[],0
    changed,report=paper.step(
        working_state,quote,signals=signals,
        known_event_blackout=combined_blackout,
        entry_evidence_ready=evidence_ready,
        **({"carry_costs":carry_costs} if integrated else {}))
    changed["processed_h1_keys"].extend(seen)
    changed["paid_inference_calls"]+=paid
    if integrated:
        changed["auto_entry_session_binding_sha256"]=session_binding
        if gate_report is not None:
            changed["auto_entry_permit_sha256"]=gate_report[
                "permit_sha256_local_only"]
            changed["auto_carry_costs_jpy_per_lot_day"]=carry_costs
        if budget_info is not None:
            changed["auto_budget_policy_sha256"]=budget_info[
                "policy_sha256_local_only"]
        if final_receipts:
            changed.setdefault("auto_budget_reservation_receipts",[]).extend(
                final_receipts)
            changed["auto_new_paid_inference_calls"]=(
                changed.get("auto_new_paid_inference_calls",0)+final_paid)
    if len(changed["processed_h1_keys"])>10000:
        raise InputError("too many H1 cycles")
    _journal_append(journal,changed,prior,quote["source_sha256"],now)
    report["paid_calls_this_cycle"]=paid+final_paid
    report["new_final_paid_calls_this_cycle"]=final_paid
    report["old_6_of_6_calls_unchanged"]=integrated
    report["final_auto_mode_selected"]=integrated
    report["final_operator_evidence_source_verified_for_paper"]=bool(gate_report)
    report["final_auto_gate_hold_reason_code"]=gate_blocked_reason
    report["final_auto_incremental_budget_active"]=budget_info is not None
    report["final_comm_manual_release_applied_this_cycle"]=current_release_applied
    report["final_operator_research_gate_open"]=integrated and signal_path_safe
    report["new_virtual_positions_permitted_by_final_gate"]=(
        integrated and evidence_ready and not risk_stop and
        quote_gap_safe and not combined_blackout)
    report["paid_calls_session_cumulative"]=changed["paid_inference_calls"]
    report["h1_new_pair_count"]=len(seen)
    report["known_macro_event_blackout_active"]=combined_blackout
    report["event_calendar_supplied"]=known_blackout["calendar_supplied"]
    report["independent_future_event_calendar_attested"]=False
    report["independent_broker_clock_attested"]=False
    report["entry_readiness_gate_open"]=(evidence_ready and not risk_stop
                                          and quote_gap_safe and not combined_blackout)
    report["new_paid_ai_allowed_by_evidence_gate"]=paid_safe
    report["ai_signal_pipeline_skipped_by_unattested_safety_hold"]=not signal_path_safe
    report["manual_comm_release_applied_this_cycle"] = manual_comm_release_applied
    return report


def _initialize(root:Path)->None:
    if root.is_symlink():
        raise InputError("unsafe paper root")
    root.mkdir(exist_ok=True)
    for name in ("journal","captures","ai_research"):
        (root/name).mkdir(exist_ok=True)
        if (root/name).is_symlink():
            raise InputError("symlink paper folder")


def main(argv=None)->int:
    p=argparse.ArgumentParser(
        description="Local read-only MT4 DEMO -> internal virtual FX portfolio")
    p.add_argument("--mt4-files",type=Path,required=True)
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--news-bundle",type=Path,action="append",default=[])
    p.add_argument("--analyst-model",default="")
    p.add_argument("--reviewer-model",default="")
    p.add_argument("--allow-paid-ai",action="store_true")
    p.add_argument("--max-paid-calls-lifetime",type=int,default=0)
    p.add_argument("--watch",action="store_true")
    p.add_argument("--interval-seconds",type=int,default=15)
    p.add_argument("--event-blackout-file",type=Path)
    p.add_argument("--final-auto-evidence-file",type=Path)
    p.add_argument("--final-auto-official-archive",type=Path)
    p.add_argument("--final-auto-budget-authorization",type=Path)
    p.add_argument("--allow-final-paid-ai",action="store_true")
    args=p.parse_args(argv)
    acquired=False
    lock=args.state_root/".single_operator.lock"
    try:
        if (not args.mt4_files.is_dir() or args.mt4_files.is_symlink()
                or not str(args.mt4_files.resolve()).lower().endswith(
                    os.path.join("MQL4","Files").lower())
                or len(args.news_bundle)>5
                or not 5<=args.interval_seconds<=60
                or type(args.max_paid_calls_lifetime) is not int
                or not 0<=args.max_paid_calls_lifetime<=MAX_PAID_LIFETIME
                or args.allow_paid_ai != bool(args.max_paid_calls_lifetime)
                or (args.allow_paid_ai and (
                    not args.news_bundle or
                    not args.analyst_model or not args.reviewer_model or
                    args.analyst_model==args.reviewer_model or
                    not os.environ.get("OPENAI_API_KEY")))
                or (not (args.allow_paid_ai or args.allow_final_paid_ai) and (
                    args.analyst_model or args.reviewer_model))
                or (args.allow_final_paid_ai and (
                    args.allow_paid_ai or not args.news_bundle or
                    not args.analyst_model or not args.reviewer_model or
                    args.analyst_model==args.reviewer_model or
                    not os.environ.get("OPENAI_API_KEY") or
                    args.final_auto_budget_authorization is None))
                or ((args.final_auto_evidence_file is None)!=
                    (args.final_auto_official_archive is None))
                or (args.final_auto_budget_authorization is not None and
                    not args.allow_final_paid_ai)
                or (args.allow_final_paid_ai and
                    args.final_auto_evidence_file is None)
                or (args.final_auto_evidence_file is not None and
                    args.allow_paid_ai)):
            raise InputError("invalid final paper startup")
        if any(not b.is_dir() or b.is_symlink() for b in args.news_bundle):
            raise InputError("missing archived news")
        _initialize(args.state_root)
        if args.allow_final_paid_ai:
            for name in ("auto_ai_research","auto_budget_journal"):
                folder=args.state_root/name
                if folder.is_symlink():
                    raise InputError("unsafe final auto accounting folder")
                folder.mkdir(exist_ok=True)
        if lock.exists() or lock.is_symlink():
            raise InputError("previous paper operator lock requires audit")
        with lock.open("x",encoding="utf-8") as f:
            f.write("running; review journal on unexpected stop\n")
            f.flush()
            os.fsync(f.fileno())
        acquired=True
        while True:
            now=datetime.now(timezone.utc)
            try:
                outcome=run_one_cycle(
                    args.mt4_files,args.state_root,args.news_bundle,
                    allow_paid=args.allow_paid_ai,
                    analyst_model=args.analyst_model,
                    reviewer_model=args.reviewer_model,
                    paid_limit=args.max_paid_calls_lifetime,now=now,
                    event_blackout_file=args.event_blackout_file,
                    final_auto_evidence=args.final_auto_evidence_file,
                    final_auto_official_archive=args.final_auto_official_archive,
                    final_auto_budget_authorization=
                        args.final_auto_budget_authorization,
                    allow_final_paid=args.allow_final_paid_ai)
            except InputError:
                # Never hide a malformed ledger / potential paid request.
                # An unsafe newer CSV must be examined before resuming.
                raise
            print(json.dumps(outcome,ensure_ascii=False),flush=True)
            if not args.watch:
                break
            time.sleep(args.interval_seconds)
        lock.unlink()
        acquired=False
        return 0
    except KeyboardInterrupt:
        if acquired:
            # Deliberate operator stop, not a crash, is safe to release.
            lock.unlink()
        print(json.dumps({"status":"PAPER_OPERATOR_STOPPED_NO_BROKER_ORDERS",
                          "real_orders_permitted":False}))
        return 0
    except (InputError,OSError,ValueError,TypeError,KeyError,UnicodeError,
            OverflowError,ArithmeticError):
        # The lock remains after faults to prevent undetected replays.
        print(json.dumps({
            "status":"PAPER_RUNTIME_FAIL_CLOSED_REVIEW_LOCK_AND_LEDGER",
            "broker_orders_sent_this_run":0,
            "demo_broker_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
