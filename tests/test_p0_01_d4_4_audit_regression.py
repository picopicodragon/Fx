"""D4-4: repository safety audit plus mutation-focused regression tests.

Offline tests only. Read committed repository artifacts; no MT4 or private files.
"""
import copy
import json
import unittest
from pathlib import Path

from scripts.p0_01_offline_approval_gate import deny_all, invariant_holds
from scripts.p0_01_offline_five_field_mock import PAIRS, FIELDS
from scripts.p0_01_offline_provenance_guard import EXPECTED_UNITS

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "specs/p0_01_mt4_readonly_observation_plan.json"
DESIGN = ROOT / "specs/p0_01_five_field_offline_mock_design.json"


def rows():
    return [{"symbol": pair, "properties": dict(
        min_lot="0.1", lot_step="0.01", point_quote="0.001",
        tick_size_points="1", tick_value_deposit_currency="10")}
        for pair in PAIRS]


def manual():
    return {
        "origin": "MANUAL_UNVERIFIED",
        "observed_at": "2026-10-28T00:00:00+00:00",
        "evidence_kind": "MANUAL_SCREEN_NOTE_UNVERIFIED",
        "account_currency": "JPY",
        "contract_basis_confirmed": False,
        "symbols": [{"symbol": r["symbol"], "properties": dict(r["properties"]),
                     "units": dict(EXPECTED_UNITS)} for r in rows()],
    }


class AuditSafetyInvariants(unittest.TestCase):
    def test_committed_observations_remain_null(self):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.assertEqual({x["symbol"] for x in plan["symbol_status"]}, set(PAIRS))
        for entry in plan["symbol_status"]:
            self.assertIs(entry["production_usable"], False)
            self.assertEqual(set(entry["verified_values"]), set(FIELDS))
            self.assertTrue(all(v is None for v in entry["verified_values"].values()))

    def test_design_authority_remains_blocked(self):
        design = json.loads(DESIGN.read_text(encoding="utf-8"))
        safety = design["safety"]
        self.assertEqual(safety["phase_1"], "BLOCKED")
        for key in ("broker_queried", "orders_generated", "terminal_deployed",
                    "terminal_execution_approved", "forward_trading_enabled",
                    "implementation_approved", "human_safety_approval"):
            self.assertIs(safety[key], False)

    def test_output_authorization_invariants_both_stages(self):
        for stage, payload, timestamp in (
            ("SYNTHETIC", rows(), None),
            ("MANUAL_CANDIDATE", manual(), "2026-10-28T01:00:00+00:00"),
        ):
            with self.subTest(stage=stage):
                report = deny_all(stage, payload, timestamp)
                self.assertTrue(invariant_holds(report))
                self.assertEqual(report["phase_1"], "BLOCKED")

    def test_mutated_result_permission_rejected(self):
        report = deny_all("SYNTHETIC", rows())
        for key in ("broker_verified", "production_usable", "orders_generated",
                    "terminal_execution_approved", "forward_trading_enabled"):
            with self.subTest(key=key):
                altered = dict(report)
                altered[key] = True
                self.assertFalse(invariant_holds(altered))

    def test_result_schema_mutations_rejected(self):
        report = deny_all("SYNTHETIC", rows())
        for change in ("status", "phase", "key", "missing"):
            mutated = dict(report)
            if change == "status":
                mutated["status"] = "BROKER_VERIFIED"
            elif change == "phase":
                mutated["phase_1"] = "RUNNING"
            elif change == "key":
                mutated["approval"] = True
            else:
                mutated.pop("broker_verified")
            self.assertFalse(invariant_holds(mutated))

    def test_input_authorization_injection_rejected(self):
        value = manual()
        for key in ("broker_verified", "production_usable",
                    "forward_trading_enabled", "human_safety_approval"):
            altered = copy.deepcopy(value)
            altered[key] = True
            self.assertEqual(
                deny_all("MANUAL_CANDIDATE", altered,
                         "2026-10-28T01:00:00+00:00")["status"],
                "REVIEW_REQUIRED")

    def test_audit_source_does_not_use_sensitive_runtime_interfaces(self):
        source_paths = (
            ROOT / "scripts/p0_01_offline_five_field_mock.py",
            ROOT / "scripts/p0_01_offline_provenance_guard.py",
            ROOT / "scripts/p0_01_offline_approval_gate.py",
        )
        forbidden = ("import socket", "import requests", "import MetaTrader5",
                     "import subprocess", "OrderSend(", "MarketInfo(", "FileOpen(")
        for path in source_paths:
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                with self.subTest(module=path.name, token=token):
                    self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
