"""FWD-063/064: offline MetaEditor v2 compile-evidence intake.

Only accepts an operator-authored JSON record and the exact local MQL4 source.
It NEVER launches MetaEditor, MT4, Windows services, external APIs or orders.
Even a reported '0 errors' is an *unverified operator claim*, never approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research.offline_backtest import InputError, timestamp
from research.forward_mt4_v2_source_contract import review as static_review
from research.forward_active_pair_scope import FORMAL_PAIRS

SCHEMA = "fx_forward_metaeditor_evidence_v1"
MAX_BYTES = 16000
HEX = re.compile(r"^[0-9a-f]{64}$")
COMPILER_STATES = ("NOT_RUN", "REPORTED_SUCCESS", "REPORTED_FAILURE")


def inspect(record: dict, mql4: bytes) -> dict:
    if (type(record) is not dict or
            set(record) != {
                "schema", "captured_at_utc", "compiler_status",
                "source_sha256", "reported_error_count",
                "reported_warning_count", "operator_environment",
                "account_type_reported", "mt4_script_executed"} or
            record.get("schema") != SCHEMA or
            record.get("compiler_status") not in COMPILER_STATES or
            type(record.get("reported_error_count")) is not int or
            not 0 <= record["reported_error_count"] <= 100000 or
            type(record.get("reported_warning_count")) is not int or
            not 0 <= record["reported_warning_count"] <= 100000 or
            record.get("operator_environment") != "WINDOWS_MANUAL" or
            record.get("account_type_reported") != "DEMO" or
            record.get("mt4_script_executed") is not False or
            type(record.get("source_sha256")) is not str or
            not HEX.fullmatch(record["source_sha256"])):
        raise InputError("invalid or unsupported manual compiler declaration")
    timestamp(record["captured_at_utc"])
    static = static_review(mql4)
    if record["source_sha256"] != hashlib.sha256(mql4).hexdigest():
        raise InputError("compiler source hash mismatch")
    if record["compiler_status"] == "NOT_RUN" and (
            record["reported_error_count"] or record["reported_warning_count"]):
        raise InputError("impossible compiler status")
    if record["compiler_status"] == "REPORTED_SUCCESS" and (
            record["reported_error_count"] != 0):
        raise InputError("claimed success with reported errors")
    if record["compiler_status"] == "REPORTED_FAILURE" and (
            record["reported_error_count"] == 0):
        raise InputError("failure lacks error count")
    return {
        "schema": SCHEMA,
        "status": "METAEDITOR_EVIDENCE_RESEARCH_HOLD_NO_GO",
        "captured_at_utc": record["captured_at_utc"],
        "source_sha256": record["source_sha256"],
        "formal_pairs": list(FORMAL_PAIRS),
        "source_static_contract_passed": static["static_contract_passed"],
        "compiler_status_self_reported": record["compiler_status"],
        "compiler_errors_self_reported": record["reported_error_count"],
        "compiler_warnings_self_reported": record["reported_warning_count"],
        "mt4_script_executed": False,
        "metaeditor_compilation_independently_verified": False,
        "terminal_access_performed_by_auditor": False,
        "account_type_independently_verified": False,
        "demo_order_execution_enabled": False,
        "blocking_reasons": sorted([
            "COMPILE_REPORT_NOT_AUTHENTICATED",
            "MT4_TERMINAL_EXECUTION_NOT_VERIFIED",
            "BROKER_ACCOUNT_TYPE_NOT_AUTHENTICATED",
        ] + ([] if static["static_contract_passed"] else [
            "MQL4_SOURCE_CONTRACT_FAILED"])),
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline source-linked MetaEditor evidence")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir() or
                not a.manifest.is_file() or
                not 0 < a.manifest.stat().st_size <= MAX_BYTES or
                not a.source.is_file() or a.source.stat().st_size > 50000):
            raise InputError("invalid or colliding input/output")
        raw = json.loads(a.manifest.read_text(encoding="utf-8-sig"))
        result = inspect(raw, a.source.read_bytes())
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": result["status"],
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False}))
        return 0
    except (InputError, ValueError, TypeError, OSError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "METAEDITOR_EVIDENCE_UNVERIFIED",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
