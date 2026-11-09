"""FX-AI-ARCH-003: deterministic 25-event comparison, audit and paid-call ledger."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import ai_provider_annual_audit as annual
from research import ai_provider_comparison as gateway
from research.offline_backtest import InputError


class AnnualProviderAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = (Path(__file__).parent.parent / "research" /
                        "datasets" / "official_2025_macro_evidence_seed.json")
        cls.events = annual.ordered_events(cls.evidence)

    def fake_call(self, registry=None, count=75, fail_at=None):
        # Exactly same frozen event per provider; deliberate reanalysis mismatch.
        seen = []
        def responses(model, instruction, packet, *, key):
            seen.append(("responses", packet["source_id"]))
            if fail_at and len(seen) == fail_at:
                raise InputError("simulated ambiguous request failure")
            return {"priority": "HIGH", "reanalysis": "NO"}
        def http(url, payload, key):
            provider = "jev" if url == gateway.TYPESAFE_SYSTEMONE else "decisions"
            seen.append((provider, url))
            if fail_at and len(seen) == fail_at:
                raise InputError("simulated ambiguous request failure")
            label = "YES" if provider == "decisions" else "NO"
            if provider == "jev":
                return {"answers": {
                    "priority": {"type": "choice", "choice": "HIGH",
                                 "confidence": 0.8},
                    "reanalysis": {"type": "choice", "choice": label,
                                   "confidence": 0.7}}}
            return {"answers": [
                {"type": "choice", "name": "priority", "choice": "HIGH",
                 "confidence": 0.8},
                {"type": "choice", "name": "reanalysis", "choice": label,
                 "confidence": 0.7},
            ]}
        return seen, responses, http

    def test_full_25_event_comparison_and_disagreement_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.json"
            journal = annual.new_journal(self.events)
            annual._atomic_json(path, journal)
            seen, responses, http = self.fake_call()
            result = annual.run(
                self.events, path, selected_budget=75,
                credentials={"OPENAI_API_KEY": "fake",
                             "TYPESAFE_API_KEY": "fake"},
                responses_call=responses, http_call=http)
            self.assertEqual(len(seen), 75)
            self.assertEqual(result["request_attempts_started"], 75)
            report = annual.audit(result, self.events)
            self.assertEqual(report["source_events"], 25)
            self.assertEqual(report["completed_event_groups"], 25)
            self.assertEqual(report["completed_api_decisions"], 75)
            self.assertEqual(report["disagreement_event_groups"], 25)
            self.assertEqual(report["unanimous_event_groups"], 0)
            self.assertEqual(report["disagreement_type_counts"],
                             {"REANALYSIS_DIFFERENCE": 25})
            self.assertEqual(len(report["event_level_triage"]), 25)
            self.assertFalse(report["causation_identified"])
            self.assertIsNone(report["estimated_total_api_cost_jpy"])
            self.assertTrue(all(
                item["verified_causal_explanation"] is None
                and item["human_review_required"]
                for item in report["disagreement_details"]))
            self.assertEqual(report["runtime_go_no_go"], "NO_GO")
            self.assertFalse(report["real_orders_permitted"])

    def test_seed_first_event_avoids_three_paid_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "original.json"
            seen, responses, http = self.fake_call()
            journal = annual.new_journal(self.events)
            annual._atomic_json(original, journal)
            completed = annual.run(self.events, original,
                                   selected_budget=3,
                                   credentials={
                                       "OPENAI_API_KEY": "fake",
                                       "TYPESAFE_API_KEY": "fake"},
                                   responses_call=responses, http_call=http)
            seed = Path(folder) / "seed.json"
            seed.write_text(json.dumps({
                "providers": list(annual.PROVIDERS),
                "event_count": 1, "actual_api_requests": 3,
                "runtime_go_no_go": "NO_GO",
                "real_orders_permitted": False,
                "research_decisions": completed["completed"]},
                ensure_ascii=False), encoding="utf-8")
            imported = annual._seed_rows(seed, self.events)
            resumed_path = Path(folder) / "resumed.json"
            annual._atomic_json(
                resumed_path, annual.new_journal(self.events, imported))
            seen2, responses2, http2 = self.fake_call()
            after = annual.run(
                self.events, resumed_path, selected_budget=72,
                credentials={"OPENAI_API_KEY": "fake",
                             "TYPESAFE_API_KEY": "fake"},
                responses_call=responses2, http_call=http2)
            self.assertEqual(len(seen2), 72)
            self.assertEqual(len(after["completed"]), 75)
            self.assertEqual(after["seed_imported_requests"], 3)
            self.assertEqual(after["request_attempts_started"], 72)

    def test_pending_request_blocks_retry_after_ambiguous_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.json"
            annual._atomic_json(path, annual.new_journal(self.events))
            seen, responses, http = self.fake_call(fail_at=2)
            with self.assertRaises(InputError):
                annual.run(
                    self.events, path, selected_budget=3,
                    credentials={"OPENAI_API_KEY": "fake",
                                 "TYPESAFE_API_KEY": "fake"},
                    responses_call=responses, http_call=http)
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(stored["completed"]), 1)
            self.assertEqual(stored["request_attempts_started"], 2)
            self.assertEqual(stored["pending_request"]["provider"], "jev")
            with self.assertRaisesRegex(InputError, "AMBIGUOUS_PAID_CALL"):
                annual.run(
                    self.events, path, selected_budget=1,
                    credentials={"OPENAI_API_KEY": "fake",
                                 "TYPESAFE_API_KEY": "fake"},
                    responses_call=responses, http_call=http)
            self.assertEqual(len(seen), 2)

    def test_offline_init_and_report_never_calls_network(self):
        with tempfile.TemporaryDirectory() as folder:
            journal_path = Path(folder) / "journal.json"
            report_path = Path(folder) / "report.json"
            with patch.object(gateway.ProviderRegistry, "evaluate",
                              side_effect=AssertionError("network prohibited")):
                sink = io.StringIO()
                with contextlib.redirect_stdout(sink):
                    code = annual.main([
                        "--evidence", str(self.evidence),
                        "--journal", str(journal_path),
                        "--report", str(report_path)])
            self.assertEqual(code, 0)
            self.assertTrue(journal_path.exists())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["completed_event_groups"], 0)
            self.assertEqual(report["source_events"], 25)
            self.assertFalse(report["real_orders_permitted"])
            self.assertIn("PARTIAL_NO_GO", sink.getvalue())
            self.assertEqual(
                annual.main(["--evidence", str(self.evidence),
                             "--journal", str(journal_path)]), 2)

    def test_offline_audit_of_existing_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.json"
            annual._atomic_json(path, annual.new_journal(self.events))
            report = Path(folder) / "audit.json"
            code = annual.main([
                "--evidence", str(self.evidence),
                "--journal", str(path), "--audit-only",
                "--report", str(report)])
            self.assertEqual(code, 0)
            self.assertTrue(report.is_file())

    def test_invalid_fingerprint_or_tampered_choices_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.json"
            data = annual.new_journal(self.events)
            data["event_fingerprint_sha256"] = "injected"
            with self.assertRaises(InputError):
                annual.validate_journal(data, self.events)
            ok = annual.new_journal(self.events)
            ok["completed"].append({
                "event_id": self.events[0]["id"],
                "provider": "responses",
                "contract": gateway.QUESTION_VERSION, "pair": "USD/JPY",
                "result": {"priority": "BUY", "reanalysis": "NO",
                           "priority_confidence": None,
                           "reanalysis_confidence": None}})
            with self.assertRaises(InputError):
                annual.validate_journal(ok, self.events)

    def test_explicit_budget_and_credentials_before_billed_call(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.json"
            annual._atomic_json(path, annual.new_journal(self.events))
            with self.assertRaises(InputError):
                annual.run(self.events, path,
                           selected_budget=76, credentials={})
            with self.assertRaises(InputError):
                annual.run(self.events, path,
                           selected_budget=75, credentials={})
            self.assertIsNone(json.loads(
                path.read_text(encoding="utf-8"))["pending_request"])
            with patch.dict("os.environ", {"OPENAI_API_KEY": "fake",
                                           "TYPESAFE_API_KEY": "fake"}):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = annual.main([
                        "--evidence", str(self.evidence),
                        "--journal", str(path), "--resume",
                        "--max-api-calls", "0", "--allow-external-api"])
                self.assertEqual(code, 2)
                self.assertIn("FAIL_CLOSED", buf.getvalue())

    def test_partial_report_does_not_fake_full_sample_size(self):
        j = annual.new_journal(self.events)
        result = annual.audit(j, self.events)
        self.assertEqual(result["completed_api_decisions"], 0)
        self.assertEqual(result["completed_event_groups"], 0)
        self.assertEqual(result["disagreement_details"], [])
        self.assertFalse(result["human_labeled_quality_verified"])


if __name__ == "__main__":
    unittest.main()
