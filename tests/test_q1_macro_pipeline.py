"""Acceptance tests: genuine archived official releases + offline preflight only.

Synthetic market prices in tests, never calls a paid model or broker.
"""
from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research import q1_macro_pipeline as pipeline
from research import macro_ai_backtest as macro
from research.offline_backtest import InputError, timestamp


def fake_h1(pair: str, side: str) -> str:
    import datetime as dt
    base = {"usdjpy": 155.0, "eurjpy": 160.0, "eurusd": 1.04}[pair]
    tick = 0.01 if pair.endswith("jpy") else 0.0001
    text = io.StringIO()
    writer = csv.writer(text, lineterminator="\n")
    writer.writerow(("timestamp", "open", "high", "low", "close"))
    for idx in range(110):
        t = int((dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
                 + dt.timedelta(hours=idx)).timestamp() * 1000)
        v = base + tick * (idx / 3 + (1 if side == "ask" else 0))
        writer.writerow((t, f"{v:.6f}", f"{v+3*tick:.6f}",
                         f"{v-3*tick:.6f}", f"{v:.6f}"))
    return text.getvalue()


class OfficialDatasetTests(unittest.TestCase):
    def test_official_release_archive_ten_real_dates(self):
        events, meta = macro.evidence_file(pipeline.DEFAULT_EVIDENCE)
        self.assertEqual(meta["evidence_event_count"], 10)
        self.assertEqual(set(events), {
            "USNFP20250110", "USCPI20250115", "USFOMC20250129",
            "USNFP20250207", "USCPI20250212", "USNFP20250307",
            "USCPI20250312", "USFOMC20250319",
            "JPBOJ20250124", "JPBOJ20250319"})
        for key, event in events.items():
            with self.subTest(key=key):
                self.assertTrue(event["source_url"].startswith(
                    ("https://www.bls.gov/", "https://www.federalreserve.gov/",
                     "https://www.boj.or.jp/")))
                self.assertIsInstance(event["market_expectation"], str)
                self.assertGreaterEqual(timestamp(event["available_at_utc"]),
                                        timestamp(event["published_at_utc"]))
                self.assertLess(timestamp(event["available_at_utc"]),
                                datetime(2025, 4, 1, tzinfo=timezone.utc))

    def test_consensus_sources_disclose_missing_snapshot_authentication(self):
        path = (pipeline.DEFAULT_EVIDENCE.parent /
                "official_2025q1_consensus_provenance.json")
        sidecar = json.loads(path.read_text(encoding="utf-8"))
        events, _ = macro.evidence_file(pipeline.DEFAULT_EVIDENCE)
        self.assertEqual(sidecar["schema"], "fx_macro_consensus_provenance_v1")
        records = sidecar["records"]
        self.assertEqual(len(records), 6)
        self.assertEqual({r["id"] for r in records},
                         {k for k, v in events.items() if v["market_expectation"]})
        self.assertTrue(all(r["forecast_source_url"].startswith("https://")
                            and r["verified_asof_snapshot"] is False
                            for r in records))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.price_dir = self.root / "data"
        self.price_dir.mkdir()
        for sym in ("usdjpy", "eurjpy", "eurusd"):
            for side in ("bid", "ask"):
                name = f"{sym}-h1-{side}-2025-01-01-2025-04-01.csv"
                (self.price_dir / name).write_text(
                    fake_h1(sym, side), encoding="utf-8")

    def test_preflight_has_no_ai_and_no_real_orders(self):
        sources, info = pipeline.preflight(
            self.price_dir, pipeline.DEFAULT_EVIDENCE)
        self.assertEqual(len(sources), 10)
        self.assertFalse(info["ai_api_called"])
        self.assertFalse(info["ai_backtest_executed"])
        self.assertEqual(info["runtime_go_no_go"], "NO_GO")
        self.assertTrue(info["safety_hold_latched"])
        self.assertEqual(info["market_consensus_values_missing"], 4)
        self.assertEqual(len(info["input_price_checksums"]), 6)
        self.assertGreater(info["priced_bars"], 80)

    def test_invalid_or_missing_market_prices_preflight_fails(self):
        p = next(iter(pipeline.prices(self.price_dir).values()))[0]
        p.unlink()
        with self.assertRaises(InputError):
            pipeline.preflight(self.price_dir, pipeline.DEFAULT_EVIDENCE)

    def test_no_external_api_flag_never_creates_artifact(self):
        import contextlib
        import io as iomod
        out = iomod.StringIO()
        decisions = self.root / "decisions.json"
        report = self.root / "report.json"
        with contextlib.redirect_stdout(out):
            status = pipeline.main([
                "--prices-dir", str(self.price_dir),
                "--decisions-out", str(decisions),
                "--report-out", str(report)])
        self.assertEqual(status, 0)
        self.assertIn("PRECHECK_RESEARCH_ONLY_NO_GO", out.getvalue())
        self.assertFalse(decisions.exists())
        self.assertFalse(report.exists())

    def test_external_api_explicit_flag_without_key_fails_closed(self):
        import contextlib
        import io as iomod
        import os
        from unittest.mock import patch
        out = iomod.StringIO()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with contextlib.redirect_stdout(out):
                status = pipeline.main([
                    "--prices-dir", str(self.price_dir),
                    "--decisions-out", str(self.root / "decisions.json"),
                    "--report-out", str(self.root / "report.json"),
                    "--analyst-model", "a", "--reviewer-model", "b",
                    "--allow-external-api"])
        self.assertEqual(status, 2)
        self.assertIn("FAIL_CLOSED", out.getvalue())
        self.assertFalse((self.root / "decisions.json").exists())
        self.assertFalse((self.root / "report.json").exists())


    def test_macro_api_http_category_does_not_echo_secrets(self):
        from research import macro_ai_generate as ai
        for code, expected in (
            (400, "HTTP_400_INVALID_REQUEST_OR_MODEL_OPTIONS"),
            (401, "HTTP_401_INVALID_API_KEY"),
            (403, "HTTP_403_PERMISSION_DENIED"),
            (404, "HTTP_404_MODEL_UNAVAILABLE_OR_NOT_FOUND"),
            (429, "HTTP_429_RATE_OR_QUOTA_LIMIT"),
            (503, "HTTP_5XX_PROVIDER_FAILURE"),
        ):
            with self.subTest(code=code):
                self.assertEqual(ai._http_failure(code), expected)

    def test_failed_external_ai_reports_stage_without_credential(self):
        import contextlib
        import io as iomod
        from unittest.mock import patch
        import os
        from research import macro_ai_generate as ai
        out = iomod.StringIO()
        secret = "DONT_EXPOSE_TEST_KEY"
        with patch.dict(os.environ, {"OPENAI_API_KEY": secret}):
            with patch.object(ai, "generate",
                              side_effect=ai.MacroAPIError("HTTP_429_RATE_OR_QUOTA_LIMIT")):
                with contextlib.redirect_stdout(out):
                    status = pipeline.main([
                        "--prices-dir", str(self.price_dir),
                        "--decisions-out", str(self.root / "decisions.json"),
                        "--report-out", str(self.root / "report.json"),
                        "--analyst-model", "model-a",
                        "--reviewer-model", "model-b",
                        "--allow-external-api"])
        parsed = json.loads(out.getvalue())
        self.assertEqual(status, 2)
        self.assertEqual(parsed["failure_stage"], "AI_GENERATION")
        self.assertEqual(parsed["failure_reason"],
                         "HTTP_429_RATE_OR_QUOTA_LIMIT")
        self.assertEqual(parsed["runtime_go_no_go"], "NO_GO")
        self.assertNotIn(secret, out.getvalue())
        self.assertFalse((self.root / "decisions.json").exists())


if __name__ == "__main__":
    unittest.main()
