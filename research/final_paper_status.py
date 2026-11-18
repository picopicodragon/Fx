"""Offline read-only final-paper portfolio audit.

No provider calls, MT4 access, order interface or paper state mutation.
Existing event chain is checked before summarizing virtual results.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_runtime as runtime
from research.offline_backtest import InputError

SCHEMA="fx_final_paper_operating_status_v1"


def summarize(root:Path, *, now:datetime|None=None)->dict:
    state,head=runtime._journal_load(root/"journal")
    current=now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise InputError("status requires aware clock")
    if (type(state.get("paid_inference_calls")) is not int or
            not 0<=state["paid_inference_calls"]<=runtime.MAX_PAID_LIFETIME):
        raise InputError("invalid AI usage state")
    last=state["last_quote_epoch"]
    if type(last) is not int or last<0:
        raise InputError("invalid last quote clock")
    age=None if last==0 else int(current.timestamp())-last
    if age is not None and age< -10:
        raise InputError("future last quote clock")
    level=("NO_CAPTURE" if age is None else "LEVEL2" if age>=600
           else "LEVEL1" if age>=60 else "FRESH")
    halted=any(state[k] for k in (
        "daily_loss_latched","dd4_latched","dd5_latched",
        "communication_latched"))
    trades=state["trade_log"]
    wins=sum(1 for trade in trades if D(trade["virtual_pnl_jpy"])>0)
    losses=sum(1 for trade in trades if D(trade["virtual_pnl_jpy"])<0)
    realized=sum((D(trade["virtual_pnl_jpy"]) for trade in trades),D("0"))
    equity=D(state["equity_jpy"])
    start=D(state["start_capital_jpy"])
    return {
        "schema":SCHEMA,
        "status":"FINAL_PAPER_JOURNAL_AUDITED_VIRTUAL_ONLY_NO_GO",
        "completed_cycles":state["cycle_number"],
        "journal_head_sha256_local_only":head,
        "virtual_start_capital_jpy":state["start_capital_jpy"],
        "virtual_cash_jpy":state["cash_jpy"],
        "virtual_equity_jpy":state["equity_jpy"],
        "virtual_net_pnl_jpy":format(equity-start,".2f"),
        "virtual_realized_pnl_jpy":format(realized,".2f"),
        "virtual_trade_count":len(trades),
        "virtual_wins":wins,"virtual_losses":losses,
        "virtual_open_position_count":len(state["positions"]),
        "max_virtual_open_risk_jpy":format(sum((
            D(p["risk_jpy"]) for p in state["positions"]),D("0")),".2f"),
        "ny17_day":state["ny17_day"],
        "dd4_latched":state["dd4_latched"],
        "dd5_latched":state["dd5_latched"],
        "daily_loss_latched":state["daily_loss_latched"],
        "communication_latched":state["communication_latched"],
        "paid_ai_calls_lifetime":state["paid_inference_calls"],
        "paid_ai_calls_remaining_under_current_limit":
            runtime.MAX_PAID_LIFETIME-state["paid_inference_calls"],
        "paid_ai_lifetime_cap_reached":
            state["paid_inference_calls"]==runtime.MAX_PAID_LIFETIME,
        "api_cost_jpy_verified":False,
        "api_budget_renewal_authorized":False,
        "last_recorded_quote_age_seconds_pc_derived":age,
        "price_stream_warning_level_pc_derived":level,
        "quote_recent_enough_for_further_paper_evaluation":
            level=="FRESH" and not halted,
        "new_paid_ai_calls_authorized_by_status":False,
        "watchdog_only_does_not_persist_communication_latch":True,
        "jev_enabled":False,
        "independent_broker_clock_attested":False,
        "market_consensus_calendar_attested":False,
        "transaction_costs_fully_verified":False,
        "model_profitability_established":False,
        "broker_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Local paper-only risk/equity status")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        report=summarize(args.state_root)
        if args.out.exists() or args.out.is_symlink() or (
                not args.out.parent.is_dir() or
                args.out.parent.is_symlink()):
            raise InputError("unsafe status output")
        with args.out.open("x",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2)
        print(json.dumps(report,ensure_ascii=False))
        return 0
    except (InputError,ValueError,OSError,KeyError,TypeError,UnicodeError):
        print(json.dumps({
            "status":"FINAL_PAPER_STATUS_FAIL_CLOSED_NO_GO",
            "broker_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
            "safety_hold_latched":True,
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
