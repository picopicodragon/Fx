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


def _plain_keys(record: object) -> bool:
    """Reject unknown key comparison hooks before any set, get or lookup."""
    return type(record) is dict and all(type(key) is str for key in record)


def _safety_matches(safety: object) -> bool:
    if not _plain_keys(safety) or set(safety) != set(EXPECTED_SAFETY):
        return False
    return all(type(safety[name]) is type(expected)
               and safety[name] == expected
               for name, expected in EXPECTED_SAFETY.items())


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors: list[str] = []
    try:
        docs = injected if injected is not None else {
            p: _read(root, p) for p in (TRACE, PINNED)}
        if not _plain_keys(docs):
            return ["P67_SOURCE_INDEX_OR_TRACE_INVALID"]
        trace, index = docs[TRACE], docs[PINNED]
        if not _plain_keys(trace) or not _plain_keys(index):
            return ["P67_SOURCE_INDEX_OR_TRACE_INVALID"]

        if (set(index) != set(PIN_FIELDS)
                or type(index.get("schema_version")) is not int
                or index["schema_version"] != 1
                or type(index.get("classification")) is not str
                or index["classification"] !=
                "OFFLINE_SOURCE_INDEX_NOT_PRODUCTION_APPROVAL"
                or type(index.get("scope")) is not str
                or index["scope"] != "RISK-3P-67-72"):
            errors.append("P67_PINNED_INDEX_SCOPE_CHANGED")

        if not _safety_matches(index.get("safety")):
            errors.append("P67_REAL_PERMISSION_OR_MERGE_FORGED")

        sources = index.get("sources")
        mappings = trace.get("offline_synthetic_mappings")
        if (type(sources) is not list or len(sources) != 45
                or any(type(x) is not str for x in sources)
                or sources != sorted(set(sources))):
            errors.append("P67_EXPECTED_45_UNIQUE_SOURCE_NAMES")
        if (type(mappings) is not list or len(mappings) != 45
                or any(not _plain_keys(row)
                       or set(row) != {"source", "spec_ids", "tests",
                                       "production_authorized"}
                       or type(row.get("source")) is not str
                       or row.get("production_authorized") is not False
                       for row in mappings)):
            errors.append("P67_TRACEABILITY_ROWS_NOT_OFFLINE")
        elif type(sources) is list and all(type(x) is str for x in sources):
            current = [row["source"] for row in mappings]
            if len(set(current)) != len(current) or sorted(current) != sources:
                errors.append("P67_OMITTED_OR_UNREVIEWED_SOURCE_MAPPING")
    except Exception:
        # Untrusted synthetic records can raise arbitrary Python exceptions.
        # Never expose exception text or a partial source mapping.
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
