"""FWD-441..488: one-shot multi-region official-news snapshot safety tests."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_multi_official_news_snapshot as news
from research import forward_global_macro_evidence as global_macro
from research import forward_macro_integrated_readiness as integrated
from research.offline_backtest import InputError

UTC = "2026-11-13T03:00:00Z"
PUB = "Fri, 13 Nov 2026 02:30:00 GMT"
ECB = "https://www.ecb.europa.eu/press/pr/date/2026/html/example.en.html"
BOJ = "https://www.boj.or.jp/en/mopo/2026/example.htm"
FED = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261113a.htm"
BLS = "https://www.bls.gov/news.release/cpi.htm"


def rss(feed, published=PUB, link=None):
    hosts = {
        "ecb_press": ECB, "boj_whatsnew": BOJ,
        "fed_policy": FED, "bls_cpi": BLS, "bls_empsit": BLS,
    }
    link = link or hosts[feed]
    return (
        "<rss version='2.0'><channel><title>Official fixture</title>"
        "<item><title>Example official published item</title>"
        "<link>" + link + "</link>"
        "<pubDate>" + published + "</pubDate>"
        "<description>Research-only fixture</description></item>"
        "</channel></rss>"
    ).encode()


def atom(feed="ecb_press", published="2026-11-13T02:30:00Z"):
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<entry><title>Released text</title>"
        '<link rel="alternate" href="' + (
            ECB if feed == "ecb_press" else BOJ) + '"/>'
        "<published>" + published + "</published></entry></feed>"
    ).encode()


def sources():
    return {
        "ecb_press": rss("ecb_press"),
        "boj_whatsnew": rss("boj_whatsnew"),
    }


class NewsCaptureTests(unittest.TestCase):
    def test_ecb_boj_xml_data_and_regions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = sources()
            m = news.prepare(raw, captured_at_utc=UTC,
                             collection_mode="LOCAL_COPY")
            self.assertEqual(len(m["feeds"]), 2)
            self.assertEqual(m["feeds"]["ecb_press"]["news_item_count"], 1)
            self.assertEqual(m["feeds"]["boj_whatsnew"]["news_item_count"], 1)
            self.assertEqual(m["scheduled_event_count"], 0)
            self.assertEqual(m["pre_release_consensus_count"], 0)
            self.assertEqual(m["network_calls_expected"], 0)
            self.assertFalse(m["source_authenticity_independently_verified"])
            news.save(root / "snapshot", raw, m)
            r = news.verify(root / "snapshot")
        self.assertEqual(r["observed_regions"], {"USD": 0, "EUR": 1, "JPY": 1})
        self.assertEqual(r["feed_count"], 2)
        self.assertTrue(r["historical_news_does_not_prove_upcoming_calendar"])
        self.assertTrue(r["consensus_evidence_missing"])
        self.assertEqual(r["network_calls_this_run"], 0)
        self.assertFalse(r["demo_orders_permitted"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertTrue(r["safety_hold_latched"])

    def test_existing_us_feed_integration(self):
        r = news.prepare(
            {"fed_policy": rss("fed_policy"), "bls_cpi": rss("bls_cpi")},
            captured_at_utc=UTC, collection_mode="LOCAL_COPY")
        self.assertEqual(r["feeds"]["fed_policy"]["news_item_count"], 1)
        self.assertEqual(r["feeds"]["bls_cpi"]["news_item_count"], 1)
        self.assertEqual(r["network_calls_expected"], 0)

    def test_all_five_feeds_are_one_bounded_bundle(self):
        raw = {key: rss(key) for key in news.FEEDS}
        manifest = news.prepare(raw, captured_at_utc=UTC,
                                collection_mode="EXPLICIT_NETWORK_SINGLE_PASS")
        self.assertEqual(manifest["network_calls_expected"], 5)
        self.assertEqual(len(manifest["feeds"]), 5)
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "snap"
            news.save(folder, raw, manifest)
            report = news.verify(folder)
        self.assertEqual(report["feed_count"], 5)
        self.assertEqual(report["observed_regions"],
                         {"USD": 3, "EUR": 1, "JPY": 1})
        self.assertFalse(report["real_orders_permitted"])

    def test_ecb_atom_and_boj_atom(self):
        for feed in ("ecb_press", "boj_whatsnew"):
            with self.subTest(feed=feed):
                r = news._parse_news(atom(feed), feed, UTC)
                self.assertEqual(len(r), 1)
                self.assertEqual(r[0]["published_at_utc"],
                                 "2026-11-13T02:30:00Z")

    def test_rss_dates_can_use_explicit_iso_dc_date(self):
        raw = (
            b'<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            b"<channel><item><title>BOJ notice</title>"
            b"<link>https://www.boj.or.jp/en/notice.htm</link>"
            b"<dc:date>2026-11-13T02:30:00+00:00</dc:date>"
            b"</item></channel></rss>")
        r = news._parse_news(raw, "boj_whatsnew", UTC)
        self.assertEqual(r[0]["published_at_utc"], "2026-11-13T02:30:00Z")

    def test_unknown_host_and_insecure_link_rejected(self):
        for bad in (
            "https://www.boj.or.jp.evil.test/mopo",
            "http://www.boj.or.jp/en/mopo",
            "https://www.ecb.europa.eu/press/pr",
            "https://www.boj.or.jp:8080/en/mopo",
            "https://alice@www.boj.or.jp/en/mopo",
        ):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                news._parse_news(rss("boj_whatsnew", link=bad),
                                 "boj_whatsnew", UTC)

    def test_wrong_atom_link_not_accepted(self):
        raw = atom().replace(
            b'rel="alternate"', b'rel="self"')
        with self.assertRaises(InputError):
            news._parse_news(raw, "ecb_press", UTC)

    def test_future_publication_is_rejected(self):
        with self.assertRaises(InputError):
            news._parse_news(
                rss("ecb_press", published="Fri, 13 Nov 2026 04:30:00 GMT"),
                "ecb_press", UTC)

    def test_unzoned_pub_date_fails_closed(self):
        with self.assertRaises(InputError):
            news._parse_news(
                rss("boj_whatsnew", published="2026-11-13T02:30:00"),
                "boj_whatsnew", UTC)

    def test_malformed_xml_and_external_entity_refused(self):
        with self.assertRaises((InputError, Exception)):
            news._parse_news(b"<rss>", "ecb_press", UTC)
        with self.assertRaises(InputError):
            news._parse_news(b"<!DOCTYPE rss [<!ENTITY x SYSTEM 'file:///etc/passwd'>]>"
                             + rss("ecb_press"), "ecb_press", UTC)

    def test_duplicate_item_link_rejected(self):
        first = rss("ecb_press").decode()
        duplicate = first.replace(
            "</channel>", "<item><title>Other</title><link>"+ECB
            +"</link><pubDate>"+PUB+"</pubDate></item></channel>")
        with self.assertRaises(InputError):
            news._parse_news(duplicate.encode(), "ecb_press", UTC)

    def test_unknown_feed_not_accepted(self):
        with self.assertRaises(InputError):
            news.prepare({"unknown_feed": rss("ecb_press")},
                         captured_at_utc=UTC, collection_mode="LOCAL_COPY")

    def test_invalid_capture_date_rejected(self):
        with self.assertRaises(InputError):
            news.prepare(sources(), captured_at_utc="2026-11-13T12:00:00+09:00",
                         collection_mode="LOCAL_COPY")

    def test_overly_large_xml_fails_before_parse(self):
        with self.assertRaises(InputError):
            news._parse_news(b"X" * (news.MAX_XML+1), "ecb_press", UTC)

    def test_no_implicit_network(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "snap"
            with patch.object(news, "_download",
                              side_effect=AssertionError("network attempted")):
                with patch("sys.stdout", new_callable=io.StringIO) as buf:
                    rc = news.main(["--out-dir", str(out)])
            self.assertEqual(rc, 2)
            self.assertFalse(out.exists())
            self.assertIn("FAIL_CLOSED", buf.getvalue())

    def test_offline_local_copy_validates_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            xml = root / "ECB.xml"
            xml.write_bytes(rss("ecb_press"))
            out = root / "snap"
            with patch.object(news, "_download",
                              side_effect=AssertionError("network attempted")):
                with patch.object(news, "_now", return_value=UTC):
                    with patch("sys.stdout", new_callable=io.StringIO) as buf:
                        rc = news.main([
                            "--out-dir", str(out),
                            "--feed-file", "ecb_press="+str(xml)])
            self.assertEqual(rc, 0)
            self.assertEqual(news.verify(out)["feed_count"], 1)
            self.assertEqual(xml.read_bytes(), rss("ecb_press"))
            self.assertTrue(json.loads(buf.getvalue())["snapshot_dir_created"])

    def test_network_is_one_explicit_call_per_feed(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "snap"
            with patch.object(news, "_download",
                              side_effect=lambda feed: rss(feed)) as down:
                with patch.object(news, "_now", return_value=UTC):
                    with patch("sys.stdout", new_callable=io.StringIO) as buf:
                        rc = news.main([
                            "--out-dir", str(out), "--allow-network",
                            "--feed", "ecb_press",
                            "--feed", "boj_whatsnew"])
            self.assertEqual(rc, 0)
            self.assertEqual(down.call_count, 2)
            self.assertEqual(news.verify(out)["feed_count"], 2)
            self.assertEqual(json.loads(buf.getvalue())["status"],
                             "MULTI_OFFICIAL_NEWS_SNAPSHOT_RESEARCH_HOLD_NO_GO")

    def test_network_aborts_without_complete_snapshot_if_second_feed_fails(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "snap"
            def mock(feed):
                if feed == "ecb_press":
                    raise InputError("HTTP 403")
                return rss(feed)
            with patch.object(news, "_download", side_effect=mock):
                with patch("sys.stdout", new_callable=io.StringIO) as buf:
                    rc = news.main([
                        "--out-dir", str(out), "--allow-network",
                        "--feed", "boj_whatsnew", "--feed", "ecb_press"])
            self.assertEqual(rc, 2)
            self.assertFalse(out.exists())
            self.assertFalse(json.loads(buf.getvalue())["real_orders_permitted"])

    def test_existing_dir_blocks_fetch_before_network(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "snap"
            out.mkdir()
            with patch.object(news, "_download",
                              side_effect=AssertionError("network called")):
                with patch("sys.stdout", new_callable=io.StringIO) as buf:
                    code = news.main([
                        "--out-dir", str(out),
                        "--allow-network", "--feed", "ecb_press"])
            self.assertEqual(code, 2)
            self.assertEqual(set(out.iterdir()), set())

    def test_offline_bundle_tampering_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = sources()
            m = news.prepare(raw, captured_at_utc=UTC,
                             collection_mode="LOCAL_COPY")
            out = root / "snap"
            news.save(out, raw, m)
            p = out / "boj_whatsnew.xml"
            p.write_bytes(p.read_bytes() + b"\\nchanged")
            with self.assertRaises(InputError):
                news.verify(out)

    def test_manifest_forged_go_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = sources()
            m = news.prepare(raw, captured_at_utc=UTC,
                             collection_mode="LOCAL_COPY")
            out = root / "snap"
            news.save(out, raw, m)
            fp = out / "manifest.json"
            data = json.loads(fp.read_text())
            data["real_orders_permitted"] = True
            fp.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(InputError):
                news.verify(out)

    def test_missing_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = sources()
            m = news.prepare(raw, captured_at_utc=UTC,
                             collection_mode="LOCAL_COPY")
            out = root / "snap"
            news.save(out, raw, m)
            (out / "manifest.json").unlink()
            with self.assertRaises(InputError):
                news.verify(out)

    def test_verify_cli_does_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = sources()
            m = news.prepare(raw, captured_at_utc=UTC,
                             collection_mode="LOCAL_COPY")
            out = root / "snap"
            news.save(out, raw, m)
            before = {p.name: p.read_bytes() for p in out.iterdir()}
            with patch("sys.stdout", new_callable=io.StringIO) as buf:
                rc = news.main(["--verify-bundle", str(out)])
            self.assertEqual(rc, 0)
            r = json.loads(buf.getvalue())
            self.assertEqual(r["files_written_this_run"], 0)
            self.assertEqual(r["network_calls_this_run"], 0)
            self.assertFalse(r["real_orders_permitted"])
            self.assertEqual(before, {p.name:p.read_bytes() for p in out.iterdir()})

    def test_mutual_exclusive_mode_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "feed.xml"
            f.write_bytes(rss("ecb_press"))
            with patch("sys.stdout", new_callable=io.StringIO) as buf:
                rc = news.main([
                    "--out-dir", str(root / "snap"),
                    "--allow-network", "--feed-file", "ecb_press="+str(f)])
            self.assertEqual(rc, 2)
            self.assertFalse((root / "snap").exists())


class ResearchBoardNewsBindings(unittest.TestCase):
    VERIFIED = {
        "feed_count": 3,
        "news_items_count": 6,
        "observed_regions": {"USD": 1, "EUR": 1, "JPY": 1},
    }

    def test_global_board_keeps_news_separate_from_future_events(self):
        with patch.object(global_macro.official_news, "verify",
                          return_value=self.VERIFIED) as v:
            r = global_macro.inspect(
                asof_utc=UTC,
                official_news_bundle=Path("out/fake-news-snapshot"))
        v.assert_called_once()
        self.assertTrue(r["official_news_bundle_verified"])
        self.assertEqual(r["official_news_feed_count"], 3)
        self.assertEqual(r["external_event_observations_supplied"], 0)
        self.assertIn("PUBLISHED_RSS_NEWS_CANNOT_REPLACE_FUTURE_EVENT_CALENDAR",
                      r["unresolved_holds"])
        self.assertFalse(r["official_news_provides_upcoming_events_or_consensus"])
        self.assertFalse(r["demo_orders_permitted"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_integrated_board_adds_news_but_never_marks_schedule_complete(self):
        campaign = {
            "unresolved_warnings_and_safety_holds": ["PRICE_UNVERIFIED"],
            "next_research_actions": [],
            "price_csv_count": 114,
            "complete_cycle_count": 0,
            "observed_macro_event_count": 0,
            "review_count": 0,
            "descriptive_two_snapshot_mark_count": 0,
        }
        with patch.object(integrated, "campaign", return_value=campaign):
            with patch.object(integrated.official_news, "verify",
                              return_value=self.VERIFIED):
                r = integrated.inspect(
                    [("live", Path("out/placeholder"))],
                    asof_utc=UTC,
                    official_news_bundle=Path("out/fake-news-snapshot"))
        self.assertEqual(r["official_news_item_count"], 6)
        self.assertEqual(r["scheduled_bls_event_count"], 0)
        self.assertIn("OFFICIAL_RSS_NEWS_NOT_A_FUTURE_MACRO_CALENDAR",
                      r["unresolved_holds"])
        self.assertFalse(r["official_news_calendar_or_consensus_sufficient"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertFalse(r["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
