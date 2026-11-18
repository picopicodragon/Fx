"""FINAL-PAPER-104: five-gate offline release assessment.

Operator-supplied or PC-derived observations are not independent proof.
This module performs no broker actions, networking, inference or state repair.
It distinguishes proven quote observation from authorization for a NEW trade.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research import final_paper_runtime as runtime
from research import final_paper_status as status
from research import final_paper_ai_continuation_audit as paid
from research import final_paper_budget_readiness as budget
from research import final_paper_event_coverage_audit as events
from research import final_paper_quote_contract_evidence as contracts
from research import final_paper_stream_diagnostic as stream
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_five_gate_readiness_v1"
RELEASE_SHA = "manual_comm_release_sha256"
GATE_NAMES = (
    "PAPER_CONSUMER_HEALTH",
    "APPROVED_COMMUNICATION_RECOVERY",
    "MACRO_CLOCK_AND_COST_EVIDENCE",
    "PAID_AI_BUDGET_AND_AUTHORIZATION",
    "NEW_VIRTUAL_ENTRY_E2E",
)


def assess(root: Path, mt4: Path, *, billing_statement: Path | None = None,
           event_calendar: Path | None = None) -> dict:
    # All auditors are offline/read-only and validate their own inputs.
    state, head = runtime._journal_load(root / "journal")
    operating = status.summarize(root)
    reconciled = paid.audit(root)
    cost = budget.review(root, billing_statement)
    calendar = events.audit(event_calendar)
    contract = contracts.audit(mt4)
    gap = stream.diagnose(root, mt4)
    if (head != operating["journal_head_sha256_local_only"]
            or head != reconciled["journal_head_sha256_local_only"]
            or state["cycle_number"] != operating["completed_cycles"]
            or state["cycle_number"] != reconciled["journal_cycles"]):
        raise InputError("NON_ATOMIC_OR_MODIFIED_PAPER_JOURNAL")
    # Read-only source files don't attest MT4 Expert or Python PID.
    stream_current = (
        gap["diagnosis"] == "LATEST_MT4_QUOTE_ALREADY_PROCESSED"
        and operating["price_stream_warning_level_pc_derived"] == "FRESH"
        and contract["latest_quote_fresh_pc_derived"] is True
    )
    marker = state.get(RELEASE_SHA)
    release_marker_valid = (
        type(marker) is str
        and runtime.SHA.fullmatch(marker) is not None
    )
    release_applied = (
        release_marker_valid
        and state.get("communication_latched") is False
    )
    no_other_risk = all(
        state.get(key) is False for key in (
            "dd4_latched", "dd5_latched", "daily_loss_latched")
    )
    calendar_proven = (
        calendar["calendar_source_independently_attested"] is True
        and calendar["all_important_events_covered"] is True
        and calendar["consensus_captured_before_release"] is True
    )
    clock_proven = (
        operating["independent_broker_clock_attested"] is True
        and contract["broker_clock_independently_attested"] is True
    )
    all_costs_proven = (
        contract["full_transaction_costs_verified"] is True
        and operating["transaction_costs_fully_verified"] is True
    )
    paid_reconciled = (
        reconciled["paid_calls_recorded_in_journal"]
        == reconciled["paid_calls_in_completed_ledgers"]
    )
    renewal_authorized = (
        cost["operator_approved_paid_renewal"] is True
        and cost["provider_billing_independently_verified"] is True
        and cost["arithmetic_room_for_reserved_two_calls"] is True
        and cost["future_paid_inference_authorized"] is True
    ) if "future_paid_inference_authorized" in cost else False
    paid_headroom = (
        operating["paid_ai_calls_remaining_under_current_limit"] >= 2
    )
    live_entry_authorized = (
        stream_current and release_applied and no_other_risk
        and calendar_proven and clock_proven and all_costs_proven
        and paid_reconciled and renewal_authorized and paid_headroom
        and state.get("broker_orders_permitted") is False
        and state.get("virtual_only") is True
    )
    gates = {
        GATE_NAMES[0]: {
            "price_capture_and_journal_fresh": stream_current,
            "python_process_independently_attested": False,
            "mt4_expert_independently_attested": False,
            "passed": False,
        },
        GATE_NAMES[1]: {
            "one_use_approval_marker_in_journal": release_marker_valid,
            "communication_latch_cleared": release_applied,
            "other_risk_latches_absent": no_other_risk,
            "passed": release_applied and no_other_risk,
        },
        GATE_NAMES[2]: {
            "usd_eur_jpy_calendar_and_consensus_attested": calendar_proven,
            "independent_clock_attested": clock_proven,
            "full_costs_attested": all_costs_proven,
            "passed": calendar_proven and clock_proven and all_costs_proven,
        },
        GATE_NAMES[3]: {
            "completed_model_ledgers_reconciled": paid_reconciled,
            "existing_paid_two_call_headroom": paid_headroom,
            "provider_billing_and_renewal_approved": renewal_authorized,
            "passed": paid_reconciled and paid_headroom and renewal_authorized,
        },
        GATE_NAMES[4]: {
            "technical_virtual_engine_present": True,
            "live_approved_new_signal_present": False,
            "live_virtual_entry_and_exit_proven": False,
            "passed": False,
        },
    }
    # Re-validate snapshot integrity against concurrent writer before report.
    _, again = runtime._journal_load(root / "journal")
    if again != head:
        raise InputError("NON_ATOMIC_OR_MODIFIED_PAPER_JOURNAL")
    return {
        "schema": SCHEMA,
        "status": "PAPER_FIVE_GATE_INTEGRATED_RESEARCH_HOLD_NO_GO",
        "completed_cycles": state["cycle_number"],
        "journal_head_sha256_local_only": head,
        "gates": gates,
        "passed_gate_count": sum(1 for gate in gates.values()
                                 if gate["passed"]),
        "gate_count": len(gates),
        "current_virtual_positions": len(state.get("positions", [])),
        "existing_paid_calls_used": operating["paid_ai_calls_lifetime"],
        "legacy_paid_limit_reset": False,
        "independent_clock_or_event_proven_by_pc_metadata": False,
        "virtual_entry_preconditions_structurally_met": live_entry_authorized,
        "live_new_virtual_entry_proven": False,
        "new_paid_inference_permitted": False,
        "new_virtual_positions_permitted": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="All five paper gates, offline and no orders")
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--mt4-files", required=True, type=Path)
    parser.add_argument("--billing-statement", type=Path)
    parser.add_argument("--event-calendar", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = assess(args.state_root, args.mt4_files,
                        billing_statement=args.billing_statement,
                        event_calendar=args.event_calendar)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("UNSAFE_READINESS_OUTPUT_PATH")
        with args.out.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2,
                      allow_nan=False)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (InputError, ValueError, TypeError, OSError, UnicodeError,
            KeyError, OverflowError):
        print(json.dumps({
            "schema": SCHEMA,
            "status": "PAPER_FIVE_GATE_FAIL_CLOSED_NO_GO",
            "new_paid_inference_permitted": False,
            "new_virtual_positions_permitted": False,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
