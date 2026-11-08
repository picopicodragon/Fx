"""Bounded privacy-safe reporting of fictional QA results, in memory only.

Untrusted input values and error descriptions are never copied to output.
This is an allowlisted schema projection, NOT a general-purpose PII scrubber.
"""
from __future__ import annotations

NAMES = ("chain", "two_witnesses", "fake_timeline", "unsigned_review")
EXPECTED = (
    "PASS_SYNTHETIC_HASH_CHAIN_ONLY", "PASS_TWO_FAKE_WITNESSES_ONLY",
    "PASS_SIMULATED_CLOCK_CONSISTENCY_ONLY", "PASS_NO_REAL_APPROVAL_ONLY",
)
ROOT_KEYS = ("classification", "checks", "safety")
CHECK_KEYS = ("name", "mock_status", "mock_only", "real_evidence_verified",
              "raw_errors")
SAFETY = {
    "raw_payload_storage_authorized": False,
    "real_broker_evidence_collected": False,
    "p05_passed": 0, "g1_real_verified": 0,
    "real_mt4_read_authorized": False,
    "order_action_authorized": False,
    "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
}


def _exact_keys(value: object, names: tuple[str, ...]) -> bool:
    if type(value) is not dict or len(value) != len(names):
        return False
    found = tuple(value)
    return all(type(k) is str for k in found) and set(found) == set(names)


def _safe_safety(value: object) -> bool:
    if not _exact_keys(value, tuple(SAFETY)):
        return False
    return all(type(value[k]) is type(SAFETY[k]) and value[k] == SAFETY[k]
               for k in SAFETY)


def _safe_mock_check(value: object, name: str, expected: str) -> bool:
    if not _exact_keys(value, CHECK_KEYS):
        return False
    return (type(value["name"]) is str and value["name"] == name
            and type(value["mock_status"]) is str
            and value["mock_status"] == expected
            and value["mock_only"] is True
            and value["real_evidence_verified"] is False
            and type(value["raw_errors"]) is list
            and value["raw_errors"] == [])


def fixture() -> dict:
    return {
        "classification": "FICTIONAL_QA_SUMMARY_NO_REAL_PAYLOAD",
        "checks": [
            {"name": name, "mock_status": status,
             "mock_only": True, "real_evidence_verified": False,
             "raw_errors": []}
            for name, status in zip(NAMES, EXPECTED)
        ],
        "safety": dict(SAFETY),
    }


def summarize(untrusted: object) -> dict:
    """All output keys/values are locally constructed fixed codes and counts."""
    codes = []
    if not _exact_keys(untrusted, ROOT_KEYS):
        codes.append("P58_UNKNOWN_ENVELOPE_OR_RAW_DATA_FIELD")
    else:
        if (type(untrusted["classification"]) is not str
                or untrusted["classification"] !=
                "FICTIONAL_QA_SUMMARY_NO_REAL_PAYLOAD"
                or not _safe_safety(untrusted["safety"])):
            codes.append("P58_SCOPE_OR_PERMISSION_SPOOF")
        checks = untrusted["checks"]
        if type(checks) is not list or len(checks) != 4:
            codes.append("P58_EXPECTED_FOUR_FICTIONAL_CHECKS")
        else:
            for i, (name, expected) in enumerate(zip(NAMES, EXPECTED), 1):
                value = checks[i - 1]
                if not _safe_mock_check(value, name, expected):
                    codes.append("P58_UNSAFE_OR_UNTRUSTED_RESULT:" + str(i))
    return {
        "status": "PASS_SAFE_FAKE_SUMMARY_ONLY" if not codes else "FAIL_CLOSED",
        "check_slots": 4,
        "synthetic_checks_consistent": 4 if not codes else 0,
        "submitted_values_echoed": False,
        "real_evidence_authenticated": False,
        "raw_evidence_collected": False,
        "p05_passed": 0, "g1_real_verified": 0,
        "real_mt4_read_authorized": False,
        "order_execution_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": codes,
    }
