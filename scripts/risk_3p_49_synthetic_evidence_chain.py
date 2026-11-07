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
    if not _exact_keys(data, PACKAGE_KEYS):
        errors.append("P49_INVALID_OR_SENSITIVE_PACKAGE_FIELDS")
    else:
        if (type(data["classification"]) is not str
                or data["classification"] != CLASSIFICATION
                or type(data["genesis"]) is not str
                or data["genesis"] != GENESIS):
            errors.append("P49_REAL_WORLD_AUTHORITY_CLAIMED")
        if not _safe_safety(data["safety"]):
            errors.append("P49_FORGED_P05_OR_BROKER_PERMISSION")
        rows = data["rows"]
        if type(rows) is not list or len(rows) != 3:
            errors.append("P49_EXACTLY_THREE_FAKE_EVENTS_REQUIRED")
        else:
            prev = GENESIS
            for i, row in enumerate(rows):
                n = str(i + 1)
                if not _exact_keys(row, ROW_KEYS):
                    errors.append("P49_INVALID_ROW_OR_SECRET_FIELD:" + n)
                    continue
                identity_ok = (
                    type(row["sequence"]) is int
                    and row["sequence"] == i + 1
                    and type(row["kind"]) is str and row["kind"] == KINDS[i]
                    and type(row["fake_time"]) is str
                    and row["fake_time"] == TIMES[i]
                    and type(row["source_token"]) is str
                    and row["source_token"] == TOKENS[i])
                if not identity_ok:
                    errors.append("P49_EVENT_ORDER_OR_SYNTHETIC_SOURCE_DRIFT:" + n)
                prev_hash = row["previous_hash"]
                prev_ok = type(prev_hash) is str and prev_hash == prev
                if not prev_ok:
                    errors.append("P49_HASH_CHAIN_DISCONNECTED:" + n)
                digest = row["digest"]
                digest_ok = (type(digest) is str
                             and HEX64.fullmatch(digest) is not None)
                if not digest_ok:
                    errors.append("P49_DIGEST_INVALID:" + n)
                elif identity_ok and type(prev_hash) is str:
                    try:
                        expected = digest_payload(
                            sequence=row["sequence"], kind=row["kind"],
                            fake_time=row["fake_time"],
                            source_token=row["source_token"],
                            previous_hash=prev_hash)
                        if digest != expected:
                            errors.append("P49_DIGEST_CONTENT_MISMATCH:" + n)
                    except Exception:
                        # Neither untrusted objects nor hash formatting errors
                        # can turn an invalid fake event into authority.
                        errors.append("P49_DIGEST_CONTENT_MISMATCH:" + n)
                prev = digest if type(digest) is str else ""
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
