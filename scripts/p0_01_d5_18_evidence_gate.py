"""D5-18: offline-only, fail-closed account evidence reconciliation.

No MT4, broker, network, file, clock, order, or approval operations.
All supplied 'measurement' records are synthetic claims, not real measurements.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

_SOURCES = frozenset(("USER_REPORT", "VISUAL_OBSERVATION",
                      "SYNTHETIC_SYSTEM_MEASUREMENT"))
_VALUES = frozenset(("PRESENT", "ABSENT", "UNKNOWN"))
_FIELDS = ("positions", "pending_orders", "ea_running")
_RECORD_FIELDS = frozenset(("evidence_id", "source_kind", "account_scope",
                           "observed_at_utc", *_FIELDS))
_STATES = frozenset(("S17-01", "S17-02", "S17-03", "S17-04",
                     "S17-05", "S17-06", "S17-07", "S17-08"))
_UTC_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_SCOPE_PATTERN = re.compile(r"SYNTHETIC_[A-Z0-9_]{1,40}\Z")
_ID_PATTERN = re.compile(r"EVID_[A-Z0-9_]{1,40}\Z")


def _denied(status: str, *, records_reviewed: int = 0) -> dict[str, object]:
    """Use one shared non-authorizing output for all branches."""
    return {
        "status": status,
        "records_reviewed": records_reviewed,
        "account_identity_consistency": "NOT_RECONCILED",
        "positions_status": "UNKNOWN",
        "pending_orders_status": "UNKNOWN",
        "ea_running_status": "UNKNOWN",
        "runtime_go_no_go": "NO_GO",
        "verified_values": None,
        "broker_verified": False,
        "production_usable": False,
        "read_only_ex4_execution_approved": False,
        "terminal_execution_approved": False,
        "orders_generated": False,
        "forward_trading_enabled": False,
        "phase_1": "BLOCKED",
    }


def _utc_timestamp(value: object) -> bool:
    if type(value) is not str or _UTC_PATTERN.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return parsed.year >= 2000 and parsed.replace(
            tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") == value
    except (ValueError, OverflowError):
        return False


def evaluate_d517_evidence_ledger(ledger: object) -> dict[str, object]:
    """Recognize the *unverified* D5-17 ledger, without granting authority.

    A modified ledger claiming completion or broker verification is rejected,
    not treated as evidence that an external safety review happened.
    """
    rejected = _denied("LEDGER_REJECTED_FAIL_CLOSED")
    if type(ledger) is not dict:
        return rejected
    try:
        if (type(ledger.get("schema_version")) is not int
                or ledger["schema_version"] != 1
                or ledger.get("id") != "P0-01-D5-17-ACCOUNT-EVIDENCE-RECONCILIATION"
                or ledger.get("scope") != "SINGLE_MT4_ENVIRONMENT_DESIGN_ONLY"
                or ledger.get("account_identity_consistency") != "NOT_RECONCILED"
                or ledger.get("positions_status") != "UNKNOWN"
                or ledger.get("pending_orders_status") != "UNKNOWN"
                or ledger.get("ea_running_status") != "UNKNOWN"
                or ledger.get("verified_values", "MISSING") is not None
                or ledger.get("runtime_go_no_go") != "NO_GO"
                or ledger.get("phase_1") != "BLOCKED"):
            return rejected
        for k in ("broker_verified", "production_usable",
                  "orders_generated", "read_only_ex4_execution_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            if ledger.get(k) is not False:
                return rejected
        if (ledger.get("inquiry_status") != "CANCELLED_DO_NOT_SEND"
                or ledger.get("multiple_demo_accounts") != "OUT_OF_SCOPE"):
            return rejected
        approvals = ledger.get("approvals")
        if (type(approvals) is not dict or not approvals
                or any(v is not False for v in approvals.values())):
            return rejected
        checks = ledger.get("check_states")
        if (type(checks) is not list or len(checks) != 8
                or {x["id"] for x in checks if type(x) is dict} != _STATES):
            return rejected
        if any(type(x) is not dict or x.get("status") != "NOT_PERFORMED"
               or x.get("evidence", "MISSING") is not None for x in checks):
            return rejected
        records = ledger.get("evidence")
        if (type(records) is not list or len(records) != 2
                or any(type(x) is not dict for x in records)):
            return rejected
        by_id = {r.get("id"): r for r in records}
        if len(by_id) != 2 or set(by_id) != {"EV-OLD", "EV-NEW"}:
            return rejected
        old, new = by_id["EV-OLD"], by_id["EV-NEW"]
        if (old.get("source_type") != "PRIOR_USER_VISUAL_REPORT"
                or old.get("scope_label") != "PRIOR_MT4_DEMO_A"
                or old.get("positions_or_pending_orders") != "PRESENT_REPORTED_PREVIOUSLY"
                or old.get("macd_sample") != "OBSERVED_PREVIOUSLY"
                or new.get("source_type") != "LATEST_USER_REPORTED"
                or new.get("scope_label") != "EXISTING_RAKUTEN_ACCOUNT_UNSPECIFIED"
                or new.get("positions_and_orders") != "NONE_REPORTED"
                or new.get("usage") != "DORMANT_REPORTED"):
            return rejected
        if any(r.get("broker_confirmed") is not False
               or r.get("current_state_verified") is not False
               or r.get("observed_at_utc", "MISSING") is not None
               or r.get("reported_at_utc", "MISSING") is not None
               for r in records):
            return rejected
    except (TypeError, KeyError, ValueError):
        return rejected
    return _denied("D517_REPORTS_NOT_RECONCILED_NO_GO", records_reviewed=2)


def evaluate_synthetic_evidence_records(bundle: object) -> dict[str, object]:
    """Compare bounded *synthetic* records without asserting live facts.

    Compare contradictory claims only within the same synthetic scope and
    identical observation instant. Changing timestamps may reflect changed
    state; it is insufficient evidence of the current state, not a conflict.
    """
    rejected = _denied("SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")
    if type(bundle) is not dict:
        return rejected
    if (bundle.get("origin") != "SYNTHETIC_ONLY"
            or type(bundle.get("schema_version")) is not int
            or bundle["schema_version"] != 1
            or type(bundle.get("account_scope")) is not str
            or _SCOPE_PATTERN.fullmatch(bundle["account_scope"]) is None
            or set(bundle) != {"origin", "schema_version", "account_scope", "records"}):
        return rejected
    records = bundle["records"]
    if type(records) is not list or not 1 <= len(records) <= 20:
        return rejected
    seen_ids: set[str] = set()
    scopes: set[str] = set()
    times: set[str | None] = set()
    sources: set[str] = set()
    by_instant: dict[tuple[str, str], dict[str, str]] = {}
    conflict = False
    try:
        for record in records:
            if type(record) is not dict or set(record) != _RECORD_FIELDS:
                return rejected
            eid = record["evidence_id"]
            scope = record["account_scope"]
            source = record["source_kind"]
            stamp = record["observed_at_utc"]
            if (type(eid) is not str or _ID_PATTERN.fullmatch(eid) is None
                    or eid in seen_ids or type(scope) is not str
                    or _SCOPE_PATTERN.fullmatch(scope) is None
                    or type(source) is not str or source not in _SOURCES
                    or (stamp is not None and not _utc_timestamp(stamp))
                    or any(type(record[k]) is not str or record[k] not in _VALUES
                           for k in _FIELDS)):
                return rejected
            seen_ids.add(eid)
            scopes.add(scope)
            sources.add(source)
            times.add(stamp)
            if stamp is not None:
                group = by_instant.setdefault((scope, stamp), {})
                for field in _FIELDS:
                    value = record[field]
                    if value == "UNKNOWN":
                        continue
                    if field in group and group[field] != value:
                        conflict = True
                    group[field] = value
    except (KeyError, TypeError, ValueError):
        return rejected
    if scopes != {bundle["account_scope"]}:
        return _denied("ACCOUNT_SCOPE_MISMATCH_NO_GO",
                       records_reviewed=len(records))
    if conflict:
        return _denied("EVIDENCE_CONFLICT_NO_GO",
                       records_reviewed=len(records))
    if (len(times) == 1 and None not in times and len(sources) >= 2
            and len(records) >= 2):
        only = next(iter(by_instant.values()))
        if all(only.get(k) in ("PRESENT", "ABSENT") for k in _FIELDS):
            return _denied("SYNTHETIC_INTERNALLY_CONSISTENT_NO_GO",
                           records_reviewed=len(records))
    return _denied("EVIDENCE_INSUFFICIENT_NO_GO",
                   records_reviewed=len(records))
