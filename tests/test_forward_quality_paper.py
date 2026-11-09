"""FWD-02 to FWD-05 offline deterministic forward quality and paper tests."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import forward_observation as obs
from research import forward_quality as quality
from research import forward_paper as paper
from research.offline_backtest import InputError

START = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)


def iso(d):
    return d.isoformat(timespec="seconds").replace("+00:00", "Z")


class ForwardQualityAndPaperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "forward"
        obs.initialize(self.store, "forward_quality_mock", now=START)

    @staticmethod
    def quote(*, bid="150.000", ask="150.010", pair="USD/JPY"):
        return {"pair": pair, "bid": bid, "ask": ask,
                "quote_to_jpy": "1",
                "source_status": "USER_SUPPLIED_UNVERIFIED"}

    @staticmethod
    def event():
        return {"pair": "USD/JPY", "title": "Fake rate report",
                "source_url": "https://example.invalid/fixture",
                "published_at_utc": iso(START),
                "content": "Synthetic test only",
                "consensus": "", "released_value": "0.5",
                "source_status": "USER_SUPPLIED_UNVERIFIED"}

    @staticmethod
    def scenario():
        return {
            "schema": paper.SCHEMA, "hypothetical_only": True,
            "starting_jpy": "100000", "stop_pips": "20",
            "reward_multiple": "1.5", "max_simulated_positions": 1,
            "commission_jpy": "0",
        }

    def add(self, kind, data, seconds=0, name="fixture"):
        at = START + timedelta(seconds=seconds)
        s = {"schema": obs.SCHEMA, "kind": kind,
             "observed_at_utc": iso(at),
             "source_id": "fixture_feed",
             "payload": data}
        file = self.root / (name + ".json")
        file.write_text(json.dumps(s), encoding="utf-8")
        return obs.ingest(self.store, file, now=at)

    def test_quality_empty_stale_and_missing_consensus(self):
        empty = quality.quality_report(self.store, asof_utc=iso(START))
        self.assertFalse(empty[
            "current_asof_quote_freshness"]["USD/JPY"]["quote_fresh"])
        self.add("MACRO_EVENT", self.event())
        self.add("PRICE_QUOTE", self.quote(), seconds=1)
        result = quality.quality_report(
            self.store, asof_utc=iso(START + timedelta(seconds=5)))
        self.assertEqual(result["macro_events_missing_consensus"], 1)
        self.assertTrue(result[
            "current_asof_quote_freshness"]["USD/JPY"]["quote_fresh"])
        self.assertTrue(result[
            "current_asof_quote_freshness"]["USD/JPY"][
                "event_blackout_observed"])
        self.assertFalse(result["full_economic_calendar_coverage_verified"])
        late = quality.quality_report(
            self.store, asof_utc=iso(START + timedelta(minutes=10)))
        self.assertFalse(late[
            "current_asof_quote_freshness"]["USD/JPY"]["quote_fresh"])
        self.assertFalse(late["source_authenticity_verified"])
        self.assertEqual(late["runtime_go_no_go"], "NO_GO")

    def test_reviewed_paper_single_position_target(self):
        e = self.add("MACRO_EVENT", self.event())
        h = self.add("MACRO_HYPOTHESIS", {
            "pair": "USD/JPY", "direction": "LONG",
            "thesis": "Synthetic thesis",
            "counterevidence": "Synthetic counterexample",
            "model_id": "analyst-model",
            "basis_sha256": e["record_sha256"], "research_only": True,
        }, seconds=1, name="hyp")
        self.add("INDEPENDENT_REVIEW", {
            "pair": "USD/JPY", "review_of_sha256": h["record_sha256"],
            "verdict": "APPROVED",
            "rationale": "Approved for the test of a paper simulator only",
            "model_id": "other-model", "research_only": True,
        }, seconds=2, name="review")
        self.add("PRICE_QUOTE", self.quote(), seconds=3, name="q1")
        self.add("PRICE_QUOTE",
                 self.quote(bid="150.320", ask="150.330"),
                 seconds=4, name="q2")
        result = paper.replay(
            self.store, self.scenario(),
            asof_utc=iso(START + timedelta(seconds=4)))
        position = result["hypothetical_position"]
        self.assertIsNotNone(position)
        self.assertEqual(position["exit_reason"], "HYPOTHETICAL_TARGET")
        self.assertLessEqual(
            float(position["initial_risk_jpy"]), 500)
        self.assertEqual(position["simulated_units"], 2000)
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["daily_and_drawdown_risk_engine_certified"])

    def test_reviewed_paper_stop_and_hold(self):
        e = self.add("MACRO_EVENT", self.event())
        h = self.add("MACRO_HYPOTHESIS", {
            "pair": "USD/JPY", "direction": "SHORT",
            "thesis": "Synthetic thesis",
            "counterevidence": "Synthetic counterexample",
            "model_id": "analyst",
            "basis_sha256": e["record_sha256"], "research_only": True,
        }, seconds=1, name="h")
        self.add("INDEPENDENT_REVIEW", {
            "pair": "USD/JPY", "review_of_sha256": h["record_sha256"],
            "verdict": "APPROVED", "rationale": "Paper only",
            "model_id": "reviewer", "research_only": True,
        }, seconds=2, name="r")
        self.add("PRICE_QUOTE", self.quote(),
                 seconds=3, name="q1")
        self.add("PRICE_QUOTE", self.quote(bid="150.300", ask="150.310"),
                 seconds=4, name="q2")
        result = paper.replay(self.store, self.scenario(),
                              asof_utc=iso(START + timedelta(seconds=4)))
        self.assertEqual(result["hypothetical_position"]["exit_reason"],
                         "HYPOTHETICAL_STOP")
        self.assertLess(float(result["hypothetical_pnl_jpy"]), 0)

    def test_no_approved_review_means_no_position(self):
        self.add("PRICE_QUOTE", self.quote(), name="q0")
        self.add("PRICE_QUOTE", self.quote(), seconds=1, name="q1")
        result = paper.replay(self.store, self.scenario(),
                              asof_utc=iso(START + timedelta(seconds=1)))
        self.assertIsNone(result["hypothetical_position"])
        self.assertEqual(result["hypothetical_pnl_jpy"], "0.0000")

    def test_hypothesis_model_must_differ_from_reviewer(self):
        e = self.add("MACRO_EVENT", self.event())
        h = self.add("MACRO_HYPOTHESIS", {
            "pair": "USD/JPY", "direction": "LONG",
            "thesis": "Research", "counterevidence": "Data",
            "model_id": "same", "basis_sha256": e["record_sha256"],
            "research_only": True,
        }, seconds=1, name="h")
        self.add("INDEPENDENT_REVIEW", {
            "pair": "USD/JPY", "review_of_sha256": h["record_sha256"],
            "verdict": "APPROVED", "rationale": "not independent",
            "model_id": "same", "research_only": True,
        }, seconds=2, name="r")
        with self.assertRaises(InputError):
            paper.replay(self.store, self.scenario(),
                         asof_utc=iso(START + timedelta(seconds=3)))

    def test_scenario_rejects_unbounded_authorization(self):
        for mutation in (
                {"hypothetical_only": False},
                {"starting_jpy": "200000"},
                {"max_simulated_positions": 2},
                {"stop_pips": "0"},
                {"commission_jpy": "-1"},
                {"reward_multiple": "50"}):
            with self.subTest(mutation=mutation), self.assertRaises(InputError):
                paper.scenario_validate({**self.scenario(), **mutation})

    def test_offline_cli_quality_and_paper(self):
        scenario = self.root / "plan.json"
        scenario.write_text(json.dumps(self.scenario()), encoding="utf-8")
        qout = self.root / "quality.json"
        pout = self.root / "paper.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(quality.main([
                "--store", str(self.store),
                "--asof-utc", iso(START), "--out", str(qout)]), 0)
            self.assertEqual(paper.main([
                "--store", str(self.store), "--scenario", str(scenario),
                "--asof-utc", iso(START), "--out", str(pout)]), 0)
            self.assertEqual(paper.main([
                "--store", str(self.store), "--scenario", str(scenario),
                "--asof-utc", iso(START), "--out", str(pout)]), 2)
        result = json.loads(pout.read_text(encoding="utf-8"))
        self.assertIsNone(result["hypothetical_position"])
        self.assertFalse(result["mt4_connected"])


if __name__ == "__main__":
    unittest.main()
