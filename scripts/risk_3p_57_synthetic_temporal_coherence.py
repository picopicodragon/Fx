"""Two fictional observer clocks: ordering, skew and session-continuity checks.

No real wall clock, broker clock, system monotonic clock or filesystem access.
A PASS validates a simulated timeline only and cannot prove actual freshness.
"""
from __future__ import annotations

from datetime import datetime

ROOT_KEYS = ("classification", "account_alias", "terminal", "witness", "safety")
STREAM_KEYS = ("origin", "session_alias", "samples")
SAMPLE_KEYS = ("seq", "fake_utc", "synthetic_monotonic_ticks")
ACCOUNT = "SIM_ACCOUNT_A"
SESSIONS = ("SIM_TERMINAL_SESSION_A", "SIM_WITNESS_SESSION_A")
ORIGINS = ("SIM_TERMINAL_TEST_DOUBLE", "SIM_INDEPENDENT_WITNESS_TEST_DOUBLE")
SAFETY = {
    "broker_clock_proven": False,
    "real_freshness_verified": False,
    "real_monotonic_clock_continuity_proven": False,
    "real_mt4_session_authorized": False,
    "p05_passed": 0, "g1_real_verified": 0,
    "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
}


def fixture() -> dict:
    streams = []
    for origin, session, tickbase in zip(ORIGINS, SESSIONS, (100, 200)):
        streams.append({
            "origin": origin, "session_alias": session,
            "samples": [{
                "seq": i + 1,
                "fake_utc": f"SIM_2000-01-01T00:00:0{i}Z",
                "synthetic_monotonic_ticks": tickbase + i,
            } for i in range(3)],
        })
    return {
        "classification": "SIM_TIMELINE_NOT_REAL_TIME_OR_BROKER_EVIDENCE",
        "account_alias": ACCOUNT, "terminal": streams[0],
        "witness": streams[1], "safety": dict(SAFETY),
    }


def _parse_fake_utc(raw: object):
    if (type(raw) is not str or len(raw) != 24
            or not raw.startswith("SIM_2000-01-01T")
            or not raw.endswith("Z")):
        return None
    try:
        return datetime.strptime(raw[4:], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _validate_stream(value: object, origin: str, session: str):
    errors = []
    if type(value) is not dict or set(value) != set(STREAM_KEYS):
        return ["P57_STREAM_MISSING_OR_SENSITIVE_FIELDS"], None
    if value["origin"] != origin or value["session_alias"] != session:
        errors.append("P57_SOURCE_IDENTITY_OR_SESSION_CHANGED")
    samples = value["samples"]
    if type(samples) is not list or len(samples) != 3:
        return errors + ["P57_REQUIRED_THREE_SAMPLES"], None
    parsed = []
    for i, row in enumerate(samples):
        label = str(i + 1)
        if (type(row) is not dict or set(row) != set(SAMPLE_KEYS)
                or type(row.get("seq")) is not int
                or row.get("seq") != i + 1
                or type(row.get("synthetic_monotonic_ticks")) is not int
                or row.get("synthetic_monotonic_ticks") < 1
                or row.get("synthetic_monotonic_ticks") > 1000000):
            errors.append("P57_BAD_SEQUENCE_OR_MONOTONIC_SAMPLE:" + label)
            continue
        stamp = _parse_fake_utc(row.get("fake_utc"))
        if stamp is None:
            errors.append("P57_REAL_OR_MALFORMED_TIME:" + label)
            continue
        parsed.append((stamp, row["synthetic_monotonic_ticks"]))
    if len(parsed) == 3:
        for i in (1, 2):
            elapsed = (parsed[i][0] - parsed[i - 1][0]).total_seconds()
            diff = parsed[i][1] - parsed[i - 1][1]
            if not (0 < elapsed <= 10) or not (0 < diff <= 10):
                errors.append("P57_ROLLBACK_REPLAY_OR_GAP:" + str(i + 1))
    return errors, parsed if len(parsed) == 3 else None


def evaluate(data: object) -> dict:
    errors = []
    if type(data) is not dict or set(data) != set(ROOT_KEYS):
        errors.append("P57_ENVELOPE_MISSING_OR_PRIVATE_FIELDS")
    else:
        if (data["classification"] !=
                "SIM_TIMELINE_NOT_REAL_TIME_OR_BROKER_EVIDENCE"
                or data["account_alias"] != ACCOUNT):
            errors.append("P57_REAL_SOURCE_OR_ACCOUNT_SPOOF")
        if data["safety"] != SAFETY:
            errors.append("P57_REAL_FRESHNESS_OR_RUNTIME_PERMISSION_FORGED")
        sources = []
        for label, origin, session in (
            ("terminal", ORIGINS[0], SESSIONS[0]),
            ("witness", ORIGINS[1], SESSIONS[1]),
        ):
            findings, parsed = _validate_stream(data[label], origin, session)
            errors.extend(x + ":" + label for x in findings)
            sources.append(parsed)
        if all(x is not None for x in sources):
            for i in range(3):
                if abs((sources[0][i][0] - sources[1][i][0]).total_seconds()) > 2:
                    errors.append("P57_INTERSOURCE_FAKE_SKEW:" + str(i + 1))
    return {
        "status": "PASS_SIMULATED_CLOCK_CONSISTENCY_ONLY"
        if not errors else "FAIL_CLOSED",
        "synthetic_sample_pairs": 3,
        "real_timestamp_authenticity_verified": False,
        "real_data_freshness_verified": False,
        "real_clock_monotonicity_verified": False,
        "p05_passed": 0, "g1_real_verified": 0,
        "real_mt4_session_authorized": False,
        "order_or_ea_action_authorized": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "errors": errors,
    }
