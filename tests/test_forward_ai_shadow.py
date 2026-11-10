"""FWD-004 opt-in AI shadow: offline injected inference, paid retry lock."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research import forward_observation as obs
from research import forward_ai_shadow as ai
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 9, 22, 0, 0, tzinfo=timezone.utc)


class ForwardAiShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "local_journal"
        self.ledger = self.root / "paid_shadow_ledger.json"
        obs.initialize(self.store, "ai_shadow_fixture", now=NOW)
        sample = {
            "schema": obs.SCHEMA, "kind": "MACRO_EVENT",
            "observed_at_utc": "2026-11-09T22:00:00Z",
            "source_id": "fixture",
            "payload": {
                "pair": "USD/JPY",
                "title": "Synthetic rate report",
                "source_url": "https://example.invalid/synthetic",
                "published_at_utc": "2026-11-09T21:59:00Z",
                "content": "No real market data",
                "consensus": "0bp", "released_value": "25bp",
                "source_status": "USER_SUPPLIED_UNVERIFIED",
            },
        }
        file = self.root / "event.json"
        file.write_text(json.dumps(sample), encoding="utf-8")
        self.event = obs.ingest(self.store, file, now=NOW)[
            "record_sha256"]
        self.called = []

    def inference(self, model, prompt, packet, *, key):
        self.called.append((model, key))
        if model == "analyst-fixture":
            return {
                "action": "HOLD",
                "hypothesis": "Synthetic finding",
                "counterevidence": "Synthetic contrary result",
            }
        return {
            "verdict": "PENDING",
            "rationale": "Unverified research data",
        }

    def run_trial(self, n, *, key="dummy"):
        return ai.run(
            self.store, self.event, self.ledger,
            analyst_model="analyst-fixture",
            reviewer_model="reviewer-fixture",
            max_api_calls=n, allow_external_api=n > 0,
            api_key=key, inference=self.inference)

    def test_paid_calls_explicit_staged_no_orders(self):
        initial = self.run_trial(0)
        self.assertEqual(initial["paid_calls_this_run"], 0)
        self.assertEqual(self.called, [])
        self.assertFalse(initial["real_orders_permitted"])
        mid = self.run_trial(1)
        self.assertEqual(mid["stage"], "REVIEW_PENDING")
        self.assertEqual(len(self.called), 1)
        final = self.run_trial(1)
        self.assertEqual(final["stage"], "COMPLETE")
        self.assertEqual(len(self.called), 2)
        none = self.run_trial(0)
        self.assertEqual(none["paid_calls_this_run"], 0)
        self.assertEqual(len(self.called), 2)

    def test_publication_requires_complete_ledger(self):
        self.run_trial(1)
        with self.assertRaises(InputError):
            ai.publish(
                self.store, self.event, self.ledger,
                analyst_model="analyst-fixture",
                reviewer_model="reviewer-fixture")
        self.run_trial(1)
        result = ai.publish(
            self.store, self.event, self.ledger,
            analyst_model="analyst-fixture",
            reviewer_model="reviewer-fixture")
        self.assertIn("NO_GO", result["status"])
        audit = obs.audit(self.store)
        self.assertEqual(audit["record_count"], 3)
        self.assertEqual(audit["by_kind"]["INDEPENDENT_REVIEW"], 1)
        with self.assertRaises(InputError):
            ai.publish(
                self.store, self.event, self.ledger,
                analyst_model="analyst-fixture",
                reviewer_model="reviewer-fixture")

    def test_ambiguous_paid_failure_latched_no_retry(self):
        self.run_trial(0)
        def ambiguous(*args, **kwargs):
            raise InputError("uncertain billable response")
        with self.assertRaises(InputError):
            ai.run(
                self.store, self.event, self.ledger,
                analyst_model="analyst-fixture",
                reviewer_model="reviewer-fixture",
                max_api_calls=1, allow_external_api=True,
                api_key="dummy", inference=ambiguous)
        ledger = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(ledger["pending_request"], "analyst")
        with self.assertRaises(InputError):
            self.run_trial(1)
        self.assertEqual(self.called, [])

    def test_unsafe_key_models_and_input_rejected(self):
        with self.assertRaises(InputError):
            self.run_trial(1, key="")
        with self.assertRaises(InputError):
            ai.run(self.store, self.event, self.ledger,
                   analyst_model="analyst-fixture",
                   reviewer_model="analyst-fixture",
                   max_api_calls=1, allow_external_api=True,
                   api_key="dummy", inference=self.inference)
        with self.assertRaises(InputError):
            ai.run(self.store, "f" * 64, self.ledger,
                   analyst_model="analyst-fixture",
                   reviewer_model="reviewer-fixture",
                   max_api_calls=0, allow_external_api=False,
                   api_key="", inference=self.inference)
        self.assertEqual(self.called, [])

    def test_ledger_model_fingerprint_tampering_rejected(self):
        self.run_trial(0)
        ledger = json.loads(self.ledger.read_text(encoding="utf-8"))
        ledger["analyst_model"] = "unapproved-other"
        self.ledger.write_text(json.dumps(ledger), encoding="utf-8")
        with self.assertRaises(InputError):
            self.run_trial(1)
        self.assertEqual(self.called, [])


if __name__ == "__main__":
    unittest.main()
