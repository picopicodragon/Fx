"""3-pair real-H1/archived-news periodic AI smoke and fail-closed tests."""
from __future__ import annotations

import csv
import email.utils
import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from research import final_demo_periodic as periodic
from research import final_demo_periodic_ai as pipeline
from research import forward_multi_official_news_snapshot as news
from research.offline_backtest import InputError

NOW=datetime(2026,11,17,6,0,tzinfo=timezone.utc)


def prepare_captures(root:Path)->Path:
    folder=root/"h1"
    folder.mkdir()
    captured=int(NOW.timestamp())
    oldest=captured-121*3600
    for symbol,base in (("USDJPY",157.0),("EURJPY",178.0),("EURUSD",1.15)):
        filename=f"FxDemoH1_{symbol}_20261117_060000.csv"
        with (folder/filename).open("w",newline="",encoding="ascii") as fp:
            writer=csv.writer(fp,lineterminator="\n")
            writer.writerow(periodic.FIELDS)
            for i in range(periodic.BAR_COUNT):
                close=base+0.0002*i
                writer.writerow([symbol,"H1",str(oldest+i*3600),
                    f"{close:.5f}",f"{close+0.0003:.5f}",
                    f"{close-0.0003:.5f}",f"{close:.5f}","42",
                    str(captured)])
    return folder


def create_bundle(root:Path,feed:str)->Path:
    published=NOW-timedelta(hours=2)
    url={
        "fed_policy":"https://www.federalreserve.gov/newsevents/pressreleases/monetary20261117a.htm",
        "boj_whatsnew":"https://www.boj.or.jp/en/mopo/outlook/gor2611a.htm",
    }[feed]
    xml=(
        '<rss version="2.0"><channel><title>Official</title><item>'
        '<title>Official dated policy observation</title>'
        '<link>'+url+'</link>'
        '<pubDate>'+email.utils.format_datetime(published)+'</pubDate>'
        '<description>Policy update only, not a future calendar.</description>'
        '</item></channel></rss>').encode("utf-8")
    directory=root/feed
    manifest=news.prepare({feed:xml},
        captured_at_utc=NOW.isoformat().replace("+00:00","Z"),
        collection_mode="LOCAL_COPY")
    news.save(directory,{feed:xml},manifest)
    selfcheck=news.verify(directory)
    assert selfcheck["feed_count"]==1
    return directory


