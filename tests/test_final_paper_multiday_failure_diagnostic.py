"""Do not swallow original historical quote failures or skip official hashes."""
from __future__ import annotations

import contextlib
import csv
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as paper
from research import final_paper_multiday_quote_stress as multi


def quote(folder:Path, dt:datetime, *, damaged=False)->Path:
    epoch=int(dt.timestamp())
    path=folder / f"FxPaperQuote_{dt.strftime('%Y%m%d_%H%M%S')}.csv"
    with path.open("w",encoding="utf-8",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=paper.QUOTE_FIELDS)
        writer.writeheader()
        for symbol,bid,spread in (
            ("USDJPY","159.50",".005"),
            ("EURJPY","175.20",".01"),
            ("EURUSD","1.1000",".00005"),
        ):
            writer.writerow({
                "pair":"GBPJPY" if damaged and symbol=="EURJPY" else symbol,
                "bid":bid,"ask":str(D(bid)+D(spread)),
                "capture_epoch_utc_pc":epoch,
                "broker_time_epoch_unattested":epoch+7200,
                "tick_time_broker_epoch_unattested":epoch+7199,
                "tickvalue_jpy_broker_reported":"100",
                "ticksize_broker_reported":
                    ".00001" if symbol=="EURUSD" else ".001",
                "min_lot_broker_reported":".01",
                "lot_step_broker_reported":".01",
                "max_lot_broker_reported":"20",
                "point_broker_reported":
                    ".00001" if symbol=="EURUSD" else ".001",
            })
    return path


class FailClosedDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.folder=self.root/"MQL4"/"Files"
        self.folder.mkdir(parents=True)
        self.now=datetime(2026,11,20,3,0,tzinfo=timezone.utc)

    def _call(self):
        buffer=io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc=multi.main([
                "--mt4-files",str(self.folder),
                "--out",str(self.root/"not-to-be-created.json"),
            ])
        return rc,json.loads(buffer.getvalue())

    def test_historical_bad_file_is_identified_but_never_skipped(self):
        quote(self.folder,self.now)
        bad=quote(self.folder,self.now+timedelta(minutes=1),damaged=True)
        quote(self.folder,self.now+timedelta(minutes=2))
        rc,obj=self._call()
        self.assertEqual(rc,2)
        self.assertEqual(obj["status"],"MULTIDAY_QUOTE_STRESS_FAIL_CLOSED_NO_GO")
        self.assertEqual(obj["source_file_basename"],bad.name)
        self.assertEqual(obj["source_file_ordinal"],2)
        self.assertEqual(obj["original_complete_files_verified_before_failure"],1)
        self.assertEqual(obj["diagnostic_phase"],"VALIDATE_ORIGINAL_QUOTE")
        self.assertEqual(obj["diagnostic_reason_code"],
                         "THREE_CURRENCY_PAIRS_INVALID")
        self.assertFalse(obj["original_broker_quote_contents_exposed"])
        self.assertFalse(obj["new_virtual_positions_permitted"])
        self.assertFalse(obj["new_paid_ai_calls_permitted"])
        self.assertFalse(obj["real_orders_permitted"])
        self.assertFalse((self.root/"not-to-be-created.json").exists())
        # Source remained unmodified and was not quarantined/deleted.
        self.assertTrue(bad.exists())
        self.assertIn("GBPJPY",bad.read_text("utf-8"))
        self.assertNotIn("GBPJPY",json.dumps(obj))

    def test_invalid_filename_rejects_entire_set_safely(self):
        quote(self.folder,self.now)
        quote(self.folder,self.now+timedelta(minutes=1))
        (self.folder/"FxPaperQuote_bad.csv").write_text("invalid")
        rc,obj=self._call()
        self.assertEqual(rc,2)
        self.assertEqual(obj["diagnostic_reason_code"],
                         "MULTIDAY_UNEXPECTED_QUOTE_SOURCE")
        self.assertFalse(obj["new_virtual_positions_permitted"])

    def test_success_outputs_not_auto_go(self):
        quote(self.folder,self.now)
        quote(self.folder,self.now+timedelta(minutes=1))
        rc,obj=self._call()
        self.assertEqual(rc,0)
        self.assertEqual(obj["status"],
                         "MULTIDAY_REAL_QUOTE_STRESS_RESEARCH_HOLD_NO_GO")
        self.assertFalse(obj["new_virtual_positions_permitted"])
        self.assertTrue((self.root/"not-to-be-created.json").exists())

    def test_windows_wrapper_audits_official_archive_even_after_bad_quote(self):
        ps=(Path(__file__).resolve().parents[1]/
            "scripts/final_paper_multiday_macro_integrity_once.ps1").read_text(
                encoding="utf-8")
        first=ps.index("final_paper_multiday_quote_stress")
        second=ps.index("final_paper_official_archive_integrity")
        gate=ps.index("if ($marketExit -ne 0 -or $archiveExit -ne 0)")
        self.assertLess(first,second)
        self.assertLess(second,gate)
        self.assertIn("$marketExit = $LASTEXITCODE",ps)
        self.assertIn("$archiveExit = $LASTEXITCODE",ps)
        for forbidden in ("Remove-Item","Start-Process","Stop-Process",
                          "Rename-Item","OrderSend","AllowPaidAi"):
            self.assertNotIn(forbidden,ps)


if __name__=="__main__":
    unittest.main()
