"""One-use manual virtual communication-latch release safety regression."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research import final_paper_manual_comm_release as release
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)
BASE = int(NOW.timestamp())


def quote(epoch):
    return {
        "capture_epoch": epoch,
        "source_sha256": "a" * 64,
        "quotes": {
            pair: {
                "bid": paper.D("159.50") if pair == "USD/JPY"
                    else paper.D("175.20") if pair == "EUR/JPY"
                    else paper.D("1.1000"),
                "ask": paper.D("159.505") if pair == "USD/JPY"
                    else paper.D("175.21") if pair == "EUR/JPY"
                    else paper.D("1.10005"),
                "ticksize": paper.D(".001"),
                "tickvalue": paper.D("100"),
                "minlot": paper.D(".01"),
                "maxlot": paper.D("20"),
                "step": paper.D(".01"),
                "point": paper.D(".001"),
            } for pair in paper.PAIRS
        },
    }


def history(root, *, extra_gap=0):
    runtime._initialize(root)
    begin = BASE - 119 * 60 - 3360 - extra_gap
    state = paper.initial_state()
    head = "0" * 64
    for cycle in range(1, 121):
        epoch = (begin + (cycle - 1) * 60
                 + (3360 if cycle >= 107 else 0)
                 + (extra_gap if cycle >= 110 else 0))
        state, _ = paper.step(state, quote(epoch),
                              entry_evidence_ready=False)
        head = runtime._journal_append(
            root / "journal", state, head, "a" * 64,
            datetime.fromtimestamp(epoch, tz=timezone.utc))
    assert state["communication_latched"] is True
    assert state["cycle_number"] == 120
    assert state["last_quote_epoch"] == BASE
    return state, head


def review_result(state, head):
    return {
        "historical_event_id": release.EVENT,
        "recent_quote_continuity_and_risk_review_ok": True,
        "release_plan_may_be_reviewed_by_operator": True,
        "journal_cycles": state["cycle_number"],
        "journal_head_sha256_local_only": head,
    }


class ManualCommunicationReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "virtual"
        self.mt4 = Path(self.tmp.name) / "MQL4" / "Files"
        self.mt4.mkdir(parents=True)
        self.state, self.head = history(self.root)

    def _stage(self, approval=release.APPROVAL):
        with patch.object(release.reentry, "review",
                          return_value=review_result(self.state, self.head)), \
             patch.object(runtime, "_latest_quote",
                          return_value=quote(BASE)):
            return release.stage(
                self.root, self.mt4, now=NOW,
                operator_approval=approval)

    def test_requires_explicit_local_opt_in_and_no_lock(self):
        with self.assertRaises(InputError):
            self._stage("")
        self.assertFalse((self.root / release.NAME).exists())
        lock = self.root / ".single_operator.lock"
        lock.write_text("running")
        with self.assertRaises(InputError):
            self._stage()
        lock.unlink()
        self.assertEqual(runtime._journal_load(self.root / "journal")[1],
                         self.head)

    def test_one_shot_stage_and_replay_proof(self):
        report = self._stage()
        self.assertFalse(report["communication_latch_cleared"])
        self.assertFalse(report["new_paid_calls_permitted"])
        self.assertFalse(report["broker_orders_permitted"])
        with self.assertRaises(InputError):
            self._stage()
        self.assertTrue(runtime._journal_load(self.root / "journal")[0][
            "communication_latched"])

    def test_stale_or_altered_permit_fails_closed(self):
        self._stage()
        file = self.root / release.NAME
        record = json.loads(file.read_text("utf-8"))
        record["journal_cycles"] += 1
        file.write_text(json.dumps(record))
        with self.assertRaises(InputError):
            release.apply_if_valid(self.root, self.state, self.head,
                                   quote(BASE + 60),
                                   NOW + timedelta(seconds=60))
        record["journal_cycles"] -= 1
        record["permit_sha256"] = runtime._digest(
            {k: v for k, v in record.items() if k != "permit_sha256"})
        file.write_text(json.dumps(record))
        with self.assertRaises(InputError):
            release.apply_if_valid(self.root, self.state, self.head,
                                   quote(BASE + 360),
                                   NOW + timedelta(seconds=360))

    def test_another_unattested_long_gap_blocks_staging(self):
        other = Path(self.tmp.name) / "virtual2"
        state, head = history(other, extra_gap=660)
        with patch.object(release.reentry, "review",
                          return_value=review_result(state, head)), \
             patch.object(runtime, "_latest_quote",
                          return_value=quote(BASE)):
            with self.assertRaises(InputError):
                release.stage(other, self.mt4, now=NOW,
                              operator_approval=release.APPROVAL)
        self.assertFalse((other / release.NAME).exists())

    def test_runtime_consumes_exactly_once_on_new_quote_and_relatches(self):
        self._stage()
        self.assertTrue(self.state["communication_latched"])
        with patch.object(runtime, "_latest_quote",
                          return_value=quote(BASE + 60)), \
             patch.object(runtime, "_latest_h1_copy",
                          return_value=None):
            result = runtime.run_one_cycle(
                self.mt4, self.root, [], allow_paid=False,
                analyst_model="", reviewer_model="", paid_limit=0,
                now=NOW + timedelta(seconds=60))
        self.assertTrue(result["manual_comm_release_applied_this_cycle"])
        self.assertFalse(result["communication_latched"])
        self.assertEqual(result["broker_orders_sent_this_run"], 0)
        self.assertEqual(result["paid_calls_this_cycle"], 0)
        after, _ = runtime._journal_load(self.root / "journal")
        self.assertEqual(after["cycle_number"], 121)
        self.assertEqual(after["manual_comm_release_sha256"],
                         json.loads((self.root / release.NAME).read_text())[
                             "permit_sha256"])
        self.assertEqual(len(list((self.root / "journal").glob("*.json"))),
                         121)
        # Same historical approval never clears a later >600-second gap.
        with patch.object(runtime, "_latest_quote",
                          return_value=quote(BASE + 900)), \
             patch.object(runtime, "_latest_h1_copy",
                          return_value=None):
            again = runtime.run_one_cycle(
                self.mt4, self.root, [], allow_paid=False,
                analyst_model="", reviewer_model="", paid_limit=0,
                now=NOW + timedelta(seconds=900))
        self.assertFalse(again["manual_comm_release_applied_this_cycle"])
        self.assertTrue(again["communication_latched"])

    def test_missing_or_expired_quote_never_clears(self):
        self._stage()
        state, applied = release.apply_if_valid(
            self.root, self.state, self.head, quote(BASE), NOW)
        self.assertFalse(applied)
        self.assertTrue(state["communication_latched"])
        with self.assertRaises(InputError):
            release.apply_if_valid(
                self.root, self.state, self.head, quote(BASE + 190),
                NOW + timedelta(seconds=190))

    def test_no_broker_or_paid_ai_cap_changes_in_release_source(self):
        code = (Path(__file__).resolve().parents[1] / "research"
                / "final_paper_manual_comm_release.py").read_text("utf-8")
        for forbidden in (
            "OrderSend(", "OrderClose(", "OrderModify(", "WebRequest(",
            "OPENAI_API_KEY", "ai.run(", "MAX_PAID_LIFETIME = 8",
            "lock.unlink("):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main()
