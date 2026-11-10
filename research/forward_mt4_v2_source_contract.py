"""FWD-060 (corrected approved three-pair scope): offline v2 MQL4 export-contract audit, not executable certification.

Inspect the source text only. The MT4 executable, MetaEditor compiler,
broker session, terminal permissions, data license and clock are NOT tested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research.forward_mt4_v2_quote import COLUMNS, ORIGIN, PAIRS_V2
from research.offline_backtest import InputError

SCHEMA = "fx_forward_mt4_v2_source_contract_v1"
BANNED = ("OrderSend", "OrderModify", "OrderClose", "OrderDelete",
          "OrderCloseBy", "WebRequest", "ShellExecute", "WinExec",
          "FILE_COMMON", "#import", "AccountNumber", "AccountLogin")
NEEDED = ("#property strict", "void OnStart()", "IsDemo()",
          "IsConnected()", "MODE_BID", "MODE_ASK", "MODE_TIME",
          "TimeCurrent()", "TimeGMT()", "FILE_CSV",
          "FxForwardReadOnlyQuoteV2.csv",
          "MANUAL_MT4_DEMO_V2_UNVERIFIED", "tick_age_seconds",
          "server_tick_time", "server_now_time")


def review(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= 50000:
        raise InputError("invalid source size")
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("invalid MQL4 encoding") from exc
    if "\x00" in source:
        raise InputError("binary source")
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    failures = []
    for token in BANNED:
        if (re.search(r"\b" + re.escape(token) + r"\b", clean,
                      flags=re.IGNORECASE) if token != "#import"
                else "#import" in clean):
            failures.append("BANNED_SOURCE_TOKEN_" + token)
    for token in NEEDED:
        if token not in clean:
            failures.append("MISSING_SOURCE_TOKEN_" + token)
    for source_name in ("USDJPY", "EURJPY", "EURUSD"):
        if ('symbol == "' + source_name + '"') not in clean:
            failures.append("MISSING_SYMBOL_" + source_name)
    for obsolete_symbol in ("GBPUSD", "AUDUSD"):
        if re.search(r'symbol\s*==\s*"'+obsolete_symbol+r'"', clean):
            failures.append("OUT_OF_SCOPE_SYMBOL_" + obsolete_symbol)
    if tuple(PAIRS_V2) != ("USD/JPY", "EUR/JPY", "EUR/USD"):
        failures.append("THREE_PAIR_CONTRACT_UNEXPECTED")
    if tuple(COLUMNS) != (
            "observed_at_utc", "pair", "bid", "ask", "quote_to_jpy",
            "server_tick_time", "server_now_time", "tick_age_seconds",
            "account_type", "origin"):
        failures.append("CSV_SCHEMA_UNEXPECTED")
    if ORIGIN != "MANUAL_MT4_DEMO_V2_UNVERIFIED":
        failures.append("SOURCE_ORIGIN_UNEXPECTED")
    return {
        "schema": SCHEMA,
        "status": "MT4_V2_SOURCE_CONTRACT_HOLD_NO_GO",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "static_contract_passed": not failures,
        "static_failures": sorted(failures),
        "metaeditor_compilation_verified": False,
        "mt4_real_execution_verified": False,
        "broker_tick_time_timezone_attested": False,
        "operator_human_review_completed": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline MQL4 v2 source preflight, NO_GO")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir() or
                not a.source.is_file() or a.source.stat().st_size > 50000):
            raise InputError("bad source/output path")
        result = review(a.source.read_bytes())
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": result["status"],
                          "static_contract_passed": result["static_contract_passed"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0 if result["static_contract_passed"] else 2
    except (InputError, OSError, ValueError, TypeError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "MT4_V2_SOURCE_CONTRACT_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
