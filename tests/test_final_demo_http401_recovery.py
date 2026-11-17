"""Recovery after definite HTTP401: no inference, ledger deletion or auto retry."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import final_demo_http401_recovery as recovery
from research import final_demo_periodic_ai as pipeline
from research.offline_backtest import InputError


class _FakeHTTPResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return json.dumps({"data": [
            {"id": "research-analysis"},
            {"id": "research-reviewer"}]}).encode()


def _pending(root: Path) -> Path:
    ledger = root / "ai_USDJPY_20261117_170000_000.json"
    ledger.write_text(json.dumps({
        "schema": pipeline.SCHEMA,
        "packet_sha256": "0" * 64,
        "analyst_model": "research-analysis",
        "reviewer_model": "research-reviewer",
        "stage": "ANALYST_PENDING",
        "pending_role": "analyst",
        "analyst": None,
        "reviewer": None,
        "execution_authorized": False,
        "real_orders_permitted": False,
    }), encoding="utf-8")
    return ledger


class HTTP401RecoveryTests(unittest.TestCase):
    def test_explicit_http401_restores_only_manual_next_cycle_without_modifying_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = _pending(root)
            original = ledger.read_bytes()
            with self.assertRaises(InputError):
                recovery.check_directory(root)
            with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-key"}), \
                    patch.object(recovery.urllib.request, "urlopen",
                                 return_value=_FakeHTTPResponse()) as call:
                result = recovery.review_http401(ledger, operator_confirmed=True)
                self.assertEqual(call.call_count, 1)
                request = call.call_args.args[0]
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(request.full_url,
                                 "https://api.openai.com/v1/models")
            self.assertEqual(result["authentication_http"], 200)
            self.assertEqual(result["api_inference_calls_this_run"], 0)
            self.assertEqual(ledger.read_bytes(), original)
            reviewed = recovery.check_directory(root)
            self.assertEqual(reviewed["operator_reviewed_http401"], 1)
            marker = recovery._review_path(ledger)
            self.assertTrue(marker.exists())
            self.assertNotIn("synthetic-key", marker.read_text())
            with self.assertRaises(InputError):
                recovery.review_http401(ledger, operator_confirmed=True)

    def test_requires_explicit_ack_and_never_contacts_api_implicitly(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = _pending(Path(d))
            with patch.object(recovery.urllib.request, "urlopen") as call:
                with self.assertRaises(InputError):
                    recovery.review_http401(
                        ledger, operator_confirmed=False)
                call.assert_not_called()
            self.assertFalse(recovery._review_path(ledger).exists())

    def test_readonly_check_never_calls_network(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _pending(root)
            with patch.object(recovery.urllib.request, "urlopen") as call:
                with self.assertRaises(InputError):
                    recovery.check_directory(root)
                call.assert_not_called()

    def test_bad_key_does_not_create_review_marker(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = _pending(Path(d))
            with patch.dict("os.environ", {"OPENAI_API_KEY": ""}), \
                    patch.object(recovery.urllib.request, "urlopen") as call:
                with self.assertRaises(InputError):
                    recovery.review_http401(
                        ledger, operator_confirmed=True)
                call.assert_not_called()
            self.assertFalse(recovery._review_path(ledger).exists())

    def test_model_not_listed_cannot_resolve_pending(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = _pending(Path(d))
            class UnavailableModels(_FakeHTTPResponse):
                def read(self, _limit):
                    return b'{"data":[{"id":"irrelevant"}]}'
            with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic"}), \
                    patch.object(recovery.urllib.request, "urlopen",
                                 return_value=UnavailableModels()):
                with self.assertRaises(InputError):
                    recovery.review_http401(
                        ledger, operator_confirmed=True)
            self.assertFalse(recovery._review_path(ledger).exists())

    def test_review_tied_to_exact_original_ledger_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = _pending(root)
            with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic"}), \
                    patch.object(recovery.urllib.request, "urlopen",
                                 return_value=_FakeHTTPResponse()):
                recovery.review_http401(ledger, operator_confirmed=True)
            ledger.write_bytes(ledger.read_bytes() + b" ")
            with self.assertRaises(InputError):
                recovery.check_directory(root)

    def test_reviewer_or_unacknowledged_pending_cannot_reconcile(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            ledger = _pending(root)
            state = json.loads(ledger.read_text())
            state["stage"] = "REVIEW_PENDING"
            state["pending_role"] = "reviewer"
            state["analyst"] = {
                "action": "HOLD",
                "hypothesis": "Insufficient consensus",
                "counterevidence": "No event"}
            ledger.write_text(json.dumps(state))
            with patch.object(recovery.urllib.request, "urlopen") as call:
                with self.assertRaises(InputError):
                    recovery.review_http401(
                        ledger, operator_confirmed=True)
                call.assert_not_called()
            self.assertFalse(recovery._review_path(ledger).exists())

    def test_powershell_paid_path_requires_reviewed_ledger_check(self):
        script = (Path(__file__).resolve().parents[1] /
                  "scripts" / "final_demo_periodic_once.ps1").read_text()
        self.assertIn("final_demo_http401_recovery --check-directory", script)
        self.assertIn("if ($LASTEXITCODE -ne 0)", script)
        self.assertNotIn("Remove-Item", script)


if __name__ == "__main__":
    unittest.main()
