"""FWD-191..204: secure BLS Atom ingestion and RSS backward compatibility."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import forward_observation as journal
from research import forward_rss as rss
from research import forward_rss_diagnose as diag
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
ASOF = "2026-11-10T09:00:00Z"
ATOM = "http://www.w3.org/2005/Atom"


def atom(*, published="2026-11-10T08:30:00-00:00", count=1,
         link="https://www.bls.gov/news.release/cpi.toc.htm",
         summary="Research only", only_updated=False, zone=True,
         rel="alternate", other_links="", root_ns=ATOM):
    entries = []
    for n in range(count):
        title = "CPI synthetic" + str(n)
        uri = link.replace("cpi.toc", "cpi" + str(n) + ".toc")
        pub = ("" if only_updated else
               f"<published>{published}</published>")
        update = ("2026-11-10T08:30:01-00:00" if zone
                  else "2026-11-10T08:30:01")
        entries.append(
            f"<entry><title>{title}</title>"
            f"<link rel='{rel}' href='{uri}'/>"
            + other_links +
            f"<updated>{update}</updated>" + pub +
            f"<summary>{summary}</summary></entry>")
    ns = f" xmlns='{root_ns}'" if root_ns else ""
    return ("<feed" + ns + ">" + "".join(entries) +
            "</feed>").encode("utf-8")


class SecureAtomTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = self.root/"journal"
        journal.initialize(self.store, "atom_research", now=NOW)

    def test_cpi_atom_asof_provenance_and_nonforecast(self):
        data = rss.parse_feed(atom(), "bls_cpi", received_utc=ASOF)
        self.assertEqual(len(data), 1)
        item = data[0]
        self.assertEqual(item["payload"]["published_at_utc"],
                         "2026-11-10T08:30:00Z")
        self.assertEqual(item["payload"]["consensus"], "")
        self.assertEqual(item["payload"]["released_value"], "")
        self.assertEqual(item["payload"]["source_status"],
                         "USER_SUPPLIED_UNVERIFIED")
        self.assertEqual(item["observed_at_utc"], ASOF)

    def test_empsit_atom_has_same_contract(self):
        data = rss.parse_feed(atom(), "bls_empsit", received_utc=ASOF)
        self.assertEqual(data[0]["source_id"], "bls_empsit")
        self.assertEqual(data[0]["payload"]["pair"], "USD/JPY")

    def test_atom_valid_recent_import_to_hash_journal(self):
        a = rss.import_xml(self.store, "bls_cpi", atom(), now=NOW)
        self.assertEqual(a["new_recent_items"], 1)
        self.assertEqual(journal.audit(self.store)["record_count"], 1)
        repeat = rss.import_xml(self.store, "bls_cpi", atom(), now=NOW)
        self.assertEqual(repeat["new_recent_items"], 0)
        self.assertEqual(journal.audit(self.store)["record_count"], 1)

    def test_rss_2_0_still_accepted(self):
        data = (b"<rss version='2.0'><channel>"
                b"<item><title>old RSS</title>"
                b"<link>https://www.federalreserve.gov/newsevents/pressreleases/"
                b"monetary.htm</link>"
                b"<pubDate>Tue, 10 Nov 2026 08:00:00 GMT</pubDate>"
                b"<description>Research</description></item></channel></rss>")
        item = rss.parse_feed(data, "fed_policy", received_utc=ASOF)[0]
        self.assertEqual(item["payload"]["published_at_utc"],
                         "2026-11-10T08:00:00Z")
        self.assertEqual(item["payload"]["source_status"],
                         "USER_SUPPLIED_UNVERIFIED")

    def test_atom_rejected_for_frb_unexpected_root(self):
        with self.assertRaises(InputError):
            rss.parse_feed(atom(), "fed_policy", received_utc=ASOF)

    def test_non_atom_feed_rejected(self):
        with self.assertRaises(InputError):
            rss.parse_feed(atom(root_ns=""), "bls_cpi", received_utc=ASOF)

    def test_missing_published_never_backfills_updated(self):
        with self.assertRaisesRegex(InputError, "ATOM_PUBLISHED"):
            rss.parse_feed(atom(only_updated=True),
                           "bls_cpi", received_utc=ASOF)

    def test_naive_published_rejected(self):
        with self.assertRaisesRegex(InputError, "TIMEZONE"):
            rss.parse_feed(atom(published="2026-11-10T08:30:00"),
                           "bls_cpi", received_utc=ASOF)

    def test_future_publication_rejected(self):
        with self.assertRaises(InputError):
            rss.parse_feed(atom(published="2026-11-11T12:00:00Z"),
                           "bls_cpi", received_utc=ASOF)

    def test_offset_converts_published_to_utc(self):
        data = rss.parse_feed(atom(
            published="2026-11-10T17:30:00+09:00"),
            "bls_cpi", received_utc=ASOF)
        self.assertEqual(data[0]["payload"]["published_at_utc"],
                         "2026-11-10T08:30:00Z")

    def test_foreign_official_other_host_rejected_in_bls_atom(self):
        with self.assertRaises(InputError):
            rss.parse_feed(atom(link="https://www.federalreserve.gov/"
                                    "news.release/cpi.toc.htm"),
                           "bls_cpi", received_utc=ASOF)

    def test_foreign_domain_rejected_in_atom(self):
        with self.assertRaises(InputError):
            rss.parse_feed(atom(link="https://attacker.example/"
                                    "news.release/cpi.toc.htm"),
                           "bls_cpi", received_utc=ASOF)

    def test_relative_link_rejected(self):
        with self.assertRaises(InputError):
            rss.parse_feed(atom(link="/news.release/cpi.toc.htm"),
                           "bls_cpi", received_utc=ASOF)

    def test_multiple_alternate_links_rejected(self):
        other = ("<link rel='alternate' href='https://www.bls.gov/"
                 "news.release/other.htm'/>")
        with self.assertRaisesRegex(InputError, "NOT_UNIQUE"):
            rss.parse_feed(atom(other_links=other),
                           "bls_cpi", received_utc=ASOF)

    def test_self_link_is_not_alternate(self):
        extra = ("<link rel='self' href='https://www.bls.gov/"
                 "feed/cpi.rss'/>")
        data = rss.parse_feed(atom(other_links=extra),
                              "bls_cpi", received_utc=ASOF)
        self.assertEqual(len(data), 1)

    def test_duplicate_links_across_entries_rejected(self):
        raw = atom().decode("utf-8")
        entry = raw.split("<entry>")[1].split("</entry>")[0]
        raw = raw.replace("</feed>", "<entry>" + entry + "</entry></feed>")
        with self.assertRaisesRegex(InputError, "duplicate"):
            rss.parse_feed(raw.encode("utf-8"),
                           "bls_cpi", received_utc=ASOF)

    def test_max_items_30_preserved(self):
        with self.assertRaisesRegex(InputError, "excessive"):
            rss.parse_feed(atom(count=31),
                           "bls_cpi", received_utc=ASOF)

    def test_new_recent_cap_three_and_max_five_preserved(self):
        raw = atom(count=4)
        with self.assertRaisesRegex(InputError, "cap"):
            rss.import_xml(self.store, "bls_cpi", raw, now=NOW, max_new=3)
        self.assertEqual(journal.audit(self.store)["record_count"], 0)
        result = rss.import_xml(self.store, "bls_cpi", raw, now=NOW, max_new=5)
        self.assertEqual(result["new_recent_items"], 4)

    def test_older_than_24h_never_rewritten_as_new(self):
        result = rss.import_xml(self.store, "bls_cpi", atom(
            published="2026-11-08T01:00:00Z"), now=NOW)
        self.assertEqual(result["new_recent_items"], 0)
        self.assertEqual(journal.audit(self.store)["record_count"], 0)

    def test_explicit_atom_xml_no_network(self):
        f = self.root/"local.xml"
        f.write_bytes(atom())
        original_import = rss.import_xml
        with patch.object(rss, "get_feed",
                          side_effect=AssertionError("must not fetch")), (
                patch.object(rss, "import_xml",
                             side_effect=lambda *a, **kw: original_import(
                                 *a, now=NOW, **kw))):
            result = rss.main(["--store", str(self.store),
                               "--feed", "bls_cpi",
                               "--xml-file", str(f)])
        self.assertEqual(result, 0)
        self.assertEqual(journal.audit(self.store)["record_count"], 1)

    def test_dtd_and_entity_still_rejected(self):
        raw = b"<!DOCTYPE feed [<!ENTITY x SYSTEM 'file:///etc/passwd'>]>" + atom()
        with self.assertRaises(InputError):
            rss.parse_feed(raw, "bls_cpi", received_utc=ASOF)

    def test_diagnostic_recognizes_atom_without_ingesting(self):
        report = diag.diagnose(self.store, "bls_cpi",
                               asof_utc=ASOF, raw=atom())
        self.assertEqual(report["status"],
                         "RSS_DIAGNOSTIC_PREFLIGHT_OK_NO_GO")
        self.assertEqual(report["feed_items_parsed"], 1)
        self.assertEqual(report["unseen_published_within_24h"], 1)
        self.assertFalse(report["journal_modified"])
        self.assertEqual(journal.audit(self.store)["record_count"], 0)

    def test_diagnostic_reports_missing_atom_published(self):
        report = diag.diagnose(self.store, "bls_cpi", asof_utc=ASOF,
                               raw=atom(only_updated=True))
        self.assertEqual(report["reason_code"],
                         "ATOM_PUBLISHED_MISSING_OR_INVALID")
        self.assertEqual(report["stage"], "PARSE_AND_PREFLIGHT")

    def test_bad_date_and_duplicate_dont_corrupt_journal(self):
        data = atom(count=1)
        with self.assertRaises(InputError):
            rss.import_xml(self.store, "bls_cpi",
                           data.replace(b"2026-11-10T08:30:00-00:00",
                                        b"bad-date"), now=NOW)
        self.assertEqual(journal.audit(self.store)["record_count"], 0)

    def test_https_allowlist_and_no_redirect_unchanged(self):
        self.assertEqual(rss.FEEDS["bls_cpi"],
                         "https://www.bls.gov/feed/cpi.rss")
        self.assertEqual(rss.FEEDS["bls_empsit"],
                         "https://www.bls.gov/feed/empsit.rss")
        self.assertEqual(rss.MAX_ITEMS, 30)
        self.assertEqual(rss.MAX_RESPONSE, 256_000)
        self.assertEqual(rss.TIMEOUT, 12)


if __name__=="__main__":
    unittest.main()
