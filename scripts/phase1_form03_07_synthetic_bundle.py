"""RISK-3P-08..12: one unconnected FORM-03..07 synthetic loss-input review.

NOT a certified loss upper bound, execution engine, market/broker data adapter,
or risk approval. All values are fictional. A computed result always forbids
order submission, retries and STOP release, irrespective of arithmetic.
No filesystem, network, clock, MT4, cloud, or account I/O is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import re

from scripts.phase1_three_pair_synthetic_stop_conversion import PAIRS


DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)
COST_TYPES = ("SPREAD", "COMMISSION", "SWAP", "SLIPPAGE")
ORDER_STATUSES = ("POSITION", "PENDING", "CANDIDATE", "RESERVED")
PORTIONS = ("WHOLE", "FILLED", "REMAINDER")


@dataclass(frozen=True)
class Quote:
    pair: str
    bid: str
    ask: str
    epoch: int
    snapshot_id: str


@dataclass(frozen=True)
class Cost:
    kind: str
    amount_jpy: str
    disposition: str
    asserted_in_base: bool


@dataclass(frozen=True)
class Slice:
    slice_id: str
    order_id: str
    pair: str
    side: str
    status: str
    portion: str
    volume_lots: str
    min_lot: str
    lot_step: str
    max_lot: str
    asserted_quote_loss: str
    quote_currency: str
    costs: tuple[Cost, ...]


@dataclass(frozen=True)
class Snapshot:
    epoch: int
    broker_epoch: int
    quote_epoch: int
    reservation_epoch: int
    snapshot_id: str
    broker_reconciled: bool
    pending_reconciled: bool
    inflight_reconciled: bool
    currency_exposure_reconciled: bool
    dispatch_state: str
    gap_assumption: str


@dataclass(frozen=True)
class Review:
    reason: str
    computed_synthetic_only: bool = False
    per_slice_jpy: tuple[tuple[str, str], ...] | None = None
    candidate_jpy: str | None = None
    aggregate_jpy: str | None = None
    candidate_above_existing_fraction: bool | None = None
    aggregate_above_existing_fraction: bool | None = None
    gross_loss_nonnetted: bool = True
    price_conversion_policy_approved: bool = False
    broker_contract_verified: bool = False
    costs_verified: bool = False
    account_and_order_state_verified: bool = False
    real_gap_loss_bound_verified: bool = False
    owner_approval_recorded: bool = False
    order_allowed: bool = False
    automatic_retry_allowed: bool = False
    stop_release_allowed: bool = False
    production_authorized: bool = False
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    verified_values: None = None


def _deny(reason: str) -> Review:
    return Review(reason=reason)


def _number(value: object, *, zero: bool = False) -> Decimal | None:
    if (type(value) is not str or len(value) > 40
            or DECIMAL.fullmatch(value) is None):
        return None
    try:
        result = Decimal(value)
        if (not result.is_finite() or result > Decimal("1e12")
                or (result < 0 if zero else result <= 0)
                or (result != 0 and result < Decimal("1e-12"))
                or len(result.normalize().as_tuple().digits) > 18):
            return None
        return result
    except (ValueError, InvalidOperation, ArithmeticError):
        return None


def review_synthetic_bundle(quotes: object, slices: object, state: object, *,
                            equity_jpy: object) -> Review:
    """Compute only an illustrative sum of asserted USD/JPY losses.

    FORM-03: positive synthetic USD-quote loss * USD/JPY ASK; JPY * 1.
    FORM-04: add only cost entries marked ADDITIONAL; costs marked INCLUDED
             must explicitly assert already-in-base accounting to avoid
             accidentally adding the same cost twice. Assertions are NOT proof.
    FORM-05: broker, price, reserved-risk and pending/inflight generations
             must all match, otherwise reject.
    FORM-06: positions, pending, reserved and candidates all add their
             asserted loss; opposite sides and triangular offsets never net.
             Partial fills require distinct FILLED/REMAINDER portions.
    FORM-07: no rounding, float coercion or lot adjustment; strict Decimal
             comparisons to existing equity-based 0.5%/1.0%.
    """
    if type(state) is not Snapshot:
        return _deny("INVALID_SNAPSHOT")
    if (type(state.epoch) is not int or state.epoch < 0
            or any(type(v) is not int or v != state.epoch for v in (
                state.broker_epoch, state.quote_epoch, state.reservation_epoch))
            or type(state.snapshot_id) is not str or not state.snapshot_id):
        return _deny("MIXED_OR_INVALID_DECISION_GENERATION")
    if not all(x is True for x in (
            state.broker_reconciled, state.pending_reconciled,
            state.inflight_reconciled, state.currency_exposure_reconciled)):
        return _deny("ACCOUNT_PENDING_RESERVATION_OR_EXPOSURE_UNRECONCILED")
    if (state.dispatch_state != "QUIESCENT_SYNTHETIC_ONLY"
            or type(state.dispatch_state) is not str):
        return _deny("DISPATCH_OR_CANCEL_OUTCOME_UNKNOWN")
    if (state.gap_assumption != "SYNTHETIC_BOUNDED_EXAMPLE_ONLY"
            or type(state.gap_assumption) is not str):
        return _deny("GAP_OR_SLIPPAGE_UNBOUNDED")
    equity = _number(equity_jpy)
    if equity is None:
        return _deny("EQUITY_UNCOMPUTABLE")
    if type(quotes) is not dict or set(quotes) != set(PAIRS):
        return _deny("INCOMPLETE_THREE_PAIR_QUOTE_SET")
    converted: dict[str, tuple[Decimal, Decimal]] = {}
    for pair in PAIRS:
        quote = quotes[pair]
        if type(quote) is not Quote or quote.pair != pair:
            return _deny("QUOTE_FORMAT_UNTRUSTWORTHY")
        if (type(quote.epoch) is not int or quote.epoch != state.quote_epoch
                or type(quote.snapshot_id) is not str
                or quote.snapshot_id != state.snapshot_id):
            return _deny("QUOTE_STALE_OR_MIXED_SNAPSHOT")
        bid, ask = _number(quote.bid), _number(quote.ask)
        if bid is None or ask is None or bid > ask:
            return _deny("QUOTE_BID_ASK_INVALID")
        converted[pair] = (bid, ask)
    if type(slices) not in (tuple, list) or not slices:
        return _deny("RISK_SLICES_MISSING")
    seen: set[str] = set()
    groups: dict[str, list[Slice]] = {}
    candidate_count = 0
    candidate_jpy = Decimal(0)
    aggregate_jpy = Decimal(0)
    results: list[tuple[str, str]] = []
    with localcontext() as context:
        context.prec = 48
        for item in slices:
            if type(item) is not Slice:
                return _deny("SLICE_FORMAT_INVALID")
            if (type(item.slice_id) is not str or not item.slice_id
                    or item.slice_id in seen
                    or type(item.order_id) is not str or not item.order_id):
                return _deny("DUPLICATE_OR_INVALID_SLICE_ID")
            seen.add(item.slice_id)
            if (type(item.pair) is not str or item.pair not in PAIRS
                    or type(item.side) is not str or item.side not in ("BUY", "SELL")
                    or type(item.status) is not str
                    or item.status not in ORDER_STATUSES
                    or type(item.portion) is not str
                    or item.portion not in PORTIONS):
                return _deny("UNSUPPORTED_RISK_SLICE_STATE")
            if item.quote_currency != item.pair.split("/")[1]:
                return _deny("WRONG_QUOTE_CURRENCY_FOR_PAIR")
            volume = _number(item.volume_lots)
            minimum = _number(item.min_lot)
            step = _number(item.lot_step)
            maximum = _number(item.max_lot)
            quote_loss = _number(item.asserted_quote_loss, zero=True)
            if any(x is None for x in (volume, minimum, step, maximum, quote_loss)):
                return _deny("MISSING_OR_INVALID_LOT_OR_LOSS_ASSERTION")
            if (step > minimum or maximum < minimum
                    or volume < minimum or volume > maximum
                    or (volume - minimum) % step != 0):
                return _deny("LOT_GRID_OR_BOUNDARY_INVALID")
            if type(item.costs) not in (tuple, list) or len(item.costs) != 4:
                return _deny("FOUR_COST_COMPONENTS_REQUIRED")
            kinds: set[str] = set()
            additional_cost = Decimal(0)
            for cost in item.costs:
                if (type(cost) is not Cost
                        or type(cost.kind) is not str
                        or cost.kind not in COST_TYPES
                        or cost.kind in kinds):
                    return _deny("DUPLICATE_OR_UNSUPPORTED_COST_KIND")
                kinds.add(cost.kind)
                amount = _number(cost.amount_jpy, zero=True)
                if amount is None:
                    return _deny("MISSING_OR_INVALID_COST_AMOUNT")
                if cost.disposition == "ADDITIONAL":
                    if cost.asserted_in_base is not False:
                        return _deny("COST_ACCOUNTING_CONTRADICTION")
                    additional_cost += amount
                elif cost.disposition == "INCLUDED_IN_BASE":
                    if cost.asserted_in_base is not True:
                        return _deny("COST_ACCOUNTING_CONTRADICTION")
                else:
                    return _deny("COST_ACCOUNTING_UNKNOWN")
            if kinds != set(COST_TYPES):
                return _deny("FOUR_COST_COMPONENTS_REQUIRED")
            conversion = (converted["USD/JPY"][1]
                          if item.quote_currency == "USD" else Decimal(1))
            jpy = quote_loss * conversion + additional_cost
            if not jpy.is_finite() or jpy > Decimal("1e22"):
                return _deny("SYNTHETIC_RESULT_OUT_OF_RANGE")
            results.append((item.slice_id, str(jpy)))
            aggregate_jpy += jpy
            if item.status == "CANDIDATE":
                candidate_count += 1
                candidate_jpy += jpy
            groups.setdefault(item.order_id, []).append(item)
        if candidate_count != 1:
            return _deny("EXACTLY_ONE_CANDIDATE_REQUIRED")
        for related in groups.values():
            if len(related) == 1:
                if related[0].portion != "WHOLE":
                    return _deny("ORPHAN_PARTIAL_FILL_PORTION")
            elif (len(related) != 2
                  or {x.portion for x in related} != {"FILLED", "REMAINDER"}
                  or {x.status for x in related} != {"POSITION", "PENDING"}
                  or {x.pair for x in related}.__len__() != 1
                  or {x.side for x in related}.__len__() != 1):
                return _deny("PARTIAL_FILL_NOT_RECONCILED")
        if aggregate_jpy > Decimal("1e22"):
            return _deny("SYNTHETIC_RESULT_OUT_OF_RANGE")
        candidate_over = candidate_jpy > equity * Decimal("0.005")
        aggregate_over = aggregate_jpy > equity * Decimal("0.010")
    return Review(
        reason=("SYNTHETIC_EXISTING_LIMIT_EXCEEDED_NO_GO"
                if candidate_over or aggregate_over
                else "SYNTHETIC_ASSERTED_LOSS_ONLY_NO_GO"),
        computed_synthetic_only=True,
        per_slice_jpy=tuple(results),
        candidate_jpy=str(candidate_jpy),
        aggregate_jpy=str(aggregate_jpy),
        candidate_above_existing_fraction=candidate_over,
        aggregate_above_existing_fraction=aggregate_over,
    )
