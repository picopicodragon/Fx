"""FWD-085..094: offline DEMO timer evidence tests (no broker/MT4)."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research.forward_mt4_observation_evidence import (
    inspect, main, START_MARK, STOP_MARK, CSV_MARK, CHANGE_STOP
)
from research.offline_backtest import InputError
from tests.test_forward_080_083_mt4_capture import add, PAIRS, ASOF


def capture(root: Path, count: int, *, skip_symbol: str | None = None) -> Path:
    directory = root / "csv"
    directory.mkdir()
    base = datetime(2026, 11, 10, 6, 0, 0, tzinfo=timezone.utc)
    for i in range(count):
        stamp = (base + timedelta(minutes=i)).strftime("%Y%m%d_%H%M%S")
        for symbol in PAIRS:
            if symbol != skip_symbol:
                add(directory, symbol, stamp)
    return directory


class DemoObservationEvidenceTests(unittest.TestCase):
    def test_eight_cycles_24_files_manifest_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = capture(root, 8)
            a = inspect(directory, asof_utc=ASOF)
            b = inspect(directory, asof_utc=ASOF)
            self.assertEqual(a["csv_manifest"], b["csv_manifest"])
            self.assertEqual(len(a["csv_manifest"]), 24)
            self.assertEqual(a["capture_audit"]["complete_cycle_count"], 8)
            self.assertEqual(a["capture_audit"]["incomplete_cycle_count"], 0)
            self.assertIn("THIRTY_CYCLE_STOP_NOT_YET_OBSERVED",
                          a["observed_issues_and_safety_holds"])
            self.assertEqual(a["runtime_go_no_go"], "NO_GO")

    def test_real_manifest_hash_matches_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = capture(root, 1)
            result = inspect(directory, asof_utc=ASOF)
            for row in result["csv_manifest"]:
                self.assertEqual(row["sha256"],
                                 hashlib.sha256((directory / row["filename"]).read_bytes()).hexdigest())

    def test_missing_pairs_are_reported_not_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = capture(root, 2, skip_symbol="EURUSD")
            result = inspect(directory, asof_utc=ASOF)
            self.assertIn("PARTIAL_THREE_PAIR_CYCLES",
                          result["observed_issues_and_safety_holds"])

    def test_actual_log_errors_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = capture(root, 1)
            log = root / "expert.log"
            log.write_text(START_MARK+"\n"+CHANGE_STOP+"\n", encoding="utf-8")
            result = inspect(directory, asof_utc=ASOF, experts_log=log)
            self.assertEqual(result["observer_log"]["start_markers"], 1)
            self.assertEqual(result["observer_log"]["failure_markers"], 1)
            self.assertIn("OBSERVER_LOG_ERRORS_PRESENT",
                          result["observed_issues_and_safety_holds"])
            self.assertFalse(result["observer_log"]["source_independently_authenticated"])

    def test_no_observer_log_means_stop_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = capture(root, 1)
            result = inspect(directory, asof_utc=ASOF)
            self.assertIn("EXPERT_LOG_NOT_PROVIDED",
                          result["observed_issues_and_safety_holds"])
            self.assertFalse(result["continuous_30_cycle_stoppage_independently_verified"])

    def test_thirty_cycles_without_cap_log_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,30)
            result=inspect(directory,asof_utc=ASOF)
            self.assertIn("STOP_LOG_EVIDENCE_NOT_PROVIDED",
                          result["observed_issues_and_safety_holds"])

    def test_thirty_cycles_with_cap_log_remains_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,30)
            log=root/"expert.log"
            log.write_text(START_MARK+"\n"+CSV_MARK+"\n"+STOP_MARK+"\n")
            result=inspect(directory,asof_utc=ASOF, experts_log=log)
            self.assertEqual(result["stop_evidence_assessment"],
                             "SELF_REPORTED_CAP_MARKER_AND_30_CSV_CYCLES")
            self.assertFalse(result["continuous_30_cycle_stoppage_independently_verified"])
            self.assertEqual(result["runtime_go_no_go"],"NO_GO")

    def test_early_stop_marker_with_eight_cycles_is_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,8)
            log=root/"expert.log"
            log.write_text(STOP_MARK)
            report=inspect(directory,asof_utc=ASOF, experts_log=log)
            self.assertIn("CAP_STOP_MARKER_BUT_FEWER_THAN_30_CAPTURE_CYCLES",
                          report["observed_issues_and_safety_holds"])

    def test_multiple_start_markers_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,1)
            log=root/"expert.log"
            log.write_text(START_MARK+"\n"+START_MARK)
            report=inspect(directory,asof_utc=ASOF, experts_log=log)
            self.assertIn("MULTIPLE_SESSION_STARTS_IN_SUPPLIED_LOG",
                          report["observed_issues_and_safety_holds"])

    def test_compile_zero_warning_is_only_self_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,1)
            log=root/"compile.txt"
            log.write_text("0 errors, 0 warnings, 192 msec elapsed")
            report=inspect(directory,asof_utc=ASOF, compile_log=log)
            self.assertTrue(report["compile_report"]["self_reported_zero_errors_zero_warnings"])
            self.assertFalse(report["compile_report"]["independently_verified"])

    def test_bad_compile_report_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,1)
            log=root/"compile.txt"
            log.write_text("0 errors, 6 warnings")
            report=inspect(directory,asof_utc=ASOF, compile_log=log)
            self.assertIn("COMPILE_ZERO_WARNING_EVIDENCE_NOT_PRESENT",
                          report["observed_issues_and_safety_holds"])

    def test_binary_log_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,1)
            log=root/"expert.log"
            log.write_bytes(b"hello\x00world")
            with self.assertRaises(InputError):
                inspect(directory,asof_utc=ASOF, experts_log=log)

    def test_cli_never_overwrites_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            directory=capture(root,2)
            out=root/"report.json"
            args=["--directory",str(directory),"--asof-utc",ASOF,
                  "--out",str(out)]
            self.assertEqual(main(args),0)
            self.assertEqual(main(args),2)
            self.assertFalse(json.loads(out.read_text())["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
