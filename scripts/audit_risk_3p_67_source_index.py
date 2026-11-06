"""Exact source inventory cross-check for Q109 synthetic-only modules.

Both inputs are public repository planning records. This detects accidental
source omission, not tampering if an attacker rewrites both records. No live
account, broker, network, private file, real approval or automatic merge.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE = "specs/traceability.json"
PINNED = "specs/risk_3p_67_pinned_offline_source_index_20261106.json"
EXPECTED_SAFETY = {
    "real_mt4_access_authorized": False,
    "main_auto_merge_authorized": False,
    "production_approval_granted": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}
PIN_FIELDS = ("schema_version", "classification", "scope", "sources", "safety")


def _read(root: Path, name: str):
    return json.loads((root / name).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors = []
    try:
        docs = injected if injected is not None else {
            p: _read(root, p) for p in (TRACE, PINN)}
        trace, index = docs[TRACE], docs[PINN]
        if type(trace) is not dict or type(index) is not dict:
            return ["P67_SOURCE_INDEX_OR_TRACE_INVALID"]
        if (set(index) != set(PIN_FIELDS)
                or type(index.get("schema_version")) is not int
                or index["schema_version"] != 1
                or index["classification"] !=
                "OFFLINE_SOURCE_INDEX_NOT_PRODUCTION_APPROVAL"
                or index["scope"] != "RISK-3P-67-72"):
            errors.append("P67_PINNED_INDEX_SCOPE_CHANGED")
        if index.get("safety") != EXPECTED_SAFETY:
            errors.append("P67_REAL_PERMISSION_OR_MERGE_FORGED")
        sources = index.get("sources")
        mappings = trace.get("offline_synthetic_mappings")
        if (type(sources) is not list or len(sources) != 45
                or any(type(x) is not str for x in sources)
                or sources != sorted(set(sources))):
            errors.append("P67_EXPECTED_45_UNIQUE_SOURCE_NAMES")
        if (type(mappings) is not list or len(mappings) != 45
                or any(type(row) is not dict
                       or set(row) != {"source", "spec_ids", "tests",
                                       "production_authorized"}
                       or type(row.get("source")) is not str
                       or row.get("production_authorized") is not False
                       for row in mappings)):
            errors.append("P67_TRACEABILITY_ROWS_NOT_OFFLINE")
        elif type(sources) is list:
            current = [row["source"] for row in mappings]
            if len(set(current)) != len(current) or sorted(current) != sources:
                errors.append("P67_OMITTED_OR_UNREVIEWED_SOURCE_MAPPING")
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        errors.append("P67_PUBLIC_INDEX_READ_OR_SCHEMA_FAILURE")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_PINNED_OFFLINE_INVENTORY_ONLY"
        if not errors else "FAIL_CLOSED",
        "expected_offline_sources": 45,
        "real_source_authenticity_verified": False,
        "production_approval_recorded": False,
        "p05_passed": 0, "g1_real_verified": 0,
        "real_mt4_access_authorized": False,
        "main_auto_merge_authorized": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
