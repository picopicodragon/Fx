"""P05-01/04: synthetic identity and single-session gate, not a login tool.

All aliases are fictional, accepted outputs NEVER authorize MT4 access.
"""
from __future__ import annotations

KEYS = ("schema", "classification", "owner_ui", "terminal", "mock_server",
        "safety")
ENDPOINT_KEYS = ("origin", "account_alias", "account_class", "session_alias",
                 "status", "observed_at_token")
SAFETY = {
    "p05_passed": 0, "real_identity_verified": False,
    "real_session_verified": False, "new_login_authorized": False,
    "parallel_session_authorized": False, "order_authorized": False,
    "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
}
BASE_ACCOUNT = "SIM_ACCOUNT_A"
BASE_SESSION = "SIM_SESSION_A"
TIME_TOKEN = "SIM_NOT_REAL_UTC_OBSERVATION"


def _exact(value: object, names: tuple[str, ...]) -> bool:
    return type(value) is dict and set(value) == set(names)


def fixture() -> dict:
    terminal = {
        "origin": "SIM_TERMINAL_UI", "account_alias": BASE_ACCOUNT,
        "account_class": "SIM_DEMO", "session_alias": BASE_SESSION,
        "status": "SIM_CONNECTED", "observed_at_token": TIME_TOKEN,
    }
    server = dict(terminal)
    server["origin"] = "SIM_INDEPENDENT_SERVER_TEST_DOUBLE"
    return {
        "schema": 1, "classification": "SIM_ONLY_NEVER_REAL_EVIDENCE",
        "owner_ui": "DEMO_COMMUNICATING_DISPLAY_OWNER_REPORT_ONLY",
        "terminal": terminal, "mock_server": server, "safety": dict(SAFETY),
    }


def evaluate(data: object) -> dict:
    errors: list[str] = []
    if not _exact(data, KEYS):
        errors.append("P38_INVALID_OR_EXTRA_FIELDS")
    else:
        if (type(data["schema"]) is not int or data["schema"] != 1
                or data["classification"] != "SIM_ONLY_NEVER_REAL_EVIDENCE"
                or data["owner_ui"] !=
                "DEMO_COMMUNICATING_DISPLAY_OWNER_REPORT_ONLY"):
            errors.append("P38_OWNER_UI_PROMOTED_TO_IDENTITY")
        if data["safety"] != SAFETY:
            errors.append("P38_FORGED_LOGIN_OR_TRADE_PERMISSION")
        for name, origin in (("terminal", "SIM_TERMINAL_UI"),
                             ("mock_server",
                              "SIM_INDEPENDENT_SERVER_TEST_DOUBLE")):
            endpoint = data[name]
            if (not _exact(endpoint, ENDPOINT_KEYS)
                    or endpoint.get("origin") != origin
                    or endpoint.get("account_alias") != BASE_ACCOUNT
                    or endpoint.get("account_class") != "SIM_DEMO"
                    or endpoint.get("session_alias") != BASE_SESSION
                    or endpoint.get("status") != "SIM_CONNECTED"
                    or endpoint.get("observed_at_token") != TIME_TOKEN):
                errors.append("P38_IDENTITY_OR_SESSION_UNVERIFIED:" + name)
    return {
        "status": "PASS_SIMULATED_IDENTIFIERS_ONLY" if not errors
        else "FAIL_CLOSED",
        "simulated_match": not errors,
        "real_account_identity_verified": False,
        "real_single_session_verified": False,
        "p05_01_accepted": False, "p05_04_accepted": False,
        "p05_checks_passed": 0,
        "mt4_login_authorized": False, "new_demo_account_authorized": False,
        "parallel_session_authorized": False, "order_authorized": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "errors": errors,
    }
