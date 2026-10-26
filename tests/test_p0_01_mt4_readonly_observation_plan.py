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
            self.plan["status"], "READONLY_MQL4_COMPILATION_OWNER_REPORTED_ALL_RUNTIME_VALUES_PENDING"
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
        self.assertIs(self.plan["permissions"]["terminal_readonly_code_implemented"], True)
        self.assertIs(self.plan["permissions"]["terminal_readonly_source_created"], True)
        self.assertIs(self.plan["permissions"]["one_shot_source_default_disabled"], True)
        self.assertIs(self.plan["permissions"]["read_only_terminal_execution_requires_separate_owner_security_review"], True)
        for key in ("terminal_connected", "terminal_deployed",
                    "terminal_execution_approved",
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

    def test_owner_reported_compile_does_not_enable_terminal_execution(self):
        permission = self.plan["permissions"]
        self.assertIs(permission["terminal_compilation_approved"], True)
        self.assertEqual(
            permission["terminal_compile_approval_scope"],
            "METAEDITOR_F7_ONLY_NO_TERMINAL_EXECUTION_2026_10_26",
        )
        self.assertIs(permission["terminal_compiled"], True)
        self.assertIs(permission["terminal_deployed"], False)
        self.assertIs(permission["terminal_execution_approved"], False)
        self.assertIs(permission["broker_queried"], False)
        self.assertIs(permission["orders_generated"], False)
        self.assertIs(self.plan["safety_gates"]["forward_trading_enabled"], False)
        self.assertEqual(self.plan["safety_gates"]["phase_1"], "BLOCKED")

    def test_owner_compiler_report_is_not_independent_attestation(self):
        permissions = self.plan["permissions"]
        self.assertEqual(
            self.plan["status"],
            "READONLY_MQL4_COMPILATION_OWNER_REPORTED_ALL_RUNTIME_VALUES_PENDING"
        )
        self.assertEqual(
            permissions["terminal_compilation_evidence_status"],
            "OWNER_REPORTED_RESULT_NOT_INDEPENDENTLY_VERIFIED"
        )
        report = permissions["terminal_compilation_owner_report"]
        self.assertEqual(report["source"], "DIRECT_OWNER_CHAT_REPORT")
        self.assertEqual(report["errors"], 0)
        self.assertEqual(report["warnings"], 0)
        self.assertEqual(report["elapsed_ms"], 291)
        self.assertFalse(report["compiled_ex4_attested"])
        self.assertFalse(report["source_hash_attested"])
        self.assertFalse(report["compiler_version_attested"])
        self.assertFalse(permissions["terminal_execution_approved"])
        for symbol in self.plan["symbol_status"]:
            self.assertEqual(symbol["runtime_observation_status"], "PENDING")
            self.assertFalse(symbol["production_usable"])
            self.assertTrue(all(v is None for v in symbol["verified_values"].values()))

    def test_pre_execution_evidence_does_not_approve_mql4_runtime(self):
        record = self.plan["permissions"]["pre_execution_review"]
        self.assertEqual(record["status"], "PARTIAL_LOCAL_OFFLINE_REVIEW_ONLY")
        self.assertEqual(record["python_unittest_count"], 409)
        self.assertEqual(record["python_unittest_status"], "OWNER_REPORTED_OK")
        self.assertEqual(record["static_source_audit_status"], "OWNER_REPORTED_PASS")
        self.assertEqual(record["repo_to_compile_mq4_sha256"],
                         "OWNER_REPORTED_MATCH_HASH_VALUES_NOT_SHARED")
        self.assertEqual(record["ex4_file_exists"], "OWNER_REPORTED_TRUE")
        self.assertEqual(record["ex4_size_bytes"], 13644)
        for key in ("ex4_binary_reproducibly_bound_to_source",
                    "terminal_symbol_mapping_checked",
                    "terminal_account_type_checked",
                    "terminal_log_handling_checked",
                    "terminal_execution_allowed"):
            self.assertIs(record[key], False)
        self.assertFalse(self.plan["permissions"]["terminal_execution_approved"])
        self.assertFalse(self.plan["permissions"]["terminal_deployed"])
        self.assertFalse(self.plan["permissions"]["broker_queried"])
        self.assertFalse(self.plan["safety_gates"]["forward_trading_enabled"])
        self.assertEqual(self.plan["safety_gates"]["phase_1"], "BLOCKED")

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

    def test_unentered_weekend_does_not_claim_market_is_closed(self):
        record = check_v2(copy.deepcopy(self.template), self.official)
        for pair in record["pairs"]:
            self.assertEqual(pair["weekend_session_display_status"], {
                "saturday": "UNRECORDED", "sunday": "UNRECORDED"
            })
            self.assertEqual(pair["status"], "INCOMPLETE")
            self.assertIn("trading_hours_display.saturday",
                          pair["missing_display_fields"])

    def test_explicitly_observed_no_weekend_session_stays_unverified(self):
        data = copy.deepcopy(self.template)
        for item in data["symbols"]:
            hours = item["display_properties"]["trading_hours_display"]
            hours["saturday"] = "NO_SESSION_DISPLAYED"
            hours["sunday"] = "NO_SESSION_DISPLAYED"
        record = check_v2(data, self.official)
        self.assertEqual(record["status"], "INCOMPLETE")
        for pair in record["pairs"]:
            self.assertEqual(pair["weekend_session_display_status"], {
                "saturday": "NO_SESSION_DISPLAYED_UNVERIFIED",
                "sunday": "NO_SESSION_DISPLAYED_UNVERIFIED"
            })
            self.assertNotIn("trading_hours_display.saturday",
                             pair["missing_display_fields"])
            self.assertIn("tick_value_deposit_currency", pair["missing_fields"])

    def test_weekend_raw_text_is_preserved_but_never_echoed(self):
        data = copy.deepcopy(self.template)
        data["symbols"][0]["display_properties"]["trading_hours_display"]["saturday"] = (
            "呼値(00:00-24:00) / 取引(01:00-23:55)"
        )
        data["symbols"][0]["display_properties"]["trading_hours_display"]["sunday"] = (
            "PRIVATE-DO-NOT-ECHO"
        )
        before = copy.deepcopy(data)
        checked = check_v2(data, self.official)
        self.assertEqual(data, before)
        self.assertEqual(
            checked["pairs"][0]["weekend_session_display_status"],
            {"saturday": "DISPLAY_TEXT_RECORDED_UNVERIFIED",
             "sunday": "DISPLAY_TEXT_RECORDED_UNVERIFIED"}
        )
        self.assertNotIn("PRIVATE-DO-NOT-ECHO", str(checked))
        self.assertNotIn("01:00-23:55", str(checked))

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
