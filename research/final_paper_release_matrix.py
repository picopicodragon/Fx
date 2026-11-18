"""Unified local research/paper readiness matrix. Read-only, always NO_GO.

Assesses price observation, journal integrity, intentional-stop evidence,
API billing and virtual entry blockers without performing orders, AI or
a risk latch clear. No automatic inference from user-supplied statements
to independent provider/broker certification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research import final_paper_status as status
from research import final_paper_reentry_review as reentry
from research import final_paper_budget_readiness as billing
from research import final_paper_event_coverage_audit as macro
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_release_matrix_v1"


def evaluate(root:Path, *, billing_statement:Path|None=None,
             event_calendar:Path|None=None)->dict:
    operating=status.summarize(root)
    review=reentry.review(root)
    costs=billing.review(root,billing_statement)
    calendar=macro.audit(event_calendar)
    head=operating["journal_head_sha256_local_only"]
    if (head!=review["journal_head_sha256_local_only"] or
            operating["completed_cycles"]!=review["journal_cycles"]):
        raise InputError("readiness snapshots raced")
    fresh=operating["price_stream_warning_level_pc_derived"]=="FRESH"
    reason=[]
    if not fresh:
        reason.append("LAST_QUOTE_NOT_FRESH")
    if operating["communication_latched"]:
        reason.append("COMMUNICATION_LEVEL2_LATCH_NOT_APPROVED_FOR_RELEASE")
    if (operating["dd4_latched"] or operating["dd5_latched"]
            or operating["daily_loss_latched"]):
        reason.append("OTHER_RISK_LATCH_ACTIVE")
    if not review["recent_quote_continuity_and_risk_review_ok"]:
        reason.append("CONTINUOUS_OBSERVATION_OR_REVIEW_INCOMPLETE")
    if not review["explicit_release_approval_recorded"]:
        reason.append("EXPLICIT_OPERATOR_REENTRY_APPROVAL_ABSENT")
    if costs["old_lifetime_paid_call_cap_exhausted"]:
        reason.append("PAID_AI_LIFETIME_6_CALL_LIMIT_EXHAUSTED")
    if not costs["provider_billing_independently_verified"]:
        reason.append("INDEPENDENT_API_BILLING_EVIDENCE_ABSENT")
    if not costs["operator_approved_paid_renewal"]:
        reason.append("EXPLICIT_PAID_AI_RENEWAL_APPROVAL_ABSENT")
    if not operating["independent_broker_clock_attested"]:
        reason.append("INDEPENDENT_MT4_CLOCK_ATTESTATION_ABSENT")
    if not operating["market_consensus_calendar_attested"]:
        reason.append("OFFICIAL_EVENT_COVERAGE_AND_POINT_IN_TIME_CONSENSUS_ABSENT")
    if not operating["transaction_costs_fully_verified"]:
        reason.append("TRANSACTION_COSTS_NOT_FULLY_ATTESTED")
    if operating["virtual_open_position_count"]!=0:
        reason.append("UNREVIEWED_VIRTUAL_POSITION")
    return {
        "schema":SCHEMA,
        "status":"PAPER_READINESS_MATRIX_RESEARCH_HOLD_NO_GO",
        "completed_cycles":operating["completed_cycles"],
        "journal_head_sha256_local_only":head,
        "latest_quote_age_seconds_pc_derived":
            operating["last_recorded_quote_age_seconds_pc_derived"],
        "price_feed_observation_viable_now":fresh,
        "historical_manual_stop_attested":
            review["historical_manual_stop_attested"],
        "recent_continuity_review_sufficient":
            review["recent_quote_continuity_and_risk_review_ok"],
        "communication_latched":operating["communication_latched"],
        "unpaid_quote_monitoring_can_continue":True,
        "monthly_budget_limit_jpy":costs["monthly_budget_limit_jpy"],
        "calendar_local_archive_supplied":calendar["calendar_supplied"],
        "calendar_locally_archived_events":calendar["locally_archived_event_count"],
        "calendar_currency_evidence_missing":
            calendar["currencies_without_any_event_evidence"],
        "known_important_event_blackout_active_now":
            calendar["known_blackout_active_now"],
        "calendar_completeness_independently_attested":False,
        "manual_billing_statement_supplied":
            costs["operator_billing_statement_supplied"],
        "budget_arithmetic_room_for_two_calls_only":
            costs["arithmetic_room_for_reserved_two_calls"],
        "ai_calls_cumulative":operating["paid_ai_calls_lifetime"],
        "ai_calls_remaining_under_existing_limit":
            operating["paid_ai_calls_remaining_under_current_limit"],
        "virtual_entry_blockers":reason,
        "virtual_entry_phase_approved":False,
        "independent_model_profitability_established":False,
        "new_paid_inference_permitted":False,
        "new_virtual_positions_permitted":False,
        "demo_order_execution_permitted":False,
        "real_order_execution_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Read-only complete final paper gap matrix")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--billing-statement",type=Path)
    p.add_argument("--event-calendar",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        out=evaluate(args.state_root,billing_statement=args.billing_statement,
                     event_calendar=args.event_calendar)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("unsafe new readiness report")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(out,ensure_ascii=False,allow_nan=False))
        return 0
    except (InputError,OSError,ValueError,KeyError,TypeError,
            UnicodeError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"PAPER_READINESS_MATRIX_FAIL_CLOSED_NO_GO",
            "virtual_entry_phase_approved":False,
            "new_paid_inference_permitted":False,
            "new_virtual_positions_permitted":False,
            "demo_order_execution_permitted":False,
            "real_order_execution_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
