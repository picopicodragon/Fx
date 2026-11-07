"""PR merge, simulated success and owner folder acceptance are NOT P05 consent.

Deterministic offline permission-separation test. No signature collection,
GUI interactions, brokerage access, file I/O or actual review records.
"""
from __future__ import annotations

REQUIRED = ("classification", "observations", "unsigned_p05", "safety")
OBS_KEYS = ("simulated_pr_merged", "simulated_ci_passed",
            "owner_local_storage_accepted_for_offline_only",
            "simulated_witnesses_match", "synthetic_hash_chain_passes")
ROW_KEYS = ("check_id", "real_evidence_verified", "explicit_owner_signoff",
            "real_mt4_observation_authorized")
SAFETY = {
    "p05_required": 8, "p05_passed": 0,
    "g1_real_verified": 0,
    "fx_saf_originals_verified": 0,
    "form_decisions_approved": 0,
    "broker_read_authorized": False,
    "real_orders_or_ea_authorized": False,
    "live_or_demo_order_execution_authorized": False,
    "stop_release_authorized": False,
    "phase1_approved": False,
    "real_human_approval_recorded": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}



def _exact_keys(value: object, names: tuple[str, ...]) -> bool:
    if type(value) is not dict or len(value) != len(names):
        return False
    keys = tuple(value)
    return all(type(key) is str for key in keys) and set(keys) == set(names)


def _safe_safety(value: object) -> bool:
    if not _exact_keys(value, tuple(SAFETY)):
        return False
    return all(type(value[k]) is type(SAFETY[k]) and value[k] == SAFETY[k]
               for k in SAFETY)



def fixture() -> dict:
    return {
        "classification": "OFFLINE_OWNER_APPROVAL_BOUNDARY_MOCK_ONLY",
        "observations": {
            "simulated_pr_merged": True,
            "simulated_ci_passed": True,
            "owner_local_storage_accepted_for_offline_only": True,
            "simulated_witnesses_match": True,
            "synthetic_hash_chain_passes": True,
        },
        "unsigned_p05": [
            {
                "check_id": f"P05-{i:02d}",
                "real_evidence_verified": False,
                "explicit_owner_signoff": False,
                "real_mt4_observation_authorized": False,
            }
            for i in range(1, 9)
        ],
        "safety": dict(SAFETY),
    }


def evaluate(data: object) -> dict:
    errors: list[str] = []
    if not _exact_keys(data, REQUIRED):
        errors.append("P51_INVALID_OR_UNEXPECTED_PRIVATE_FIELDS")
    else:
        if (type(data["classification"]) is not str
                or data["classification"] !=
                "OFFLINE_OWNER_APPROVAL_BOUNDARY_MOCK_ONLY"):
            errors.append("P51_REAL_PERMISSION_SCOPE_SPOOFED")
        observations = data["observations"]
        if (not _exact_keys(observations, OBS_KEYS)
                or any(observations[k] is not True for k in OBS_KEYS)):
            errors.append("P51_PRIOR_REPORT_OR_SYNTHETIC_RESULT_RELABELED")
        rows = data["unsigned_p05"]
        if type(rows) is not list or len(rows) != 8:
            errors.append("P51_EIGHT_UNSIGNED_P05_ROWS_REQUIRED")
        else:
            for i, row in enumerate(rows, 1):
                if (not _exact_keys(row, ROW_KEYS)
                        or type(row["check_id"]) is not str
                        or row["check_id"] != f"P05-{i:02d}"
                        or any(row[k] is not False for k in ROW_KEYS
                               if k != "check_id")):
                    errors.append("P51_OWNER_OR_BROKER_APPROVAL_FORGED:"
                                  + str(i))
        if not _safe_safety(data["safety"]):
            errors.append("P51_STOP_OR_P05_AUTHORIZATION_FORGED")
    return {
        "status": "PASS_NO_REAL_APPROVAL_ONLY" if not errors else "FAIL_CLOSED",
        "p05_items_still_unsigned": 8,
        "p05_passed": 0,
        "g1_real_verified": 0,
        "real_account_identity_verified": False,
        "owner_p05_approval_recorded": False,
        "real_mt4_read_authorized": False,
        "real_order_execution_authorized": False,
        "phase1_approved": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
