"""Executable contract tests for the demo-only final-test bridge.

Tests cannot replace a real MetaEditor compilation or Rakuten DEMO session.
"""
from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_demo_intent as demo
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)
EVENT = "a" * 64
ACCOUNT = 1234567


def event(age_minutes=3, source_id="macro_joined"):
    observation = NOW - timedelta(minutes=age_minutes)
    return {
        "source_id": source_id,
        "observed_at_utc": observation.isoformat().replace("+00:00", "Z"),
        "payload": {
            "pair": "EUR/USD",
            "title": "Official macro observation",
            "source_url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary2026.htm",
            "published_at_utc": (
                observation - timedelta(minutes=1)
            ).isoformat().replace("+00:00", "Z"),
            "consensus": "1.0",
            "released_value": "1.2",
            "content": (
                "[RESEARCH_ONLY_UNATTESTED_SOURCE_HASHES] "
                "original_macro_event=" + "b"*64 + " "
                "forecast_capture=" + "c"*64 + " "
                "release_excerpt=" + "d"*64
            ),
        }
    }


def state(side="LONG", verdict="APPROVED", pending=None, published=True):
    return {
        "analyst_model": "macro-analyst",
        "reviewer_model": "macro-reviewer",
        "stage": "COMPLETE",
        "pending_request": pending,
        "published_to_observation": published,
        "analyst": {"action": side},
        "reviewer": {"verdict": verdict},
    }


class TestFinalDemoIntent(unittest.TestCase):
    def configured(self, folder, candidate, *, record=None):
        path = folder / "ledger.json"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        stack = []
        import contextlib
        context = contextlib.ExitStack()
        context.enter_context(patch.object(
            demo.obs, "audit", return_value={
                "runtime_go_no_go": "NO_GO", "safety_hold_latched": True}))
        context.enter_context(patch.object(
            demo.ai, "_event", return_value=record or event()))
        context.enter_context(patch.object(demo.ai, "_base", return_value={}))
        context.enter_context(patch.object(demo.ai, "_valid", return_value=None))
        context.enter_context(patch.object(demo, "_approved_review_in_journal", return_value=True))
        return path, context

    def test_dry_run_and_atomic_files_bind_real_demo_account(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ledger, context=self.configured(root,state())
            with context:
                decision=demo.inspect(root,EVENT,ledger,account_number=ACCOUNT,now=NOW)
                self.assertEqual(decision["status"],
                                 "DEMO_INTENT_CANDIDATE_VALIDATED_NOT_EXECUTED")
                self.assertEqual(decision["symbol"],"EURUSD")
                self.assertEqual(decision["side"],"BUY")
                self.assertFalse(decision["real_orders_permitted"])
                self.assertEqual(decision["orders_sent_this_run"],0)
                dest=demo.write_demo_intent(root, decision,
                                            account_number=ACCOUNT)
                self.assertEqual(dest.name,"FxDemoIntent_v1.csv")
                fields=next(csv.reader(io.StringIO(dest.read_text("ascii"))))
                self.assertEqual(fields,[
                    "FXDEMO1",str(ACCOUNT),EVENT,str(int(NOW.timestamp())),
                    str(int(NOW.timestamp())+90),"EURUSD","BUY",EVENT
                ])
                self.assertEqual(len(list(root.iterdir())),2)

    def test_fresh_official_fed_policy_can_be_reviewed_for_demo_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ledger, context=self.configured(
                root,state(side="SHORT"),
                record=event(source_id="fed_policy"))
            with context:
                candidate=demo.inspect(root,EVENT,ledger,
                    account_number=ACCOUNT,now=NOW)
            self.assertEqual(candidate["side"],"SELL")
            self.assertFalse(candidate["source_authenticity_independently_attested"])
            self.assertEqual(candidate["orders_sent_this_run"],0)

    def test_stale_unreviewed_missing_consensus_pending_and_unpublished_rejected(self):
        candidates=[
            (state(side="HOLD"),event()),
            (state(verdict="REJECTED"),event()),
            (state(pending="analyst"),event()),
            (state(published=False),event()),
            (state(),event(age_minutes=300)),
            (state(),event(source_id="bls_cpi")),
        ]
        for s,e in candidates:
            with self.subTest(s=s,e=e):
                with tempfile.TemporaryDirectory() as td:
                    root=Path(td)
                    ledger,context=self.configured(root,s,record=e)
                    with context:
                        with self.assertRaises(InputError):
                            demo.inspect(root,EVENT,ledger,account_number=ACCOUNT,now=NOW)
                    self.assertFalse((root/demo.FILE_NAME).exists())

    def test_unpublished_hypothesis_is_not_an_executable_signal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ledger,context=self.configured(root,state())
            with context:
                with patch.object(demo,"_approved_review_in_journal",return_value=False):
                    with self.assertRaises(InputError):
                        demo.inspect(root,EVENT,ledger,account_number=ACCOUNT,now=NOW)
            self.assertFalse((root/demo.FILE_NAME).exists())

    def test_account_zero_or_unlisted_sha_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ledger,context=self.configured(root,state())
            with context:
                for account in (0,-1,1000000000):
                    with self.assertRaises(InputError):
                        demo.inspect(root,EVENT,ledger,
                                     account_number=account,now=NOW)
                with self.assertRaises(InputError):
                    demo.inspect(root,"not-sha",ledger,
                                 account_number=ACCOUNT,now=NOW)

    def test_cli_without_explicit_optin_makes_no_signal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            ledger,context=self.configured(root,state())
            with context:
                ret=demo.main([
                    "--store",str(root),
                    "--event-sha256",EVENT,
                    "--ledger",str(ledger),
                    "--expected-demo-account",str(ACCOUNT)
                ])
            self.assertEqual(ret,0)
            self.assertFalse((root/demo.FILE_NAME).exists())

    def test_mql4_executor_has_demo_and_order_limits_default_off(self):
        script=(Path(__file__).resolve().parents[1]/
                "mt4"/"demo"/"FxFinalTestDemoExecutor.mq4")
        code=script.read_text(encoding="utf-8")
        for required in (
            "EnableDemoOrders = false", "IsDemo()", "ExpectedDemoAccount",
            "AccountNumber()", "AccountCurrency() != \"JPY\"",
            "VerifiedNy17StartEquityJPY", "VerifiedPeakEquityJPY",
            "FXD_INTENT", "FxdHex64", "FxdRiskContract",
            "0.005", "0.985", "0.95", "0.96",
            "FxdHasAnyBrokerOrder()", "FXDEMO_HALTED_",
            "OrderSend(", "OrderClose(", "OrderModify(",
            "FxDemoConsumed_", "FxdActiveRiskAllowed()",
        ):
            self.assertIn(required,code,required)
        self.assertNotIn("FILE_COMMON",code.replace(
            "// Only reads MQL4/Files/FxDemoIntent_v1.csv; no DLL, WebRequest or FILE_COMMON.",
            ""))
        self.assertNotIn("WebRequest(",code)
        # MetaEditor warning 313: explicit grouping must preserve the
        # OR of magic mismatch and (neither BUY nor SELL).
        self.assertIn(
            "if((OrderMagicNumber() != FXD_MAGIC) ||\n"
            "         ((OrderType() != OP_BUY) && (OrderType() != OP_SELL))) continue;",
            code)
        self.assertNotIn(
            "OrderType() != OP_BUY && OrderType() != OP_SELL", code)


if __name__ == "__main__":
    unittest.main()
