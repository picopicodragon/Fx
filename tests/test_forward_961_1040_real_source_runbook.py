"""FWD-961..1040: source originals + existing evidence runbook compatibility."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_evidence_runbook as runbook
from research import forward_regional_source_intake as regional
from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

ASOF="2026-11-13T04:00:00Z"
ORIGINAL="BLS saved calendar Consumer Price Index at 2026-11-20 10:00 ET"


def create_sources(root: Path) -> Path:
    original=root/"calendar.txt"
    original.write_text(ORIGINAL,encoding="utf-8")
    manifest=root/"regional.json"
    content={
        "schema": regional.SCHEMA,
        "observed_at_utc": "2026-11-13T03:00:00Z",
        "horizon_days": 14,
        "sources": [{
            "source_id": "bls_calendar",
            "source_kind": "OFFICIAL_SCHEDULE",
            "filename": "calendar.txt",
            "source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
            "sha256": hashlib.sha256(ORIGINAL.encode()).hexdigest(),
            "published_at_utc": "2026-11-12T12:00:00Z",
            "captured_at_utc": "2026-11-13T02:00:00Z",
        }],
        "events": [{
            "event_id": "official-cpi-test",
            "currency": "USD",
            "event_type": "INFLATION",
            "title": "Consumer Price Index",
            "scheduled_at_utc": "2026-11-20T15:00:00Z",
            "calendar_source_id": "bls_calendar",
            "calendar_excerpt": ORIGINAL,
            "consensus": None,
        }],
    }
    manifest.write_text(json.dumps(content),encoding="utf-8")
    return manifest


def plan(root:Path, *,regional_manifest=None,mt4_source=None,store=None,legacy=False):
    data=runbook.empty_plan()
    if regional_manifest is not None:
        data["regional_source_manifest"]=str(regional_manifest)
    if mt4_source is not None:
        data["mt4_observer_source"]=str(mt4_source)
    if store is not None:
        data["observation_store"]=str(store)
    if legacy:
        data.pop("regional_source_manifest")
        data.pop("mt4_observer_source")
    path=root/"plan.json"
    path.write_text(json.dumps(data),encoding="utf-8")
    return path


class RunbookRealEvidenceTests(unittest.TestCase):
    def test_legacy_evidence_plan_remains_readable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=plan(root,legacy=True)
            decoded,digest=runbook.read_plan(p)
        self.assertIsNone(decoded["regional_source_manifest"])
        self.assertIsNone(decoded["mt4_observer_source"])
        self.assertEqual(len(digest),64)

    def test_empty_new_plan_has_optional_source_keys(self):
        data=runbook.empty_plan()
        self.assertIn("regional_source_manifest",data)
        self.assertIn("mt4_observer_source",data)
        self.assertIsNone(data["regional_source_manifest"])
        self.assertIsNone(data["mt4_observer_source"])

    def test_actual_regional_saved_file_passes_through_macro_hub(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            origin=root/"orig"
            origin.mkdir()
            manifest=create_sources(origin)
            p=plan(root,regional_manifest=manifest)
            decoded,sha=runbook.read_plan(p)
            report=runbook.inspect(decoded,asof_utc=ASOF,plan_sha256=sha)
        r=report["regional_original_source_intake"]
        self.assertEqual(r["source_file_count"],1)
        self.assertEqual(r["event_observations_count"],1)
        self.assertEqual(r["missing_pre_release_consensus_count"],1)
        self.assertEqual(report["fullstack_report"][
            "external_macro_event_observations"],1)
        self.assertEqual(report["fullstack_report"][
            "external_macro_by_currency"]["USD"],1)
        self.assertFalse(report["operational_acceptance_debt"][
            "owner_signoff_supplied_or_inferred"])
        self.assertFalse(report["real_orders_permitted"])
        self.assertFalse(report["demo_orders_permitted"])
        self.assertTrue(report["safety_hold_latched"])

    def test_missing_macro_source_manifest_maintains_research_hold(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=plan(root)
            decoded,sha=runbook.read_plan(p)
            report=runbook.inspect(decoded,asof_utc=ASOF,plan_sha256=sha)
        self.assertIsNone(report["regional_original_source_intake"])
        self.assertIn("NO_RAW_REGIONAL_ORIGINAL_SOURCES",
                      report["additional_real_evidence_holds"])
        self.assertEqual(report["runtime_go_no_go"],"NO_GO")

    def test_fake_observer_source_does_not_infer_runtime_safety(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            mq=root/"observer.mq4"
            mq.write_text("void OnTick(){ OrderSend(...); }")
            p=plan(root,mt4_source=mq)
            decoded,sha=runbook.read_plan(p)
            r=runbook.inspect(decoded,asof_utc=ASOF,plan_sha256=sha)
        s=r["mt4_observer_source_static_review"]
        self.assertFalse(s["static_preflight_passed"])
        self.assertIn("PROHIBITED_OrderSend",s["static_failures"])
        self.assertFalse(s["demo_trading_allowed"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertIn("MT4_OBSERVER_STATIC_PREFLIGHT_FAILED_OR_MISSING",
                      r["additional_real_evidence_holds"])

    def test_legacy_only_external_macro_file_works(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            raw=root/"external.json"
            content={"schema":macro.SCHEMA,
                     "observed_at_utc":"2026-11-13T03:00:00Z",
                     "horizon_days":14,"events":[]}
            raw.write_text(json.dumps(content))
            p=plan(root,legacy=True)
            data=json.loads(p.read_text())
            data["external_macro_file"]=str(raw)
            p.write_text(json.dumps(data))
            decoded,sha=runbook.read_plan(p)
            r=runbook.inspect(decoded,asof_utc=ASOF,plan_sha256=sha)
        self.assertEqual(r["fullstack_report"][
            "external_macro_event_observations"],0)
        self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_cannot_supply_both_external_and_original_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            origin=root/"orig"
            origin.mkdir()
            manifest=create_sources(origin)
            other=root/"external.json"
            other.write_text("{}")
            p=plan(root,regional_manifest=manifest)
            data=json.loads(p.read_text())
            data["external_macro_file"]=str(other)
            p.write_text(json.dumps(data))
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_journal_store_must_be_directory_not_file(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            store=root/"journal"
            store.mkdir()
            p=plan(root,store=store)
            decoded,_=runbook.read_plan(p)
            self.assertEqual(decoded["observation_store"],store)
            store.rmdir()
            store.write_text("not a directory")
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_init_plan_can_reference_existing_regional_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            origin=root/"orig"
            origin.mkdir()
            manifest=create_sources(origin)
            p=root/"initial.json"
            with patch("sys.stdout",new_callable=io.StringIO) as out:
                code=runbook.main([
                    "--init-plan",str(p),
                    "--init-regional-source-manifest",str(manifest)])
            self.assertEqual(code,0)
            data=json.loads(p.read_text())
            self.assertEqual(Path(data["regional_source_manifest"]),manifest)
            self.assertEqual(json.loads(out.getvalue())[
                "runtime_go_no_go"],"NO_GO")
            self.assertEqual((origin/"calendar.txt").read_text(), ORIGINAL)

    def test_init_plan_with_missing_source_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=root/"plan.json"
            with patch("sys.stdout",new_callable=io.StringIO) as out:
                code=runbook.main([
                    "--init-plan",str(p),
                    "--init-regional-source-manifest",str(root/"missing")])
            self.assertEqual(code,2)
            self.assertFalse(p.exists())
            self.assertEqual(json.loads(out.getvalue())[
                "status"],"RUNBOOK_RESEARCH_FAIL_CLOSED_NO_GO")

    def test_existing_observation_store_file_from_invalid_plan_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            f=root/"store.json"
            f.write_text("{}")
            p=plan(root,store=f)
            with self.assertRaises(InputError):
                runbook.read_plan(p)

    def test_init_mt4_static_source_with_banned_order_call_still_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            mq=root/"mt4_observer.mq4"
            mq.write_text("void OnTimer(){ OrderSend(...); }")
            p=root/"runbook.json"
            with patch("sys.stdout",new_callable=io.StringIO) as out:
                status=runbook.main([
                    "--init-plan",str(p),
                    "--init-mt4-observer-source",str(mq)])
            self.assertEqual(status,0)
            data=json.loads(p.read_text())
            self.assertEqual(Path(data["mt4_observer_source"]),mq)
            self.assertEqual(json.loads(out.getvalue())[
                "runtime_go_no_go"],"NO_GO")
            self.assertEqual(mq.read_text(),"void OnTimer(){ OrderSend(...); }")

    def test_with_regional_originals_runbook_cli_does_not_write_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            origin=root/"orig"
            origin.mkdir()
            manifest=create_sources(origin)
            p=plan(root,regional_manifest=manifest)
            original=manifest.read_bytes()
            with patch("sys.stdout",new_callable=io.StringIO) as out:
                code=runbook.main(["--plan-file",str(p),"--asof-utc",ASOF])
            self.assertEqual(code,0)
            self.assertEqual(manifest.read_bytes(),original)
            report=json.loads(out.getvalue())
            self.assertEqual(report["network_calls_this_run"],0)
            self.assertEqual(report["orders_sent_this_run"],0)
            self.assertEqual(report["runtime_go_no_go"],"NO_GO")

    def test_corrupt_original_prevents_runbook_output(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            origin=root/"orig"
            origin.mkdir()
            manifest=create_sources(origin)
            p=plan(root,regional_manifest=manifest)
            (origin/"calendar.txt").write_text("tampered")
            out=root/"report.json"
            with patch("sys.stdout",new_callable=io.StringIO) as output:
                status=runbook.main([
                    "--plan-file",str(p),"--asof-utc",ASOF,
                    "--out",str(out)])
            self.assertEqual(status,2)
            self.assertFalse(out.exists())
            self.assertFalse(json.loads(output.getvalue())[
                "real_orders_permitted"])

    def test_unknown_plan_keys_rejected_with_new_optional_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=plan(root)
            data=json.loads(p.read_text())
            data["allow_order"]=True
            p.write_text(json.dumps(data))
            with self.assertRaises(InputError):
                runbook.read_plan(p)


if __name__ == "__main__":
    unittest.main()
