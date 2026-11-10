"""FWD-022: evidence-only forward-demo readiness blockers (never GO).

Reads locally generated FWD reports. An all-green local research assessment
does not constitute human approval, licensed market data or actual MT4 safety.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from research.offline_backtest import InputError

SCHEMA = "fx_forward_demo_readiness_v1"
MAX_BYTES = 1000000


def _validate(report: dict, status: str) -> None:
    if (type(report) is not dict or report.get("status") != status or
            report.get("runtime_go_no_go") != "NO_GO" or
            report.get("safety_hold_latched") is not True or
            report.get("real_orders_permitted") is not False):
        raise InputError("unsafe or unsupported research report")


def assess(observability: dict, quote: dict, static_mt4: dict,
           *, operator_evidence: dict | None = None) -> dict:
    _validate(observability, "FORWARD_OBSERVABILITY_HOLD_NO_GO")
    _validate(quote, "QUOTE_CONTINUITY_RESEARCH_NO_GO")
    _validate(static_mt4, "MT4_READONLY_SOURCE_STATIC_AUDIT_NO_GO")
    flags = set()
    if observability.get("blocking_reasons"):
        flags.add("OBSERVATION_RESEARCH_HOLDS")
    if quote.get("all_pairs_have_fresh_quotes") is not True:
        flags.add("QUOTES_NOT_FRESH")
    if static_mt4.get("static_token_checks_passed") is not True:
        flags.add("MQL4_STATIC_REVIEW_FAILED")
    if operator_evidence is not None:
        if (type(operator_evidence) is not dict or
                set(operator_evidence) != {"schema", "account_type_reported",
                                          "mt4_compilation_verified",
                                          "sole_terminal_session_reported",
                                          "data_license_reviewed"} or
                operator_evidence["schema"] != "fx_forward_operator_declaration_v1" or
                operator_evidence["account_type_reported"] not in ("DEMO", "UNKNOWN") or
                any(type(operator_evidence[k]) is not bool for k in (
                    "mt4_compilation_verified",
                    "sole_terminal_session_reported",
                    "data_license_reviewed"))):
            raise InputError("invalid manual declaration")
        if operator_evidence["account_type_reported"] != "DEMO":
            flags.add("DEMO_ACCOUNT_NOT_REPORTED")
        if not operator_evidence["mt4_compilation_verified"]:
            flags.add("MQL4_COMPILATION_NOT_REPORTED")
        if not operator_evidence["sole_terminal_session_reported"]:
            flags.add("SOLE_MT4_SESSION_NOT_REPORTED")
        if not operator_evidence["data_license_reviewed"]:
            flags.add("DATA_LICENSE_NOT_REPORTED")
    else:
        flags.add("OPERATOR_DECLARATION_ABSENT")
    # Self-reported flags are NEVER independent broker attestation.
    flags.update((
        "BROKER_DEMO_ACCOUNT_NOT_INDEPENDENTLY_AUTHENTICATED",
        "PRICE_AND_CLOCK_NOT_INDEPENDENTLY_ATTESTED",
        "SIMULATED_RISK_NOT_CERTIFIED_FOR_BROKER",
        "FORMAL_DEMO_ORDER_APPROVAL_NOT_GRANTED",
    ))
    return {
        "schema": SCHEMA,
        "status": "FWD_DEMO_READINESS_RESEARCH_NO_GO",
        "blocking_reasons": sorted(flags),
        "operator_report_is_not_independent_attestation": True,
        "mt4_live_terminal_access_performed": False,
        "automatic_execution_preparation_performed": False,
        "read_only_compilation_verified_by_software": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise InputError("invalid input report")
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(obj) is not dict:
        raise InputError("invalid report")
    return obj


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline demo preparation gap audit; NO_GO")
    p.add_argument("--observability", required=True, type=Path)
    p.add_argument("--quote", required=True, type=Path)
    p.add_argument("--mt4-static", required=True, type=Path)
    p.add_argument("--operator-declaration", type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir():
            raise InputError("output already exists")
        report = assess(_read(a.observability), _read(a.quote),
                        _read(a.mt4_static),
                        operator_evidence=(_read(a.operator_declaration)
                                           if a.operator_declaration else None))
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": report["status"],
                          "blocking_reasons": report["blocking_reasons"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "FWD_DEMO_READINESS_INPUT_INVALID",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
