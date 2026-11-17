"""FWD-1487: immutable offline ECB link diagnosis regressions."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_ecb_link_diagnostic as diag


def xml(links):
    pieces = [
        '<rss version="2.0"><channel><title>ECB</title>'
    ]
    for value in links:
        escaped = value.replace("&", "&amp;")
        pieces.append('<item><title>News</title><link>' + escaped
                      + '</link></item>')
    pieces.append('</channel></rss>')
    return ''.join(pieces).encode("utf-8")


class ECBSavedXMLDiagnostics(unittest.TestCase):
    def test_ecb_and_other_europa_host_are_not_equated(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "ecb.xml"
            raw = xml([
                "https://www.ecb.europa.eu/press/news.html",
                "https://www.bankingsupervision.europa.eu/press/news.html",
                "https://www.ecb.europa.eu/press/second.html",
            ])
            file.write_bytes(raw)
            report = diag.inspect_file(file)
            self.assertEqual(report["status"], "ECB_SAVED_XML_LINK_DIAGNOSTIC_NO_GO")
            self.assertEqual(report["item_count"], 3)
            self.assertEqual(report["items_not_matching_existing_allowlist"], 1)
            by_host = {r["hostname_unverified"]: r for r in report["link_groups"]}
            self.assertEqual(by_host["www.ecb.europa.eu"]["count"], 2)
            self.assertEqual(by_host["www.bankingsupervision.europa.eu"][
                "validation_reason"], "OFF_HOST_REJECTED")
            self.assertEqual(report["original_sha256_local_only"],
                             hashlib.sha256(raw).hexdigest())
            self.assertTrue(report["hostnames_are_not_authenticated_or_approved"])
            self.assertEqual(report["network_calls_this_run"], 0)
            self.assertEqual(report["journal_writes_this_run"], 0)
            self.assertEqual(report["orders_sent_this_run"], 0)
            self.assertFalse(report["real_orders_permitted"])

    def test_unsafe_url_forms_are_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"ecb.xml"
            file.write_bytes(xml([
                "http://www.ecb.europa.eu/article",
                "https://user:token@www.ecb.europa.eu/article",
                "https://www.ecb.europa.eu:8443/article",
                "https://bad.example.com/secret?q=private",
                "https://www.ecb.europa.eu/article#section",
                "/relative-path",
            ]))
            result=diag.inspect_file(file)
            reasons={x["validation_reason"] for x in result["link_groups"]}
            self.assertIn("NON_HTTPS_REJECTED",reasons)
            self.assertIn("PORT_OR_CREDENTIALS_REJECTED",reasons)
            self.assertIn("OFF_HOST_REJECTED",reasons)
            self.assertIn("FRAGMENT_REJECTED",reasons)
            self.assertEqual(result["items_not_matching_existing_allowlist"],6)
            encoded=json.dumps(result)
            self.assertNotIn("token",encoded)
            self.assertNotIn("bad.example.com",encoded)
            self.assertNotIn("private",encoded)

    def test_exact_path_shape_and_duplicate_counts_without_leaking_links(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"ecb.xml"
            raw=xml([
                "https://www.ecb.europa.eu",
                "https://www.ecb.europa.eu//press/release-1.html",
                "https://www.ecb.europa.eu//press/release-1.html",
                "https://www.ecb.europa.eu/press/release-2.html",
            ])
            file.write_bytes(raw)
            report=diag.inspect_file(file)
            groups={v["validation_reason"]:v["count"] for v in report["link_groups"]}
            self.assertEqual(groups["EMPTY_URL_PATH"],1)
            self.assertEqual(groups["ECB_LEGACY_PATH_PRESERVED_METADATA_ONLY"],2)
            self.assertEqual(groups["ALLOWLIST_MATCHED"],1)
            self.assertEqual(report["item_count"],4)
            self.assertEqual(report["distinct_link_count"],3)
            self.assertEqual(report["items_not_matching_existing_allowlist"],1)
            self.assertNotIn("release-1",json.dumps(report))
            self.assertEqual(file.read_bytes(),raw)
            self.assertFalse(report["real_orders_permitted"])

    def test_missing_file_or_doctype_remains_fail_closed_without_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            missing=root/"missing.xml"
            self.assertEqual(diag.main(["--xml-file",str(missing)]),2)
            file=root/"bad.xml"
            file.write_bytes(b'<!DOCTYPE rss><rss><channel/></rss>')
            with self.assertRaises(Exception):
                diag.inspect_file(file)
            self.assertEqual(sorted(p.name for p in root.iterdir()),["bad.xml"])

    def test_atom_alternate_link_is_summarized_without_authorization(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"ecb.xml"
            file.write_text('''<feed xmlns="http://www.w3.org/2005/Atom">
              <entry><link rel="alternate"
              href="https://www.ecb.europa.eu/press/one.html" /></entry>
            </feed>''',encoding="utf-8")
            result=diag.inspect_file(file)
            self.assertEqual(result["item_count"],1)
            self.assertEqual(result["items_not_matching_existing_allowlist"],0)
            self.assertEqual(result["runtime_go_no_go"],"NO_GO")
            self.assertFalse(result["demo_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
