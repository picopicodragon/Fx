"""FWD-183..190 RSS diagnostics: no network unless explicit, no mutation."""
import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import forward_observation as obs
from research import forward_rss as rss
from research import forward_rss_diagnose as diagnosis

NOW = datetime(2026, 11, 10, 8, tzinfo=timezone.utc)
ASOF = "2026-11-10T08:00:00Z"


def xml(count=1, *, old=False):
    pub = ("Mon, 09 Nov 2026 06:00:00 GMT" if old
           else "Tue, 10 Nov 2026 07:30:00 GMT")
    items = []
    for n in range(count):
        items.append(
            "<item><title>Research only</title>"
            f"<link>https://www.bls.gov/news.release/test{n}.htm</link>"
            f"<pubDate>{pub}</pubDate>"
            "<description>Synthetic fixture</description></item>"
        )
    return ("<rss version='2.0'><channel>" + "".join(items) +
            "</channel></rss>").encode("utf-8")


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = self.root/"journal"
        obs.initialize(self.store,"rss_research",now=NOW)

    def test_valid_offline_preflight_does_not_ingest(self):
        with patch.object(rss,"get_feed",side_effect=AssertionError("network")):
            report = diagnosis.diagnose(
                self.store, "bls_cpi", asof_utc=ASOF, raw=xml())
        self.assertEqual(report["status"],"RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")
        self.assertEqual(report["feed_items_parsed"],1)
        self.assertEqual(report["unseen_published_within_24h"],1)
        self.assertFalse(report["network_opted_in"])
        self.assertFalse(report["journal_modified"])
        self.assertEqual(report["runtime_go_no_go"],"NO_GO")
        self.assertEqual(obs.audit(self.store)["record_count"],0)

    def test_known_http_403_is_classified_without_body(self):
        exc=urllib.error.HTTPError(
            "https://www.bls.gov/feed/cpi.rss",403,"secret error text",
            None,None)
        with patch.object(rss,"get_feed",side_effect=exc):
            report=diagnosis.diagnose(
                self.store,"bls_cpi",asof_utc=ASOF,allow_network=True)
        self.assertEqual(report["stage"],"FETCH")
        self.assertEqual(report["reason_code"],"HTTP_403")
        self.assertNotIn("secret",json.dumps(report))
        self.assertEqual(report["api_calls_this_run"],0)
        self.assertEqual(obs.audit(self.store)["record_count"],0)

    def test_known_http_429_and_500_are_classified(self):
        for status, code in ((429,"HTTP_429"),(503,"HTTP_5XX")):
            with self.subTest(status=status):
                exc=urllib.error.HTTPError(
                    "https://www.bls.gov/feed/empsit.rss",
                    status,"provider secret",None,None)
                with patch.object(rss,"get_feed",side_effect=exc):
                    report=diagnosis.diagnose(
                        self.store,"bls_empsit",asof_utc=ASOF,
                        allow_network=True)
                self.assertEqual(report["reason_code"],code)
                self.assertFalse(report["journal_modified"])

    def test_network_error_is_safely_redacted(self):
        with patch.object(rss,"get_feed",side_effect=urllib.error.URLError(
                "user's private network details")):
            report=diagnosis.diagnose(
                self.store,"bls_cpi",asof_utc=ASOF,allow_network=True)
        self.assertEqual(report["reason_code"],"NETWORK_TLS_DNS_OR_TIMEOUT")
        self.assertNotIn("private",json.dumps(report))

    def test_html_page_not_mistaken_for_rss(self):
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,
            raw=b"<html>access denied</html>")
        self.assertEqual(report["stage"],"PARSE_AND_PREFLIGHT")
        self.assertEqual(report["reason_code"],"UNEXPECTED_XML_ROOT")
        self.assertEqual(obs.audit(self.store)["record_count"],0)

    def test_invalid_xml_classified(self):
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,raw=b"<rss")
        self.assertEqual(report["reason_code"],"INVALID_RSS_XML")

    def test_foreign_link_is_rejected(self):
        raw=xml().replace(b"www.bls.gov",b"www.example.org")
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,raw=raw)
        self.assertEqual(report["reason_code"],"ITEM_URL_NOT_ALLOWLISTED")

    def test_suspicious_dtd_is_rejected(self):
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,
            raw=b"<!DOCTYPE rss [<!ENTITY x SYSTEM 'file:///tmp/x'>]>" + xml())
        self.assertEqual(report["reason_code"],"UNSAFE_XML_OR_SIZE")

    def test_many_recent_items_over_cap_maintains_fail_closed(self):
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,raw=xml(4),
            max_new=3)
        self.assertEqual(report["reason_code"],"NEW_RECENT_ITEMS_OVER_CAP")
        self.assertEqual(report["unseen_published_within_24h"],4)
        self.assertEqual(report["items_that_would_be_ingested_if_normal_import_ran"],0)
        self.assertEqual(obs.audit(self.store)["record_count"],0)

    def test_existing_authorized_upper_cap_passes_four(self):
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,raw=xml(4),max_new=5)
        self.assertEqual(report["status"],"RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")
        self.assertEqual(report["items_that_would_be_ingested_if_normal_import_ran"],4)
        self.assertFalse(report["journal_modified"])

    def test_over_five_not_relaxed(self):
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,raw=xml(6),max_new=5)
        self.assertEqual(report["reason_code"],"NEW_RECENT_ITEMS_OVER_CAP")

    def test_expired_items_not_rewritten_as_recent_events(self):
        report=diagnosis.diagnose(
            self.store,"bls_empsit",asof_utc=ASOF,raw=xml(old=True))
        self.assertEqual(report["unseen_but_older_than_24h"],1)
        self.assertEqual(report["unseen_published_within_24h"],0)
        self.assertFalse(report["journal_modified"])

    def test_same_feed_existing_event_not_reimported(self):
        rss.import_xml(self.store,"bls_cpi",xml(),now=NOW)
        report=diagnosis.diagnose(
            self.store,"bls_cpi",asof_utc=ASOF,raw=xml())
        self.assertEqual(report["already_seen_in_this_feed"],1)
        self.assertEqual(report["unseen_published_within_24h"],0)
        self.assertEqual(obs.audit(self.store)["record_count"],1)

    def test_journal_malformed_rejected_before_feed(self):
        (self.store/"00000002.json").write_text("{}")
        with patch.object(rss,"get_feed",side_effect=AssertionError("network")):
            report=diagnosis.diagnose(
                self.store,"bls_cpi",asof_utc=ASOF,raw=xml())
        self.assertEqual(report["stage"],"JOURNAL_AUDIT")
        self.assertNotEqual(report["status"],"RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")

    def test_sources_must_be_exactly_one(self):
        for raw,net in ((None,False),(xml(),True)):
            with self.subTest(raw=raw is not None,net=net):
                report=diagnosis.diagnose(
                    self.store,"bls_cpi",asof_utc=ASOF,
                    raw=raw,allow_network=net)
                self.assertEqual(report["stage"],"INPUT")
                self.assertEqual(report["status"],"RSS_DIAGNOSTIC_FAIL_CLOSED_NO_GO")

    def test_network_still_requires_explicit_flag(self):
        with patch.object(rss,"get_feed",return_value=xml()) as mocked:
            report=diagnosis.diagnose(
                self.store,"bls_cpi",asof_utc=ASOF,allow_network=True)
            mocked.assert_called_once_with("bls_cpi")
        self.assertTrue(report["network_opted_in"])
        self.assertEqual(report["api_calls_this_run"],0)

    def test_cli_offline_xml_no_journal_modification(self):
        path=self.root/"raw.xml";path.write_bytes(xml())
        with patch("sys.stdout",new_callable=io.StringIO) as stream:
            result=diagnosis.main([
                "--store",str(self.store),"--feed","bls_empsit",
                "--xml-file",str(path)])
        self.assertEqual(result,0)
        self.assertEqual(json.loads(stream.getvalue())["journal_modified"],False)
        self.assertEqual(obs.audit(self.store)["record_count"],0)

    def test_cli_bad_local_xml_fail_closed(self):
        with patch("sys.stdout",new_callable=io.StringIO) as stream:
            result=diagnosis.main([
                "--store",str(self.store),"--feed","bls_cpi",
                "--xml-file",str(self.root/"absent.xml")])
        self.assertEqual(result,2)
        self.assertEqual(json.loads(stream.getvalue())["reason_code"],
                         "UNREADABLE_OR_OVERSIZED_LOCAL_XML")

    def test_no_unapproved_orders_or_data_publishing(self):
        result=diagnosis.diagnose(
            self.store,"fed_policy",asof_utc=ASOF,raw=xml())
        self.assertFalse(result["demo_orders_permitted"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertFalse(result["automatic_retry_permitted"])


if __name__=="__main__":
    unittest.main()
