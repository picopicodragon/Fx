"""FWD-1462: official-feed capture by real-clock, no-order, no-AI regressions."""
from __future__ import annotations

import email.utils
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research import forward_macro_feed_once as source
from research import forward_observation as obs
from research import forward_multi_official_news_snapshot as news

NOW = datetime(2026, 11, 17, 2, 0, 0, tzinfo=timezone.utc)


def make_xml(feed: str, published: datetime, suffix: str = "x") -> bytes:
    host = news.SOURCE_HOSTS[feed]
    url = f"https://{host}/news/official-{suffix}.html"
    date = email.utils.format_datetime(published)
    content = (
        f'<rss version="2.0"><channel><title>Official news feed</title>'
        f'<item><title>Official news {suffix}</title><link>{url}</link>'
        f'<pubDate>{date}</pubDate><description>Bulletin only. '
        f'No economic consensus.</description></item></channel></rss>'
    )
    return content.encode("utf-8")


class FeedCaptureTests(unittest.TestCase):
    def setup(self, root):
        store = root/"journal"
        obs.initialize(store,"macro_feed_test",now=NOW-timedelta(hours=5))
        return store

    def test_local_US_feed_archive_and_journal_append(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            store=self.setup(root)
            file=root/"fed.xml"
            file.write_bytes(make_xml(
                "fed_policy", NOW-timedelta(minutes=40)))
            result=source.run(
                store,root/"capture1",["fed_policy"],xml_files={
                    "fed_policy":file},clock=lambda:NOW)
            self.assertEqual(result["status"],
                             "OFFICIAL_FEEDS_ARCHIVED_HOLD_NO_GO")
            self.assertEqual(result["feed_bundles_verified_format"],1)
            self.assertEqual(result["new_recent_us_journal_records"],1)
            self.assertEqual(result["network_calls_attempted"],0)
            self.assertEqual(result["ai_inference_calls_this_run"],0)
            self.assertEqual(result["orders_sent_this_run"],0)
            self.assertFalse(result["demo_orders_permitted"])
            self.assertFalse(result["real_orders_permitted"])
            self.assertEqual(obs.audit(store)["by_kind"]["MACRO_EVENT"],1)
            archive=root/"capture1"/"fed_policy"
            self.assertEqual(news.verify(archive)["feed_count"],1)
            original=archive/"fed_policy.xml"
            self.assertEqual(original.read_bytes(),file.read_bytes())
            report=json.loads(
                (root/"capture1"/"capture_report.json").read_text())
            self.assertEqual(report["new_recent_us_journal_records"],1)

    def test_duplicate_recent_feed_does_not_duplicate_journal_record(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            store=self.setup(root)
            file=root/"fed.xml"
            file.write_bytes(make_xml("fed_policy",NOW-timedelta(minutes=20)))
            args=dict(allow_network=False,xml_files={"fed_policy":file},clock=lambda:NOW)
            first=source.run(store,root/"capture1",["fed_policy"],**args)
            second=source.run(store,root/"capture2",["fed_policy"],**args)
            self.assertEqual(first["new_recent_us_journal_records"],1)
            self.assertEqual(second["new_recent_us_journal_records"],0)
            self.assertEqual(obs.audit(store)["by_kind"]["MACRO_EVENT"],1)

    def test_old_publication_is_archived_never_falsely_registered_as_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            file=root/"old.xml"
            file.write_bytes(make_xml("fed_policy",NOW-timedelta(days=3)))
            result=source.run(store,root/"archive",["fed_policy"],
                xml_files={"fed_policy":file},clock=lambda:NOW)
            self.assertEqual(result["new_recent_us_journal_records"],0)
            self.assertEqual(obs.audit(store)["record_count"],0)
            self.assertEqual(result["feeds"][0]["status"],
                "SOURCE_ARCHIVED_NO_RECENT_US_RELEASE_HOLD_NO_GO")

    def test_ECB_and_BOJ_news_archive_not_an_AI_macro_event(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            selected=["ecb_press","boj_whatsnew"]
            paths={}
            for feed in selected:
                file=root/(feed+".xml")
                file.write_bytes(make_xml(feed,NOW-timedelta(minutes=5),feed))
                paths[feed]=file
            result=source.run(store,root/"archive",selected,
                xml_files=paths,clock=lambda:NOW)
            self.assertEqual(result["feed_bundles_verified_format"],2)
            self.assertEqual(result["new_recent_us_journal_records"],0)
            self.assertEqual(obs.audit(store)["record_count"],0)
            self.assertEqual(news.verify(root/"archive"/"ecb_press")["feed_count"],1)
            self.assertTrue(all(
                r["regional_feed_journal_intake_disabled"] for r in result["feeds"]))

    def test_explicit_network_download_permitted_only_with_optin(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            calls=[]
            def get(feed):
                calls.append(feed)
                return make_xml(feed,NOW-timedelta(minutes=5))
            result=source.run(store,root/"archive",["fed_policy","ecb_press"],
                allow_network=True,downloader=get,clock=lambda:NOW)
            self.assertEqual(calls,["fed_policy","ecb_press"])
            self.assertEqual(result["network_calls_attempted"],2)
            self.assertEqual(result["new_recent_us_journal_records"],1)
            self.assertFalse(result["real_orders_permitted"])

    def test_one_feed_failure_does_not_claim_complete_or_block_valid_feed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            def get(feed):
                if feed=="bls_cpi":
                    raise OSError("official service unavailable")
                return make_xml(feed,NOW-timedelta(minutes=3))
            result=source.run(store,root/"archive",["bls_cpi","fed_policy"],
                allow_network=True,downloader=get,clock=lambda:NOW)
            self.assertEqual(result["status"],"OFFICIAL_FEEDS_PARTIAL_HOLD_NO_GO")
            self.assertEqual(result["feed_bundles_verified_format"],1)
            self.assertEqual(result["new_recent_us_journal_records"],1)
            self.assertEqual(obs.audit(store)["record_count"],1)
            self.assertTrue((root/"archive"/"capture_report.json").is_file())
            self.assertFalse((root/"archive"/"bls_cpi").exists())

    def test_network_mode_rejects_ambiguous_and_disallowed_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            with self.assertRaises(Exception):
                source.run(store,root/"test",["fed_policy"],
                           allow_network=False)
            self.assertFalse((root/"test").exists())
            with self.assertRaises(Exception):
                source.run(store,root/"test",["fed_policy"],
                           allow_network=True,
                           xml_files={"fed_policy":root/"unused.xml"})
            self.assertFalse((root/"test").exists())

    def test_refuses_output_inside_journal_without_mutating(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            file=root/"fed.xml"
            file.write_bytes(make_xml("fed_policy",NOW-timedelta(minutes=1)))
            with self.assertRaises(Exception):
                source.run(store,store/"feed_bundle",["fed_policy"],
                           xml_files={"fed_policy":file})
            self.assertFalse((store/"feed_bundle").exists())

    def test_refuses_overwrite_and_duplicate_feed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            file=root/"fed.xml"
            file.write_bytes(make_xml("fed_policy",NOW-timedelta(minutes=1)))
            archive=root/"archive"
            source.run(store,archive,["fed_policy"],
                       xml_files={"fed_policy":file},clock=lambda:NOW)
            with self.assertRaises(Exception):
                source.run(store,archive,["fed_policy"],
                           xml_files={"fed_policy":file},clock=lambda:NOW)
            with self.assertRaises(Exception):
                source.run(store,root/"dup",["fed_policy","fed_policy"],
                           xml_files={"fed_policy":file},clock=lambda:NOW)
            self.assertFalse((root/"dup").exists())

    def test_future_published_article_is_not_added_to_journal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            file=root/"future.xml"
            file.write_bytes(make_xml("fed_policy",NOW+timedelta(days=1)))
            result=source.run(store,root/"archive",["fed_policy"],
                xml_files={"fed_policy":file},clock=lambda:NOW)
            self.assertEqual(result["feed_bundles_verified_format"],0)
            self.assertEqual(result["new_recent_us_journal_records"],0)
            self.assertEqual(result["status"],"OFFICIAL_FEEDS_ALL_FAILED_HOLD_NO_GO")
            self.assertEqual(obs.audit(store)["record_count"],0)

    def test_cli_defaults_to_failclosed_with_no_optin(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            with patch("sys.stdout",new_callable=io.StringIO) as stdout:
                code=source.main(["--store",str(store),
                                  "--out-dir",str(root/"new")])
            self.assertEqual(code,2)
            result=json.loads(stdout.getvalue())
            self.assertFalse(result["demo_orders_permitted"])
            self.assertEqual(result["network_calls_attempted"],0)
            self.assertFalse((root/"new").exists())

    def test_cli_offline_local_XML_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=self.setup(root)
            file=root/"fed.xml"
            file.write_bytes(make_xml("fed_policy",NOW-timedelta(days=2)))
            # 'now' in CLI is real current. Old XML must not masquerade as
            # new: no matter what the wall-clock time is on CI.
            with patch("research.forward_macro_feed_once._utc_now",
                       return_value=NOW):
                with patch("sys.stdout",new_callable=io.StringIO) as stdout:
                    code=source.main([
                        "--store",str(store),"--out-dir",str(root/"new"),
                        "--feed","fed_policy",
                        "--feed-file","fed_policy="+str(file)])
            self.assertEqual(code,0)
            result=json.loads(stdout.getvalue())
            self.assertEqual(result["new_recent_us_journal_records"],0)
            self.assertEqual(result["feed_bundles_verified_format"],1)
            self.assertEqual(obs.audit(store)["record_count"],0)


if __name__ == "__main__":
    unittest.main()
