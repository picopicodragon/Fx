"""RISK-3P-02: static migration inventory, not a broker or trading check.

Read-only, repo-local audit. Old four-pair evidence and local user archives are
not rewritten. No authority to change acceptance, connect MT4, or trade.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "specs/risk_3p_02_transition_impact_20261104.json"
TARGET = ("USD/JPY", "EUR/JPY", "EUR/USD")
HISTORY = ("USD/JPY", "EUR/JPY", "GBP/USD", "AUD/USD")
LEGACY_RE = re.compile(r"\b(?:GBP/USD|AUD/USD|GBPUSD|AUDUSD)\b")
IGNORED_SELF = "scripts/audit_risk_3p_02_migration.py"


def load(root: Path) -> dict:
    return json.loads((root / REGISTRY).read_text(encoding="utf-8"))


def _synthetic_pairs(root: Path) -> object:
    """Inspect source as data; never execute the synthetic module."""
    tree = ast.parse(
        (root / "scripts/phase1_three_pair_synthetic_risk.py")
        .read_text(encoding="utf-8"))
    for statement in tree.body:
        if (isinstance(statement, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "PAIRS"
                        for t in statement.targets)):
            return ast.literal_eval(statement.value)
    return None


def audit(root: Path, document: object = None) -> list[str]:
    errors: list[str] = []
    try:
        d = load(root) if document is None else document
        if type(d) is not dict:
            return ["INVALID_REGISTRY"]
        if d.get("schema_version") != 1 or d.get("id") != "RISK-3P-02-TRANSITION-IMPACT-20261104":
            errors.append("INVALID_REGISTRY_ID")
        if d.get("scope") != "DESIGN_IMPACT_ANALYSIS_ONLY":
            errors.append("UNAUTHORIZED_SCOPE")
        if d.get("target_pairs") != list(TARGET):
            errors.append("TARGET_PAIRS_NOT_3P")
        if d.get("historical_q3_pairs") != list(HISTORY):
            errors.append("HISTORICAL_Q3_CHANGED")
        if d.get("legacy_exclusions") != ["GBP/USD", "AUD/USD"]:
            errors.append("LEGACY_EXCLUSIONS_CHANGED")
        if d.get("target_g1_attribute_count") != 15 or d.get("historical_g1_attribute_count") != 20:
            errors.append("G1_SCOPE_COUNTS_CHANGED")
        if (d.get("target_g1_status") != "OWNER_APPROVED_FORMAL_SCOPE_UNVERIFIED_NOT_G1_ACCEPTANCE"
                or d.get("status") != "INVENTORIED_NOT_MIGRATED"):
            errors.append("FALSE_MIGRATION_ACCEPTANCE")
        if (any(d.get(k) is not False for k in (
                "implementation_authorized", "production_authorized",
                "broker_connection_authorized", "stop_release_authorized"))
                or d.get("verified_values", "INVALID") is not None
                or d.get("phase_1") != "BLOCKED"
                or d.get("runtime_go_no_go") != "NO_GO"
                or d.get("safety_hold_latched") is not True):
            errors.append("SAFETY_STATE_PROMOTED")
        entries = d.get("inventory")
        if type(entries) is not list or not entries:
            return errors + ["INVENTORY_MISSING"]
        names: set[str] = set()
        for row in entries:
            if (type(row) is not dict or
                    any(type(row.get(k)) is not str or not row[k]
                        for k in ("path", "category", "next_action", "finding"))):
                errors.append("INVENTORY_ROW_INVALID")
                continue
            path = row["path"]
            if path in names or path.startswith("/") or ".." in Path(path).parts:
                errors.append("INVENTORY_DUPLICATE_OR_UNSAFE_PATH")
            names.add(path)
            if not (root / path).is_file():
                errors.append("INVENTORY_FILE_MISSING:" + path)
        legacy = d.get("legacy_code_paths")
        if (type(legacy) is not list or not legacy or
                len(legacy) != len(set(legacy)) or
                any(type(p) is not str or p not in names for p in legacy)):
            return errors + ["LEGACY_CODE_INVENTORY_INVALID"]
        inventory_by_name = {row["path"]: row for row in entries
                             if type(row) is dict and type(row.get("path")) is str}
        for p in legacy:
            row = inventory_by_name[p]
            if row["category"] != "LEGACY_4P_CODE" or row["next_action"] not in (
                    "VERSION_REQUIRED", "SEPARATE_AUTHORIZATION_REQUIRED"):
                errors.append("LEGACY_CODE_MISCLASSIFIED:" + p)
        actual: set[str] = set()
        for base, pattern in (("scripts", "*.py"), ("mt4", "*.mq4")):
            folder = root / base
            if folder.is_dir():
                for file in folder.rglob(pattern):
                    relative = file.relative_to(root).as_posix()
                    if relative != IGNORED_SELF and LEGACY_RE.search(
                            file.read_text(encoding="utf-8")):
                        actual.add(relative)
        for p in sorted(actual - set(legacy)):
            errors.append("UNREGISTERED_LEGACY_4P_CODE:" + p)
        for p in sorted(set(legacy) - actual):
            # Some helpers inherit 4P through imports rather than containing
            # literal symbols. They must still stay inventoried.
            if p not in {"scripts/mt4_manual_symbol_v2.py"}:
                errors.append("LEGACY_CODE_REFERENCE_NOT_FOUND:" + p)

        if tuple(_synthetic_pairs(root)) != TARGET:
            errors.append("SYNTHETIC_TARGET_DRIFT")
        gap = json.loads((root / "specs/p0_01_d5_25_gap_verification_matrix.json")
                         .read_text(encoding="utf-8"))
        g1 = next(x for x in gap["gaps"] if x["id"] == "G1")
        if (g1["implementation_status"] != "UNRESOLVED"
                or g1["release_blocker"] is not True
                or g1["real_world_verified"] is not False
                or "3通貨ペア×5主要契約属性" not in g1["subject"]):
            errors.append("FORMAL_G1_SCOPE_OR_NO_GO_DRIFT")
        from scripts.audit_risk_3p_28_owner_g1_scope import audit as audit_scope
        if audit_scope(root):
            errors.append("G1_SCOPE_APPROVAL_OR_HISTORY_CORRUPTED")
        trace = json.loads((root / "specs/traceability.json")
                           .read_text(encoding="utf-8"))
        m = [x for x in trace["offline_synthetic_mappings"]
             if x["source"] == "scripts/phase1_three_pair_synthetic_risk.py"]
        if (len(m) != 1 or m[0]["production_authorized"] is not False
                or m[0]["tests"] != [
                    "tests/test_phase1_three_pair_synthetic_risk.py",
                    "tests/test_risk_3p_79_84_numeric_boundaries.py",
                    "tests/test_risk_3p_91_96_decimal_context_isolation.py",
                    "tests/test_risk_3p_97_102_fraction_oracle.py",
                    "tests/test_risk_3p_103_108_loss_handoff_binding.py",
                    "tests/test_risk_3p_109_114_exposure_exactness.py",
                    "tests/test_risk_3p_115_120_malformed_handoff_objects.py",
                    "tests/test_risk_3p_121_126_mock_map_key_guard.py",
                ]):
            errors.append("THREE_PAIR_SYNTHETIC_PRODUCTION_PROMOTED")
    except (OSError, ValueError, KeyError, TypeError, SyntaxError,
            StopIteration, AttributeError) as exc:
        errors.append("MIGRATION_AUDIT_DATA_INVALID:" + type(exc).__name__)
    return errors


def main() -> None:
    errors = audit(ROOT)
    if errors:
        raise SystemExit("RISK-3P-02 static audit FAILED:\n" +
                         "\n".join("- " + x for x in errors))
    data = load(ROOT)
    print("RISK-3P-02: PASS (design inventory only, no migration or trading authorization)")
    print("TARGET 3: " + ", ".join(data["target_pairs"]))
    print("LEGACY_4P_CODE_REQUIRES_MIGRATION: " +
          str(len(data["legacy_code_paths"])))
    print("INVENTORY_FILES: " + str(len(data["inventory"])))
    print("G1 3x5: OWNER-APPROVED FORMAL REVIEW SCOPE, 0/15 VERIFIED; historic 4x5 archived")
    print("PHASE-1 BLOCKED | runtime NO_GO | safety_hold_latched=true")


if __name__ == "__main__":
    main()
