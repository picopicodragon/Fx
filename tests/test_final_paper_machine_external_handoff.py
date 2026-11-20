"""Physical-machine handoff and public external evidence fail-closed tests."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research import final_paper_public_source_snapshot as official
from research import final_paper_openai_costs_readonly as costs

NOW = datetime(2026, 11, 20, 1, 0, tzinfo=timezone.utc)


class OfficialSnapshotTests(unittest.TestCase):
    def test_network_is_explicit_and_no_coverage_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(official.SnapshotError):
                official.snapshot(root / "archive", now=NOW)
            called = []
            def fake(url):
                called.append(url)
                return b"official public bytes", "Fri, 20 Nov 2026 01:00:00 GMT"
            result = official.snapshot(root / "archive",
                                      allow_network=True,
                                      now=NOW, fetcher=fake)
            self.assertEqual(len(called), len(official.SOURCES))
            self.assertEqual(result["archived_count"], len(official.SOURCES))
            self.assertFalse(result["all_important_usd_eur_jpy_events_covered"])
            self.assertFalse(result["broker_clock_independently_verified"])
            self.assertFalse(result["new_virtual_positions_allowed"])
            self.assertFalse(result["new_paid_ai_calls_allowed"])
            file = root/"archive"/"us_bls_calendar_ics.ics"
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),
                result["sources"][0]["sha256_local_only"])
            with self.assertRaises(official.SnapshotError):
                official.snapshot(root / "archive", allow_network=True,
                                  fetcher=fake, now=NOW)

    def test_partial_official_network_failure_does_not_claim_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            def partial(url):
                if "ecb.europa.eu" in url:
                    raise official.SnapshotError("offline")
                return b"source", ""
            result = official.snapshot(Path(temp)/"partial",
                                      allow_network=True,
                                      now=NOW, fetcher=partial)
            self.assertEqual(result["archived_count"],
                             len(official.SOURCES)-1)
            self.assertIn("eur_ecb_calendar",result["failed_source_ids"])
            self.assertEqual(result["status"],
                             "PUBLIC_OFFICIAL_SOURCE_ARCHIVE_PARTIAL_NO_GO")
            self.assertFalse(result["consensus_point_in_time_verified"])


class ProviderCostTests(unittest.TestCase):
    def test_usd_amount_read_but_jpy_and_fx_scope_not_verifiable(self):
        response = {
            "data":[
                {"results":[
                    {"object":"organization.costs.result",
                     "amount":{"currency":"usd","value":1.25}}
                ]},
                {"results":[
                    {"object":"organization.costs.result",
                     "amount":{"currency":"usd","value":0.75}}
                ]},
            ],
            "has_more":False,
        }
        class MockReply:
            def __init__(self, req):
                self.req=req
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def geturl(self):return self.req.full_url
            def read(self, n):return json.dumps(response).encode("utf-8")
        def fake(req, timeout):
            self.assertEqual(req.get_method(), "GET")
            self.assertIn("/v1/organization/costs?",req.full_url)
            self.assertEqual(timeout,20)
            return MockReply(req)
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/"provider.json"
            with patch.dict(os.environ,{"OPENAI_ADMIN_KEY":"sk-admin_testing_123456789"}):
                with self.assertRaises(costs.CostEvidenceError):
                    costs.run(target,now=NOW,fetch=fake)
                result=costs.run(target,allow_network=True,
                                 now=NOW,fetch=fake)
            self.assertEqual(result["provider_reported_organization_cost_usd"],
                             "2.00")
            self.assertFalse(result["fx_project_cost_isolated"])
            self.assertFalse(result["monthly_3000_jpy_compliance_verified"])
            self.assertFalse(result["further_paid_api_calls_approved"])
            self.assertFalse(result["new_virtual_positions_permitted"])

    def test_pagination_or_non_usd_is_fail_closed(self):
        for payload in (
            {"data":[{"results":[]}],"has_more":True},
            {"data":[{"results":[{"object":"organization.costs.result",
                    "amount":{"currency":"jpy","value":99}}]}],
             "has_more":False},
            {"data":[{"results":[{"object":"organization.costs.result",
                    "amount":{"currency":"usd","value":-1}}]}],
             "has_more":False},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(costs.CostEvidenceError):
                    costs.parse_costs(payload)

    def test_windows_script_does_not_change_live_supervisor(self):
        script=(Path(__file__).resolve().parents[1]/
                "scripts/final_paper_local_machine_handoff_once.ps1").read_text(
                encoding="utf-8")
        self.assertIn("Get-CimInstance Win32_Process",script)
        self.assertIn("Get-FileHash",script)
        self.assertIn("w32tm.exe /query /status",script)
        for forbidden in (
            "Stop-Process", "Start-Process", "Remove-Item",
            "OrderSend", "OrderClose", "OPENAI_ADMIN_KEY",
            "Invoke-RestMethod", "Set-ExecutionPolicy",
        ):
            self.assertNotIn(forbidden,script)
        for name in (
            "research/final_paper_public_source_snapshot.py",
            "research/final_paper_openai_costs_readonly.py"
        ):
            code=(Path(__file__).resolve().parents[1]/name).read_text(
                encoding="utf-8")
            for forbidden in ("OrderSend(", "OrderClose(", "ai.run(",
                              "allow_external_api=True", "lock.unlink("):
                self.assertNotIn(forbidden,code)


if __name__ == "__main__":
    unittest.main()
