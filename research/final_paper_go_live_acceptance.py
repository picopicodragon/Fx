"""Final human-gated FX PAPER launch acceptance, no live actions.

Combines historical 3020 original quote byte provenance, two current
Windows supervisor snapshots, official 6 originals, paid 6/6 ledgers,
current quote, candidate V2 MetaEditor source, and all outstanding gates.

Not a deployment tool: it never stops/starts the supervisor, changes risk
state, touches archived source bytes, sends AI requests or broker orders.
No local Boolean permit can prove independent source authenticity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research import final_paper_resumed_continuity as continuity
from research import final_paper_ai_continuation_audit as paid
from research import final_paper_official_archive_integrity as official
from research import final_paper_clockfix_prospective as clockfix
from research import final_paper_quote_contract_forensics as forensic
from research import final_paper_integrated_control as control
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_go_live_acceptance_v1"

APPROVAL_ACTIONS=(
    "AUTHORIZE_MANUAL_V2_METAEDITOR_COMPILE_OLD_EA_STOP_AND_SINGLE_DEMO_EA_START",
    "AUTHORIZE_CURRENT_INCIDENT_COMMUNICATION_LATCH_RELEASE_ONLY_AFTER_REVIEW",
    "AUTHORIZE_NEW_PAID_AI_BUDGET_MONTHLY_JPY_AND_API_CALL_CAP",
)
INDEPENDENT_REQUIRED=(
    "PROVE_COMPILED_V2_EXPERTS_START_AND_OLD_EA_STOP_FROM_REAL_TERMINAL",
    "VERIFY_OFFICIAL_USD_EUR_JPY_HIGH_IMPACT_EVENT_COMPLETENESS_AND_BLACKOUT",
    "ARCHIVE_PRE_RELEASE_CONSENSUS_WITH_INDEPENDENT_CAPTURE_TIMES",
    "VERIFY_PC_AND_BROKER_CLOCKS_AGAINST_INDEPENDENT_REFERENCE",
    "VALIDATE_SPREAD_SLIPPAGE_SWAP_AND_CONTRACT_COSTS",
    "VERIFY_PROVIDER_HARD_SPEND_LIMIT_AND_INDEPENDENT_JPY_USAGE_RECEIPTS",
)


def _existing_root(folder:Path)->bool:
    return (folder.is_dir() and not folder.is_symlink()
            and not any(p.is_symlink() for p in folder.parents))


def _historical_chain(
        mt4:Path, baseline_report:Path,
        candidate_mq4:Path)->tuple[dict,str,int]:
    """Recheck every original byte, including previously invalid 4 quotes."""
    clockfix._read_baseline(baseline_report)
    originals=forensic._inventory(mt4)
    historical=[f for f in originals if
                f.name<=clockfix.BASELINE["last_source_basename"]]
    baseline=clockfix.BASELINE
    if (len(historical)!=3020 or
            historical[0].name!=baseline["first_source_basename"] or
            historical[-1].name!=baseline["last_source_basename"]):
        raise InputError("GO_LIVE_HISTORICAL_QUOTE_INVENTORY_CHANGED")
    sha=b"\x00"*32
    for file in historical:
        sha=hashlib.sha256(
            sha+file.name.encode("ascii")+
            bytes.fromhex(clockfix._source_sha(file))).digest()
    if sha.hex()!=baseline["original_sequence_sha256_local_only"]:
        raise InputError("GO_LIVE_HISTORICAL_ORIGINALS_CHANGED")
    if (not candidate_mq4.is_file() or candidate_mq4.is_symlink()
            or any(x.is_symlink() for x in candidate_mq4.parents)
            or not 0<candidate_mq4.stat().st_size<25000):
        raise InputError("GO_LIVE_CANDIDATE_EA_SOURCE_UNSAFE")
    raw=candidate_mq4.read_bytes()
    if (b'PAPER_BUILD_TAG "FXPAPER-CLOCKFREEZE-20261120-V2"' not in raw
            or b"OrderSend(" in raw or b"OrderClose(" in raw
            or b"OrderModify(" in raw or b"WebRequest(" in raw
            or b"#import" in raw):
        raise InputError("GO_LIVE_CANDIDATE_EA_MUST_BE_READONLY_V2")
    return baseline,hashlib.sha256(raw).hexdigest(),len(originals)


def review(
    root:Path,mt4:Path,archive:Path,baseline_report:Path,
    candidate_mq4:Path, first_snapshot:Path,second_snapshot:Path,
)->dict:
    if (not _existing_root(root) or not _existing_root(mt4)
            or mt4.name.lower()!="files"
            or mt4.parent.name.lower()!="mql4"):
        raise InputError("GO_LIVE_EXISTING_REAL_DEMO_ROOTS_REQUIRED")
    proof=continuity.verify(root,first_snapshot,second_snapshot)
    if (proof["status"]!=
            "PAPER_RESUMED_OBSERVATION_TWO_POINT_CONSISTENT_NO_GO"
            or proof["communication_latched"] is not True
            or proof["paid_calls_reconciled_and_unchanged"] is not True
            or proof["journal_hash_chain_valid"] is not True):
        raise InputError("GO_LIVE_SUPERVISOR_EVIDENCE_UNVERIFIED")
    state,head=runtime._journal_load(root/"journal")
    if (state["cycle_number"]!=proof["latest_journal_cycles"]
            or head!=proof["latest_journal_head_sha256_local_only"]
            or state["communication_latched"] is not True
            or state["positions"]!=[] or state["pending_signals"]!=[]
            or state["paid_inference_calls"]!=6):
        raise InputError("GO_LIVE_HEAD_OR_RISK_CHANGED_DURING_REVIEW")
    billed=paid.audit(root)
    if (billed["paid_calls_recorded_in_journal"]!=6
            or billed["paid_calls_in_completed_ledgers"]!=6
            or billed["journal_head_sha256_local_only"]!=head):
        raise InputError("GO_LIVE_PAID_LEDGER_UNRECONCILED")
    originals=official.audit(archive)
    if (originals["original_source_count"]!=6
            or originals["all_saved_bytes_locally_consistent"] is not True):
        raise InputError("GO_LIVE_OFFICIAL_BYTES_NOT_MATCHED")
    baseline,candidate_sha,inventory=_historical_chain(
        mt4,baseline_report,candidate_mq4)
    second=continuity._snap(continuity._read(second_snapshot))
    quote_path=mt4/second["quote_name"]
    if not quote_path.is_file() or quote_path.is_symlink():
        raise InputError("GO_LIVE_LAST_QUOTE_SOURCE_MISSING")
    if hashlib.sha256(quote_path.read_bytes()).hexdigest()!=second["quote_sha256"]:
        raise InputError("GO_LIVE_LAST_QUOTE_CHANGED_SINCE_SNAPSHOT")
    quote=paper.validate_quotes(
        quote_path,now=datetime.fromtimestamp(
            second["captured_epoch"],tz=timezone.utc))
    if (quote["source_sha256"]!=second["quote_sha256"]
            or quote["capture_epoch"]!=second["quote_epoch"]):
        raise InputError("GO_LIVE_LAST_QUOTE_INVALID")
    gate,budget=control.existing_runtime_no_go(
        state,quote,{"active_known_blackout":False})
    all_blocked=sorted(set(gate["block_reasons"]+budget["failure_reasons"]))
    return {
        "schema":SCHEMA,
        "status":"GO_LIVE_EVIDENCE_VERIFIED_OPERATOR_GATES_REMAIN_NO_GO",
        "existing_readonly_observation_continuity_confirmed":True,
        "same_python_supervisor_at_two_samples":True,
        "journal_cycles":state["cycle_number"],
        "journal_head_sha256_local_only":head,
        "observed_paid_ai_calls_not_reset":6,
        "official_original_local_bytes_verified":6,
        "official_publisher_and_time_independently_verified":False,
        "historical_quote_count_verified":3020,
        "historical_original_sequence_sha256":
            baseline["original_sequence_sha256_local_only"],
        "historical_four_invalid_quotes_retained":True,
        "all_original_quote_inventory_count":inventory,
        "candidate_mq4_v2_source_sha256_local_only":candidate_sha,
        "candidate_v2_source_no_broker_order_calls":True,
        "candidate_v2_compiled_and_installed_on_mt4":False,
        "paid_api_dispatch_eligible":False,
        "new_live_virtual_entry_eligible":False,
        "remaining_runtime_block_reasons":all_blocked,
        "operator_approvals_not_yet_given":list(APPROVAL_ACTIONS),
        "independent_evidence_not_yet_attested":list(INDEPENDENT_REQUIRED),
        "current_communication_latch_cleared":False,
        "windows_mt4_or_python_process_restarted_by_audit":False,
        "historical_original_files_modified":False,
        "new_paid_ai_api_calls":0,
        "new_actual_virtual_positions":0,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Fail-closed human-gated full AI PAPER startup review")
    for flag in ("state-root","mt4-files","official-archive",
                 "baseline-report","candidate-mq4",
                 "first-snapshot","second-snapshot","out"):
        p.add_argument("--"+flag,type=Path,required=True)
    args=p.parse_args(argv)
    try:
        report=review(args.state_root,args.mt4_files,args.official_archive,
            args.baseline_report,args.candidate_mq4,
            args.first_snapshot,args.second_snapshot)
        out=args.out
        if (out.exists() or out.is_symlink()
                or not _existing_root(out.parent)
                or out.parent.resolve()==args.mt4_files.resolve()):
            raise InputError("GO_LIVE_REPORT_OUTPUT_NOT_NEW_OR_UNSAFE")
        with out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,ValueError,TypeError,KeyError,
            UnicodeError,OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"GO_LIVE_EVIDENCE_FAIL_CLOSED_NO_GO",
            "current_communication_latch_cleared":False,
            "new_paid_ai_api_calls":0,
            "new_actual_virtual_positions":0,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
