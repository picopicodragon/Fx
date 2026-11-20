"""Final paper single fail-closed safety and budget control plane.

This is PURE evaluation: no broker/provider calls or filesystem writes.
Runtime adapter uses currently UNATTESTED values and remains NO_GO.
Hypothetical true attestations used in unit tests are NOT live permissions.
"""
from __future__ import annotations

from decimal import Decimal as D, InvalidOperation

from research import final_paper_engine as paper
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_integrated_safety_gate_v1"
MAX_OLD_PAID_CALLS=6
MONTHLY_PLANNED_CAP_JPY=D("3000")
RISK=("communication_latched","dd4_latched","dd5_latched","daily_loss_latched")


def _amount(value:object)->D:
    if isinstance(value,bool) or type(value) not in (str,int,D):
        raise InputError("INTEGRATED_BUDGET_CURRENCY_VALUE_UNTRUSTED")
    try:
        n=D(str(value))
    except (InvalidOperation,ArithmeticError,ValueError) as exc:
        raise InputError("INTEGRATED_BUDGET_AMOUNT_INVALID") from exc
    if not n.is_finite() or n<0 or n.as_tuple().exponent < -2:
        raise InputError("INTEGRATED_BUDGET_PRECISION_OR_AMOUNT_INVALID")
    return n


def budget_check(state:dict, *,
                 new_budget_operator_approved:bool=False,
                 provider_jpy_invoice_independently_reconciled:bool=False,
                 provider_spending_hard_limit_verified:bool=False,
                 approved_month_cap_jpy:object="0",
                 provider_month_spend_jpy:object="0",
                 worst_case_next_two_calls_jpy:object="0",
                 month_api_calls:int=0, month_call_cap:int=0)->dict:
    """Reserve the upper cost of BOTH analyst/reviewer requests in advance.

    No approval is persisted or granted here. Live runtime never derives
    the evidence booleans from arbitrary local JSON. Previous 6/6 API
    ledgers must stay intact; a new monthly budget is separate.
    """
    if (type(state) is not dict
            or type(state.get("paid_inference_calls")) is not int
            or not 0<=state["paid_inference_calls"]<=MAX_OLD_PAID_CALLS
            or type(month_api_calls) is not int or month_api_calls<0
            or type(month_call_cap) is not int or month_call_cap<0
            or any(type(v) is not bool for v in (
                new_budget_operator_approved,
                provider_jpy_invoice_independently_reconciled,
                provider_spending_hard_limit_verified))):
        raise InputError("INTEGRATED_BUDGET_STATE_INVALID")
    cap=_amount(approved_month_cap_jpy)
    spend=_amount(provider_month_spend_jpy)
    next_pair=_amount(worst_case_next_two_calls_jpy)
    if cap>MONTHLY_PLANNED_CAP_JPY:
        raise InputError("INTEGRATED_BUDGET_EXCEEDS_3000JPY_PROPOSAL")
    reasons=[]
    if state["paid_inference_calls"]!=MAX_OLD_PAID_CALLS:
        reasons.append("PREVIOUS_6_CALL_BILLING_LEDGER_NOT_FINAL")
    if not new_budget_operator_approved:
        reasons.append("NEW_AI_BUDGET_OPERATOR_APPROVAL_MISSING")
    if not provider_jpy_invoice_independently_reconciled:
        reasons.append("PROVIDER_COST_JPY_INVOICE_UNVERIFIED")
    if not provider_spending_hard_limit_verified:
        reasons.append("PROVIDER_BILLING_HARD_LIMIT_UNVERIFIED")
    if cap==0 or next_pair==0:
        reasons.append("MONTH_CAP_OR_NEXT_TWO_CALL_UPPER_BOUND_MISSING")
    if spend+next_pair>cap:
        reasons.append("UPPER_BOUND_NEXT_PAIR_EXCEEDS_REMAINING_JPY")
    if month_api_calls+2>month_call_cap:
        reasons.append("ANALYST_REVIEWER_TWO_CALL_CAP_EXHAUSTED")
    return {
        "schema":"fx_final_paper_budget_reservation_v1",
        "status":("HYPOTHETICAL_BUDGET_EVIDENCE_COMPLETE_NOT_AUTHORIZED"
                  if not reasons else "AI_BUDGET_HOLD_NO_GO"),
        "historic_api_calls_preserved":state["paid_inference_calls"],
        "planned_maximum_jpy":str(MONTHLY_PLANNED_CAP_JPY),
        "approved_cap_jpy":str(cap),
        "observed_month_spend_jpy":str(spend),
        "next_analyst_reviewer_max_jpy":str(next_pair),
        "remaining_after_possible_reservation_jpy":
            str(max(D("0"),cap-spend-next_pair)),
        "conditions_satisfied_hypothetically":not reasons,
        "failure_reasons":reasons,
        "new_billable_dispatch_authorized_by_this_review":False,
        "actual_paid_api_calls":0,
        "broker_orders_permitted":False,
    }


