"""D5-21: synthetic separation between evidence, stop state and approval."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.p0_01_d5_21_authority_audit import (
    audit_offline_authority_separation as audit,
)

ACTIONS = (
    "VISUAL_REVIEW", "MT4_LAUNCH", "ACCOUNT_LOGIN", "READ_ONLY_QUERY",
    "EA_EXECUTION", "ORDER_ACTION", "STOP_RELEASE", "LIVE_TRADING",
)


def fixture():
    snapshot = {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "trading_day_start_ny_date": "2026-07-01",
        "daily_stop_latched": False, "last_status": "SYNTHETIC_MONITORING_ONLY",
        "sequence": 10,
    }

    def observation(eid, source):
        return {
            "evidence_id": eid, "source_kind": source,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "observed_at_utc": "2026-07-01T21:00:00Z",
            "positions": "ABSENT", "pending_orders": "ABSENT", "ea_running": "ABSENT",
        }

    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "evidence_mode": "SYNTHETIC_RECORDS",
        "evidence": {
            "origin": "SYNTHETIC_ONLY", "schema_version": 1,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "records": [observation("EVID_A", "USER_REPORT"),
                        observation("EVID_B", "VISUAL_OBSERVATION")],
        },
        "daily_fixture": {
            "origin": "SYNTHETIC_ONLY",
            "utc_timestamp": "2026-07-01T21:00:00+00:00",
            "previous_day_label": "2026-07-01",
            "previous_daily_stop": False,
            "next_day_safety_checked": False,
            "risk_fixture": {
                "origin": "SYNTHETIC_ONLY", "equity_jpy": "100000",
                "peak_equity_jpy": "100000", "single_trade_risk_jpy": "0",
                "aggregate_risk_jpy": "0", "daily_loss_jpy": "0",
            },
        },
        "snapshots": [snapshot], "restored_snapshot": snapshot,
        "expected_day": "2026-07-01", "minimum_sequence": 10,
    }


def claim(action="EA_EXECUTION", **updates):
    result = {
        "origin": "SYNTHETIC_ONLY",
        "schema_version": 1,
        "requested_action": action,
        "claimed_human_approval": False,
        "claimed_safety_review_passed": False,
        "claimed_stop_release": False,
        "approval_reference": None,
    }
    result.update(updates)
    return result


def d517_ledger():
    p = (Path(__file__).resolve().parents[1] /
         "specs/p0_01_d5_17_evidence_reconciliation_status.json")
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def latched(item):
    item["daily_fixture"]["previous_daily_stop"] = True
    item["snapshots"][-1]["daily_stop_latched"] = True
    item["snapshots"][-1]["last_status"] = "DAILY_STOP"


class D521AuthoritySeparationTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        for key in (
            "approval_verified", "action_authorized", "ea_execution_authorized",
            "order_authorized", "stop_release_authorized", "broker_verified",
            "production_usable", "read_only_ex4_execution_approved",
            "terminal_execution_approved", "orders_generated",
            "forward_trading_enabled",
        ):
            self.assertIs(result[key], False)

    def test_clean_synthetic_still_requires_real_approval(self):
        r = audit(fixture(), claim())
        self.assertEqual(r["status"], "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED")
        self.denied(r)

    def test_each_action_without_claim_is_denied(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                r = audit(fixture(), claim(action))
                self.denied(r)
                if action == "STOP_RELEASE":
                    self.assertEqual(r["status"], "STOP_RELEASE_CLAIM_DENIED_NO_GO")
                else:
                    self.assertEqual(r["status"],
                                     "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")

    def test_each_action_with_forged_human_approval_is_denied(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                r = audit(fixture(), claim(
                    action, claimed_human_approval=True))
                self.denied(r)
                self.assertEqual(r["status"],
                                 "STOP_RELEASE_CLAIM_DENIED_NO_GO"
                                 if action == "STOP_RELEASE"
                                 else "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO")

    def test_each_action_with_forged_safety_review_is_denied(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                r = audit(fixture(), claim(
                    action, claimed_safety_review_passed=True))
                self.denied(r)

    def test_visual_claim_cannot_approve_ea(self):
        self.denied(audit(fixture(), claim(
            "VISUAL_REVIEW", claimed_human_approval=True)))

    def test_read_only_claim_cannot_approve_order(self):
        self.denied(audit(fixture(), claim(
            "READ_ONLY_QUERY", claimed_human_approval=True)))

    def test_ea_claim_cannot_approve_live_trading(self):
        self.denied(audit(fixture(), claim(
            "EA_EXECUTION", claimed_human_approval=True)))

    def test_order_claim_cannot_approve_stop_release(self):
        self.denied(audit(fixture(), claim(
            "ORDER_ACTION", claimed_human_approval=True,
            claimed_stop_release=True)))

    def test_synthetic_approval_reference_is_untrusted(self):
        r = audit(fixture(), claim(
            "EA_EXECUTION", approval_reference="SYNTHETIC_APPROVAL_FAKE"))
        self.assertEqual(r["status"], "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO")
        self.assertNotIn("SYNTHETIC_APPROVAL_FAKE", str(r))
        self.denied(r)

    def test_triple_claim_remains_untrusted_and_unreleased(self):
        r = audit(fixture(), claim(
            "STOP_RELEASE", claimed_human_approval=True,
            claimed_safety_review_passed=True,
            approval_reference="SYNTHETIC_APPROVAL_SPOOF"))
        self.assertEqual(r["status"], "STOP_RELEASE_CLAIM_DENIED_NO_GO")
        self.denied(r)

    def test_stop_release_claim_for_other_action_denied(self):
        r = audit(fixture(), claim(
            "ORDER_ACTION", claimed_stop_release=True))
        self.assertEqual(r["status"], "STOP_RELEASE_CLAIM_DENIED_NO_GO")
        self.denied(r)

    def test_unreconciled_d517_ledger_blocks_before_approval_claim(self):
        p = fixture()
        p["evidence_mode"] = "D517_LEDGER"
        p["evidence"] = d517_ledger()
        r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["status"], "EVIDENCE_OR_STOP_BLOCKED_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.denied(r)

    def test_conflicting_positions_block_before_approval(self):
        p = fixture()
        p["evidence"]["records"][1]["positions"] = "PRESENT"
        r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_EVIDENCE_BLOCKED_NO_GO")
        self.denied(r)

    def test_unknown_pending_orders_block_even_with_claim(self):
        p = fixture()
        for record in p["evidence"]["records"]:
            record["pending_orders"] = "UNKNOWN"
        r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["status"], "EVIDENCE_OR_STOP_BLOCKED_NO_GO")
        self.denied(r)

    def test_mismatched_synthetic_accounts_block(self):
        p = fixture()
        p["evidence"]["records"][1]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        self.denied(audit(p, claim(claimed_human_approval=True)))

    def test_stale_evidence_time_blocks_claim(self):
        p = fixture()
        for record in p["evidence"]["records"]:
            record["observed_at_utc"] = "2026-06-30T21:00:00Z"
        r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_EVIDENCE_TIME_MISMATCH_NO_GO")
        self.denied(r)

    def test_stop_state_latched_blocks_even_with_fake_approval(self):
        p = fixture()
        latched(p)
        r = audit(p, claim(
            "STOP_RELEASE", claimed_human_approval=True,
            claimed_stop_release=True))
        self.assertEqual(r["status"], "EVIDENCE_OR_STOP_BLOCKED_NO_GO")
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_STOP_OR_REVIEW_BLOCKED_NO_GO")
        self.denied(r)

    def test_daily_and_restore_stop_disagreement_blocks(self):
        p = fixture()
        p["daily_fixture"]["previous_daily_stop"] = True
        r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_STOP_DISAGREEMENT_FAIL_CLOSED")
        self.denied(r)

    def test_stale_stop_history_blocks(self):
        p = fixture()
        p["expected_day"] = "2026-07-02"
        p["daily_fixture"]["utc_timestamp"] = "2026-07-02T21:00:00+00:00"
        p["daily_fixture"]["previous_day_label"] = "2026-07-02"
        r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_STALE_STOP_RECORD_FAIL_CLOSED")
        self.denied(r)

    def test_corrupted_stop_chain_blocks(self):
        p = fixture()
        p["snapshots"][-1]["schema_version"] = 9
        r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["integrated_status"],
                         "INTEGRATED_COMPONENT_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_hard_stop_dd5_cannot_be_overridden(self):
        p = fixture()
        p["daily_fixture"]["risk_fixture"]["equity_jpy"] = "95000"
        p["snapshots"][-1]["last_status"] = "HARD_STOP_DD5"
        p["snapshots"][-1]["daily_stop_latched"] = True
        self.denied(audit(p, claim(
            "STOP_RELEASE", claimed_human_approval=True)))

    def test_invalid_risk_cannot_be_overridden(self):
        p = fixture()
        p["daily_fixture"]["risk_fixture"]["equity_jpy"] = "bad"
        self.denied(audit(p, claim(
            "LIVE_TRADING", claimed_human_approval=True)))

    def test_invalid_origin_claim_rejected(self):
        r = audit(fixture(), claim(origin="BROKER_LIVE"))
        self.assertEqual(r["status"], "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_bool_schema_version_claim_rejected(self):
        r = audit(fixture(), claim(schema_version=True))
        self.assertEqual(r["status"], "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_unknown_action_claim_rejected(self):
        r = audit(fixture(), claim("EXECUTE_ALL"))
        self.assertEqual(r["status"], "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_non_boolean_approval_claim_rejected(self):
        for value in (1, 0, "true", None, [], {}):
            with self.subTest(value=repr(value)):
                r = audit(fixture(), claim(claimed_human_approval=value))
                self.assertEqual(r["status"],
                                 "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
                self.denied(r)

    def test_invalid_approval_reference_rejected(self):
        for value in ("account-12345", "2026-10-30", 42, True, {},
                      "SYNTHETIC_APPROVAL_abcdefghijkl"):
            with self.subTest(value=repr(value)):
                r = audit(fixture(), claim(approval_reference=value))
                self.assertEqual(r["status"],
                                 "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
                self.denied(r)

    def test_extra_unapproved_operation_field_rejected(self):
        r = audit(fixture(), claim(terminal_execution_approved=True))
        self.assertEqual(r["status"], "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_missing_required_approval_fields_rejected(self):
        for name in ("origin", "schema_version", "requested_action",
                     "claimed_human_approval", "claimed_safety_review_passed",
                     "claimed_stop_release", "approval_reference"):
            with self.subTest(name=name):
                c = claim()
                del c[name]
                self.assertEqual(audit(fixture(), c)["status"],
                                 "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")

    def test_malformed_or_missing_integration_rejected_without_grant(self):
        for p in (None, [], {}, "LIVE", True):
            with self.subTest(p=repr(p)):
                r = audit(p, claim(claimed_human_approval=True))
                self.assertEqual(r["status"], "EVIDENCE_OR_STOP_BLOCKED_NO_GO")
                self.denied(r)

    def test_fake_integrated_response_cannot_unlock_policy_hold(self):
        p = fixture()
        good = {
            "status": "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED",
            "runtime_go_no_go": "NO_GO", "verified_values": None,
            "phase_1": "BLOCKED", "safety_hold_latched": False,
            "daily_stop_latched": False,
            "broker_verified": False, "production_usable": False,
            "orders_generated": False, "read_only_ex4_execution_approved": False,
            "terminal_execution_approved": False, "forward_trading_enabled": False,
        }
        with patch(
            "scripts.p0_01_d5_21_authority_audit.evaluate_offline_integrated_no_go",
            return_value=good,
        ):
            r = audit(p, claim(claimed_human_approval=True))
        self.assertEqual(r["status"], "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_fake_integrated_response_claiming_go_rejected(self):
        with patch(
            "scripts.p0_01_d5_21_authority_audit.evaluate_offline_integrated_no_go",
            return_value={"status": "INTEGRATED_SYNTHETIC_COHERENT_NEVER_AUTHORIZED",
                          "runtime_go_no_go": "GO"},
        ):
            r = audit(fixture(), claim(claimed_human_approval=True))
        self.assertEqual(r["status"], "AUTHORITY_INPUT_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_input_objects_not_mutated(self):
        p, c = fixture(), claim(
            claimed_human_approval=True,
            approval_reference="SYNTHETIC_APPROVAL_FAKE")
        old_p, old_c = copy.deepcopy(p), copy.deepcopy(c)
        self.denied(audit(p, c))
        self.assertEqual(p, old_p)
        self.assertEqual(c, old_c)

    def test_sequential_calls_do_not_inherit_claims(self):
        p = fixture()
        first = audit(p, claim(claimed_human_approval=True))
        second = audit(p, claim())
        self.assertEqual(first["status"],
                         "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO")
        self.assertEqual(second["status"],
                         "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")
        self.denied(first)
        self.denied(second)

    def test_output_schema_never_echoes_synthetic_authority(self):
        r = audit(fixture(), claim(
            "ORDER_ACTION",
            claimed_human_approval=True,
            approval_reference="SYNTHETIC_APPROVAL_FAKE"))
        self.assertNotIn("SYNTHETIC_APPROVAL_FAKE", repr(r))
        self.assertNotIn("ORDER_ACTION", repr(r))
        self.denied(r)


if __name__ == "__main__":
    unittest.main()
