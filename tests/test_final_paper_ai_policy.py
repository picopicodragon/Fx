"""Final-paper phase policy: Jev is NOT used; bounded independent AI."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_runtime as runtime
from research import final_paper_engine as paper


class FinalPaperProviderPolicyTests(unittest.TestCase):
    def test_user_phase_choice_is_machine_readable(self):
        base=Path(__file__).resolve().parents[1]
        p=json.loads((base/"specs"/"ai_provider_phase_policy_20261118.json").read_text())
        self.assertFalse(p["final_paper_test"]["jev_enabled"])
        self.assertFalse(p["completed_system"]["jev_enabled"])
        self.assertEqual(p["final_paper_test"]["order_execution"],
                         "NO_BROKER_ORDERS")
        self.assertEqual(p["final_paper_test"]["portfolio_execution"],
                         "LOCAL_VIRTUAL_POSITIONS_ONLY")
        self.assertFalse(p["completed_system"]["live_order_authorized"])

    def test_not_opted_in_marks_new_h1_without_any_model_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            runtime._initialize(root)
            state=paper.initial_state()
            seen_h1={"captures":{
                sym:{"candles":[{"server_epoch":123456}]} for sym in paper.SYMS}}
            with patch.object(runtime.period,"_read_h1",return_value=seen_h1), \
                 patch.object(runtime.ai,"run") as inference:
                sig,seen,n=runtime._signals_for_new_h1(
                    state,root/"captures",[],root,
                    datetime.now(timezone.utc),
                    allow_paid=False,analyst_model="",
                    reviewer_model="",max_paid_calls=0)
                inference.assert_not_called()
            self.assertEqual(sig,[])
            self.assertEqual(len(seen),3)
            self.assertEqual(n,0)

    def test_six_paid_calls_cap_three_pairs_and_no_jev(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            runtime._initialize(root)
            state=paper.initial_state()
            stub={"captures":{
                sym:{"candles":[{"server_epoch":123456}]} for sym in paper.SYMS}}
            packet={
                "macro_coverage_complete_research_only":True,
                "technical":{"atr14":0.15}}
            ai_result={
                "stage":"COMPLETE","paid_calls_this_run":2,
                "packet_sha256_local_only":"b"*64,
                "model_action_research_only":"HOLD",
                "model_verdict":"APPROVED"}
            with patch.object(runtime.period,"_read_h1",return_value=stub), \
                 patch.object(runtime.period,"run",return_value=packet), \
                 patch.object(runtime.ai,"run",return_value=ai_result) as inference, \
                 patch.object(runtime.review401,"check_directory") as safety:
                sig,seen,n=runtime._signals_for_new_h1(
                    state,root/"captures",[root/"dummy_bundle"],root,
                    datetime.now(timezone.utc),
                    allow_paid=True,analyst_model="gpt-6.1-sol",
                    reviewer_model="gpt-6-astra",
                    max_paid_calls=6)
                self.assertEqual(inference.call_count,3)
                self.assertEqual(safety.call_count,3)
            self.assertEqual(n,6)
            self.assertEqual(len(sig),3)
            self.assertEqual(len(seen),3)
            self.assertTrue(all(s["action"]=="HOLD" for s in sig))
            state["paid_inference_calls"]=6
            with patch.object(runtime.period,"_read_h1",return_value=stub), \
                 patch.object(runtime.ai,"run") as inference:
                sig,seen,n=runtime._signals_for_new_h1(
                    state,root/"captures",[root/"dummy_bundle"],root,
                    datetime.now(timezone.utc),
                    allow_paid=True,analyst_model="gpt-6.1-sol",
                    reviewer_model="gpt-6-astra",
                    max_paid_calls=6)
                inference.assert_not_called()
            self.assertEqual(n,0)

    def test_jev_connector_not_in_final_runtime(self):
        base=Path(__file__).resolve().parents[1]
        source=(base/"research"/"final_paper_runtime.py").read_text()
        self.assertNotIn("TYPESAFE_API_KEY",source)
        self.assertNotIn("typesafe.ai",source)
        self.assertNotIn("OPENAI_DECISIONS",source)
        self.assertNotIn("OrderSend(",source)


if __name__=="__main__":
    unittest.main()
