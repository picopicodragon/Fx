"""FWD-1361: real-source static review and copied CSV pilot integration tests."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research import forward_demo_pilot as pilot
from research import forward_evidence_runbook as runbook
from research.forward_mt4_v2_quote import COLUMNS
from research.offline_backtest import InputError

ASOF = "2026-11-10T09:00:00Z"
SYMBOLS = {"USDJPY": "USD/JPY", "EURJPY": "EUR/JPY", "EURUSD": "EUR/USD"}


def session(root: Path, name: str, minute: int, cycles: int, *,
            missing_symbol: str | None = None) -> Path:
    path = root / name
    path.mkdir()
    first = datetime(2026, 11, 10, 6, 0, 0, tzinfo=timezone.utc)
    for i in range(cycles):
        moment = first + timedelta(minutes=minute+i)
        suffix = moment.strftime("%Y%m%d_%H%M%S")
        observed = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        for symbol, pair in SYMBOLS.items():
            if symbol == missing_symbol:
                continue
            values = (
                observed, pair, "150.000", "150.005",
                "150.00000" if symbol == "EURUSD" else "1.00000",
                "2026-11-10T08:00:00", "2026-11-10T08:00:05",
                "5", "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED",
            )
            (path / f"FxFwdV3_{symbol}_{suffix}.csv").write_text(
                ",".join(COLUMNS) + "\n" + ",".join(values) + "\n",
                encoding="utf-8")
    return path


def cli(*args):
    with patch("sys.stdout", new_callable=io.StringIO) as stream:
        code = pilot.main(list(args))
    return code, json.loads(stream.getvalue())


class ForwardReadOnlyPilotTests(unittest.TestCase):
    def test_prepare_uses_committed_fixed_observer_only(self):
        result, audited, sources = pilot.inspect(
            mode="prepare", asof_utc=ASOF)
        self.assertIsNone(audited)
        self.assertEqual(sources, [])
        self.assertTrue(result["observer_static_preflight_passed"])
        self.assertEqual(result["observer_timer_interval_seconds_declared"],60)
        self.assertEqual(result["observer_maximum_timer_cycles_declared"],30)
        self.assertEqual(len(result["operator_manual_gate_statuses"]),9)
        self.assertTrue(all(x["verified_by_this_program"] is False
                            for x in result["operator_manual_gate_statuses"]))
        self.assertFalse(result["observer_metaeditor_compile_verified"])
        self.assertFalse(result["observer_ea_executed_by_this_program"])
        self.assertFalse(result["mt4_data_folder_accessed_by_this_program"])
        self.assertEqual(result["runtime_go_no_go"],"NO_GO")
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["demo_orders_permitted"])

    def test_prepare_does_not_create_files_without_out(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("network forbidden")):
                code, output=cli("--mode","prepare","--asof-utc",ASOF)
            self.assertEqual(list(root.iterdir()),[])
        self.assertEqual(code,0)
        self.assertEqual(output["network_calls_this_run"],0)
        self.assertEqual(output["API_calls_this_run"],0)
        self.assertEqual(output["orders_sent_this_run"],0)

    def test_write_once_prepare_report_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"preflight.json"
            rc,report=cli("--mode","prepare","--asof-utc",ASOF,
                          "--out",str(out))
            self.assertEqual(rc,0)
            body=json.loads(out.read_text())
            self.assertEqual(body["pilot_summary"]["status"],
                             "MT4_READONLY_PILOT_PREPARATION_NEEDS_OPERATOR_ACTION_NO_GO")
            self.assertIsNone(body["runbook_report_if_audited"])
            original=out.read_bytes()
            again,res=cli("--mode","prepare","--asof-utc",ASOF,
                          "--out",str(out))
            self.assertEqual(again,2)
            self.assertEqual(original,out.read_bytes())
            self.assertFalse(res["demo_orders_permitted"])

    def test_audit_two_complete_cycles_through_real_fullstack_runbook(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            copied=session(root,"copy",0,2)
            out=root/"report.json"
            code,summary=cli("--mode","audit","--asof-utc",ASOF,
                             "--session","first="+str(copied),
                             "--out",str(out))
            self.assertEqual(code,0)
            self.assertEqual(summary["copied_mt4_session_count"],1)
            self.assertEqual(summary["copied_quote_csv_count"],6)
            self.assertEqual(summary["complete_observation_cycle_count"],2)
            self.assertFalse(summary["operator_authorization_or_real_broker_safety_proven"])
            self.assertFalse(summary["research_observation_is_real_mt4_attestation"])
            self.assertFalse(summary["demo_forward_orders_authorized"])
            self.assertFalse(summary["real_forward_orders_authorized"])
            self.assertTrue(summary["no_go_cannot_be_cleared_by_report"])
            self.assertEqual(summary["runtime_go_no_go"],"NO_GO")
            self.assertTrue(summary["safety_hold_latched"])
            output=json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(output["runbook_report_if_audited"]["status"],
                             "RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO")
            self.assertEqual(output["runbook_report_if_audited"][
                "fullstack_report"]["mt4_copied_observation_session_count"],1)
            self.assertFalse(output["runbook_report_if_audited"][
                "real_orders_permitted"])

    def test_real_fullstack_audit_with_two_manually_copied_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=session(root,"copy1",0,2)
            b=session(root,"copy2",15,2)
            summary,audited,_=pilot.inspect(
                mode="audit",asof_utc=ASOF,
                sessions=["s1="+str(a),"s2="+str(b)])
        self.assertEqual(summary["copied_mt4_session_count"],2)
        self.assertEqual(summary["copied_quote_csv_count"],12)
        self.assertEqual(summary["complete_observation_cycle_count"],4)
        self.assertEqual(audited["fullstack_report"]["price_csv_count"],12)
        self.assertFalse(summary["real_orders_permitted"])

    def test_incomplete_cycle_remains_unverified_and_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            copied=session(root,"partial",0,2,missing_symbol="EURUSD")
            summary,report,_=pilot.inspect(
                mode="audit",asof_utc=ASOF,
                sessions=["incomplete="+str(copied)])
        self.assertEqual(summary["complete_observation_cycle_count"],0)
        self.assertTrue(summary["pending_holds_preview"])
        self.assertFalse(summary["demo_orders_permitted"])
        self.assertEqual(report["fullstack_report"]["runtime_go_no_go"],"NO_GO")

    def test_existing_plan_with_manually_copied_session_is_supported(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            copied=session(root,"copy",0,1)
            data=runbook.empty_plan()
            data["sessions"]=[{
                "label":"test","directory":str(copied),
                "experts_log":None,"compile_log":None}]
            p=root/"runbook.json"
            p.write_text(json.dumps(data))
            summary,report,_=pilot.inspect(
                mode="audit",asof_utc=ASOF,plan_file=p)
        self.assertEqual(summary["copied_quote_csv_count"],3)
        self.assertEqual(report["input_evidence_counts"]["mt4_sessions"],1)
        self.assertFalse(summary["demo_orders_permitted"])

    def test_audit_explicitly_refuses_plan_with_no_session(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=root/"plan.json"
            p.write_text(json.dumps(runbook.empty_plan()))
            with self.assertRaises(InputError):
                pilot.inspect(mode="audit",asof_utc=ASOF,plan_file=p)
            code,result=cli("--mode","audit","--asof-utc",ASOF,
                            "--plan-file",str(p))
        self.assertEqual(code,2)
        self.assertEqual(result["status"],"MT4_READONLY_PILOT_FAIL_CLOSED_NO_GO")

    def test_no_sessions_for_audit_fails_closed(self):
        code,result=cli("--mode","audit","--asof-utc",ASOF)
        self.assertEqual(code,2)
        self.assertFalse(result["real_orders_permitted"])

    def test_unresolved_manual_gate_stays_false_after_audit(self):
        with tempfile.TemporaryDirectory() as td:
            copied=session(Path(td),"s",0,1)
            result,_,_=pilot.inspect(
                mode="audit",asof_utc=ASOF,sessions=["s="+str(copied)])
        self.assertFalse(any(x["verified_by_this_program"]
                             for x in result["operator_manual_gate_statuses"]))

    def test_rejects_session_and_plan_together(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); p=root/"plan.json"; p.write_text(
                json.dumps(runbook.empty_plan()))
            copied=session(root,"copy",0,1)
            with self.assertRaises(InputError):
                pilot.inspect(mode="audit",asof_utc=ASOF,
                              sessions=["s="+str(copied)],plan_file=p)

    def test_prepare_rejects_session_or_plan_inputs(self):
        with self.assertRaises(InputError):
            pilot.inspect(mode="prepare",asof_utc=ASOF,
                          sessions=["a=not-a-real-dir"])

    def test_invalid_duplicate_session_label_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=session(root,"copy1",0,1)
            b=session(root,"copy2",10,1)
            with self.assertRaises(InputError):
                pilot.inspect(mode="audit",asof_utc=ASOF,
                              sessions=["dup="+str(a),"dup="+str(b)])

    def test_missing_session_folder_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(InputError):
                pilot.inspect(mode="audit",asof_utc=ASOF,
                              sessions=["missing="+str(Path(td)/"absent")])

    def test_bad_csv_content_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=session(root,"copy",0,1)
            (next(folder.iterdir())).write_text("BAD_CSV_CONTENT")
            code,result=cli("--mode","audit","--asof-utc",ASOF,
                            "--session","s="+str(folder))
        self.assertEqual(code,2)
        self.assertFalse(result["demo_orders_permitted"])
        self.assertTrue(result["safety_hold_latched"])

    def test_no_output_written_on_bad_csv(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=session(root,"copy",0,1)
            (next(folder.iterdir())).write_text("BAD_CSV_CONTENT")
            out=root/"report.json"
            code,_=cli("--mode","audit","--asof-utc",ASOF,
                       "--session","s="+str(folder),"--out",str(out))
            self.assertEqual(code,2)
            self.assertFalse(out.exists())

    def test_output_inside_copied_evidence_folder_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=session(root,"copy",0,1)
            before={p.name:p.read_bytes() for p in folder.iterdir()}
            code,_=cli("--mode","audit","--asof-utc",ASOF,
                       "--session","s="+str(folder),
                       "--out",str(folder/"pilot.json"))
            self.assertEqual(code,2)
            self.assertEqual({p.name:p.read_bytes() for p in folder.iterdir()},
                             before)

    def test_incorrect_utc_timestamp_fails_closed(self):
        code,result=cli("--mode","prepare",
                        "--asof-utc","2026-11-10T09:00:00+09:00")
        self.assertEqual(code,2)
        self.assertEqual(result["runtime_go_no_go"],"NO_GO")

    def test_static_audit_forged_success_flags_rejected(self):
        with patch.object(pilot.observer,"inspect", return_value={
            "status":"DEMO_TIMER_OBSERVER_STATIC_RESEARCH_NO_GO",
            "static_preflight_passed":True,
            "timer_seconds_declared":60,
            "maximum_timer_cycles_declared":30,
            "runtime_go_no_go":"GO",
            "safety_hold_latched":True,
            "demo_trading_allowed":False,
            "real_orders_permitted":False,
        }):
            with self.assertRaises(InputError):
                pilot.inspect(mode="prepare",asof_utc=ASOF)

    def test_tampered_static_observer_source_rejected(self):
        original=pilot.SOURCE
        with tempfile.TemporaryDirectory() as td:
            bad=Path(td)/"observer.mq4"
            bad.write_text("void OnTimer(){OrderSend();}")
            with patch.object(pilot,"SOURCE",bad):
                with self.assertRaises(InputError):
                    pilot.inspect(mode="prepare",asof_utc=ASOF)
        self.assertEqual(pilot.SOURCE,original)

    def test_no_network_even_with_real_csv_review(self):
        with tempfile.TemporaryDirectory() as td:
            copied=session(Path(td),"copy",0,1)
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("network forbidden")):
                result,_,_=pilot.inspect(
                    mode="audit",asof_utc=ASOF,
                    sessions=["s="+str(copied)])
        self.assertEqual(result["network_calls_this_run"],0)
        self.assertEqual(result["API_calls_this_run"],0)
        self.assertEqual(result["orders_sent_this_run"],0)

    def test_fullstack_forged_GO_is_rejected(self):
        fake = {
            "status":"RUNBOOK_RESEARCH_READINESS_HOLD_NO_GO",
            "runtime_go_no_go":"GO",
            "safety_hold_latched":True,
            "demo_orders_permitted":False,
            "real_orders_permitted":False,
            "orders_sent_this_run":0,
        }
        with tempfile.TemporaryDirectory() as td:
            copied=session(Path(td),"copy",0,1)
            with patch.object(pilot.runbook,"inspect",return_value=fake):
                with self.assertRaises(InputError):
                    pilot.inspect(mode="audit",asof_utc=ASOF,
                                  sessions=["s="+str(copied)])

    def test_forward_pilot_wrapper_contains_no_mt4_execution(self):
        script=Path(__file__).resolve().parents[1] / \
            "scripts/forward_demo_pilot_once.ps1"
        text=script.read_text(encoding="utf-8")
        self.assertIn("research.forward_demo_pilot",text)
        self.assertIn("LASTEXITCODE",text)
        for forbidden in ("Start-Process", "MetaEditor.exe",
                          "terminal.exe", "ExecutionPolicy Bypass",
                          "Invoke-WebRequest", "OrderSend(", "MQL4\\Experts\\"):
            self.assertNotIn(forbidden,text)


if __name__ == "__main__":
    unittest.main()
