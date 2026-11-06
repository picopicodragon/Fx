"""Twenty-nine deterministic offline safety-boundary regressions.

No actual import of tested source overrides, no MT4 or external data access.
Includes six import-allowlist attacks, six import-time calls, and Q109 drift.
"""
from __future__ import annotations

import copy

from scripts import audit_risk_3p_56_static_offline_boundary as source
from scripts import audit_risk_3p_67_source_index as index
from scripts import audit_risk_3p_69_import_time_safety as importer
from scripts import risk_3p_65_integrated_offline_audit as prior

EXPECTED_SCENARIOS = 29
CANARY = "SIM_PRIVATE_FAULT_70_NOT_FOR_LOGGING"


def campaign() -> dict:
    errors = []
    completed = 0
    try:
        for i, path in enumerate(source.TARGETS, 1):
            for code in ("from scripts import unreviewed_broker_adapter",
                         "import scripts.bad_connector"):
                result = source.audit(overrides={path: code})
                completed += 1
                if not any("P56_UNAPPROVED_LOCAL_MODULE_IMPORT" in x
                           for x in result):
                    errors.append("P70_UNSAFE_IMPORT_NOT_REJECTED:" + str(i))
            for code in ("dangerous_top_level()",
                         "some_name = execute_at_import()"):
                result = importer.audit(overrides={path: code})
                completed += 1
                if not any("P69_IMPORT_TIME_" in x for x in result):
                    errors.append("P70_IMPORT_TIME_EXECUTION_NOT_REJECTED:"
                                  + str(i))
        docs = {path: index._read(index.ROOT, path)
                for path in (index.TRACE, index.PINNED)}
        for name, change in (
            ("DELETE", lambda d: d[index.TRACE]["offline_synthetic_mappings"].pop()),
            ("PRODUCTION", lambda d: d[index.TRACE][
                "offline_synthetic_mappings"][0].update(
                    production_authorized=True)),
            ("REPLACE", lambda d: d[index.PINNED]["sources"][0:1].__setitem__(
                0, "scripts/unreviewed_secret_70.py")),
        ):
            clone = copy.deepcopy(docs)
            change(clone)
            completed += 1
            if not index.audit(injected=clone):
                errors.append("P70_PINNED_INVENTORY_MUTATION_PASSED:" + name)
        baseline = dict(zip(prior.NAMES, prior._outputs()))
        for name, edit in (
            ("real_auth", lambda d: d["existing_mock_quality"].update(
                real_order_or_ea_action_authorized=True)),
            ("unknown", lambda d: d["offline_q109_traces"].update(
                broker_password=CANARY)),
        ):
            doc = copy.deepcopy(baseline)
            edit(doc)
            completed += 1
            result = prior.evaluate(injected=doc)
            if (result["status"] != "FAIL_CLOSED"
                    or result["runtime_go_no_go"] != "NO_GO"
                    or result["safety_hold_latched"] is not True
                    or result["automatic_main_merge_authorized"] is not False):
                errors.append("P70_INTEGRATED_AUTHORITY_FORGERY_PASSED:" + name)
            if CANARY in str(result):
                errors.append("P70_SENSITIVE_RESULT_ECHOED")
        if completed != EXPECTED_SCENARIOS:
            errors.append("P70_INCOMPLETE_29_MOCK_FAULT_CAMPAIGN")
    except (OSError, KeyError, ValueError, TypeError,
            IndexError, AttributeError, RecursionError):
        errors.append("P70_SYNTHETIC_CAMPAIGN_INPUT_INVALID")
    return {
        "status": "PASS_TWENTY_NINE_OFFLINE_ATTACKS_ONLY"
        if not errors else "FAIL_CLOSED",
        "mock_failures_exercised": completed,
        "pure_modules_reviewed": len(source.TARGETS),
        "real_source_security_proven": False,
        "real_broker_evidence_verified": False,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "real_mt4_access_authorized": False,
        "order_execution_authorized": False,
        "main_auto_merge_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
