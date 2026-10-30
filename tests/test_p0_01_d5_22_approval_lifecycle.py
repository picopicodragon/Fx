"""D5-22: synthetic approval lifecycle and denial-only authority cross-checks."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts.p0_01_d5_22_approval_lifecycle import (
    audit_synthetic_approval_lifecycle as lifecycle,
    audit_synthetic_lifecycle_with_authority as integrated,
)

ACTIONS = (
    "VISUAL_REVIEW", "MT4_LAUNCH", "ACCOUNT_LOGIN", "READ_ONLY_QUERY",
    "EA_EXECUTION", "ORDER_ACTION", "STOP_RELEASE", "LIVE_TRADING",
)


def fixture(action="EA_EXECUTION", cause="NONE"):
    record_id = "SYNTH_APPROVAL_TEST"
    issued = "2026-07-01T21:00:00Z"
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "record": {
            "record_id": record_id, "action": action,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A",
            "stop_cause": cause, "issued_at_utc": issued,
            "expires_at_utc": "2026-07-01T21:30:00Z",
        },
        "events": [{"sequence": 0, "event_type": "PROPOSED",
                    "record_id": record_id, "occurred_at_utc": issued}],
        "request": {
            "action": action, "account_scope": "SYNTHETIC_ACCOUNT_A",
            "terminal_scope": "SYNTHETIC_TERMINAL_A", "stop_cause": cause,
        },
        "as_of_utc": "2026-07-01T21:10:00Z",
    }


def add_claim(p, stamp="2026-07-01T21:05:00Z"):
    p["events"].append({
        "sequence": len(p["events"]), "event_type": "APPROVAL_CLAIMED",
        "record_id": p["record"]["record_id"], "occurred_at_utc": stamp,
    })


def add_revocation(p, stamp="2026-07-01T21:06:00Z"):
    p["events"].append({
        "sequence": len(p["events"]), "event_type": "REVOKED",
        "record_id": p["record"]["record_id"], "occurred_at_utc": stamp,
    })


def gate_fixture():
    snapshot = {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "trading_day_start_ny_date": "2026-07-01",
        "daily_stop_latched": False,
        "last_status": "SYNTHETIC_MONITORING_ONLY", "sequence": 10,
    }
    def observation(eid, kind):
        return {
            "evidence_id": eid, "source_kind": kind,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "observed_at_utc": "2026-07-01T21:00:00Z",
            "positions": "ABSENT", "pending_orders": "ABSENT",
            "ea_running": "ABSENT",
        }
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "evidence_mode": "SYNTHETIC_RECORDS",
        "evidence": {
            "origin": "SYNTHETIC_ONLY", "schema_version": 1,
            "account_scope": "SYNTHETIC_ACCOUNT_A",
            "records": [
                observation("EVID_A", "USER_REPORT"),
                observation("EVID_B", "VISUAL_OBSERVATION"),
            ],
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


class D522SyntheticApprovalLifecycleTests(unittest.TestCase):
    def denied(self, r):
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertIsNone(r["verified_values"])
        self.assertIs(r["safety_hold_latched"], True)
        self.assertEqual(r["effective_approved_actions"], [])
        for key in (
            "approval_verified", "action_authorized", "ea_execution_authorized",
            "order_authorized", "stop_release_authorized", "broker_verified",
            "production_usable", "read_only_ex4_execution_approved",
            "terminal_execution_approved", "orders_generated",
            "forward_trading_enabled",
        ):
            self.assertIs(r[key], False)

    def rejected(self, p):
        r = lifecycle(p)
        self.assertEqual(r["status"], "LIFECYCLE_INPUT_REJECTED_FAIL_CLOSED")
        self.assertEqual(r["lifecycle_state"], "INVALID")
        self.denied(r)

    def test_proposed_record_without_claim_remains_denied(self):
        r = lifecycle(fixture())
        self.assertEqual(r["status"], "LIFECYCLE_PROPOSED_NO_GO")
        self.assertEqual(r["lifecycle_state"], "PROPOSED")
        self.denied(r)

    def test_claimed_record_is_never_verified(self):
        p = fixture()
        add_claim(p)
        r = lifecycle(p)
        self.assertEqual(r["status"], "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO")
        self.assertEqual(r["lifecycle_state"], "CLAIMED_NOT_VERIFIED")
        self.assertEqual(r["events_reviewed"], 2)
        self.denied(r)

    def test_revocation_after_claim_has_priority(self):
        p = fixture()
        add_claim(p)
        add_revocation(p)
        r = lifecycle(p)
        self.assertEqual(r["status"], "LIFECYCLE_REVOKED_NO_GO")
        self.assertEqual(r["lifecycle_state"], "REVOKED")
        self.assertEqual(r["events_reviewed"], 3)
        self.denied(r)

    def test_proposal_can_be_revoked_without_claim(self):
        p = fixture()
        add_revocation(p)
        r = lifecycle(p)
        self.assertEqual(r["status"], "LIFECYCLE_REVOKED_NO_GO")
        self.denied(r)

    def test_revocation_wins_over_expiration(self):
        p = fixture()
        add_claim(p)
        add_revocation(p)
        p["as_of_utc"] = "2026-07-01T21:35:00Z"
        r = lifecycle(p)
        self.assertEqual(r["status"], "LIFECYCLE_REVOKED_NO_GO")
        self.denied(r)

    def test_expired_claim_is_never_reactivated(self):
        p = fixture()
        add_claim(p)
        p["as_of_utc"] = "2026-07-01T21:30:01Z"
        r = lifecycle(p)
        self.assertEqual(r["lifecycle_state"], "EXPIRED")
        self.assertEqual(r["status"], "LIFECYCLE_EXPIRED_NO_GO")
        self.denied(r)

    def test_expiration_at_exact_boundary(self):
        p = fixture()
        add_claim(p)
        p["as_of_utc"] = p["record"]["expires_at_utc"]
        self.assertEqual(lifecycle(p)["status"], "LIFECYCLE_EXPIRED_NO_GO")

    def test_expiration_one_second_before_boundary(self):
        p = fixture()
        add_claim(p)
        p["as_of_utc"] = "2026-07-01T21:29:59Z"
        self.assertEqual(lifecycle(p)["status"],
                         "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO")

    def test_unclaimed_record_expires(self):
        p = fixture()
        p["as_of_utc"] = "2026-07-01T21:35:00Z"
        self.assertEqual(lifecycle(p)["status"], "LIFECYCLE_EXPIRED_NO_GO")

    def test_maximum_synthetic_duration_accepted_but_denied(self):
        p = fixture()
        p["record"]["expires_at_utc"] = "2026-07-01T22:00:00Z"
        self.assertEqual(lifecycle(p)["status"], "LIFECYCLE_PROPOSED_NO_GO")

    def test_overlong_duration_rejected(self):
        p = fixture()
        p["record"]["expires_at_utc"] = "2026-07-01T22:00:01Z"
        self.rejected(p)

    def test_zero_and_reversed_duration_rejected(self):
        for expiry in ("2026-07-01T21:00:00Z", "2026-07-01T20:59:59Z"):
            p = fixture()
            p["record"]["expires_at_utc"] = expiry
            self.rejected(p)

    def test_asof_before_issuance_rejected(self):
        p = fixture()
        p["as_of_utc"] = "2026-07-01T20:59:59Z"
        self.rejected(p)

    def test_future_claim_event_rejected(self):
        p = fixture()
        add_claim(p, "2026-07-01T21:11:00Z")
        self.rejected(p)

    def test_late_claim_after_expiration_rejected(self):
        p = fixture()
        p["as_of_utc"] = "2026-07-01T21:45:00Z"
        add_claim(p, "2026-07-01T21:31:00Z")
        self.rejected(p)

    def test_backdated_claim_before_issue_rejected(self):
        p = fixture()
        add_claim(p, "2026-07-01T20:59:59Z")
        self.rejected(p)

    def test_event_time_reversal_rejected(self):
        p = fixture()
        add_claim(p, "2026-07-01T21:06:00Z")
        add_revocation(p, "2026-07-01T21:05:00Z")
        self.rejected(p)

    def test_duplicate_sequence_rejected(self):
        p = fixture()
        add_claim(p)
        p["events"][1]["sequence"] = 0
        self.rejected(p)

    def test_sequence_gap_rejected(self):
        p = fixture()
        add_claim(p)
        p["events"][1]["sequence"] = 2
        self.rejected(p)

    def test_boolean_sequence_rejected(self):
        p = fixture()
        p["events"][0]["sequence"] = False
        self.rejected(p)

    def test_repeated_approval_claim_rejected(self):
        p = fixture()
        add_claim(p)
        add_claim(p, "2026-07-01T21:06:00Z")
        self.rejected(p)

    def test_claim_after_revocation_rejected(self):
        p = fixture()
        add_revocation(p)
        add_claim(p, "2026-07-01T21:07:00Z")
        self.rejected(p)

    def test_double_revocation_rejected(self):
        p = fixture()
        add_revocation(p)
        add_revocation(p, "2026-07-01T21:07:00Z")
        self.rejected(p)

    def test_first_event_cannot_be_claim(self):
        p = fixture()
        p["events"][0]["event_type"] = "APPROVAL_CLAIMED"
        self.rejected(p)

    def test_proposal_timestamp_must_match_issue(self):
        p = fixture()
        p["events"][0]["occurred_at_utc"] = "2026-07-01T21:00:01Z"
        self.rejected(p)

    def test_empty_and_excessive_events_rejected(self):
        p = fixture()
        p["events"] = []
        self.rejected(p)
        p = fixture()
        p["events"].extend(copy.deepcopy(p["events"]) * 3)
        self.rejected(p)

    def test_event_record_id_mismatch_rejected(self):
        p = fixture()
        add_claim(p)
        p["events"][1]["record_id"] = "SYNTH_APPROVAL_OTHER"
        self.rejected(p)

    def test_scope_action_mismatch_denied(self):
        p = fixture()
        p["request"]["action"] = "ORDER_ACTION"
        self.assertEqual(lifecycle(p)["status"], "LIFECYCLE_SCOPE_MISMATCH_NO_GO")

    def test_scope_account_mismatch_denied(self):
        p = fixture()
        add_claim(p)
        p["request"]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        self.assertEqual(lifecycle(p)["status"], "LIFECYCLE_SCOPE_MISMATCH_NO_GO")

    def test_scope_terminal_mismatch_denied(self):
        p = fixture()
        p["request"]["terminal_scope"] = "SYNTHETIC_TERMINAL_B"
        self.assertEqual(lifecycle(p)["status"], "LIFECYCLE_SCOPE_MISMATCH_NO_GO")

    def test_stop_cause_mismatch_denied(self):
        p = fixture("STOP_RELEASE", "DD4")
        add_claim(p)
        p["request"]["stop_cause"] = "DD5"
        r = lifecycle(p)
        self.assertEqual(r["status"], "LIFECYCLE_SCOPE_MISMATCH_NO_GO")
        self.denied(r)

    def test_stop_release_same_cause_still_denied(self):
        p = fixture("STOP_RELEASE", "DD5")
        add_claim(p)
        r = lifecycle(p)
        self.assertEqual(r["status"], "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO")
        self.denied(r)

    def test_all_actions_never_grant_authority(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                p = fixture(action, "DD4" if action == "STOP_RELEASE" else "NONE")
                add_claim(p)
                self.denied(lifecycle(p))

    def test_normal_action_with_stop_cause_rejected(self):
        self.rejected(fixture("EA_EXECUTION", "DD5"))

    def test_stop_release_without_reason_rejected(self):
        self.rejected(fixture("STOP_RELEASE", "NONE"))

    def test_real_account_like_identifiers_rejected(self):
        p = fixture()
        p["record"]["account_scope"] = "12345678"
        self.rejected(p)
        p = fixture()
        p["request"]["terminal_scope"] = "C:\\MT4"
        self.rejected(p)

    def test_unknown_stop_cause_rejected(self):
        self.rejected(fixture("STOP_RELEASE", "OTHER_REASON"))

    def test_invalid_timestamp_variants_rejected(self):
        for bad in ("2026-02-30T21:00:00Z", "2026-07-01T25:00:00Z",
                    "2026-07-01T21:00:00+00:00", "2026-07-01T21:00:00",
                    True, 42, None, ""):
            with self.subTest(value=repr(bad)):
                p = fixture()
                p["as_of_utc"] = bad
                self.rejected(p)

    def test_missing_or_extra_fields_rejected(self):
        p = fixture()
        p["real_approval_verified"] = True
        self.rejected(p)
        p = fixture()
        del p["record"]["terminal_scope"]
        self.rejected(p)
        p = fixture()
        p["events"][0]["orders_authorized"] = True
        self.rejected(p)

    def test_malformed_inputs_and_schema_rejected(self):
        for value in (None, [], {}, "LIVE", True):
            with self.subTest(value=repr(value)):
                self.rejected(value)
        p = fixture()
        p["schema_version"] = True
        self.rejected(p)
        p = fixture()
        p["origin"] = "BROKER_LIVE"
        self.rejected(p)

    def test_no_state_persists_across_calls(self):
        p = fixture()
        add_claim(p)
        self.assertEqual(lifecycle(p)["status"],
                         "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO")
        p2 = fixture()
        self.assertEqual(lifecycle(p2)["status"], "LIFECYCLE_PROPOSED_NO_GO")

    def test_replaying_same_synthetic_record_remains_untrusted(self):
        p = fixture()
        add_claim(p)
        first, second = lifecycle(p), lifecycle(copy.deepcopy(p))
        self.assertEqual(first, second)
        self.assertEqual(first["approval_verified"], False)
        self.denied(first)

    def test_input_not_mutated_by_lifecycle(self):
        p = fixture()
        add_claim(p)
        old = copy.deepcopy(p)
        self.denied(lifecycle(p))
        self.assertEqual(p, old)

    def test_cross_gate_clean_claim_stays_untrusted(self):
        p = fixture()
        add_claim(p)
        r = integrated(gate_fixture(), p)
        self.assertEqual(r["status"], "LIFECYCLE_AND_AUTHORITY_NO_GO")
        self.assertEqual(r["lifecycle_status"],
                         "LIFECYCLE_CLAIMED_UNTRUSTED_NO_GO")
        self.assertEqual(r["authority_status"],
                         "UNTRUSTED_APPROVAL_CLAIM_DENIED_NO_GO")
        self.denied(r)

    def test_cross_gate_proposal_stays_unapproved(self):
        r = integrated(gate_fixture(), fixture())
        self.assertEqual(r["authority_status"],
                         "EXPLICIT_APPROVAL_NOT_PRESENT_NO_GO")
        self.denied(r)

    def test_cross_gate_expired_record_does_not_activate(self):
        p = fixture()
        add_claim(p)
        p["as_of_utc"] = p["record"]["expires_at_utc"]
        r = integrated(gate_fixture(), p)
        self.assertEqual(r["lifecycle_status"], "LIFECYCLE_EXPIRED_NO_GO")
        self.denied(r)

    def test_cross_gate_revoked_record_does_not_activate(self):
        p = fixture()
        add_claim(p)
        add_revocation(p)
        r = integrated(gate_fixture(), p)
        self.assertEqual(r["lifecycle_status"], "LIFECYCLE_REVOKED_NO_GO")
        self.denied(r)

    def test_cross_gate_stop_state_blocks_even_claimed(self):
        g = gate_fixture()
        g["daily_fixture"]["previous_daily_stop"] = True
        g["snapshots"][0]["daily_stop_latched"] = True
        g["snapshots"][0]["last_status"] = "DAILY_STOP"
        p = fixture()
        add_claim(p)
        r = integrated(g, p)
        self.assertEqual(r["authority_status"], "EVIDENCE_OR_STOP_BLOCKED_NO_GO")
        self.denied(r)

    def test_cross_gate_malformed_approval_rejected(self):
        r = integrated(gate_fixture(), {"schema_version": True})
        self.assertEqual(r["status"],
                         "LIFECYCLE_AND_AUTHORITY_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_cross_gate_fake_go_response_rejected(self):
        p = fixture()
        add_claim(p)
        with patch(
            "scripts.p0_01_d5_22_approval_lifecycle.audit_offline_authority_separation",
            return_value={"status": "APPROVED", "runtime_go_no_go": "GO"},
        ):
            r = integrated(gate_fixture(), p)
        self.assertEqual(r["status"],
                         "LIFECYCLE_AND_AUTHORITY_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_cross_gate_fake_release_response_rejected(self):
        p = fixture()
        add_claim(p)
        with patch(
            "scripts.p0_01_d5_22_approval_lifecycle.audit_offline_authority_separation",
            return_value={"status": "VALID", "runtime_go_no_go": "NO_GO",
                          "phase_1": "BLOCKED", "safety_hold_latched": False},
        ):
            r = integrated(gate_fixture(), p)
        self.assertEqual(r["status"],
                         "LIFECYCLE_AND_AUTHORITY_REJECTED_FAIL_CLOSED")
        self.denied(r)

    def test_cross_gate_input_not_mutated(self):
        p, g = fixture(), gate_fixture()
        add_claim(p)
        old_p, old_g = copy.deepcopy(p), copy.deepcopy(g)
        self.denied(integrated(g, p))
        self.assertEqual(p, old_p)
        self.assertEqual(g, old_g)


if __name__ == "__main__":
    unittest.main()
