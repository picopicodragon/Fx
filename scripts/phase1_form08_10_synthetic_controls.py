"""RISK-3P-13..15: offline examples for FORM-08 (day), 09 (DD), 10 (time).

NOT an authorized financial ledger, DD engine, freshness policy, live risk
calculator, clock authority or trading component. No I/O, broker, OS clock
reads or mutable persistent state. All Review objects are NO_GO/BLOCKED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, time
from decimal import Decimal, InvalidOperation
import re
from zoneinfo import ZoneInfo


NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)
STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z", re.ASCII)
SOURCES = ("ACCOUNT", "POSITIONS", "PENDING", "FX_QUOTES", "CONVERSION", "LEDGER")


@dataclass(frozen=True)
class Daily:
    opening_equity_jpy: str
    current_equity_jpy: str
    net_external_cashflows_jpy: str
    opening_anchor_utc: str
    asof_utc: str
    account_epoch: int
    ledger_epoch: int
    cashflows_reconciled: bool
    pnl_reconciled: bool
    corrections_complete: bool
    profit_offset_status: str


@dataclass(frozen=True)
class Drawdown:
    current_unit_value: str
    historic_high_water_unit_value: str
    state_epoch: int
    persistent_hwm_verified: bool
    flow_unitization_reconciled: bool
    restart_consistent: bool
    existing_stop_latched: bool
    hwm_source: str


@dataclass(frozen=True)
class Observation:
    source: str
    observed_at_utc: str
    epoch: int


@dataclass(frozen=True)
class Freshness:
    decision_utc: str
    epoch: int
    observations: tuple[Observation, ...]
    source_age_policies_approved: bool
    clock_discontinuity_detected: bool
    market_hours_confirmed: bool


@dataclass(frozen=True)
class Review:
    reason: str
    arithmetic_only: bool = False
    daily_illustrative_loss_jpy: str | None = None
    daily_illustrative_limit_jpy: str | None = None
    daily_stop_triggered_in_synthetic_example: bool | None = None
    dd_illustrative_fraction: str | None = None
    dd4_triggered_in_synthetic_example: bool | None = None
    dd5_triggered_in_synthetic_example: bool | None = None
    freshness_policy_verified: bool = False
    cashflows_or_hwm_real_evidence_verified: bool = False
    broker_account_verified: bool = False
    owner_approval_recorded: bool = False
    operational_stop_release_allowed: bool = False
    order_allowed: bool = False
    automatic_retry_allowed: bool = False
    production_authorized: bool = False
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    verified_values: None = None


def _deny(reason: str) -> Review:
    return Review(reason=reason)


def _amount(value: object, *, signed: bool = False, zero: bool = False):
    if (type(value) is not str or len(value) > 40
            or NUMBER.fullmatch(value) is None):
        return None
    if not signed and value.startswith("-"):
        return None
    try:
        n = Decimal(value)
        if (not n.is_finite() or abs(n) > Decimal("1e12")
                or (not signed and (n < 0 if zero else n <= 0))
                or (n != 0 and abs(n) < Decimal("1e-12"))
                or len(n.normalize().as_tuple().digits) > 18):
            return None
        return n
    except (ValueError, InvalidOperation, ArithmeticError):
        return None


def _utc_stamp(value: object) -> datetime | None:
    if type(value) is not str or not STAMP.fullmatch(value):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.year < 2000 or dt.tzinfo != timezone.utc:
            return None
        return dt
    except (ValueError, OverflowError, TypeError):
        return None


def ny17_anchor_utc(asof: datetime) -> datetime:
    """Evaluate a GIVEN aware instant; never read the current system clock."""
    if (type(asof) is not datetime or asof.tzinfo is None
            or asof.utcoffset() is None):
        raise ValueError("requires an aware instant")
    ny = asof.astimezone(ZoneInfo("America/New_York"))
    boundary_date = ny.date() if ny.timetz().replace(tzinfo=None) >= time(17) else (
        ny.date() - timedelta(days=1))
    return datetime.combine(boundary_date, time(17),
                            ZoneInfo("America/New_York")).astimezone(timezone.utc)


def review_daily(daily: object) -> Review:
    if type(daily) is not Daily:
        return _deny("INVALID_DAILY_INPUT")
    opening = _amount(daily.opening_equity_jpy)
    current = _amount(daily.current_equity_jpy, zero=True)
    net_flow = _amount(daily.net_external_cashflows_jpy, signed=True)
    if any(x is None for x in (opening, current, net_flow)):
        return _deny("DAILY_AMOUNT_OR_DENOMINATOR_UNCOMPUTABLE")
    anchor = _utc_stamp(daily.opening_anchor_utc)
    asof = _utc_stamp(daily.asof_utc)
    if anchor is None or asof is None or anchor > asof:
        return _deny("NY17_BOUNDARY_OR_CLOCK_INVALID")
    if anchor != ny17_anchor_utc(asof):
        return _deny("NY17_BOUNDARY_OR_CLOCK_INVALID")
    if (type(daily.account_epoch) is not int or daily.account_epoch < 0
            or type(daily.ledger_epoch) is not int
            or daily.ledger_epoch != daily.account_epoch):
        return _deny("DAILY_ACCOUNT_LEDGER_EPOCH_MISMATCH")
    if (daily.cashflows_reconciled is not True
            or daily.pnl_reconciled is not True
            or daily.corrections_complete is not True):
        return _deny("DAILY_EXTERNAL_FLOW_OR_PNL_NOT_RECONCILED")
    if daily.profit_offset_status != "SYNTHETIC_COMPARISON_ONLY":
        return _deny("DAILY_PROFIT_OFFSET_UNDECIDED")
    # This is only one proposed illustrative normalization, not a formal
    # PnL/fee/profit-offset or external-cashflow booking policy.
    loss = max(Decimal(0), opening + net_flow - current)
    bound = opening * Decimal("0.015")
    return Review(
        reason="SYNTHETIC_DAILY_STOP_EXAMPLE_NO_GO" if loss >= bound
        else "SYNTHETIC_DAILY_COMPARISON_ONLY_NO_GO",
        arithmetic_only=True,
        daily_illustrative_loss_jpy=str(loss),
        daily_illustrative_limit_jpy=str(bound),
        daily_stop_triggered_in_synthetic_example=loss >= bound,
    )


def review_dd(dd: object) -> Review:
    if type(dd) is not Drawdown:
        return _deny("INVALID_DD_INPUT")
    current = _amount(dd.current_unit_value)
    peak = _amount(dd.historic_high_water_unit_value)
    if current is None or peak is None or current > peak:
        return _deny("UNIT_VALUE_OR_HWM_UNRELIABLE")
    if type(dd.state_epoch) is not int or dd.state_epoch < 0:
        return _deny("INVALID_DD_STATE_EPOCH")
    if (dd.persistent_hwm_verified is not True
            or dd.flow_unitization_reconciled is not True
            or dd.restart_consistent is not True
            or dd.existing_stop_latched is not True):
        return _deny("DD_HWM_OR_STOP_PERSISTENCE_UNKNOWN")
    if dd.hwm_source != "SYNTHETIC_PRIOR_PEAK_ONLY":
        return _deny("DD_HWM_SOURCE_UNVERIFIED")
    with __import__("decimal").localcontext() as context:
        context.prec = 48
        drawdown = (peak - current) / peak
    return Review(
        reason="SYNTHETIC_DD_STOP_EXAMPLE_NO_GO"
        if drawdown >= Decimal("0.04")
        else "SYNTHETIC_DD_COMPARISON_ONLY_NO_GO",
        arithmetic_only=True,
        dd_illustrative_fraction=str(drawdown),
        dd4_triggered_in_synthetic_example=drawdown >= Decimal("0.04"),
        dd5_triggered_in_synthetic_example=drawdown >= Decimal("0.05"),
    )


def review_freshness(value: object) -> Review:
    if type(value) is not Freshness:
        return _deny("INVALID_TIME_REVIEW")
    decision = _utc_stamp(value.decision_utc)
    if decision is None or type(value.epoch) is not int or value.epoch < 0:
        return _deny("DECISION_CLOCK_OR_EPOCH_INVALID")
    if value.clock_discontinuity_detected is not False:
        return _deny("CLOCK_DISCONTINUITY_OR_ROLLBACK")
    if type(value.observations) not in (tuple, list) or len(value.observations) != len(SOURCES):
        return _deny("TIME_SOURCES_INCOMPLETE")
    names: set[str] = set()
    for item in value.observations:
        if type(item) is not Observation or item.source not in SOURCES:
            return _deny("INVALID_TIME_SOURCE")
        if item.source in names:
            return _deny("DUPLICATE_TIME_SOURCE")
        names.add(item.source)
        stamp = _utc_stamp(item.observed_at_utc)
        if stamp is None or stamp > decision:
            return _deny("TIME_SOURCE_MISSING_OR_FUTURE")
        if type(item.epoch) is not int or item.epoch != value.epoch:
            return _deny("CAUSAL_GENERATION_MISMATCH")
    if value.market_hours_confirmed is not True:
        return _deny("MARKET_HOURS_UNCONFIRMED")
    if value.source_age_policies_approved is not False:
        # A boolean "approved" claim cannot substitute per-source
        # explicit policy with measured bounded age and approval provenance.
        return _deny("FALSE_UNIVERSAL_FRESHNESS_APPROVAL")
    # Not checking an invented generic TTL means even old timestamps do NOT
    # produce a positive "fresh" result. No real-time authority is granted.
    return Review(reason="SYNTHETIC_TIME_SHAPE_ONLY_NO_TTL_NO_GO",
                  arithmetic_only=True)
