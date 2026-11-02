"""Unconnected Q197-Q199 mock handoff review for Way E tests.

No network, broker adapter, order command, credential, or approval path exists.
Every outcome forbids dispatch, retry, stop release, and runtime promotion.
"""
from __future__ import annotations


_PHASES = {"PREPARED", "DISPATCHING"}
_RESPONSES = {"NO_RESPONSE", "RESPONSE_ACCEPTED", "RESPONSE_REJECTED",
              "OUTCOME_UNKNOWN"}


def _result(reason: str, reconcile: bool = False) -> dict[str, object]:
    return {
        "reason": reason,
        "independent_reconciliation_required": reconcile,
        "dispatch_allowed": False,
        "automatic_retry_allowed": False,
        "stop_release_allowed": False,
        "safety_hold_latched": True,
        "phase_1": "BLOCKED",
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
    }


def review_mock_handoff(record: object) -> dict[str, object]:
    """Review a fixed synthetic dispatch record; never return order authority."""
    if type(record) is not dict or set(record) != {
        "phase", "response", "broker_match", "public_metadata",
    }:
        return _result("INVALID_RECORD")
    phase, response = record["phase"], record["response"]
    match, metadata = record["broker_match"], record["public_metadata"]
    if (type(phase) is not str or phase not in _PHASES
            or type(response) is not str or response not in _RESPONSES
            or type(match) not in (type(None), bool)):
        return _result("INVALID_STATE")
    if (type(metadata) is not dict or set(metadata) != {
        "gate_id", "scenario_id", "label",
    } or type(metadata.get("gate_id")) is not str
            or metadata["gate_id"] != "G4"
            or type(metadata.get("scenario_id")) is not str
            or metadata["scenario_id"] not in {"P1-05-F01", "P1-05-F03", "P1-05-F04"}
            or type(metadata.get("label")) is not str
            or metadata["label"] != response):
        return _result("PUBLIC_METADATA_REJECTED")
    if phase == "PREPARED":
        if response != "NO_RESPONSE" or match is not None:
            return _result("PRE_DISPATCH_CONTRADICTION")
        return _result("PREPARED_NOT_DISPATCH_PROOF")
    if response in {"NO_RESPONSE", "OUTCOME_UNKNOWN"}:
        return _result("OUTCOME_UNKNOWN_NO_BLIND_RETRY", True)
    if response == "RESPONSE_ACCEPTED":
        return _result("SYNTHETIC_RESPONSE_NOT_EXECUTION_PROOF", True)
    return _result("REJECTED_RESPONSE_NO_RETRY", match is not None)
