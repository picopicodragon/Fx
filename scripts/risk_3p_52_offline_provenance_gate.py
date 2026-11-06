"""Compose synthetic provenance, witness, PR-consent and prior P05 QA checks.

This is only an offline integration test. It has no authority to approve P05,
read MT4 data, authenticate a broker, or change orders.
"""
from __future__ import annotations

from pathlib import Path

from scripts import risk_3p_49_synthetic_evidence_chain as chain
from scripts import risk_3p_50_synthetic_dual_witness as witness
from scripts import risk_3p_51_mock_approval_separation as approval
from scripts import risk_3p_47_48_offline_quality_gate as prior

ROOT = Path(__file__).resolve().parents[1]
CASE_NAMES = ("simulated_chain", "simulated_dual_witness",
              "unsigned_owner_review", "existing_p05_quality_gate")
EXPECTED = (
    "PASS_SYNTHETIC_HASH_CHAIN_ONLY",
    "PASS_TWO_FAKE_WITNESSES_ONLY",
    "PASS_NO_REAL_APPROVAL_ONLY",
    "PASS_OFFLINE_QUALITY_GATE_ONLY",
)
REQUIRED_FALSE = (
    "broker_origin_verified", "actual_source_independence_verified",
    "human_approval_verified", "owner_p05_approval_recorded",
    "real_mt4_read_authorized", "real_order_execution_authorized",
    "order_action_authorized", "orders_authorized",
    "cryptographic_authenticity_verified", "real_account_data_collected",
)
REQUIRED_ZERO = (
    "p05_passed", "g1_verified", "actual_broker_fields_verified",
    "g1_real_verified", "real_p05_passed",
)


def _results(root: Path):
    return (
        chain.evaluate(chain.fixture()),
        witness.evaluate(witness.fixture()),
        approval.evaluate(approval.fixture()),
        prior.evaluate(root),
    )


def evaluate(root: Path = ROOT, *, injected: dict | None = None) -> dict:
    errors = []
    outputs = _results(root)
    for i, (name, status, raw) in enumerate(
            zip(CASE_NAMES, EXPECTED, outputs), 1):
        result = injected.get(name, raw) if type(injected) is dict else raw
        if (type(result) is not dict or result.get("status") != status
                or result.get("errors") != []
                or result.get("runtime_go_no_go") != "NO_GO"
                or result.get("safety_hold_latched") is not True):
            errors.append("P52_COMPOSITE_RESULT_UNTRUSTED:" + str(i))
            continue
        if any(key in result and result[key] is not False
               for key in REQUIRED_FALSE):
            errors.append("P52_REAL_WORLD_AUTHORITY_FABRICATED:" + str(i))
        if any(key in result and
               (type(result[key]) is not int or result[key] != 0)
               for key in REQUIRED_ZERO):
            errors.append("P52_P05_OR_G1_VALUES_FAKE_ACCEPTED:" + str(i))
    if injected is not None and (type(injected) is not dict
                                 or set(injected) - set(CASE_NAMES)):
        errors.append("P52_INJECTED_UNKNOWN_OR_SENSITIVE_CASE")
    return {
        "status": "PASS_OFFLINE_PROVENANCE_QA_ONLY" if not errors
        else "FAIL_CLOSED",
        "offline_modules_checked": len(CASE_NAMES),
        "real_broker_evidence_verified": False,
        "independent_source_authenticity_verified": False,
        "trusted_timestamp_verified": False,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "real_owner_authorization_recorded": False,
        "real_mt4_read_authorized": False,
        "real_order_execution_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
