"""FINAL-PAPER-31: diagnose missing/stale MT4 quotes vs stalled consumer.

Only local synthetic CSV and append-only paper journal are touched in tests.
"""
from __future__ import annotations

import csv
import os
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_stream_diagnostic as probe
from research import final_paper_runtime as runtime
from research import final_paper_engine as paper
from research.offline_backtest import InputError

NOW=datetime(2026,11,18,5,0,tzinfo=timezone.utc)
T=int(NOW.timestamp())


def seed(root:Path, journal_epoch:int=0):
    runtime._initialize(root)
    if journal_epoch:
        state=paper.initial_state()
        state["cycle_number"]=1
        state["last_quote_epoch"]=journal_epoch
        runtime._journal_append(
            root/"journal",state,"0"*64,"a"*64,NOW)


def raw(mt4:Path, epoch:int):
    mt4.mkdir(parents=True,exist_ok=True)
    file=mt4/"FxPaperQuote_20261118_130000.csv"
    with file.open("w",newline="",encoding="utf-8") as output:
        writer=csv.writer(output)
        writer.writerow(paper.QUOTE_FIELDS)
        for sym in paper.SYMS:
            writer.writerow([sym,"159.501","159.506",epoch,epoch,epoch,
                             "100",".001",".01",".01","20",".001"])
    os.utime(file,(epoch,epoch))
    return file


class ReadOnlyStreamGapTests(unittest.TestCase):
    def test_report_2020_second_stale_observer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            mt4=Path(tmp)/"MT4"/"MQL4"/"Files"
            seed(root,T-2020)
            raw(mt4,T-2020)
            before=(root/"journal"/"00000001.json").read_bytes()
            report=probe.diagnose(root,mt4,now=NOW)
            self.assertEqual(report["journal_cycles"],1)
            self.assertEqual(report["diagnosis"],
                             "MT4_OBSERVER_QUOTE_STREAM_STALE")
            self.assertEqual(report["last_processed_quote_age_seconds_pc_derived"],
                             2020)
            self.assertEqual(report["latest_raw_quote_age_seconds_pc_derived"],2020)
            self.assertFalse(report["raw_quote_ahead_of_journal"])
            self.assertEqual((root/"journal"/"00000001.json").read_bytes(),
                             before)
            self.assertFalse(report["new_paid_calls_authorized"])
            self.assertFalse(report["demo_orders_permitted"])

    def test_fresh_raw_quote_unconsumed_identifies_python_side(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            mt4=Path(tmp)/"MT4"/"MQL4"/"Files"
            seed(root,T-2020)
            raw(mt4,T-20)
            (root/".single_operator.lock").write_text("running")
            report=probe.diagnose(root,mt4,now=NOW)
            self.assertEqual(report["diagnosis"],
                             "FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON")
            self.assertTrue(report["raw_quote_ahead_of_journal"])
            self.assertTrue(report["runtime_lock_present_not_process_proof"])
            self.assertEqual(report["paper_supervisor_running"],"NOT_ATTESTED")

    def test_recent_quote_already_processed_is_not_claimed_process_alive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            mt4=Path(tmp)/"MT4"/"MQL4"/"Files"
            seed(root,T-20)
            raw(mt4,T-20)
            report=probe.diagnose(root,mt4,now=NOW)
            self.assertEqual(report["diagnosis"],"LATEST_MT4_QUOTE_ALREADY_PROCESSED")
            self.assertEqual(report["mt4_observer_running"],"NOT_ATTESTED")

    def test_missing_mt4_quote_identified_no_restarts_or_orders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            mt4=Path(tmp)/"MT4"/"MQL4"/"Files"
            seed(root,T-2020)
            mt4.mkdir(parents=True)
            report=probe.diagnose(root,mt4,now=NOW)
            self.assertEqual(report["diagnosis"],"MT4_OBSERVER_HAS_NO_QUOTE_CSV")
            self.assertFalse(report["new_paid_calls_authorized"])
            self.assertEqual(report["api_calls_this_run"],0)

    def test_stale_raw_but_unconsumed_distinct_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            mt4=Path(tmp)/"MT4"/"MQL4"/"Files"
            seed(root,T-2020)
            raw(mt4,T-180)
            report=probe.diagnose(root,mt4,now=NOW)
            self.assertEqual(report["diagnosis"],
                             "UNPROCESSED_MT4_QUOTES_ALREADY_STALE")

    def test_malformed_quote_fails_closed_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"paper"
            mt4=Path(tmp)/"MT4"/"MQL4"/"Files"
            seed(root,T-2020)
            file=raw(mt4,T-20)
            file.write_text("incorrect,untrusted\n",encoding="utf-8")
            with self.assertRaises(InputError):
                probe.diagnose(root,mt4,now=NOW)
            self.assertEqual(len(list((root/"journal").glob("*.json"))),1)

    def test_stateless_script_has_no_network_order_or_ledger_mutations(self):
        base=Path(__file__).resolve().parents[1]
        paths=("research/final_paper_stream_diagnostic.py",
               "scripts/final_paper_stream_diagnostic_once.ps1")
        for path in paths:
            source=(base/path).read_text("utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                              "WebRequest(", "OPENAI_API_KEY",
                              "TYPESAFE_API_KEY", "allow_external_api=True",
                              "lock.unlink(", "journal_append("):
                self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
