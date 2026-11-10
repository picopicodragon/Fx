"""FWD-075/076/078 static guard for UNDEPLOYED read-only 3-pair MT4 observer.

This is text inspection only; it does not attest compiler behavior, EA safety
at runtime, actual quote provenance, the user's terminal, or live trading.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from research.offline_backtest import PAIRS, InputError
from research.forward_mt4_v2_quote import COLUMNS

SCHEMA = "fx_forward_demo_timer_observer_source_review_v1"
BANNED = (
    "OrderSend", "OrderModify", "OrderClose", "OrderDelete",
    "OrderCloseBy", "WebRequest", "WinExec", "ShellExecute",
    "FILE_COMMON", "#import", "AccountLogin", "AccountNumber",
    "FileDelete", "FileMove", "FileCopy", "IsTradeAllowed",
    "TerminalInfoInteger", "EventSetMillisecondTimer"
)
REQUIRED = (
    "#property strict", "int OnInit()", "void OnTimer()",
    "void OnDeinit(", "EventSetTimer(", "EventKillTimer()",
    "IsDemo()", "IsConnected()", 'Symbol() != "USDJPY"',
    "MODE_BID", "MODE_ASK", "MODE_TIME", "TimeCurrent()",
    "TimeGMT()", "FileIsExist(", "FILE_CSV", "FILE_WRITE",
    "FILE_ANSI", "FileFlush(", "FileClose(", "FXFWD_MAX_CYCLES 30",
    "FXFWD_TIMER_SECONDS 60", "MANUAL_MT4_DEMO_V2_UNVERIFIED",
    "quote_to_jpy", "server_tick_time", "server_now_time",
    "tick_age_seconds", "observed_at_utc"
)


def inspect(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= 60000:
        raise InputError("missing/oversize source")
    try:
        src = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("unreadable source") from exc
    if "\x00" in src:
        raise InputError("binary content")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", src, flags=re.DOTALL)
    failures = []
    for term in BANNED:
        if (term == "#import" and term in clean) or (
            term != "#import" and re.search(
                r"\b" + re.escape(term) + r"\b", clean, re.IGNORECASE)):
            failures.append("PROHIBITED_" + term)
    for term in REQUIRED:
        if term not in clean:
            failures.append("REQUIRED_MISSING_" + term)
    # Match numeric defines with a word boundary, never a prefix: 30000
    # must not pass a required cap of 30.
    if not re.search(r"#define\s+FXFWD_MAX_CYCLES\s+30\b", clean):
        failures.append("INVALID_TIMER_CYCLE_CAP")
    if not re.search(r"#define\s+FXFWD_TIMER_SECONDS\s+60\b", clean):
        failures.append("INVALID_TIMER_INTERVAL")
    for symbol, pair in (("USDJPY","USD/JPY"),
                         ("EURJPY","EUR/JPY"),
                         ("EURUSD","EUR/USD")):
        if '"'+symbol+'"' not in clean or '"'+pair+'"' not in clean:
            failures.append("PAIR_MISSING_" + pair)
    for symbol in ("GBPUSD","AUDUSD"):
        if '"'+symbol+'"' in clean:
            failures.append("OUT_OF_SCOPE_" + symbol)
    if tuple(PAIRS) != ("USD/JPY","EUR/JPY","EUR/USD"):
        failures.append("RESEARCH_PAIR_CONTRACT_MISMATCH")
    if tuple(COLUMNS) != (
            "observed_at_utc", "pair", "bid", "ask", "quote_to_jpy",
            "server_tick_time", "server_now_time", "tick_age_seconds",
            "account_type", "origin"):
        failures.append("CSV_CONTRACT_MISMATCH")
    if re.search(r"\bif\s*\(\s*!\s*RefreshRates\s*\(\s*\)\s*\)",clean):
        failures.append("REFRESHRATES_BOOLEAN_MISUSE")
    return {
        "schema": SCHEMA,
        "status": "DEMO_TIMER_OBSERVER_STATIC_RESEARCH_NO_GO",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "static_preflight_passed": not failures,
        "static_failures": sorted(set(failures)),
        "formal_pairs": list(PAIRS),
        "timer_seconds_declared": 60,
        "maximum_timer_cycles_declared": 30,
        "metaeditor_compilation_verified": False,
        "actual_mt4_runtime_verified": False,
        "actual_continuous_capture_verified": False,
        "independent_broker_quote_verified": False,
        "demo_trading_allowed": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline read-only MT4 EA static audit")
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir() or
            not a.source.is_file() or a.source.is_symlink() or
            not 0 < a.source.stat().st_size <= 60000):
            raise InputError("unsafe paths")
        result = inspect(a.source.read_bytes())
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": result["status"],
                          "static_preflight_passed": result["static_preflight_passed"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0 if result["static_preflight_passed"] else 2
    except (InputError, OSError, ValueError, TypeError, UnicodeError):
        print(json.dumps({"status":"FAIL_CLOSED",
                          "reason":"READONLY_OBSERVER_SOURCE_UNVERIFIED",
                          "runtime_go_no_go":"NO_GO",
                          "safety_hold_latched":True,
                          "real_orders_permitted":False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
