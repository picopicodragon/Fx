"""FX-AI-ARCH-001 provider adapters: offline fixtures, never paid API."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import ai_provider_comparison as gateway
from research import macro_ai_backtest as macro
from research.offline_backtest import InputError


MOCK_DECISIONS = {
    "model": "gpt-6-luna",
    "answers": [
        {"type": "choice", "name": "priority", "choice": "HIGH",
         "confidence": 0.86,
         "probabilities": [
             {"value": "HIGH", "probability": 0.86},
             {"value": "MEDIUM", "probability": 0.1},
             {"value": "LOW", "probability": 0.03},
             {"value": "UNKNOWN", "probability": 0.01}]},
        {"type": "choice", "name": "reanalysis", "choice": "YES",
         "confidence": 0.79,
         "probabilities": [
             {"value": "YES", "probability": 0.79},
             {"value": "NO", "probability": 0.16},
             {"value": "UNKNOWN", "probability": 0.05}]},
    ],
}
MOCK_JEV = {
    "model": "jev-1.13.0", "answers": {
        "priority": {
            "type": "choice", "choice": "HIGH", "confidence": 0.86,
            "probabilities": {"HIGH": 0.86, "MEDIUM": 0.10,
                              "LOW": 0.03, "UNKNOWN": 0.01}},
        "reanalysis": {
            "type": "choice", "choice": "YES", "confidence": 0.79,
            "probabilities": {"YES": 0.79, "NO": 0.16, "UNKNOWN": 0.05}},
    },
}


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence_path = (
            Path(__file__).parent.parent / "research" / "datasets" /
            "official_2025_macro_evidence_seed.json")
        cls.sources, _ = macro.evidence_file(cls.evidence_path)

    def setUp(self):
        event = sorted(self.sources.values(),
                       key=lambda e: (e["available_at_utc"], e["id"]))[0]
        self.packet = gateway.evidence_packet(event, "USD/JPY")

    def test_payload_shapes_real_vendor_contracts(self):
        d = gateway.openai_decisions_payload(self.packet)
        j = gateway.jev_payload(self.packet)
        self.assertEqual(d["model"], "gpt-6-luna")
        self.assertEqual([q["name"] for q in d["questions"]],
                         ["priority", "reanalysis"])
        self.assertTrue(all(q["type"] == "choice" for q in d["questions"]))
        self.assertEqual(j["model"], "jev-1.13.0")
        self.assertEqual(j["questions"]["priority"]["type"], "choice")
        self.assertIn("UNKNOWN", j["questions"]["priority"]["criteria"])
        self.assertIn("asof_utc", j["state"])
        self.assertNotIn("api_key", j["state"])

    def test_three_providers_same_internal_contract_no_broker(self):
        called = []
        def fake_http(url, body, key):
            called.append((url, body, key))
            return copy.deepcopy(
                MOCK_JEV if url == gateway.TYPESAFE_SYSTEMONE
                else MOCK_DECISIONS)
        def fake_response(model, instruction, data, *, key):
            called.append(("responses", model, key))
            return {"priority": "HIGH", "reanalysis": "YES"}
        registry = gateway.ProviderRegistry()
        outcomes = [registry.evaluate(
            provider, self.packet,
            credentials={"OPENAI_API_KEY": "fake-o",
                         "TYPESAFE_API_KEY": "fake-j"},
            responses_call=fake_response, http_call=fake_http)
            for provider in gateway.PROVIDERS]
        self.assertEqual(len(called), 3)
        self.assertEqual([r["provider"] for r in outcomes],
                         list(gateway.PROVIDERS))
        self.assertEqual({r["result"]["priority"] for r in outcomes},
                         {"HIGH"})
        self.assertEqual({r["result"]["reanalysis"] for r in outcomes},
                         {"YES"})
        self.assertTrue(all(r["runtime_go_no_go"] == "NO_GO"
                            and not r["real_orders_permitted"]
                            for r in outcomes))
        self.assertIsNone(outcomes[0]["result"]["priority_confidence"])
        self.assertAlmostEqual(outcomes[1]["result"]["priority_confidence"],
                               0.86)

    def test_refusal_unknown_choice_or_missing_confidence_fail_closed(self):
        for bad in (
            {"answers": [{"type": "refusal", "name": "priority"},
                         MOCK_DECISIONS["answers"][1]]},
            {"answers": [{"type": "choice", "name": "priority",
                          "choice": "BUY", "confidence": 0.99},
                         MOCK_DECISIONS["answers"][1]]},
            {"answers": [MOCK_DECISIONS["answers"][0],
                         {"type": "choice", "name": "reanalysis",
                          "choice": "YES"}]},
            {"answers": []},
        ):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                gateway.normalize_decisions(bad)
        bad_jev = copy.deepcopy(MOCK_JEV)
        bad_jev["answers"]["priority"]["confidence"] = 1.5
        with self.assertRaises(InputError):
            gateway.normalize_jev(bad_jev)

    def test_no_implicit_fallback_after_http_failure(self):
        calls = []
        def broken_http(url, body, key):
            calls.append(url)
            raise gateway.ProviderError("NETWORK")
        with self.assertRaises(gateway.ProviderError):
            gateway.ProviderRegistry().evaluate(
                "jev", self.packet,
                credentials={"TYPESAFE_API_KEY": "fake"},
                http_call=broken_http)
        self.assertEqual(calls, [gateway.TYPESAFE_SYSTEMONE])

    def test_source_validation_and_provider_restriction_before_paid_call(self):
        r = gateway.ProviderRegistry()
        for provider in ("unknown", "decisions", "jev"):
            with self.subTest(provider=provider), self.assertRaises(InputError):
                r.evaluate(provider, self.packet, credentials={})
        mutated = {**self.packet, "pair": "GBP/USD"}
        with self.assertRaises(InputError):
            r.evaluate("decisions", mutated,
                       credentials={"OPENAI_API_KEY": "fake"})
        mutated = {**self.packet, "scope": "LIVE_TRADE"}
        with self.assertRaises(InputError):
            r.evaluate("decisions", mutated,
                       credentials={"OPENAI_API_KEY": "fake"})

    def test_compare_three_way_same_frozen_packets(self):
        seen = []
        def mock_http(url, body, key):
            seen.append(("typed", url))
            return copy.deepcopy(
                MOCK_DECISIONS if url == gateway.OPENAI_DECISIONS
                else MOCK_JEV)
        def mock_response(model, instruction, data, *, key):
            seen.append(("responses", data["source_id"]))
            return {"priority": "HIGH", "reanalysis": "YES"}
        result = gateway.compare(
            self.sources, selected=gateway.PROVIDERS, pair="EUR/USD",
            max_events=2, credentials={
                "OPENAI_API_KEY": "fake", "TYPESAFE_API_KEY": "fake"},
            http_call=mock_http, responses_call=mock_response)
        self.assertEqual(len(seen), 6)
        self.assertEqual(result["actual_api_requests"], 6)
        self.assertEqual(len(result["research_decisions"]), 6)
        for i in (0, 3):
            hashes = {x["evidence_sha256"]
                      for x in result["research_decisions"][i:i+3]}
            self.assertEqual(len(hashes), 1)
        self.assertFalse(result["human_labeled_quality_verified"])
        self.assertIsNone(result["estimated_usd_cost"])

    def test_default_cli_preflight_is_zero_api_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            b = io.StringIO()
            with patch.object(gateway, "_safe_http",
                              side_effect=AssertionError("no network")):
                with contextlib.redirect_stdout(b):
                    code = gateway.main([
                        "--evidence", str(self.evidence_path),
                        "--out", str(path),
                        "--providers", "responses", "jev", "decisions",
                        "--pair", "USD/JPY", "--max-events", "2"])
            self.assertEqual(code, 0)
            self.assertFalse(path.exists())
            self.assertIn('"planned_requests": 6', b.getvalue())

    def test_explicit_opt_in_budget_blocks_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "report.json"
            buf = io.StringIO()
            with patch.dict("os.environ", {"OPENAI_API_KEY": "fake",
                                           "TYPESAFE_API_KEY": "fake"}):
                with patch.object(gateway, "_safe_http",
                                  side_effect=AssertionError("no network")):
                    with contextlib.redirect_stdout(buf):
                        result = gateway.main([
                            "--evidence", str(self.evidence_path),
                            "--out", str(path), "--providers",
                            "responses", "jev", "decisions",
                            "--pair", "USD/JPY", "--max-events", "2",
                            "--max-api-calls", "5",
                            "--allow-external-api"])
            self.assertEqual(result, 2)
            self.assertFalse(path.exists())
            self.assertIn("FAIL_CLOSED", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
