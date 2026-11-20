"""One-off manual lock preservation for FREE observation, NO trades."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_manual_observation_recovery as mod
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 20, 2, 32, tzinfo=timezone.utc)
HEAD = "a" * 64


def current_state():
    return {
        "cycle_number": 550,
        "last_quote_epoch": mod.EXPECTED_LAST_QUOTE,
        "communication_latched": True,
        "daily_loss_latched": False,
        "dd4_latched": False,
        "dd5_latched": False,
        "positions": [],
        "pending_signals": [],
        "paid_inference_calls": 6,
    }


def forensic():
    return {
        "journal_cycles": 550,
        "last_consumed_quote_utc_pc_unattested":
            datetime.fromtimestamp(
                mod.EXPECTED_LAST_QUOTE, tz=timezone.utc).isoformat(),
        "journal_communication_latched": True,
        "runtime_lock_exists": True,
        "quote_stream_diagnosis": "FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON",
        "new_interruption_longer_than_600_seconds": True,
        "latest_raw_quote_age_seconds_pc_derived": 60,
        "virtual_open_position_count": 0,
        "pending_signal_count": 0,
        "other_risk_latches": {
            "daily_loss_latched": False,
            "dd4_latched": False,
            "dd5_latched": False,
        },
        "paid_calls_journal": 6,
        "paid_calls_completed_ledgers": 6,
        "journal_head_sha256_local_only": HEAD,
        "runtime_lock_sha256_local_only": mod.hashlib.sha256(
            mod.LOCK_BYTES).hexdigest(),
    }


class ManualFreeObservationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "state"
        self.root.mkdir()
        self.mt4 = Path(self.tmp.name) / "MQL4" / "Files"
        self.mt4.mkdir(parents=True)
        self.lock = self.root / ".single_operator.lock"
        self.lock.write_bytes(mod.LOCK_BYTES)

    def _recover(self, approval=mod.APPROVAL, absence=True, report=None):
        with patch.object(mod.incident, "investigate",
                          return_value=forensic() if report is None
                          else report), \
             patch.object(mod.runtime, "_journal_load",
                          return_value=(current_state(), HEAD)):
            return mod.recover(self.root, self.mt4,
                               operator_approval=approval,
                               windows_absence_checked=absence,
                               now=NOW)

    def test_explicit_manual_approval_and_windows_pid_attestation_required(self):
        with self.assertRaises(InputError):
            self._recover(approval="")
        with self.assertRaises(InputError):
            self._recover(absence=False)
        self.assertTrue(self.lock.exists())
        self.assertFalse((self.root / mod.RECEIPT_NAME).exists())

    def test_manual_lock_quarantined_original_bytes_preserved_no_trade(self):
        result = self._recover()
        self.assertEqual(result["status"],
                         "MANUAL_LOCK_ARCHIVED_OBSERVATION_RESTART_CANDIDATE_NO_GO")
        self.assertFalse(self.lock.exists())
        self.assertEqual((self.root / mod.ARCHIVE_NAME).read_bytes(),
                         mod.LOCK_BYTES)
        receipt=json.loads((self.root / mod.RECEIPT_NAME).read_text("utf-8"))
        self.assertTrue(receipt["communication_latched_unchanged"])
        self.assertFalse(receipt["new_38h_communication_gap_release_authorized"])
        self.assertFalse(result["new_virtual_entries_permitted"])
        self.assertFalse(result["new_paid_ai_calls_permitted"])
        self.assertFalse(result["supervisor_restarted"])
        with self.assertRaises(InputError):
            self._recover()  # one-use lock archive, no replay

    def test_incomplete_external_evidence_does_not_move_lock(self):
        for key, value in (
            ("journal_cycles", 551),
            ("virtual_open_position_count", 1),
            ("pending_signal_count", 1),
            ("paid_calls_journal", 7),
            ("latest_raw_quote_age_seconds_pc_derived", 400),
            ("new_interruption_longer_than_600_seconds", False),
            ("journal_communication_latched", False),
            ("quote_stream_diagnosis", "MT4_OBSERVER_QUOTE_STREAM_STALE"),
        ):
            with self.subTest(key=key):
                item=forensic()
                item[key]=value
                with self.assertRaises(InputError):
                    self._recover(report=item)
                self.assertTrue(self.lock.exists())
                self.assertFalse((self.root/mod.RECEIPT_NAME).exists())

    def test_old_comm_release_permit_blocks_new_incident(self):
        (self.root/"manual_comm_release_20261118.json").write_text("{}")
        with self.assertRaises(InputError):
            self._recover()
        self.assertTrue(self.lock.exists())

    def test_unexpected_lock_contents_rejected(self):
        self.lock.write_text("other operator\n")
        with self.assertRaises(InputError):
            self._recover()
        self.assertTrue(self.lock.exists())

    def test_windows_recovery_does_not_auto_launch_process(self):
        code=(Path(__file__).resolve().parents[1]/
              "scripts/final_paper_manual_observation_recovery_once.ps1"
              ).read_text("utf-8")
        self.assertIn("ApproveObservationOnlyRecovery", code)
        self.assertIn("Get-CimInstance Win32_Process", code)
        self.assertIn("final_paper_free_resume_preflight_once", code)
        for forbidden in ("Stop-Process", "Start-Process", "Remove-Item",
                          "Rename-Item", "OrderSend",
                          "Invoke-WebRequest", "AllowPaidAi"):
            self.assertNotIn(forbidden,code)


if __name__=="__main__":
    unittest.main()
