"""Synthetic-only point-in-time macro evidence and model replay tests."""
from __future__ import annotations

import copy
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from research import macro_ai_backtest as macro
from research import macro_ai_generate as generator
from research.offline_backtest import InputError
def make_csv(pair, side, *, count=55):
    base = {"usdjpy": 150.0, "eurjpy": 160.0, "eurusd": 1.08}[pair]
    tick = 0.01 if pair.endswith("jpy") else 0.0001
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\\n")
    writer.writerow(["timestamp", "open", "high", "low", "close"])
    for i in range(count):
        drift = (i if i < 30 else 60 - i) * tick * 2
        value = base + drift + (tick if side == "ask" else 0)
        writer.writerow([1735689600000 + i * 3600000,
                         format(value, ".6f"),
                         format(value + 3 * tick, ".6f"),
                         format(value - 3 * tick, ".6f"),
                         format(value, ".6f")])
    return stream.getvalue()



def event(event_id="E001", available="2025-01-02T10:00:00Z"):
    return {
        "id": event_id, "source_url": "https://example.org/release",
        "source_type": "economic_release",
        "published_at_utc": "2025-01-02T09:00:00Z",
        "available_at_utc": available,
        "text": "FICTIONAL test economic indicator: actual 1.2 vs forecast 1.0.",
        "market_expectation": "1.0", "observed_result": "1.2",
    }


def decision(sources, asof="2025-01-02T12:00:00Z",
             verdict="APPROVED", action="LONG", pair="USD/JPY"):
    return {
        "id": "D001", "asof_utc": asof, "pair": pair,
        "evidence_ids": sorted(sources),
        "evidence_sha256": macro.canonical_hash(
            [sources[k] for k in sorted(sources)]),
        "analyst": {"model": "mock-analyst-a", "action": action,
                    "hypothesis": "Fictional surprise suggests currency support.",
                    "counterevidence": "Already priced in, could reverse."},
        "reviewer": {"model": "mock-reviewer-b", "verdict": verdict,
                     "rationale": "Synthetic review of fictitious evidence."},
    }


class MacroReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.evidence = self.root / "evidence.json"
        self.journal = self.root / "decisions.json"
        self.evidence.write_text(json.dumps(
            {"schema": "fx_macro_evidence_v1", "events": [event()]}),
            encoding="utf-8")
        self.sources = {"E001": event()}
        self.journal.write_text(json.dumps({
            "schema": "fx_macro_decisions_v1",
            "decisions": [decision(self.sources)],
        }), encoding="utf-8")
        self.files = {}
        for symbol in ("usdjpy", "eurjpy", "eurusd"):
            paths = []
            for side in ("bid", "ask"):
                path = self.root / (symbol + "-" + side + ".csv")
                path.write_text(make_csv(symbol, side, count=55),
                                encoding="utf-8")
                paths.append(path)
            self.files[symbol] = tuple(paths)

    def test_positive_macro_replay_is_not_sma(self):
        report = macro.run(self.files, self.evidence, self.journal)
        self.assertEqual(report["status"], "RESEARCH_ONLY_NO_GO")
        self.assertTrue(report["safety_hold_latched"])
        self.assertFalse(report["real_order_execution_authorized"])
        self.assertEqual(report["historical_research"]["strategy"],
                         "POINT_IN_TIME_TEXT_AI_DUAL_REVIEW_REPLAY")
        self.assertEqual(report["macro_ai_research"]["decision_count"], 1)
        self.assertEqual(report["macro_ai_research"]["approved_nonhold_count"], 1)
        self.assertEqual(report["macro_ai_research"]["review_verdict_counts"]
                         ["APPROVED"], 1)
        self.assertEqual(report["trade_count"], 1)

    def test_rejected_ai_never_falls_back_to_sma(self):
        row = decision(self.sources, verdict="REJECTED")
        self.journal.write_text(json.dumps({
            "schema": "fx_macro_decisions_v1", "decisions": [row],
        }), encoding="utf-8")
        report = macro.run(self.files, self.evidence, self.journal)
        self.assertEqual(report["trade_count"], 0)
        self.assertEqual(report["macro_ai_research"]["approved_nonhold_count"], 0)

    def test_future_source_blocked_even_if_ai_approves(self):
        row = decision(self.sources, asof="2025-01-02T08:00:00Z")
        with self.assertRaises(InputError):
            macro.validate_decision(row, self.sources)

    def test_self_declared_availability_cannot_precede_publication(self):
        bad = event(available="2025-01-02T08:00:00Z")
        self.evidence.write_text(json.dumps({
            "schema": "fx_macro_evidence_v1", "events": [bad]
        }), encoding="utf-8")
        with self.assertRaises(InputError):
            macro.evidence_file(self.evidence)

    def test_changed_evidence_or_wrong_hash_rejected(self):
        row = decision(self.sources)
        altered = copy.deepcopy(self.sources)
        altered["E001"]["text"] += " revised after decision"
        with self.assertRaises(InputError):
            macro.validate_decision(row, altered)

    def test_same_model_name_is_not_independent(self):
        row = decision(self.sources)
        row["reviewer"]["model"] = row["analyst"]["model"]
        with self.assertRaises(InputError):
            macro.validate_decision(row, self.sources)

    def test_pending_revision_or_rejected_must_be_hold(self):
        for verdict in ("PENDING", "REVISION", "REJECTED"):
            with self.subTest(verdict=verdict):
                row = decision(self.sources, verdict=verdict)
                self.assertEqual(macro.validate_decision(row, self.sources)[2],
                                 "HOLD")

    def test_duplicate_pair_asof_rejected(self):
        raw = decision(self.sources)
        raw2 = copy.deepcopy(raw)
        raw2["id"] = "D002"
        self.journal.write_text(json.dumps({
            "schema": "fx_macro_decisions_v1",
            "decisions": [raw, raw2]
        }), encoding="utf-8")
        with self.assertRaises(InputError):
            macro.decision_file(self.journal, self.sources)

    def test_decision_not_matching_historical_bar_rejected(self):
        row = decision(self.sources, asof="2025-05-02T12:00:00Z")
        self.journal.write_text(json.dumps({
            "schema": "fx_macro_decisions_v1", "decisions": [row]
        }), encoding="utf-8")
        with self.assertRaises(InputError):
            macro.run(self.files, self.evidence, self.journal)

    def test_untrusted_malformed_or_injected_fields_rejected(self):
        for addition in ({"override": "ALLOW_TRADING"},
                         {"future_news": "tomorrow's NFP"}):
            row = decision(self.sources)
            row.update(addition)
            with self.subTest(addition=addition), self.assertRaises(InputError):
                macro.validate_decision(row, self.sources)

    def test_empty_event_manifest_or_journal_refused(self):
        self.evidence.write_text(json.dumps({
            "schema": "fx_macro_evidence_v1", "events": []}), encoding="utf-8")
        with self.assertRaises(InputError):
            macro.evidence_file(self.evidence)
        self.journal.write_text(json.dumps({
            "schema": "fx_macro_decisions_v1", "decisions": []}), encoding="utf-8")
        with self.assertRaises(InputError):
            macro.decision_file(self.journal, self.sources)

    def test_replay_deterministic(self):
        a = macro.run(self.files, self.evidence, self.journal)
        self.assertEqual(a, macro.run(self.files, self.evidence, self.journal))

    def test_explicit_flag_required_without_api_calls(self):
        from contextlib import redirect_stdout
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = generator.main([
                "--evidence", str(self.evidence),
                "--out", str(self.root / "result.json"),
                "--analyst-model", "a",
                "--reviewer-model", "b"])
        self.assertEqual(exit_code, 2)
        self.assertIn("FAIL_CLOSED", output.getvalue())
        self.assertFalse((self.root / "result.json").exists())

    def test_generator_fake_inference_produces_dual_ai_records(self):
        calls = []
        def fake(model, instruction, data, *, key):
            calls.append((model, data))
            if model == "mock-analyst-a":
                return {"action": "LONG",
                        "hypothesis": "Fictional macro story",
                        "counterevidence": "Could be priced in"}
            return {"verdict": "APPROVED", "rationale": "Fictional check"}
        generated = generator.generate(
            self.sources, analyst_model="mock-analyst-a",
            reviewer_model="mock-reviewer-b", max_decisions=1,
            api_key="FAKE_TEST_ONLY", inference=fake)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "mock-analyst-a")
        self.assertEqual(calls[1][0], "mock-reviewer-b")
        self.assertEqual(generated["decisions"][0]["pair"], "USD/JPY")
        self.assertEqual(generated["decisions"][0]["asof_utc"],
                         "2025-01-02T10:00:00Z")
        self.assertEqual(macro.validate_decision(generated["decisions"][0],
                                                  self.sources)[2], "LONG")

    def test_generator_batches_multiple_sources_same_hour(self):
        other = event("E002", available="2025-01-02T10:10:00Z")
        grouped = {"E001": event(), "E002": other}
        def fake(model, instruction, data, *, key):
            if model == "mock-analyst-a":
                return {"action": "HOLD", "hypothesis": "No sufficient data",
                        "counterevidence": "Evidence uncertain"}
            return {"verdict": "PENDING", "rationale": "Insufficient"}
        result = generator.generate(
            grouped, analyst_model="mock-analyst-a",
            reviewer_model="mock-reviewer-b", max_decisions=6,
            api_key="FAKE_TEST_ONLY", inference=fake)
        self.assertEqual(len(result["decisions"]), 3)
        self.assertEqual(len(result["decisions"][0]["evidence_ids"]), 2)
        self.assertEqual(len(set((d["pair"], d["asof_utc"])
                                 for d in result["decisions"])), 3)

    def test_generator_rejects_same_model_or_no_key(self):
        for kwargs in (
                {"analyst_model": "a", "reviewer_model": "a",
                 "max_decisions": 1, "api_key": "FAKE"},
                {"analyst_model": "a", "reviewer_model": "b",
                 "max_decisions": 1, "api_key": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(InputError):
                generator.generate(self.sources, **kwargs)


if __name__ == "__main__":
    unittest.main()
