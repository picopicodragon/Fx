"""Read-only preflight BEFORE a human starts final automatic virtual mode.

Requires: original 6/6 reconciled, exact current journal, newly approved
official/clock/consensus/cost evidence, human-approved new JPY budget and
an explicit one-shot approval for the CURRENT communication incident.
This cannot clear any risk latch, launch a process or charge an API.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_auto_entry_gate as gate
from research import final_paper_auto_budget as budget
from research import final_paper_runtime as runtime
from research import final_paper_ai_continuation_audit as legacy
from research import final_paper_current_comm_release as comm
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_final_auto_preflight_v1"


def review(root:Path,mt4:Path,evidence:Path,official:Path,
           budget_policy:Path,analyst_model:str,reviewer_model:str,
           *,now:datetime|None=None)->dict:
    now=now or datetime.now(timezone.utc)
    if (now.tzinfo is None or now.utcoffset().total_seconds()!=0
            or (root/".single_operator.lock").exists()
            or (root/".single_operator.lock").is_symlink()
            or not mt4.is_dir() or mt4.is_symlink()
            or not str(mt4.resolve()).lower().endswith(
                str(Path("MQL4")/"Files").lower())):
        raise InputError("FINAL_AUTO_RUNNING_MONITOR_OR_PATH_UNSAFE")
    state,head=runtime._journal_load(root/"journal")
    if (state.get("virtual_only") is not True
            or state.get("broker_orders_permitted") is not False
            or state.get("paid_inference_calls")!=6
            or state.get("positions")!=[]
            or state.get("pending_signals")!=[]
            or any(state.get(v) is not False for v in (
                "dd4_latched","dd5_latched","daily_loss_latched"))):
        raise InputError("FINAL_AUTO_LEGACY_RISK_UNSAFE")
    recon=legacy.audit(root)
    if (recon["paid_calls_in_completed_ledgers"]!=6
            or recon["paid_calls_recorded_in_journal"]!=6
            or recon["journal_head_sha256_local_only"]!=head):
        raise InputError("FINAL_AUTO_LEGACY_6_OF_6_UNRECONCILED")
    quote=runtime._latest_quote(mt4,now)
    if quote is None:
        raise InputError("FINAL_AUTO_FRESH_MT4_QUOTE_REQUIRED")
    binding=state.get("auto_entry_session_binding_sha256",head)
    checked=gate.evaluate(evidence,official,quote,now=now,
                          entry_binding_sha=binding)
    policy=budget.policy(budget_policy,now=now,
                         session_binding_sha=binding,
                         analyst_model=analyst_model,
                         reviewer_model=reviewer_model)
    account=budget.check(policy,root/"auto_budget_journal",
                         journal_reserve_shas=state.get(
                             "auto_budget_reservation_receipts",[]))
    # Even a successful new AI cap and official evidence bundle CANNOT
    # release communication stop by implicit inference or API call.
    comm_release_expected=state.get("communication_latched") is True
    incident=comm.gaps(root) if comm_release_expected else None
    permit=root/comm.FILE_NAME
    if comm_release_expected and (
            not permit.is_file() or permit.is_symlink()):
        raise InputError("FINAL_AUTO_CURRENT_GAP_APPROVAL_ABSENT")
    return {
        "schema":SCHEMA,
        "status":"FINAL_AUTO_OPERATOR_PREREQUISITES_CHECKED_NO_GO",
        "observed_journal_cycles":state["cycle_number"],
        "original_journal_head_sha256":head,
        "old_paid_calls_and_reconciled_ledger":6,
        "original_communication_latched":state["communication_latched"],
        "one_shot_communication_release_file_staged":
            comm_release_expected,
        "all_historical_interruption_fingerprint":
            incident["all_historical_gaps_fingerprint_sha256"]
            if incident else None,
        "operator_attested_entry_evidence_hash":
            checked["permit_sha256_local_only"],
        "known_macro_blackout_active":
            checked["known_event_blackout_active"],
        "new_budget_policy_sha256":policy["policy_sha256_local_only"],
        "new_paid_requests_already_reserved":account[
            "spent_or_reserved_calls"],
        "new_jpy_conservative_reserves":account["spent_or_reserved_jpy"],
        "new_paid_monthly_jpy_ceiling":policy["max_jpy"],
        "independent_provider_billing_total_proven_by_code":False,
        "independent_clock_and_calendar_claims_proven_by_code":False,
        "operator_must_confirm_no_python_process_outside_preflight":True,
        "existing_supervisor_stopped_by_this_run":False,
        "virtual_entries_started_by_this_run":False,
        "paid_model_called_by_this_run":False,
        "broker_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Read-only full automatic virtual paper preflight")
    p.add_argument("--state-root",required=True,type=Path)
    p.add_argument("--mt4-files",required=True,type=Path)
    p.add_argument("--evidence",required=True,type=Path)
    p.add_argument("--official-archive",required=True,type=Path)
    p.add_argument("--budget-authorization",required=True,type=Path)
    p.add_argument("--analyst-model",required=True)
    p.add_argument("--reviewer-model",required=True)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        result=review(args.state_root,args.mt4_files,args.evidence,
                      args.official_archive,args.budget_authorization,
                      args.analyst_model,args.reviewer_model)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("FINAL_AUTO_PREFLIGHT_OUTPUT_UNSAFE")
        with args.out.open("x",encoding="utf-8") as out:
            json.dump(result,out,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,OSError,KeyError,ValueError,TypeError,
            UnicodeError,OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"FINAL_AUTO_PREFLIGHT_FAIL_CLOSED_NO_GO",
            "virtual_entries_started_by_this_run":False,
            "paid_model_called_by_this_run":False,
            "broker_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
