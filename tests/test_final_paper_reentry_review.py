"""Operator manual-stop classification is not release authorization."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import final_paper_reentry_review as module
from research.offline_backtest import InputError

VERIFIED={
    "ready_for_manual_root_cause_review":True,
    "communication_latched":True,
    "virtual_open_positions":0,
    "pending_signals":0,
    "no_other_risk_latches":True,
    "journal_cycles":153,
    "journal_head_sha256_local_only":"a"*64,
}
ATTEST={
    "schema":"fx_final_paper_interruption_operator_attestation_v1",
    "event_id":"PAPER_20261118_CYCLE_106_TO_107",
    "classification":"OPERATOR_ATTESTED_INTENTIONAL_STOP",
    "operator_declared_stop_was_manual_and_regular":True,
    "applicable_to_other_future_stops":False,
    "observation_gap":{
        "previous_journal_cycle":106,
        "next_journal_cycle":107,
        "unobserved_seconds_pc_derived":3420,
    }
}


class FinalPaperReentryReviewTests(unittest.TestCase):
    def _evaluate(self,review=None,attest=None):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"manual_stop.json"
            path.write_text(json.dumps(attest if attest is not None
                                       else ATTEST),encoding="utf-8")
            with patch.object(module.recovery,"review",
                              return_value=review if review is not None else VERIFIED):
                return module.review(Path(temp),attestation=path)

    def test_known_approved_manual_stop_does_not_release_risk_latch(self):
        out=self._evaluate()
        self.assertEqual(out["historical_stop_classification"],
                         "OPERATOR_ATTESTED_INTENTIONAL_STOP")
        self.assertTrue(out["recent_quote_continuity_and_risk_review_ok"])
        self.assertTrue(out["release_plan_may_be_reviewed_by_operator"])
        self.assertFalse(out["explicit_release_approval_recorded"])
        self.assertFalse(out["communication_latch_cleared"])
        self.assertFalse(out["new_virtual_entries_permitted"])
        self.assertFalse(out["new_paid_ai_calls_permitted"])
        self.assertFalse(out["real_orders_permitted"])

    def test_no_continuity_or_other_risk_latch_blocks_plan(self):
        for state in [
            dict(VERIFIED,ready_for_manual_root_cause_review=False),
            dict(VERIFIED,communication_latched=False),
            dict(VERIFIED,virtual_open_positions=1),
            dict(VERIFIED,pending_signals=1),
            dict(VERIFIED,no_other_risk_latches=False),
        ]:
            with self.subTest(state=state):
                self.assertFalse(self._evaluate(review=state)[
                    "release_plan_may_be_reviewed_by_operator"])

    def test_different_stop_not_silently_attested(self):
        evidence=json.loads(json.dumps(ATTEST))
        evidence["observation_gap"]["next_journal_cycle"]=108
        with self.assertRaises(InputError):
            self._evaluate(attest=evidence)

    def test_no_network_order_or_mutation(self):
        s=(Path(__file__).resolve().parents[1]/
           "research"/"final_paper_reentry_review.py").read_text("utf-8")
        for forbidden in ("OrderSend(","OrderClose(", "urllib.request",
                          "OPENAI_API_KEY", "ai.run(", "_journal_append(",
                          "lock.unlink("):
            self.assertNotIn(forbidden,s)


if __name__=="__main__":
    unittest.main()
