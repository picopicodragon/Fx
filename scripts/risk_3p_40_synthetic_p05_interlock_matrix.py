"""Compose P05 simulated identity, EA and order checks without granting P05.

Pure in-memory synthetic test double orchestration. No actual MT4 or network.
"""
from __future__ import annotations

from scripts import risk_3p_36_synthetic_order_reconciliation as orders
from scripts import risk_3p_38_synthetic_session_identity as identity
from scripts import risk_3p_39_synthetic_ea_no_interference as ea

KEYS = ("classification", "stage", "account_identity",
        "ea_no_interference", "orders", "safety")
EXPECTED_SAFETY = {
    "p05_all_eight_accepted": False,
    "p05_passed": 0,
    "account_identity_verified": False,
    "single_session_verified": False,
    "ea_runtime_verified": False,
    "server_order_reconciled": False,
    "read_only_non_interference_proven": False,
    "storage_acl_independently_verified": False,
    "g1_15_fields_verified": False,
    "human_p05_08_signoff": False,
    "real_mt4_access_authorized": False,
    "orders_authorized": False,
    "stop_release_authorized": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}


def fixture(*, simulated_exposure: bool = False) -> dict:
    return {
        "classification": "SYNTHETIC_P05_INTERLOCKS_NOT_REAL_PROOF",
        "stage": "OFFLINE_DESIGN_VALIDATION_ONLY",
        "account_identity": identity.fixture(),
        "ea_no_interference": ea.fixture(),
        "orders": orders.make_fixture(exposure=simulated_exposure),
        "safety": dict(EXPECTED_SAFETY),
    }


def evaluate(package: object) -> dict:
    errors = []
    if type(package) is not dict or set(package) != set(KEYS):
        errors.append("P40_INVALID_OR_SECRET_FIELDS")
    else:
        if (package["classification"] !=
                "SYNTHETIC_P05_INTERLOCKS_NOT_REAL_PROOF"
                or package["stage"] != "OFFLINE_DESIGN_VALIDATION_ONLY"):
            errors.append("P40_SYNTHETIC_SCOPE_PROMOTED")
        if package["safety"] != EXPECTED_SAFETY:
            errors.append("P40_RUNTIME_OR_P05_APPROVAL_FORGED")
        scenarios = (
            ("identity", identity.evaluate(package["account_identity"]),
             "PASS_SIMULATED_IDENTIFIERS_ONLY"),
            ("ea", ea.evaluate(package["ea_no_interference"]),
             "PASS_OFFLINE_NON_INTERFERENCE_PLAN_ONLY"),
            ("orders", orders.evaluate_synthetic_reconciliation(
                package["orders"]), "PASS_OFFLINE_SYNTHETIC_ONLY"),
        )
        for label, result, expected in scenarios:
            if result["status"] != expected or result["runtime_go_no_go"] != "NO_GO":
                errors.append("P40_" + label.upper() + "_SIMULATION_BLOCKED")
            if result["safety_hold_latched"] is not True:
                errors.append("P40_" + label.upper() + "_SAFETY_HOLD_LOST")
    return {
        "status": "PASS_SYNTHETIC_MATRIX_ONLY" if not errors
        else "FAIL_CLOSED",
        "simulated_checks_integrated": 3,
        "real_p05_passed": 0,
        "real_g1_fields_verified": 0,
        "real_broker_orders_absent_verified": False,
        "human_p05_08_signoff": False,
        "real_mt4_read_authorized": False,
        "broker_order_or_ea_action_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
