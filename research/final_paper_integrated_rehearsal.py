"""Full offline rehearsal of model-reviewed FX signal -> risk engine.

No order or live journal, no new paid AI. Inputs are synthetic fixtures or
caller-provided validated data. Can test with H1-linked COMPLETE two-model
signals after an independent verifier is implemented, but cannot itself
prove macro authenticity, independent clock or actual broker fills.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime,timezone
from pathlib import Path

from research import final_paper_engine as paper
from research import final_paper_integrated_control as control
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_ai_virtual_integration_rehearsal_v1"


def run_virtual_rehearsal(
    original_quote:dict, signal:dict, *,
    verified_complete_usd_eur_jpy_events:bool,
    verified_independent_broker_pc_clock:bool,
    verified_pre_release_consensus_time:bool,
    verified_spread_slippage_swap_costs:bool,
    verified_single_readonly_mt4_ea:bool,
    known_important_event_blackout:bool=False,
)->dict:
    """Isolated only. An APPROVED signal must pass the pure evidence gate.

    Verified parameters in *unit tests* model a hypothetical future proof,
    not proof of today's MT4 account. Never call from live runtime.
    """
    if (type(original_quote) is not dict
            or type(signal) is not dict or not paper._valid_signal(signal)):
        raise InputError("INTEGRATION_REHEARSAL_QUOTE_OR_SIGNAL_INVALID")
    state=paper.initial_state()
    # First cycle marks an actually verified captured market price; a
    # second quote is required to execute model recommendation without
    # same-cycle execution. The first state is not persisted anywhere.
    state["last_quote_epoch"]=original_quote["capture_epoch"]-1
    gate=control.assess(
        state,quote_epoch=original_quote["capture_epoch"],
        known_important_event_blackout=known_important_event_blackout,
        verified_complete_usd_eur_jpy_events=
            verified_complete_usd_eur_jpy_events,
        verified_independent_broker_pc_clock=
            verified_independent_broker_pc_clock,
        verified_pre_release_consensus_time=
            verified_pre_release_consensus_time,
        verified_spread_slippage_swap_costs=
            verified_spread_slippage_swap_costs,
        verified_single_readonly_mt4_ea=
            verified_single_readonly_mt4_ea,
    )
    model_review_ready=gate["saved_two_model_ai_signal_eligible_by_evidence"]
    # In the real supervisor, the AI signal is independently loaded from
    # linked H1/official evidence only when signal_path_safe. Here, a
    # hypothetical injected signal exercises the same pure portfolio code.
    incoming=[signal] if model_review_ready else []
    next_state,result=paper.step(
        state,original_quote,signals=incoming,
        known_event_blackout=known_important_event_blackout,
        entry_evidence_ready=model_review_ready)
    if result["broker_orders_sent_this_run"]!=0:
        raise InputError("INTEGRATION_REHEARSAL_BROKER_ORDER_UNEXPECTED")
    open_count=len(next_state["positions"])
    risk_sum=sum(paper._risk(p) for p in next_state["positions"])
    if risk_sum>paper.INITIAL*paper.CONCURRENT:
        raise InputError("INTEGRATION_REHEARSAL_TOTAL_RISK_EXCEEDED")
    if any(paper._risk(p)>paper.INITIAL*paper.FRACTION
           for p in next_state["positions"]):
        raise InputError("INTEGRATION_REHEARSAL_TRADE_RISK_EXCEEDED")
    return {
        "schema":SCHEMA,
        "status":"OFFLINE_AI_TO_VIRTUAL_PORTFOLIO_MECHANICS_RESEARCH_NO_GO",
        "model_review_injected_as_offline_fixture_only":True,
        "pure_evidence_gate_block_reasons":gate["block_reasons"],
        "hypothetical_evidence_eligible":model_review_ready,
        "hypothetical_virtual_position_count":open_count,
        "hypothetical_total_risk_jpy":str(risk_sum),
        "hypothetical_engine_events":result["events"],
        "simulated_paper_cycle_count":1,
        "approved_ai_model_outputs_actual":False,
        "actual_live_virtual_positions_opened":False,
        "actual_paid_api_calls":0,
        "actual_broker_orders":0,
        "live_paper_journal_touched":False,
        "live_communication_latch_touched":False,
        "model_performance_verified":False,
        "new_paid_ai_requests_permitted":False,
        "new_live_virtual_entries_permitted":False,
        "demo_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def run_unattested_source(quote_path:Path)->dict:
    """Accept only an original real DEMO quote, not a fabricated safe flag."""
    import re
    if (not quote_path.is_file() or quote_path.is_symlink()
            or quote_path.parent.name.lower()!="files"
            or quote_path.parent.parent.name.lower()!="mql4"
            or re.fullmatch(r"FxPaperQuote_[0-9]{8}_[0-9]{6}\.csv",
                            quote_path.name) is None):
        raise InputError("INTEGRATION_REHEARSAL_ORIGINAL_SOURCE_UNSAFE")
    stamp=datetime.strptime(quote_path.name[13:-4],
                            "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    quote=paper.validate_quotes(
        quote_path,now=stamp.replace(tzinfo=timezone.utc))
    if quote["capture_epoch"]!=int(stamp.timestamp()):
        raise InputError("INTEGRATION_REHEARSAL_SOURCE_CAPTURE_INVALID")
    # These are NOT actual AI model outputs. They test the synthetic data
    # flow, but never unlock actual virtual trade on the Windows machine.
    outcomes={}
    for pair in paper.PAIRS:
        from hashlib import sha256
        signal={
            "id":sha256(("ISOLATED_ONLY:"+pair).encode()).hexdigest(),
            "pair":pair,"action":"LONG","verdict":"APPROVED",
            "reviewed_epoch":quote["capture_epoch"]-1,
            "atr14":str(paper.PIP[pair]*paper.D("10")),
            "packet_sha256":"0"*64,
        }
        outcomes[pair]=run_virtual_rehearsal(
            quote,signal,
            verified_complete_usd_eur_jpy_events=False,
            verified_independent_broker_pc_clock=False,
            verified_pre_release_consensus_time=False,
            verified_spread_slippage_swap_costs=False,
            verified_single_readonly_mt4_ea=False,
        )
    return {
        "schema":"fx_final_paper_real_quote_three_pair_rehearsal_v1",
        "status":"THREE_PAIR_AI_VIRTUAL_INTEGRATION_OFFLINE_HOLD_NO_GO",
        "source":quote_path.name,
        "three_pair_statuses":{pair:{
            "hypothetical_position_count":
                result["hypothetical_virtual_position_count"],
            "reasons":result["pure_evidence_gate_block_reasons"],
        } for pair,result in outcomes.items()},
        "actual_new_virtual_entries":0,
        "actual_paid_requests":0,
        "broker_orders":0,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Three-pair real DEMO source offline final AI/virtual risk rehearsal")
    p.add_argument("--quote",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=run_unattested_source(args.quote)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir() or args.out.parent.is_symlink()):
            raise InputError("INTEGRATION_REHEARSAL_OUTPUT_UNSAFE")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,OSError,TypeError,ValueError,KeyError,
            UnicodeError,OverflowError,ArithmeticError):
        print(json.dumps({
            "schema":"fx_final_paper_real_quote_three_pair_rehearsal_v1",
            "status":"AI_VIRTUAL_REHEARSAL_FAIL_CLOSED_NO_GO",
            "new_virtual_entries_permitted":False,
            "new_paid_ai_requests_permitted":False,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
