"""Blocked live paper entries cannot inspect old saved AI or spend calls."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime

NOW=datetime(2026,11,20,3,0,tzinfo=timezone.utc)
EPOCH=int(NOW.timestamp())


def quote(epoch):
    return {
        "capture_epoch":epoch,
        "source_sha256":"a"*64,
        "quotes":{
            pair: {
                "bid":paper.D("159.5"),
                "ask":paper.D("159.505"),
                "tickvalue":paper.D("100"),
                "ticksize":paper.D(".001"),
                "minlot":paper.D(".01"),
                "maxlot":paper.D("20"),
                "step":paper.D(".01"),
                "point":paper.D(".001"),
            } for pair in paper.PAIRS
        },
    }


class QuoteOnlyBlockedPolicy(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)/"paper"
        runtime._initialize(self.root)

    def run_once(self, *, communication=False, previous_gap=60,
                 future_attestation=False, blackout=False):
        prior=paper.initial_state()
        prior["cycle_number"]=1
        prior["last_quote_epoch"]=EPOCH-previous_gap
        prior["communication_latched"]=communication
        runtime._journal_append(self.root/"journal",prior,
                                "0"*64,"a"*64,NOW)
        archived=self.root/"captured_real_h1"
        archived.mkdir()
        verified={
            "active_known_blackout":blackout,
            "independent_calendar_coverage_attested":future_attestation,
            "pc_clock_independently_attested":future_attestation,
            "calendar_supplied":future_attestation,
        }
        with patch.object(runtime, "_latest_quote",return_value=quote(EPOCH)), \
             patch.object(runtime, "_latest_h1_copy",
                          return_value=archived), \
             patch.object(runtime.blackout,"check",
                          return_value=verified), \
             patch.object(runtime,"_signals_for_new_h1") as signals, \
             patch.object(runtime.ai,"run") as paid, \
             patch.object(runtime.completed_decision,"load_completed") as saved:
            outcome=runtime.run_one_cycle(
                Path(self.t.name),self.root,[self.root/"archived_official"],
                allow_paid=True,analyst_model="test-analyst",
                reviewer_model="test-reviewer",paid_limit=6,now=NOW)
            signals.assert_not_called()
            paid.assert_not_called()
            saved.assert_not_called()
        state,_=runtime._journal_load(self.root/"journal")
        self.assertEqual(state["cycle_number"],2)
        self.assertEqual(state["positions"],[])
        self.assertEqual(state["pending_signals"],[])
        self.assertEqual(state["paid_inference_calls"],0)
        self.assertTrue(outcome["ai_signal_pipeline_skipped_by_unattested_safety_hold"])
        self.assertEqual(outcome["paid_calls_this_cycle"],0)
        self.assertEqual(outcome["broker_orders_sent_this_run"],0)
        return state,outcome

    def test_communication_latched_quote_continues_but_ai_is_never_read(self):
        self.run_once(communication=True)

    def test_unverified_calendar_alone_prevents_ai_signal_replay(self):
        self.run_once()

    def test_600s_gap_never_runs_paid_or_saved_ai_even_with_mocked_attestation(self):
        state,report=self.run_once(previous_gap=720,
                                   future_attestation=True)
        self.assertTrue(state["communication_latched"])
        self.assertFalse(report["entry_readiness_gate_open"])

    def test_known_event_blackout_prevents_ai_signal_replay(self):
        self.run_once(future_attestation=True,blackout=True)


if __name__=="__main__":
    unittest.main()
