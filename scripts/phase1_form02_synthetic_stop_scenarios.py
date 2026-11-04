"""RISK-3P-07 / FORM-02: synthetic stop/order-kind shape review ONLY.

No live broker, quote feed, terminal, files, keys, order dispatch, or SL edits.
The sole positive shape result is NOT a bound on stop-loss execution or P&L.
Do not connect this to order approval or treat it as an FX-SAF implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from scripts.phase1_three_pair_synthetic_stop_conversion import PAIRS


_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)
_KINDS = ("MARKET", "LIMIT", "STOP")
_STAGES = ("CANDIDATE", "PENDING", "POSITION")
_OUTCOMES = {
    "CANDIDATE": "NOT_DISPATCHED",
    "PENDING": "PENDING_CONFIRMED",
    "POSITION": "FILLED_CONFIRMED",
}


@dataclass(frozen=True)
class SyntheticStopCase:
    pair: str
    side: str
    order_kind: str
    stage: str
    planned_entry: str | None
    trigger_price: str | None
    fill_price: str | None
    stop_price: str | None
    quote_bid: str
    quote_ask: str
    epoch: int
    quote_epoch: int
    stop_ack_epoch: int | None
    server_stop_state: str
    stop_update_state: str
    execution_state: str
    gap_state: str
    broker_state_reconciled: bool
    pending_state_reconciled: bool
    inflight_state_reconciled: bool


@dataclass(frozen=True)
class Review:
    reason: str
    synthetic_shape_reviewed: bool = False
    reference_origin: str | None = None
    reference_price: str | None = None
    measured_loss_jpy: None = None
    finite_gap_loss_bound_verified: bool = False
    real_broker_stop_verified: bool = False
    trading_contract_verified: bool = False
    form02_approved: bool = False
    production_authorized: bool = False
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    order_allowed: bool = False
    stop_release_allowed: bool = False
    automatic_retry_allowed: bool = False
    result_authorizes_protective_order_change: bool = False
    verified_values: None = None


def _reject(reason: str) -> Review:
    return Review(reason)


def _number(value: object) -> Decimal | None:
    if (type(value) is not str or len(value) > 40
            or _DECIMAL.fullmatch(value) is None):
        return None
    try:
        n = Decimal(value)
        if (not n.is_finite() or not (Decimal("1e-12") <= n <= Decimal("1e12"))
                or len(n.normalize().as_tuple().digits) > 18):
            return None
        return n
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def review_synthetic_stop_shape(case: object) -> Review:
    """Offline consistency check for a fictional single-order snapshot.

    MARKET: planned_entry is only a reference, never a guaranteed fill.
    LIMIT/STOP: trigger_price is a proposed activation reference.
    POSITION: fill_price supersedes planned entry or activation reference.
    A returned shape-review result still cannot authorize any order.
    """
    if type(case) is not SyntheticStopCase:
        return _reject("INVALID_CASE")
    if (type(case.pair) is not str or case.pair not in PAIRS
            or type(case.side) is not str or case.side not in ("BUY", "SELL")
            or type(case.order_kind) is not str or case.order_kind not in _KINDS
            or type(case.stage) is not str or case.stage not in _STAGES):
        return _reject("PAIR_SIDE_KIND_OR_STAGE_UNSUPPORTED")
    if (case.broker_state_reconciled is not True
            or case.pending_state_reconciled is not True
            or case.inflight_state_reconciled is not True):
        return _reject("BROKER_PENDING_OR_INFLIGHT_UNKNOWN")
    if (type(case.epoch) is not int or case.epoch < 0
            or type(case.quote_epoch) is not int
            or case.quote_epoch != case.epoch):
        return _reject("STALE_OR_INVALID_SYNTHETIC_QUOTE_EPOCH")
    bid, ask = _number(case.quote_bid), _number(case.quote_ask)
    if bid is None or ask is None or bid > ask:
        return _reject("QUOTE_MISSING_OR_CROSSED")
    if (type(case.gap_state) is not str
            or case.gap_state != "NO_GAP_IN_SYNTHETIC_EXAMPLE"):
        return _reject("GAP_OR_SLIPPAGE_UNBOUNDED")
    if (type(case.stop_update_state) is not str
            or case.stop_update_state not in ("NONE", "CONFIRMED")):
        return _reject("STOP_REPLACE_OR_REMOVAL_UNCONFIRMED")
    if case.stage != "POSITION" and case.stop_update_state != "NONE":
        return _reject("STOP_REPLACE_ON_NONPOSITION")
    if case.order_kind == "MARKET" and case.stage == "PENDING":
        return _reject("UNSUPPORTED_MARKET_PENDING")
    if (type(case.execution_state) is not str
            or case.execution_state != _OUTCOMES[case.stage]):
        return _reject("EXECUTION_PARTIAL_OR_UNKNOWN")
    if case.stage == "CANDIDATE":
        if case.server_stop_state != "NOT_SENT" or case.stop_ack_epoch is not None:
            return _reject("CANDIDATE_CANNOT_CLAIM_SERVER_STOP")
    else:
        if (case.server_stop_state != "CONFIRMED"
                or type(case.stop_ack_epoch) is not int
                or case.stop_ack_epoch != case.epoch):
            return _reject("SERVER_STOP_MISSING_OR_STALE")
    if case.order_kind == "MARKET":
        if case.trigger_price is not None:
            return _reject("MARKET_WITH_UNEXPECTED_TRIGGER")
    else:
        trigger = _number(case.trigger_price)
        if trigger is None:
            return _reject("PENDING_TRIGGER_MISSING_OR_INVALID")
        if case.stage != "POSITION":
            if case.order_kind == "LIMIT":
                plausible = (trigger < ask if case.side == "BUY" else trigger > bid)
            else:
                plausible = (trigger > ask if case.side == "BUY" else trigger < bid)
            if not plausible:
                return _reject("TRIGGER_NOT_ON_EXPECTED_SIDE_OF_SYNTHETIC_QUOTE")
    if case.stage == "POSITION":
        reference = _number(case.fill_price)
        if reference is None:
            return _reject("POSITION_FILL_UNCONFIRMED")
        origin = "SYNTHETIC_RECORDED_FILL"
    else:
        if case.fill_price is not None:
            return _reject("UNEXPECTED_FILL_BEFORE_POSITION")
        if case.order_kind == "MARKET":
            reference = _number(case.planned_entry)
            origin = "UNGUARANTEED_MARKET_PLAN"
        else:
            reference = _number(case.trigger_price)
            origin = "UNGUARANTEED_PENDING_TRIGGER"
        if reference is None:
            return _reject("ENTRY_REFERENCE_MISSING")
    stop = _number(case.stop_price)
    if stop is None:
        return _reject("STOP_PRICE_MISSING_OR_INVALID")
    if ((case.side == "BUY" and stop >= reference)
            or (case.side == "SELL" and stop <= reference)):
        return _reject("STOP_WRONG_SIDE_OR_ZERO_DISTANCE")
    # No positive risk output and NO authorization, including for this shape.
    return Review("SYNTHETIC_SHAPE_ONLY_NO_LOSS_BOUND_NO_GO",
                  synthetic_shape_reviewed=True,
                  reference_origin=origin,
                  reference_price=str(reference))
