"""RISK-3P-01: unconnected three-pair currency-exposure arithmetic.

Pure synthetic fixtures ONLY. Not an order-sizing, risk approval, FX pricing,
broker reconciliation, market data, or trading module. All outcomes are NO_GO.
The supplied 'max_loss_jpy' is an illustrative assertion, NOT a verified SL
risk estimate. No network, host, MT4, credentials, disk, or clock I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Context, Decimal, Inexact, Rounded, localcontext
from fractions import Fraction

from scripts import phase1_three_pair_synthetic_stop_conversion as stop_conversion
import re


PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
# Defensive ceilings apply only to this fictional arithmetic fixture,
# not to real account settings, broker lot limits or authorization.
MAX_SYNTHETIC_TRADES = 128
MAX_SIMULATED_ID_CHARS = 128
MAX_SYNTHETIC_ASOF = (1 << 63) - 1
# Native legs multiply up to two 40-character coefficients, then the gross
# JPY conversion multiplies a third. Across 128 records, retaining both
# ~120-digit large terms and 10^-114 fractional tails requires more than
# 96 significant digits. 256 prevents silently understated mock exposure.
# These are illustrative figures only and never enable orders.
DECIMAL_WORK_PRECISION = 256
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
            or len(snapshot_id) > MAX_SIMULATED_ID_CHARS
            or not snapshot_id.isprintable()):
        return _reject("INVALID_SYNTHETIC_SNAPSHOT_IDENTITY")
    equity = _decimal(equity_jpy)
    if equity is None or equity <= 0:
        return _reject("INVALID_SYNTHETIC_EQUITY")
    if not _mock_plain_three_pair_map(quotes):
        return _reject("QUOTE_SET_INCOMPLETE_OR_EXTRA")
    validated: dict[str, tuple[Decimal, Decimal]] = {}
    for pair in PAIRS:
        quote = quotes[pair]
        if (type(quote) is not Quote or type(quote.pair) is not str
                or quote.pair != pair):
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

    # The old 96-digit context preserved risk limits but could round the
    # three-factor JPY gross exposure (EUR/USD quantity * EUR/USD ASK *
    # USD/JPY ASK). A 256-digit independent context also retains micro
    # fractional legs in the presence of very large synthetic positions.
    # Use an independent Decimal context. Caller rounding mode, exponent
    # bounds and Inexact/Rounded traps must not change mock risk decisions.
    with localcontext(Context(prec=DECIMAL_WORK_PRECISION)) as ctx:
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
                    or not trade.trade_id.isprintable()
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
        # Precision is an implementation detail, not permission to discard
        # tiny FX exposure. This independent context records any operation
        # that rounded coefficients (even an exactly discarded zero tail).
        # A rounded mock result must never be reported as complete.
        if ctx.flags[Inexact] or ctx.flags[Rounded]:
            return _reject("SYNTHETIC_ARITHMETIC_ROUNDED_FAIL_CLOSED")
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


@dataclass(frozen=True)
class SyntheticHandoffReview:
    """Only asserts in-memory mock consistency; never validates broker facts."""

    reason: str
    mock_binding_consistent: bool = False
    mock_records_bound: int = 0
    independent_broker_origin_verified: bool = False
    human_p05_signoff: bool = False
    runtime_go_no_go: str = "NO_GO"
    phase_1: str = "BLOCKED"
    safety_hold_latched: bool = True
    order_allowed: bool = False
    automatic_retry_allowed: bool = False
    stop_release_allowed: bool = False
    verified_values: None = None


def _handoff_reject(code: str) -> SyntheticHandoffReview:
    return SyntheticHandoffReview(code)


def _mock_plain_three_pair_map(value: object) -> bool:
    """Reject hostile mapping keys before hashing or comparing any key.

    A built-in dict may contain user-defined keys. Constructing a set from
    keys invokes their hash method and possibly custom equality. Inspect
    exact key types by iteration first; hash only plain built-in strings.
    This protects only the in-memory synthetic 3-pair boundary.
    """
    if type(value) is not dict or len(value) != len(PAIRS):
        return False
    keys = tuple(value)
    return (all(type(key) is str for key in keys)
            and set(keys) == set(PAIRS))


def _mock_plain_report(report: object, expected: type) -> bool:
    """Require inert primitive child report fields before any comparisons.

    A frozen dataclass alone is not a schema: callers can still construct it
    with arbitrary Python objects that execute code through __eq__. This
    narrow offline review compares only plain text, bools, None, and rows.
    """
    if type(report) is not expected:
        return False
    for field in fields(expected):
        value = getattr(report, field.name)
        if type(value) is str:
            if len(value) > 512:
                return False
        elif type(value) in (bool, type(None)):
            continue
        elif type(value) is tuple:
            if len(value) > MAX_SYNTHETIC_TRADES:
                return False
            for item in value:
                if (type(item) is not tuple or len(item) != 2
                        or type(item[0]) is not str
                        or type(item[1]) is not str
                        or len(item[0]) > MAX_SIMULATED_ID_CHARS
                        or len(item[1]) > 512):
                    return False
        else:
            return False
    return True


def _mock_plain_dataclass(record: object, expected: type) -> bool:
    """Reject unexpected objects before tuple equality or recomputation."""
    if type(record) is not expected:
        return False
    for field in fields(expected):
        value = getattr(record, field.name)
        if field.name == "observed_at":
            if (type(value) is not int
                    or not 0 <= value <= MAX_SYNTHETIC_ASOF):
                return False
        elif type(value) is not str or len(value) > MAX_SIMULATED_ID_CHARS:
            return False
    return True


def _mock_stop_protected(report: stop_conversion.Review) -> bool:
    return (
        _mock_plain_report(report, stop_conversion.Review)
        and report.illustrative_complete is True
        and report.reason in (
            "SYNTHETIC_HARD_LIMIT_EXCEEDED_NEVER_AUTHORIZED",
            "SYNTHETIC_ARITHMETIC_ONLY_NEVER_AUTHORIZED")
        and report.runtime_go_no_go == "NO_GO"
        and report.phase_1 == "BLOCKED"
        and report.safety_hold_latched is True
        and report.order_allowed is False
        and report.automatic_retry_allowed is False
        and report.stop_release_allowed is False
        and report.result_authorizes_trade is False
        and report.broker_contract_verified is False
        and report.costs_verified is False
        and report.stop_execution_guaranteed is False
        and report.verified_values is None
        and report.quote_conversion_method == "UNAPPROVED_SYNTHETIC_ONLY"
    )


def _mock_portfolio_protected(report: Review) -> bool:
    return (
        _mock_plain_report(report, Review)
        and report.arithmetic_complete is True
        and report.reason in (
            "EXISTING_HARD_LIMIT_OVER_IN_SYNTHETIC_INPUT",
            "SYNTHETIC_ARITHMETIC_ONLY_NOT_AUTHORIZED")
        and report.runtime_go_no_go == "NO_GO"
        and report.phase_1 == "BLOCKED"
        and report.safety_hold_latched is True
        and report.order_allowed is False
        and report.automatic_retry_allowed is False
        and report.stop_release_allowed is False
        and report.verified_values is None
    )


def review_synthetic_loss_handoff(
    contracts: object, stop_quotes: object, tickets: object,
    stop_result: object, portfolio_quotes: object, trades: object,
    portfolio_result: object, *,
    asof: object, snapshot_id: object, equity_jpy: object,
    positions_reconciled: object, pending_reconciled: object,
    inflight_reconciled: object,
) -> SyntheticHandoffReview:
    """Bind two *fictional* computations to a one-to-one input ledger.

    Recomputes both hypothetical outputs from the supplied *same* snapshot,
    requiring exact report identity. Matches each ticket and trade by order,
    ID, pair, side, status, exact rational units and asserted loss. Does not
    authenticate source facts, validate real SL fills, or permit an order.
    """
    if (type(asof) is not int or not 0 <= asof <= MAX_SYNTHETIC_ASOF
            or type(snapshot_id) is not str or not snapshot_id
            or len(snapshot_id) > MAX_SIMULATED_ID_CHARS
            or not snapshot_id.isprintable() or _decimal(equity_jpy) is None):
        return _handoff_reject("P103_MOCK_SNAPSHOT_OR_EQUITY_INVALID")
    if (positions_reconciled is not True or pending_reconciled is not True
            or inflight_reconciled is not True):
        return _handoff_reject("P103_UNKNOWN_MOCK_RECONCILIATION")
    if (type(tickets) not in (list, tuple)
            or type(trades) not in (list, tuple)
            or not tickets or len(tickets) != len(trades)
            or len(tickets) > MAX_SYNTHETIC_TRADES):
        return _handoff_reject("P103_MISSING_OR_MISMATCHED_MOCK_ROWS")
    if (not _mock_plain_three_pair_map(contracts)
            or not _mock_plain_three_pair_map(stop_quotes)
            or not _mock_plain_three_pair_map(portfolio_quotes)):
        return _handoff_reject("P103_MOCK_THREE_PAIR_SCOPE_MISMATCH")
    if not (_mock_stop_protected(stop_result)
            and _mock_portfolio_protected(portfolio_result)):
        return _handoff_reject("P103_UNVERIFIED_OR_PRIVILEGED_MOCK_OUTPUT")
    for pair in PAIRS:
        contract = contracts[pair]
        if not _mock_plain_dataclass(contract, stop_conversion.Contract):
            return _handoff_reject("P103_MOCK_CONTRACT_FIELD_INVALID")
        s, p = stop_quotes[pair], portfolio_quotes[pair]
        if (not _mock_plain_dataclass(s, stop_conversion.Quote)
                or not _mock_plain_dataclass(p, Quote)
                or (s.pair, s.bid, s.ask, s.observed_at, s.snapshot_id)
                != (p.pair, p.bid, p.ask, p.observed_at, p.snapshot_id)):
            return _handoff_reject("P103_MOCK_SNAPSHOT_QUOTE_MISMATCH")
    report_rows = stop_result.per_ticket_illustrative_loss_jpy
    if (type(report_rows) is not tuple or len(report_rows) != len(tickets)
            or type(stop_result.candidate_illustrative_loss_jpy) is not str
            or type(stop_result.total_illustrative_loss_jpy) is not str
            or type(portfolio_result.candidate_max_loss_jpy) is not str
            or type(portfolio_result.total_max_loss_jpy) is not str):
        return _handoff_reject("P103_MOCK_STOP_REPORT_ROW_MISMATCH")
    try:
        for ticket, trade, item in zip(tickets, trades, report_rows):
            if (type(ticket) is not stop_conversion.Ticket
                    or type(trade) is not Trade
                    or type(item) is not tuple or len(item) != 2
                    or type(item[0]) is not str
                    or type(item[1]) is not str):
                return _handoff_reject("P103_MOCK_IDENTITY_OR_ORDER_CHANGED")
            if (not _mock_plain_dataclass(ticket, stop_conversion.Ticket)
                    or not _mock_plain_dataclass(trade, Trade)):
                if (any(type(getattr(ticket, name)) is not str
                        for name in (
                            "volume_lots", "planned_entry", "stop_price",
                            "adverse_buffer_quote_per_base",
                            "additional_cost_jpy"))
                        or type(trade.base_units) is not str
                        or type(trade.max_loss_jpy) is not str):
                    return _handoff_reject("P103_MOCK_UNPARSABLE_AMOUNT")
                return _handoff_reject("P103_MOCK_IDENTITY_OR_ORDER_CHANGED")
            if ((ticket.ticket_id, ticket.pair, ticket.side, ticket.status)
                    != (trade.trade_id, trade.pair, trade.side, trade.status)
                    or item[0] != ticket.ticket_id):
                return _handoff_reject("P103_MOCK_IDENTITY_OR_ORDER_CHANGED")
            contract = contracts[ticket.pair]
            if (type(contract) is not stop_conversion.Contract
                    or _decimal(trade.base_units) is None
                    or _decimal(trade.max_loss_jpy) is None
                    or stop_conversion._parse(ticket.volume_lots) is None
                    or stop_conversion._parse(contract.base_units_per_lot)
                    is None
                    or _decimal(item[1]) is None):
                return _handoff_reject("P103_MOCK_UNPARSABLE_AMOUNT")
            if (Fraction(Decimal(trade.base_units))
                    != Fraction(Decimal(ticket.volume_lots))
                    * Fraction(Decimal(contract.base_units_per_lot))
                    or Fraction(Decimal(trade.max_loss_jpy))
                    != Fraction(Decimal(item[1]))):
                return _handoff_reject("P103_MOCK_UNIT_OR_LOSS_ASSERTION_DRIFT")

        if (Fraction(Decimal(stop_result.candidate_illustrative_loss_jpy))
                != Fraction(Decimal(portfolio_result.candidate_max_loss_jpy))
                or Fraction(Decimal(stop_result.total_illustrative_loss_jpy))
                != Fraction(Decimal(portfolio_result.total_max_loss_jpy))
                or stop_result.candidate_exceeds_existing_fraction
                is not portfolio_result.candidate_exceeds_existing_limit
                or stop_result.aggregate_exceeds_existing_fraction
                is not portfolio_result.total_exceeds_existing_limit):
            return _handoff_reject("P103_MOCK_TOTAL_OR_LIMIT_DRIFT")
    except (KeyError, ValueError, TypeError, ArithmeticError, OverflowError):
        return _handoff_reject("P103_MOCK_HANDOFF_FORMAT_INVALID")

    try:
        recomputed_stop = stop_conversion.review_synthetic_stop_risk(
            contracts, stop_quotes, tickets, equity_jpy=equity_jpy,
            asof=asof, snapshot_id=snapshot_id,
            positions_reconciled=positions_reconciled,
            pending_reconciled=pending_reconciled,
            inflight_reservations_reconciled=inflight_reconciled)
        recomputed_portfolio = review_synthetic_portfolio(
            portfolio_quotes, trades, equity_jpy=equity_jpy,
            asof=asof, snapshot_id=snapshot_id,
            positions_reconciled=positions_reconciled,
            pending_orders_reconciled=pending_reconciled)
    except Exception:
        # Only a fixed public code is emitted. Never reproduce input objects,
        # exception text, personal data or a privileged/positive result.
        return _handoff_reject("P103_MOCK_RECOMPUTATION_EXCEPTION")
    if (not _mock_stop_protected(recomputed_stop)
            or not _mock_portfolio_protected(recomputed_portfolio)
            or stop_result != recomputed_stop
            or portfolio_result != recomputed_portfolio):
        return _handoff_reject("P103_MOCK_RECOMPUTATION_MISMATCH")

    return SyntheticHandoffReview(
        "PASS_OFFLINE_MOCK_BINDING_ONLY",
        mock_binding_consistent=True,
        mock_records_bound=len(tickets),
    )
