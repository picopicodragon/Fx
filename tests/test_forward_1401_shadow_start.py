"""FWD-1401..1440: actionable shadow-forward start/step/status regressions."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research import forward_shadow_start as shadow
from research import forward_evidence_runbook as runbook
from research.forward_mt4_v2_quote import COLUMNS
from research.offline_backtest import InputError

ASOF = "2026-11-10T09:00:00Z"
TEMPLATE = datetime(2026, 11, 10, 6, 0, 0, tzinfo=timezone.utc)
PAIRS = {"USDJPY":"USD/JPY","EURJPY":"EUR/JPY","EURUSD":"EUR/USD"}


def make_session(parent: Path, label: str, base: int, count: int,
                 missing: str | None = None) -> Path:
    directory = parent/label
    directory.mkdir()
    for step in range(count):
        at = TEMPLATE + timedelta(minutes=base+step)
        name=at.strftime("%Y%m%d_%H%M%S")
        iso=at.strftime("%Y-%m-%dT%H:%M:%SZ")
        for symbol, pair in PAIRS.items():
            if symbol == missing:
                continue
            row = [iso, pair,"150.000","150.005",
                   "150.00000" if pair=="EUR/USD" else "1.00000",
                   "2026-11-10T08:00:00","2026-11-10T08:00:05",
                   "5", "DEMO", "MANUAL_MT4_DEMO_V2_UNVERIFIED"]
            (directory/("FxFwdV3_"+symbol+"_"+name+".csv")).write_text(
                ",".join(COLUMNS)+"\n"+",".join(row)+"\n", encoding="utf-8")
    return directory


def cmd(*args):
    with patch("sys.stdout", new_callable=io.StringIO) as stream:
        rc = shadow.main(list(args))
    return rc,json.loads(stream.getvalue())


class ForwardCampaignStartTests(unittest.TestCase):
    def test_start_registers_existing_real_copied_sessions_as_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"first",0,6)
            b=make_session(root,"second",15,24)
            target=root/"ledger"
            code,res=cmd("--mode","start","--state-dir",str(target),
                         "--session","s1="+str(a),
                         "--session","s2="+str(b),"--asof-utc",ASOF)
            self.assertEqual(code,0)
            self.assertTrue(res["status"].startswith("SHADOW_FORWARD_STARTED_"))
            self.assertEqual(res["session_count"],2)
            self.assertEqual(res["complete_cycles"],30)
            self.assertEqual(res["registered_macro_events"],0)
            self.assertEqual(res["registered_review_count"],0)
            self.assertEqual(res["orders_sent_this_run"],0)
            self.assertFalse(res["demo_orders_permitted"])
            self.assertFalse(res["real_orders_permitted"])
            rows=shadow._load(target)
            self.assertEqual(len(rows),1)
            record=rows[0]["record"]
            self.assertEqual(record["incomplete_cycles_all_sessions"],0)
            self.assertEqual(set(record["per_pair_shadow_decision_gate"]),set(PAIRS.values()))
            self.assertTrue(all(
                row["direction"]=="NO_SIGNAL" and
                row["simulated_fill_generated"] is False
                for row in record["per_pair_shadow_decision_gate"].values()))
            self.assertTrue(record["future_macro_calendar_and_consensus_incomplete"])
            self.assertFalse(record["actual_AI_inference_performed"])

    def test_state_creation_does_not_modify_csv_originals(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"first",0,1)
            originals={p.name:p.read_bytes() for p in a.iterdir()}
            target=root/"new_state"
            rc,_=cmd("--mode","start","--state-dir",str(target),
                     "--session","s1="+str(a),"--asof-utc",ASOF)
            self.assertEqual(rc,0)
            self.assertEqual(originals,{p.name:p.read_bytes() for p in a.iterdir()})
            self.assertEqual([p.name for p in target.iterdir()],["00000001.json"])

    def test_step_requires_new_session_and_rechecks_all_old_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"first",0,2)
            b=make_session(root,"second",10,2)
            folder=root/"history"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--session","first="+str(a),
                                 "--asof-utc",ASOF)[0],0)
            code,result=cmd("--mode","step","--state-dir",str(folder),
                            "--session","second="+str(b),
                            "--asof-utc",ASOF)
            self.assertEqual(code,0)
            self.assertEqual(result["session_count"],2)
            self.assertEqual(result["new_session_count"],1)
            self.assertEqual(result["complete_cycles"],4)
            rows=shadow._load(folder)
            self.assertEqual(rows[1]["prev_record_sha256"],rows[0]["record_sha256"])
            self.assertTrue(rows[1]["record"]["old_sessions_rechecked_sha256_each_step"])
            self.assertFalse(rows[1]["record"]["real_orders_permitted"])

    def test_missing_new_session_fails_closed_no_unrelated_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,2); folder=root/"history"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--session","s1="+str(a),
                                 "--asof-utc",ASOF)[0],0)
            rc,r=cmd("--mode","step","--state-dir",str(folder),
                     "--asof-utc",ASOF)
            self.assertEqual(rc,2)
            self.assertEqual(r["status"],"SHADOW_FORWARD_FAIL_CLOSED_NO_GO")
            self.assertEqual(len(list(folder.iterdir())),1)

    def test_tampered_historical_csv_causes_step_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,2)
            b=make_session(root,"two",10,2); folder=root/"history"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--session","s1="+str(a),
                                 "--asof-utc",ASOF)[0],0)
            orig=next(a.iterdir()); orig.write_text(orig.read_text()+" ")
            rc,r=cmd("--mode","step","--state-dir",str(folder),
                     "--session","s2="+str(b),"--asof-utc",ASOF)
            self.assertEqual(rc,2)
            self.assertFalse(r["real_orders_permitted"])
            self.assertEqual(len(list(folder.iterdir())),1)

    def test_tampered_ledger_record_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,1); folder=root/"history"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--session","s1="+str(a),
                                 "--asof-utc",ASOF)[0],0)
            p=folder/"00000001.json"; doc=json.loads(p.read_text())
            doc["record"]["demo_orders_permitted"]=True
            p.write_text(json.dumps(doc))
            rc,r=cmd("--mode","status","--state-dir",str(folder))
            self.assertEqual(rc,2)
            self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_status_is_read_only_and_warns_originals_not_rechecked(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,1); folder=root/"history"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--session","s1="+str(a),
                                 "--asof-utc",ASOF)[0],0)
            before=(folder/"00000001.json").read_bytes()
            rc,res=cmd("--mode","status","--state-dir",str(folder))
            self.assertEqual(rc,0)
            self.assertEqual(res["registered_record_count"],1)
            self.assertFalse(res["source_rechecked_in_this_status_call"])
            self.assertEqual(before,(folder/"00000001.json").read_bytes())
            self.assertFalse(res["demo_orders_permitted"])

    def test_second_start_cannot_overwrite_campaign(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,1); folder=root/"history"
            args=("--mode","start","--state-dir",str(folder),
                  "--session","s1="+str(a),"--asof-utc",ASOF)
            self.assertEqual(cmd(*args)[0],0)
            self.assertEqual(cmd(*args)[0],2)

    def test_partial_pair_never_creates_started_record(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,2,missing="EURUSD")
            folder=root/"ledger"
            rc,res=cmd("--mode","start","--state-dir",str(folder),
                       "--session","s1="+str(a),"--asof-utc",ASOF)
            self.assertEqual(rc,2)
            self.assertEqual(res["runtime_go_no_go"],"NO_GO")
            self.assertFalse(folder.exists())

    def test_no_evidence_does_not_start(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); folder=root/"ledger"
            rc,res=cmd("--mode","start","--state-dir",str(folder),
                       "--asof-utc",ASOF)
        self.assertEqual(rc,2)
        self.assertFalse(res["demo_orders_permitted"])

    def test_historical_old_baseline_not_claimed_live(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"old",0,1)
            result=shadow.inspect(
                mode="start",asof_utc="2026-11-15T09:00:00Z",
                new_sessions=["old="+str(a)])
        self.assertEqual(result["status"],
                         "SHADOW_FORWARD_BASELINE_ONLY_HOLD_NO_GO")
        self.assertFalse(result["new_observation_within_24h"])

    def test_reused_label_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,1)
            b=make_session(root,"two",10,1); folder=root/"state"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--session","s1="+str(a),"--asof-utc",ASOF)[0],0)
            rc,_=cmd("--mode","step","--state-dir",str(folder),
                     "--session","s1="+str(b),"--asof-utc",ASOF)
        self.assertEqual(rc,2)

    def test_old_timestamp_overlap_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,2)
            b=make_session(root,"two",1,2); folder=root/"state"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--session","s1="+str(a),"--asof-utc",ASOF)[0],0)
            rc,_=cmd("--mode","step","--state-dir",str(folder),
                     "--session","s2="+str(b),"--asof-utc",ASOF)
        self.assertEqual(rc,2)

    def test_state_folder_cannot_live_inside_csv_session(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,2)
            folder=a/"history"
            rc,_=cmd("--mode","start","--state-dir",str(folder),
                     "--session","s1="+str(a),"--asof-utc",ASOF)
            self.assertEqual(rc,2)
            self.assertFalse(folder.exists())

    def test_plan_file_with_known_sessions_is_supported(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,2)
            plan=runbook.empty_plan()
            plan["sessions"]=[{"label":"s1","directory":str(a),
                               "experts_log":None,"compile_log":None}]
            plan_path=root/"plan.json";plan_path.write_text(json.dumps(plan))
            folder=root/"state"
            rc,res=cmd("--mode","start","--state-dir",str(folder),
                       "--plan-file",str(plan_path),"--asof-utc",ASOF)
            self.assertEqual(rc,0)
            self.assertEqual(res["complete_cycles"],2)
            self.assertIsNotNone(shadow._load(folder)[0]["record"][
                "evidence_plan_sha256_local_only"])

    def test_extra_keys_in_runbook_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,1)
            plan=runbook.empty_plan()
            plan["sessions"]=[{"label":"s1","directory":str(a),
                               "experts_log":None,"compile_log":None}]
            plan["permission_to_order"]=True
            source=root/"plan.json";source.write_text(json.dumps(plan))
            folder=root/"ledger"
            self.assertEqual(cmd("--mode","start","--state-dir",str(folder),
                                 "--plan-file",str(source),
                                 "--asof-utc",ASOF)[0],2)

    def test_source_hash_is_deterministic_and_uses_named_files(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,2)
            first=shadow._session_manifest(a)
            second=shadow._session_manifest(a)
            self.assertEqual(first,second)
            self.assertEqual(first["file_count"],6)

    def test_initial_start_prohibits_any_real_ai_or_network(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); a=make_session(root,"one",0,1)
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("unexpected paid or web")):
                result=shadow.inspect(
                    mode="start",asof_utc=ASOF,
                    new_sessions=["one="+str(a)])
        self.assertFalse(result["actual_AI_inference_performed"])
        self.assertEqual(result["network_calls_this_run"],0)
        self.assertEqual(result["API_calls_this_run"],0)
        self.assertEqual(result["orders_sent_this_run"],0)


if __name__ == "__main__":
    unittest.main()
