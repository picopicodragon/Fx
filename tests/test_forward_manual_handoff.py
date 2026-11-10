"""FWD-043..047 offline manual handoff, tampering and missing-pair checks."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from research.forward_manual_handoff import capture, verify_capture, main as handoff_cli
from research.forward_manual_three_pair import audit, main as three_pair_cli
from research.offline_backtest import InputError

STAMP = "2026-11-10T03:00:00Z"
HEADER = ("observed_at_utc,pair,bid,ask,quote_to_jpy,account_type,origin\n")
ORIGIN = "MANUAL_MT4_DEMO_EXPORT_UNVERIFIED"


def source(path, pair="USD/JPY", at=STAMP, account="DEMO"):
    row = f"{at},{pair},150.001,150.020,1,{account},{ORIGIN}\n"
    path.write_text(HEADER + row, encoding="utf-8")
    return path


class ManualHandoffTests(unittest.TestCase):
    def test_capture_preserves_original_and_hash(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv")
            before = src.read_bytes()
            destination = base / "capture001"
            out = capture(src, destination, capture_id="c001", asof_utc=STAMP)
            self.assertEqual(src.read_bytes(), before)
            self.assertEqual((destination / "quote.csv").read_bytes(), before)
            self.assertEqual(out["csv_sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(verify_capture(destination)["pair"], "USD/JPY")
            self.assertFalse(out["real_orders_permitted"])
            self.assertFalse(out["journal_import_performed"])

    def test_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv")
            (base / "capture").mkdir()
            with self.assertRaises(InputError):
                capture(src, base / "capture", capture_id="c001", asof_utc=STAMP)

    def test_live_identity_rejected_and_destination_absent(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv", account="LIVE")
            dest = base / "capture"
            with self.assertRaises(InputError):
                capture(src, dest, capture_id="c001", asof_utc=STAMP)
            self.assertFalse(dest.exists())

    def test_stale_quote_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv", at="2026-11-10T02:45:00Z")
            with self.assertRaises(InputError):
                capture(src, base / "capture", capture_id="c001", asof_utc=STAMP)

    def test_future_quote_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv", at="2026-11-10T03:01:00Z")
            with self.assertRaises(InputError):
                capture(src, base / "capture", capture_id="c001", asof_utc=STAMP)

    def test_corrupted_copy_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv")
            dest = base / "capture"
            capture(src, dest, capture_id="c001", asof_utc=STAMP)
            (dest / "quote.csv").write_text("tampered")
            with self.assertRaises(InputError):
                verify_capture(dest)

    def test_corrupted_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv")
            dest = base / "capture"
            capture(src, dest, capture_id="c001", asof_utc=STAMP)
            receipt_path = dest / "receipt.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["real_orders_permitted"] = True
            receipt_path.write_text(json.dumps(receipt))
            with self.assertRaises(InputError):
                verify_capture(dest)

    def test_invalid_capture_id_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv")
            with self.assertRaises(InputError):
                capture(src, base / "capture", capture_id="../evil", asof_utc=STAMP)

    def test_no_overwrite_on_repeat_cli(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv")
            args = ["--source", str(src), "--out-dir", str(base / "c001"),
                    "--capture-id", "c001", "--asof-utc", STAMP]
            self.assertEqual(handoff_cli(args), 0)
            self.assertEqual(handoff_cli(args), 2)

    def test_zero_length_csv_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base / "raw.csv").write_bytes(b"")
            with self.assertRaises(InputError):
                capture(base / "raw.csv", base / "c001",
                        capture_id="c001", asof_utc=STAMP)

    def test_one_pair_reports_missing_two(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            src = source(base / "raw.csv")
            dest = base / "c001"
            capture(src, dest, capture_id="c001", asof_utc=STAMP)
            result = audit([dest], asof_utc=STAMP)
            self.assertEqual(result["capture_count"], 1)
            self.assertIn("MISSING_EUR_JPY", result["blocking_reasons"])
            self.assertIn("MISSING_EUR_USD", result["blocking_reasons"])
            self.assertFalse(result["real_orders_permitted"])

    def test_three_pair_captures_still_no_go(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            folders = []
            for i, pair in enumerate(("USD/JPY", "EUR/JPY", "EUR/USD"), 1):
                path = source(base / f"raw{i}.csv", pair=pair)
                dest = base / f"c{i:03d}"
                capture(path, dest, capture_id=f"c{i:03d}", asof_utc=STAMP)
                folders.append(dest)
            result = audit(folders, asof_utc=STAMP)
            self.assertEqual(result["capture_count"], 3)
            self.assertFalse(result["real_orders_permitted"])
            self.assertFalse(result["automatic_collection_started"])
            self.assertIn("QUOTE_SERVER_CLOCK_NOT_ATTESTED",
                          result["blocking_reasons"])

    def test_duplicate_pair_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            folders = []
            for i in (1, 2):
                dest = base / f"c{i}"
                capture(source(base / f"raw{i}.csv"), dest,
                        capture_id=f"c{i}", asof_utc=STAMP)
                folders.append(dest)
            with self.assertRaises(InputError):
                audit(folders, asof_utc=STAMP)

    def test_stale_relative_to_audit_is_held(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            dest = base / "c001"
            capture(source(base / "raw.csv"), dest,
                    capture_id="c001", asof_utc=STAMP)
            result = audit([dest], asof_utc="2026-11-10T03:02:00Z")
            self.assertIn("STALE_USD_JPY", result["blocking_reasons"])

    def test_unknown_capture_folder_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            dest = base / "result.json"
            rc = three_pair_cli(["--capture-dir", str(base / "nonexistent"),
                                 "--asof-utc", STAMP, "--out", str(dest)])
            self.assertEqual(rc, 2)
            self.assertFalse(dest.exists())

    def test_capture_file_is_not_a_trading_instruction(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            dest = base / "c001"
            data = capture(source(base / "raw.csv"), dest,
                           capture_id="c001", asof_utc=STAMP)
            for field in ("mt4_terminal_started_or_modified",
                          "journal_import_performed", "real_orders_permitted",
                          "demo_order_execution_enabled"):
                self.assertFalse(data[field])


if __name__ == "__main__":
    unittest.main()
