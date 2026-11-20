"""Offline full original multi-day quote and archived-source coverage tests."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as paper
from research import final_paper_multiday_quote_stress as multi
from research import final_paper_official_archive_integrity as archive
from research import final_paper_public_source_snapshot as original
from research.offline_backtest import InputError

UTC=timezone.utc
START=datetime(2026,11,17,3,0,tzinfo=UTC)


def capture(folder:Path, dt:datetime, *, widened=False, offset=7200):
    epoch=int(dt.timestamp())
    path=folder/f"FxPaperQuote_{dt.strftime('%Y%m%d_%H%M%S')}.csv"
    spreads=(".016",".024",".00011") if widened else (
        ".005",".01",".00005")
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=paper.QUOTE_FIELDS)
        writer.writeheader()
        for sym,bid,spr in zip(paper.SYMS,("159.50","175.20","1.1000"),
                                spreads):
            writer.writerow({
                "pair":sym,"bid":bid,"ask":str(D(bid)+D(spr)),
                "capture_epoch_utc_pc":epoch,
                "broker_time_epoch_unattested":epoch+offset,
                "tick_time_broker_epoch_unattested":epoch+offset-1,
                "tickvalue_jpy_broker_reported":"100",
                "ticksize_broker_reported":"0.001" if sym!="EURUSD"
                                            else "0.00001",
                "min_lot_broker_reported":"0.01",
                "lot_step_broker_reported":"0.01",
                "max_lot_broker_reported":"20",
                "point_broker_reported":"0.001" if sym!="EURUSD"
                                         else "0.00001",
            })
    return path


class MultidayQuoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/"MQL4"/"Files"
        self.folder.mkdir(parents=True)

    def test_three_day_spread_widening_and_quote_gaps_stay_research(self):
        for day in range(3):
            for minute in range(10):
                capture(self.folder, START+timedelta(days=day,
                    minutes=minute),widened=minute in (6,7))
        data=multi.review(self.folder)
        self.assertEqual(data["original_complete_quote_cycles_scanned"],30)
        self.assertEqual(data["distinct_ny17_observed_day_buckets"],3)
        self.assertTrue(data["minimum_three_ny17_days_observed_research_only"])
        self.assertEqual(data["quote_intervals_above_600_seconds"],2)
        self.assertEqual(
            data["observed_three_pairs"]["USD/JPY"][
                "at_least_twice_observed_median_count"],6)
        self.assertEqual(
            data["observed_three_pairs"]["USD/JPY"][
                "longest_consecutive_twice_median_samples"],2)
        self.assertEqual(data["observed_three_pairs"]["USD/JPY"][
            "observed_max_spread_pips"],"1.60")
        self.assertFalse(data["full_trading_day_coverage_proven"])
        self.assertFalse(data["broker_clock_independently_attested"] if
                         "broker_clock_independently_attested" in data
                         else data["independently_attested_broker_clock"])
        self.assertFalse(data["new_virtual_positions_permitted"])
        self.assertFalse(data["new_paid_ai_calls_permitted"])
        self.assertEqual(len(data["per_ny17_day"]),3)

    def test_single_day_real_240_samples_stays_insufficient(self):
        for minute in range(240):
            capture(self.folder,START+timedelta(minutes=minute),
                    widened=minute==239)
        data=multi.review(self.folder)
        self.assertEqual(data["distinct_ny17_observed_day_buckets"],1)
        self.assertEqual(data["quote_intervals_above_90_seconds"],0)
        self.assertEqual(data["observed_three_pairs"]["EUR/USD"][
            "observed_max_spread_pips"],"1.10")
        self.assertFalse(data["minimum_three_ny17_days_observed_research_only"])
        self.assertFalse(data["full_execution_spread_slippage_swap_cost_proven"])

    def test_reject_tampered_original_and_overlimit_file_count(self):
        capture(self.folder,START)
        other=capture(self.folder,START+timedelta(minutes=1))
        a=other.read_text("utf-8")
        other.write_text(a.replace(str(int((START+timedelta(minutes=1)).timestamp())),
                                 str(int(START.timestamp()))))
        with self.assertRaises(InputError):
            multi.review(self.folder)
        with self.assertRaises(InputError):
            multi.review(self.folder,max_files=10081)


class PublicArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/"official_public_capture_20261120_113041_303"
        self.payload=b"source-original"
        self.record=original.snapshot(
            self.folder, allow_network=True,
            fetcher=lambda _: (self.payload,"Fri, 20 Nov 2026 02:30:00 GMT"),
            now=datetime(2026,11,20,2,30,tzinfo=UTC))

    def test_all_six_hashes_match_without_economic_calendar_approval(self):
        out=archive.audit(self.folder)
        self.assertTrue(out["all_saved_bytes_locally_consistent"])
        self.assertEqual(out["original_source_count"],6)
        self.assertFalse(out["complete_usd_eur_jpy_high_impact_calendar_verified"])
        self.assertFalse(out["pre_release_consensus_independently_verified"])
        self.assertFalse(out["new_paid_ai_calls_permitted"])
        self.assertFalse(out["new_virtual_positions_permitted"])

    def test_modified_or_missing_source_fails_closed(self):
        source=self.folder/"us_bls_calendar_ics.ics"
        source.write_bytes(self.payload+b"tamper")
        with self.assertRaises(InputError):
            archive.audit(self.folder)
        source.write_bytes(self.payload)
        source.unlink()
        with self.assertRaises(InputError):
            archive.audit(self.folder)

    def test_nonoriginal_or_extra_page_fails_closed(self):
        m=self.folder/"manifest.json"
        obj=json.loads(m.read_text("utf-8"))
        obj["sources"][0]["url"]="https://example.com/evil.ics"
        m.write_text(json.dumps(obj))
        with self.assertRaises(InputError):
            archive.audit(self.folder)
        obj["sources"][0]["url"]=original.SOURCES["us_bls_calendar_ics"]
        m.write_text(json.dumps(obj))
        (self.folder/"untracked.html").write_text("not in manifest")
        with self.assertRaises(InputError):
            archive.audit(self.folder)

    def test_no_network_or_broker_calls_in_new_reviewers(self):
        base=Path(__file__).resolve().parents[1]
        for f in ("research/final_paper_multiday_quote_stress.py",
                  "research/final_paper_official_archive_integrity.py"):
            src=(base/f).read_text("utf-8")
            for forbidden in ("_journal_append(","OrderSend(","OrderClose(",
                              "allow_external_api=True","urllib.request",
                              "lock.unlink(", "OPENAI_API_KEY"):
                self.assertNotIn(forbidden,src)


if __name__=="__main__":
    unittest.main()
