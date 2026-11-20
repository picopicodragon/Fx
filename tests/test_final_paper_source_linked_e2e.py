"""Historical source-linked replay and no-cost saved review gates."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from research import final_paper_e2e_replay as replay
from research import final_paper_completed_decision as saved
from research import final_paper_engine as paper
from research.offline_backtest import InputError

NOW = datetime(2026,11,18,8,0,tzinfo=timezone.utc)
T = int(NOW.timestamp())


def quote(epoch, bid="159.50"):
    bid = paper.D(bid)
    return {
      "capture_epoch":epoch,"source_sha256":"a"*64,
      "quotes":{pair:{
         "bid":bid,"ask":bid+paper.D(".005"),
         "tickvalue":paper.D("100"),"ticksize":paper.D(".001"),
         "minlot":paper.D(".01"),"maxlot":paper.D("10"),
         "step":paper.D(".01"),"point":paper.D(".001"),
      } for pair in paper.PAIRS},
    }


def signal(action="LONG", verdict="APPROVED"):
    return {
      "id":"a"*64, "pair":"USD/JPY","action":action,"verdict":verdict,
      "reviewed_epoch":T-5,"atr14":".15","packet_sha256":"b"*64,
    }


class SourceLinkedReplayTests(unittest.TestCase):
    def test_hypothetical_open_and_take_profit_without_live_permission(self):
        quotes=[quote(T),quote(T+60,"159.55"),quote(T+120,"160.20")]
        result=replay.replay_captures(quotes,signal())
        self.assertTrue(result["virtual_position_opened"])
        self.assertTrue(result["virtual_stop_or_target_seen"])
        self.assertEqual(result["virtual_closed_trade_count"],1)
        self.assertEqual(result["virtual_position_count"],0)
        self.assertEqual(result["api_calls_this_run"],0)
        self.assertEqual(result["broker_orders_this_run"],0)
        self.assertFalse(result["live_virtual_entries_authorized"])
        self.assertFalse(result["real_transaction_costs_verified"])

    def test_hold_is_not_a_trade(self):
        r=replay.replay_captures([quote(T),quote(T+60)],signal("HOLD"))
        self.assertFalse(r["virtual_position_opened"])
        self.assertEqual(r["virtual_closed_trade_count"],0)

    def test_event_blackout_blocks_hypothetical_entry(self):
        with patch.object(replay.blackout,"check",return_value={
            "active_known_blackout":True}):
            result=replay.replay_captures(
                [quote(T),quote(T+60)],signal(),
                event_blackout_file=Path("/hypothetical-schedule"))
        self.assertFalse(result["virtual_position_opened"])

    def test_gaps_and_duplicate_or_reversed_quotes_rejected(self):
        for data in (
            [quote(T),quote(T)],
            [quote(T),quote(T+601)],
            [quote(T+60),quote(T)],
            [quote(T)],
        ):
            with self.subTest(captures=[x["capture_epoch"] for x in data]):
                with self.assertRaises(InputError):
                    replay.replay_captures(data,signal())

    def test_exact_ai_packet_binding_and_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"ai_research"
            folder.mkdir()
            bar=1794980000
            file=folder/f"ai_USDJPY_{bar}_20261118_075959.json"
            file.write_text('{"not":"real ledger"}',encoding="utf-8")
            os.utime(file,(T-5,T-5))
            state={
                "stage":"COMPLETE","pending_role":None,
                "analyst_model":"gpt-6.1-sol",
                "reviewer_model":"gpt-6-astra",
                "analyst":{"action":"LONG"},
                "reviewer":{"verdict":"APPROVED"},
                "packet_sha256":"b"*64,
            }
            h1={"captured_at_utc_pc_unattested":datetime.fromtimestamp(
                  T-100,tz=timezone.utc).isoformat().replace("+00:00","Z")}
            report={
                "macro_coverage_complete_research_only":True,
                "technical":{"atr14":0.15},
            }
            with patch.object(saved.ledger_reader,"_read_ledger",
                              return_value=(state,"c"*64)), \
                 patch.object(saved.period,"_read_h1",return_value=h1), \
                 patch.object(saved.period,"run",return_value=report), \
                 patch.object(saved.ai,"_identity",return_value={
                    "packet_sha256":"b"*64}), \
                 patch.object(saved.ai,"_valid") as valid, \
                 patch("research.final_paper_ai_continuation_audit.audit",
                       return_value={
                           "paid_calls_recorded_in_journal":6,
                           "paid_calls_in_completed_ledgers":6,
                       }):
                found=saved.load_completed(root,root,[root], "USD/JPY",
                                           bar,NOW)
                valid.assert_called_once()
                self.assertEqual(found["action"],"LONG")
                self.assertEqual(found["verdict"],"APPROVED")
                self.assertEqual(found["reviewed_epoch"],T-5)
            with patch.object(saved.ledger_reader,"_read_ledger",
                              return_value=(state,"c"*64)), \
                 patch.object(saved.period,"_read_h1",return_value=h1), \
                 patch.object(saved.period,"run",return_value=report), \
                 patch.object(saved.ai,"_identity",return_value={
                    "packet_sha256":"d"*64}), \
                 patch.object(saved.ai,"_valid"), \
                 patch("research.final_paper_ai_continuation_audit.audit",
                       return_value={
                           "paid_calls_recorded_in_journal":6,
                           "paid_calls_in_completed_ledgers":6,
                       }):
                with self.assertRaises(InputError):
                    saved.load_completed(root,root,[root],"USD/JPY",
                                         bar,NOW)
            with self.assertRaises(InputError):
                saved.load_completed(root,root,[root],"USD/JPY",
                                     bar,NOW+timedelta(seconds=4300))

    def test_runtime_reuses_completed_same_bar_ledger_without_paid_request(self):
        from research import final_paper_runtime as runtime
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            runtime._initialize(root)
            state=paper.initial_state()
            bars={"captures":{
                sym:{"candles":[{"server_epoch":123456}]}
                for sym in paper.SYMS}}
            decision=signal()
            with patch.object(runtime.period,"_read_h1",return_value=bars), \\
                 patch.object(runtime.completed_decision,"load_completed",
                     side_effect=[decision,None,None]), \\
                 patch.object(runtime.ai,"run") as inference:
                sig,seen,n=runtime._signals_for_new_h1(
                    state,root/"captures",[root/"archived_news"],root,NOW,
                    allow_paid=False,analyst_model="",reviewer_model="",
                    max_paid_calls=0)
                inference.assert_not_called()
            self.assertEqual(len(sig),1)
            self.assertEqual(sig[0]["id"],decision["id"])
            self.assertEqual(len(seen),3)
            self.assertEqual(n,0)
            state["processed_h1_keys"]=seen
            state["used_signal_ids"]=[decision["id"]]
            with patch.object(runtime.period,"_read_h1",return_value=bars), \\
                 patch.object(runtime.completed_decision,"load_completed") as proof, \\
                 patch.object(runtime.ai,"run") as inference:
                sig,seen,n=runtime._signals_for_new_h1(
                    state,root/"captures",[root/"archived_news"],root,NOW,
                    allow_paid=False,analyst_model="",reviewer_model="",
                    max_paid_calls=0)
                proof.assert_not_called()
                inference.assert_not_called()
            self.assertEqual(sig,[])
            self.assertEqual(seen,[])
            self.assertEqual(n,0)

    def test_no_api_or_broker_interfaces_in_replay(self):
        base=Path(__file__).resolve().parents[1]
        for name in ("research/final_paper_e2e_replay.py",
                     "research/final_paper_completed_decision.py"):
            code=(base/name).read_text("utf-8")
            for forbidden in (
                "OrderSend(", "OrderClose(", "OrderModify(", "WebRequest(",
                "urllib.request", "ai.run(", "OPENAI_API_KEY",
                "lock.unlink(", "_journal_append("
            ):
                self.assertNotIn(forbidden,code)


if __name__=="__main__":
    unittest.main()
