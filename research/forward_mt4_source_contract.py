"""FWD-051: compare shipped MQL4 export *source* against local intake contract.

Static, conservative preflight only. Does not compile MQL4, execute MT4,
measure server tick age, access credentials, or permit any kind of order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from research.forward_mt4_static_audit import inspect_source
from research.forward_mt4_quote_import import COLUMNS, ORIGIN
from research.offline_backtest import InputError

SCHEMA = "fx_forward_mt4_source_contract_v1"
REQUIRED_SOURCE_FRAGMENTS = (
    'FileWrite(handle, "observed_at_utc", "pair", "bid", "ask",',
    '"quote_to_jpy", "account_type", "origin");',
    '"DEMO", "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED");',
    'FileOpen("FxForwardReadOnlyQuote.csv",',
    'RefreshRates();',
    'if(!IsDemo())',
    'if(!IsConnected())',
)


def review(raw: bytes) -> dict:
    static = inspect_source(raw)
    try:
        source = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise InputError("invalid MQL4 encoding") from exc
    failures = list(static["static_blocking_reasons"])
    for idx, fragment in enumerate(REQUIRED_SOURCE_FRAGMENTS, 1):
        if fragment not in source:
            failures.append("SOURCE_CONTRACT_FRAGMENT_MISSING_" + str(idx))
    if tuple(COLUMNS) != (
            "observed_at_utc", "pair", "bid", "ask", "quote_to_jpy",
            "account_type", "origin"):
        failures.append("PYTHON_IMPORT_CONTRACT_CHANGED")
    if ORIGIN != "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED":
        failures.append("ORIGIN_IDENTITY_CHANGED")
    # The source writes TimeGMT rather than a verified broker tick timestamp.
    # The clock is not independent. This is intentionally an enduring blocker.
    failures.extend((
        "METAEDITOR_COMPILE_NOT_EXECUTED",
        "MT4_REAL_TERMINAL_NOT_OBSERVED",
        "BROKER_TICK_TIMESTAMP_NOT_VERIFIED",
        "WINDOWS_CLOCK_NOT_INDEPENDENTLY_ATTESTED",
    ))
    return {
        "schema": SCHEMA,
        "status": "MT4_SOURCE_CONTRACT_REVIEW_HOLD_NO_GO",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "static_token_checks_passed": static["static_token_checks_passed"],
        "source_fragment_checks_passed": all(
            f.startswith(("METAEDITOR_", "MT4_REAL_", "BROKER_TICK_",
                          "WINDOWS_CLOCK_")) for f in failures),
        "blocking_reasons": sorted(failures),
        "source_compiled_in_metaeditor": False,
        "terminal_quote_export_tested": False,
        "broker_account_authenticated": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline MQL4-to-Python CSV contract review")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output collision")
        if not a.source.is_file() or a.source.stat().st_size > 50000:
            raise InputError("MQL4 source absent or oversized")
        result = review(a.source.read_bytes())
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({
            "status": result["status"],
            "source_fragment_checks_passed": result["source_fragment_checks_passed"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0 if result["source_fragment_checks_passed"] else 2
    except (InputError, OSError, ValueError, TypeError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "MT4_CSV_SOURCE_CONTRACT_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
