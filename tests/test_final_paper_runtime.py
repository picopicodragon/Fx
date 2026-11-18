"""FINAL-PAPER: append-only integrity, replay refusal and read-only startup."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_runtime as runtime
from research import final_paper_engine as paper
from research.offline_backtest import InputError

NOW=datetime(2026,11,18,1,0,tzinfo=timezone.utc)
EPOCH=int(NOW.timestamp())


def quote(epoch=EPOCH):
    return {
      "capture_epoch":epoch,
      "source_sha256":"a"*64,
      "quotes":{pair:{
        "bid":paper.D("159.5") if pair=="USD/JPY" else
              paper.D("175.2") if pair=="EUR/JPY" else paper.D("1.1"),
        "ask":paper.D("159.505") if pair=="USD/JPY" else
              paper.D("175.21") if pair=="EUR/JPY" else paper.D("1.10005"),
        "ticksize":paper.D(".001") if pair.endswith("JPY") else paper.D(".00001"),
        "tickvalue":paper.D("100"),
        "minlot":paper.D(".01"),"maxlot":paper.D("20"),
        "step":paper.D(".01"),"point":paper.D(".001"),
      } for pair in paper.PAIRS},
    }


class FinalPaperRuntimeTests(unittest.TestCase):
    def test_initialized_zero_order_virtual_cycle_and_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"virtual"
            runtime._initialize(root)
            with patch.object(runtime,"_latest_quote",return_value=quote()), \
                 patch.object(runtime,"_latest_h1_copy",return_value=None):
                report=runtime.run_one_cycle(
                    Path(temp),root,[],allow_paid=False,
                    analyst_model="",reviewer_model="",paid_limit=0,now=NOW)
            self.assertEqual(report["virtual_equity_jpy"],"100000.00")
            self.assertEqual(report["broker_orders_sent_this_run"],0)
            self.assertFalse(report["real_orders_permitted"])
            state,digest=runtime._journal_load(root/"journal")
            self.assertEqual(state["cycle_number"],1)
            self.assertEqual(len(digest),64)
            self.assertFalse(state["broker_orders_permitted"])
            with patch.object(runtime,"_latest_quote",return_value=quote(EPOCH)):
                self.assertEqual(runtime.run_one_cycle(
                    Path(temp),root,[],allow_paid=False,
                    analyst_model="",reviewer_model="",paid_limit=0,
                    now=NOW)["status"],"PAPER_WAITING_FOR_NEXT_QUOTE")
            self.assertEqual(runtime._journal_load(root/"journal")[0][
                "cycle_number"],1)

    def test_tampered_or_deleted_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            runtime._initialize(root)
            state,_=paper.step(paper.initial_state(),quote())
            runtime._journal_append(root/"journal",state,"0"*64,"a"*64,NOW)
            event=root/"journal"/"00000001.json"
            altered=json.loads(event.read_text())
            altered["state"]["cash_jpy"]="999999999.00"
            event.write_text(json.dumps(altered))
            with self.assertRaises(InputError):
                runtime._journal_load(root/"journal")
            event.unlink()
            (root/"journal"/"00000002.json").write_text("{}")
            with self.assertRaises(InputError):
                runtime._journal_load(root/"journal")

    def test_no_ai_opt_in_causes_no_paid_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            runtime._initialize(root)
            with patch.object(runtime,"_latest_quote",return_value=quote()), \
                 patch.object(runtime,"_latest_h1_copy",return_value=None), \
                 patch.object(runtime.ai,"run") as inference:
                report=runtime.run_one_cycle(
                    Path(temp),root,[],allow_paid=False,
                    analyst_model="",reviewer_model="",paid_limit=0,now=NOW)
                inference.assert_not_called()
            self.assertEqual(report["paid_calls_this_cycle"],0)

    def test_runtime_sources_do_not_import_trading_or_jev(self):
        base=Path(__file__).resolve().parents[1]
        for name in ("research/final_paper_engine.py",
                     "research/final_paper_runtime.py",
                     "mt4/read_only/FxFinalPaperReadOnlyObserver.mq4"):
            code=(base/name).read_text(encoding="utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                              "OrderDelete(", "WebRequest(", "FILE_COMMON",
                              "#import ", "TYPESAFE_API_KEY",
                              "api.typesafe.ai", "EnableDemoOrders=true"):
                self.assertNotIn(forbidden,code)
        self.assertIn("max-paid-calls-lifetime",
                      (base/"research/final_paper_runtime.py").read_text())


if __name__=="__main__":
    unittest.main()