def assess(state:dict, *,
           quote_epoch:int,
           known_important_event_blackout:bool,
           verified_complete_usd_eur_jpy_events:bool,
           verified_independent_broker_pc_clock:bool,
           verified_pre_release_consensus_time:bool,
           verified_spread_slippage_swap_costs:bool,
           verified_single_readonly_mt4_ea:bool,
           budget_conditions_satisfied:bool=False)->dict:
    """Three-pair strategy + risk gate, with *externally validated* inputs.

    This function is not a standalone attestor. Its return cannot override
    the communication latch or grant live entry without runner checks.
    """
    if (type(state) is not dict or state.get("schema")!=paper.SCHEMA
            or state.get("virtual_only") is not True
            or state.get("broker_orders_permitted") is not False
            or type(state.get("last_quote_epoch")) is not int
            or type(state.get("paid_inference_calls")) is not int
            or not 0<=state["paid_inference_calls"]<=MAX_OLD_PAID_CALLS
            or type(quote_epoch) is not int or quote_epoch<=0
            or any(type(state.get(k)) is not bool for k in RISK)
            or any(type(v) is not bool for v in (
                known_important_event_blackout,
                verified_complete_usd_eur_jpy_events,
                verified_independent_broker_pc_clock,
                verified_pre_release_consensus_time,
                verified_spread_slippage_swap_costs,
                verified_single_readonly_mt4_ea,
                budget_conditions_satisfied))):
        raise InputError("INTEGRATED_GATE_STATE_INVALID")
    reason=[]
    previous=state["last_quote_epoch"]
    if quote_epoch<=previous:
        reason.append("QUOTE_NOT_NEW_OR_REVERSED")
    if previous>0 and quote_epoch-previous>600:
        reason.append("QUOTE_GAP_EXCEEDS_600S")
    if known_important_event_blackout:
        reason.append("HIGH_IMPACT_EVENT_15M_BLACKOUT")
    for value,code in (
        (verified_complete_usd_eur_jpy_events,
         "COMPLETE_USD_EUR_JPY_CALENDAR_UNATTESTED"),
        (verified_independent_broker_pc_clock,
         "BROKER_AND_PC_CLOCK_NOT_INDEPENDENTLY_ATTESTED"),
        (verified_pre_release_consensus_time,
         "PRE_RELEASE_CONSENSUS_NOT_TIME_ATTESTED"),
        (verified_spread_slippage_swap_costs,
         "SPREAD_SLIPPAGE_SWAP_COSTS_UNVERIFIED"),
        (verified_single_readonly_mt4_ea,
         "EXCLUSIVE_READONLY_DEMO_EA_NOT_ATTESTED"),
    ):
        if not value:
            reason.append(code)
    for key in RISK:
        if state[key]:
            reason.append("RISK_STOP_"+key.upper())
    ready=not reason
    return {
        "schema":SCHEMA,
        "status":("HYPOTHETICAL_EVIDENCE_GATE_PASSED_NOT_LIVE_AUTHORITY"
                  if ready else "AI_VIRTUAL_EXECUTION_HOLD_NO_GO"),
        "pairs":list(paper.PAIRS),
        "block_reasons":reason,
        "saved_two_model_ai_signal_eligible_by_evidence":ready,
        "new_paid_two_model_ai_eligible_by_evidence_and_budget":
            ready and budget_conditions_satisfied,
        "live_virtual_entry_authorized_by_this_pure_evaluator":False,
        "new_paid_request_authorized_by_this_pure_evaluator":False,
        "demo_broker_orders_permitted":False,
        "real_orders_permitted":False,
        "safety_hold_if_considered_in_live_runtime":not ready,
    }


def existing_runtime_no_go(state:dict,quote:dict,known:dict)->tuple[dict,dict]:
    """Production wiring: existing local saved calendar NEVER attests all.

    Independent verifiers are not yet implemented/deployed, therefore real
    evidence arguments are all FALSE. Never accept operator-controlled JSON
    as a substitute for independent source, timing, cost or clock proofs.
    """
    if (type(quote) is not dict or type(known) is not dict
            or type(known.get("active_known_blackout")) is not bool):
        raise InputError("INTEGRATED_RUNTIME_PROOF_INVALID")
    result=assess(
        state,quote_epoch=quote["capture_epoch"],
        known_important_event_blackout=known["active_known_blackout"],
        verified_complete_usd_eur_jpy_events=False,
        verified_independent_broker_pc_clock=False,
        verified_pre_release_consensus_time=False,
        verified_spread_slippage_swap_costs=False,
        verified_single_readonly_mt4_ea=False,
    )
    return result,budget_check(state)
