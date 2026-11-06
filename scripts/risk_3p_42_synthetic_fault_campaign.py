"""Reproducible purely fictional P05 fault-injection campaign.

No broker access, account IDs, external files or real timer/clock input.
All expected failures are synthetic, never evidence of real-world safety.
"""
from __future__ import annotations

import copy

from scripts import risk_3p_40_synthetic_p05_interlock_matrix as gate

# IDs are deliberately stable for PR review and regression tracking.
FAULTS = (
    ("P42-01", "P40_IDENTITY_SIMULATION_BLOCKED",
     lambda p: p["account_identity"]["terminal"].update(
         account_alias="SIM_WRONG_ACCOUNT")),
    ("P42-02", "P40_IDENTITY_SIMULATION_BLOCKED",
     lambda p: p["account_identity"]["mock_server"].update(
         session_alias="SIM_PARALLEL_SESSION")),
    ("P42-03", "P40_IDENTITY_SIMULATION_BLOCKED",
     lambda p: p["account_identity"]["terminal"].update(
         account_class="SIM_LIVE")),
    ("P42-04", "P40_EA_SIMULATION_BLOCKED",
     lambda p: p["ea_no_interference"]["simulation"].update(
         autotrading_display="SIM_ON_LIKE")),
    ("P42-05", "P40_EA_SIMULATION_BLOCKED",
     lambda p: p["ea_no_interference"]["simulation"].update(
         ea_execution_proven=True)),
    ("P42-06", "P40_EA_SIMULATION_BLOCKED",
     lambda p: p["ea_no_interference"]["simulation"].update(
         proposed_interaction="SIM_START_SCRIPT")),
    ("P42-07", "P40_ORDERS_SIMULATION_BLOCKED",
     lambda p: p["orders"]["server"]["rows"][3].update(
         open_positions=2)),
    ("P42-08", "P40_ORDERS_SIMULATION_BLOCKED",
     lambda p: p["orders"]["server"]["rows"][0].update(
         pending_orders=1)),
    ("P42-09", "P40_ORDERS_SIMULATION_BLOCKED",
     lambda p: p["orders"].update(server=None)),
    ("P42-10", "P40_ORDERS_SIMULATION_BLOCKED",
     lambda p: p["orders"]["terminal"].update(
         coverage="SIM_TRADE_TAB_BALANCE_ONLY")),
    ("P42-11", "P40_ORDERS_SIMULATION_BLOCKED",
     lambda p: p["orders"]["server"].update(
         asof_utc="SIM_2000-01-01T00:00:31Z")),
    ("P42-12", "P40_ORDERS_SIMULATION_BLOCKED",
     lambda p: p["orders"]["terminal"]["rows"].pop()),
    ("P42-13", "P40_RUNTIME_OR_P05_APPROVAL_FORGED",
     lambda p: p["safety"].update(runtime_go_no_go="GO")),
    ("P42-14", "P40_RUNTIME_OR_P05_APPROVAL_FORGED",
     lambda p: p["safety"].update(p05_passed=8)),
    ("P42-15", "P40_INVALID_OR_SECRET_FIELDS",
     lambda p: p.update(
         account_number="PRIVATE_ACCOUNT_IDENTIFIER_NOT_TO_LEAK")),
    ("P42-16", "P40_RUNTIME_OR_P05_APPROVAL_FORGED",
     lambda p: p["safety"].update(
         real_mt4_access_authorized=True)),
)


def campaign() -> dict:
    errors = []
    for exposure in (False, True):
        baseline = gate.evaluate(
            gate.fixture(simulated_exposure=exposure))
        if (baseline["status"] != "PASS_SYNTHETIC_MATRIX_ONLY"
                or baseline["real_p05_passed"] != 0
                or baseline["runtime_go_no_go"] != "NO_GO"
                or baseline["safety_hold_latched"] is not True):
            errors.append("P42_BAD_FICTIONAL_BASELINE")
    for fault_id, expected, mutation in FAULTS:
        package = copy.deepcopy(gate.fixture())
        mutation(package)
        result = gate.evaluate(package)
        if (result["status"] != "FAIL_CLOSED"
                or expected not in result["errors"]
                or result["real_p05_passed"] != 0
                or result["real_mt4_read_authorized"] is not False
                or result["runtime_go_no_go"] != "NO_GO"
                or result["safety_hold_latched"] is not True):
            errors.append("P42_FAULT_NOT_BLOCKED:" + fault_id)
    return {
        "status": "PASS_SYNTHETIC_FAULT_CAMPAIGN_ONLY"
        if not errors else "FAIL_CLOSED",
        "simulated_baselines": 2,
        "simulated_faults_exercised": len(FAULTS),
        "real_p05_checks_passed": 0,
        "real_g1_fields_verified": 0,
        "real_mt4_access_authorized": False,
        "order_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
