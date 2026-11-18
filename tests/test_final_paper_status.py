"""Final paper local status: meaningful virtual equity without orders."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_engine as paper
from research import final_paper_runtime as runtime
from research import final_paper_status as status
from research.offline_backtest import InputError

T=datetime(2026,11,18,0,0,tzinfo=timezone.utc)


class PaperStatusTests(unittest.TestCase):
    def test_readonly_status_reports_100k_before_trades(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"virtual"
            runtime._initialize(root)
            result=status.summarize(root)
            self.assertEqual(result["virtual_start_capital_jpy"],"100000.00")
            self.assertEqual(result["virtual_net_pnl_jpy"],"0.00")
            self.assertEqual(result["virtual_trade_count"],0)
            self.assertFalse(result["jev_enabled"])
            self.assertFalse(result["broker_orders_permitted"])

    def test_status_from_completed_chain(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"virtual"
            runtime._initialize(root)
            state=paper.initial_state()
            obs={"capture_epoch":int(T.timestamp()),
                 "quotes":{pair:{
                     "bid":paper.D("150"),"ask":paper.D("150.01"),
                     "tickvalue":paper.D("100"),
                     "ticksize":paper.D(".001"),
                     "minlot":paper.D(".01"),"step":paper.D(".01"),
                     "maxlot":paper.D("20"),"point":paper.D(".001")}
                     for pair in paper.PAIRS}}
            state,_=paper.step(state,obs)
            runtime._journal_append(
                root/"journal",state,"0"*64,"a"*64,T)
            result=status.summarize(root)
            self.assertEqual(result["completed_cycles"],1)
            self.assertEqual(result["virtual_equity_jpy"],"100000.00")
            self.assertEqual(len(result["journal_head_sha256_local_only"]),64)
            self.assertFalse(result["real_orders_permitted"])

    def test_status_halts_on_corrupted_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"virtual"
            runtime._initialize(root)
            (root/"journal"/"00000001.json").write_text("{}")
            with self.assertRaises(InputError):
                status.summarize(root)


if __name__=="__main__":
    unittest.main()
