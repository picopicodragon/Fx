"""FWD-1281..1360: write-once history registration and fullstack runbook."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_evidence_runbook as runbook
from research import forward_regional_history_register as registrar
from research import forward_regional_evidence_history as history
from research import forward_regional_source_intake as intake
from research.offline_backtest import InputError

ASOF = "2026-11-15T05:00:00Z"


def mk(root, name, *, observed="2026-11-13T03:00:00Z", currency="USD",
       event_id="demo-cpi", at="2026-11-20T15:00:00Z",
       title="Consumer Price Index"):
    folder = root / name
    folder.mkdir()
    raw = "Official saved schedule: "+title+" at "+at
    (folder / "calendar.txt").write_text(raw,encoding="utf-8")
    url = {
        "USD": "https://www.bls.gov/schedule/news_release/",
        "EUR": "https://www.ecb.europa.eu/press/",
        "JPY": "https://www.boj.or.jp/en/mopo/",
    }[currency]
    manifest = {
        "schema": intake.SCHEMA,
        "observed_at_utc": observed,
        "horizon_days": 14,
        "sources": [{
            "source_id": "official", "source_kind": "OFFICIAL_SCHEDULE",
            "filename": "calendar.txt", "source_url": url,
            "sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "published_at_utc": "2026-11-12T12:00:00Z",
            "captured_at_utc": "2026-11-13T02:00:00Z",
        }],
        "events": [{
            "event_id": event_id, "currency": currency,
            "event_type": "INFLATION", "title": title,
            "scheduled_at_utc": at, "calendar_source_id": "official",
            "calendar_excerpt": raw, "consensus": None,
        }],
    }
    p=folder/"original_manifest.json"
    p.write_text(json.dumps(manifest),encoding="utf-8")
    return p


def cmd(args):
    with patch("sys.stdout",new_callable=io.StringIO) as stream:
        rc=registrar.main(args)
    return rc,json.loads(stream.getvalue())


class RegistrationTests(unittest.TestCase):
    def test_register_two_regional_manifests_and_verify_history(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            originals=root/"raw"; originals.mkdir()
            a=mk(originals,"usd",currency="USD",event_id="usd-cpi")
            b=mk(originals,"eur",currency="EUR",event_id="eur-cpi")
            dest=root/"history.json"
            code,report=cmd([
                "--manifest",str(a),"--manifest",str(b),
                "--asof-utc",ASOF,"--out",str(dest)])
            self.assertEqual(code,0)
            self.assertEqual(report["registered_sources"],2)
            self.assertTrue(report["new_history_file_written_once"])
            self.assertEqual(report["read_only_recheck_snapshot_count"],2)
            self.assertFalse(report["registered_provenance_independently_authenticated"])
            history_raw=json.loads(dest.read_text())
            self.assertEqual(history_raw["schema"],history.SCHEMA)
            self.assertEqual(
                history_raw["entries"][0]["manifest_sha256"],
                hashlib.sha256(a.read_bytes()).hexdigest())
            self.assertEqual(
                history.inspect(dest,asof_utc=ASOF)[
                    "upcoming_event_count_by_currency_unattested"]["EUR"],1)
            self.assertEqual(report["runtime_go_no_go"],"NO_GO")
            self.assertFalse(report["real_orders_permitted"])

    def test_precheck_uses_no_file_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            original=root/"raw"; original.mkdir()
            a=mk(original,"usd")
            before=a.read_bytes()
            code,r=cmd(["--manifest",str(a),"--asof-utc",ASOF])
            self.assertEqual(code,0)
            self.assertEqual(r["files_written_this_run"],0)
            self.assertEqual(a.read_bytes(),before)
            self.assertEqual(r["network_calls_this_run"],0)
            self.assertFalse(r["demo_orders_permitted"])

    def test_second_registration_creates_new_history_without_overwriting_first(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            original=root/"raw"; original.mkdir()
            a=mk(original,"first",currency="USD",event_id="usd")
            b=mk(original,"second",currency="JPY",event_id="jpy",
                 observed="2026-11-14T03:00:00Z")
            old=root/"history1.json"; new=root/"history2.json"
            self.assertEqual(cmd([
                "--manifest",str(a),"--asof-utc",ASOF,
                "--out",str(old)])[0],0)
            old_before=old.read_bytes()
            code,report=cmd([
                "--previous-history",str(old),"--manifest",str(b),
                "--asof-utc",ASOF,"--out",str(new)])
            self.assertEqual(code,0)
            self.assertEqual(old.read_bytes(),old_before)
            self.assertTrue(report["prior_history_included"])
            self.assertEqual(report["read_only_recheck_snapshot_count"],2)
            self.assertEqual(history.inspect(new,asof_utc=ASOF)[
                "upcoming_event_count_by_currency_unattested"]["JPY"],1)

    def test_duplicate_sources_not_registered_twice(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            orig=root/"raw"; orig.mkdir()
            a=mk(orig,"usd")
            out=root/"new.json"
            code,res=cmd([
                "--manifest",str(a),"--manifest",str(a),
                "--asof-utc",ASOF,"--out",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertFalse(res["real_orders_permitted"])

    def test_old_history_original_tampered_is_not_re_registered(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            orig=root/"raw"; orig.mkdir()
            a=mk(orig,"usd")
            old=root/"old.json"
            self.assertEqual(cmd([
                "--manifest",str(a),"--asof-utc",ASOF,"--out",str(old)])[0],0)
            (a.parent/"calendar.txt").write_text("TAMPER")
            out=root/"new.json"
            code,res=cmd([
                "--previous-history",str(old),
                "--asof-utc",ASOF,"--out",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertTrue(res["safety_hold_latched"])

    def test_no_explicit_sources_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"unused.json"
            code,res=cmd(["--asof-utc",ASOF,"--out",str(out)])
        self.assertEqual(code,2)
        self.assertFalse(res["demo_orders_permitted"])

    def test_registration_does_not_overwrite_an_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"usd")
            out=root/"existing.json"; out.write_text("untouched")
            code,res=cmd([
                "--manifest",str(a),"--asof-utc",ASOF,"--out",str(out)])
            self.assertEqual(code,2)
            self.assertEqual(out.read_text(),"untouched")
            self.assertFalse(res["real_orders_permitted"])

    def test_registration_does_not_write_to_original_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"usd")
            out=a.parent/"history.json"
            code,res=cmd([
                "--manifest",str(a),"--asof-utc",ASOF,"--out",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertEqual(res["runtime_go_no_go"],"NO_GO")

    def test_reversed_capture_order_refused_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"old",observed="2026-11-13T03:00:00Z")
            b=mk(raw,"new",observed="2026-11-14T03:00:00Z")
            out=root/"history.json"
            code,res=cmd(["--manifest",str(b),"--manifest",str(a),
                         "--asof-utc",ASOF,"--out",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertFalse(res["real_orders_permitted"])

    def test_new_history_registration_rejects_future_capture(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"future",observed="2026-11-16T03:00:00Z")
            out=root/"history.json"
            code,r=cmd(["--manifest",str(a),"--asof-utc",ASOF,
                        "--out",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertEqual(r["status"],
                             "REGIONAL_HISTORY_REGISTRATION_FAIL_CLOSED_NO_GO")

    def test_a_synced_history_file_can_be_verified_in_runbook(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"usd")
            hist=root/"history.json"
            self.assertEqual(cmd([
                "--manifest",str(a),"--asof-utc",ASOF,
                "--out",str(hist)])[0],0)
            plan=runbook.empty_plan()
            plan["regional_history_file"]=str(hist)
            p=root/"plan.json"; p.write_text(json.dumps(plan))
            with patch("sys.stdout",new_callable=io.StringIO) as output:
                rc=runbook.main(["--plan-file",str(p),"--asof-utc",ASOF])
                result=json.loads(output.getvalue())
            self.assertEqual(rc,0)
            audit=result["regional_saved_history_readiness"]
            self.assertEqual(audit["registered_snapshot_count"],1)
            self.assertIn("NO_UPCOMING_EUR_EVENT_IN_SAVED_HISTORY",
                          audit["unresolved_holds"])
            self.assertTrue(result["regional_saved_history_missing"] is False)
            self.assertEqual(result["runtime_go_no_go"],"NO_GO")
            self.assertFalse(result["demo_orders_permitted"])
            self.assertEqual(result["orders_sent_this_run"],0)

    def test_old_plan_without_optional_fields_still_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data=runbook.empty_plan()
            for key in ("regional_history_file","regional_source_manifest",
                        "mt4_observer_source"):
                data.pop(key)
            p=root/"legacy.json"; p.write_text(json.dumps(data))
            result,_=runbook.read_plan(p)
        self.assertIsNone(result["regional_history_file"])
        self.assertIsNone(result["regional_source_manifest"])

    def test_mid_era_plan_without_history_key_still_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data=runbook.empty_plan()
            data.pop("regional_history_file")
            p=root/"prior.json"; p.write_text(json.dumps(data))
            result,_=runbook.read_plan(p)
        self.assertIsNone(result["regional_history_file"])

    def test_unknown_runbook_field_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data=runbook.empty_plan()
            data["auto_trading"]=True
            p=root/"invalid.json"; p.write_text(json.dumps(data))
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_runbook_bad_history_sha_causes_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"usd"); hist=root/"history.json"
            self.assertEqual(cmd([
                "--manifest",str(a),"--asof-utc",ASOF,
                "--out",str(hist)])[0],0)
            contents=json.loads(hist.read_text())
            contents["entries"][0]["manifest_sha256"]="f"*64
            hist.write_text(json.dumps(contents))
            plan=runbook.empty_plan(); plan["regional_history_file"]=str(hist)
            p=root/"plan.json"; p.write_text(json.dumps(plan))
            with patch("sys.stdout",new_callable=io.StringIO) as output:
                rc=runbook.main(["--plan-file",str(p),"--asof-utc",ASOF])
                result=json.loads(output.getvalue())
            self.assertEqual(rc,2)
            self.assertFalse(result["real_orders_permitted"])
            self.assertEqual(result["status"],"RUNBOOK_RESEARCH_FAIL_CLOSED_NO_GO")

    def test_runbook_init_with_history_file_path(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"usd"); hist=root/"history.json"
            self.assertEqual(cmd(["--manifest",str(a),"--asof-utc",ASOF,
                                 "--out",str(hist)])[0],0)
            plan=root/"plan.json"
            with patch("sys.stdout",new_callable=io.StringIO) as output:
                rc=runbook.main(["--init-plan",str(plan),
                                "--init-regional-history-file",str(hist)])
                response=json.loads(output.getvalue())
            self.assertEqual(rc,0)
            self.assertEqual(json.loads(plan.read_text())["regional_history_file"],
                             str(hist))
            self.assertEqual(response["runtime_go_no_go"],"NO_GO")

    def test_runbook_init_refuses_missing_history_path(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); plan=root/"new.json"
            with patch("sys.stdout",new_callable=io.StringIO) as output:
                rc=runbook.main(["--init-plan",str(plan),
                                "--init-regional-history-file",
                                str(root/"missing.json")])
            self.assertEqual(rc,2)
            self.assertFalse(plan.exists())

    def test_cli_readonly_register_never_accesses_network(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); raw=root/"raw"; raw.mkdir()
            a=mk(raw,"usd")
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("network unexpected")):
                rc,res=cmd(["--manifest",str(a),"--asof-utc",ASOF])
        self.assertEqual(rc,0)
        self.assertEqual(res["network_calls_this_run"],0)


if __name__ == "__main__":
    unittest.main()
