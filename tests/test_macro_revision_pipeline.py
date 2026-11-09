"""Synthetic offline tests for historical REVISION auditing and replay.

Never calls external API, never connects to broker.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import macro_revision_pipeline as revised
from research import macro_ai_backtest as replay
from research.offline_backtest import InputError, PAIRS
from test_macro_ai_backtest import make_csv, event, decision


class RevisionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.evidence_path = self.root / "evidence.json"
        self.sources = {"E001": event()}
        self.evidence_path.write_text(json.dumps({
            "schema": "fx_macro_evidence_v1", "events": list(self.sources.values())
        }), encoding="utf-8")
        self.initial = decision(self.sources, verdict="REVISION")
        self.baseline = {"schema": "fx_macro_decisions_v1",
                         "decisions": [self.initial]}
        self.files = {}
        for pair in ("usdjpy", "eurjpy", "eurusd"):
            paths = []
            for side in ("bid", "ask"):
                path = self.root / f"{pair}-{side}.csv"
                path.write_text(make_csv(pair, side), encoding="utf-8")
                paths.append(path)
            self.files[pair] = tuple(paths)

    def _fake(self, *, verdicts=("REVISION", "APPROVED"), action="LONG"):
        calls = []
        def inference(model, instruction, data, *, key):
            calls.append((model, data))
            if model == "mock-analyst-a":
                return {"action": action, "hypothesis": "Evidence-only update",
                        "counterevidence": "Prices may already reflect news"}
            step = (len(calls) // 2) - 1
            return {"verdict": verdicts[step],
                    "rationale": f"Reviewer explained revision {step+1}"}
        return inference, calls

    def _run(self, inference):
        return revised.revise(
            self.baseline, self.sources, api_key="FAKE",
            analyst_model="mock-analyst-a", reviewer_model="mock-reviewer-b",
            inference=inference)

    def test_three_formal_pairs_are_exactly_backtest_pairs(self):
        self.assertEqual(PAIRS, ("USD/JPY", "EUR/JPY", "EUR/USD"))

    def test_offline_audit_preserves_review_reasons(self):
        report = revised.initial_audit(self.baseline, self.sources)
        self.assertEqual(report["paid_api_calls"], 0)
        self.assertEqual(len(report["revision_cases"]), 1)
        self.assertEqual(report["revision_cases"][0]["initial"]["reviewer_rationale"],
                         self.initial["reviewer"]["rationale"])
        self.assertEqual(report["before"]["approved_nonhold"], 0)

    def test_max_two_retries_final_approved(self):
        fake, calls = self._fake()
        final, audit = self._run(fake)
        self.assertEqual(len(calls), 4)
        self.assertEqual(audit["paid_api_calls"], 4)
        self.assertEqual(audit["revision_cases"][0]["revisions_used"], 2)
        self.assertEqual(final["decisions"][0]["reviewer"]["verdict"], "APPROVED")
        self.assertEqual(audit["before"]["approved_nonhold"], 0)
        self.assertEqual(audit["after"]["approved_nonhold"], 1)
        self.assertEqual(self.baseline["decisions"][0]["reviewer"]["verdict"],
                         "REVISION")
        replay.validate_decision(final["decisions"][0], self.sources)

    def test_two_revisions_never_auto_approve(self):
        fake, calls = self._fake(verdicts=("REVISION", "REVISION"))
        final, report = self._run(fake)
        self.assertEqual(len(calls), 4)
        self.assertEqual(final["decisions"][0]["reviewer"]["verdict"], "REVISION")
        self.assertEqual(replay.validate_decision(final["decisions"][0],
                                                   self.sources)[2], "HOLD")
        self.assertEqual(report["after"]["approved_nonhold"], 0)

    def test_rejected_or_pending_stops_retry(self):
        for verdict in ("REJECTED", "PENDING"):
            with self.subTest(verdict=verdict):
                fake, calls = self._fake(verdicts=(verdict,))
                final, report = self._run(fake)
                self.assertEqual(len(calls), 2)
                self.assertEqual(report["paid_api_calls"], 2)
                self.assertEqual(replay.validate_decision(final["decisions"][0],
                                                           self.sources)[2], "HOLD")

    def test_approved_hold_remains_non_trading(self):
        fake, calls = self._fake(verdicts=("APPROVED",), action="HOLD")
        final, report = self._run(fake)
        self.assertEqual(len(calls), 2)
        self.assertEqual(report["after"]["approved_nonhold"], 0)
        self.assertEqual(replay.validate_decision(final["decisions"][0],
                                                   self.sources)[2], "HOLD")

    def test_both_models_distinct_and_original_same_models(self):
        fake, calls = self._fake()
        with self.assertRaises(InputError):
            revised.revise(self.baseline, self.sources, api_key="FAKE",
                           analyst_model="mock-analyst-a",
                           reviewer_model="mock-analyst-a", inference=fake)
        with self.assertRaises(InputError):
            revised.revise(self.baseline, self.sources, api_key="FAKE",
                           analyst_model="different-model",
                           reviewer_model="mock-reviewer-b", inference=fake)
        self.assertEqual(calls, [])

    def test_malformed_revision_fails_closed(self):
        def bad(model, instruction, data, *, key):
            return {"action": "LONG", "hypothesis": "a",
                    "counterevidence": "b", "execute_orders": True}
        with self.assertRaises(InputError):
            self._run(bad)

    def test_compare_uses_same_sources_and_no_sma_fallback(self):
        fake, _ = self._fake(verdicts=("APPROVED",))
        final, audit = self._run(fake)
        outcome = revised.compare(self.baseline, final, audit, self.sources,
                                  self.files, self.evidence_path)
        self.assertEqual(outcome["before"]["trade_count"], 0)
        self.assertEqual(outcome["after"]["trade_count"], 1)
        self.assertEqual(outcome["runtime_go_no_go"], "NO_GO")
        self.assertFalse(outcome["real_orders_permitted"])

    def test_compare_rejects_provenance_changes(self):
        fake, _ = self._fake(verdicts=("APPROVED",))
        final, audit = self._run(fake)
        final["decisions"][0]["asof_utc"] = "2025-01-03T12:00:00Z"
        audit["final_journal_sha256"] = replay.canonical_hash(final)
        with self.assertRaises(InputError):
            revised.compare(self.baseline, final, audit, self.sources,
                            self.files, self.evidence_path)

    def test_duplicate_decisions_fail_before_inference(self):
        duplicated = copy.deepcopy(self.initial)
        duplicated["id"] = "D002"
        self.baseline["decisions"].append(duplicated)
        fake, calls = self._fake()
        with self.assertRaises(InputError):
            self._run(fake)
        self.assertEqual(calls, [])

    def test_no_opt_in_performs_no_inference_or_broker_action(self):
        journal = self.root / "original.json"
        journal.write_text(json.dumps(self.baseline), encoding="utf-8")
        audit_out = self.root / "audit.json"
        import contextlib, io
        output = io.StringIO()
        with patch.object(revised.ai, "response_json",
                          side_effect=AssertionError("API should not be called")):
            with contextlib.redirect_stdout(output):
                exitcode = revised.main([
                    "--decisions", str(journal),
                    "--evidence", str(self.evidence_path),
                    "--audit-out", str(audit_out)])
        self.assertEqual(exitcode, 0)
        self.assertTrue(audit_out.exists())
        self.assertEqual(json.loads(audit_out.read_text())["paid_api_calls"], 0)
        self.assertIn("NO_GO", output.getvalue())


if __name__ == "__main__":
    unittest.main()
