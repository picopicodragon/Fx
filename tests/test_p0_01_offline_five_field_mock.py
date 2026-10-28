"""Deterministic offline-only synthetic tests for P0-01 D2."""
import copy
import unittest

from scripts.p0_01_offline_five_field_mock import (
    PAIRS, FIELDS, PASS, REVIEW, INCOMPLETE,
    parse_positive_token, validate_fixture_shape,
    validate_positive_decimal_tokens, compare_synthetic_field_invariants,
    report_safe_status_codes_only,
)


def fixture():
    base = dict(min_lot="0.1", lot_step="0.01", point_quote="0.001",
                tick_size_points="1", tick_value_deposit_currency="10")
    return [{"symbol": p, "properties": dict(base)} for p in PAIRS]


class SyntheticD2Tests(unittest.TestCase):
    def test_valid_is_never_broker_verified(self):
        outcome = report_safe_status_codes_only(fixture())
        self.assertEqual(outcome["status"], PASS)
        self.assertFalse(outcome["production_usable"])
        self.assertFalse(outcome["broker_queried"])
        self.assertFalse(outcome["orders_generated"])
        self.assertFalse(outcome["forward_trading_enabled"])
        self.assertEqual(outcome["phase_1"], "BLOCKED")

    def test_each_of_twenty_null_fields_incomplete(self):
        for i in range(4):
            for field in FIELDS:
                with self.subTest(i=i, field=field):
                    rows = fixture()
                    rows[i]["properties"][field] = None
                    self.assertEqual(compare_synthetic_field_invariants(rows), INCOMPLETE)

    def test_empty_is_incomplete(self):
        rows = fixture()
        rows[0]["properties"]["min_lot"] = ""
        self.assertEqual(compare_synthetic_field_invariants(rows), INCOMPLETE)

    def test_invalid_numeric_fail_closed(self):
        bad = [0, 1, True, 0.1, -3, "0", "-1", "NaN", "Infinity", "1e500",
               "1e-13", "1e13", "1.234567890123456789", " 1", "+1",
               "1" * 49, "１２", {}, [], object()]
        for value in bad:
            with self.subTest(type=type(value).__name__, representation=type(value).__name__):
                rows = fixture()
                rows[0]["properties"]["min_lot"] = value
                self.assertEqual(report_safe_status_codes_only(rows)["status"], REVIEW)

    def test_shape_rejects_unknown_duplicate_missing_and_extra(self):
        for mutation in ("duplicate", "unknown", "missing", "extra", "field"):
            rows = fixture()
            if mutation == "duplicate":
                rows[1]["symbol"] = rows[0]["symbol"]
            elif mutation == "unknown":
                rows[0]["symbol"] = "XXX/JPY"
            elif mutation == "missing":
                rows.pop()
            elif mutation == "extra":
                rows[0]["unexpected"] = "x"
            else:
                del rows[0]["properties"]["min_lot"]
            with self.subTest(mutation=mutation):
                self.assertEqual(validate_fixture_shape(rows), REVIEW)

    def test_invalid_precedes_incomplete(self):
        rows = fixture()
        rows[0]["properties"]["min_lot"] = None
        rows[1]["properties"]["lot_step"] = "-1"
        self.assertEqual(compare_synthetic_field_invariants(rows), REVIEW)

    def test_lot_step_above_minimum_rejected(self):
        rows = fixture()
        rows[0]["properties"]["lot_step"] = "0.2"
        self.assertEqual(compare_synthetic_field_invariants(rows), REVIEW)

    def test_unit_multiplication_not_interchangeability(self):
        rows = fixture()
        rows[0]["properties"]["point_quote"] = "0.0001"
        rows[0]["properties"]["tick_size_points"] = "2"
        self.assertEqual(compare_synthetic_field_invariants(rows), PASS)
        rows[0]["properties"]["point_quote"] = "1e-12"
        rows[0]["properties"]["tick_size_points"] = "0.000000000001"
        self.assertEqual(compare_synthetic_field_invariants(rows), REVIEW)

    def test_failures_never_echo_input(self):
        rows = fixture()
        secret = "UNIQUE_PRIVATE_INPUT_MARKER"
        rows[0]["properties"]["min_lot"] = secret
        self.assertNotIn(secret, repr(report_safe_status_codes_only(rows)))

    def test_reject_unexpected_root_types_without_echo(self):
        for candidate in (None, {}, (), "PRIVATE_PAYLOAD", 42):
            with self.subTest(type=type(candidate).__name__):
                result = report_safe_status_codes_only(candidate)
                self.assertEqual(result["status"], REVIEW)
                self.assertFalse(result["production_usable"])
                self.assertNotIn("PRIVATE_PAYLOAD", repr(result))

    def test_no_file_or_network_dependencies(self):
        import inspect
        import scripts.p0_01_offline_five_field_mock as module
        source = inspect.getsource(module)
        for forbidden in ("import socket", "import requests", "import subprocess",
                          "import MetaTrader5", "OrderSend(", "MarketInfo(",
                          "open(", "read_text(", "write_text("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
