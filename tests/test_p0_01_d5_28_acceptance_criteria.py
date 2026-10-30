"""D5-28: provenance schema, simulated chronology, G6 future acceptance tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from scripts.p0_01_d5_28_acceptance_criteria import audit_d528_acceptance_design

_ROOT = Path(__file__).resolve().parents[1]


def load(path):
    with (_ROOT / path).open(encoding="utf-8") as stream:
        return json.load(stream)


def design():
    return load("specs/p0_01_d5_28_acceptance_contract.json")


def case():
    def record(rid):
        return {
            "report_id": rid,
            "provenance_class": "UNVERIFIED_SYNTHETIC_REPORT",
            "account_token": "SYNTHETIC_ACCOUNT_A",
            "terminal_token": "SYNTHETIC_TERMINAL_A",
            "observed_at_utc": "2026-07-01T21:00:00Z",
            "recorded_at_utc": "2026-07-01T21:01:00Z",
            "positions": "ABSENT", "pending_orders": "ABSENT",
            "ea_attachment": "ABSENT", "autotrading": "ABSENT",
        }
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "g2_records": [record("EV-OLD"), record("EV-NEW")],
        "g6_scenario": {
            "threat": "NONE", "persist_state": "SYNTHETIC_CONSISTENT",
            "anchor_state": "SYNTHETIC_MATCH",
            "revocation_state": "SYNTHETIC_NO_REVOCATION",
            "clock_state": "SYNTHETIC_STABLE",
            "simulated_io_only": True,
        },
        "simulated_stop_release_claim": False,
    }


_UNSET = object()


class D528AcceptanceCriteriaTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertEqual(set(result), {
            "status", "g2_real_world_resolved", "g6_real_world_resolved",
            "evidence_provenance_authenticated", "account_identity_verified",
            "positions_verified", "pending_orders_verified",
            "ea_state_verified", "trusted_clock_verified",
            "trusted_anchor_verified", "atomic_persistence_verified",
            "revocation_durable_verified", "real_transition_authorized",
            "visual_review_approved", "mt4_launch_approved",
            "mt4_read_only_approved", "host_io_approved",
            "approval_verified", "action_authorized",
            "ea_execution_authorized", "order_authorized",
            "stop_release_authorized", "effective_approved_actions",
            "safety_hold_latched", "phase_1", "runtime_go_no_go",
            "verified_values", "broker_verified", "production_usable",
            "read_only_ex4_execution_approved", "terminal_execution_approved",
            "orders_generated", "forward_trading_enabled",
        })
        for key, value in result.items():
            if key.endswith("_approved") or key.endswith("_verified") or key.endswith("_authorized"):
                self.assertIs(value, False, key)
        for key in (
            "g2_real_world_resolved", "g6_real_world_resolved",
            "evidence_provenance_authenticated", "trusted_anchor_verified",
            "broker_verified", "production_usable", "orders_generated",
            "forward_trading_enabled",
        ):
            self.assertIs(result[key], False, key)
        return result

    def check(self, status, d=_UNSET, c=_UNSET):
        r = self.denied(audit_d528_acceptance_design(
            design() if d is _UNSET else d, case() if c is _UNSET else c))
        self.assertEqual(r["status"], status)
        return r

    def test_complete_synthetic_format_still_no_go(self):
        self.check("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO")

    def test_both_synthetic_present_still_no_go(self):
        c = case()
        for item in c["g2_records"]:
            for key in ("positions", "pending_orders", "ea_attachment",
                        "autotrading"):
                item[key] = "PRESENT"
        self.check("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO", c=c)

    def test_unknown_positions_never_resolved(self):
        c = case()
        for item in c["g2_records"]:
            item["positions"] = "UNKNOWN"
        self.check("D528_G2_SYNTHETIC_UNKNOWN_NO_GO", c=c)

    def test_unknown_pending_orders_never_resolved(self):
        c = case()
        for item in c["g2_records"]:
            item["pending_orders"] = "UNKNOWN"
        self.check("D528_G2_SYNTHETIC_UNKNOWN_NO_GO", c=c)

    def test_unknown_ea_never_resolved(self):
        c = case()
        for item in c["g2_records"]:
            item["ea_attachment"] = "UNKNOWN"
        self.check("D528_G2_SYNTHETIC_UNKNOWN_NO_GO", c=c)

    def test_unknown_autotrading_never_resolved(self):
        c = case()
        for item in c["g2_records"]:
            item["autotrading"] = "UNKNOWN"
        self.check("D528_G2_SYNTHETIC_UNKNOWN_NO_GO", c=c)

    def test_account_scope_mismatch(self):
        c = case()
        c["g2_records"][1]["account_token"] = "SYNTHETIC_ACCOUNT_B"
        self.check("D528_G2_SYNTHETIC_SCOPE_MISMATCH_NO_GO", c=c)

    def test_terminal_scope_mismatch(self):
        c = case()
        c["g2_records"][1]["terminal_token"] = "SYNTHETIC_TERMINAL_B"
        self.check("D528_G2_SYNTHETIC_SCOPE_MISMATCH_NO_GO", c=c)

    def test_observation_time_mismatch(self):
        c = case()
        c["g2_records"][1]["observed_at_utc"] = "2026-07-01T21:00:10Z"
        self.check("D528_G2_SYNTHETIC_TIME_MISMATCH_NO_GO", c=c)

    def test_report_times_may_differ_without_claiming_identity(self):
        c = case()
        c["g2_records"][1]["recorded_at_utc"] = "2026-07-01T21:02:00Z"
        r = self.check("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO", c=c)
        self.assertIs(r["account_identity_verified"], False)

    def test_report_conflict_positions(self):
        c = case()
        c["g2_records"][1]["positions"] = "PRESENT"
        self.check("D528_G2_SYNTHETIC_REPORT_CONFLICT_NO_GO", c=c)

    def test_report_conflict_pending_orders(self):
        c = case()
        c["g2_records"][1]["pending_orders"] = "PRESENT"
        self.check("D528_G2_SYNTHETIC_REPORT_CONFLICT_NO_GO", c=c)

    def test_report_conflict_ea(self):
        c = case()
        c["g2_records"][1]["ea_attachment"] = "PRESENT"
        self.check("D528_G2_SYNTHETIC_REPORT_CONFLICT_NO_GO", c=c)

    def test_report_conflict_autotrading(self):
        c = case()
        c["g2_records"][1]["autotrading"] = "PRESENT"
        self.check("D528_G2_SYNTHETIC_REPORT_CONFLICT_NO_GO", c=c)

    def test_failure_priority_over_g2_mismatch(self):
        c = case()
        c["g2_records"][1]["account_token"] = "SYNTHETIC_ACCOUNT_B"
        c["g6_scenario"]["threat"] = "POWER_LOSS_MID_WRITE"
        self.check("D528_G6_UNTRUSTED_OR_FAULT_NO_GO", c=c)

    def test_claimed_stop_release_never_applied(self):
        c = case()
        c["simulated_stop_release_claim"] = True
        self.check("D528_RELEASE_CLAIM_DENIED_NO_GO", c=c)

    def test_all_ten_g6_synthetic_faults_stop(self):
        for row in design()["g6"]["acceptance"]:
            with self.subTest(threat=row["threat"]):
                c = case()
                c["g6_scenario"]["threat"] = row["threat"]
                self.check("D528_G6_UNTRUSTED_OR_FAULT_NO_GO", c=c)

    def test_real_co_edit_detection_not_claimed(self):
        d = design()
        item = d["g6"]["acceptance"][3]
        self.assertEqual(item["threat"], "CO_EDIT_ALL_REFERENCES")
        self.assertIs(item["real_world_verified"], False)
        c = case()
        # If a forger rewrites *all* untrusted fields, internal consistency
        # cannot reveal it. This outcome is never a real authorization.
        self.check("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO", c=c)

    def test_storage_fault_state_denied(self):
        for state in ("SYNTHETIC_FAULT", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                c = case()
                c["g6_scenario"]["persist_state"] = state
                self.check("D528_G6_UNTRUSTED_OR_FAULT_NO_GO", c=c)

    def test_anchor_fault_state_denied(self):
        for state in ("SYNTHETIC_MISMATCH", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                c = case()
                c["g6_scenario"]["anchor_state"] = state
                self.check("D528_G6_UNTRUSTED_OR_FAULT_NO_GO", c=c)

    def test_revocation_erasure_or_revocation_denied(self):
        for state in ("SYNTHETIC_ERASURE", "SYNTHETIC_REVOKED",
                      "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                c = case()
                c["g6_scenario"]["revocation_state"] = state
                self.check("D528_G6_UNTRUSTED_OR_FAULT_NO_GO", c=c)

    def test_clock_anomaly_or_unknown_denied(self):
        for state in ("SYNTHETIC_ANOMALY", "SYNTHETIC_UNKNOWN"):
            with self.subTest(state=state):
                c = case()
                c["g6_scenario"]["clock_state"] = state
                self.check("D528_G6_UNTRUSTED_OR_FAULT_NO_GO", c=c)

    def test_design_requires_ten_acceptance_ids(self):
        rows = design()["g6"]["acceptance"]
        self.assertEqual([x["acceptance_id"] for x in rows],
                         [f"G6-AC-{i:02d}" for i in range(1, 11)])
        for row in rows:
            self.assertEqual(row["expected_status"],
                             "SAFETY_HOLD_LATCHED_NO_GO")
            self.assertIs(row["future_real_test_required"], True)
            self.assertIs(row["real_world_verified"], False)

    def test_design_no_approval_flags(self):
        self.assertTrue(all(v is False for v in design()["approvals"].values()))
        self.check("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO")

    def test_design_g2_fields_are_separate(self):
        fields = design()["g2"]["required_fields"]
        for field in ("observed_at_utc", "recorded_at_utc",
                      "positions", "pending_orders", "ea_attachment",
                      "autotrading", "provenance_class"):
            self.assertIn(field, fields)

    def test_changed_g2_evidence_required_fields_rejected(self):
        d = design()
        d["g2"]["required_fields"].pop()
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_removed_separate_pending_orders_rejected(self):
        d = design()
        d["g2"]["required_checks"].remove("PENDING_ORDERS")
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_real_account_identifier_policy_rejected(self):
        d = design()
        d["g2"]["identity_policy"] = "GITHUB_RAW_ACCOUNT_NUMBER"
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_claimed_real_current_state_rejected(self):
        d = design()
        d["g2"]["no_current_state_verified"] = False
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_actual_anchor_claim_rejected(self):
        d = design()
        d["g6"]["independent_anchor_verified"] = True
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_actual_storage_claim_rejected(self):
        d = design()
        d["g6"]["no_real_storage"] = False
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_acceptance_removed_rejected(self):
        d = design()
        d["g6"]["acceptance"].pop()
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_duplicate_threat_rejected(self):
        d = design()
        d["g6"]["acceptance"][1]["threat"] = "ATOMIC_COMMIT_TORN"
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_unknown_acceptance_id_rejected(self):
        d = design()
        d["g6"]["acceptance"][1]["acceptance_id"] = "G6-AC-XX"
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_future_real_test_cannot_be_skipped(self):
        d = design()
        d["g6"]["acceptance"][0]["future_real_test_required"] = False
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_g6_cannot_be_marked_verified(self):
        d = design()
        d["g6"]["acceptance"][0]["real_world_verified"] = True
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_cannot_rewrite_failure_to_go(self):
        d = design()
        d["g6"]["acceptance"][0]["expected_status"] = "GO"
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_cannot_authorize_order(self):
        d = design()
        d["approvals"]["order_action"] = True
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_cannot_authorize_host_io(self):
        d = design()
        d["approvals"]["host_io"] = True
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_false_approval_as_integer_rejected(self):
        d = design()
        d["approvals"]["mt4_launch"] = 0
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_go_and_verified_values_rejected(self):
        for field, value in (("runtime_go_no_go", "GO"),
                             ("verified_values", {})):
            with self.subTest(field=field):
                d = design()
                d[field] = value
                self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_extra_approval_key_rejected(self):
        d = design()
        d["auto_approve"] = True
        self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_case_looks_like_real_account_number_rejected(self):
        c = case()
        c["g2_records"][0]["account_token"] = "12345678"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_extra_raw_account_key_rejected(self):
        c = case()
        c["g2_records"][0]["account_number"] = "SECRET"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_missing_provenance_rejected(self):
        c = case()
        del c["g2_records"][0]["provenance_class"]
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_real_provenance_claim_rejected(self):
        c = case()
        c["g2_records"][1]["provenance_class"] = "BROKER_VERIFIED"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_missing_observation_timestamp_rejected(self):
        c = case()
        c["g2_records"][0]["observed_at_utc"] = None
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_invalid_calendar_date_rejected(self):
        c = case()
        c["g2_records"][0]["observed_at_utc"] = "2026-02-30T21:00:00Z"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_non_utc_timestamp_rejected(self):
        c = case()
        c["g2_records"][0]["observed_at_utc"] = "2026-07-01T21:00:00+00:00"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_observed_after_recorded_rejected(self):
        c = case()
        c["g2_records"][0]["recorded_at_utc"] = "2026-07-01T20:59:59Z"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_extra_report_rejected(self):
        c = case()
        c["g2_records"].append(copy.deepcopy(c["g2_records"][1]))
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_swapped_report_ids_rejected(self):
        c = case()
        c["g2_records"].reverse()
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_unknown_market_state_rejected(self):
        c = case()
        c["g2_records"][0]["pending_orders"] = "REAL_ABSENT"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_bool_state_rejected(self):
        c = case()
        c["g2_records"][0]["positions"] = False
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_simulated_real_io_rejected(self):
        c = case()
        c["g6_scenario"]["simulated_io_only"] = False
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_unknown_g6_fault_rejected(self):
        c = case()
        c["g6_scenario"]["threat"] = "REAL_DISK_WRITE"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_fake_persistent_state_rejected(self):
        c = case()
        c["g6_scenario"]["persist_state"] = "OS_VERIFIED"
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_boolean_release_as_integer_rejected(self):
        c = case()
        c["simulated_stop_release_claim"] = 1
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_invalid_schema_and_origin_rejected(self):
        for field, value in (("origin", "LIVE"), ("schema_version", True),
                             ("schema_version", 2)):
            with self.subTest(field=field):
                c = case()
                c[field] = value
                self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_extra_permission_rejected(self):
        c = case()
        c["orders_generated"] = True
        self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_invalid_outer_types_rejected(self):
        for value in (None, [], {}, "MT4", True):
            with self.subTest(value=repr(value)):
                self.check("D528_CASE_REJECTED_FAIL_CLOSED", c=value)
                self.check("D528_DESIGN_REJECTED_FAIL_CLOSED", d=value)

    def test_input_unchanged_by_audit(self):
        d, c = design(), case()
        before = copy.deepcopy((d, c))
        self.denied(audit_d528_acceptance_design(d, c))
        self.assertEqual((d, c), before)

    def test_consecutive_calls_never_authorize(self):
        d = design()
        self.check("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO", d=d)
        c = case()
        c["simulated_stop_release_claim"] = True
        self.check("D528_RELEASE_CLAIM_DENIED_NO_GO", d=d, c=c)
        self.check("D528_SYNTHETIC_ACCEPTANCE_FORMAT_COHERENT_NO_GO", d=d)

    def test_g2_g6_predecessor_real_world_flags_unchanged(self):
        prior = load("specs/p0_01_d5_27_status.json")
        matrix = load("specs/p0_01_d5_25_gap_verification_matrix.json")
        self.assertEqual(prior["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(prior["current_positions"], "UNKNOWN")
        self.assertEqual(prior["current_pending_orders"], "UNKNOWN")
        self.assertIs(prior["g6_trust_anchor_real"], False)
        self.assertIs(prior["g6_host_io_test_approved"], False)
        for row in matrix["gaps"]:
            self.assertEqual(row["implementation_status"], "UNRESOLVED")
            self.assertIs(row["real_world_verified"], False)
            self.assertIs(row["release_blocker"], True)

    def test_new_status_no_go(self):
        status = load("specs/p0_01_d5_28_status.json")
        self.assertEqual(status["test_count_previous"], 1018)
        self.assertEqual(status["phase_1"], "BLOCKED")
        self.assertEqual(status["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(status["verified_values"])
        for field in ("broker_verified", "terminal_execution_approved",
                      "forward_trading_enabled", "g2_real_world_resolved",
                      "g6_real_world_resolved"):
            self.assertIs(status[field], False)


if __name__ == "__main__":
    unittest.main()
