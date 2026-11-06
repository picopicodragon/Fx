"""Cross-document G1 3x5 blank provenance alignment, without real observation.

Check the *identity and ordering* of all 15 source/handoff pairs, which a
simple verified-count check could miss. Never imports any broker data or
grants acceptance; reads repository specifications only.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = "specs/risk_3p_33_p05_07_offline_provenance_readiness_20261106.json"
HANDOFF = "specs/risk_3p_53_54_future_evidence_handoff_20261106.json"
DEBT = "specs/risk_3p_46_48_offline_acceptance_debt_20261106.json"
P05_DAG = "specs/risk_3p_59_p05_dependency_dag_20261106.json"
FILES = (G1, HANDOFF, DEBT, P05_DAG)
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
FIELDS = ("min_lot", "lot_step", "point_quote", "tick_size_points",
          "tick_value_deposit_currency")
SOURCE_ROW_KEYS = ("pair", "field", "value", "unit", "terminal_symbol",
                   "observed_at_utc", "primary_source_ref",
                   "independent_source_ref", "reviewer_ref", "status")
HANDOFF_ROW_KEYS = ("pair", "field", "real_broker_value",
                    "real_observation_utc", "real_primary_source_ref",
                    "real_independent_source_ref", "unit", "verified")
SOURCE_NULL = ("value", "unit", "terminal_symbol", "observed_at_utc",
               "primary_source_ref", "independent_source_ref", "reviewer_ref")
HANDOFF_NULL = ("real_broker_value", "real_observation_utc",
                "real_primary_source_ref", "real_independent_source_ref", "unit")


def _read(root: Path, name: str):
    return json.loads((root / name).read_text(encoding="utf-8"))


def audit(root: Path = ROOT, injected: dict | None = None) -> list[str]:
    errors = []
    try:
        docs = injected if injected is not None else {
            name: _read(root, name) for name in FILES
        }
        original, handoff, debt, dag = (docs[name] for name in FILES)
        if any(type(x) is not dict for x in
               (original, handoff, debt, dag)):
            return ["P63_MISSING_OR_MALFORMED_PUBLIC_SPEC"]
        if (original.get("target_pairs") != list(PAIRS)
                or original.get("required_fields") != list(FIELDS)
                or original.get("required_items") != 15
                or original.get("safety", {}).get(
                    "independently_verified_g1_items") != 0):
            errors.append("P63_SOURCE_G1_SCOPE_DRIFT")
        if (handoff.get("permission", {}).get(
                    "g1_fifteen_fields_verified") != 0
                or handoff.get("permission", {}).get(
                    "runtime_go_no_go") != "NO_GO"
                or handoff.get("permission", {}).get(
                    "real_mt4_session_read_authorized") is not False):
            errors.append("P63_HANDOFF_REAL_EVIDENCE_FORGED")
        if (debt.get("safety", {}).get("g1_real_verified") != 0
                or debt.get("safety", {}).get("p05_passed") != 0
                or debt.get("safety", {}).get(
                    "safety_hold_latched") is not True
                or dag.get("state", {}).get("g1_real_verified") != 0
                or dag.get("state", {}).get("p05_passed") != 0):
            errors.append("P63_CROSS_DOCUMENT_APPROVAL_DRIFT")
        oldrows, newrows = original.get("g1_entries"), handoff.get("g1_rows")
        if (type(oldrows) is not list or len(oldrows) != 15
                or type(newrows) is not list or len(newrows) != 15):
            errors.append("P63_EXPECTED_BOTH_FIFTEEN_ROWS")
        else:
            for i, (pair, field) in enumerate(
                    (p, f) for p in PAIRS for f in FIELDS):
                number = str(i + 1)
                a, b = oldrows[i], newrows[i]
                if (type(a) is not dict or set(a) != set(SOURCE_ROW_KEYS)
                        or a.get("pair") != pair or a.get("field") != field
                        or a.get("status") !=
                        "UNVERIFIED_NO_TERMINAL_EVIDENCE"
                        or any(a.get(key, "MISSING") is not None
                               for key in SOURCE_NULL)):
                    errors.append("P63_SOURCE_ITEM_FAKE_OR_MISORDERED:" + number)
                if (type(b) is not dict or set(b) != set(HANDOFF_ROW_KEYS)
                        or b.get("pair") != pair or b.get("field") != field
                        or b.get("verified") is not False
                        or any(b.get(key, "MISSING") is not None
                               for key in HANDOFF_NULL)):
                    errors.append("P63_HANDOFF_ITEM_FAKE_OR_MISORDERED:" + number)
    except (OSError, TypeError, KeyError, AttributeError, ValueError,
            IndexError):
        errors.append("P63_OFFLINE_SOURCE_READ_FAILURE")
    return errors


def snapshot(root: Path = ROOT, injected: dict | None = None) -> dict:
    errors = audit(root, injected)
    return {
        "status": "PASS_BLANK_G1_LEDGER_ALIGNMENT_ONLY"
        if not errors else "FAIL_CLOSED",
        "required_real_g1_rows": 15,
        "real_g1_verified": 0,
        "p05_real_accepted": 0,
        "real_broker_sources_confirmed": False,
        "human_p05_signoff": False,
        "real_mt4_access_authorized": False,
        "real_order_or_ea_action_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2))
