"""P0-01 D5-3 synthetic contract/currency/lot-grid regression suite."""
import copy
import unittest

from scripts.p0_01_d5_3_synthetic_contract import (
    assess_synthetic_contract, CONSISTENT, REVIEW, INCOMPLETE
)


def fixture():
    result = []
    for symbol, point, tick, conversion in (
        ("USD/JPY", "0.001", "100", "1"),
        ("EUR/JPY", "0.001", "100", "1"),
        ("GBP/USD", "0.00001", "150", "150"),
        ("AUD/USD", "0.00001", "150", "150"),
    ):
        result.append({
            "symbol": symbol,
            "quote_currency": symbol.split("/")[1],
            "tick_value_basis": "PER_1_LOT",
            "contract_size_base_units_per_lot": "100000",
            "quote_to_deposit_synthetic_rate": conversion,
            "requested_lots": "0.11",
            "properties": {
                "min_lot": "0.10", "lot_step": "0.01",
                "point_quote": point, "tick_size_points": "1",
                "tick_value_deposit_currency": tick,
            }
        })
    return {"origin": "SYNTHETIC_ONLY", "account_currency": "JPY", "symbols": result}


class D53SyntheticContractTests(unittest.TestCase):
    def denied(self, response):
        self.assertEqual(response["phase_1"], "BLOCKED")
        for key in ("broker_verified", "production_usable", "broker_queried",
                    "orders_generated", "terminal_execution_approved",
                    "forward_trading_enabled"):
            self.assertIs(response[key], False)

    def test_consistent_synthetic_never_verified(self):
        x = assess_synthetic_contract(fixture())
        self.assertEqual(x["status"], CONSISTENT)
        self.denied(x)

    def test_quote_account_conversion_mismatch(self):
        f = fixture()
        f["symbols"][0]["quote_to_deposit_synthetic_rate"] = "150"
        self.assertEqual(assess_synthetic_contract(f)["status"], REVIEW)

    def test_nonaccount_quote_conversion_identity_inconsistent(self):
        f = fixture()
        f["symbols"][2]["quote_to_deposit_synthetic_rate"] = "1"
        self.assertEqual(assess_synthetic_contract(f)["status"], REVIEW)

    def test_contract_size_wrong_tick_value(self):
        f = fixture()
        f["symbols"][1]["contract_size_base_units_per_lot"] = "50000"
        self.assertEqual(assess_synthetic_contract(f)["status"], REVIEW)

    def test_lot_step_origin_mismatch_and_minimum(self):
        for lots in ("0.105", "0.09"):
            f = fixture()
            f["symbols"][0]["requested_lots"] = lots
            with self.subTest(lots=lots):
                self.assertEqual(assess_synthetic_contract(f)["status"], REVIEW)

    def test_tick_size_mismatch(self):
        f = fixture()
        f["symbols"][0]["properties"]["tick_size_points"] = "2"
        self.assertEqual(assess_synthetic_contract(f)["status"], REVIEW)

    def test_missing_and_bad_conversion(self):
        for value, expected in ((None, INCOMPLETE), ("", INCOMPLETE),
                                ("NaN", REVIEW), ("1e2", REVIEW)):
            f = fixture()
            f["symbols"][2]["quote_to_deposit_synthetic_rate"] = value
            with self.subTest(value=value):
                self.assertEqual(assess_synthetic_contract(f)["status"], expected)

    def test_source_approval_injection_rejected(self):
        f = fixture()
        f["broker_verified"] = True
        self.assertEqual(assess_synthetic_contract(f)["status"], REVIEW)
        self.denied(assess_synthetic_contract(f))

    def test_no_mutation_or_echo(self):
        f = fixture()
        original = copy.deepcopy(f)
        self.denied(assess_synthetic_contract(f))
        self.assertEqual(f, original)
        f["symbols"][0]["requested_lots"] = "SECRET_NEVER_ECHO"
        self.assertNotIn("SECRET_NEVER_ECHO", repr(assess_synthetic_contract(f)))

    def test_bad_input_denied(self):
        for x in (None, [], {}, True, "bad", object()):
            with self.subTest(kind=type(x).__name__):
                r = assess_synthetic_contract(x)
                self.assertEqual(r["status"], REVIEW)
                self.denied(r)


if __name__ == "__main__":
    unittest.main()
