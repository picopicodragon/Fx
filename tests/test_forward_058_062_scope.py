"""FWD-058-062: future regressions must not reintroduce the superseded four pairs.

This test intentionally reads the current authoritative contract and active
code, not the historical Q3 decision ledger. This does not certify trading.
"""
import unittest
from pathlib import Path

from research.offline_backtest import PAIRS as RESEARCH_PAIRS, InputError
from research.forward_mt4_v2_quote import PAIRS_V2, parse, COLUMNS
from research.forward_mt4_v2_four_pair import review as aggregate
from research.forward_mt4_v2_source_contract import review as static_review
from research.forward_active_pair_scope import inspect, FORMAL_PAIRS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4"
NOW = "2026-11-10T03:00:00Z"


def quote(pair):
    conv = "1.00000" if pair.endswith("/JPY") else "150.00000"
    row = [NOW, pair, "150.01", "150.03", conv,
           "2026-11-10T11:59:50", "2026-11-10T12:00:00",
           "10", "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED"]
    return (",".join(COLUMNS) + "\n" + ",".join(row) + "\n").encode()


class FormalScopeTests(unittest.TestCase):
    def test_authoritative_scope_is_three_pairs_in_all_modules(self):
        self.assertEqual(FORMAL_PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))
        self.assertEqual(tuple(RESEARCH_PAIRS), FORMAL_PAIRS)
        self.assertEqual(tuple(PAIRS_V2), FORMAL_PAIRS)

    def test_all_three_are_accepted_research_only(self):
        rows = [parse(quote(pair), asof_utc=NOW) for pair in FORMAL_PAIRS]
        result = aggregate(rows, asof_utc=NOW)
        self.assertEqual(result["pairs_present"], sorted(FORMAL_PAIRS))
        self.assertEqual(result["status"],
                         "MT4_V2_THREE_PAIR_RESEARCH_HOLD_NO_GO")
        self.assertTrue(result["three_pair_scope_consistent_with_research"])
        self.assertFalse(result["real_orders_permitted"])

    def test_superseded_pairs_are_disallowed(self):
        for pair in ("GBP/USD", "AUD/USD"):
            with self.subTest(pair=pair):
                with self.assertRaises(InputError):
                    parse(quote(pair), asof_utc=NOW)

    def test_missing_eurusd_blocks_without_missing_out_of_scope(self):
        rows = [parse(quote(pair), asof_utc=NOW) for pair in FORMAL_PAIRS[:2]]
        result = aggregate(rows, asof_utc=NOW)
        self.assertIn("MISSING_EUR_USD", result["blocking_reasons"])
        self.assertNotIn("MISSING_GBP_USD", result["blocking_reasons"])
        self.assertNotIn("MISSING_AUD_USD", result["blocking_reasons"])

    def test_export_source_mentions_only_approved_chart_symbols(self):
        raw = SOURCE.read_bytes()
        for symbol in ("USDJPY", "EURJPY", "EURUSD"):
            self.assertIn(('symbol == "' + symbol + '"').encode(), raw)
        for symbol in ("GBPUSD", "AUDUSD"):
            self.assertNotIn(('symbol == "' + symbol + '"').encode(), raw)
        self.assertIn(b'if(pair == "EUR/USD")', raw)

    def test_static_contract_rejects_added_obsolete_pair(self):
        raw = SOURCE.read_bytes()
        contaminated = raw + b'\nvoid added(){ if(symbol == "GBPUSD") Print("bad"); }'
        result = static_review(contaminated)
        self.assertFalse(result["static_contract_passed"])
        self.assertIn("OUT_OF_SCOPE_SYMBOL_GBPUSD", result["static_failures"])

    def test_active_pair_scope_audit_is_no_go_even_when_consistent(self):
        result = inspect(SOURCE.read_bytes())
        self.assertTrue(result["pair_scope_consistent"])
        self.assertEqual(result["approved_pairs"], list(FORMAL_PAIRS))
        self.assertFalse(result["real_orders_permitted"])
        self.assertTrue(result["safety_hold_latched"])

    def test_active_pair_scope_rejects_obsolete_symbol(self):
        raw = SOURCE.read_bytes() + b'\nvoid added(){ if(symbol == "AUDUSD") Print("bad"); }'
        result = inspect(raw)
        self.assertFalse(result["pair_scope_consistent"])
        self.assertIn("MT4_V2_SOURCE_CONTRACT_FAILED", result["blocking_reasons"])

    def test_formal_docs_have_current_scope_and_history(self):
        for filename in ("README.md", "MASTER_SPEC.md", "DECISIONS.md"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn("USD/JPY", text)
            self.assertIn("EUR/JPY", text)
            self.assertIn("EUR/USD", text)
            self.assertIn("2026-11-10", text)
        doc = (ROOT / "docs/forward_053_057_mt4_v2_four_pairs.md").read_text(
            encoding="utf-8")
        self.assertIn("現行正式仕様", doc)
        self.assertIn("旧Q3", doc)


if __name__ == "__main__":
    unittest.main()
