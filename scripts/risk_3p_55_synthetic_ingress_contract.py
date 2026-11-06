"""Strict in-memory synthetic evidence intake *dry run*, not real ingestion.

No MT4/network access, persistence, private folder reads, account identifiers,
live evidence acceptance, or human approval. Reject unknown keys and
unsourced payloads; a PASS only establishes mock format consistency.
"""
from __future__ import annotations

from scripts import risk_3p_49_synthetic_evidence_chain as chain
from scripts import risk_3p_50_synthetic_dual_witness as witness
from scripts import risk_3p_51_mock_approval_separation as consent

PACKAGE_KEYS = ("schema_version", "classification", "source_mode",
                "event_chain", "two_witnesses", "owner_review", "safety")
SAFETY = {
    "p05_passed": 0,
    "g1_real_verified": 0,
    "real_source_authenticated": False,
    "actual_observation_authorized": False,
    "broker_credentials_available": False,
    "private_payload_collection_authorized": False,
    "human_approval_recorded": False,
    "mt4_access_authorized": False,
    "order_or_ea_execution_authorized": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}


def fixture() -> dict:
    return {
        "schema_version": 1,
        "classification": "SIMULATED_INTAKE_CONTRACT_NEVER_REAL_EVIDENCE",
        "source_mode": "TWO_IN_MEMORY_FAKE_SOURCES_NO_EXTERNAL_AUTH",
        "event_chain": chain.fixture(),
        "two_witnesses": witness.fixture(),
        "owner_review": consent.fixture(),
        "safety": dict(SAFETY),
    }


def evaluate(package: object) -> dict:
    errors = []
    if type(package) is not dict or set(package) != set(PACKAGE_KEYS):
        errors.append("P55_INGRESS_ENVELOPE_MISSING_OR_SENSITIVE_FIELDS")
    else:
        if (type(package["schema_version"]) is not int
                or package["schema_version"] != 1
                or package["classification"] !=
                "SIMULATED_INTAKE_CONTRACT_NEVER_REAL_EVIDENCE"
                or package["source_mode"] !=
                "TWO_IN_MEMORY_FAKE_SOURCES_NO_EXTERNAL_AUTH"):
            errors.append("P55_REAL_SOURCE_OR_ACCESS_SCOPE_SPOOFED")
        if package["safety"] != SAFETY:
            errors.append("P55_BROKER_OR_APPROVAL_PERMISSION_FORGED")
        for key, evaluator, expected, label in (
            ("event_chain", chain.evaluate, "PASS_SYNTHETIC_HASH_CHAIN_ONLY",
             "CHAIN"),
            ("two_witnesses", witness.evaluate, "PASS_TWO_FAKE_WITNESSES_ONLY",
             "WITNESSES"),
            ("owner_review", consent.evaluate, "PASS_NO_REAL_APPROVAL_ONLY",
             "REVIEW"),
        ):
            try:
                result = evaluator(package[key])
                if (result.get("status") != expected
                        or result.get("runtime_go_no_go") != "NO_GO"
                        or result.get("safety_hold_latched") is not True):
                    errors.append("P55_UNTRUSTED_SYNTHETIC_" + label)
            except (KeyError, ValueError, TypeError, IndexError,
                    AttributeError, OverflowError):
                errors.append("P55_MALFORMED_SYNTHETIC_" + label)
    return {
        "status": "PASS_SYNTHETIC_INGRESS_FORMAT_ONLY" if not errors
        else "FAIL_CLOSED",
        "fake_event_count": 3,
        "fake_g1_field_count": 15,
        "real_observation_count": 0,
        "real_broker_origin_verified": False,
        "human_p05_signoff": False,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "private_data_read_authorized": False,
        "real_mt4_read_authorized": False,
        "orders_or_ea_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