class PeriodicTests(unittest.TestCase):
    def test_closed_H1_and_saved_news_independent_of_event(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            folder=prepare_captures(root)
            bundles=[create_bundle(root,"fed_policy"),
                     create_bundle(root,"boj_whatsnew")]
            result=periodic.run(folder,bundles,"USD/JPY",
                                root/"next.json",now=NOW)
            self.assertTrue(result["macro_coverage_complete_research_only"])
            self.assertEqual(result["news_items_used"],2)
            self.assertEqual(result["technical"]["closed_H1_bar_count"],120)
            self.assertEqual(result["technical"]["ema_trend"],"UP")
            self.assertEqual(result["ai_inference_calls_this_run"],0)
            self.assertEqual(result["demo_orders_sent_this_run"],0)
            self.assertFalse(result["demo_orders_permitted"])
            self.assertEqual(result["status"],
                "PERIODIC_PRICE_MACRO_PACKET_PREPARED_RESEARCH_HOLD_NO_GO")
            self.assertFalse((root/"next.json").exists())

    def test_mt4_exporter_readonly_three_pair_closed_bar_contract(self):
        script=(Path(__file__).resolve().parents[1]/
                "mt4"/"read_only"/"FxFinalTestH1Export.mq4")
        raw=script.read_text("utf-8")
        for token in ("#property strict","IsDemo()","PERIOD_H1",
                      "FXD_BARS 120","USDJPY","EURJPY","EURUSD",
                      "for(int n=FXD_BARS;n>=1;n--)",
                      "FILE_CSV","capture_epoch_utc_pc",
                      "if(FileIsExist(names[i]))"):
            self.assertIn(token,raw)
        for forbidden in ("OrderSend(","OrderModify(","OrderClose(",
                          "WebRequest(","#import ","FILE_COMMON|"):
            self.assertNotIn(forbidden,raw)

    def test_empty_macro_region_holds_without_fake_event(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=prepare_captures(root)
            bundles=[create_bundle(root,"fed_policy")]
            result=periodic.run(folder,bundles,"USD/JPY",
                                root/"next.json",now=NOW)
            self.assertFalse(result["macro_coverage_complete_research_only"])
            self.assertEqual(result["status"],
                "PERIODIC_PRICE_PACKET_MACRO_COVERAGE_INCOMPLETE_NO_GO")

    def test_stale_clock_and_partial_CSV_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            folder=prepare_captures(root)
            bundles=[create_bundle(root,"fed_policy"),
                     create_bundle(root,"boj_whatsnew")]
            with self.assertRaises(InputError):
                periodic.run(folder,bundles,"USD/JPY",root/"x.json",
                             now=NOW+timedelta(hours=1))
            (folder/"FxDemoH1_EURJPY_20261117_060000.csv").unlink()
            with self.assertRaises(InputError):
                periodic.run(folder,bundles,"USD/JPY",root/"x.json",
                             now=NOW)

    def test_modified_news_manifest_fails_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=prepare_captures(root)
            fed=create_bundle(root,"fed_policy")
            boj=create_bundle(root,"boj_whatsnew")
            (fed/"fed_policy.xml").write_bytes(b"<rss/>")
            with self.assertRaises(InputError):
                periodic.run(folder,[fed,boj],"USD/JPY",
                             root/"r.json",now=NOW)

    def test_two_model_AI_research_is_bounded_and_never_an_order(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            folder=prepare_captures(root)
            bundles=[create_bundle(root,"fed_policy"),
                     create_bundle(root,"boj_whatsnew")]
            ledger=root/"ledger.json"
            def infer(model,prompt,packet,*,key):
                self.assertEqual(key,"synthetic-test-key")
                if model=="research-analysis":
                    return {"action":"HOLD","hypothesis":"No confirmed edge",
                            "counterevidence":"No consensus"}
                return {"verdict":"APPROVED","rationale":"HOLD is conservative"}
            with patch.dict("os.environ",{"OPENAI_API_KEY":"synthetic-test-key"}):
                result=pipeline.run(folder,bundles,"USD/JPY",ledger,
                    analyst_model="research-analysis",
                    reviewer_model="research-reviewer",
                    allow_external_api=True,max_api_calls=2,
                    now=NOW,inference=infer)
            self.assertEqual(result["paid_calls_this_run"],2)
            self.assertEqual(result["model_verdict"],"APPROVED")
            self.assertEqual(result["model_action_research_only"],"HOLD")
            self.assertTrue(result["candidate_is_not_an_executable_order"])
            self.assertEqual(result["orders_sent_this_run"],0)
            self.assertFalse(result["demo_orders_permitted"])
            with patch.dict("os.environ",{"OPENAI_API_KEY":"synthetic-test-key"}):
                no_op=pipeline.run(folder,bundles,"USD/JPY",ledger,
                    analyst_model="research-analysis",
                    reviewer_model="research-reviewer",
                    allow_external_api=True,max_api_calls=2,
                    now=NOW,inference=lambda *a,**kw: self.fail("replayed API"))
            self.assertEqual(no_op["paid_calls_this_run"],0)

    def test_safe_error_has_no_response_body_and_discloses_pending_stage(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Path(d)/"ai_USDJPY_test.json"
            ledger.write_text(json.dumps({
                "stage":"ANALYST_PENDING","pending_role":"analyst",
                "analyst":None,"reviewer":None,
                "SECRET_CONTENT":"never print"}),encoding="utf-8")
            from research.macro_ai_generate import MacroAPIError
            problem=MacroAPIError(
                "HTTP_404_MODEL_UNAVAILABLE_OR_NOT_FOUND",
                api_param="model",api_code="model_not_found",
                message_category="UNCLASSIFIED_INPUT_ERROR")
            report=pipeline.safe_failure_report(problem,ledger)
            self.assertEqual(report["failure_category"],
                             "HTTP_404_MODEL_UNAVAILABLE_OR_NOT_FOUND")
            self.assertEqual(report["ledger_state"],"ANALYST_PENDING")
            self.assertEqual(report["pending_role"],"analyst")
            self.assertTrue(report["api_dispatch_may_have_occurred"])
            self.assertFalse(report["retry_permitted"])
            self.assertNotIn("SECRET_CONTENT",json.dumps(report))

    def test_absent_ledger_reports_preflight_without_paid_assumption(self):
        with tempfile.TemporaryDirectory() as d:
            report=pipeline.safe_failure_report(
                InputError("stale/future PC clock H1 snapshot"),
                Path(d)/"absent.json")
            self.assertEqual(report["failure_category"],
                             "LOCAL_PREFLIGHT_OR_VALIDATION")
            self.assertEqual(report["ledger_state"],"ABSENT")
            self.assertFalse(report["api_dispatch_may_have_occurred"])
            self.assertFalse(report["retry_permitted"])

    def test_AI_no_optin_and_pending_request_never_retried(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=prepare_captures(root)
            bundles=[create_bundle(root,"fed_policy"),
                     create_bundle(root,"boj_whatsnew")]
            ledger=root/"ledger.json"
            report=pipeline.run(folder,bundles,"USD/JPY",ledger,
                analyst_model="research-analysis",
                reviewer_model="research-reviewer",now=NOW)
            self.assertEqual(report["status"],"PERIODIC_AI_PREFLIGHT_ONLY_NO_GO")
            self.assertFalse(ledger.exists())
            with patch.dict("os.environ",{"OPENAI_API_KEY":"synthetic-test-key"}):
                def broken(*args,**kwargs): raise RuntimeError("unknown API outcome")
                with self.assertRaises(RuntimeError):
                    pipeline.run(folder,bundles,"USD/JPY",ledger,
                        analyst_model="research-analysis",
                        reviewer_model="research-reviewer",
                        allow_external_api=True,max_api_calls=2,
                        now=NOW,inference=broken)
            self.assertEqual(json.loads(ledger.read_text())[
                "pending_role"],"analyst")
            with patch.dict("os.environ",{"OPENAI_API_KEY":"synthetic-test-key"}):
                with self.assertRaises(InputError):
                    pipeline.run(folder,bundles,"USD/JPY",ledger,
                        analyst_model="research-analysis",
                        reviewer_model="research-reviewer",
                        allow_external_api=True,max_api_calls=2,
                        now=NOW,inference=lambda *a,**kw: self.fail("retry"))


if __name__=="__main__":
    unittest.main()
