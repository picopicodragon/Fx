"""RISK-3P-04: synthetic three-pair stop-distance and JPY-conversion review.

This deliberately NON-OPERATIONAL demonstration contains no approved broker
contract, fill model, risk budget authority, or source of market prices.
All outputs retain BLOCKED/NO_GO and forbid orders and STOP release.
No filesystem, clock, network, account, MT4, or live-trading operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, InvalidOperation, localcontext
import re


PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
STATUSES = frozenset(("POSITION", "PENDING", "CANDIDATE"))
_TOKEN = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)
SYNTHETIC_TRADE_LIMIT = Decimal("0.005")
SYNTHETIC_AGGREGATE_LIMIT = Decimal("0.01")
# These are defensive simulation limits, not approved broker specifications.
MAX_SYNTHETIC_TICKETS = 128
MAX_SYNTHETIC_ID_CHARS = 128
MAX_SYNTHETIC_ASOF = (1 << 63) - 1
DECIMAL_WORK_PRECISION = 96


@dataclass(frozen=True)
class Contract:
    pair: str
    base_units_per_lot: str
    min_lot: str
    lot_step: str
    max_lot: str


@dataclass(frozen=True)
class Quote:
    pair: str
    bid: str
    ask: str
    observed_at: int
    snapshot_id: str


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    pair: str
    side: str
    status: str
    volume_lots: str
    planned_entry: str
    stop_price: str
    adverse_buffer_quote_per_base: str
    additional_cost_jpy: str
    snapshot_id: str


@dataclass(frozen=True)
class Review:
    reason: str
    illustrative_complete: bool = False
    per_ticket_illustrative_loss_jpy: tuple[tuple[str, str], ...] | None = None
    candidate_illustrative_loss_jpy: str | None = None
    total_illustrative_loss_jpy: str | None = None
    candidate_exceeds_existing_fraction: bool | None = None
    aggregate_exceeds_existing_fraction: bool | None = None
    quote_conversion_method: str = "UNAPPROVED_SYNTHETIC_ONLY"
    broker_contract_verified: bool = False
    costs_verified: bool = False
    stop_execution_guaranteed: bool = False
    result_authorizes_trade: bool = False
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    order_allowed: bool = False
    stop_release_allowed: bool = False
    automatic_retry_allowed: bool = False
    verified_values: None = None


def _reject(reason: str) -> Review:
    return Review(reason)


def _parse(value: object, *, zero: bool = False) -> Decimal | None:
    """Strict bounded decimal strings. No float or bool coercion."""
    if (type(value) is not str or len(value) > 40 or
            _TOKEN.fullmatch(value) is None):
        return None
    try:
        number = Decimal(value)
        # normalize() rounds at the caller's ambient Decimal precision.
        # Count the exact input coefficient instead, ignoring trailing zeros,
        # so low-precision caller settings cannot launder 19+ significant
        # digits into the allowed 18-digit fictional contract.
        digits = number.as_tuple().digits
        significant = len(digits)
        while significant > 1 and digits[significant - 1] == 0:
            significant -= 1
        if (not number.is_finite() or number > Decimal("1e12")
                or (number < 0 if zero else number <= 0)
                or (number != 0 and number < Decimal("1e-12"))
                or significant > 18):
            return None
        return number
    except (InvalidOperation, ArithmeticError, ValueError):
        return None


def review_synthetic_stop_risk(
    contracts: object, quotes: object, tickets: object, *,
    equity_jpy: object, asof: object, snapshot_id: object,
    positions_reconciled: object, pending_reconciled: object,
    inflight_reservations_reconciled: object,
) -> Review:
    """Evaluate one fictional snapshot. No positive authorization ever.

    BUY theoretical quote loss = (planned_entry - stop + explicit_buffer)
                                 * volume_lots * base_units_per_lot.
    SELL theoretical quote loss = (stop - planned_entry + explicit_buffer)
                                  * volume_lots * base_units_per_lot.
    For EUR/USD alone a *positive* USD quote loss is multiplied by the
    fictional USD/JPY ASK as a pessimistic illustration, NOT a broker-approved
    liquidation/JPY conversion rule. JPY-quoted pairs use factor 1.
    All three pair quotes are required to have exactly one snapshot identity.
    Explicit added JPY costs are required; zero is only a synthetic assumption.
    Existing, pending and candidate loss illustrations are NOT NETTED.
    """
    if (positions_reconciled is not True or pending_reconciled is not True
            or inflight_reservations_reconciled is not True):
        return _reject("BROKER_OR_INFLIGHT_STATE_UNKNOWN")
    if (type(asof) is not int or not 0 <= asof <= MAX_SYNTHETIC_ASOF
            or type(snapshot_id) is not str or not snapshot_id
            or len(snapshot_id) > MAX_SYNTHETIC_ID_CHARS
            or not snapshot_id.isprintable()):
        return _reject("MISSING_OR_INVALID_SNAPSHOT_IDENTITY")
    equity = _parse(equity_jpy)
    if equity is None:
        return _reject("MISSING_OR_INVALID_EQUITY")
    if (type(contracts) is not dict or set(contracts) != set(PAIRS)):
        return _reject("CONTRACT_SET_INCOMPLETE")
    checked_contracts: dict[str, tuple[Decimal, ...]] = {}
    for pair in PAIRS:
        row = contracts[pair]
        if type(row) is not Contract or row.pair != pair:
            return _reject("INVALID_SYNTHETIC_CONTRACT")
        values = tuple(_parse(getattr(row, field)) for field in (
            "base_units_per_lot", "min_lot", "lot_step", "max_lot"))
        if any(x is None for x in values):
            return _reject("CONTRACT_ATTRIBUTES_UNKNOWN")
        units, minimum, step, maximum = values
        if minimum > maximum or step > minimum:
            return _reject("INCOHERENT_SYNTHETIC_LOT_CONTRACT")
        checked_contracts[pair] = values
    if type(quotes) is not dict or set(quotes) != set(PAIRS):
        return _reject("QUOTE_SET_INCOMPLETE")
    checked_quotes: dict[str, tuple[Decimal, Decimal]] = {}
    for pair in PAIRS:
        q = quotes[pair]
        if type(q) is not Quote or q.pair != pair:
            return _reject("INVALID_QUOTE")
        if (type(q.observed_at) is not int or q.observed_at != asof
                or type(q.snapshot_id) is not str
                or q.snapshot_id != snapshot_id):
            return _reject("STALE_OR_MIXED_QUOTE")
        bid, ask = _parse(q.bid), _parse(q.ask)
        if bid is None or ask is None or bid > ask:
            return _reject("INVALID_BID_ASK")
        checked_quotes[pair] = (bid, ask)

    if type(tickets) not in (tuple, list) or not tickets:
        return _reject("MISSING_TICKETS")
    if len(tickets) > MAX_SYNTHETIC_TICKETS:
        return _reject("SYNTHETIC_WORKLOAD_BOUND_EXCEEDED")
    seen: set[str] = set()
    candidate_count = 0
    candidate_loss = Decimal(0)
    total_loss = Decimal(0)
    rows: list[tuple[str, str]] = []
    # Up to 18 significant decimal digits per validated input; products of
    # stop distance, units, volume and conversion plus 128 sums can exceed
    # the 48-digit context. 96 digits preserve those synthetic fractions.
    # Fresh Decimal context prevents inherited Emax/Emin, rounding modes and
    # traps from altering illustrative stop-loss arithmetic.
    with localcontext(Context(prec=DECIMAL_WORK_PRECISION)):
        for ticket in tickets:
            if type(ticket) is not Ticket:
                return _reject("INVALID_TICKET")
            if (type(ticket.ticket_id) is not str or not ticket.ticket_id
                    or len(ticket.ticket_id) > MAX_SYNTHETIC_ID_CHARS
                    or not ticket.ticket_id.isprintable()
                    or ticket.ticket_id in seen):
                return _reject("DUPLICATE_OR_MISSING_TICKET_ID")
            seen.add(ticket.ticket_id)
            if (type(ticket.pair) is not str or ticket.pair not in PAIRS
                    or type(ticket.side) is not str
                    or ticket.side not in ("BUY", "SELL")
                    or type(ticket.status) is not str
                    or ticket.status not in STATUSES):
                return _reject("INVALID_PAIR_SIDE_OR_ORDER_STATUS")
            if type(ticket.snapshot_id) is not str or ticket.snapshot_id != snapshot_id:
                return _reject("TICKET_SNAPSHOT_MISMATCH")
            vol = _parse(ticket.volume_lots)
            entry = _parse(ticket.planned_entry)
            stop = _parse(ticket.stop_price)
            buffer = _parse(ticket.adverse_buffer_quote_per_base, zero=True)
            costs = _parse(ticket.additional_cost_jpy, zero=True)
            if any(v is None for v in (vol, entry, stop, buffer, costs)):
                return _reject("STOP_VOLUME_OR_COST_UNCOMPUTABLE")
            units_per_lot, minimum, step, maximum = checked_contracts[ticket.pair]
            if (vol < minimum or vol > maximum
                    or (vol - minimum) % step != 0):
                return _reject("MIN_LOT_OR_STEP_NOT_SATISFIED")
            if ticket.side == "BUY":
                distance = entry - stop
            else:
                distance = stop - entry
            if distance <= 0:
                return _reject("MISSING_OR_WRONG_SIDE_STOP")
            quote_loss = (distance + buffer) * units_per_lot * vol
            conversion = (checked_quotes["USD/JPY"][1]
                          if ticket.pair == "EUR/USD" else Decimal(1))
            illustrative_jpy = quote_loss * conversion + costs
            # This is not a bound on real-world fills, gaps, or conversion.
            if not illustrative_jpy.is_finite() or illustrative_jpy < 0:
                return _reject("NUMERIC_OVERFLOW")
            rows.append((ticket.ticket_id, str(illustrative_jpy)))
            total_loss += illustrative_jpy
            if ticket.status == "CANDIDATE":
                candidate_count += 1
                candidate_loss += illustrative_jpy

        if candidate_count != 1:
            return _reject("EXACTLY_ONE_CANDIDATE_REQUIRED")
        candidate_over = candidate_loss > equity * SYNTHETIC_TRADE_LIMIT
        aggregate_over = total_loss > equity * SYNTHETIC_AGGREGATE_LIMIT
    return Review(
        reason=("SYNTHETIC_HARD_LIMIT_EXCEEDED_NEVER_AUTHORIZED"
                if candidate_over or aggregate_over
                else "SYNTHETIC_ARITHMETIC_ONLY_NEVER_AUTHORIZED"),
        illustrative_complete=True,
        per_ticket_illustrative_loss_jpy=tuple(rows),
        candidate_illustrative_loss_jpy=str(candidate_loss),
        total_illustrative_loss_jpy=str(total_loss),
        candidate_exceeds_existing_fraction=candidate_over,
        aggregate_exceeds_existing_fraction=aggregate_over,
    )
