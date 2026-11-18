"""No-cost DEMO quote sampling records spreads, never certifies costs."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_quote_contract_evidence as evidence
from research import final_paper_engine as paper
from research.offline_backtest import InputError

T=1794963600
NOW=datetime.fromtimestamp(T+9*60+16,tz=timezone.utc)


def write_quote(folder:Path,n:int,*,spread:int=5):
    epoch=T+n*60
    file=folder/(datetime.fromtimestamp(
        epoch,tz=timezone.utc).strftime("FxPaperQuote_%Y%m%d_%H%M%S.csv"))
    with file.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.writer(handle)
        writer.writerow(paper.QUOTE_FIELDS)
        for symbol,bid,ask,tickvalue,ticksize in (
            ("USDJPY","159.500",f"{159.500+spread*.001:.3f}","100",".001"),
            ("EURJPY","175.200","175.210","100",".001"),
            ("EURUSD","1.10000","1.10005","155",".00001")
        ):
            writer.writerow([symbol,bid,ask,epoch,epoch,epoch,
                             tickvalue,ticksize,".01",".01","20",ticksize])
    return file


class FinalPaperQuoteContractEvidenceTests(unittest.TestCase):
    def test_ten_h1_compatible_snapshots_observe_spreads_not_total_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"MT4"/"MQL4"/"Files"
            folder.mkdir(parents=True)
            for i in range(10):
                write_quote(folder,i,spread=5+i%2)
            output=evidence.audit(folder,now=NOW)
            self.assertEqual(output["sampled_complete_three_pair_cycles"],10)
            self.assertEqual(output["latest_quote_age_seconds_pc_derived"],16)
            self.assertTrue(output["latest_quote_fresh_pc_derived"])
            self.assertTrue(output["sampled_intervals_all_30_to_90_seconds"])
            self.assertEqual(output["sampled_quote_interval_max_seconds"],60)
            self.assertEqual(output["per_pair"]["USD/JPY"][
                "spread_min_pips_observed"],"0.5")
            self.assertEqual(output["per_pair"]["USD/JPY"][
                "spread_max_pips_observed"],"0.6")
            self.assertEqual(output["per_pair"]["USD/JPY"][
                "broker_reported_tickvalue_unique_count"],1)
            self.assertFalse(output["full_transaction_costs_verified"])
            self.assertFalse(output["broker_clock_independently_attested"])
            self.assertFalse(output["new_virtual_entries_permitted"])
            self.assertFalse(output["new_paid_ai_calls_permitted"])

    def test_raw_mt4_sample_fresh_through_120_seconds_not_121(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"MT4"/"MQL4"/"Files"
            folder.mkdir(parents=True)
            write_quote(folder,0)
            for age,expected in ((59,True),(60,True),(70,True),
                                 (120,True),(121,False)):
                with self.subTest(age=age):
                    at=datetime.fromtimestamp(T+age,tz=timezone.utc)
                    output=evidence.audit(folder,now=at)
                    self.assertEqual(output[
                        "latest_quote_fresh_pc_derived"],expected)
                    self.assertEqual(output[
                        "latest_quote_age_seconds_pc_derived"],age)
                    self.assertFalse(output["full_transaction_costs_verified"])

    def test_only_last_ten_snapshots_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"MT4"/"MQL4"/"Files"
            folder.mkdir(parents=True)
            for i in range(13):
                write_quote(folder,i)
            current=datetime.fromtimestamp(T+12*60+10,tz=timezone.utc)
            output=evidence.audit(folder,now=current)
            self.assertEqual(output["sampled_complete_three_pair_cycles"],10)

    def test_malformed_or_reversed_data_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"MT4"/"MQL4"/"Files"
            folder.mkdir(parents=True)
            file=write_quote(folder,0)
            file.write_text("bad\n",encoding="utf-8")
            with self.assertRaises(InputError):
                evidence.audit(folder,now=NOW)
            file.unlink()
            with self.assertRaises(InputError):
                evidence.audit(folder,now=NOW)

    def test_snapshot_count_must_be_strict_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"MT4"/"MQL4"/"Files"
            folder.mkdir(parents=True)
            write_quote(folder,0)
            for count in (0,11,True,-1):
                with self.subTest(count=count),self.assertRaises(InputError):
                    evidence.audit(folder,max_files=count,now=NOW)

    def test_cli_does_not_overwrite_previous_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/"MT4"/"MQL4"/"Files"
            folder.mkdir(parents=True)
            write_quote(folder,0)
            out=Path(tmp)/"audit.json"
            with patch.object(evidence,"audit",
                              return_value=evidence.audit(folder,now=NOW)):
                self.assertEqual(evidence.main([
                    "--mt4-files",str(folder),"--out",str(out)]),0)
                before=out.read_bytes()
                self.assertEqual(evidence.main([
                    "--mt4-files",str(folder),"--out",str(out)]),2)
            self.assertEqual(before,out.read_bytes())

    def test_no_broker_network_paid_ai_or_shutdown_calls(self):
        root=Path(__file__).resolve().parents[1]
        for file in ("research/final_paper_quote_contract_evidence.py",
                     "scripts/final_paper_quote_contract_audit_once.ps1"):
            source=(root/file).read_text(encoding="utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "OrderModify(",
                              "urllib.request", "WebRequest(",
                              "OPENAI_API_KEY","TYPESAFE_API_KEY",
                              "Remove-Item", "Stop-Process",
                              "_journal_append(", "lock.unlink("):
                self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
