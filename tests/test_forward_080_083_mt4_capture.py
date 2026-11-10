"""FWD-080..083 offline timer evidence regression tests."""
import tempfile
import unittest
from pathlib import Path
from research.forward_mt4_v2_quote import COLUMNS
from research.forward_mt4_timer_capture_audit import inspect, main
from research.offline_backtest import InputError

ASOF="2026-11-10T06:10:00Z"
PAIRS={"USDJPY":"USD/JPY","EURJPY":"EUR/JPY","EURUSD":"EUR/USD"}


def add(directory, symbol, stamp, *, conversion=None, name=None):
    from datetime import datetime, timezone
    utc=datetime.strptime(stamp,"%Y%m%d_%H%M%S").replace(
        tzinfo=timezone.utc).isoformat().replace("+00:00","Z")
    if conversion is None:
        conversion="150.000" if symbol=="EURUSD" else "1"
    fields=[utc,PAIRS[symbol],"150.000","150.005",conversion,
            "2026-11-10T08:09:50","2026-11-10T08:10:00","10",
            "DEMO","MANUAL_MT4_DEMO_V2_UNVERIFIED"]
    name=name or f"FxFwdV3_{symbol}_{stamp}.csv"
    p=directory/name
    p.write_text(",".join(COLUMNS)+"\n"+",".join(fields)+"\n")
    return p


class DemoTimerCaptureAuditTests(unittest.TestCase):
    def test_two_complete_cycles_60_seconds(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for stamp in ("20261110_060000","20261110_060100"):
                for sym in PAIRS: add(root,sym,stamp)
            result=inspect(root,asof_utc=ASOF)
            self.assertEqual(result["complete_cycle_count"],2)
            self.assertEqual(result["cycle_intervals_seconds"],[60])
            self.assertEqual(result["incomplete_cycle_count"],0)
            self.assertFalse(result["real_orders_permitted"])
            self.assertFalse(result["captures_from_actual_mt4_verified"])

    def test_missing_eurusd_is_anomaly(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            add(root,"USDJPY","20261110_060000")
            add(root,"EURJPY","20261110_060000")
            report=inspect(root,asof_utc=ASOF)
            self.assertIn("INCOMPLETE_THREE_PAIR_CYCLE",
                          report["blocking_reasons"])

    def test_missing_timer_cycle_is_anomaly(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for stamp in ("20261110_060000","20261110_060300"):
                for sym in PAIRS:add(root,sym,stamp)
            report=inspect(root,asof_utc=ASOF)
            self.assertIn("CAPTURE_INTERVAL_NOT_60S",
                          report["blocking_reasons"])

    def test_same_usdjpy_rate_different_decimal_scale_not_mismatch(self):
        # Reproduce MQL4: USDJPY bid prints 3 digits, conversion prints 5.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for symbol in PAIRS:
                p=add(root,symbol,"20261110_060000",
                      conversion="157.94000" if symbol=="EURUSD" else None)
                if symbol=="USDJPY":
                    p.write_text(p.read_text().replace(
                        ",150.000,150.005,", ",157.940,157.945,"))
            result=inspect(root,asof_utc=ASOF)
            self.assertEqual(result["complete_cycle_count"],1)
            self.assertNotIn("EURUSD_USDJPY_CONVERSION_INCONSISTENT",
                             result["blocking_reasons"])
            self.assertFalse(result["real_orders_permitted"])

    def test_equal_with_leading_and_trailing_zeros_not_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for symbol in PAIRS:
                p=add(root,symbol,"20261110_060000",
                      conversion="150.00000" if symbol=="EURUSD" else None)
                if symbol=="USDJPY":
                    p.write_text(p.read_text().replace(
                        ",150.000,150.005,", ",150.000,150.005,"))
            result=inspect(root,asof_utc=ASOF)
            self.assertNotIn("EURUSD_USDJPY_CONVERSION_INCONSISTENT",
                             result["blocking_reasons"])

    def test_actual_numeric_difference_still_detected_with_scale(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for symbol in PAIRS:
                p=add(root,symbol,"20261110_060000",
                      conversion="157.94100" if symbol=="EURUSD" else None)
                if symbol=="USDJPY":
                    p.write_text(p.read_text().replace(
                        ",150.000,150.005,", ",157.940,157.945,"))
            result=inspect(root,asof_utc=ASOF)
            self.assertIn("EURUSD_USDJPY_CONVERSION_INCONSISTENT",
                          result["blocking_reasons"])

    def test_bad_conversion_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for sym in PAIRS:
                add(root,sym,"20261110_060000",
                    conversion="149.999" if sym=="EURUSD" else None)
            report=inspect(root,asof_utc=ASOF)
            self.assertIn("EURUSD_USDJPY_CONVERSION_INCONSISTENT",
                          report["blocking_reasons"])

    def test_pair_name_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=add(root,"USDJPY","20261110_060000")
            p.write_text(p.read_text().replace("USD/JPY","EUR/JPY"))
            with self.assertRaises(InputError): inspect(root,asof_utc=ASOF)

    def test_future_dated_capture_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            add(root,"USDJPY","20261110_061100")
            with self.assertRaises(InputError): inspect(root,asof_utc=ASOF)

    def test_filename_time_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=add(root,"USDJPY","20261110_060000")
            p.write_text(p.read_text().replace("06:00:00Z","06:00:01Z"))
            with self.assertRaises(InputError): inspect(root,asof_utc=ASOF)

    def test_duplicate_csv_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=add(root,"USDJPY","20261110_060000")
            (root/"FxFwdV3_EURJPY_20261110_060000.csv").write_bytes(p.read_bytes())
            with self.assertRaises(InputError): inspect(root,asof_utc=ASOF)

    def test_unexpected_file_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            add(root,"USDJPY","20261110_060000")
            (root/"notes.txt").write_text("notes")
            with self.assertRaises(InputError):inspect(root,asof_utc=ASOF)

    def test_empty_directory_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(InputError):
                inspect(Path(folder),asof_utc=ASOF)

    def test_symlink_directory_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            link=root/"link"
            try:
                link.symlink_to(root,target_is_directory=True)
            except (OSError,NotImplementedError):
                self.skipTest("symlink permissions unavailable")
            with self.assertRaises(InputError):inspect(link,asof_utc=ASOF)

    def test_cli_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/"source";source.mkdir()
            add(source,"USDJPY","20261110_060000")
            out=root/"report.json"
            args=["--directory",str(source),"--asof-utc",ASOF,
                  "--out",str(out)]
            self.assertEqual(main(args),0)
            self.assertEqual(main(args),2)
            self.assertTrue(out.is_file())


if __name__=="__main__":
    unittest.main()
