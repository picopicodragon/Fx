"""DEMO-SPRINT: bounded, no-background forward decision cycle invariants."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_demo_cycle as cycle
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)
EVENT = "a" * 64


class FinalDemoCycleTests(unittest.TestCase):
    def test_empty_journal_does_not_call_ai_or_write_intent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ledgers=root/"ledgers"
            ledgers.mkdir()
            with patch.object(cycle.observation, "audit",
                              return_value={"runtime_go_no_go":"NO_GO",
                                            "safety_hold_latched":True,
                                            "record_count":0}):
                with patch.object(cycle.ai, "run") as paid:
                    result=cycle.run(root,ledgers,account=1234567,
                        analyst_model="analyst",reviewer_model="reviewer",now=NOW)
                    paid.assert_not_called()
            self.assertEqual(result["status"],
                             "DEMO_CYCLE_NO_RECENT_ELIGIBLE_MACRO_EVENT")
            self.assertFalse(result["demo_intent_written"])
            self.assertEqual(result["api_calls_this_run"],0)
            self.assertEqual(result["orders_sent_this_run"],0)

    def test_bad_account_or_implicit_billing_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for optin,count in ((False,2),(True,0),(True,3)):
                with self.subTest(optin=optin,count=count):
                    with self.assertRaises(InputError):
                        cycle.run(root,root,account=1234567,
                            analyst_model="one",reviewer_model="two",
                            max_api_calls=count,allow_external_api=optin,
                            now=NOW)
            with self.assertRaises(InputError):
                cycle.run(root,root,account=0,analyst_model="one",
                    reviewer_model="two",now=NOW)

    def test_ny17_boundary_is_dst_aware(self):
        before=datetime(2026,11,17,21,59,tzinfo=timezone.utc)
        after=datetime(2026,11,17,22,0,tzinfo=timezone.utc)
        self.assertEqual(cycle._ny17_key(before),"ny17_2026-11-16")
        self.assertEqual(cycle._ny17_key(after),"ny17_2026-11-17")
        # Summer NY17 is 21:00Z, winter is 22:00Z.
        summer=datetime(2026,7,1,21,0,tzinfo=timezone.utc)
        self.assertEqual(cycle._ny17_key(summer),"ny17_2026-07-01")

    def test_recent_event_without_api_optin_remains_no_signal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ledgers=root/"ledgers"
            ledgers.mkdir()
            record={
                "record_sha256":EVENT,
                "snapshot":{
                    "kind":"MACRO_EVENT",
                    "source_id":"fed_policy",
                    "observed_at_utc":(NOW-timedelta(minutes=1))
                        .isoformat().replace("+00:00","Z"),
                    "payload":{"published_at_utc":(NOW-timedelta(minutes=2))
                        .isoformat().replace("+00:00","Z")},
                },
            }
            (root/"00000001.json").write_text(json.dumps(record))
            with patch.object(cycle.observation,"audit",
                    return_value={"runtime_go_no_go":"NO_GO",
                                  "safety_hold_latched":True,"record_count":1}):
                with patch.object(cycle.ai,"run") as paid:
                    result=cycle.run(root,ledgers,account=1234567,
                        analyst_model="one",reviewer_model="two",now=NOW)
                    paid.assert_not_called()
            self.assertEqual(result["status"],"DEMO_CYCLE_AI_NOT_OPTED_IN_HOLD")
            self.assertEqual(list(ledgers.rglob("*.json")),[])
            self.assertFalse((ledgers/cycle._ny17_key(NOW)/".demo_cycle.lock").exists())

    def test_unverified_journal_safety_gate_cannot_advance(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch.object(cycle.observation,"audit",
                return_value={"runtime_go_no_go":"GO",
                              "safety_hold_latched":False,"record_count":0}):
                with self.assertRaises(InputError):
                    cycle.run(root,root,account=1234567,
                        analyst_model="one",reviewer_model="two",now=NOW)


if __name__ == "__main__":
    unittest.main()
