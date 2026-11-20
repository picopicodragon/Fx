"""Real-source three-pair tick timing race and no-trading remediation tests."""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as engine
from research import final_paper_quote_time_order_campaign as campaign
from research import final_paper_multiday_quote_stress as strict
from research.offline_backtest import InputError

BASE=datetime(2026,11,19,3,50,52,tzinfo=timezone.utc)


def write_quote(folder:Path,dt:datetime, *, inversion=False,
                filename_time_mismatch=False)->Path:
    epoch=int(dt.timestamp())
    name=f"FxPaperQuote_{dt.strftime('%Y%m%d_%H%M%S')}.csv"
    path=folder/name
    with path.open("w",encoding="utf-8",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=engine.QUOTE_FIELDS)
        writer.writeheader()
        for i,(symbol,bid,wide) in enumerate((
            ("USDJPY","158.500",".005"),
            ("EURJPY","175.300",".01"),
            ("EURUSD","1.10000",".00005"),
        )):
            tick=epoch+7200-1
            if inversion and i==0:
                tick=epoch+7200+1
            if inversion and i==1:
                tick=epoch+7200+2
            writer.writerow({
                "pair":symbol,
                "bid":bid,
                "ask":str(D(bid)+D(wide)),
                "tick_time_broker_epoch_unattested":tick,
                "broker_time_epoch_unattested":epoch+7200,
                "capture_epoch_utc_pc":epoch+(1 if
                    filename_time_mismatch else 0),
                "tickvalue_jpy_broker_reported":"100",
                "ticksize_broker_reported":".001" if i<2 else ".00001",
                "min_lot_broker_reported":".01",
                "lot_step_broker_reported":".01",
                "max_lot_broker_reported":"20",
                "point_broker_reported":".001" if i<2 else ".00001",
            })
    return path


class ClockRaceResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.folder=self.root/"MQL4"/"Files"
        self.folder.mkdir(parents=True)

    def test_two_pair_future_tick_event_preserved_and_segments_separate(self):
        first=write_quote(self.folder,BASE)
        bad=write_quote(self.folder,BASE+timedelta(seconds=60),
                        inversion=True)
        last=write_quote(self.folder,BASE+timedelta(seconds=120))
        originals={f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                   for f in (first,bad,last)}
        result=campaign.review(self.folder)
        self.assertEqual(result["reviewed_original_count"],3)
        self.assertEqual(result["strict_engine_valid_original_count"],2)
        self.assertEqual(result["invalid_original_count"],1)
        self.assertFalse(result["all_originals_passed_strict_engine"])
        self.assertEqual(result["future_tick_after_broker_count_by_pair"],
                         {"USDJPY":1,"EURJPY":1,"EURUSD":0})
        self.assertEqual(result["future_tick_lead_seconds_max_by_pair"],
                         {"USDJPY":1,"EURJPY":2,"EURUSD":0})
        self.assertEqual(
            result["invalid_condition_occurrences"][
                "TICK_TIME_AFTER_BROKER_TIME"],1)
        self.assertEqual(result["valid_segments_around_invalid_or_missing_minutes"],2)
        self.assertEqual(result["longest_valid_contiguous_sample_count"],1)
        self.assertEqual(result["first_invalid_originals_up_to_25"][0][
            "source_basename"],bad.name)
        self.assertFalse(result["new_virtual_positions_permitted"])
        self.assertFalse(result["new_paid_ai_calls_permitted"])
        self.assertFalse(result["partial_valid_segments_can_enable_new_virtual_entries"])
        for f in (first,bad,last):
            self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),
                             originals[f.name])
        with self.assertRaises(InputError):
            strict.review(self.folder)

    def test_missing_minute_breaks_valid_contiguous_research_run(self):
        write_quote(self.folder,BASE)
        write_quote(self.folder,BASE+timedelta(seconds=120))
        result=campaign.review(self.folder)
        self.assertEqual(result["invalid_original_count"],0)
        self.assertEqual(result["time_gaps_above_90s_between_all_source_files"],1)
        self.assertEqual(result["longest_valid_contiguous_sample_count"],1)
        self.assertEqual(result["valid_segments_around_invalid_or_missing_minutes"],2)
        self.assertFalse(result["new_virtual_positions_permitted"])

    def test_filename_capture_mismatch_not_silently_accepted(self):
        write_quote(self.folder,BASE)
        bad=write_quote(self.folder,BASE+timedelta(seconds=60),
                        filename_time_mismatch=True)
        result=campaign.review(self.folder)
        self.assertEqual(result["invalid_original_count"],1)
        self.assertEqual(result["first_invalid_originals_up_to_25"][0][
            "source_basename"],bad.name)
        self.assertIn("CAPTURE_TIME_DIFFERS_FROM_FILENAME",
                      result["invalid_condition_occurrences"])
        self.assertFalse(result["all_originals_passed_strict_engine"])

    def test_invalid_filename_is_a_fail_closed_campaign_not_a_skip(self):
        write_quote(self.folder,BASE)
        write_quote(self.folder,BASE+timedelta(seconds=60))
        (self.folder/"FxPaperQuote_bad.csv").write_bytes(b"bad")
        with self.assertRaises(InputError):
            campaign.review(self.folder)

    def test_mql4_observer_freezes_each_field_before_server_clock_read(self):
        src=(Path(__file__).resolve().parents[1]/
             "mt4/read_only/FxFinalPaperReadOnlyObserver.mq4"
            ).read_text("utf-8")
        start=src.index("bool PaperSnapshot(datetime pcUtc)")
        end=src.index("bool PaperExportH1",start)
        snap=src[start:end]
        self.assertIn("tickTimes[i]=(datetime)MarketInfo(s,MODE_TIME)",snap)
        self.assertIn("datetime brokerNow=TimeCurrent();",snap)
        self.assertIn("if(tickAge<0 || tickAge>30)",snap)
        self.assertIn("IntegerToString((int)tickTimes[n])",snap)
        self.assertIn("DoubleToString(bids[n],digits[n])",snap)
        self.assertIn("DoubleToString(asks[n],digits[n])",snap)
        self.assertLess(snap.index("tickTimes[i]=(datetime)MarketInfo"),
                        snap.index("datetime brokerNow=TimeCurrent()"))
        self.assertLess(snap.index("datetime brokerNow=TimeCurrent()"),
                        snap.index("int f=FileOpen(output"))
        # No MarketInfo can be read again in serialization loop.
        output_loop=snap[snap.index("int f=FileOpen(output"):]
        self.assertNotIn("MarketInfo(",output_loop)
        self.assertNotIn("PaperSnapshot(pcUtc,brokerNow)",src)
        self.assertIn("if(!PaperSnapshot(pcUtc))",src)
        self.assertIn("AccountCurrency()==\"JPY\"",src)
        self.assertIn("IsDemo() && IsConnected()",src)
        for forbidden in ("OrderSend(","OrderClose(","OrderModify(",
                          "WebRequest(","#import","ShellExecute",
                          "AccountFreeMarginCheck("):
            self.assertNotIn(forbidden,src)

    def test_windows_script_no_risk_latch_or_runtime_mutation(self):
        wrapper=(Path(__file__).resolve().parents[1]/
                 "scripts/final_paper_quote_time_order_campaign_once.ps1"
                ).read_text("utf-8")
        self.assertIn("final_paper_quote_time_order_campaign",wrapper)
        for forbidden in ("Start-Process","Stop-Process","Remove-Item",
                          "Rename-Item","OrderSend","AllowPaidAi",
                          "Set-Content","Invoke-WebRequest"):
            self.assertNotIn(forbidden,wrapper)
        source=(Path(__file__).resolve().parents[1]/
                "research/final_paper_quote_time_order_campaign.py"
               ).read_text("utf-8")
        for forbidden in ("_journal_append(", "OrderSend(", "OrderClose(",
                          "allow_external_api=True","urllib.request",
                          "lock.unlink(", "OPENAI_API_KEY"):
            self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
