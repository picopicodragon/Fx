"""70 reproducible synthetic corruption injections across P60 subreports.

No broker, external payload, timers, terminal, network or private files.
This exercises fail-closed *offline QA results*, not actual trading controls.
"""
from __future__ import annotations

import copy

from scripts import risk_3p_60_offline_ingress_quality_gate as quality
from scripts import risk_3p_61_strict_offline_result_contract as strict

CANARY = "PRIVATE_SIM_CANARY_64_DO_NOT_ECHO"
FAULTS = (
    "ADDED_UNKNOWN_APPROVAL",
    "STATUS_CLAIMED_REAL",
    "RUNTIME_GO",
    "STOP_LATCH_LOST",
    "ERRORS_REMOVED",
    "FORGED_ACCEPTED_COUNT",
    "TYPE_CONFUSED_ZERO_COUNTER",
    "SECRET_ERROR_TEXT",
    "PRIVATE_STATUS_STRING",
    "MISSING_STATUS",
)


def _counter_key(record: dict) -> str:
    for key in ("p05_passed", "p05_real_accepted"):
        if key in record:
            return key
    raise ValueError("offline status lacked acceptance zero counter")


def mutate(original: dict, fault: str):
    copy_value = copy.deepcopy(original)
    if fault == "ADDED_UNKNOWN_APPROVAL":
        copy_value["allow_real_trading_after_ci"] = True
    elif fault == "STATUS_CLAIMED_REAL":
        copy_value["status"] = "PASS_REAL_BROKER_CERTIFIED"
    elif fault == "RUNTIME_GO":
        copy_value["runtime_go_no_go"] = "GO"
    elif fault == "STOP_LATCH_LOST":
        copy_value["safety_hold_latched"] = False
    elif fault == "ERRORS_REMOVED":
        copy_value.pop("errors")
    elif fault == "FORGED_ACCEPTED_COUNT":
        copy_value[_counter_key(copy_value)] = 8
    elif fault == "TYPE_CONFUSED_ZERO_COUNTER":
        copy_value[_counter_key(copy_value)] = False
    elif fault == "SECRET_ERROR_TEXT":
        copy_value["errors"] = [CANARY]
    elif fault == "PRIVATE_STATUS_STRING":
        copy_value["status"] = CANARY
    elif fault == "MISSING_STATUS":
        copy_value.pop("status")
    else:
        raise ValueError("unknown synthetic corruption type")
    return copy_value


def campaign() -> dict:
    errors = []
    try:
        originals = dict(zip(quality.NAMES, quality._outputs()))
        for name in quality.NAMES:
            if strict.check(name, originals[name]):
                errors.append("P64_INVALID_BASELINE:" + str(
                    quality.NAMES.index(name) + 1))
        for i, name in enumerate(quality.NAMES, 1):
            for j, fault in enumerate(FAULTS, 1):
                changed = mutate(originals[name], fault)
                # Strict contract checks all 70 corruptions directly,
                # avoiding 70 expensive recursive evaluations of the same
                # existing synthetic QA dependency tree.
                findings = strict.check(name, changed)
                if not findings:
                    errors.append(f"P64_MUTATION_ACCEPTED:{i}:{j}")
                if CANARY in str(findings):
                    errors.append(f"P64_INJECTED_PRIVATE_VALUE_ECHOED:{i}:{j}")
            # Each of the seven report classes is also checked through the
            # real composite offline P60 path at least once.
            sample = mutate(originals[name], "ADDED_UNKNOWN_APPROVAL")
            gate = quality.evaluate(injected={name: sample})
            if (gate["status"] != "FAIL_CLOSED"
                    or gate["runtime_go_no_go"] != "NO_GO"
                    or gate["safety_hold_latched"] is not True
                    or gate["p05_passed"] != 0
                    or gate["real_mt4_access_authorized"] is not False
                    or gate["real_order_or_ea_action_authorized"] is not False):
                errors.append("P64_COMPOSITE_INTEGRATION_MISSED:" + str(i))
            if CANARY in str(gate):
                errors.append("P64_INTEGRATION_ECHOED_PRIVATE_VALUE:" + str(i))
    except (ValueError, TypeError, KeyError, AttributeError, IndexError,
            RecursionError):
        errors.append("P64_OFFLINE_ADVERSARIAL_HARNESS_FAILURE")
    return {
        "status": "PASS_SEVENTY_MOCK_CORRUPTIONS_ONLY"
        if not errors else "FAIL_CLOSED",
        "offline_baseline_classes": len(quality.NAMES),
        "synthetic_mutation_types": len(FAULTS),
        "synthetic_corruptions_checked": len(quality.NAMES) * len(FAULTS),
        "composite_integration_cases_checked": len(quality.NAMES),
        "p05_passed": 0,
        "g1_real_verified": 0,
        "actual_broker_evidence_received": False,
        "human_signoff_verified": False,
        "real_mt4_access_authorized": False,
        "order_execution_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
