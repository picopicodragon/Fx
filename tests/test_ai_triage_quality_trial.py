"""FX-AI-ARCH-004: offline matched quality rubric and paid-cap safeguards."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import ai_triage_quality_trial as trial
from research import ai_provider_comparison as gateway
from research.offline_backtest import InputError


class QualityTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.sha = trial.load_cases()
        cls.case_by_id = {x["id"]: x for x in cls.cases}

    @staticmethod
    def _answers(case, variant):
        if variant == "v1":
            return "HIGH", "YES"
        return case["reference_priority"], case["reference_reanalysis"]

    def mock_callbacks(self, fail_at=None):
        calls = []
        def call_responses(model, instruction, p, *, key):
            variant = "v2" if trial.V2_PRIORITY in instruction else "v1"
            case = self.case_by_id[p["source_id"]]
            calls.append(("responses", variant, case["id"]))
            if fail_at == len(calls):
                raise InputError("simulated ambiguous API failure")
            priority, reanalysis = self._answers(case, variant)
            return {"priority": priority, "reanalysis": reanalysis}
        def call_http(url, data, key):
            provider = ("jev" if url == gateway.TYPESAFE_SYSTEMONE
                        else "decisions")
            if provider == "jev":
                p = json.loads(data["state"])
                variant = ("v2" if trial.V2_PRIORITY ==
                           data["questions"]["priority"]["instructions"]
                           else "v1")
            else:
                p = json.loads(data["input"].split("\n", 1)[1])
                variant = ("v2" if trial.V2_PRIORITY ==
                           data["questions"][0]["instructions"] else "v1")
            case = self.case_by_id[p["source_id"]]
            calls.append((provider, variant, case["id"]))
            if fail_at == len(calls):
                raise InputError("simulated ambiguous API failure")
            priority, reanalysis = self._answers(case, variant)
            def choice(name, value):
                return {"type": "choice", "name": name, "choice": value,
                        "confidence": 0.8}
            if provider == "jev":
                return {"answers": {
                    "priority": choice("priority", priority),
                    "reanalysis": choice("reanalysis", reanalysis)}}
            return {"answers": [choice("priority", priority),
                                choice("reanalysis", reanalysis)]}
        return calls, call_responses, call_http

    def test_synthetic_class_balance_and_no_label_leakage(self):
        self.assertEqual(len(self.cases), 16)
        classes = {x["reference_priority"] for x in self.cases}
        self.assertEqual(classes, set(trial.TYPES))
        for case in self.cases:
            packet_text = gateway._packet_text(trial.packet(case))
            self.assertNotIn("reference_priority", packet_text)
            self.assertNotIn("reference_reanalysis", packet_text)
            self.assertTrue(case["source_url"].startswith(
                "https://example.invalid/synthetic/"))

    def test_full_paired_96_fake_calls_and_scoring(self):
        with tempfile.TemporaryDirectory() as directory:
            journal_path = Path(directory) / "quality.json"
            trial.annual._atomic_json(
                journal_path, trial.empty_journal(self.cases, self.sha))
            calls, responses, http = self.mock_callbacks()
            journal = None
            for _ in range(4):
                journal = trial.run(
                    self.cases, self.sha, journal_path,
                    max_api_calls=24,
                    credentials={
                        "OPENAI_API_KEY": "fake",
                        "TYPESAFE_API_KEY": "fake"},
                    responses_call=responses, http_call=http)
            self.assertEqual(len(calls), 96)
            self.assertEqual(len(journal["completed"]), 96)
            r = trial.quality_report(journal, self.cases, self.sha)
            self.assertEqual(r["completed_requests"], 96)
            self.assertIn("COMPLETE_NO_GO", r["status"])
            self.assertFalse(r["historical_model_quality_established"])
            self.assertEqual(r["ground_truth_status"],
                             "SYNTHETIC_RUBRIC_ONLY_NOT_HUMAN_VALIDATED")
            self.assertEqual(len(r["paired_prompt_changes"]), 48)
            self.assertEqual(len(r["case_level_discrepancies"]), 3*13)
            for name in trial.PROVIDERS:
                self.assertEqual(
                    r["variant_provider_metrics"]["v2/"+name][
                        "both_reference_matches"], 16)
                self.assertLess(
                    r["variant_provider_metrics"]["v1/"+name][
                        "both_reference_matches"], 16)
            self.assertFalse(r["real_orders_permitted"])

    def test_pending_failure_does_not_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            trial.annual._atomic_json(
                path, trial.empty_journal(self.cases, self.sha))
            calls, response, http = self.mock_callbacks(fail_at=2)
            with self.assertRaises(InputError):
                trial.run(self.cases, self.sha, path, max_api_calls=3,
                          credentials={"OPENAI_API_KEY": "fake",
                                       "TYPESAFE_API_KEY": "fake"},
                          responses_call=response, http_call=http)
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(persisted["completed"]), 1)
            self.assertEqual(persisted["requests_started"], 2)
            self.assertIsNotNone(persisted["pending_request"])
            with self.assertRaises(InputError):
                trial.run(self.cases, self.sha, path, max_api_calls=1,
                          credentials={"OPENAI_API_KEY": "fake",
                                       "TYPESAFE_API_KEY": "fake"},
                          responses_call=response, http_call=http)
            self.assertEqual(len(calls), 2)

    def test_offline_default_and_readonly_audit_no_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            report = Path(directory) / "report.json"
            with patch.object(gateway, "_safe_http",
                              side_effect=AssertionError("network forbidden")):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(trial.main([
                        "--journal", str(path), "--report", str(report)]), 0)
            self.assertTrue(path.exists())
            self.assertEqual(
                json.loads(report.read_text(encoding="utf-8"))[
                    "completed_requests"], 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(trial.main([
                    "--journal", str(path), "--audit-only"]), 0)
                self.assertEqual(trial.main([
                    "--journal", str(path)]), 2)

    def test_unsafe_limits_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            trial.annual._atomic_json(
                path, trial.empty_journal(self.cases, self.sha))
            calls, response, http = self.mock_callbacks()
            for count in (0, 25, 97):
                with self.subTest(count=count), self.assertRaises(InputError):
                    trial.run(self.cases, self.sha, path,
                              max_api_calls=count,
                              credentials={"OPENAI_API_KEY": "fake",
                                           "TYPESAFE_API_KEY": "fake"},
                              responses_call=response, http_call=http)
            with self.assertRaises(InputError):
                trial.run(self.cases, self.sha, path,
                          max_api_calls=1, credentials={},
                          responses_call=response, http_call=http)
            self.assertEqual(calls, [])

    def test_tamper_journal_and_fixture_hash_rejected(self):
        j = trial.empty_journal(self.cases, self.sha)
        j["fixture_sha256"] = "changed"
        with self.assertRaises(InputError):
            trial.verify(j, self.cases, self.sha)
        j = trial.empty_journal(self.cases, self.sha)
        j["pending_request"] = {"slot": 999, "case_id": "bad",
                                "variant": "v1", "provider": "jev"}
        with self.assertRaises(InputError):
            trial.verify(j, self.cases, self.sha)
        j = trial.empty_journal(self.cases, self.sha)
        j["requests_started"] = 2
        with self.assertRaises(InputError):
            trial.verify(j, self.cases, self.sha)

    def test_v2_payloads_share_question_version(self):
        case = self.cases[0]
        packet = trial.packet(case)
        d = trial.v2_decisions_payload(packet)
        j = trial.v2_jev_payload(packet)
        self.assertEqual(d["questions"][0]["instructions"], trial.V2_PRIORITY)
        self.assertEqual(j["questions"]["reanalysis"]["instructions"],
                         trial.V2_REANALYSIS)
        self.assertNotIn("reference_priority",
                         json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
