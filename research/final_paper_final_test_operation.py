"""One-command FINAL TEST V1: existing MT4->Python OBSERVATION operation.

This is NOT a fresh supervisor launch and NEVER a broker/virtual-entry release.
Requires two real Windows snapshots >=60s apart, a live growing hashed
journal, reconciled 6/6 AI ledger, current DEMO quote, and six archived
official originals. A separate IN-MEMORY synthetic-signal risk exercise
proves only the engine's no-order/blocking mechanics. It does not create
AI decisions, performance, virtual entries in live journal or paid calls.

Fail closed for any missing evidence; no process, lock, journal or MT4 change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as engine
from research import final_paper_resumed_continuity as continuity
from research import final_paper_official_archive_integrity as official
from research import final_paper_runtime as runtime
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_test_v1_observation_operation_v1"
STATUS="FINAL_TEST_V1_OBSERVATION_RUNNING_TRADING_HOLD_NO_GO"


def _is_real_mt4_folder(path:Path)->bool:
    return (path.is_dir() and not path.is_symlink()
            and not any(part.is_symlink() for part in path.parents)
            and path.name.lower()=="files"
            and path.parent.name.lower()=="mql4")


def _synthetic_mechanical_exercise(quote:dict)->list[dict]:
    """Use market contract data but NO actual AI recommendation or state."""
    checks=[]
    for pair in engine.PAIRS:
        sig={
            "id":hashlib.sha256(
                ("OFFLINE_ONLY_NOT_AI_DECISION:"+pair).encode("ascii")
            ).hexdigest(),
            "pair":pair,"action":"LONG","verdict":"APPROVED",
            "reviewed_epoch":quote["capture_epoch"]-1,
            "atr14":str(engine.PIP[pair]*D("10")),
            "packet_sha256":"0"*64,
        }
        # Production-like hold must block even a syntactically APPROVED
        # hypothetical signal, without touching the live journal.
        locked=engine.initial_state()
        locked["communication_latched"]=True
        blocked,blocked_result=engine.step(
            locked,quote,signals=[sig],entry_evidence_ready=False)
        if (blocked["positions"] or blocked["trade_log"]
                or blocked_result["broker_orders_sent_this_run"]!=0
                or "VIRTUAL_ENTRY_BLOCKED_UNATTESTED_SAFETY_EVIDENCE"
                   not in blocked_result["events"]):
            raise InputError("FINAL_TEST_SYNTHETIC_HOLD_NOT_ENFORCED")
        # In a *different* completely isolated, freshly initialized
        # in-memory scenario, exercise risk sizing or a min-lot reject.
        model=engine.initial_state()
        hypothetical,outcome=engine.step(
            model,quote,signals=[sig],entry_evidence_ready=True)
        opened="VIRTUAL_POSITION_OPENED" in outcome["events"]
        minlot="VIRTUAL_LOT_BELOW_MINIMUM" in outcome["events"]
        if not (opened or minlot) or outcome["broker_orders_sent_this_run"]!=0:
            raise InputError("FINAL_TEST_SYNTHETIC_RISK_ENGINE_INVALID")
        if opened:
            if (len(hypothetical["positions"])!=1
                    or D(hypothetical["positions"][0]["risk_jpy"])
                    >D("500.00")):
                raise InputError("FINAL_TEST_SYNTHETIC_RISK_LIMIT_EXCEEDED")
        else:
            if hypothetical["positions"]:
                raise InputError("FINAL_TEST_SYNTHETIC_REJECT_OPENED_POSITION")
        checks.append({
            "pair":pair,
            "hypothetical_synthetic_approved_signal_only":True,
            "live_communications_hold_blocked_entry":True,
            "separate_risk_sizing_result":
                "ISOLATED_HYPOTHETICAL_POSITION"
                if opened else "ISOLATED_MIN_LOT_REJECTION",
            "test_scenario_position_not_persisted":True,
            "not_an_actual_ai_decision":True,
            "performance_or_profitability_proven":False,
        })
    return checks


def assess(state_root:Path, mt4:Path, first:Path, second:Path,
           official_archive:Path)->dict:
    if (not state_root.is_dir() or state_root.is_symlink()
            or any(p.is_symlink() for p in state_root.parents)
            or not _is_real_mt4_folder(mt4)):
        raise InputError("FINAL_TEST_EXISTING_EVIDENCE_FOLDERS_REQUIRED")
    proof=continuity.verify(state_root,first,second)
    archive=official.audit(official_archive)
    if (proof.get("status")!=
            "PAPER_RESUMED_OBSERVATION_TWO_POINT_CONSISTENT_NO_GO"
            or proof.get("same_python_pid_and_start_time") is not True
            or proof.get("same_session_journal_advanced_cycles",0)<1
            or proof.get("paid_calls_reconciled_and_unchanged") is not True
            or proof.get("communication_latched") is not True
            or proof.get("other_risk_latches_absent") is not True
            or proof.get("new_paid_ai_calls_permitted") is not False
            or proof.get("new_virtual_positions_permitted") is not False
            or archive.get("status")!=
            "SIX_LOCAL_OFFICIAL_ORIGINALS_HASH_MATCH_RESEARCH_NO_GO"
            or archive.get("original_source_count")!=6):
        raise InputError("FINAL_TEST_UNVERIFIED_PROCESS_OR_ORIGINALS")
    snap=continuity._read(second)
    latest=snap.get("mt4_quote_source_files")
    if (type(latest) is not list or not latest
            or type(latest[0]) is not dict):
        raise InputError("FINAL_TEST_MISSING_LAST_SNAPSHOT")
    name=latest[0].get("name")
    sha=latest[0].get("sha256")
    if (type(name) is not str
            or continuity.QUOTE.fullmatch(name) is None
            or type(sha) is not str or
            runtime.SHA.fullmatch(sha) is None):
        raise InputError("FINAL_TEST_LAST_SOURCE_UNSAFE")
    file=mt4/name
    if not file.is_file() or file.is_symlink():
        raise InputError("FINAL_TEST_ORIGINAL_MISSING")
    if hashlib.sha256(file.read_bytes()).hexdigest()!=sha:
        raise InputError("FINAL_TEST_ORIGINAL_CHANGED_SINCE_SNAPSHOT")
    now=continuity._time(snap["captured_utc_pc_unattested"])
    observation=engine.validate_quotes(file,now=now)
    if observation["source_sha256"]!=sha:
        raise InputError("FINAL_TEST_QUOTE_SHA_MISMATCH")
    # The Python supervisor can append a fresh cycle at any time.
    # Accept a monotonic advance, but never an older/replayed snapshot.
    journal,head=runtime._journal_load(state_root/"journal")
    if (journal.get("cycle_number",0)<proof["latest_journal_cycles"]
            or journal.get("last_quote_epoch",0)<
               proof["first_snapshot_epoch_pc_unattested"]-120
            or journal.get("communication_latched") is not True
            or any(journal.get(k) is not False for k in (
                "dd4_latched","dd5_latched","daily_loss_latched"))
            or journal.get("positions")!=[]
            or journal.get("pending_signals")!=[]
            or journal.get("paid_inference_calls")!=6):
        raise InputError("FINAL_TEST_LIVE_RISK_GATE_INVALID")
    # The in-memory exercise never asks the live supervisor to authorize
    # or act on these synthetic scenario signals.
    mechanics=_synthetic_mechanical_exercise(observation)
    return {
        "schema":SCHEMA,
        "status":STATUS,
        "phase":"FINAL_TEST_V1_REAL_DEMO_OBSERVATION_AND_OFFLINE_MECHANICS",
        "current_supervisor_running_evidenced_by_two_snapshots":True,
        "mt4_quote_capture_and_paper_journal_advancing":True,
        "current_process_started_or_restarted_by_this_run":False,
        "supervisor_snapshot_interval_seconds_pc_derived":
            proof["interval_seconds_pc_derived"],
        "same_python_supervisor_pid_and_start_time":True,
        "journal_cycles_at_report":journal["cycle_number"],
        "journal_head_sha256_local_only":head,
        "latest_verified_original_quote_name":name,
        "latest_verified_original_quote_sha256_local_only":sha,
        "six_saved_official_sources_byte_hash_consistent":True,
        "official_public_archive_manifest_sha256_local_only":
            archive["local_manifest_sha256"],
        "historical_four_clock_inversions_remain_unrepaired":True,
        "running_mt4_ea_v2_build_independently_attested":False,
        "isolated_synthetic_risk_and_block_tests":mechanics,
        "real_ai_macro_decision_replayed_or_incurred":False,
        "actual_live_virtual_position_opened":False,
        "saved_communication_latch_remains_active":True,
        "existing_paid_ai_calls_used":6,
        "unpaid_quotes_only":True,
        "independent_macro_calendar_consensus_clock_and_cost_verified":False,
        "independent_metaeditor_compile_and_ea_deployment_verified":False,
        "final_full_virtual_trading_go":False,
        "new_virtual_entries_permitted":False,
        "new_paid_ai_inference_permitted":False,
        "demo_broker_orders_permitted":False,
        "real_broker_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
        "PC_clock_or_process_identity_independently_attested":False,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Existing DEMO observer -> final no-order test V1")
    p.add_argument("--state-root",required=True,type=Path)
    p.add_argument("--mt4-files",required=True,type=Path)
    p.add_argument("--first",required=True,type=Path)
    p.add_argument("--second",required=True,type=Path)
    p.add_argument("--official-archive",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        report=assess(args.state_root,args.mt4_files,args.first,args.second,
                      args.official_archive)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("FINAL_TEST_OUTPUT_MUST_BE_NEW")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,ValueError,TypeError,KeyError,
            UnicodeError,OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"FINAL_TEST_V1_EVIDENCE_INCOMPLETE_FAIL_CLOSED_NO_GO",
            "current_process_started_or_restarted_by_this_run":False,
            "actual_live_virtual_position_opened":False,
            "new_virtual_entries_permitted":False,
            "new_paid_ai_inference_permitted":False,
            "demo_broker_orders_permitted":False,
            "real_broker_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
