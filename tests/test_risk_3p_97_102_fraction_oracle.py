"""Independent integer-rational oracle for two *fictional* FX risk engines.

Fraction computes exact rational arithmetic separately from Decimal. Only
synthetic USD/JPY, EUR/JPY, EUR/USD snapshots are used, no market/broker data,
account state, MT4, filesystem or credentials. "PASS" is not trade approval.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, Context, Inexact, Overflow, Rounded, ROUND_DOWN
from decimal import localcontext
from fractions import Fraction
from itertools import product
import unittest

from scripts import phase1_three_pair_synthetic_stop_conversion as sl
from scripts import phase1_three_pair_synthetic_risk as pf

PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
QUOTE_ROWS = {
    "USD/JPY": ("150.5", "151.5"),
    "EUR/JPY": ("180.5", "181.5"),
    "EUR/USD": ("1.1990", "1.2010"),
}
ENTRIES = {
    "USD/JPY": ("151.1", "150.8", "151.4"),
    "EUR/JPY": ("181.2", "180.7", "181.7"),
    "EUR/USD": ("1.2020", "1.1980", "1.2060"),
}
EQUITY = "100000"
SID = "SIM-INDEPENDENT-RATIONAL-97"
ASOF = 97


def rat(value):
    """No binary float conversion, no ambient Decimal arithmetic."""
    return Fraction(Decimal(value))


def exact_decimal(value: Fraction) -> str:
    """Render a terminating rational using integers, never float/Decimal math."""
    n, d = value.numerator, value.denominator
    twos = fives = 0
    reduced = d
    while reduced % 2 == 0:
        twos += 1
        reduced //= 2
    while reduced % 5 == 0:
        fives += 1
        reduced //= 5
    if reduced != 1:
        raise ValueError("nonterminating rational not allowed in mock FX data")
    places = max(twos, fives)
    integer = abs(n) * 10 ** places // d
    if integer * d != abs(n) * 10 ** places:
        raise AssertionError("incorrect independent integer conversion")
    digits = str(integer).zfill(places + 1)
    out = digits if places == 0 else (
        digits[:-places] + "." + digits[-places:])
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return ("-" if n < 0 else "") + out


def contracts(units="100000", maximum="2"):
    return {p: sl.Contract(p, units, "0.01", "0.01", maximum)
            for p in PAIRS}


def stop_quotes(ask_override=None):
    vals = dict(QUOTE_ROWS)
    if ask_override is not None:
        vals["USD/JPY"] = (vals["USD/JPY"][0], ask_override)
    return {p: sl.Quote(p, bid, ask, ASOF, SID)
            for p, (bid, ask) in vals.items()}


def portfolio_quotes(ask_override=None):
    return {p: pf.Quote(q.pair, q.bid, q.ask, q.observed_at, q.snapshot_id)
            for p, q in stop_quotes(ask_override).items()}


def ticket(pair, side, status="CANDIDATE", volume="0.01",
           buffer="0", cost="0", ident="sim-1"):
    entry, buy_stop, sell_stop = ENTRIES[pair]
    return sl.Ticket(ident, pair, side, status, volume, entry,
                     buy_stop if side == "BUY" else sell_stop,
                     buffer, cost, SID)


def oracle_loss(t: sl.Ticket, c: dict, q: dict) -> Fraction:
    direction = rat(t.planned_entry) - rat(t.stop_price) if t.side == "BUY" else (
        rat(t.stop_price) - rat(t.planned_entry))
    if direction <= 0:
        raise AssertionError("fictional stop direction incorrect")
    amount = ((direction + rat(t.adverse_buffer_quote_per_base))
              * rat(t.volume_lots) * rat(c[t.pair].base_units_per_lot))
    if t.pair == "EUR/USD":
        amount *= rat(q["USD/JPY"].ask)
    return amount + rat(t.additional_cost_jpy)


def invoke_stop(tickets, c=None, q=None, equity=EQUITY,
                positions=True, pending=True, inflight=True):
    return sl.review_synthetic_stop_risk(
        contracts() if c is None else c,
        stop_quotes() if q is None else q, tickets,
        equity_jpy=equity, asof=ASOF, snapshot_id=SID,
        positions_reconciled=positions, pending_reconciled=pending,
        inflight_reservations_reconciled=inflight)


def to_portfolio_trades(tickets, c=None, q=None):
    c = contracts() if c is None else c
    q = stop_quotes() if q is None else q
    return [
        pf.Trade(t.ticket_id, t.pair, t.side, t.status,
                 exact_decimal(rat(t.volume_lots)
                               * rat(c[t.pair].base_units_per_lot)),
                 exact_decimal(oracle_loss(t, c, q)))
        for t in tickets
    ]


def invoke_portfolio(trades, q=None, equity=EQUITY,
                     positions=True, pending=True):
    return pf.review_synthetic_portfolio(
        portfolio_quotes() if q is None else q, trades,
        asof=ASOF, snapshot_id=SID, equity_jpy=equity,
        positions_reconciled=positions,
        pending_orders_reconciled=pending)


class ExactIntegerOracleTests(unittest.TestCase):
    def no_go_stop(self, r):
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.result_authorizes_trade)
        self.assertFalse(r.stop_release_allowed)
        self.assertFalse(r.automatic_retry_allowed)
        self.assertFalse(r.broker_contract_verified)
        self.assertFalse(r.stop_execution_guaranteed)
        self.assertIsNone(r.verified_values)

    def no_go_portfolio(self, r):
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        self.assertFalse(r.order_allowed)
        self.assertFalse(r.stop_release_allowed)
        self.assertFalse(r.automatic_retry_allowed)
        self.assertIsNone(r.verified_values)

    def compare_stop_to_fraction_oracle(self, tickets, c=None, q=None,
                                         equity=EQUITY):
        c = contracts() if c is None else c
        q = stop_quotes() if q is None else q
        r = invoke_stop(tickets, c, q, equity)
        self.assertTrue(r.illustrative_complete, r)
        expected = [oracle_loss(t, c, q) for t in tickets]
        self.assertEqual(len(r.per_ticket_illustrative_loss_jpy), len(tickets))
        for t, (ticket_id, found), oracle in zip(
                tickets, r.per_ticket_illustrative_loss_jpy, expected):
            self.assertEqual(ticket_id, t.ticket_id)
            self.assertEqual(rat(found), oracle)
        candidate = sum((amount for t, amount in zip(tickets, expected)
                         if t.status == "CANDIDATE"), Fraction(0))
        total = sum(expected, Fraction(0))
        self.assertEqual(rat(r.candidate_illustrative_loss_jpy), candidate)
        self.assertEqual(rat(r.total_illustrative_loss_jpy), total)
        self.assertEqual(r.candidate_exceeds_existing_fraction,
                         candidate > rat(equity) / 200)
        self.assertEqual(r.aggregate_exceeds_existing_fraction,
                         total > rat(equity) / 100)
        self.no_go_stop(r)
        return r

    def test_exact_integer_decimal_formatter_without_float_roundoff(self):
        for raw in ("0", "0.000000000001", "500.000000000001",
                    "999999999999999999999.999999999999",
                    "-0.125", "3.140000", "1000"):
            with self.subTest(raw=raw):
                self.assertEqual(rat(exact_decimal(rat(raw))), rat(raw))

    def test_48_pair_side_volume_cost_cases_match_independent_fraction(self):
        scenarios = 0
        for pair, side, vol, buffer, cost in product(
                PAIRS, ("BUY", "SELL"), ("0.01", "0.03"),
                ("0", "0.00000001"), ("0", "0.000000000001")):
            with self.subTest(pair=pair, side=side, vol=vol,
                              buffer=buffer, cost=cost):
                t = ticket(pair, side, volume=vol,
                           buffer=buffer, cost=cost)
                self.compare_stop_to_fraction_oracle([t])
                scenarios += 1
        self.assertEqual(scenarios, 48)

    def test_three_pair_mixed_candidate_position_pending_have_exact_total(self):
        ts = [
            ticket("EUR/USD", "BUY", "CANDIDATE", "0.03", "0.00000001",
                   "0.000000000001", "c"),
            ticket("USD/JPY", "SELL", "POSITION", "0.01", "0.00000001",
                   "0", "o"),
            ticket("EUR/JPY", "BUY", "PENDING", "0.03", "0",
                   "0.000000000001", "p"),
        ]
        r = self.compare_stop_to_fraction_oracle(ts)
        p = invoke_portfolio(to_portfolio_trades(ts))
        self.assertTrue(p.arithmetic_complete)
        self.assertEqual(rat(p.total_max_loss_jpy),
                         rat(r.total_illustrative_loss_jpy))
        self.assertEqual(rat(p.candidate_max_loss_jpy),
                         rat(r.candidate_illustrative_loss_jpy))
        self.assertEqual(p.total_exceeds_existing_limit,
                         r.aggregate_exceeds_existing_fraction)
        self.assertEqual(p.candidate_exceeds_existing_limit,
                         r.candidate_exceeds_existing_fraction)
        self.no_go_portfolio(p)

    def test_ask_conversion_increase_cannot_reduce_eur_usd_illustration(self):
        t = ticket("EUR/USD", "BUY")
        low = stop_quotes("151.5")
        high = stop_quotes("152.5")
        a = self.compare_stop_to_fraction_oracle([t], q=low)
        b = self.compare_stop_to_fraction_oracle([t], q=high)
        difference = oracle_loss(t, contracts(), high) - oracle_loss(
            t, contracts(), low)
        self.assertGreater(difference, 0)
        self.assertEqual(rat(b.candidate_illustrative_loss_jpy)
                         - rat(a.candidate_illustrative_loss_jpy), difference)

    def test_conversion_ask_change_does_not_change_jpy_quoted_loss(self):
        for pair in ("USD/JPY", "EUR/JPY"):
            with self.subTest(pair=pair):
                t = ticket(pair, "BUY")
                a = self.compare_stop_to_fraction_oracle([t],
                                                          q=stop_quotes("151.5"))
                b = self.compare_stop_to_fraction_oracle([t],
                                                          q=stop_quotes("152.5"))
                self.assertEqual(a.total_illustrative_loss_jpy,
                                 b.total_illustrative_loss_jpy)

    def test_additional_positive_fee_only_increases_risk(self):
        for pair, side in product(PAIRS, ("BUY", "SELL")):
            with self.subTest(pair=pair, side=side):
                base = ticket(pair, side)
                higher = replace(base, additional_cost_jpy="0.000000000001")
                lower_result = self.compare_stop_to_fraction_oracle([base])
                upper_result = self.compare_stop_to_fraction_oracle([higher])
                self.assertEqual(
                    rat(upper_result.candidate_illustrative_loss_jpy)
                    - rat(lower_result.candidate_illustrative_loss_jpy),
                    rat("0.000000000001"))

    def test_positive_adverse_buffer_only_increases_risk(self):
        for pair in PAIRS:
            with self.subTest(pair=pair):
                original = ticket(pair, "SELL")
                increased = replace(original,
                                    adverse_buffer_quote_per_base="0.00000001")
                low = self.compare_stop_to_fraction_oracle([original])
                high = self.compare_stop_to_fraction_oracle([increased])
                self.assertGreater(rat(high.candidate_illustrative_loss_jpy),
                                   rat(low.candidate_illustrative_loss_jpy))

    def test_exact_rational_gross_and_net_currency_legs(self):
        ts = [
            ticket("EUR/USD", "BUY", "CANDIDATE", "0.01", ident="c"),
            ticket("EUR/JPY", "SELL", "POSITION", "0.03", ident="p"),
            ticket("USD/JPY", "BUY", "PENDING", "0.01", ident="o"),
        ]
        ps = to_portfolio_trades(ts)
        review = invoke_portfolio(ps)
        self.assertTrue(review.arithmetic_complete)
        net = {k: Fraction(0) for k in ("USD", "EUR", "JPY")}
        gross = {k: Fraction(0) for k in net}
        qs = portfolio_quotes()
        for t in ps:
            base, currency = t.pair.split("/")
            units = rat(t.base_units)
            sign = 1 if t.side == "BUY" else -1
            px = rat(qs[t.pair].ask if sign == 1 else qs[t.pair].bid)
            for name, amount in ((base, units * sign),
                                 (currency, -units * sign * px)):
                net[name] += amount
                gross[name] += abs(amount)
        for name, text in review.net_native:
            self.assertEqual(rat(text), net[name])
        for name, text in review.gross_native:
            self.assertEqual(rat(text), gross[name])
        oracle_gross_jpy = (gross["JPY"]
                            + gross["USD"] * rat(qs["USD/JPY"].ask)
                            + gross["EUR"] * rat(qs["EUR/JPY"].ask))
        self.assertEqual(rat(review.gross_currency_legs_jpy),
                         oracle_gross_jpy)
        self.no_go_portfolio(review)

    def test_quote_bid_ask_spread_increase_cannot_reduce_gross_exposure(self):
        t = pf.Trade("c", "EUR/USD", "BUY", "CANDIDATE", "1000", "100")
        regular = portfolio_quotes()
        widened = portfolio_quotes()
        widened["EUR/USD"] = replace(widened["EUR/USD"], ask="1.3010")
        a = invoke_portfolio([t], q=regular)
        b = invoke_portfolio([t], q=widened)
        self.assertTrue(a.arithmetic_complete)
        self.assertTrue(b.arithmetic_complete)
        self.assertGreaterEqual(rat(b.gross_currency_legs_jpy),
                                rat(a.gross_currency_legs_jpy))
        self.no_go_portfolio(a)
        self.no_go_portfolio(b)

    def test_high_magnitude_product_plus_microfee_exact_as_fraction(self):
        maximum = "999999999999"
        c = contracts(units=maximum, maximum=maximum)
        q = stop_quotes(ask_override=maximum)
        q["USD/JPY"] = replace(q["USD/JPY"], bid=maximum)
        t = sl.Ticket("hi", "EUR/USD", "BUY", "CANDIDATE",
                      maximum, maximum, "1", "0",
                      "0.000000000001", SID)
        r = self.compare_stop_to_fraction_oracle([t], c=c, q=q,
                                                  equity=maximum)
        self.assertTrue(r.candidate_exceeds_existing_fraction)

    def test_exact_half_percent_and_one_percent_using_rational_oracle(self):
        # Synthetic stops for USD/JPY with 0.01 lots produce 500 JPY
        # and an exactly matching 1000 JPY combined budget.
        x = sl.Ticket("c", "USD/JPY", "BUY", "CANDIDATE",
                      "0.01", "150.5", "150", "0", "0", SID)
        y = sl.Ticket("p", "USD/JPY", "SELL", "PENDING",
                      "0.01", "150", "150.5", "0", "0", SID)
        result = self.compare_stop_to_fraction_oracle([x, y])
        self.assertFalse(result.candidate_exceeds_existing_fraction)
        self.assertFalse(result.aggregate_exceeds_existing_fraction)

    def test_microfee_at_exact_limit_is_detected_as_excess(self):
        x = sl.Ticket("c", "USD/JPY", "BUY", "CANDIDATE",
                      "0.01", "150.5", "150", "0", "0.000000000001", SID)
        y = sl.Ticket("p", "USD/JPY", "SELL", "PENDING",
                      "0.01", "150", "150.5", "0", "0", SID)
        result = self.compare_stop_to_fraction_oracle([x, y])
        self.assertTrue(result.candidate_exceeds_existing_fraction)
        self.assertTrue(result.aggregate_exceeds_existing_fraction)

    def test_trades_no_reconciliation_cannot_get_any_positive_authority(self):
        t = ticket("EUR/USD", "BUY")
        for opts in ({"pending": False}, {"inflight": False},
                     {"positions": False}):
            with self.subTest(opts=opts):
                s = invoke_stop([t], **opts)
                self.assertFalse(s.illustrative_complete)
                self.no_go_stop(s)
        p = invoke_portfolio(to_portfolio_trades([t]), pending=False)
        self.assertFalse(p.arithmetic_complete)
        self.no_go_portfolio(p)

    def test_tampered_pretended_loss_value_still_never_grants_trading(self):
        t = ticket("USD/JPY", "BUY")
        assumed = to_portfolio_trades([t])
        lowered = [replace(assumed[0], max_loss_jpy="0.000000000001")]
        actual = invoke_portfolio(lowered)
        self.assertTrue(actual.arithmetic_complete)
        self.assertNotEqual(rat(actual.candidate_max_loss_jpy),
                            oracle_loss(t, contracts(), stop_quotes()))
        self.no_go_portfolio(actual)

    def test_float_input_is_not_accepted_as_contract_or_risk_data(self):
        c = contracts()
        c["EUR/USD"] = replace(c["EUR/USD"], base_units_per_lot=100000.0)
        s = invoke_stop([ticket("EUR/USD", "BUY")], c=c)
        self.assertFalse(s.illustrative_complete)
        self.no_go_stop(s)
        p = invoke_portfolio([
            pf.Trade("c", "EUR/USD", "BUY", "CANDIDATE", "1", 100.0)])
        self.assertFalse(p.arithmetic_complete)
        self.no_go_portfolio(p)

    def test_hostile_external_decimal_settings_cannot_change_exact_outputs(self):
        ts = [ticket("EUR/USD", "BUY", "CANDIDATE", "0.03",
                     "0.00000001", "0.000000000001")]
        expected = self.compare_stop_to_fraction_oracle(ts)
        with localcontext() as caller:
            caller.prec = 3
            caller.rounding = ROUND_DOWN
            caller.Emax = 9
            caller.Emin = -9
            caller.traps[Inexact] = True
            caller.traps[Rounded] = True
            caller.traps[Overflow] = True
            measured = self.compare_stop_to_fraction_oracle(ts)
            self.assertEqual(measured, expected)

    def test_rational_oracle_never_authenticates_a_real_broker_contract(self):
        self.assertEqual(sl.PAIRS, pf.PAIRS)
        self.assertEqual(sl.PAIRS, PAIRS)
        self.assertEqual(sl.SYNTHETIC_TRADE_LIMIT, Decimal("0.005"))
        self.assertEqual(sl.SYNTHETIC_AGGREGATE_LIMIT, Decimal("0.01"))
        result = self.compare_stop_to_fraction_oracle([
            ticket("EUR/JPY", "SELL")])
        self.assertEqual(result.quote_conversion_method,
                         "UNAPPROVED_SYNTHETIC_ONLY")
        self.assertFalse(result.broker_contract_verified)


if __name__ == "__main__":
    unittest.main()
