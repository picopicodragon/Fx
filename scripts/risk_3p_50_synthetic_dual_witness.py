"""Mock-only 3x5 two-witness comparison; not independent broker verification.

Two fictional sources are generated inside this process. Matching strings
do NOT establish real-world independence, unit conversion, or authenticity.
"""
from __future__ import annotations

from scripts import validate_risk_3p_34_synthetic_provenance as base

ROOT_KEYS = ("classification", "primary", "second_witness", "safety")
WITNESS_KEYS = ("source_kind", "account_alias", "fake_utc", "rows")
ROW_KEYS = ("pair", "field", "synthetic_decimal", "unit",
            "source_token")
ALIAS = "SIM_ACCOUNT_WITNESS_A"
SAFETY = {
    "p05_passed": 0, "g1_real_verified": 0,
    "real_broker_source_independence_verified": False,
    "trusted_timestamp_verified": False,
    "actual_mt4_properties_observed": False,
    "owner_signature_verified": False,
    "real_mt4_read_authorized": False,
    "orders_authorized": False,
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
    primary = base.make_synthetic_fixture()
    witness = {
        "source_kind": "SIM_INDEPENDENT_SOURCE_TEST_DOUBLE",
        "account_alias": ALIAS,
        "fake_utc": "SIM_2000-01-01T00:00:01Z",
        "rows": [
            {
                "pair": item["pair"],
                "field": item["field"],
                "synthetic_decimal": item["synthetic_value_decimal"],
                "unit": item["unit"],
                "source_token": f"SIM_WITNESS_{i + 1:02d}",
            }
            for i, item in enumerate(primary["rows"])
        ],
    }
    return {
        "classification": "SIM_TWO_WITNESSES_NOT_REAL_EVIDENCE",
        "primary": primary,
        "second_witness": witness,
        "safety": dict(SAFETY),
    }


def evaluate(data: object) -> dict:
    errors: list[str] = []
    if not _exact_keys(data, ROOT_KEYS):
        errors.append("P50_INVALID_OR_EXTRA_PACKAGE_FIELDS")
    else:
        if (type(data["classification"]) is not str
                or data["classification"] !=
                "SIM_TWO_WITNESSES_NOT_REAL_EVIDENCE"):
            errors.append("P50_FAKE_SOURCES_MISREPRESENTED")
        if not _safe_safety(data["safety"]):
            errors.append("P50_FORGED_REAL_EVIDENCE_OR_PERMISSION")
        try:
            first = base.check_synthetic_package(data["primary"])
            first_ok = (type(first) is dict
                        and all(type(k) is str for k in first)
                        and type(first.get("status")) is str
                        and first["status"] == "PASS_SYNTHETIC_CONTRACT_ONLY")
        except Exception:
            first_ok = False
        if not first_ok:
            errors.append("P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID")
        second = data["second_witness"]
        if not _exact_keys(second, WITNESS_KEYS):
            errors.append("P50_SECOND_WITNESS_STRUCTURE_INVALID")
        elif (type(second["source_kind"]) is not str
              or second["source_kind"] != "SIM_INDEPENDENT_SOURCE_TEST_DOUBLE"
              or type(second["account_alias"]) is not str
              or second["account_alias"] != ALIAS
              or type(second["fake_utc"]) is not str
              or second["fake_utc"] != "SIM_2000-01-01T00:00:01Z"):
            errors.append("P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")
        else:
            rows = second["rows"]
            if type(rows) is not list or len(rows) != 15:
                errors.append("P50_FIFTEEN_WITNESS_ROWS_REQUIRED")
            elif (first_ok and type(data["primary"]) is dict
                    and all(type(k) is str for k in data["primary"])
                    and type(data["primary"].get("rows")) is list
                    and len(data["primary"]["rows"]) == 15):
                for i, (row, primary) in enumerate(
                        zip(rows, data["primary"]["rows"]), 1):
                    if not _exact_keys(row, ROW_KEYS):
                        errors.append("P50_WITNESS_ROW_SECRET_OR_MISSING:" + str(i))
                        continue
                    if (any(type(row[k]) is not str for k in ROW_KEYS)
                            or type(primary) is not dict
                            or any(type(k) is not str for k in primary)
                            or type(primary.get("synthetic_value_decimal"))
                            is not str
                            or row["pair"] != base.PAIRS[(i - 1) // 5]
                            or row["field"] != base.FIELDS[(i - 1) % 5]
                            or row["source_token"] != f"SIM_WITNESS_{i:02d}"
                            or row["unit"] != base.UNITS[
                                base.FIELDS[(i - 1) % 5]]
                            or row["synthetic_decimal"] !=
                            primary["synthetic_value_decimal"]):
                        errors.append("P50_SOURCE_VALUE_OR_UNIT_CONFLICT:" + str(i))
    return {
        "status": "PASS_TWO_FAKE_WITNESSES_ONLY" if not errors else "FAIL_CLOSED",
        "fictitious_fields": 15,
        "actual_broker_fields_verified": 0,
        "actual_source_independence_verified": False,
        "human_approval_verified": False,
        "p05_passed": 0,
        "real_mt4_read_authorized": False,
        "orders_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "errors": errors,
    }
