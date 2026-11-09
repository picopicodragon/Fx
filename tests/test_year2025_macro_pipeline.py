"""2025 annual-source and period research: synthetic tests; no paid APIs."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from research import year2025_macro_pipeline as annual
from research import macro_ai_backtest as replay
from research import macro_ai_generate as ai
from research.offline_backtest import Bar, InputError, PAIRS


def synthetic_bars():
    dates = [datetime(2025, m, day, 12, tzinfo=timezone.utc)
             for m, day in ((1, 3), (1, 6), (2, 3), (3, 3), (4, 3),
                            (5, 5), (6, 3), (7, 3), (8, 4),
                            (9, 3), (9, 30), (10, 1), (10, 2),
                            (11, 4), (12, 29), (12, 30))]
    out = []
    for date in dates:
        for pair in PAIRS:
            price = D("150") if pair == "USD/JPY" else (
                D("160") if pair == "EUR/JPY" else D("1.1"))
            out.append(Bar(date, pair, price, price + D("0.1"),
                           price - D("0.1"), price, D("1"),
                           D("150") if pair == "EUR/USD" else D(1),
                           "HOLD"))
    return out


def pricing():
    return {
        "aligned_bars_per_pair": 5000,
        "input_checksums": {"usdjpy_bid_sha256": "synthetic"},
        "known_limitations": ["synthetic"],
    }


class FullYearMacroTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_real_official_corpus_has_all_months_three_pairs(self):
        sources, meta = annual.check_corpus(annual.EVIDENCE)
        self.assertEqual(len(sources), 36)
        self.assertEqual(meta["months_with_evidence"], list(range(1, 13)))
        self.assertEqual(meta["currency_pairs"], list(PAIRS))
        self.assertEqual(annual.expected_decisions(sources), 108)
        self.assertGreater(meta["market_expectations_missing"], 20)
        self.assertFalse(meta["market_consensus_point_in_time_authenticated"])
        self.assertTrue(all(
            item["market_expectation"] == ""
            for key, item in sources.items()
            if key.startswith("EUECB")))
        self.assertEqual(sources["USNFP20251120"]["available_at_utc"],
                         "2025-11-20T13:30Z")
        self.assertEqual(sources["USCPI20251024"]["available_at_utc"],
                         "2025-10-24T12:30Z")
        self.assertNotIn("USNFP20251003", sources)
        self.assertNotIn("USCPI20251113", sources)

    def test_evidence_only_is_offline_without_price_files(self):
        output = io.StringIO()
        with patch.object(ai, "response_json",
                          side_effect=AssertionError("No API expected")):
            with contextlib.redirect_stdout(output):
                exit_code = annual.main(["--evidence-only",
                                         "--prices-dir", str(self.root)])
        self.assertEqual(exit_code, 0)
        info = json.loads(output.getvalue())
        self.assertEqual(info["expected_full_year_decisions"], 108)
        self.assertEqual(info["runtime_go_no_go"], "NO_GO")

    def test_evidence_cannot_include_future_or_unsafe_domain(self):
        source = json.loads(annual.EVIDENCE.read_text(encoding="utf-8"))
        bad = self.root / "altered.json"
        source["events"][0]["available_at_utc"] = "2026-01-03T12:00:00Z"
        bad.write_text(json.dumps(source), encoding="utf-8")
        with self.assertRaises(InputError):
            annual.check_corpus(bad)
        source["events"][0]["available_at_utc"] = "2025-01-10T13:30:00Z"
        source["events"][0]["source_url"] = "https://unsafe.example/gossip"
        bad.write_text(json.dumps(source), encoding="utf-8")
        with self.assertRaises(InputError):
            annual.check_corpus(bad)

    def test_no_api_flag_price_preflight_only(self):
        out = io.StringIO()
        with patch.object(annual, "check_year_prices",
                          return_value={"verified_months": list(range(1, 13))}):
            with patch.object(ai, "response_json",
                              side_effect=AssertionError("No paid API")):
                with contextlib.redirect_stdout(out):
                    exit_code = annual.main([])
        self.assertEqual(exit_code, 0)
        self.assertIn("2025_PRICE_PREFLIGHT_NO_GO", out.getvalue())

    def test_missing_price_year_fails_closed(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = annual.main(["--prices-dir", str(self.root)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["runtime_go_no_go"],
                         "NO_GO")

    def test_full_year_price_preflight_months_and_gaps(self):
        # Mock hist.prepare only: actual CSV loader has extensive existing tests.
        bars = []
        t = datetime(2025, 1, 2, tzinfo=timezone.utc)
        while t < datetime(2025, 12, 29, tzinfo=timezone.utc):
            for pair in PAIRS:
                bars.append(Bar(t, pair, D("100"), D("101"),
                                D("99"), D("100"), D("1"), D("1"),
                                "HOLD"))
            t += timedelta(days=3)
        with patch.object(annual.hist, "prepare",
                          return_value=(bars, pricing())):
            info = annual.check_year_prices(self.root)
        self.assertEqual(info["verified_months"], list(range(1, 13)))
        with patch.object(annual.hist, "prepare",
                          return_value=(bars[:24], pricing())):
            with self.assertRaises(InputError):
                annual.check_year_prices(self.root)

    def test_rolling_evidence_window_includes_late_year(self):
        events, _ = annual.check_corpus(annual.EVIDENCE)
        calls = []
        def fake(model, instruction, context, *, key):
            if model == "analyst":
                calls.append(context)
                return {"action": "HOLD", "hypothesis": "Insufficient",
                        "counterevidence": "No consensus"}
            return {"verdict": "APPROVED", "rationale": "Hold is safe"}
        journal = ai.generate(
            events, analyst_model="analyst", reviewer_model="reviewer",
            max_decisions=108, decision_limit=120,
            api_key="SYNTHETIC", inference=fake)
        self.assertEqual(len(journal["decisions"]), 108)
        self.assertEqual(len(calls), 108)
        self.assertTrue(any(
            row["id"] == "EUECB20251218"
            for row in calls[-1]["evidence"]))
        self.assertLessEqual(len(calls[-1]["evidence"]), 30)
        self.assertTrue(all(
            replay.validate_decision(d, events)[2] == "HOLD"
            for d in journal["decisions"]))
        self.assertTrue(all(d["pair"] in PAIRS for d in journal["decisions"]))

    def test_yearly_budget_cannot_silently_exceed_opt_in(self):
        out = io.StringIO()
        with patch.object(annual, "check_year_prices",
                          return_value={"verified_months": list(range(1, 13))}):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "FAKE_KEY"}):
                with patch.object(ai, "generate",
                                  side_effect=AssertionError("Paid API called")):
                    with contextlib.redirect_stdout(out):
                        code = annual.main(["--allow-external-api",
                                            "--max-decisions", "108"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["status"],
                         "FAIL_CLOSED")

    def test_period_evaluation_separate_sma_and_immutable_inputs(self):
        source, _ = annual.check_corpus(annual.EVIDENCE)
        d = {
            "id": "YTEST001", "asof_utc": "2025-09-05T13:00:00Z",
            "pair": "USD/JPY",
            "evidence_ids": sorted(k for k, v in source.items()
                                   if v["available_at_utc"] <=
                                   "2025-09-05T13:00:00Z")[-30:],
            "evidence_sha256": "",
            "analyst": {"model": "a", "action": "HOLD",
                        "hypothesis": "Test hypothesis",
                        "counterevidence": "No market consensus"},
            "reviewer": {"model": "b", "verdict": "APPROVED",
                         "rationale": "Hold allowed"},
        }
        d["evidence_sha256"] = replay.canonical_hash(
            [source[k] for k in d["evidence_ids"]])
        journal_path = self.root / "decisions.json"
        journal_path.write_text(json.dumps(
            {"schema": "fx_macro_decisions_v1", "decisions": [d]}),
            encoding="utf-8")
        # Patch bar alignment because synthetic bars do not have this H1 close:
        # create a matching time for the decision, with three pairs.
        bars = synthetic_bars()
        matched = datetime(2025, 9, 5, 12, tzinfo=timezone.utc)
        for pair in PAIRS:
            bars.append(Bar(matched, pair, D("100"), D("101"),
                            D("99"), D("100"), D("1"), D("1"),
                            "LONG"))
        bars.sort(key=lambda b: (b.time, PAIRS.index(b.pair)))
        with patch.object(annual.hist, "prepare",
                          return_value=(bars, pricing())):
            outcome = annual.evaluate_periods(annual.EVIDENCE,
                                              journal_path, self.root)
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")
        self.assertFalse(outcome["held_out_window_is_prospective"])
        self.assertEqual(set(outcome["calendar_2025"]),
                         {"full_year", "development_jan_sep",
                          "held_out_oct_dec"})
        self.assertEqual(outcome["calendar_2025"]["full_year"]["trade_count"], 0)
        self.assertEqual(outcome["sma10_30_separate_control"]["strategy"],
                         "SMA_CROSSOVER_ONLY_NOT_AI")


if __name__ == "__main__":
    unittest.main()
