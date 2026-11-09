"""FWD-02: official RSS bounded network contract, all tests offline."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from research import forward_observation as obs
from research import forward_rss as rss
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 10, 8, 0, tzinfo=timezone.utc)


def xml(*, pub="Tue, 10 Nov 2026 07:30:00 GMT",
        title="Employment Situation", url="https://www.bls.gov/news.release/empsit.htm"):
    return (f'<rss version="2.0"><channel><title>Fixture RSS</title>'
            f'<item><title>{title}</title><link>{url}</link>'
            f'<pubDate>{pub}</pubDate>'
            f'<description>Research-only test data</description>'
            f'</item></channel></rss>').encode()


class ForwardRssTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = self.root / "journal"
        obs.initialize(self.store, "rss_fixture", now=NOW)

    def test_offline_rss_capture_deduplicates_without_network(self):
        result = rss.import_xml(self.store, "bls_empsit", xml(), now=NOW)
        self.assertEqual(result["new_recent_items"], 1)
        self.assertFalse(result["source_authenticity_verified"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertEqual(obs.audit(self.store)["record_count"], 1)
        repeat = rss.import_xml(self.store, "bls_empsit", xml(), now=NOW)
        self.assertEqual(repeat["new_recent_items"], 0)
        self.assertEqual(obs.audit(self.store)["record_count"], 1)

    def test_source_is_unverified_and_consensus_not_fabricated(self):
        rows = rss.parse_feed(xml(), "bls_empsit",
                              received_utc="2026-11-10T08:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["payload"]["consensus"], "")
        self.assertEqual(rows[0]["payload"]["released_value"], "")
        self.assertEqual(rows[0]["payload"]["source_status"],
                         "USER_SUPPLIED_UNVERIFIED")
        self.assertEqual(rows[0]["observed_at_utc"],
                         "2026-11-10T08:00:00Z")
        self.assertEqual(rows[0]["payload"]["published_at_utc"],
                         "2026-11-10T07:30:00Z")

    def test_future_old_dtd_foreign_and_redirect_rejected(self):
        for payload in (
            xml(pub="Tue, 10 Nov 2026 09:00:00 GMT"),
            xml(url="https://evil.example/releases"),
            xml(url="http://www.bls.gov/releases"),
            xml(title="bad", url="https://www.bls.gov.evil.example/x"),
            b"<!DOCTYPE rss [<!ENTITY x SYSTEM 'file:///etc/passwd'>]>"
            + xml(),
            b"<xml/>",
        ):
            with self.subTest(payload=payload), self.assertRaises(
                    (InputError, Exception)):
                rss.parse_feed(payload, "bls_empsit",
                               received_utc="2026-11-10T08:00:00Z")
        result = rss.import_xml(
            self.store, "bls_empsit",
            xml(pub="Mon, 09 Nov 2026 06:00:00 GMT"), now=NOW)
        self.assertEqual(result["new_recent_items"], 0)
        self.assertEqual(obs.audit(self.store)["record_count"], 0)
        with self.assertRaises(InputError):
            rss.NoRedirect().redirect_request(
                Mock(), Mock(), 302, "changed", {}, "https://evil.example")

    def test_explicit_small_cap_rejects_without_partial_ingest(self):
        one = xml().decode().split("<item>")[1].split("</item>")[0]
        two = one.replace("Employment Situation", "CPI").replace(
            "/empsit.htm", "/cpi.htm")
        raw = ('<rss version="2.0"><channel><title>Fixture</title><item>'
               + one + '</item><item>' + two +
               '</item></channel></rss>').encode()
        with self.assertRaises(InputError):
            rss.import_xml(self.store, "bls_empsit", raw,
                           now=NOW, max_new=1)
        self.assertEqual(obs.audit(self.store)["record_count"], 0)

    def test_no_network_by_default(self):
        with self.assertRaises(InputError):
            rss.get_feed("not_allowlisted")
        file = self.root / "raw.xml"
        file.write_bytes(xml())
        self.assertEqual(rss.main([
            "--store", str(self.store), "--feed", "bls_empsit",
            "--xml-file", str(file)]), 0)
        self.assertEqual(rss.main([
            "--store", str(self.store), "--feed", "bls_empsit"]), 2)
        self.assertEqual(obs.audit(self.store)["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
