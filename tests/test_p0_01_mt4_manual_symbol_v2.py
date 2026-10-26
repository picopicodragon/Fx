"""Synthetic-only MT4 manual v2 migration and validation safety tests."""
import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation
from scripts.mt4_manual_symbol_v2 import (
    DAYS, DISPLAY_FIELDS, DISPLAY_TEXT_FIELDS, EXPECTED_PAIRS, OFFICIAL, ROOT,
    V2_TEMPLATE, check_v2, migrate_to_v2, run, safe_location,
)

V1_TEMPLATE = ROOT / "specs/p0_01_mt4_manual_symbol_template.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MT4ManualSymbolV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1 = load(V1_TEMPLATE)
        cls.v2 = load(V2_TEMPLATE)
        cls.official = load(OFFICIAL)

    def v2_doc(self):
        return copy.deepcopy(self.v2)

    def legacy_doc(self):
        return copy.deepcopy(self.v1)

    def by_symbol(self, d, symbol):
        return next(x for x in d["symbols"] if x["symbol"] == symbol)

    def test_v2_has_exact_paired_display_fields_and_null_defaults(self):
        self.assertEqual(self.v2["schema_version"], 2)
        self.assertEqual(self.v2["kind"], "MT4_MANUAL_SYMBOL_PROPERTIES_V2")
        self.assertEqual([r["symbol"] for r in self.v2["symbols"]],
                         list(EXPECTED_PAIRS))
        for row in self.v2["symbols"]:
            display = row["display_properties"]
            self.assertEqual(set(display), DISPLAY_FIELDS)
            self.assertEqual(set(display["trading_hours_display"]), set(DAYS))
            self.assertIsNone(display["spread_mode"])
            for field in DISPLAY_TEXT_FIELDS:
                self.assertIsNone(display[field])
            self.assertTrue(all(value is None for value in
                                display["trading_hours_display"].values()))
            self.assertTrue(all(value is None for value in
                                row["properties"].values()))

    def test_lossless_migration_preserves_every_entered_old_value(self):
        v1 = self.legacy_doc()
        for i, row in enumerate(v1["symbols"]):
            row["properties"]["lot_size_base_units"] = "100000"
            row["properties"]["digits"] = "3" if i < 2 else "5"
            row["properties"]["spread_points"] = str(i + 1)
            row["properties"]["stop_level_points"] = "0"
        original_copy = copy.deepcopy(v1)
        v2 = migrate_to_v2(v1, self.v2)
        self.assertEqual(v1, original_copy)
        for old_row in v1["symbols"]:
            new_row = self.by_symbol(v2, old_row["symbol"])
            self.assertEqual(new_row["properties"], old_row["properties"])
            self.assertTrue(all(new_row["display_properties"][field] is None
                                for field in DISPLAY_TEXT_FIELDS))
            self.assertIsNone(new_row["display_properties"]["spread_mode"])

    def test_floating_spread_is_not_misclassified_as_points(self):
        d = self.v2_doc()
        for row in d["symbols"]:
            row["display_properties"]["spread_mode"] = "FLOATING"
            self.assertIsNone(row["properties"]["spread_points"])
        self.assertEqual(check_v2(d, self.official)["status"], "INCOMPLETE")
        self.by_symbol(d, "USD/JPY")["properties"]["spread_points"] = "12"
        result = check_v2(d, self.official)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        record = next(x for x in result["pairs"] if x["symbol"] == "USD/JPY")
        self.assertIn("spread_points:FLOATING_DISPLAY_IS_NOT_NUMERIC_QUOTE",
                      record["findings"])

    def test_raw_display_modes_and_seven_days_not_guessed(self):
        d = self.v2_doc()
        row = self.by_symbol(d, "AUD/USD")
        p = row["display_properties"]
        p.update({
            "spread_mode": "FLOATING",
            "margin_currency": "AUD",
            "profit_calculation_mode": "Forex",
            "margin_calculation_mode": "Forex",
            "hedged_margin_display": "0",
            "margin_rate_display": "4.00%",
            "trade_mode_display": "Full access",
            "execution_mode_display": "Market",
            "gtc_mode_display": "GTC",
        })
        p["trading_hours_display"]["sunday"] = "Closed"
        p["trading_hours_display"]["monday"] = "00:00-23:59"
        self.assertEqual(check_v2(d, self.official)["status"], "INCOMPLETE")
        self.assertIsNone(p["trading_hours_display"]["tuesday"])

    def test_malformed_currency_spread_and_session_inputs_rejected(self):
        d = self.v2_doc()
        self.by_symbol(d, "USD/JPY")["display_properties"]["spread_mode"] = "フローティング"
        self.by_symbol(d, "EUR/JPY")["display_properties"]["margin_currency"] = "JPY-SECRET"
        self.by_symbol(d, "GBP/USD")["display_properties"]["profit_calculation_mode"] = "bad\ntext"
        self.by_symbol(d, "AUD/USD")["display_properties"]["trading_hours_display"]["monday"] = "a" * 300
        result = check_v2(d, self.official)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        by_name = {x["symbol"]: x for x in result["pairs"]}
        self.assertIn("spread_mode:INVALID_ENUM", by_name["USD/JPY"]["findings"])
        self.assertIn("margin_currency:INVALID_CURRENCY", by_name["EUR/JPY"]["findings"])
        self.assertIn("profit_calculation_mode:INVALID_DISPLAY_TEXT",
                      by_name["GBP/USD"]["findings"])
        self.assertIn("trading_hours_display.monday:INVALID_TEXT",
                      by_name["AUD/USD"]["findings"])

    def test_extra_keys_account_number_and_missing_weekday_fails_schema(self):
        d = self.v2_doc()
        d["account_number"] = "synthetic-private"
        self.assertEqual(check_v2(d, self.official)["findings"],
                         ["V2_DOCUMENT_SCHEMA"])
        self.assertNotIn("synthetic-private", str(check_v2(d, self.official)))
        d = self.v2_doc()
        del d["symbols"][0]["display_properties"]["trading_hours_display"]["saturday"]
        self.assertEqual(check_v2(d, self.official)["findings"],
                         ["V2_TRADING_HOURS_SCHEMA"])
        d = self.v2_doc()
        d["symbols"][0]["display_properties"]["secret"] = "synthetic"
        self.assertEqual(check_v2(d, self.official)["findings"],
                         ["V2_FIELD_SET"])

    def test_all_fields_only_returns_non_authorizing_comparison(self):
        d = self.v2_doc()
        for row in d["symbols"]:
            symbol = row["symbol"]
            p = row["properties"]
            p.update({
                "lot_size_base_units": "100000",
                "min_lot": "0.01", "lot_step": "0.01", "max_lot": "20",
                "point_quote": "0.001" if symbol.endswith("JPY") else "0.00001",
                "digits": "3" if symbol.endswith("JPY") else "5",
                "tick_size_points": "1",
                "tick_value_deposit_currency": "1",
                "stop_level_points": "0", "freeze_level_points": "0",
                "spread_points": None,
            })
            display = row["display_properties"]
            display["spread_mode"] = "FLOATING"
            display["margin_currency"] = symbol[:3]
            for field in DISPLAY_TEXT_FIELDS:
                if field != "margin_currency":
                    display[field] = "Example only"
            for day in DAYS:
                display["trading_hours_display"][day] = "Example only"
        result = check_v2(d, self.official)
        self.assertEqual(result["status"], "COMPARED_FIELDS_ONLY")
        self.assertNotIn("APPROVED", str(result))

    def test_reject_unsafe_legacy_input_without_mutating_it(self):
        d = self.legacy_doc()
        d["account_id"] = "test-only"
        with self.assertRaises(ValueError):
            migrate_to_v2(d, self.v2)
        d = self.legacy_doc()
        d["symbols"][0]["properties"]["min_lot"] = 0.01
        with self.assertRaises(ValueError):
            migrate_to_v2(d, self.v2)

    def test_local_migration_cli_creates_new_file_without_overwriting(self):
        with tempfile.TemporaryDirectory(prefix="fx-mt4-v2-") as tmp:
            source = Path(tmp) / "mt4_symbols_local.json"
            target = Path(tmp) / "mt4_symbols_local.v2.json"
            source.write_text(json.dumps(self.legacy_doc()), encoding="utf-8")
            original = source.read_bytes()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = run(["migrate", "--input", str(source),
                              "--output", str(target)])
            self.assertEqual(result, 0)
            self.assertTrue(target.is_file())
            self.assertEqual(load(target)["schema_version"], 2)
            self.assertEqual(original, source.read_bytes())
            previous_target = target.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                second = run(["migrate", "--input", str(source),
                              "--output", str(target)])
            self.assertEqual(second, 1)
            self.assertEqual(previous_target, target.read_bytes())
            self.assertEqual(original, source.read_bytes())

    def test_incomplete_check_cli_reports_only_symbols_and_field_names(self):
        with tempfile.TemporaryDirectory(prefix="fx-mt4-v2-") as tmp:
            path = Path(tmp) / "observations.v2.json"
            record = self.v2_doc()
            record["symbols"][0]["display_properties"]["margin_rate_display"] = "PRIVATE-SYNTHETIC-MARKER"
            path.write_text(json.dumps(record), encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = run(["check", "--input", str(path)])
            self.assertEqual(code, 2)
            self.assertIn("SUMMARY: INCOMPLETE", buf.getvalue())
            self.assertNotIn("PRIVATE-SYNTHETIC-MARKER", buf.getvalue())

    def test_direct_script_entrypoint_migrates_and_checks_offline(self):
        # Regression: python scripts/mt4_manual_symbol_v2.py must not fail
        # importing the sibling validator from Windows (or Linux) script mode.
        self._check_subprocess_entrypoint([
            sys.executable, str(ROOT / "scripts/mt4_manual_symbol_v2.py")
        ])

    def test_package_module_entrypoint_migrates_and_checks_offline(self):
        self._check_subprocess_entrypoint([
            sys.executable, "-m", "scripts.mt4_manual_symbol_v2"
        ])

    def _check_subprocess_entrypoint(self, executable):
        with tempfile.TemporaryDirectory(prefix="fx-mt4-entrypoint-") as tmp:
            source = Path(tmp) / "input.v1.json"
            destination = Path(tmp) / "output.v2.json"
            source.write_text(json.dumps(self.legacy_doc()), encoding="utf-8")
            original_bytes = source.read_bytes()
            result = subprocess.run(
                [*executable, "migrate", "--input", str(source),
                 "--output", str(destination)],
                cwd=ROOT, capture_output=True, text=True, timeout=20,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(load(destination)["schema_version"], 2)
            self.assertEqual(source.read_bytes(), original_bytes)
            check = subprocess.run(
                [*executable, "check", "--input", str(destination)],
                cwd=ROOT, capture_output=True, text=True, timeout=20,
                check=False,
            )
            self.assertEqual(check.returncode, 2, check.stderr + check.stdout)
            self.assertIn("SUMMARY: INCOMPLETE", check.stdout)
            self.assertEqual(source.read_bytes(), original_bytes)

    def test_source_or_destination_inside_git_is_refused(self):
        self.assertFalse(safe_location(V1_TEMPLATE))
        with tempfile.TemporaryDirectory(prefix="fx-mt4-v2-") as tmp:
            path = Path(tmp) / "review.v2.json"
            self.assertTrue(safe_location(path))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = run(["migrate", "--input", str(V1_TEMPLATE),
                              "--output", str(path)])
            self.assertEqual(result, 1)
            self.assertFalse(path.exists())
            self.assertIn("Git-external", out.getvalue())

    def test_original_safety_registries_remain_blocked(self):
        reg = load(ROOT / "specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(reg), [])
        for item in reg["items"]:
            self.assertIs(item["implementation_approved"], False)
            self.assertIsNone(item["owner_approval"])
        phase = next(x for x in load(ROOT / "specs/acceptance_registry.json")["phases"]
                     if x["id"] == "PHASE-1")
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
