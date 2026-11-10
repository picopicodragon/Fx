"""FWD-021: conservative static inspection of undeployed MQL4 source.

Checks source content only, not compiled behavior, vendor binaries, or the
security of a running terminal. Not a permission to install/run the script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from research.offline_backtest import InputError

SCHEMA = "fx_mt4_readonly_source_audit_v1"
DISALLOWED = (
    "OrderSend", "OrderClose", "OrderDelete", "OrderModify",
    "OrderCloseBy", "OrderSelect", "WebRequest", "ShellExecute",
    "WinExec", "AccountNumber", "AccountLogin", "AccountInfoInteger",
    "DLL", "FileOpenHistory", "FILE_COMMON",
)
MANDATORY = (
    "IsDemo()", "IsConnected()", "MODE_BID", "MODE_ASK",
    "FxForwardReadOnlyQuote.csv", "FILE_WRITE",
    "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED",
)


def inspect_source(raw: bytes) -> dict:
    if type(raw) is not bytes or not raw or len(raw) > 50000:
        raise InputError("invalid MQL4 source size")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("nonutf8 MQL4 source") from exc
    if "\x00" in text:
        raise InputError("invalid MQL4 binary")
    # Strip comments before detecting required runtime guards.
    src = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.DOTALL)
    blockers = []
    for keyword in DISALLOWED:
        if re.search(r"\b" + re.escape(keyword) + r"\b", src, re.IGNORECASE):
            blockers.append("FORBIDDEN_TOKEN_" + keyword)
    for token in MANDATORY:
        if token not in src:
            blockers.append("MISSING_REQUIRED_" + token)
    if "void OnStart()" not in src or "#property strict" not in src:
        blockers.append("UNEXPECTED_SCRIPT_STRUCTURE")
    # No statement of proof: static inspection cannot exclude indirection
    # or unsafe compiled artifacts, even if all these tokens pass.
    return {
        "schema": SCHEMA,
        "status": "MT4_READONLY_SOURCE_STATIC_AUDIT_NO_GO",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "static_blocking_reasons": sorted(blockers),
        "static_token_checks_passed": not blockers,
        "metaeditor_compilation_verified": False,
        "rakuten_mt4_execution_verified": False,
        "source_behavior_certified": False,
        "mt4_demo_authenticated": False,
        "terminal_modified": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Review undeployed source; never touch MT4")
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir()
                or not a.source.is_file() or
                a.source.stat().st_size > 50000):
            raise InputError("invalid source/output")
        result = inspect_source(a.source.read_bytes())
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": result["status"],
                          "static_token_checks_passed":
                          result["static_token_checks_passed"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0 if result["static_token_checks_passed"] else 2
    except (InputError, OSError, TypeError, ValueError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_MQL4_SOURCE_AUDIT",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
