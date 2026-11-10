"""FWD-069/070: review MT4 read-only v3 exporter without starting MT4.

Static text inspection is not compilation or sandbox behavior verification.
The output stays NO_GO and cannot authorize MQL4 execution or any order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from research.offline_backtest import PAIRS, InputError
from research.forward_mt4_v2_quote import COLUMNS, ORIGIN

SCHEMA = "fx_forward_mt4_v3_source_preflight_v1"
SYMBOLS = ("USDJPY", "EURJPY", "EURUSD")
BANNED = ("OrderSend", "OrderModify", "OrderClose", "OrderDelete",
          "OrderCloseBy", "WebRequest", "WinExec", "ShellExecute",
          "FILE_COMMON", "#import", "AccountNumber", "AccountLogin",
          "FileDelete", "FileMove", "FileCopy")
REQUIRED = ("#property strict", "void OnStart()", "IsDemo()",
            "IsConnected()", "RefreshRates()", "MODE_BID", "MODE_ASK",
            "MODE_TIME", "TimeCurrent()", "TimeGMT()", "FileIsExist(",
            "FILE_CSV", "FILE_WRITE", "FILE_ANSI", "FileFlush(",
            "FileClose(", "server_tick_time", "server_now_time",
            "tick_age_seconds", "observed_at_utc", "quote_to_jpy",
            "MANUAL_MT4_DEMO_V2_UNVERIFIED")


def inspect(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= 50000:
        raise InputError("bad MQL4 source size")
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("unsupported MQL4 encoding") from exc
    if "\x00" in source:
        raise InputError("binary MQL4 content")
    # Static coarse inspection: does not resolve macros, aliases, or calls.
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    failed = []
    for name in BANNED:
        if (name == "#import" and name in clean) or (
                name != "#import" and re.search(
                    r"\b" + re.escape(name) + r"\b", clean, re.IGNORECASE)):
            failed.append("FORBIDDEN_" + name)
    for phrase in REQUIRED:
        if phrase not in clean:
            failed.append("REQUIRED_MISSING_" + phrase)
    # FWD-073: RefreshRates false means the snapshot was already current.
    # Never short-circuit the one-shot script solely on that boolean.
    if re.search(r"\\bif\\s*\\(\\s*!\\s*RefreshRates\\s*\\(\\s*\\)\\s*\\)", clean):
        failed.append("INVALID_REFRESH_RATES_FAILURE_GATE")
    if re.search(r"\\bif\\s*\\(\\s*RefreshRates\\s*\\(\\s*\\)\\s*==\\s*false", clean):
        failed.append("INVALID_REFRESH_RATES_FAILURE_GATE")
    for symbol in SYMBOLS:
        if ('symbol == "' + symbol + '"') not in clean:
            failed.append("SYMBOL_MISSING_" + symbol)
    for symbol in ("GBPUSD", "AUDUSD"):
        if re.search(r'\bsymbol\s*==\s*"' + symbol + r'"', clean):
            failed.append("FORBIDDEN_SYMBOL_" + symbol)
    if tuple(PAIRS) != ("USD/JPY", "EUR/JPY", "EUR/USD"):
        failed.append("FORMAL_THREE_PAIRS_MISMATCH")
    expected = ("observed_at_utc", "pair", "bid", "ask", "quote_to_jpy",
                "server_tick_time", "server_now_time", "tick_age_seconds",
                "account_type", "origin")
    if COLUMNS != expected or ORIGIN != "MANUAL_MT4_DEMO_V2_UNVERIFIED":
        failed.append("PYTHON_CSV_CONTRACT_MISMATCH")
    # Legacy v2 parser is intentionally reused with the v3 naming scheme.
    if '"FxFwdV3_" + symbol' not in clean:
        failed.append("UNIQUE_OUTPUT_NAMING_MISSING")
    return {
        "schema": SCHEMA, "status": "MT4_V3_SOURCE_REVIEW_NO_GO",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "static_preflight_passed": not failed,
        "static_failures": sorted(set(failed)),
        "formal_pairs": list(PAIRS),
        "metaeditor_compile_verified": False,
        "real_mt4_terminal_execution_verified": False,
        "actual_file_overwrite_prevention_verified": False,
        "broker_timestamp_authenticated": False,
        "terminal_log_capture_verified": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Review undeployed MT4 v3 source, NO_GO")
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir()
                or not a.source.is_file() or a.source.is_symlink()
                or not 0 < a.source.stat().st_size <= 50000):
            raise InputError("unsafe paths")
        result = inspect(a.source.read_bytes())
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "static_preflight_passed": result["static_preflight_passed"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False}))
        return 0 if result["static_preflight_passed"] else 2
    except (InputError, OSError, TypeError, UnicodeError, ValueError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MT4_V3_SOURCE_PREFLIGHT_INVALID",
            "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
