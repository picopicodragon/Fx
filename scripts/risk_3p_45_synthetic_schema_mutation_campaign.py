"""Deterministic adversarial in-memory inputs against offline safety contracts.

Never loads real account data, private paths, MT4 or logs. Error messages never
include submitted values. Baselines are deliberately fictional.
"""
from __future__ import annotations

import copy

from scripts import validate_risk_3p_34_synthetic_provenance as p34
from scripts import risk_3p_36_synthetic_order_reconciliation as p36
from scripts import risk_3p_38_synthetic_session_identity as p38
from scripts import risk_3p_39_synthetic_ea_no_interference as p39
from scripts import risk_3p_40_synthetic_p05_interlock_matrix as p40
from scripts import risk_3p_43_synthetic_state_transition as p43
from scripts import risk_3p_44_synthetic_safety_latch as p44

CANARY = "SENSITIVE_CANARY_PAYLOAD_45"
CONTRACTS = (
    ("P34", p34.make_synthetic_fixture, p34.check_synthetic_package),
    ("P36", p36.make_fixture, p36.evaluate_synthetic_reconciliation),
    ("P38", p38.fixture, p38.evaluate),
    ("P39", p39.fixture, p39.evaluate),
    ("P40", p40.fixture, p40.evaluate),
    ("P43", p43.fixture, p43.evaluate),
    ("P44", p44.fixture, p44.evaluate),
)
FAULT_IDS = (
    "DROP_CLASSIFICATION", "UNKNOWN_SENSITIVE_FIELD", "REAL_SCOPE_SPOOF",
    "FORGED_RUNTIME_GO", "SAFETY_KEY_INJECTION", "WRONG_ROOT_TYPE",
)


def _mutation(doc: dict, fault: str) -> object:
    if fault == "WRONG_ROOT_TYPE":
        return [doc, {"private": CANARY}]
    result = copy.deepcopy(doc)
    if fault == "DROP_CLASSIFICATION":
        result.pop("classification")
    elif fault == "UNKNOWN_SENSITIVE_FIELD":
        result["private_account_id"] = CANARY
    elif fault == "REAL_SCOPE_SPOOF":
        result["classification"] = "REAL_BROKER_CONFIRMED"
    elif fault == "FORGED_RUNTIME_GO":
        # P34 stores safety flags at the root. Other offline contracts
        # keep them in a nested safety object; both must fail closed.
        target = result["safety"] if "safety" in result else result
        target["runtime_go_no_go"] = "GO"
    elif fault == "SAFETY_KEY_INJECTION":
        target = result["safety"] if "safety" in result else result
        target["broker_secret"] = CANARY
    else:
        raise ValueError("unknown synthetic fault")
    return result


def campaign() -> dict:
    errors: list[str] = []
    for name, factory, evaluate in CONTRACTS:
        initial = factory()
        try:
            baseline = evaluate(copy.deepcopy(initial))
        except (KeyError, TypeError, ValueError, IndexError,
                AttributeError, OverflowError):
            errors.append("P45_BASELINE_CRASH:" + name)
            continue
        if (not baseline["status"].startswith("PASS_")
                or baseline["runtime_go_no_go"] != "NO_GO"
                or baseline["safety_hold_latched"] is not True):
            errors.append("P45_BASELINE_NOT_SAFE:" + name)
        for fault in FAULT_IDS:
            try:
                mutated = _mutation(initial, fault)
                result = evaluate(mutated)
                if (result["status"] != "FAIL_CLOSED"
                        or result["runtime_go_no_go"] != "NO_GO"
                        or result["safety_hold_latched"] is not True):
                    errors.append("P45_UNSAFE_MUTATION:" + name + ":" + fault)
                if CANARY in str(result):
                    errors.append("P45_PRIVATE_VALUE_LEAK:" + name + ":" + fault)
            except (KeyError, TypeError, ValueError, IndexError,
                    AttributeError, OverflowError):
                errors.append("P45_MUTATION_CRASH:" + name + ":" + fault)
    return {
        "status": "PASS_OFFLINE_MUTATION_CAMPAIGN_ONLY"
        if not errors else "FAIL_CLOSED",
        "synthetic_contracts": len(CONTRACTS),
        "synthetic_fault_kinds": len(FAULT_IDS),
        "synthetic_cases": len(CONTRACTS) * len(FAULT_IDS),
        "real_broker_safety_verified": False,
        "actual_p05_items_passed": 0,
        "real_mt4_session_authorized": False,
        "order_or_ea_operation_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
