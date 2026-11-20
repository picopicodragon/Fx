"""Read-only LIVE status of the consolidated final AI virtual trading gate.

Reuses the current original 6-source SHA archive, real source DEMO quote,
hash-chained paper journal and already paid 6/6 model ledgers.
Does NOT grant trust from unverified official content or local flags.
Never changes runtime, latch, cost ledger, orders, MT4, or API keys.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research import final_paper_ai_continuation_audit as paid
from research import final_paper_official_archive_integrity as archive
from research import final_paper_integrated_control as control
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_full_ai_virtual_go_no_go_v1"


def review(state_root:Path,mt4:Path,official_archive:Path,
           *,now:datetime|None=None)->dict:
    current=now or datetime.now(timezone.utc)
    if (current.tzinfo is None or
            not state_root.is_dir() or state_root.is_symlink()
            or any(p.is_symlink() for p in state_root.parents)
            or not mt4.is_dir() or mt4.is_symlink()
            or mt4.name.lower()!="files"
            or mt4.parent.name.lower()!="mql4"):
        raise InputError("FINAL_AI_RUNTIME_INPUT_UNSAFE")
    state,head=runtime._journal_load(state_root/"journal")
    before=paid.audit(state_root)
    if (before.get("journal_head_sha256_local_only")!=head
            or before.get("paid_calls_recorded_in_journal")!=
               state["paid_inference_calls"]):
        raise InputError("FINAL_AI_BILLING_HEAD_NOT_RECONCILED")
    originals=archive.audit(official_archive)
    if (originals.get("original_source_count")!=6
            or originals.get("all_saved_bytes_locally_consistent") is not True):
        raise InputError("FINAL_AI_SIX_ORIGINALS_NOT_VERIFIED")
    quote=runtime._latest_quote(mt4,current)
    if quote is None:
        raise InputError("FINAL_AI_RECENT_REAL_QUOTE_REQUIRED")
    # Critical: this is a snapshot of the old journal. No invented claim
    # of independent clock, full USD/EUR/JPY calendar, consensus or costs.
    known={"active_known_blackout":False}
    gate,budget=control.existing_runtime_no_go(state,quote,known)
    # Readiness is a READ-ONLY snapshot of a journal which may already have
    # ingested the latest physical quote. The strict entry gate *correctly*
    # rejects an equal epoch, but an already-ingested original is not itself
    # a reversed-price or stale-feed incident. Keep the strict entry gate
    # untouched and report the observational distinction separately.
    journal_epoch=state.get("last_quote_epoch")
    source_epoch=quote["capture_epoch"]
    if (type(journal_epoch) is not int or journal_epoch<0
            or type(source_epoch) is not int or source_epoch<=0):
        raise InputError("FINAL_AI_SOURCE_JOURNAL_TIME_INVALID")
    if source_epoch==journal_epoch:
        observation_status="LATEST_SOURCE_ALREADY_RECORDED_IN_JOURNAL"
    elif source_epoch<journal_epoch:
        observation_status="LATEST_SOURCE_BEHIND_JOURNAL_REQUIRES_REVIEW"
    else:
        observation_status="NEW_SOURCE_NOT_YET_IN_READ_ONLY_JOURNAL_SNAPSHOT"
    strict_entry_blockers=list(gate["block_reasons"])
    blockers=list(strict_entry_blockers)
    if source_epoch==journal_epoch:
        # Only the user-facing READINESS follow-up list is clarified;
        # no live signal, paid request, or virtual entry can use it.
        blockers=[x for x in blockers if x!="QUOTE_NOT_NEW_OR_REVERSED"]
    elif source_epoch<journal_epoch:
        blockers.append("SOURCE_QUOTE_EPOCH_BEHIND_LAST_JOURNAL_CYCLE")
    blockers+=budget["failure_reasons"]
    blockers+=[
        "OFFICIAL_SAVED_BYTES_ARE_NOT_EVENT_CALENDAR_SEMANTICS",
        "NO_INDEPENDENT_PROVIDER_JPY_BILLING_RECEIPT",
        "V2_METAEDITOR_COMPILATION_AND_EA_SWITCH_NOT_ATTESTED",
        "PREVIOUS_HISTORICAL_4_QUOTE_CLOCK_INVERSIONS_PRESERVED",
    ]
    return {
        "schema":SCHEMA,
        "status":"FINAL_FULL_AI_VIRTUAL_READINESS_HOLD_NO_GO",
        "date_pc_unattested":current.isoformat(),
        "pairs":list(paper.PAIRS),
        "journal_cycle_count":state["cycle_number"],
        "paper_head_sha256_local_only":head,
        "last_quote_epoch_pc_unattested":quote["capture_epoch"],
        "journal_last_quote_epoch_pc_unattested":journal_epoch,
        "source_minus_journal_epoch_seconds_pc_derived":source_epoch-journal_epoch,
        "latest_quote_observation_status":observation_status,
        "same_quote_is_normal_for_read_only_snapshot":
            source_epoch==journal_epoch,
        "strict_new_entry_gate_block_reasons":strict_entry_blockers,
        "readiness_report_never_grants_new_entry":True,
        "last_quote_sha256_local_only":quote["source_sha256"],
        "existing_paid_calls":state["paid_inference_calls"],
        "old_lifetime_ai_budget_reconciled":True,
        "saved_official_document_hash_integrity":True,
        "saved_official_archive_original_count":6,
        "integrated_evidence_gate":gate["status"],
        "integrated_budget_gate":budget["status"],
        "remaining_independent_review_requirements":sorted(set(blockers)),
        "previous_four_invalid_originals_silently_excluded":False,
        "live_runtime_restarted":False,
        "communication_latch_mutated":False,
        "live_journal_modified":False,
        "new_paid_ai_calls":0,
        "actual_virtual_positions_entered":0,
        "demo_broker_orders":0,
        "real_broker_orders":0,
        "full_ai_virtual_trading_ready":False,
        "new_virtual_entries_permitted":False,
        "new_paid_ai_inference_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Read-only consolidated AI virtual trading operational readiness")
    p.add_argument("--state-root",required=True,type=Path)
    p.add_argument("--mt4-files",required=True,type=Path)
    p.add_argument("--official-archive",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        report=review(args.state_root,args.mt4_files,args.official_archive)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("FINAL_AI_REPORT_OUTPUT_UNSAFE")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(report,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,TypeError,ValueError,KeyError,OSError,
            UnicodeError,OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"FINAL_AI_VIRTUAL_READINESS_INPUT_FAIL_CLOSED_NO_GO",
            "live_runtime_restarted":False,
            "communication_latch_mutated":False,
            "new_paid_ai_inference_permitted":False,
            "new_virtual_entries_permitted":False,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
