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
    if type(data) is not dict or set(data) != set(ROOT_KEYS):
        errors.append("P50_INVALID_OR_EXTRA_PACKAGE_FIELDS")
    else:
        if data["classification"] != "SIM_TWO_WITNESSES_NOT_REAL_EVIDENCE":
            errors.append("P50_FAKE_SOURCES_MISREPRESENTED")
        if data["safety"] != SAFETY:
            errors.append("P50_FORGED_REAL_EVIDENCE_OR_PERMISSION")
        first = base.check_synthetic_package(data["primary"])
        if first["status"] != "PASS_SYNTHETIC_CONTRACT_ONLY":
            errors.append("P50_PRIMARY_SYNTHETIC_PROVENANCE_INVALID")
        second = data["second_witness"]
        if type(second) is not dict or set(second) != set(WITNESS_KEYS):
            errors.append("P50_SECOND_WITNESS_STRUCTURE_INVALID")
        elif (second["source_kind"] != "SIM_INDEPENDENT_SOURCE_TEST_DOUBLE"
              or second["account_alias"] != ALIAS
              or second["fake_utc"] != "SIM_2000-01-01T00:00:01Z"):
            errors.append("P50_WITNESS_SCOPE_OR_FAKE_TIMESTAMP_INVALID")
        else:
            rows = second["rows"]
            if type(rows) is not list or len(rows) != 15:
                errors.append("P50_FIFTEEN_WITNESS_ROWS_REQUIRED")
            elif type(data["primary"]) is dict and type(
                    data["primary"].get("rows")) is list and len(
                    data["primary"]["rows"]) == 15:
                for i, (row, primary) in enumerate(
                        zip(rows, data["primary"]["rows"]), 1):
                    if (type(row) is not dict or set(row) != set(ROW_KEYS)):
                        errors.append("P50_WITNESS_ROW_SECRET_OR_MISSING:" +
                                      str(i))
                        continue
                    if (row["pair"] != base.PAIRS[(i - 1) // 5]
                            or row["field"] != base.FIELDS[(i - 1) % 5]
                            or row["source_token"] != f"SIM_WITNESS_{i:02d}"
                            or row["unit"] != base.UNITS[
                                base.FIELDS[(i - 1) % 5]]
                            or row["synthetic_decimal"] !=
                            primary.get("synthetic_value_decimal")):
                        errors.append("P50_SOURCE_VALUE_OR_UNIT_CONFLICT:" +
                                      str(i))
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
