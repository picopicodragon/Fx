"""Offline-only policy checks for MT4 read-only evidence plan and v2 display status."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation
from scripts.mt4_manual_symbol_v2 import (
    DAYS, DISPLAY_TEXT_FIELDS, EXPECTED_PAIRS, OFFICIAL, ROOT,
    V2_TEMPLATE, check_v2, run,
)

PLAN = ROOT / "specs/p0_01_mt4_readonly_observation_plan.json"
DOCUMENT = ROOT / "docs/p0_01_mt4_readonly_observation_plan_20261026.md"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class Mt4ReadOnlyObservationDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = load(PLAN)
        cls.template = load(V2_TEMPLATE)
        cls.official = load(OFFICIAL)

    def test_five_missing_numeric_fields_have_exact_official_api_map(self):
        expected = {
            "min_lot": "MODE_MINLOT",
            "lot_step": "MODE_LOTSTEP",
            "point_quote": "MODE_POINT",
            "tick_size_points": "MODE_TICKSIZE",
            "tick_value_deposit_currency": "MODE_TICKVALUE",
        }
        rows = self.plan["pending_runtime_fields"]
        self.assertEqual(len(rows), len(expected))
        self.assertEqual(
            {row["v2_field"]: row["official_mql4_property"] for row in rows},
            expected,
        )
        self.assertTrue(all(row["constraint"] == "finite_positive_decimal"
                            for row in rows))
        self.assertIn("MODE_TICKSIZE", DOCUMENT.read_text(encoding="utf-8"))

    def test_all_four_accounts_have_no_fake_terminal_attestation(self):
        self.assertEqual(
            self.plan["status"], "DESIGN_ONLY_ALL_RUNTIME_VALUES_PENDING"
        )
        statuses = self.plan["symbol_status"]
        self.assertEqual({p["symbol"] for p in statuses}, set(EXPECTED_PAIRS))
        needed = {x["v2_field"] for x in self.plan["pending_runtime_fields"]}
        for pair in statuses:
            self.assertEqual(pair["runtime_observation_status"], "PENDING")
            self.assertEqual(set(pair["verified_values"]), needed)
            self.assertTrue(all(v is None for v in pair["verified_values"].values()))
            self.assertIs(pair["production_usable"], False)

    def test_contract_quote_source_and_units_do_not_mix(self):
        fields = {r["v2_field"]: r for r in self.plan["pending_runtime_fields"]}
        self.assertEqual(fields["tick_size_points"]["value_unit"], "points_per_tick")
        self.assertIn(
            "deposit_currency",
            fields["tick_value_deposit_currency"]["value_unit"]
        )
        self.assertIn(
            "FORM-03", fields["tick_value_deposit_currency"]["requirement"]
        )
        x = {v["property"]: v for v in self.plan["crosscheck_fields"]}
        self.assertIn("MODE_TIME", x)
        self.assertIn("MODE_BID", x)
        self.assertIn("MODE_ASK", x)
        self.assertIsNone(x["MODE_TIME"]["v2_field"])
        self.assertIn("floating", x["MODE_STOPLEVEL"]["reason"].lower())
        self.assertIn("variable market observation", x["MODE_SPREAD"]["reason"].lower())

    def test_quote_and_trade_sessions_are_two_independent_methods(self):
        t = self.plan["session_design"]
        self.assertEqual(t["quote_api"], "SymbolInfoSessionQuote")
        self.assertEqual(t["trade_api"], "SymbolInfoSessionTrade")
        self.assertTrue(t["allow_multiple_sessions"])
        self.assertTrue(t["must_validate_server_timezone_separately"])
        self.assertEqual(tuple(t["weekdays"]), DAYS)
        self.assertEqual(t["manual_v2_capture"], "raw_text_only")
        self.assertEqual(
            set(self.plan["evidence_urls"]), {
                "mql4_symbol_constants", "mql4_marketinfo",
                "mql4_quote_sessions", "mql4_trade_sessions",
                "rakuten_mt4_public_rules"
            }
        )

    def test_all_unknown_conditions_are_fail_closed_and_no_trading_approval(self):
        reasons = self.plan["fail_closed_cases"]
        self.assertEqual(len(reasons), 12)
        self.assertEqual({x["id"] for x in reasons},
                         {f"RC-{i:02d}" for i in range(1, 13)})
        self.assertTrue(all(x["decision"] == "KEEP_UNVERIFIED_NO_ORDER"
                            for x in reasons))
        for key in ("terminal_readonly_code_implemented", "terminal_connected",
                    "broker_queried", "orders_generated", "manual_v2_input_value_exported"):
            self.assertIs(self.plan["permissions"][key], False)
        for key in ("formula_01_approved", "formula_03_approved",
                    "implementation_approved", "owner_approved_for_safety",
                    "human_safety_approval", "forward_trading_enabled"):
            self.assertIs(self.plan["safety_gates"][key], False)
        self.assertEqual(self.plan["safety_gates"]["phase_1"], "BLOCKED")
        self.assertEqual(
            check_reconciliation(load(ROOT / "specs/reconciliation_registry.json")), []
        )

    def test_v2_blank_display_fields_are_reported_separately(self):
        data = copy.deepcopy(self.template)
        result = check_v2(data, self.official)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(len(result["pairs"]), 4)
        for pair in result["pairs"]:
            self.assertEqual(pair["display_capture_status"], "PENDING_DISPLAY_INPUT")
            self.assertEqual(len(pair["missing_display_fields"]), 16)
            self.assertIn("trading_hours_display.monday",
                          pair["missing_display_fields"])
            self.assertIn("spread_mode", pair["missing_display_fields"])
            self.assertIn("min_lot", pair["missing_fields"])

    def test_every_display_field_entered_still_does_not_verify_five_runtime_values(self):
        data = copy.deepcopy(self.template)
        for pair in data["symbols"]:
            display = pair["display_properties"]
            display["spread_mode"] = "FLOATING"
            display["margin_currency"] = pair["symbol"][:3]
            for name in DISPLAY_TEXT_FIELDS:
                if name != "margin_currency":
                    display[name] = "Observed manually but not independently verified"
            for day in DAYS:
                display["trading_hours_display"][day] = (
                    "呼値(00:00-24:00) / 取引(01:00-23:55)"
                )
        result = check_v2(data, self.official)
        self.assertEqual(result["status"], "INCOMPLETE")
        for pair in result["pairs"]:
            self.assertEqual(
                pair["display_capture_status"], "ALL_DISPLAY_FIELDS_RECORDED_NOT_VERIFIED"
            )
            self.assertEqual(pair["missing_display_fields"], [])
            self.assertIn("tick_value_deposit_currency", pair["missing_fields"])
            self.assertNotIn("APPROVED", str(pair))

    def test_v2_cli_prints_only_missing_labels_or_completion_not_entered_text(self):
        data = copy.deepcopy(self.template)
        data["symbols"][0]["display_properties"]["profit_calculation_mode"] = (
            "SYNTHETIC-SECRET-MARKER"
        )
        with tempfile.TemporaryDirectory(prefix="fx-mt4-display-") as folder:
            file_path = Path(folder) / "input.v2.json"
            file_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                status = run(["check", "--input", str(file_path)])
            output = stream.getvalue()
            self.assertEqual(status, 2)
            self.assertIn("PENDING DISPLAY FIELDS", output)
            self.assertIn("SUMMARY: INCOMPLETE", output)
            self.assertNotIn("SYNTHETIC-SECRET-MARKER", output)


if __name__ == "__main__":
    unittest.main()
