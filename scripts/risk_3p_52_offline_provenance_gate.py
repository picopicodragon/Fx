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


def _plain_keys(value: object) -> bool:
    """Never hash/compare injected keys before checking their exact types."""
    return type(value) is dict and all(type(k) is str for k in value)


def evaluate(root: Path = ROOT, *, injected: dict | None = None) -> dict:
    errors: list[str] = []
    if injected is not None:
        if not _plain_keys(injected) or set(injected) - set(CASE_NAMES):
            errors.append("P52_INJECTED_UNKNOWN_OR_SENSITIVE_CASE")
    if not errors:
        try:
            outputs = _results(root)
            if type(outputs) not in (tuple, list) or len(outputs) != len(CASE_NAMES):
                errors.append("P52_OFFLINE_CHILD_EVALUATION_FAILURE")
            else:
                for i, (name, status, raw) in enumerate(
                        zip(CASE_NAMES, EXPECTED, outputs), 1):
                    value = injected.get(name, raw) if injected is not None else raw
                    if not _plain_keys(value):
                        errors.append("P52_COMPOSITE_RESULT_UNTRUSTED:" + str(i))
                        continue
                    child_status = value.get("status")
                    child_errors = value.get("errors")
                    child_runtime = value.get("runtime_go_no_go")
                    if (type(child_status) is not str or child_status != status
                            or type(child_errors) is not list or child_errors != []
                            or type(child_runtime) is not str
                            or child_runtime != "NO_GO"
                            or value.get("safety_hold_latched") is not True):
                        errors.append("P52_COMPOSITE_RESULT_UNTRUSTED:" + str(i))
                        continue
                    if any(key in value and value[key] is not False
                           for key in REQUIRED_FALSE):
                        errors.append("P52_REAL_WORLD_AUTHORITY_FABRICATED:" + str(i))
                    if any(key in value and
                           (type(value[key]) is not int or value[key] != 0)
                           for key in REQUIRED_ZERO):
                        errors.append("P52_P05_OR_G1_VALUES_FAKE_ACCEPTED:" + str(i))
                    # Even harmless-looking new fields or modified synthetic
                    # counts must not silently become trusted downstream.
                    if (not _plain_keys(raw)
                            or set(value) != set(raw)
                            or any(type(value[k]) is not type(raw[k])
                                   for k in raw)):
                        errors.append("P52_COMPOSITE_RESULT_UNTRUSTED:" + str(i))
        except Exception:
            # Public/mock subchecks can raise unexpected exceptions.
            # Never echo their text, private values or partial evidence.
            errors.append("P52_OFFLINE_CHILD_EVALUATION_FAILURE")
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
