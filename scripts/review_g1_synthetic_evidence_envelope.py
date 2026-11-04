"""RISK-3P-21: metadata-only synthetic provenance envelope precheck.

Never accepts real broker values. Its best result is a STRUCTURAL EXAMPLE
that grants no G1 evidence acceptance, source verification, market access,
order placement, STOP release, auto-resume or live risk validation.
No filesystem, time reads, network, MT4, account or other I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from scripts.review_mt4_manual_symbol_3p_v3 import PAIRS, FIVE


STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
TERMINAL = re.compile(r"[A-Z]{6}[a-zA-Z0-9._-]{0,16}\Z")
UNITS = {
    "min_lot": "LOT",
    "lot_step": "LOT",
    "point_quote": "QUOTE_CCY_PER_BASE",
    "tick_size_points": "POINT",
    "tick_value_deposit_currency": "DEPOSIT_CCY_PER_TICK_PER_REFERENCE_LOT",
}


@dataclass(frozen=True)
class ExampleEnvelope:
    pair: str
    field: str
    terminal_symbol: str
    synthetic_account_alias: str
    primary_source_id: str
    crosscheck_source_id: str
    primary_issuer: str
    crosscheck_issuer: str
    observed_at_utc: str
    crosscheck_at_utc: str
    unit_claim: str
    synthetic_only: bool
    independent_unit_checked_claim: bool
    same_account_claim: bool
    contract_version_rechecked_claim: bool
    freshness_policy_defined_claim: bool
    confidential_payload_present: bool
    raw_contract_value: None = None


@dataclass(frozen=True)
class Review:
    reason: str
    metadata_shape_consistent: bool = False
    independent_issuer_proven: bool = False
    observed_contract_value_proven: bool = False
    account_identity_proven: bool = False
    timestamp_freshness_proven: bool = False
    broker_access_authorized: bool = False
    g1_acceptance_approved: bool = False
    owner_approval_recorded: bool = False
    order_allowed: bool = False
    stop_release_allowed: bool = False
    automatic_retry_allowed: bool = False
    production_authorized: bool = False
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    verified_values: None = None


def _reject(reason: str) -> Review:
    return Review(reason=reason)


def _valid_synthetic_id(value: object) -> bool:
    return (type(value) is str and value.startswith("SYNTHETIC_")
            and 11 < len(value) <= 64 and
            all(c.isupper() or c.isdigit() or c == "_" for c in value))


def _time(value: object) -> datetime | None:
    if type(value) is not str or STAMP.fullmatch(value) is None:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo == timezone.utc and dt.year >= 2000 else None
    except (ValueError, TypeError, OverflowError):
        return None


def review_synthetic_metadata(value: object) -> Review:
    """Even fully consistent *fictional* claims cannot become broker evidence."""
    if type(value) is not ExampleEnvelope:
        return _reject("INVALID_ENVELOPE")
    if (type(value.pair) is not str or value.pair not in PAIRS
            or type(value.field) is not str or value.field not in FIVE):
        return _reject("PAIR_OR_FIELD_NOT_IN_THREE_PAIR_G1_SCOPE")
    if value.synthetic_only is not True:
        return _reject("REAL_EVIDENCE_SUBMISSION_NOT_SUPPORTED")
    if (value.confidential_payload_present is not False
            or value.raw_contract_value is not None):
        return _reject("REAL_VALUE_OR_CONFIDENTIAL_PAYLOAD_FORBIDDEN")
    if (type(value.terminal_symbol) is not str
            or TERMINAL.fullmatch(value.terminal_symbol) is None
            or not value.terminal_symbol.startswith(value.pair.replace("/", ""))):
        return _reject("ILLUSTRATIVE_TERMINAL_SYMBOL_SHAPE_INVALID")
    if not _valid_synthetic_id(value.synthetic_account_alias):
        return _reject("SYNTHETIC_ACCOUNT_ALIAS_REQUIRED")
    for item in (
        value.primary_source_id, value.crosscheck_source_id,
        value.primary_issuer, value.crosscheck_issuer,
    ):
        if not _valid_synthetic_id(item):
            return _reject("FAKE_SOURCE_IDENTIFIER_INVALID")
    if (value.primary_source_id == value.crosscheck_source_id
            or value.primary_issuer == value.crosscheck_issuer):
        return _reject("SAME_SOURCE_OR_ISSUER_CANNOT_BE_INDEPENDENT")
    primary = _time(value.observed_at_utc)
    secondary = _time(value.crosscheck_at_utc)
    if primary is None or secondary is None or primary != secondary:
        return _reject("CROSSCHECK_SNAPSHOT_TIMESTAMP_MISMATCH")
    if value.unit_claim != UNITS[value.field]:
        return _reject("EXPLICIT_UNIT_SHAPE_MISSING_OR_WRONG")
    if value.independent_unit_checked_claim is not True:
        return _reject("UNIT_NOT_INDEPENDENTLY_CHECKED_IN_FIXTURE")
    if value.same_account_claim is not True:
        return _reject("ACCOUNT_PROVENANCE_INCONSISTENT_IN_FIXTURE")
    if value.contract_version_rechecked_claim is not True:
        return _reject("CONTRACT_CHANGE_NOT_CHECKED_IN_FIXTURE")
    if value.freshness_policy_defined_claim is not False:
        # No source-specific real-world TTL policy has been approved.
        return _reject("FALSE_FRESHNESS_POLICY_APPROVAL")
    return Review("SYNTHETIC_METADATA_SHAPE_ONLY_NOT_G1_EVIDENCE",
                  metadata_shape_consistent=True)
