"""P0-01 D4-2 independent authorization invariants."""
import unittest

from scripts.p0_01_offline_approval_gate import (
    deny_all, invariant_holds, REVIEW, PENDING
)
from scripts.p0_01_offline_five_field_mock import PAIRS, FIELDS
from scripts.p0_01_offline_provenance_guard import EXPECTED_UNITS


def synthetic():
    return [{"symbol": p, "properties": {
        "min_lot": "0.1", "lot_step": "0.01",
        "point_quote": "0.001", "tick_size_points": "1",
        "tick_value_deposit_currency": "10"}} for p in PAIRS]


def candidate():
    return {"origin": "MANUAL_UNVERIFIED",
            "observed_at": "2026-10-28T00:00:00+00:00",
            "evidence_kind": "MANUAL_SCREEN_NOTE_UNVERIFIED",
            "account_currency": "JPY", "contract_basis_confirmed": False,
            "symbols": [dict(symbol=row["symbol"], properties=row["properties"],
                             units=dict(EXPECTED_UNITS)) for row in synthetic()]}


class OfflineApprovalGateTests(unittest.TestCase):
    def test_synthetic_pass_still_blocked(self):
        result = deny_all("SYNTHETIC", synthetic())
        self.assertEqual(result["status"], PENDING)
        self.assertTrue(invariant_holds(result))

    def test_candidate_pass_still_blocked(self):
        result = deny_all("MANUAL_CANDIDATE", candidate(),
                          "2026-10-28T01:00:00+00:00")
        self.assertEqual(result["status"], PENDING)
        self.assertTrue(invariant_holds(result))

    def test_unknown_stage_and_fake_approval_cannot_promote(self):
        for stage in ("BROKER_VERIFIED", "LIVE", "", None, False, 1):
            with self.subTest(stage=repr(stage)):
                result = deny_all(stage, {"approved": True})
                self.assertEqual(result["status"], REVIEW)
                self.assertTrue(invariant_holds(result))

    def test_payload_injection_does_not_grant_permission(self):
        payload = candidate()
        payload["forward_trading_enabled"] = True
        result = deny_all("MANUAL_CANDIDATE", payload,
                          "2026-10-28T01:00:00+00:00")
        self.assertEqual(result["status"], REVIEW)
        self.assertTrue(invariant_holds(result))

    def test_bad_input_never_echoed(self):
        result = deny_all("SYNTHETIC", "SECRET_ACCOUNT_PAYLOAD")
        self.assertNotIn("SECRET_ACCOUNT_PAYLOAD", repr(result))
        self.assertTrue(invariant_holds(result))

    def test_invariant_rejects_mutated_authority(self):
        original = deny_all("SYNTHETIC", synthetic())
        for key in ("broker_verified", "production_usable", "orders_generated",
                    "terminal_execution_approved", "forward_trading_enabled"):
            mutated = dict(original, **{key: True})
            with self.subTest(key=key):
                self.assertFalse(invariant_holds(mutated))

    def test_invariant_rejects_phase_and_schema_tampering(self):
        base = deny_all("SYNTHETIC", synthetic())
        self.assertFalse(invariant_holds(dict(base, phase_1="APPROVED")))
        self.assertFalse(invariant_holds(dict(base, status="BROKER_VERIFIED")))
        self.assertFalse(invariant_holds(dict(base, extra=True)))
        altered = dict(base)
        del altered["orders_generated"]
        self.assertFalse(invariant_holds(altered))

    def test_no_external_runtime_or_file_io(self):
        import inspect
        import scripts.p0_01_offline_approval_gate as module
        src = inspect.getsource(module)
        for needle in ("import socket", "import requests", "import subprocess",
                       "import MetaTrader5", "OrderSend(", "MarketInfo(",
                       "open(", "write_text(", "read_text("):
            self.assertNotIn(needle, src)


if __name__ == "__main__":
    unittest.main()
