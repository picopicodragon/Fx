"""FINAL-PAPER-03: deterministic virtual trades from DEMO bid/ask observations.

NO broker orders, NO API calls, NO open-network code. Only replaying a model
decision with independent APPROVED review and the NEXT observed DEMO quote
can create a virtual position. This is not licensed/verified execution.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from decimal import Decimal as D, ROUND_FLOOR
from pathlib import Path

from research.forward_risk_timeline import trading_day
from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_virtual_portfolio_v1"
PAIRS = ("USD/JPY","EUR/JPY","EUR/USD")
SYMS = ("USDJPY","EURJPY","EURUSD")
SYMBOL_TO_PAIR = dict(zip(SYMS, PAIRS))
PIP = {"USD/JPY":D(".01"),"EUR/JPY":D(".01"),"EUR/USD":D(".0001")}
QUOTE_FIELDS = (
    "pair","bid","ask","tick_time_broker_epoch_unattested",
    "broker_time_epoch_unattested","capture_epoch_utc_pc",
    "tickvalue_jpy_broker_reported","ticksize_broker_reported",
    "min_lot_broker_reported","lot_step_broker_reported",
    "max_lot_broker_reported","point_broker_reported",
)
QUOTE_NAME = re.compile(r"^FxPaperQuote_[0-9]{8}_[0-9]{6}\.csv$")
MONEY = D("0.01")
INITIAL = D("100000")
FRACTION = D(".005")
CONCURRENT = D(".01")
DAY_LIMIT = D(".015")
DD_LEVEL3 = D(".04")
DD_HARD = D(".05")
SLIPPAGE_PIPS_EACH_SIDE = D("1")


def _dec(value: object, *, positive: bool = False) -> D:
    if isinstance(value,bool) or type(value) not in (str,int,float,D):
        raise InputError("bad virtual amount")
    try:
        number=D(str(value))
    except ArithmeticError as exc:
        raise InputError("bad virtual amount") from exc
    if not number.is_finite() or (positive and number<=0):
        raise InputError("bad virtual amount")
    return number


def _s(v: D) -> str:
    return format(v.quantize(MONEY),"f")


def initial_state() -> dict:
    return {
        "schema":SCHEMA,"start_capital_jpy":"100000.00",
        "cash_jpy":"100000.00","equity_jpy":"100000.00",
        "peak_equity_jpy":"100000.00","ny17_day":None,
        "day_start_equity_jpy":"100000.00",
        "daily_loss_latched":False,"dd4_latched":False,
        "dd5_latched":False,"communication_latched":False,
        "positions":[],"pending_signals":[],
        "used_signal_ids":[],"trade_log":[],
        "processed_h1_keys":[],"paid_inference_calls":0,
        "last_quote_epoch":0,"cycle_number":0,
        "virtual_only":True,"broker_orders_permitted":False,
        "jev_required":False,
    }


def validate_quotes(file: Path, *, now: datetime|None=None) -> dict:
    if (not file.is_file() or file.is_symlink() or
            any(p.is_symlink() for p in file.parents) or
            not QUOTE_NAME.fullmatch(file.name)
            or not 0<file.stat().st_size<=4500):
        raise InputError("missing or unsafe DEMO quote snapshot")
    raw=file.read_bytes()
    if b"\x00" in raw:
        raise InputError("invalid quote bytes")
    try:
        reader=csv.DictReader(raw.decode("utf-8-sig").splitlines(),strict=True)
        if tuple(reader.fieldnames or ())!=QUOTE_FIELDS:
            raise InputError("invalid quote columns")
        rows=list(reader)
    except (UnicodeError,csv.Error) as exc:
        raise InputError("invalid quote CSV") from exc
    if len(rows)!=3 or tuple(row["pair"] for row in rows)!=SYMS:
        raise InputError("three quote pairs required")
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise InputError("naive time")
    quotes={}
    epochs=set()
    for row in rows:
        if None in row or set(row)!=set(QUOTE_FIELDS):
            raise InputError("quote row columns")
        try:
            epoch=int(row["capture_epoch_utc_pc"])
            broker=int(row["broker_time_epoch_unattested"])
            tick=int(row["tick_time_broker_epoch_unattested"])
            numbers=[_dec(row[key],positive=True) for key in (
                "bid","ask","tickvalue_jpy_broker_reported",
                "ticksize_broker_reported","min_lot_broker_reported",
                "lot_step_broker_reported","max_lot_broker_reported",
                "point_broker_reported")]
        except (ValueError,OverflowError,TypeError) as exc:
            raise InputError("quote parse failure") from exc
        bid,ask,tickvalue,ticksize,minlot,step,maxlot,point=numbers
        if (ask<=bid or minlot>maxlot or
                step>maxlot or epoch<=0 or broker<=0 or tick<=0 or
                not 0<=broker-tick<=30):
            raise InputError("invalid quote or reported contract")
        epochs.add(epoch)
        quotes[SYMBOL_TO_PAIR[row["pair"]]]={
            "bid":bid,"ask":ask,"tickvalue":tickvalue,"ticksize":ticksize,
            "minlot":minlot,"step":step,"maxlot":maxlot,"point":point,
        }
    if len(epochs)!=1:
        raise InputError("non-atomic quotes")
    epoch=epochs.pop()
    age=now.timestamp()-epoch
    if not -10<=age<=120:
        raise InputError("stale/future quote")
    return {"capture_epoch":epoch,"quotes":quotes,
            "source_sha256":hashlib.sha256(raw).hexdigest()}


def _mark(position: dict, quote: dict) -> D:
    direction=1 if position["direction"]=="LONG" else -1
    exit_price=(quote["bid"] if direction==1 else quote["ask"]) - (
        D(direction)*PIP[position["pair"]]*SLIPPAGE_PIPS_EACH_SIDE)
    diff=(exit_price-_dec(position["entry"],positive=True))*direction
    return diff/quote["ticksize"]*quote["tickvalue"]*_dec(position["lots"],positive=True)


def _equity(state: dict, quotes:dict)->D:
    return _dec(state["cash_jpy"])+sum((
        _mark(p,quotes[p["pair"]]) for p in state["positions"]),D("0"))


def _risk(position:dict)->D:
    return _dec(position["risk_jpy"],positive=True)


def _close(state:dict, pos:dict, quote:dict, *, reason:str, epoch:int)->None:
    pnl=_mark(pos,quote)
    state["cash_jpy"]=_s(_dec(state["cash_jpy"])+pnl)
    state["positions"].remove(pos)
    state["trade_log"].append({
        "pair":pos["pair"],"direction":pos["direction"],
        "opened_epoch":pos["opened_epoch"],"closed_epoch":epoch,
        "reason":reason,"lots":pos["lots"],"virtual_pnl_jpy":_s(pnl),
        "signal_id":pos["signal_id"],"hypothetical":True,
    })


def _valid_signal(sig:dict)->bool:
    return (type(sig) is dict and set(sig)=={
        "id","pair","action","verdict","reviewed_epoch","atr14",
        "packet_sha256"}
        and sig["pair"] in PAIRS
        and sig["action"] in ("LONG","SHORT","HOLD","FLAT")
        and sig["verdict"] in ("APPROVED","REVISION","REJECTED","PENDING")
        and type(sig["reviewed_epoch"]) is int and sig["reviewed_epoch"]>0
        and type(sig["id"]) is str and
        re.fullmatch("[a-f0-9]{64}",sig["id"]) is not None
        and type(sig["packet_sha256"]) is str and
        re.fullmatch("[a-f0-9]{64}",sig["packet_sha256"]) is not None
        and _dec(sig["atr14"])>0)


def _enter(state:dict, sig:dict, quote:dict, epoch:int)->str:
    pair=sig["pair"]
    if any(p["pair"]==pair for p in state["positions"]):
        return "PAIR_ALREADY_OPEN"
    if len(state["positions"])>=2:
        return "MAX_TWO_VIRTUAL_POSITIONS"
    # Full current mark-to-market equity is computed before new entries.
    equity=_dec(state["equity_jpy"])
    if equity<=0:
        return "NONPOSITIVE_EQUITY"
    direction=1 if sig["action"]=="LONG" else -1
    raw=quote["ask"] if direction==1 else quote["bid"]
    entry=raw+D(direction)*PIP[pair]*SLIPPAGE_PIPS_EACH_SIDE
    stopdistance=max(_dec(sig["atr14"],positive=True)*2,
                     PIP[pair]*D("5"))
    # Conservative sizing covers spread and one-pip exit slippage.
    stopdistance += PIP[pair]*SLIPPAGE_PIPS_EACH_SIDE
    loss_per_lot=(stopdistance/quote["ticksize"])*quote["tickvalue"]
    available=equity*FRACTION
    current_risk=sum((_risk(p) for p in state["positions"]),D("0"))
    available=min(available,max(D("0"),equity*CONCURRENT-current_risk))
    cap=available/loss_per_lot
    slots=(min(cap,quote["maxlot"])/quote["step"]).to_integral_value(
        rounding=ROUND_FLOOR)
    lots=slots*quote["step"]
    if lots<quote["minlot"] or lots<=0:
        return "VIRTUAL_LOT_BELOW_MINIMUM"
    potential=lots*loss_per_lot
    if potential>equity*FRACTION or potential+current_risk>equity*CONCURRENT:
        raise InputError("virtual risk limit violation")
    stop=entry-D(direction)*stopdistance
    target=entry+D(direction)*stopdistance*D("1.5")
    state["positions"].append({
        "pair":pair,"direction":sig["action"],"lots":str(lots),
        "entry":str(entry),"stop":str(stop),"target":str(target),
        "risk_jpy":_s(potential),
        "opened_epoch":epoch,"signal_id":sig["id"],
        "original_stop_distance":str(stopdistance),
        "trailing_started":False,
    })
    return "VIRTUAL_POSITION_OPENED"


def step(state:dict, capture:dict, *, signals:list[dict]|None=None)->tuple[dict,dict]:
    """Pure step; caller must durable-write new state before acknowledging."""
    if (type(state) is not dict or state.get("schema")!=SCHEMA
        or state.get("start_capital_jpy")!="100000.00"
        or state.get("virtual_only") is not True
        or state.get("broker_orders_permitted") is not False
        or state.get("jev_required") is not False):
        raise InputError("unsafe paper state")
    next_state=json.loads(json.dumps(state))
    epoch=capture["capture_epoch"]
    if type(epoch) is not int or epoch<=state["last_quote_epoch"]:
        raise InputError("quote replay or time reversed")
    quotes=capture["quotes"]
    if set(quotes)!=set(PAIRS):
        raise InputError("incomplete price set")
    events=[]
    if state["last_quote_epoch"]>0:
        delta=epoch-state["last_quote_epoch"]
        if delta>600:
            next_state["communication_latched"]=True
            events.append("VIRTUAL_COMMUNICATION_LEVEL2_LATCHED")
        elif delta>90:
            events.append("VIRTUAL_COMMUNICATION_LEVEL1_WARNING")
    for pos in list(next_state["positions"]):
        q=quotes[pos["pair"]]
        mark=q["bid"]-PIP[pos["pair"]] if pos["direction"]=="LONG" else q["ask"]+PIP[pos["pair"]]
        low=_dec(pos["stop"],positive=True)
        high=_dec(pos["target"],positive=True)
        direction=1 if pos["direction"]=="LONG" else -1
        if (direction==1 and mark<=low) or (direction==-1 and mark>=low):
            _close(next_state,pos,q,reason="VIRTUAL_STOP",epoch=epoch)
            events.append("VIRTUAL_STOP")
        elif (direction==1 and mark>=high) or (direction==-1 and mark<=high):
            _close(next_state,pos,q,reason="VIRTUAL_TARGET",epoch=epoch)
            events.append("VIRTUAL_TARGET")
        else:
            movement=(mark-_dec(pos["entry"]))*direction
            start=_dec(pos["original_stop_distance"])
            if movement>=start:
                candidate=mark-D(direction)*max(start,D("0"))
                old=_dec(pos["stop"])
                improve=(candidate-old)*direction
                minstep=max(PIP[pos["pair"]]*D("2"),start*D(".025"))
                if improve>minstep:
                    pos["stop"]=str(candidate)
                    pos["trailing_started"]=True
                    events.append("VIRTUAL_TRAIL")
    next_state["equity_jpy"]=_s(_equity(next_state,quotes))
    now=datetime.fromtimestamp(epoch,tz=timezone.utc)
    day=trading_day(now.isoformat().replace("+00:00","Z"))
    if next_state["ny17_day"]!=day:
        next_state["ny17_day"]=day
        next_state["day_start_equity_jpy"]=next_state["equity_jpy"]
        next_state["daily_loss_latched"]=False
        events.append("NY17_DAILY_RESET_PAPER_ONLY")
    equity=_dec(next_state["equity_jpy"])
    peak=max(_dec(next_state["peak_equity_jpy"]),equity)
    next_state["peak_equity_jpy"]=_s(peak)
    dd=(peak-equity)/peak
    daystart=_dec(next_state["day_start_equity_jpy"],positive=True)
    dayloss=max(D("0"),(daystart-equity)/daystart)
    if dd>=DD_LEVEL3:
        next_state["dd4_latched"]=True
    if dd>=DD_HARD:
        next_state["dd5_latched"]=True
    if dayloss>=DAY_LIMIT:
        next_state["daily_loss_latched"]=True
    if next_state["dd5_latched"] or next_state["daily_loss_latched"]:
        reason=("VIRTUAL_DD5_HALT" if next_state["dd5_latched"]
                else "VIRTUAL_DAILY_HALT")
        for pos in list(next_state["positions"]):
            _close(next_state,pos,quotes[pos["pair"]],reason=reason,epoch=epoch)
        next_state["equity_jpy"]=_s(_equity(next_state,quotes))
        events.append(reason)
    actions=signals or []
    if type(actions) is not list or len(actions)>3:
        raise InputError("invalid signal count")
    for sig in actions:
        if not _valid_signal(sig):
            raise InputError("invalid linked AI signal")
        if sig["id"] in next_state["used_signal_ids"] or any(
                s["id"]==sig["id"] for s in next_state["pending_signals"]):
            raise InputError("duplicate signal")
        next_state["pending_signals"].append(sig)
    active=[]
    for sig in next_state["pending_signals"]:
        if sig["reviewed_epoch"]>=epoch:
            active.append(sig)
            continue
        # No same-quote lookahead; expire after one H1.
        if epoch-sig["reviewed_epoch"]>4200:
            events.append("VIRTUAL_SIGNAL_EXPIRED")
            next_state["used_signal_ids"].append(sig["id"])
            continue
        if sig["verdict"]=="APPROVED" and sig["action"] in ("LONG","SHORT"):
            if (next_state["daily_loss_latched"] or
                next_state["dd4_latched"] or next_state["dd5_latched"] or
                next_state["communication_latched"]):
                events.append("VIRTUAL_RISK_HALTED")
            else:
                events.append(_enter(next_state,sig,quotes[sig["pair"]],epoch))
        else:
            events.append("AI_HOLD_OR_NONAPPROVED_NO_POSITION")
        next_state["used_signal_ids"].append(sig["id"])
    next_state["pending_signals"]=active
    next_state["equity_jpy"]=_s(_equity(next_state,quotes))
    next_state["cycle_number"]=state["cycle_number"]+1
    next_state["last_quote_epoch"]=epoch
    if len(next_state["used_signal_ids"])>10000 or len(next_state["trade_log"])>10000:
        raise InputError("paper audit state cap reached")
    return next_state,{
        "status":"VIRTUAL_PAPER_CYCLE_RECORDED_RESEARCH_NO_GO",
        "asof_pc_utc_unattested_epoch":epoch,
        "virtual_equity_jpy":next_state["equity_jpy"],
        "virtual_cash_jpy":next_state["cash_jpy"],
        "virtual_position_count":len(next_state["positions"]),
        "simulated_closed_trade_count":len(next_state["trade_log"]),
        "events":events,
        "dd4_latched":next_state["dd4_latched"],
        "dd5_latched":next_state["dd5_latched"],
        "daily_loss_latched":next_state["daily_loss_latched"],
        "communication_latched":next_state["communication_latched"],
        "jev_enabled":False,
        "broker_orders_sent_this_run":0,
        "demo_broker_orders_permitted":False,
        "real_orders_permitted":False,
        "runtime_go_no_go":"NO_GO",
        "safety_hold_latched":True,
        "simulated_only":True,
    }
