"""RISK-3P-01: unconnected three-pair currency-exposure arithmetic.

Pure synthetic fixtures ONLY. Not an order-sizing, risk approval, FX pricing,
broker reconciliation, market data, or trading module. All outcomes are NO_GO.
The supplied 'max_loss_jpy' is an illustrative assertion, NOT a verified SL
risk estimate. No network, host, MT4, credentials, disk, or clock I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
import re


PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
# Defensive ceilings apply only to this fictional arithmetic fixture,
# not to real account settings, broker lot limits or authorization.
MAX_SYNTHETIC_TRADES = 128
MAX_SIMULATED_ID_CHARS = 128
MAX_SYNTHETIC_ASOF = (1 << 63) - 1
DECIMAL_WORK_PRECISION = 96
CURRENCIES = ("USD", "EUR", "JPY")
_STATUSES = frozenset({"POSITION", "PENDING", "CANDIDATE"})
_NUMBER = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)


@dataclass(frozen=True)
class Quote:
    pair: str
    bid: str
    ask: str
    observed_at: int
    snapshot_id: str


@dataclass(frozen=True)
class Trade:
    trade_id: str
    pair: str
    side: str
    status: str
    base_units: str
    max_loss_jpy: str


@dataclass(frozen=True)
class Review:
    reason: str
    arithmetic_complete: bool = False
    net_native: tuple[tuple[str, str], ...] | None = None
    gross_native: tuple[tuple[str, str], ...] | None = None
    gross_currency_legs_jpy: str | None = None
    total_max_loss_jpy: str | None = None
    candidate_max_loss_jpy: str | None = None
    candidate_exceeds_existing_limit: bool | None = None
    total_exceeds_existing_limit: bool | None = None
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    order_allowed: bool = False
    automatic_retry_allowed: bool = False
    stop_release_allowed: bool = False
    verified_values: None = None


def _decimal(value: object) -> Decimal | None:
    """Accept a bounded, positive-notation decimal *string* only."""
    if (type(value) is not str or len(value) > 40
            or _NUMBER.fullmatch(value) is None):
        return None
    result = Decimal(value)
    return result if result.is_finite() else None


def _reject(reason: str) -> Review:
    return Review(reason=reason)


def review_synthetic_portfolio(
    quotes: object, trades: object, *, asof: object,
    snapshot_id: object, equity_jpy: object,
    positions_reconciled: object, pending_orders_reconciled: object,
) -> Review:
    """Evaluate a fictional all-fill scenario without granting permission.

    Positive base position purchases base/shorts quote at the simulated ask.
    Negative base position sells base/longs quote at the simulated bid.
    Native legs are summed for net and by absolute value for gross. Positive
    JPY conversion uses only an illustrative ask-side upper quote; it is NOT
    an actual liquidation, PnL, or loss-risk calculation.
    """
    if positions_reconciled is not True or pending_orders_reconciled is not True:
        return _reject("ACCOUNT_OR_PENDING_STATE_UNKNOWN")
    if (type(asof) is not int or not 0 <= asof <= MAX_SYNTHETIC_ASOF
            or type(snapshot_id) is not str or not snapshot_id
            or len(snapshot_id) > MAX_SIMULATED_ID_CHARS):
        return _reject("INVALID_SYNTHETIC_SNAPSHOT_IDENTITY")
    equity = _decimal(equity_jpy)
    if equity is None or equity <= 0:
        return _reject("INVALID_SYNTHETIC_EQUITY")
    if type(quotes) is not dict or set(quotes) != set(PAIRS):
        return _reject("QUOTE_SET_INCOMPLETE_OR_EXTRA")
    validated: dict[str, tuple[Decimal, Decimal]] = {}
    for pair in PAIRS:
        quote = quotes[pair]
        if type(quote) is not Quote or quote.pair != pair:
            return _reject("INVALID_QUOTE")
        if (type(quote.observed_at) is not int or quote.observed_at != asof
                or type(quote.snapshot_id) is not str
                or quote.snapshot_id != snapshot_id):
            return _reject("STALE_OR_MIXED_PRICE_SNAPSHOT")
        bid, ask = _decimal(quote.bid), _decimal(quote.ask)
        if bid is None or ask is None or bid <= 0 or ask <= 0 or bid > ask:
            return _reject("INVALID_BID_ASK")
        validated[pair] = (bid, ask)
    if type(trades) not in (tuple, list) or not trades:
        return _reject("MISSING_CANDIDATE_OR_TRADES")
    if len(trades) > MAX_SYNTHETIC_TRADES:
        return _reject("SYNTHETIC_WORKLOAD_BOUND_EXCEEDED")

    # Preserve sub-yen boundary exceedances in synthetic high-scale amounts.
    # With <=40 decimal digits per operand and <=128 tickets, 96 digits
    # accommodate product, aggregation, and both hard-limit comparisons.
    with localcontext() as ctx:
        ctx.prec = DECIMAL_WORK_PRECISION
        net = {currency: Decimal(0) for currency in CURRENCIES}
        gross = {currency: Decimal(0) for currency in CURRENCIES}
        seen: set[str] = set()
        candidate_count = 0
        candidate_loss = Decimal(0)
        total_loss = Decimal(0)
        for trade in trades:
            if type(trade) is not Trade:
                return _reject("INVALID_TRADE")
            if (type(trade.trade_id) is not str or not trade.trade_id
                    or len(trade.trade_id) > MAX_SIMULATED_ID_CHARS
                    or trade.trade_id in seen):
                return _reject("DUPLICATE_OR_INVALID_TRADE_ID")
            seen.add(trade.trade_id)
            if (type(trade.pair) is not str or trade.pair not in PAIRS
                    or type(trade.side) is not str
                    or trade.side not in ("BUY", "SELL")
                    or type(trade.status) is not str
                    or trade.status not in _STATUSES):
                return _reject("UNSUPPORTED_PAIR_SIDE_OR_STATUS")
            units, asserted_loss = _decimal(trade.base_units), _decimal(trade.max_loss_jpy)
            if units is None or units <= 0 or asserted_loss is None or asserted_loss <= 0:
                return _reject("UNVERIFIABLE_SYNTHETIC_QUANTITY_OR_LOSS")
            if trade.status == "CANDIDATE":
                candidate_count += 1
                candidate_loss += asserted_loss
            total_loss += asserted_loss
            base, quote_ccy = trade.pair.split("/")
            bid, ask = validated[trade.pair]
            sign = Decimal(1) if trade.side == "BUY" else Decimal(-1)
            effective_price = ask if sign > 0 else bid
            legs = ((base, sign * units),
                    (quote_ccy, -sign * units * effective_price))
            for currency, amount in legs:
                net[currency] += amount
                gross[currency] += abs(amount)
        if candidate_count != 1:
            return _reject("EXACTLY_ONE_NEW_CANDIDATE_REQUIRED")

        # Illustrative positive gross-equivalent only. The ask-side upper bound
        # for *gross* is not a certified value for risk, settlement, or liquidation.
        gross_jpy = (gross["JPY"]
                     + gross["USD"] * validated["USD/JPY"][1]
                     + gross["EUR"] * validated["EUR/JPY"][1])
        candidate_over = candidate_loss > equity * Decimal("0.005")
        total_over = total_loss > equity * Decimal("0.01")
        return Review(
            reason=("EXISTING_HARD_LIMIT_OVER_IN_SYNTHETIC_INPUT"
                    if candidate_over or total_over
                    else "SYNTHETIC_ARITHMETIC_ONLY_NOT_AUTHORIZED"),
            arithmetic_complete=True,
            net_native=tuple((c, str(net[c])) for c in CURRENCIES),
            gross_native=tuple((c, str(gross[c])) for c in CURRENCIES),
            gross_currency_legs_jpy=str(gross_jpy),
            total_max_loss_jpy=str(total_loss),
            candidate_max_loss_jpy=str(candidate_loss),
            candidate_exceeds_existing_limit=candidate_over,
            total_exceeds_existing_limit=total_over,
        )
