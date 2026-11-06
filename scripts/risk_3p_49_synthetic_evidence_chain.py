"""Synthetic-only event chain with deterministic SHA-256, never authentication.

The checksum detects *accidental or unsynchronized* edits to this fictional
fixture. It is NOT a digital signature, trusted timestamp, immutable ledger,
broker attestation, real order evidence, or human authorization.

No broker, network, filesystem, real account, or wall-clock reads occur.
"""
from __future__ import annotations

import hashlib
import json
import re

GENESIS = "SIM_GENESIS_NO_BROKER_PROOF"
CLASSIFICATION = "SIMULATED_CHAIN_NOT_AUTHENTICATED_EVIDENCE"
KINDS = ("SIM_TERMINAL_UI", "SIM_SERVER_TEST_DOUBLE", "SIM_OWNER_REVIEW_PENDING")
TIMES = ("SIM_2000-01-01T00:00:00Z", "SIM_2000-01-01T00:00:01Z",
         "SIM_2000-01-01T00:00:02Z")
TOKENS = ("SIM_TERMINAL_ONLY", "SIM_SERVER_ONLY", "SIM_OWNER_UNSIGNED")
ROW_KEYS = ("sequence", "kind", "fake_time", "source_token", "previous_hash",
            "digest")
PACKAGE_KEYS = ("classification", "genesis", "rows", "safety")
SAFETY = {
    "independent_broker_evidence_verified": False,
    "trusted_timestamp_verified": False,
    "human_approval_verified": False,
    "p05_accepted": False,
    "p05_passed": 0,
    "g1_verified": 0,
    "real_mt4_read_authorized": False,
    "order_action_authorized": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def digest_payload(*, sequence: int, kind: str, fake_time: str,
                   source_token: str, previous_hash: str) -> str:
    """Canonical mock data checksum. Do not use as an authority signature."""
    payload = {
        "sequence": sequence, "kind": kind, "fake_time": fake_time,
        "source_token": source_token, "previous_hash": previous_hash,
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def fixture() -> dict:
    rows = []
    prev = GENESIS
    for seq, (kind, fake_time, token) in enumerate(
            zip(KINDS, TIMES, TOKENS), 1):
        record = {
            "sequence": seq, "kind": kind, "fake_time": fake_time,
            "source_token": token, "previous_hash": prev,
        }
        record["digest"] = digest_payload(**record)
        rows.append(record)
        prev = record["digest"]
    return {
        "classification": CLASSIFICATION,
        "genesis": GENESIS,
        "rows": rows,
        "safety": dict(SAFETY),
    }


def evaluate(data: object) -> dict:
    errors: list[str] = []
    if type(data) is not dict or set(data) != set(PACKAGE_KEYS):
        errors.append("P49_INVALID_OR_SENSITIVE_PACKAGE_FIELDS")
    else:
        if data["classification"] != CLASSIFICATION or data["genesis"] != GENESIS:
            errors.append("P49_REAL_WORLD_AUTHORITY_CLAIMED")
        if data["safety"] != SAFETY:
            errors.append("P49_FORGED_P05_OR_BROKER_PERMISSION")
        rows = data["rows"]
        if type(rows) is not list or len(rows) != 3:
            errors.append("P49_EXACTLY_THREE_FAKE_EVENTS_REQUIRED")
        else:
            prev = GENESIS
            for i, row in enumerate(rows):
                n = str(i + 1)
                if type(row) is not dict or set(row) != set(ROW_KEYS):
                    errors.append("P49_INVALID_ROW_OR_SECRET_FIELD:" + n)
                    continue
                if (type(row["sequence"]) is not int
                        or row["sequence"] != i + 1
                        or row["kind"] != KINDS[i]
                        or row["fake_time"] != TIMES[i]
                        or row["source_token"] != TOKENS[i]):
                    errors.append("P49_EVENT_ORDER_OR_SYNTHETIC_SOURCE_DRIFT:" + n)
                if row["previous_hash"] != prev:
                    errors.append("P49_HASH_CHAIN_DISCONNECTED:" + n)
                if (type(row["digest"]) is not str
                        or HEX64.fullmatch(row["digest"]) is None):
                    errors.append("P49_DIGEST_INVALID:" + n)
                else:
                    expected = digest_payload(
                        sequence=row["sequence"], kind=row["kind"],
                        fake_time=row["fake_time"],
                        source_token=row["source_token"],
                        previous_hash=row["previous_hash"],
                    )
                    if row["digest"] != expected:
                        errors.append("P49_DIGEST_CONTENT_MISMATCH:" + n)
                prev = row["digest"]
    return {
        "status": "PASS_SYNTHETIC_HASH_CHAIN_ONLY" if not errors else "FAIL_CLOSED",
        "simulated_events_checked": 3,
        "cryptographic_authenticity_verified": False,
        "immutable_storage_verified": False,
        "broker_origin_verified": False,
        "real_account_data_collected": False,
        "human_approval_verified": False,
        "p05_passed": 0, "g1_verified": 0,
        "real_mt4_read_authorized": False,
        "order_action_authorized": False,
        "runtime_go_no_go": "NO_GO", "safety_hold_latched": True,
        "errors": errors,
    }
