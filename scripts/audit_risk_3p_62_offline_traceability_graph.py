"""Q109 audit of tracked mock-only sources and test references.

Only files inside this public repository are read. Does not execute sources,
resolve broker evidence, authenticate signatures, or grant phase acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
TRACE = "specs/traceability.json"
FIELDS = ("source", "spec_ids", "tests", "production_authorized")
REQUIRED_NEW = frozenset((
    "scripts/risk_3p_61_strict_offline_result_contract.py",
    "scripts/audit_risk_3p_62_offline_traceability_graph.py",
    "scripts/audit_risk_3p_63_g1_ledger_alignment.py",
    "scripts/risk_3p_64_adversarial_consistency_campaign.py",
    "scripts/risk_3p_65_integrated_offline_audit.py",
))


def _safe(path: object, folder: str) -> bool:
    if type(path) is not str or "\\" in path or len(path) > 150:
        return False
    parsed = PurePosixPath(path)
    if (parsed.is_absolute() or len(parsed.parts) != 2
            or parsed.parts[0] != folder or
            not parsed.name.endswith(".py") or
            not parsed.name.replace("_", "").replace(".", "").isalnum()):
        return False
    if folder == "tests" and not parsed.name.startswith("test_"):
        return False
    return True


def audit(root: Path = ROOT, data: object = None) -> list[str]:
    errors = []
    try:
        record = (data if data is not None else
                  json.loads((root / TRACE).read_text(encoding="utf-8")))
        if type(record) is not dict or type(
                record.get("offline_synthetic_mappings")) is not list:
            return ["P62_INVALID_TRACEABILITY_MANIFEST"]
        rows = record["offline_synthetic_mappings"]
        seen = set()
        for i, row in enumerate(rows, 1):
            idx = str(i)
            if type(row) is not dict or set(row) != set(FIELDS):
                errors.append("P62_SCHEMA_OR_SECRET_FIELD:" + idx)
                continue
            source = row.get("source")
            if not _safe(source, "scripts"):
                errors.append("P62_UNSAFE_SOURCE_PATH:" + idx)
                continue
            if source in seen:
                errors.append("P62_DUPLICATE_SOURCE_MAPPING:" + idx)
            seen.add(source)
            if row["production_authorized"] is not False:
                errors.append("P62_MOCK_ONLY_RUNTIME_PERMISSION:" + idx)
            ids = row["spec_ids"]
            if (type(ids) is not list or not ids
                    or any(type(x) is not str or not x or len(x) > 30
                           or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
                                  for c in x)
                           for x in ids)
                    or len(ids) != len(set(ids))):
                errors.append("P62_INVALID_SPEC_TRACE:" + idx)
            tests = row["tests"]
            if (type(tests) is not list or not tests
                    or any(not _safe(x, "tests") for x in tests)
                    or len(tests) != len(set(tests))):
                errors.append("P62_INVALID_TEST_PATH:" + idx)
                continue
            if not (root / source).is_file() or any(
                    not (root / test).is_file() for test in tests):
                errors.append("P62_SOURCE_OR_TEST_MISSING:" + idx)
        if not REQUIRED_NEW.issubset(seen):
            errors.append("P62_NEW_SAFETY_SOURCES_UNTRACKED")
        if len(rows) != len(seen):
            errors.append("P62_INCOMPLETE_OR_DUPLICATE_MAPPING")
        if len(rows) < 41:
            errors.append("P62_EXPECTED_PRIOR_MAPPINGS_MISSING")
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        errors.append("P62_CANNOT_READ_PUBLIC_TRACEABILITY")
    return errors


def snapshot(root: Path = ROOT, data: object = None) -> dict:
    errors = audit(root, data)
    return {
        "status": "PASS_OFFLINE_Q109_LINKS_ONLY" if not errors
        else "FAIL_CLOSED",
        "minimum_tracked_synthetic_sources": 41,
        "all_sources_production_authorized": False,
        "runtime_dependency_closure_verified": False,
        "real_evidence_or_signoff_verified": False,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "real_mt4_read_authorized": False,
        "order_execution_authorized": False,
        "main_auto_merge_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
