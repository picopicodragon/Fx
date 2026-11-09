"""2025 annual macro research: synthetic historical bid/ask and mocked API only."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research import annual_macro_pipeline as annual
from research import macro_ai_backtest as replay
from research import macro_ai_generate as ai
from research.offline_backtest import InputError, PAIRS


class AnnualEvidenceTests(unittest.TestCase):
    def test_seed_uses_same_q1_events_and_extends_all_four_quarters(self):
        events, _ = replay.evidence_file(annual.DATASET)
        self.assertEqual(len(events), 23)
        self.assertEqual(set(PAIRS), {"USD/JPY", "EUR/JPY", "EUR/USD"})
        old, _ = replay.evidence_file(
            Path(__file__).parent.parent / "research" / "datasets" /
            "official_2025q1_macro_evidence.json")
        for key, value in old.items():
            self.assertEqual(events[key], value)
        q = {int(v["available_at_utc"][5:7]) // 3
             for v in events.values()}
        self.assertGreaterEqual(len(q), 4)
        self.assertTrue(all(v["market_expectation"] == "" for k, v
                            in events.items() if k not in old))
        self.assertIn("USGDP20250430", events)
        self.assertIn("USFOMC20251210", events)
        self.assertNotIn("USNFP20251003", events)

    def test_api_generator_can_cover_more_than_q1_thirty_decisions(self):
        sources, _ = replay.evidence_file(annual.DATASET)
        def mock_inference(model, instruction, data, *, key):
            if model == "fake-analyst":
                return {"action": "HOLD", "hypothesis": "Missing consensus",
                        "counterevidence": "Insufficient timed evidence"}
            return {"verdict": "APPROVED", "rationale": "Cautious HOLD"}
        result = ai.generate(sources, analyst_model="fake-analyst",
                             reviewer_model="fake-reviewer",
                             api_key="TEST_ONLY", max_decisions=69,
                             inference=mock_inference)
        self.assertEqual(len(result["decisions"]), 69)
        self.assertEqual(result["decisions"][-1]["pair"], "EUR/USD")
        self.assertEqual(result["decisions"][-1]["asof_utc"],
                         "2025-12-10T19:00:00Z")
        for row in result["decisions"]:
            replay.validate_decision(row, sources)
        self.assertEqual({v["analyst"]["action"] for v in
                          result["decisions"]}, {"HOLD"})

    def test_inference_limit_rejects_unbounded_calls_before_any_api(self):
        sources, _ = replay.evidence_file(annual.DATASET)
        calls = []
        def mock_inference(model, instruction, data, *, key):
            calls.append(1)
            raise RuntimeError("should not execute")
        with self.assertRaises(InputError):
            ai.generate(sources, analyst_model="a", reviewer_model="b",
                        max_decisions=121, api_key="TEST_ONLY",
                        inference=mock_inference)
        self.assertEqual(calls, [])


class AnnualPriceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.price_dir = cls.root / "h1"
        cls.price_dir.mkdir()
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        stop = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = []
        moment = start
        while moment < stop:
            rows.append(str(int(moment.timestamp() * 1000)))
            moment += timedelta(hours=1)
        for symbol, midpoint in (("usdjpy", 150), ("eurjpy", 160),
                                 ("eurusd", 1.08)):
            for side in ("bid", "ask"):
                val = midpoint + (0.02 if side == "ask" else 0)
                price = f"{val:.5f}"
                lines = ["timestamp,open,high,low,close"]
                lines.extend(f"{ts},{price},{val+0.04:.5f},"
                             f"{val-0.04:.5f},{price}" for ts in rows)
                path = cls.price_dir / (
                    f"{symbol}-h1-{side}-2025-01-01-2026-01-01.csv")
                path.write_text("\\n".join(lines) + "\\n",
                                encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_annual_preflight_has_full_year_data_and_no_api(self):
        evidence, report = annual.preflight(self.price_dir, annual.DATASET)
        self.assertEqual(len(evidence), 23)
        self.assertEqual(report["possible_decisions"], 69)
        self.assertEqual(report["estimated_full_inference_api_calls"], 138)
        self.assertEqual(report["missing_consensus_event_count"], 17)
        self.assertGreater(report["aligned_bars_per_pair"], 5500)
        self.assertEqual(report["runtime_go_no_go"], "NO_GO")
        self.assertEqual(report["paid_api_calls"], 0)

    def test_annual_default_cli_is_offline_and_no_files_written(self):
        buf = io.StringIO()
        with patch.object(ai, "response_json",
                          side_effect=AssertionError("no API calls")):
            with contextlib.redirect_stdout(buf):
                result = annual.main(["--prices-dir", str(self.price_dir),
                                      "--report-out",
                                      str(self.root / "never_report.json")])
        self.assertEqual(result, 0)
        self.assertIn("ANNUAL_PRECHECK_RESEARCH_ONLY_NO_GO", buf.getvalue())
        self.assertFalse((self.root / "never_report.json").exists())

    def test_billable_calls_refused_without_hard_budget(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "TEST_ONLY"}):
            with patch.object(ai, "generate",
                              side_effect=AssertionError("must not call")):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    result = annual.main([
                        "--prices-dir", str(self.price_dir),
                        "--analyst-model", "test-analyst",
                        "--reviewer-model", "test-reviewer",
                        "--max-decisions", "69",
                        "--max-api-calls", "137",
                        "--journal-out", str(self.root / "unwritten.json"),
                        "--report-out", str(self.root / "unwritten_report.json"),
                        "--allow-external-api"])
        self.assertEqual(result, 2)
        self.assertIn("FAIL_CLOSED", buf.getvalue())
        self.assertFalse((self.root / "unwritten.json").exists())

    def test_quarter_summary_exact_reconciliation(self):
        journal = {"decisions": [
            {"asof_utc": "2025-02-12T14:00:00Z",
             "reviewer": {"verdict": "APPROVED"},
             "analyst": {"action": "LONG"}},
            {"asof_utc": "2025-11-09T15:00:00Z",
             "reviewer": {"verdict": "APPROVED"},
             "analyst": {"action": "HOLD"}},
        ]}
        result = {"net_pnl_jpy": "-75.5", "trades": [
            {"exit_time_utc": "2025-03-01T18:00:00+00:00",
             "pnl_jpy": "-100.5"},
            {"exit_time_utc": "2025-10-29T19:00:00+00:00",
             "pnl_jpy": "25"},
        ]}
        quarters = annual.quarter_summary(result, journal)
        self.assertEqual(quarters["2025Q1"]["decision_count"], 1)
        self.assertEqual(quarters["2025Q4"]["decision_count"], 1)
        self.assertEqual(quarters["2025Q1"]["realized_pnl_jpy"], "-100.5")
        self.assertEqual(quarters["2025Q4"]["realized_pnl_jpy"], "25")
        self.assertEqual(quarters["2025Q4"]["approved_nonhold"], 0)
        with self.assertRaises(InputError):
            annual.quarter_summary(
                {"net_pnl_jpy": "12", "trades": result["trades"]}, journal)

    def test_report_on_saved_journal_does_not_call_paid_api(self):
        sources, _ = replay.evidence_file(annual.DATASET)
        def mock_inference(model, instruction, data, *, key):
            if model == "a":
                return {"action": "HOLD", "hypothesis": "No action",
                        "counterevidence": "No market confirmation"}
            return {"verdict": "APPROVED", "rationale": "Approve HOLD"}
        # Use one valid event and three pairs so replay has exact H1 cutoffs.
        journal = ai.generate(sources, analyst_model="a", reviewer_model="b",
                              max_decisions=3, api_key="TEST",
                              inference=mock_inference)
        journal_path = self.root / "replay_only_decisions.json"
        report_path = self.root / "replay_only_report.json"
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        with patch.object(ai, "generate",
                          side_effect=AssertionError("must not infer")):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                status = annual.main([
                    "--prices-dir", str(self.price_dir),
                    "--decisions", str(journal_path),
                    "--report-out", str(report_path)])
        self.assertEqual(status, 0, buf.getvalue())
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["trade_count"], 0)
        self.assertEqual(saved["runtime_go_no_go"], "NO_GO")
        self.assertEqual(saved["annual_macro_research"]
                         ["quarterly_realized_exit_attribution"]
                         ["2025Q1"]["decision_count"], 3)

    def test_absent_or_q1_only_history_not_mistaken_for_year(self):
        empty = self.root / "missing_prices"
        empty.mkdir(exist_ok=True)
        with self.assertRaises(InputError):
            annual.preflight(empty, annual.DATASET)


if __name__ == "__main__":
    unittest.main()
