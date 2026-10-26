"""Only synthetic/manual MT4 source comparisons. Never connects to a broker."""
import contextlib
import copy
import io
import json
import unittest
from pathlib import Path

from scripts.validate_mt4_manual_symbol_specs import (
    ROOT,
    EXPECTED_PAIRS,
    TEMPLATE_FIELDS,
    NEEDED_TO_COMPARE,
    compare_manual_snapshot,
    main,
    safe_decimal,
)
from scripts.check_reconciliation import check_reconciliation

TEMPLATE_PATH = ROOT / "specs/p0_01_mt4_manual_symbol_template.json"
REFERENCE_PATH = ROOT / "specs/p0_01_rakuten_mt4_public_contract_evidence.json"


class ManualMt4SymbolCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tpl = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        cls.reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    def snapshot(self):
        return copy.deepcopy(self.tpl)

    def put(self, doc, symbol, field, value):
        next(p for p in doc["symbols"] if p["symbol"] == symbol)["properties"][field] = value

    def complete_synthetic(self):
        data = self.snapshot()
        for symbol in EXPECTED_PAIRS:
            values = {
                "lot_size_base_units": "100000",
                "min_lot": "0.01",
                "lot_step": "0.01",
                "max_lot": "20",
                "point_quote": ("0.001" if symbol.endswith("JPY") else "0.00001"),
                "digits": ("3" if symbol.endswith("JPY") else "5"),
                "tick_size_points": "1",
                "tick_value_deposit_currency": "1",
                "stop_level_points": "0",
                "freeze_level_points": "0",
                "spread_points": "20",
            }
            for name, value in values.items():
                self.put(data, symbol, name, value)
        return data

    def test_blank_template_persists_all_unverified_values(self):
        d = self.snapshot()
        self.assertEqual(d["data_state"], "UNVERIFIED_LOCAL_VALUES")
        self.assertEqual([p["symbol"] for p in d["symbols"]], list(EXPECTED_PAIRS))
        for pair in d["symbols"]:
            self.assertEqual(set(pair["properties"]), set(TEMPLATE_FIELDS))
            self.assertTrue(all(v is None for v in pair["properties"].values()))

    def test_blank_template_is_incomplete_and_never_trading_ok(self):
        result = compare_manual_snapshot(self.snapshot(), self.reference)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(len(result["pairs"]), 4)
        for row in result["pairs"]:
            self.assertEqual(row["status"], "INCOMPLETE")
            self.assertEqual(set(row["missing_fields"]), set(NEEDED_TO_COMPARE))

    def test_even_synthetic_complete_values_only_compare_fields(self):
        result = compare_manual_snapshot(self.complete_synthetic(), self.reference)
        self.assertEqual(result["status"], "COMPARED_FIELDS_ONLY")
        for p in result["pairs"]:
            self.assertEqual(p["findings"], [])
            self.assertEqual(p["missing_fields"], [])
        self.assertNotIn("TRADING_APPROVED", str(result))

    def test_public_lot_or_point_mismatch_needs_review(self):
        d = self.complete_synthetic()
        self.put(d, "GBP/USD", "point_quote", "0.001")
        self.put(d, "EUR/JPY", "lot_size_base_units", "10000")
        result = compare_manual_snapshot(d, self.reference)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        by_symbol = {p["symbol"]: p for p in result["pairs"]}
        self.assertTrue(any("PUBLIC_RULE_DIFFERS" in f for f
                            in by_symbol["GBP/USD"]["findings"]))
        self.assertTrue(any("PUBLIC_RULE_DIFFERS" in f for f
                            in by_symbol["EUR/JPY"]["findings"]))

    def test_lot_step_and_minimum_maximum_conflicts_require_review(self):
        d = self.complete_synthetic()
        self.put(d, "USD/JPY", "lot_step", "0.1")
        self.put(d, "AUD/USD", "max_lot", "0.001")
        result = compare_manual_snapshot(d, self.reference)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        by_symbol = {p["symbol"]: p for p in result["pairs"]}
        self.assertIn("lot_step:GREATER_THAN_MINIMUM",
                      by_symbol["USD/JPY"]["findings"])
        self.assertIn("max_lot:LESS_THAN_MINIMUM",
                      by_symbol["AUD/USD"]["findings"])

    def test_missing_tickvalue_remains_pending_not_zero(self):
        d = self.complete_synthetic()
        self.put(d, "AUD/USD", "tick_value_deposit_currency", None)
        result = compare_manual_snapshot(d, self.reference)
        self.assertEqual(result["status"], "INCOMPLETE")
        by_symbol = {p["symbol"]: p for p in result["pairs"]}
        self.assertIn("tick_value_deposit_currency",
                      by_symbol["AUD/USD"]["missing_fields"])

    def test_reject_broken_values_and_extra_sensitive_keys(self):
        d = self.complete_synthetic()
        self.put(d, "USD/JPY", "min_lot", "0")
        self.put(d, "EUR/JPY", "digits", "3.1")
        self.put(d, "GBP/USD", "lot_step", "NaN")
        self.put(d, "AUD/USD", "tick_size_points", "-1")
        result = compare_manual_snapshot(d, self.reference)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(all(p["findings"] for p in result["pairs"]))
        d = self.complete_synthetic()
        d["account_number"] = "secret-value-must-not-print"
        result = compare_manual_snapshot(d, self.reference)
        self.assertEqual(result["findings"], ["DOCUMENT_SCHEMA"])
        self.assertNotIn("secret-value", str(result))

    def test_unexpected_duplicate_and_malformed_symbols_rejected(self):
        d = self.complete_synthetic()
        d["symbols"][1]["symbol"] = "USD/JPY"
        self.assertEqual(compare_manual_snapshot(d, self.reference)["status"],
                         "REVIEW_REQUIRED")
        d = self.complete_synthetic()
        d["symbols"][0]["symbol"] = ["USD", "JPY"]
        self.assertEqual(compare_manual_snapshot(d, self.reference)["findings"],
                         ["SYMBOL_SET"])

    def test_cli_refuses_repo_input_without_reading_or_writing_it(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = main(["--input", str(TEMPLATE_PATH)])
        self.assertEqual(status, 1)
        self.assertIn("outside the Git repository", out.getvalue())
        self.assertNotIn("USD/JPY", out.getvalue())

    def test_decimal_parser_disallows_unsafe_nonfinite_or_float(self):
        for value in ("NaN", "Infinity", "-Infinity", "not-a-number", "",
                      "1" * 60, 0.01, True):
            with self.subTest(value=str(value)):
                self.assertIsNone(safe_decimal(value))
        self.assertEqual(str(safe_decimal("0.01")), "0.01")

    def test_safety_registries_and_production_remain_unapproved(self):
        reg = json.loads((ROOT / "specs/reconciliation_registry.json").read_text(
            encoding="utf-8"
        ))
        self.assertEqual(check_reconciliation(reg), [])
        for x in reg["items"]:
            self.assertIs(x["implementation_approved"], False)
            self.assertIsNone(x["owner_approval"])
        phases = json.loads((ROOT / "specs/acceptance_registry.json").read_text(
            encoding="utf-8"
        ))["phases"]
        p1 = next(p for p in phases if p["id"] == "PHASE-1")
        self.assertEqual(p1["status"], "BLOCKED")
        self.assertIsNone(p1["approval"])


if __name__ == "__main__":
    unittest.main()
