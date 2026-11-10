"""FWD-061: fail-closed active-pair scope review for FX forward research.

The older Q3 four-pair decision is historic and has been superseded.
The currently approved research and prospective trading scope is exactly
USD/JPY, EUR/JPY, EUR/USD; this tool never authorizes demo/live trading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.offline_backtest import PAIRS as LEGACY_RESEARCH_PAIRS, InputError
from research.forward_mt4_v2_quote import PAIRS_V2
from research.forward_mt4_v2_source_contract import review as source_review

SCHEMA = "fx_forward_active_three_pair_scope_v1"
FORMAL_PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")


def inspect(source: bytes) -> dict:
    if not isinstance(source, bytes):
        raise InputError("MQL4 source bytes required")
    preflight = source_review(source)
    blockers = []
    if tuple(LEGACY_RESEARCH_PAIRS) != FORMAL_PAIRS:
        blockers.append("RESEARCH_PAIR_SCOPE_MISMATCH")
    if tuple(PAIRS_V2) != FORMAL_PAIRS:
        blockers.append("MT4_V2_PAIR_SCOPE_MISMATCH")
    if not preflight["static_contract_passed"]:
        blockers.append("MT4_V2_SOURCE_CONTRACT_FAILED")
    script = source.decode("utf-8-sig")
    # This makes a historical four-pair regression visible before a PR merge.
    for symbol in ("GBPUSD", "AUDUSD"):
        if ('symbol == "' + symbol + '"') in script:
            blockers.append("OUT_OF_SCOPE_SYMBOL_" + symbol)
    return {
        "schema": SCHEMA,
        "status": "FORMAL_THREE_PAIR_RESEARCH_HOLD_NO_GO",
        "approved_pairs": list(FORMAL_PAIRS),
        "research_pairs": list(LEGACY_RESEARCH_PAIRS),
        "mt4_v2_pairs": list(PAIRS_V2),
        "pair_scope_consistent": not blockers,
        "blocking_reasons": sorted(set(blockers + [
            "BROKER_CONTRACT_ATTRIBUTES_UNVERIFIED",
            "G1_G9_AND_FX_SAF_NOT_AUTHORIZED",
            "METAEDITOR_REAL_COMPILATION_NOT_VERIFIED",
        ])),
        "mql4_source_sha256": preflight["source_sha256"],
        "historic_four_pair_decision_overridden": True,
        "real_account_scope_verified": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Check three-pair research scope, never GO")
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir() or
                not a.source.is_file() or
                a.source.stat().st_size > 50000):
            raise InputError("unsafe paths")
        report = inspect(a.source.read_bytes())
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "pair_scope_consistent": report["pair_scope_consistent"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0 if report["pair_scope_consistent"] else 2
    except (InputError, UnicodeError, OSError, TypeError, ValueError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "FORMAL_PAIR_SCOPE_MISMATCH",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
