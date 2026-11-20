"""Read-only unexpected supervisor stop triage and stale warning regression."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_supervisor_incident as incident
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 20, 2, 30, tzinfo=timezone.utc)
JOURNAL = 1795004931
MT4 = 1795141796
HEAD = "a" * 64


def state():
    return {
        "cycle_number": 550,
        "communication_latched": True,
        "dd4_latched": False, "dd5_latched": False,
        "daily_loss_latched": False,
        "positions": [], "pending_signals": [],
        "paid_inference_calls": 6,
    }


def stream_report():
    return {
        "diagnosis": "FRESH_MT4_QUOTES_NOT_PROCESSED_BY_PYTHON",
        "journal_cycles": 550,
        "last_processed_quote_epoch_pc_unattested": JOURNAL,
        "latest_raw_quote_epoch_pc_unattested": MT4,
        "latest_raw_quote_age_seconds_pc_derived": 41,
    }


class IncidentTriageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "state"
        self.root.mkdir()
        self.mt4 = Path(self.tmp.name) / "MQL4" / "Files"
        self.mt4.mkdir()
        self.lock = self.root / ".single_operator.lock"
        self.lock.write_text(
            "running; review journal on unexpected stop\n", "utf-8")

    def _review(self, head_after=HEAD):
        with patch.object(incident.runtime, "_journal_load",
                          side_effect=[(state(), HEAD), (state(), head_after)]), \
             patch.object(incident.stream, "diagnose",
                          return_value=stream_report()), \
             patch.object(incident.ai_audit, "audit", return_value={
                 "journal_cycles": 550,
                 "journal_head_sha256_local_only": HEAD,
                 "paid_calls_recorded_in_journal": 6,
                 "paid_calls_in_completed_ledgers": 6,
             }):
            return incident.investigate(self.root, self.mt4, now=NOW)

    def test_20261120_broker_fresh_python_stale_and_lock(self):
        item = self._review()
        self.assertEqual(item["journal_cycles"], 550)
        self.assertEqual(item["unconsumed_quote_gap_seconds_pc_derived"],
                         MT4 - JOURNAL)
        self.assertTrue(item["new_interruption_longer_than_600_seconds"])
        self.assertTrue(item["runtime_lock_exists"])
        self.assertEqual(item["runtime_lock_sha256_local_only"],
                         hashlib.sha256(self.lock.read_bytes()).hexdigest())
        self.assertTrue(item["journal_communication_latched"])
        self.assertEqual(item["paid_calls_journal"], 6)
        self.assertFalse(
            item["old_20261118_comm_release_approval_covers_this_gap"])
        for key in ("lock_is_proven_orphan",
                    "root_cause_of_python_exit_proven",
                    "lock_file_removed_or_renamed", "supervisor_restarted",
                    "communication_latch_released",
                    "new_virtual_positions_permitted",
                    "new_paid_ai_calls_permitted", "demo_orders_permitted",
                    "real_orders_permitted"):
            self.assertFalse(item[key])
        self.assertTrue(self.lock.exists())

    def test_racing_journal_heads_refused(self):
        with self.assertRaises(InputError):
            self._review(head_after="b" * 64)

    def test_reject_symlink_or_large_lock(self):
        self.lock.write_bytes(b"x" * 5000)
        with self.assertRaises(InputError):
            self._review()

    def test_no_lock_is_not_permission_to_start(self):
        self.lock.unlink()
        item = self._review()
        self.assertFalse(item["runtime_lock_exists"])
        self.assertFalse(item["supervisor_restarted"])
        self.assertFalse(item["new_virtual_positions_permitted"])

    def test_windows_wrapper_prohibits_manual_lock_bypass(self):
        base = Path(__file__).resolve().parents[1]
        wrapper = (base / "scripts/final_paper_supervisor_incident_once.ps1"
                   ).read_text("utf-8")
        self.assertIn("Get-CimInstance Win32_Process", wrapper)
        self.assertIn("POSSIBLE_ORPHAN_LOCK", wrapper)
        for illegal in ("Stop-Process", "Start-Process", "Remove-Item",
                        "Rename-Item", "OrderSend", "Invoke-WebRequest"):
            self.assertNotIn(illegal, wrapper)
        other = (base / "scripts/final_paper_collect_external_evidence_once.ps1"
                 ).read_text("utf-8")
        self.assertNotIn("A child command set a nonzero exit", other)


if __name__ == "__main__":
    unittest.main()
