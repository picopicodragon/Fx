"""FWD-521..552: multi-session MT4 observer evidence gates, DST and NO_GO."""
from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_mt4_long_run_review as mt4
from research.offline_backtest import InputError

ASOF = "2026-11-16T15:00:00Z"
SESSION = [("one", Path("out/demo-observations"))]


def source(*, second=False, good_log=False):
    rows = [{
        "label": "one",
        "first_observation_utc": "2026-11-13T21:59:00Z",
        "last_observation_utc": "2026-11-13T22:29:00Z",
        "complete_cycles": 30 if good_log else 12,
        "incomplete_cycles": 0,
        "stop_evidence_assessment": (
            "SELF_REPORTED_CAP_MARKER_AND_30_CSV_CYCLES"
            if good_log else "CAP_STOP_NOT_OBSERVED_IN_SUPPLIED_LOG"),
        "expert_log_supplied": good_log,
        "compile_log_supplied": good_log,
    }]
    if second:
        rows.append({
            "label": "two",
            "first_observation_utc": "2026-11-14T00:00:00Z",
            "last_observation_utc": "2026-11-14T00:30:00Z",
            "complete_cycles": 30,
            "incomplete_cycles": 0,
            "stop_evidence_assessment":
                "SELF_REPORTED_CAP_MARKER_AND_30_CSV_CYCLES",
            "expert_log_supplied": True,
            "compile_log_supplied": True,
        })
    return {
        "status": "MT4_MULTISESSION_RESEARCH_HOLD_NO_GO",
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
        "demo_orders_permitted": False,
        "sessions": rows,
        "issues_and_safety_holds": [
            "SOURCES_AND_BROKER_CLOCK_NOT_INDEPENDENTLY_ATTESTED"],
        "csv_file_count": 90*len(rows),
        "complete_cycle_count": sum(r["complete_cycles"] for r in rows),
        "incomplete_cycle_count": 0,
    }


class LongRunEvidenceTests(unittest.TestCase):
    def test_no_sessions_is_explicit_hold_without_mt4_access(self):
        with patch.object(mt4.reliability, "inspect") as call:
            r=mt4.inspect([],asof_utc=ASOF)
        call.assert_not_called()
        self.assertIn("NO_COPIED_MT4_OBSERVER_CSV_SESSIONS",
                      r["unresolved_holds"])
        self.assertEqual(r["verified_format_copied_session_count"],0)
        self.assertFalse(r["source_broker_or_demo_identity_independently_attested"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_single_session_cannot_qualify_longrun(self):
        with patch.object(mt4.reliability, "inspect",return_value=source()) as call:
            r=mt4.inspect(SESSION,asof_utc=ASOF)
        call.assert_called_once()
        self.assertEqual(r["csv_file_count"],90)
        self.assertEqual(r["complete_observation_cycle_count"],12)
        self.assertEqual(r["distinct_ny17_bucket_count"],1)
        self.assertIn("INSUFFICIENT_DISTINCT_MT4_OBSERVATION_SESSIONS",
                      r["unresolved_holds"])
        self.assertIn("MT4_OBSERVER_LOGS_OR_COMPILE_EVIDENCE_INCOMPLETE",
                      r["unresolved_holds"])
        self.assertFalse(r["orders_and_auto_trading_independently_proven_disabled"])

    def test_two_sessions_crossing_NY17_bucket_remain_unattested(self):
        s=source(second=True,good_log=True)
        with patch.object(mt4.reliability, "inspect",return_value=s):
            r=mt4.inspect(SESSION+[("two",Path("out/demo-two"))],
                          asof_utc=ASOF)
        self.assertEqual(r["distinct_ny17_bucket_count"],2)
        self.assertEqual(r["ny17_bucket_dates_observed_unattested"],
                         ["2026-11-13","2026-11-14"])
        self.assertTrue(r["all_sessions_have_self_reported_30cycle_stop_markers"])
        self.assertFalse(r["extended_live_mt4_connection_verified"])
        self.assertFalse(r["broker_clock_independently_verified"])
        self.assertFalse(r["real_orders_permitted"])

    def test_supplying_logs_without_sessions_must_fail_closed(self):
        with self.assertRaises(InputError):
            mt4.inspect([],asof_utc=ASOF,experts={"one":Path("log.txt")})

    def test_safety_escape_from_old_auditor_refused(self):
        r=source()
        r["demo_orders_permitted"]=True
        with patch.object(mt4.reliability, "inspect",return_value=r):
            with self.assertRaises(InputError):
                mt4.inspect(SESSION,asof_utc=ASOF)

    def test_broker_old_auditor_flags_are_rechecked(self):
        r=source()
        r["safety_hold_latched"]=False
        with patch.object(mt4.reliability, "inspect",return_value=r):
            with self.assertRaises(InputError):
                mt4.inspect(SESSION,asof_utc=ASOF)

    def test_ny17_boundary_jst_summer_and_winter(self):
        self.assertEqual(mt4._ny17_bucket("2026-07-01T20:59:00Z"),
                         "2026-07-01")
        self.assertEqual(mt4._ny17_bucket("2026-07-01T21:00:00Z"),
                         "2026-07-02")
        self.assertEqual(mt4._ny17_bucket("2026-11-13T21:59:00Z"),
                         "2026-11-13")
        self.assertEqual(mt4._ny17_bucket("2026-11-13T22:00:00Z"),
                         "2026-11-14")

    def test_thirty_cycle_cap_self_report_is_not_trading_permission(self):
        r=source(good_log=True)
        with patch.object(mt4.reliability, "inspect",return_value=r):
            report=mt4.inspect(SESSION,asof_utc=ASOF)
        self.assertTrue(report["all_sessions_have_self_reported_30cycle_stop_markers"])
        self.assertIn("MT4_AUTOTRADING_OFF_AND_ORDER_PATH_NOT_INDEPENDENTLY_VERIFIED",
                      report["unresolved_holds"])
        self.assertEqual(report["network_calls_this_run"],0)
        self.assertEqual(report["orders_sent_this_run"],0)

    def test_25_folders_rejected_before_file_io(self):
        many=[("x"+str(i),Path("out/"+str(i))) for i in range(25)]
        with patch.object(mt4.reliability, "inspect") as mock:
            with self.assertRaises(InputError):
                mt4.inspect(many,asof_utc=ASOF)
        mock.assert_not_called()

    def test_cli_no_sessions_returns_holds(self):
        with patch("sys.stdout",new_callable=io.StringIO) as output:
            status=mt4.main(["--asof-utc",ASOF])
        self.assertEqual(status,0)
        r=json.loads(output.getvalue())
        self.assertEqual(r["network_calls_this_run"],0)
        self.assertEqual(r["files_written_this_run"],0)
        self.assertFalse(r["real_orders_permitted"])

    def test_cli_bad_source_rejected_without_mt4_access(self):
        with patch("sys.stdout",new_callable=io.StringIO) as output:
            status=mt4.main(["--asof-utc",ASOF,
                             "--session","bad*name=C:/file"])
        self.assertEqual(status,2)
        r=json.loads(output.getvalue())
        self.assertEqual(r["status"],
                         "MT4_MULTIDAY_OBSERVATION_FAIL_CLOSED_NO_GO")
        self.assertTrue(r["safety_hold_latched"])


if __name__ == "__main__":
    unittest.main()
