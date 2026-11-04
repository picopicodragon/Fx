"""RISK-3P-03 only checks an offline unverified three-pair document.

Legacy 4-pair v1/v2 tools are intentionally not imported or edited. No market
data, broker connection, account information, approvals or order generation.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import review_mt4_manual_symbol_3p_v3 as mod


def template():
    return json.loads(mod.TEMPLATE.read_text(encoding="utf-8"))


def fixture_complete_five():
    doc = template()
    for row in doc["symbols"]:
        name = row["symbol"].replace("/", "")
        row["observation"].update({
            "terminal_symbol": name,
            "observed_at_utc": "2026-11-01T00:00:00Z",
            "source_kind": "MANUAL_MT4_SPECIFICATION",
        })
        row["properties"].update({
            "min_lot": "0.01",
            "lot_step": "0.01",
            "point_quote": "0.001",
            "tick_size_points": "1",
            "tick_value_deposit_currency": "1",
        })
    return doc


def by_pair(doc, pair="EUR/USD"):
    return next(row for row in doc["symbols"] if row["symbol"] == pair)


class ThreePairV3OfflineTests(unittest.TestCase):
    def held(self, result):
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(result["production_authorized"], False)
        self.assertIs(result["broker_contract_verified"], False)
        self.assertIs(result["g1_real_world_verified"], False)
        self.assertIs(result["broker_queried"], False)
        self.assertIs(result["order_allowed"], False)
        self.assertIs(result["automatic_retry_allowed"], False)
        self.assertIs(result["stop_release_allowed"], False)
        self.assertIsNone(result["verified_values"])

    def assert_review(self, doc, expected):
        r = mod.review_snapshot(doc)
        self.assertEqual(r["status"], mod.REVIEW)
        self.held(r)
        self.assertIn(expected, json.dumps(r, ensure_ascii=False))
        return r

    def test_baseline_template_has_three_pairs_and_no_forged_values(self):
        doc = template()
        self.assertEqual(doc["schema_version"], 3)
        self.assertEqual([row["symbol"] for row in doc["symbols"]],
                         ["USD/JPY", "EUR/JPY", "EUR/USD"])
        for row in doc["symbols"]:
            self.assertTrue(all(v is None for v in row["properties"].values()))
            self.assertTrue(all(v is None for v in row["observation"].values()))
            self.assertTrue(all(
                v is None for k, v in row["display_properties"].items()
                if k != "trading_hours_display"))
            self.assertTrue(all(
                v is None for v in
                row["display_properties"]["trading_hours_display"].values()))
        r = mod.review_snapshot(doc)
        self.assertEqual(r["status"], mod.INCOMPLETE)
        for pair in r["pairs"]:
            self.assertEqual(pair["status"], mod.INCOMPLETE)
            self.assertEqual(len(pair["missing_fields"]), len(mod.FIVE) + 3)
        self.held(r)

    def test_fake_full_five_field_snapshot_remains_unverified_no_go(self):
        doc = fixture_complete_five()
        r = mod.review_snapshot(doc)
        self.assertEqual(r["status"], mod.STRUCTURAL)
        self.assertEqual(len(r["pairs"]), 3)
        self.assertTrue(all(row["status"] == mod.STRUCTURAL for row in r["pairs"]))
        self.held(r)
        self.assertEqual(doc["data_state"], "UNVERIFIED_LOCAL_VALUES")

    def test_missing_one_of_five_or_missing_eurusd_metadata_is_incomplete(self):
        for field in mod.FIVE:
            with self.subTest(field=field):
                d = fixture_complete_five()
                by_pair(d)["properties"][field] = None
                r = mod.review_snapshot(d)
                self.assertEqual(r["status"], mod.INCOMPLETE)
                missing = next(x for x in r["pairs"] if x["symbol"] == "EUR/USD")
                self.assertIn(field, missing["missing_fields"])
                self.held(r)
        for field in ("terminal_symbol", "observed_at_utc", "source_kind"):
            with self.subTest(field=field):
                d = fixture_complete_five()
                by_pair(d)["observation"][field] = None
                self.assertEqual(mod.review_snapshot(d)["status"], mod.INCOMPLETE)

    def test_unknown_or_unapproved_symbol_list_is_rejected(self):
        for pairs in (
            ["USD/JPY", "EUR/JPY", "GBP/USD"],
            ["USD/JPY", "EUR/JPY", "AUD/USD"],
            ["USD/JPY", "EUR/JPY"],
            ["USD/JPY", "EUR/JPY", "EUR/USD", "GBP/USD"],
            ["USD/JPY", "USD/JPY", "EUR/USD"],
        ):
            with self.subTest(pairs=pairs):
                d = template()
                while len(d["symbols"]) < len(pairs):
                    d["symbols"].append(copy.deepcopy(d["symbols"][0]))
                d["symbols"] = d["symbols"][:len(pairs)]
                for row, pair in zip(d["symbols"], pairs):
                    row["symbol"] = pair
                self.assert_review(d, "SYMBOL_SET")

    def test_document_identity_and_extra_keys_do_not_promote(self):
        for key, value in (
            ("schema_version", 2), ("schema_version", True),
            ("kind", "BROKER_VERIFIED"), ("source_type", "BROKER_LIVE"),
            ("data_state", "VERIFIED"), ("scope", "PRODUCTION_ALLOWED"),
            ("instructions", None),
        ):
            with self.subTest(key=key):
                d = template()
                d[key] = value
                self.assert_review(d, "DOCUMENT_IDENTITY")
        d = fixture_complete_five()
        d["account_id"] = "PRIVATE-CANARY"
        r = self.assert_review(d, "DOCUMENT_SCHEMA")
        self.assertNotIn("PRIVATE-CANARY", str(r))

    def test_row_observation_properties_and_display_key_integrity(self):
        for sub, key, value, label in (
            ("observation", "account_id", "private", "OBSERVATION_SCHEMA"),
            ("properties", "trade_permission", True, "PROPERTY_SCHEMA"),
            ("display_properties", "secret", "PRIVATE", "DISPLAY_SCHEMA"),
        ):
            with self.subTest(sub=sub):
                d = fixture_complete_five()
                by_pair(d)[sub][key] = value
                r = self.assert_review(d, label)
                self.assertNotIn("PRIVATE", str(r))
        d = fixture_complete_five()
        by_pair(d)["properties"].pop("min_lot")
        self.assert_review(d, "PROPERTY_SCHEMA")

    def test_terminal_exact_name_and_source_are_not_attested(self):
        for raw in ("EURJPY", "USDJPY", "EUR/USD", "EURUSD-TOO-LONG-SYMBOL-SUFFIX",
                    "EURUSD\nsecret", "eurusd", "", True, 1):
            with self.subTest(name=repr(raw)):
                d = fixture_complete_five()
                by_pair(d)["observation"]["terminal_symbol"] = raw
                self.assert_review(d, "terminal_symbol:INVALID")
        d = fixture_complete_five()
        by_pair(d)["observation"]["terminal_symbol"] = "EURUSD.r"
        self.assertEqual(mod.review_snapshot(d)["status"], mod.STRUCTURAL)
        for raw in ("BROKER_VERIFIED", "PUBLIC", "", True, 1):
            with self.subTest(source=repr(raw)):
                d = fixture_complete_five()
                by_pair(d)["observation"]["source_kind"] = raw
                self.assert_review(d, "source_kind:INVALID")

    def test_missing_or_invalid_utc_receipt_is_rejected_not_aged_into_proof(self):
        for value in ("2026-11-01", "2026-11-01T00:00:00+09:00",
                      "2026-11-01T00:00:00", "2026-13-01T00:00:00Z",
                      "2026-11-01T25:00:00Z", "0000-01-01T00:00:00Z",
                      "1970-01-01T00:00:00Z", True, 1, "NO_DATE"):
            with self.subTest(timestamp=repr(value)):
                d = fixture_complete_five()
                by_pair(d)["observation"]["observed_at_utc"] = value
                self.assert_review(d, "observed_at_utc:INVALID")

    def test_positive_decimal_rejects_float_bool_nan_exponent_and_zero(self):
        for value in (0.01, 1, True, False, "0", "-1", "+1", "NaN",
                      "Infinity", "1e-4", " 1", "", "01", ".001",
                      "0.0000000000001", "12345678901234567890", object()):
            with self.subTest(value=repr(value)):
                d = fixture_complete_five()
                by_pair(d)["properties"]["min_lot"] = value
                self.assert_review(d, "min_lot:INVALID_DECIMAL_OR_RANGE")

    def test_five_field_relationship_does_not_claim_actual_contract(self):
        d = fixture_complete_five()
        by_pair(d)["properties"]["lot_step"] = "0.02"
        self.assert_review(d, "lot_step:GREATER_THAN_MIN_LOT")
        d = fixture_complete_five()
        by_pair(d)["properties"]["max_lot"] = "0.001"
        self.assert_review(d, "max_lot:LESS_THAN_MIN_LOT")
        d = fixture_complete_five()
        by_pair(d)["properties"]["digits"] = "5"
        self.assert_review(d, "point_quote:DIGITS_INCONSISTENT")
        d = fixture_complete_five()
        by_pair(d)["properties"]["digits"] = "3"
        self.assertEqual(mod.review_snapshot(d)["status"], mod.STRUCTURAL)
        self.held(mod.review_snapshot(d))

    def test_nonnegative_optional_fields_accept_zero_only(self):
        d = fixture_complete_five()
        for name in ("stop_level_points", "freeze_level_points", "spread_points"):
            by_pair(d)["properties"][name] = "0"
        self.assertEqual(mod.review_snapshot(d)["status"], mod.STRUCTURAL)
        by_pair(d)["properties"]["stop_level_points"] = "-1"
        self.assert_review(d, "stop_level_points:INVALID_DECIMAL_OR_RANGE")

    def test_floating_spread_is_never_mistaken_for_numeric_quote(self):
        d = fixture_complete_five()
        by_pair(d)["display_properties"]["spread_mode"] = "FLOATING"
        self.assertEqual(mod.review_snapshot(d)["status"], mod.STRUCTURAL)
        by_pair(d)["properties"]["spread_points"] = "1"
        self.assert_review(d, "spread_points:FLOATING_DISPLAY_NOT_QUOTE")
        by_pair(d)["properties"]["spread_points"] = None
        by_pair(d)["display_properties"]["spread_mode"] = "フローティング"
        self.assert_review(d, "spread_mode:INVALID")

    def test_private_display_values_and_broken_days_rejected_without_echo(self):
        d = fixture_complete_five()
        by_pair(d)["display_properties"]["profit_calculation_mode"] = "private\ncanary"
        r = self.assert_review(d, "profit_calculation_mode:INVALID")
        self.assertNotIn("canary", str(r))
        d = fixture_complete_five()
        by_pair(d)["display_properties"]["trading_hours_display"]["monday"] = "\rSECRET"
        r = self.assert_review(d, "trading_hours_display:INVALID_TEXT")
        self.assertNotIn("SECRET", str(r))
        d = fixture_complete_five()
        del by_pair(d)["display_properties"]["trading_hours_display"]["tuesday"]
        self.assert_review(d, "trading_hours_display:INVALID_SCHEMA")

    def test_legacy_v1_v2_templates_unchanged_and_still_four_pairs(self):
        for filename in ("p0_01_mt4_manual_symbol_template.json",
                         "p0_01_mt4_manual_symbol_template_v2.json"):
            d = json.loads((mod.ROOT / "specs" / filename).read_text(encoding="utf-8"))
            self.assertEqual([x["symbol"] for x in d["symbols"]],
                             ["USD/JPY", "EUR/JPY", "GBP/USD", "AUD/USD"])
        self.held(mod.review_snapshot(template()))

    def test_cli_does_not_emit_private_values_and_rejects_repo_template(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = mod.main(["--input", str(mod.TEMPLATE)])
        self.assertEqual(rc, 1)
        self.assertIn("outside Git", out.getvalue())
        doc = fixture_complete_five()
        by_pair(doc)["properties"]["min_lot"] = "canary12345"
        with tempfile.TemporaryDirectory(prefix="fx-3p-v3-") as tmp:
            p = Path(tmp) / "private.json"
            p.write_text(json.dumps(doc), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.main(["--input", str(p)])
            self.assertEqual(rc, 1)
            self.assertNotIn("canary12345", out.getvalue())
            self.assertIn("REVIEW_REQUIRED", out.getvalue())

    def test_cli_never_returns_success_even_when_all_five_present(self):
        with tempfile.TemporaryDirectory(prefix="fx-3p-v3-") as tmp:
            p = Path(tmp) / "private.json"
            p.write_text(json.dumps(fixture_complete_five()), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mod.main(["--input", str(p)])
            self.assertEqual(rc, 3)
            self.assertIn("FIVE_FIELDS_PRESENT_UNVERIFIED", out.getvalue())
            self.assertIn("runtime NO_GO", out.getvalue())


if __name__ == "__main__":
    unittest.main()
