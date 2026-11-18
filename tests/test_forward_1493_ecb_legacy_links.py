"""FWD-1493: bounded ECB double-slash RSS URL acceptance, research-only."""
from __future__ import annotations

import email.utils
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import forward_macro_feed_once as feed
from research import forward_multi_official_news_snapshot as news
from research import forward_observation as obs
from research.offline_backtest import InputError

NOW = datetime(2026, 11, 17, 5, 0, tzinfo=timezone.utc)


def fixture(links: list[str]) -> bytes:
    published = email.utils.format_datetime(NOW - timedelta(hours=3))
    pieces = ['<rss version="2.0"><channel><title>ECB</title>']
    for i, link in enumerate(links):
        pieces.append(
            '<item><title>Original ECB item ' + str(i) + '</title>'
            '<link>' + link.replace("&", "&amp;") + '</link>'
            '<pubDate>' + published + '</pubDate></item>')
    pieces.append('</channel></rss>')
    return ''.join(pieces).encode('utf-8')


class ECBDoubleSlashFeedTests(unittest.TestCase):
    def test_15_unique_original_paths_preserved_in_validated_bundle_without_journal(self):
        links = [
            'https://www.ecb.europa.eu//press/pr/date/2026/html/'
            'ecb.pr2601' + str(i) + '.en.html'
            for i in range(15)
        ]
        raw = fixture(links)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store = root / 'macro_journal'
            obs.initialize(store, 'ecb_safe_test', now=NOW - timedelta(days=1))
            src = root / 'ecb.xml'
            src.write_bytes(raw)
            result = feed.run(store, root / 'archive', ['ecb_press'],
                              xml_files={'ecb_press': src}, clock=lambda: NOW)
            self.assertEqual(result['status'], 'OFFICIAL_FEEDS_ARCHIVED_HOLD_NO_GO')
            self.assertEqual(result['feed_bundles_verified_format'], 1)
            self.assertEqual(result['feeds'][0]['fetched_news_items'], 15)
            self.assertEqual(result['new_recent_us_journal_records'], 0)
            self.assertEqual(result['network_calls_attempted'], 0)
            self.assertEqual(result['orders_sent_this_run'], 0)
            self.assertFalse(result['demo_orders_permitted'])
            self.assertFalse(result['real_orders_permitted'])
            self.assertEqual(obs.audit(store)['record_count'], 0)
            saved = root / 'archive' / 'ecb_press'
            self.assertEqual((saved / 'ecb_press.xml').read_bytes(), raw)
            self.assertEqual(news.verify(saved)['feed_count'], 1)
            manifest = json.loads((saved / 'manifest.json').read_text())
            self.assertEqual(
                manifest['feeds']['ecb_press']['source_sha256'],
                hashlib.sha256(raw).hexdigest())
            self.assertEqual(
                [item['link'] for item in
                 manifest['feeds']['ecb_press']['news_items_unverified']],
                links)

    def test_external_hosts_and_ambiguous_double_slash_still_rejected(self):
        invalid = [
            'https://www.ecb.europa.eu///press/a.html',
            'https://www.ecb.europa.eu//evil.example/x',
            'https://www.ecb.europa.eu//press//a.html',
            'https://www.ecb.europa.eu//press/../admin.html',
            'https://www.ecb.europa.eu//press/%2fsecret.html',
            'https://www.ecb.europa.eu//press/back\\slash.html',
            'https://www.ecb.europa.eu//',
            'https://www.ecb.europa.eu//other/a.html',
            'https://other.ecb.europa.eu//press/a.html',
            'http://www.ecb.europa.eu//press/a.html',
            'https://user:pass@www.ecb.europa.eu//press/a.html',
            'https://www.ecb.europa.eu:9443//press/a.html',
            'https://www.ecb.europa.eu//press/a.html#fragment',
        ]
        for url in invalid:
            with self.subTest(url=url):
                with self.assertRaises(InputError):
                    news._link(url, 'ecb_press')

    def test_other_feeds_never_gain_double_slash_exception(self):
        for region in ('fed_policy', 'bls_cpi', 'bls_empsit', 'boj_whatsnew'):
            with self.subTest(feed=region):
                uri = 'https://' + news.SOURCE_HOSTS[region] + '//press/a.html'
                with self.assertRaises(InputError):
                    news._link(uri, region)

    def test_normal_original_links_still_accepted_with_no_rewrite(self):
        for uri in ('https://www.ecb.europa.eu/press/a.html',
                    'https://www.ecb.europa.eu//press/a.html',
                    'https://www.ecb.europa.eu//home/html/a.html'):
            with self.subTest(uri=uri):
                self.assertEqual(news._link(uri, 'ecb_press'), uri)


if __name__ == '__main__':
    unittest.main()
