"""Offline source-backed metadata and synthetic arithmetic for Rakuten MT4.

No MT4 import, account connection, broker prices, order or implementation approval.
"""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.check_reconciliation import check_reconciliation

ROOT = Path(__file__).resolve().parents[1]
PATH = "specs/p0_01_rakuten_mt4_public_contract_evidence.json"
D = Decimal


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class RakutenMt4PublicContractEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = load(PATH)
        cls.pairs = {x["symbol"]: x for x in cls.report["pair_evidence"]}
        cls.rules = {x["id"]: x for x in cls.report["public_broker_rules"]}

    def test_public_sources_are_separate_from_private_runtime(self):
        self.assertEqual(
            self.report["status"], "PUBLIC_DOCUMENT_VERIFIED_RUNTIME_MARKETINFO_PENDING"
        )
        sources = self.report["source_documents"]
        self.assertEqual({s["id"] for s in sources}, {
            "RAKUTEN_RULES", "METAQUOTES_SYMBOL_PROPERTIES", "METAQUOTES_SPEC_WINDOW"
        })
        self.assertEqual(len(sources), 3)
        for source in sources:
            self.assertTrue(source["url"].startswith("https://"))
            self.assertEqual(source["checked_on"], "2026-10-26")
            self.assertIn(source["evidence_kind"], {
                "BROKER_PUBLIC_RULE", "OFFICIAL_PLATFORM_API_DOC",
                "OFFICIAL_PLATFORM_MANUAL"
            })
        doc = (ROOT / "docs/p0_01_rakuten_mt4_public_contract_review_20261026.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("楽天MT4", doc)
        self.assertIn("MODE_TICKVALUE", doc)
        self.assertIn("PHASE-1 BLOCKED", doc)

    def test_four_intended_pairs_and_point_quoting(self):
        self.assertEqual(set(self.pairs), {
            "USD/JPY", "EUR/JPY", "GBP/USD", "AUD/USD"
        })
        self.assertEqual(len(self.pairs), 4)
        for symbol, pair in self.pairs.items():
            with self.subTest(symbol=symbol):
                self.assertEqual(pair["base_currency"] + "/" + pair["quote_currency"],
                                 symbol)
                expected_point = D("0.001") if pair["quote_currency"] == "JPY" else D("0.00001")
                self.assertEqual(D(pair["public_one_point_quote"]), expected_point)
                self.assertEqual(pair["public_trade_increment_base_units"], "1000")
                self.assertEqual(pair["public_sample_base_units"], "1000")
                self.assertEqual(D(pair["public_sample_lots"]), D("0.01"))
                self.assertEqual(pair["source"], "RAKUTEN_RULES")
                self.assertIs(pair["runtime_confirmed"], False)

    def test_public_lot_contract_and_fee_not_zero_total_cost(self):
        self.assertEqual(D(self.rules["RR-01"]["value"]), D("100000"))
        self.assertEqual(D(self.rules["RR-02"]["value"]), D("1000"))
        self.assertEqual(D(self.rules["RR-03"]["value"]), D("0.01"))
        self.assertEqual(D(self.rules["RR-05"]["value"]), D("2000000"))
        self.assertEqual(D(self.rules["RR-01"]["value"]) *
                         D(self.rules["RR-03"]["value"]),
                         D(self.rules["RR-02"]["value"]))
        self.assertEqual(self.rules["RR-04"]["value"], "0")
        self.assertIn("spreads", self.rules["RR-04"]["qualification"])
        self.assertEqual(self.rules["RR-06"]["unit"], "margin_only")
        self.assertEqual(self.rules["RR-07"]["value"], "MT4_MUST_BE_RUNNING_TO_TRAIL")

    def test_symbol_mode_fields_unverified_with_no_private_values(self):
        fields = self.report["read_only_mt4_fields"]
        needed = {
            "MODE_LOTSIZE", "MODE_MINLOT", "MODE_LOTSTEP", "MODE_MAXLOT",
            "MODE_POINT", "MODE_DIGITS", "MODE_TICKVALUE", "MODE_TICKSIZE",
            "MODE_STOPLEVEL", "MODE_FREEZELEVEL", "MODE_SPREAD", "MODE_BID",
            "MODE_ASK", "MODE_TIME"
        }
        self.assertEqual({x["field"] for x in fields}, needed)
        self.assertEqual(len(fields), len(needed))
        self.assertTrue(all(
            x["validation_status"] == "PENDING_LOCAL_READ_ONLY_OBSERVATION"
            for x in fields
        ))
        for pair in self.pairs.values():
            for field in ("verified_account_tickvalue", "verified_account_ticksize",
                          "verified_lotstep", "verified_minlot", "verified_stoplevel"):
                self.assertIsNone(pair[field])

    def test_pip_difference_and_usd_jpy_conversion_examples(self):
        examples = self.report["arithmetic_illustrations"]
        self.assertEqual(
            examples["status"], "HYPOTHETICAL_NOT_BROKER_QUOTED_LOSS_OR_TRADE_PERMISSION"
        )
        self.assertEqual(examples["hypothetical_usd_jpy_conversion"], "150")
        cases = {x["id"]: x for x in examples["cases"]}
        self.assertEqual(set(cases), {f"BI-{i:02d}" for i in range(1, 7)})
        for case in cases.values():
            with self.subTest(case=case["id"]):
                pair = self.pairs[case["symbol"]]
                self.assertEqual(D(case["volume_lots"]) * D("100000"),
                                 D(case["volume_base"]))
                quote_loss = (D(case["volume_base"]) *
                              D(case["adverse_price_move_quote"]))
                self.assertEqual(quote_loss, D(case["loss_quote_currency"]))
                factor = (D("1") if pair["quote_currency"] == "JPY"
                          else D(examples["hypothetical_usd_jpy_conversion"]))
                self.assertEqual(quote_loss * factor,
                                 D(case["loss_jpy_hypothetical"]))

    def test_min_lot_can_exceed_risk_gate_in_synthetic_scenarios(self):
        cases = {x["id"]: x for x in self.report["arithmetic_illustrations"]["cases"]}
        equity_jpy = D("100000")
        single_limit = equity_jpy * D("0.005")
        self.assertEqual(single_limit, D("500"))
        self.assertEqual(D(cases["BI-05"]["loss_jpy_hypothetical"]), single_limit)
        self.assertGreater(D(cases["BI-06"]["loss_jpy_hypothetical"]), single_limit)
        self.assertGreaterEqual(len(self.report["remaining_form01_and_form03_gates"]), 8)
        self.assertTrue(any("MODE_TICKVALUE" in line for line in
                            self.report["remaining_form01_and_form03_gates"]))

    def test_registry_and_global_live_gate_stay_blocked(self):
        flags = self.report["safety_status"]
        for key in ("source_reconciliation_completed",
                    "formula_implementation_approved", "owner_approved_for_safety",
                    "human_safety_approval", "forward_trading_enabled",
                    "can_send_orders"):
            self.assertIs(flags[key], False)
        self.assertEqual(flags["phase_1"], "BLOCKED")
        registry = load("specs/reconciliation_registry.json")
        self.assertEqual(check_reconciliation(registry), [])
        for row in registry["items"]:
            self.assertIs(row["implementation_approved"], False)
            self.assertIsNone(row["owner_approval"])
        phase = next(
            x for x in load("specs/acceptance_registry.json")["phases"]
            if x["id"] == "PHASE-1"
        )
        self.assertEqual(phase["status"], "BLOCKED")
        self.assertIsNone(phase["approval"])


if __name__ == "__main__":
    unittest.main()
