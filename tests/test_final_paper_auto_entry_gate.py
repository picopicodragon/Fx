"""No entry without original six bytes, V2 build, official calendar and clock."""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
from pathlib import Path

from research import final_paper_engine as engine
from research import final_paper_auto_entry_gate as gate
from research import final_paper_official_archive_integrity as archive
from research import final_paper_public_source_snapshot as snapshots
from research.offline_backtest import InputError

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
BIND="a"*64


class FinalEntryEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.original=self.root/"official_public_capture_20261120_113041_303"
        snapshots.snapshot(
            self.original,allow_network=True,
            fetcher=lambda u:(("SOURCE ORIGINAL "+u).encode("ascii"),
                               "Fri, 20 Nov 2026 10:00:00 GMT"),
            now=NOW)
        verified=archive.audit(self.original)
        sha_by_id={x["source_id"]:x["sha256_local_only"]
                   for x in verified["verified_local_sha256s"]}
        self.permit=self.root/"entry_permit.json"
        source={}
        for name,ident in gate.SOURCE_IDS.items():
            filename=ident+(".ics" if ident.endswith("_ics") else ".html")
            source[name]={"filename":filename,
                          "sha256":sha_by_id[ident]}
        for item,filename,bytes_data in (
            ("independent_utc_clock","independent_ntp_time.txt",
             b"EXTERNAL REVIEWED NTP TIMESTAMP RECORD"),
            ("broker_clock","mt4_broker_time.txt",
             b"REVIEWED SEPARATE MT4 SERVER CLOCK PROOF"),
            ("pre_release_consensus","forecast_before_release.txt",
             b"REVIEWED FORECAST PRE RELEASE ARCHIVE"),
            ("cost_model","fx_cost_model_review.txt",
             b"REVIEWED BROKER COST SLIPPAGE AND SWAP AUDIT"),
            ("mt4_v2_experts_log","mt4_version_v2_experts.log",
             b"2026-11-20 FXPAPER-CLOCKFREEZE-20261120-V2 started DEMO"),
        ):
            (self.root/filename).write_bytes(bytes_data)
            source[item]={
                "filename":filename,
                "sha256":hashlib.sha256(bytes_data).hexdigest(),
            }
        self.record={
            "schema":gate.SCHEMA,
            "scope":gate.SCOPE,
            "operator_approval":gate.APPROVAL,
            "approved_at_utc":(NOW-timedelta(minutes=1)).isoformat(),
            "expires_at_utc":(NOW+timedelta(hours=2)).isoformat(),
            "bound_journal_sha256":BIND,
            "official_archive_manifest_sha256":
                verified["local_manifest_sha256"],
            "sources":source,
            "clock":{
                "independent_utc_checked_at":
                    (NOW-timedelta(minutes=1)).isoformat(),
                "broker_utc_checked_at":
                    (NOW-timedelta(minutes=1)).isoformat(),
                "pc_utc_offset_seconds":"0.1",
                "broker_utc_offset_seconds":"0.3",
                "expected_broker_minus_pc_seconds":7200,
                "external_utc_source_checked":True,
                "broker_time_independently_reviewed":True,
            },
            "calendar":{
                "coverage_start_utc":(NOW-timedelta(hours=1)).isoformat(),
                "coverage_until_utc":(NOW+timedelta(days=1)).isoformat(),
                "covered_currencies":["USD","EUR","JPY"],
                "events":[{
                    "id":"us_cpi_001","currency":"USD",
                    "release_utc":(NOW+timedelta(hours=1)).isoformat(),
                    "importance":"HIGH",
                    "source_url":snapshots.SOURCES["us_bls_calendar_ics"],
                    "original_source_id":"us_bls_calendar_ics",
                }],
                "reviewed_no_missing_high_impact_events":True,
            },
            "consensus":{
                "source_captured_at_utc":
                    (NOW-timedelta(hours=2)).isoformat(),
                "forecast_available_before_release":True,
                "source_originals_reviewed":True,
            },
            "cost":{
                "max_spread_pips":{
                    "USD/JPY":"3.0","EUR/JPY":"3.0","EUR/USD":"2.0"},
                "worst_case_swap_jpy_per_lot_per_day":{
                    pair:{"LONG":"10","SHORT":"10"} for pair in engine.PAIRS},
                "model_exit_slippage_pips_per_side":"1.0",
                "swap_and_slippage_research_reviewed":True,
            },
            "mt4":{
                "build_tag":"FXPAPER-CLOCKFREEZE-20261120-V2",
                "demo_account_verified":True,
                "single_observer_verified":True,
                "metaeditor_zero_compile_errors_verified":True,
            },
            "human_evidence_review":True,
        }
        self.capture_epoch=int((NOW-timedelta(minutes=1)).timestamp())
        self.quote_file=self.root/f"FxPaperQuote_{(NOW-timedelta(minutes=1)).strftime('%Y%m%d_%H%M%S')}.csv"
        with self.quote_file.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=engine.QUOTE_FIELDS)
            writer.writeheader()
            for i,(sym,bid,wide) in enumerate((
                ("USDJPY","159.500",".005"),("EURJPY","175.200",".01"),
                ("EURUSD","1.10000",".00005"))):
                writer.writerow({
                    "pair":sym,"bid":bid,"ask":str(D(bid)+D(wide)),
                    "tick_time_broker_epoch_unattested":
                        self.capture_epoch+7199,
                    "broker_time_epoch_unattested":self.capture_epoch+7200,
                    "capture_epoch_utc_pc":self.capture_epoch,
                    "tickvalue_jpy_broker_reported":"100",
                    "ticksize_broker_reported":
                        ".00001" if i==2 else ".001",
                    "min_lot_broker_reported":".01",
                    "lot_step_broker_reported":".01",
                    "max_lot_broker_reported":"20",
                    "point_broker_reported":
                        ".00001" if i==2 else ".001",
                })
        self.quote=engine.validate_quotes(self.quote_file,now=NOW)
        self.quote["source_original_file"]=self.quote_file
        self._save()

    def _save(self):
        self.permit.write_text(json.dumps(self.record),encoding="utf-8")

    def review(self):
        return gate.evaluate(self.permit,self.original,self.quote,
                             now=NOW,entry_binding_sha=BIND)

    def test_all_necessary_originals_and_no_order_attestation(self):
        result=self.review()
        self.assertTrue(result["entry_evidence_ready_by_operator_attestation"])
        self.assertFalse(result["known_event_blackout_active"])
        self.assertFalse(result["broker_orders_permitted"])
        self.assertFalse(result["full_independent_publication_authenticity_proven_by_code"])
        self.assertFalse(result["publisher_calendar_completeness_proven_by_code"])
        self.assertEqual(set(result["carry_costs_jpy_per_lot_day"]),
                         set(engine.PAIRS))

    def test_event_15_min_window_blocks(self):
        self.record["calendar"]["events"][0]["release_utc"]=(
            NOW+timedelta(minutes=5)).isoformat()
        self._save()
        result=self.review()
        self.assertTrue(result["known_event_blackout_active"])
        self.assertFalse(result["entry_evidence_ready_by_operator_attestation"])

    def test_old_legacy_clock_build_or_uncompiled_cannot_pass(self):
        for field,value in (
            ("build_tag","OLD_V1"),
            ("single_observer_verified",False),
            ("metaeditor_zero_compile_errors_verified",False),
            ("demo_account_verified",False),
        ):
            with self.subTest(field=field):
                before=self.record["mt4"][field]
                self.record["mt4"][field]=value
                self._save()
                with self.assertRaises(InputError):
                    self.review()
                self.record["mt4"][field]=before

    def test_forecast_source_tamper_and_wrong_journal_session_block(self):
        (self.root/"forecast_before_release.txt").write_bytes(b"tampered")
        with self.assertRaises(InputError):
            self.review()
        (self.root/"forecast_before_release.txt").write_bytes(
            b"REVIEWED FORECAST PRE RELEASE ARCHIVE")
        self.record["bound_journal_sha256"]="e"*64
        self._save()
        with self.assertRaises(InputError):
            self.review()

    def test_unreviewed_calendar_and_missing_currency_proof_fail(self):
        self.record["calendar"]["covered_currencies"]=["USD","JPY"]
        self._save()
        with self.assertRaises(InputError):
            self.review()
        self.record["calendar"]["covered_currencies"]=["USD","EUR","JPY"]
        self.record["calendar"]["reviewed_no_missing_high_impact_events"]=False
        self._save()
        with self.assertRaises(InputError):
            self.review()

    def test_cross_currency_official_event_reference_rejected(self):
        self.record["calendar"]["events"][0]["original_source_id"]=\
            "eur_ecb_calendar"
        self._save()
        with self.assertRaises(InputError):
            self.review()

    def test_broker_pc_offset_changed_two_seconds_above_anchor_blocks(self):
        data=self.quote_file.read_text("utf-8")
        self.quote_file.write_text(data.replace(
            str(self.capture_epoch+7200),str(self.capture_epoch+7203)))
        with self.assertRaises(InputError):
            self.review()

    def test_stale_independent_clock_is_not_considered_live(self):
        self.record["clock"]["independent_utc_checked_at"]=(
            NOW-timedelta(days=2)).isoformat()
        self._save()
        with self.assertRaises(InputError):
            self.review()

    def test_quote_without_original_mt4_csv_is_fail_closed(self):
        del self.quote["source_original_file"]
        with self.assertRaises(InputError):
            self.review()


if __name__=="__main__":
    unittest.main()
