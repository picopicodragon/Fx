"""Regression tests: never mutate, bypass, or leak the invalid MT4 source."""
from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as engine
from research import final_paper_quote_contract_forensics as forensic
from research import final_paper_multiday_quote_stress as strict
from research.offline_backtest import InputError

BASE=datetime(2026,11,19,3,51,52,tzinfo=timezone.utc)


def _file(folder:Path, when:datetime, problem:str|None=None)->Path:
    epoch=int(when.timestamp())
    file=folder/f"FxPaperQuote_{when.strftime('%Y%m%d_%H%M%S')}.csv"
    pairs=[("USDJPY","158.900",".005"),("EURJPY","175.200",".010"),
           ("EURUSD","1.10000",".00005")]
    with file.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=engine.QUOTE_FIELDS)
        writer.writeheader()
        for idx,(sym,bid,wide) in enumerate(pairs):
            ask=str(D(bid)+D(wide))
            row={
                "pair":sym,"bid":bid,"ask":ask,
                "tick_time_broker_epoch_unattested":epoch+7200-1,
                "broker_time_epoch_unattested":epoch+7200,
                "capture_epoch_utc_pc":epoch,
                "tickvalue_jpy_broker_reported":"100",
                "ticksize_broker_reported":".001" if idx<2 else ".00001",
                "min_lot_broker_reported":".01",
                "lot_step_broker_reported":".01",
                "max_lot_broker_reported":"20",
                "point_broker_reported":".001" if idx<2 else ".00001",
            }
            if idx==1:
                if problem=="crossed":row["ask"]=bid
                if problem=="stale_tick":row["tick_time_broker_epoch_unattested"]=epoch+7200-31
                if problem=="future_tick":row["tick_time_broker_epoch_unattested"]=epoch+7200+1
                if problem=="max_lot":row["max_lot_broker_reported"]=".005"
                if problem=="step":row["lot_step_broker_reported"]="25"
                if problem=="zero_tickvalue":row["tickvalue_jpy_broker_reported"]="0"
                if problem=="wrong_capture":row["capture_epoch_utc_pc"]=epoch+1
            writer.writerow(row)
    return file


class OriginalContractEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.folder=Path(self.t.name)/"MQL4"/"Files"
        self.folder.mkdir(parents=True)
        self.bad=_file(self.folder,BASE,problem="crossed")
        self.before=_file(self.folder,BASE-timedelta(seconds=60))
        self.after=_file(self.folder,BASE+timedelta(seconds=60))

    def _rewrite(self,issue):
        self.bad.unlink()
        self.bad=_file(self.folder,BASE,problem=issue)

    def test_user_1513_crossed_pair_explicit_field_no_original_leak(self):
        before=self.bad.read_bytes()
        r=forensic.investigate(self.folder,self.bad.name)
        self.assertEqual(r["status"],"TARGET_SOURCE_FIELD_FORENSICS_RESEARCH_HOLD_NO_GO")
        self.assertFalse(r["engine_quote_validator_passed"])
        self.assertEqual(r["issues_without_source_values"],[
            {"row_ordinal":2,"code":"ASK_NOT_GREATER_THAN_BID",
             "field":"ask","symbol":"EURJPY"}])
        self.assertEqual(len(r["nearby_original_sources"]),2)
        self.assertTrue(all(n["engine_quote_validator_passed"]
                            for n in r["nearby_original_sources"]))
        self.assertEqual(r["original_sha256_local_only"],
                         hashlib.sha256(before).hexdigest())
        self.assertEqual(self.bad.read_bytes(),before)
        for k in ("original_csv_modified","new_paid_ai_calls_permitted",
                  "new_virtual_positions_permitted","demo_orders_permitted",
                  "real_orders_permitted","overall_multiday_gate_passed"):
            self.assertFalse(r[k])
        with self.assertRaises(InputError):
            strict.review(self.folder)  # must remain full source NO_GO

    def test_time_and_contract_categories(self):
        for problem,code in (
            ("stale_tick","BROKER_RELATIVE_TICK_AGE_OVER_30S"),
            ("future_tick","TICK_TIME_AFTER_BROKER_TIME"),
            ("max_lot","MIN_LOT_EXCEEDS_MAX_LOT"),
            ("step","LOT_STEP_EXCEEDS_MAX_LOT"),
            ("zero_tickvalue","NUMERIC_FIELD_NOT_POSITIVE_FINITE"),
            ("wrong_capture","CAPTURE_TIME_DIFFERS_FROM_FILENAME"),
        ):
            with self.subTest(problem=problem):
                self._rewrite(problem)
                result=forensic.investigate(self.folder,self.bad.name)
                # The continuous engine checks quote freshness (+/-10s),
                # while the multi-day auditor additionally requires the
                # source filename to equal the original capture epoch.
                self.assertEqual(result["engine_quote_validator_passed"],
                                 problem=="wrong_capture")
                self.assertFalse(result["strict_multiday_source_passed"])
                self.assertIn(code,[i["code"]
                                   for i in result["issues_without_source_values"]])

    def test_normal_file_reports_no_anomaly_but_is_not_trade_go(self):
        r=forensic.investigate(self.folder,self.before.name)
        self.assertTrue(r["engine_quote_validator_passed"])
        self.assertEqual(r["issues_without_source_values"],[])
        self.assertFalse(r["new_virtual_positions_permitted"])

    def test_path_traversal_and_symlink_rejected(self):
        for name in ("../secret.csv","FxPaperQuote_00000000_000000.csv",
                     "FxPaperQuote_20261119_035152.csv/../../test"):
            with self.subTest(name=name):
                with self.assertRaises(InputError):
                    forensic.investigate(self.folder,name)
        with self.assertRaises(InputError):
            forensic.investigate(self.folder,self.bad.name,neighbors=4)

    def test_windows_wrapper_no_mutation_and_hash_before_after(self):
        base=Path(__file__).resolve().parents[1]
        powershell=(base/"scripts/final_paper_quote_contract_forensics_once.ps1").read_text("utf-8")
        self.assertIn("Get-FileHash",powershell)
        self.assertIn("$originalHash -ne $newHash",powershell)
        self.assertIn("FxPaperQuote_20261119_035152.csv",powershell)
        for forbidden in ("Stop-Process","Start-Process","Remove-Item",
                          "Rename-Item","Invoke-WebRequest","OrderSend",
                          "Set-Content","AllowPaidAi"):
            self.assertNotIn(forbidden,powershell)
        src=(base/"research/final_paper_quote_contract_forensics.py").read_text("utf-8")
        for forbidden in ("_journal_append(","OrderSend(","OrderClose(",
                          "allow_external_api=True","urllib.request",
                          "OPENAI_API_KEY","lock.unlink("):
            self.assertNotIn(forbidden,src)


if __name__=="__main__":
    unittest.main()
