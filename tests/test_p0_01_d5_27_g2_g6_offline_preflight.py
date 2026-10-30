"""D5-27: G2/G6 preflight checklist, threat model and denial-only faults."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from scripts.p0_01_d5_27_g2_g6_offline_preflight import (
    audit_d527_offline_preflight,
)

_ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def load(relative):
    with (_ROOT / relative).open(encoding="utf-8") as stream:
        return json.load(stream)


def design():
    return load("specs/p0_01_d5_27_g2_g6_offline_design.json")


def original():
    return load("specs/p0_01_d5_17_evidence_reconciliation_status.json")


def matrix():
    return load("specs/p0_01_d5_25_gap_verification_matrix.json")


def scenario(g2="UNKNOWN", g6="NONE", release=False):
    return {
        "origin": "SYNTHETIC_ONLY", "schema_version": 1,
        "g2_simulation": g2, "g6_failure": g6,
        "simulated_stop_release_claim": release,
    }


class D527G2G6OfflinePreflightTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])
        self.assertEqual(result["effective_approved_actions"], [])
        self.assertIs(result["safety_hold_latched"], True)
        for key in (
            "g2_real_world_resolved", "g6_real_world_resolved",
            "account_identity_verified", "positions_verified",
            "pending_orders_verified", "ea_state_verified",
            "trusted_anchor_verified", "atomic_persistence_verified",
            "revocation_durable_verified", "real_transition_authorized",
            "visual_review_approved", "mt4_launch_approved",
            "mt4_read_only_approved", "host_io_approved",
            "approval_verified", "action_authorized",
            "ea_execution_authorized", "order_authorized",
            "stop_release_authorized", "broker_verified",
            "production_usable", "read_only_ex4_execution_approved",
            "terminal_execution_approved", "orders_generated",
            "forward_trading_enabled",
        ):
            self.assertIs(result[key], False)
        return result

    def check(self, expected, d=_UNSET, old=_UNSET, m=_UNSET, s=_UNSET):
        result = self.denied(audit_d527_offline_preflight(
            design() if d is _UNSET else d,
            original() if old is _UNSET else old,
            matrix() if m is _UNSET else m,
            scenario() if s is _UNSET else s,
        ))
        self.assertEqual(result["status"], expected)
        return result

    def test_actual_design_is_offline_only_and_g2_remains_unknown(self):
        self.check("D527_G2_UNRECONCILED_NO_GO")

    def test_synthetic_consistency_never_grants_permissions(self):
        self.check("D527_OFFLINE_DESIGN_COHERENT_NEVER_AUTHORIZED",
                   s=scenario(g2="SYNTHETIC_CONSISTENT"))

    def test_all_g2_disagreement_states_retain_no_go(self):
        for g2 in ("UNKNOWN", "SYNTHETIC_SCOPE_MISMATCH",
                   "SYNTHETIC_TIME_MISMATCH", "SYNTHETIC_REPORT_CONFLICT"):
            with self.subTest(g2=g2):
                self.check("D527_G2_UNRECONCILED_NO_GO",
                           s=scenario(g2=g2))

    def test_all_ten_g6_failure_types_latch_no_go(self):
        for row in design()["g6"]["scenarios"]:
            with self.subTest(threat=row["threat"]):
                self.check("D527_G6_SIMULATED_FAILURE_LATCHED_NO_GO",
                           s=scenario(g2="SYNTHETIC_CONSISTENT",
                                      g6=row["threat"]))

    def test_g6_fault_priority_over_g2_consistency(self):
        self.check("D527_G6_SIMULATED_FAILURE_LATCHED_NO_GO",
                   s=scenario(g2="SYNTHETIC_SCOPE_MISMATCH",
                              g6="POWER_LOSS_MID_WRITE"))

    def test_release_claim_denied_even_in_consistent_simulation(self):
        self.check("D527_STOP_RELEASE_CLAIM_DENIED_NO_GO",
                   s=scenario(g2="SYNTHETIC_CONSISTENT", release=True))

    def test_release_claim_denied_even_with_g6_failure(self):
        self.check("D527_STOP_RELEASE_CLAIM_DENIED_NO_GO",
                   s=scenario(g6="CONCURRENT_WRITER", release=True))

    def test_g2_evidence_count_and_pending_observation_status(self):
        checks = design()["g2"]["checklist"]
        self.assertEqual(len(checks), 8)
        for c in checks:
            self.assertEqual(c["state"], "NOT_PERFORMED")
            self.assertIsNone(c["evidence_reference"])
            self.assertIs(c["real_world_verified"], False)
        self.check("D527_G2_UNRECONCILED_NO_GO")

    def test_g2_reports_prior_and_later_not_misrepresented_as_real_state(self):
        old = original()
        self.assertEqual([x["id"] for x in old["evidence"]],
                         ["EV-OLD", "EV-NEW"])
        self.assertEqual(old["account_identity_consistency"],
                         "NOT_RECONCILED")
        self.assertEqual(old["positions_status"], "UNKNOWN")
        self.assertEqual(old["pending_orders_status"], "UNKNOWN")
        self.assertEqual(old["ea_running_status"], "UNKNOWN")
        self.check("D527_G2_UNRECONCILED_NO_GO", old=old)

    def test_old_macd_sample_not_current_ea_proof(self):
        old = original()
        self.assertEqual(old["evidence"][0]["macd_sample"],
                         "OBSERVED_PREVIOUSLY")
        self.assertIs(old["evidence"][0]["current_state_verified"], False)
        self.check("D527_G2_UNRECONCILED_NO_GO", old=old)

    def test_old_positions_or_pending_not_separate_positions_proof(self):
        old = original()
        self.assertEqual(old["evidence"][0]["positions_or_pending_orders"],
                         "PRESENT_REPORTED_PREVIOUSLY")
        self.assertEqual(old["positions_status"], "UNKNOWN")
        self.assertEqual(old["pending_orders_status"], "UNKNOWN")

    def test_g6_co_edit_all_references_explicitly_undetectable(self):
        row = next(x for x in design()["g6"]["scenarios"]
                   if x["threat"] == "CO_EDIT_ALL_REFERENCES")
        self.assertEqual(row["detection_limit"],
                         "UNDETECTABLE_WITH_UNTRUSTED_INPUTS")
        self.check("D527_G6_SIMULATED_FAILURE_LATCHED_NO_GO",
                   s=scenario(g6=row["threat"]))

    def test_g6_other_scenarios_are_only_synthetic_rejection(self):
        for row in design()["g6"]["scenarios"]:
            if row["threat"] != "CO_EDIT_ALL_REFERENCES":
                self.assertEqual(row["detection_limit"],
                                 "SYNTHETIC_REJECTION_ONLY")

    def test_no_proposal_issues_real_operational_approval(self):
        self.assertTrue(all(v is False
                            for v in design()["approvals"].values()))
        self.assertIs(design()["g6"]["host_io_approved"], False)
        self.check("D527_G2_UNRECONCILED_NO_GO")

    def test_missing_required_checklist_row_rejected(self):
        d = design()
        d["g2"]["checklist"].pop()
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_duplicate_checklist_id_rejected(self):
        d = design()
        d["g2"]["checklist"][1]["id"] = "P27-G2-01"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_checklist_order_or_topic_change_rejected(self):
        d = design()
        d["g2"]["checklist"][0], d["g2"]["checklist"][1] = (
            d["g2"]["checklist"][1], d["g2"]["checklist"][0])
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)
        d = design()
        d["g2"]["checklist"][0]["topic"] = "LIVE_LOGIN"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_marked_verified_is_rejected(self):
        d = design()
        d["g2"]["checklist"][0]["real_world_verified"] = True
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_real_identity_cannot_be_declared(self):
        d = design()
        d["g2"]["account_identity_consistency"] = "RECONCILED"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_position_state_cannot_be_declared_absent(self):
        d = design()
        d["g2"]["current_positions"] = "ABSENT"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_pending_state_cannot_be_declared_absent(self):
        d = design()
        d["g2"]["current_pending_orders"] = "ABSENT"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_ea_state_cannot_be_declared_absent(self):
        d = design()
        d["g2"]["current_ea_state"] = "ABSENT"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_evidence_reference_cannot_be_forged(self):
        d = design()
        d["g2"]["checklist"][1]["evidence_reference"] = "MT4_LIVE"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_check_cannot_be_marked_performed(self):
        d = design()
        d["g2"]["checklist"][1]["state"] = "COMPLETE"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_future_operation_cannot_be_approved_by_design(self):
        d = design()
        d["g2"]["checklist"][1]["future_operation_approved"] = True
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_empty_future_proof_is_rejected(self):
        d = design()
        d["g2"]["checklist"][1]["future_proof_required"] = ""
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g2_checklist_real_source_id_replacement_rejected(self):
        d = design()
        d["g2"]["report_ids"] = ["LIVE_ACCOUNT_ID", "EV-NEW"]
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_missing_threat_scenario_rejected(self):
        d = design()
        d["g6"]["scenarios"].pop()
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_duplicate_scenario_id_rejected(self):
        d = design()
        d["g6"]["scenarios"][2]["id"] = "P27-G6-02"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_scenario_reordering_rejected(self):
        d = design()
        d["g6"]["scenarios"][0], d["g6"]["scenarios"][1] = (
            d["g6"]["scenarios"][1], d["g6"]["scenarios"][0])
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_threat_name_change_rejected(self):
        d = design()
        d["g6"]["scenarios"][0]["threat"] = "ALLOW_AUTO_RESTART"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_fault_response_cannot_be_changed_to_go(self):
        d = design()
        d["g6"]["scenarios"][0]["expected_outcome"] = "GO"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_fault_cannot_claim_real_verification(self):
        d = design()
        d["g6"]["scenarios"][0]["real_world_verified"] = True
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_fault_cannot_authorize_host_io(self):
        d = design()
        d["g6"]["scenarios"][0]["host_io_approved"] = True
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_fault_simulation_cannot_be_marked_live(self):
        d = design()
        d["g6"]["scenarios"][0]["simulation_mode"] = "REAL_DISK"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_anchor_cannot_be_claimed_real(self):
        d = design()
        d["g6"]["independent_trust_anchor_implemented"] = True
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_persistence_or_revocation_cannot_be_claimed_real(self):
        for field in ("atomic_persistence_verified", "revocation_durable"):
            with self.subTest(field=field):
                d = design()
                d["g6"][field] = True
                self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_co_edit_limitation_cannot_be_hidden(self):
        d = design()
        d["g6"]["scenarios"][3]["detection_limit"] = "FULLY_DETECTED"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_g6_future_proof_cannot_be_empty(self):
        d = design()
        d["g6"]["scenarios"][0]["future_proof_required"] = []
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_approval_flags_cannot_be_set(self):
        for name in design()["approvals"]:
            with self.subTest(name=name):
                d = design()
                d["approvals"][name] = True
                self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_approval_false_as_integer_rejected(self):
        d = design()
        d["approvals"]["host_io"] = 0
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_top_level_extra_authorization_field_rejected(self):
        d = design()
        d["order_authorized"] = True
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_cannot_switch_to_second_demo_account(self):
        d = design()
        d["scope"] = "MULTIPLE_MT4_ACCOUNTS"
        self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_cannot_set_go_or_verified_values(self):
        for key, value in (("runtime_go_no_go", "GO"),
                           ("verified_values", {"USDJPY": "VERIFIED"})):
            with self.subTest(key=key):
                d = design()
                d[key] = value
                self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_design_invalid_schema_or_origin_rejected(self):
        for key, value in (("origin", "BROKER_LIVE"),
                           ("schema_version", True), ("schema_version", 2)):
            with self.subTest(key=key):
                d = design()
                d[key] = value
                self.check("D527_DESIGN_REJECTED_FAIL_CLOSED", d=d)

    def test_old_user_report_marked_verified_rejected(self):
        old = original()
        old["evidence"][0]["current_state_verified"] = True
        self.check("D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_report_timestamp_invented_rejected(self):
        old = original()
        old["evidence"][0]["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_and_later_report_status_forged_rejected(self):
        old = original()
        old["evidence"][1]["positions_and_orders"] = "VERIFIED_ABSENT"
        self.check("D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_report_account_identity_forged_rejected(self):
        old = original()
        old["account_identity_consistency"] = "RECONCILED"
        self.check("D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_preflight_cannot_be_marked_performed(self):
        old = original()
        old["check_states"][0]["status"] = "PASS"
        self.check("D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_approval_cannot_be_upgraded(self):
        old = original()
        old["approvals"]["mt4_launch"] = True
        self.check("D527_EVIDENCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_matrix_g2_cannot_be_marked_solved(self):
        m = matrix()
        next(x for x in m["gaps"] if x["id"] == "G2")[
            "real_world_verified"] = True
        self.check("D527_GAP_BASELINE_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_g6_cannot_remove_release_blocker(self):
        m = matrix()
        next(x for x in m["gaps"] if x["id"] == "G6")[
            "release_blocker"] = False
        self.check("D527_GAP_BASELINE_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_other_gaps_remain_unresolved(self):
        m = matrix()
        next(x for x in m["gaps"] if x["id"] == "G9")[
            "implementation_status"] = "RESOLVED"
        self.check("D527_GAP_BASELINE_REJECTED_FAIL_CLOSED", m=m)

    def test_matrix_duplicate_gap_rejected(self):
        m = matrix()
        m["gaps"][-1]["id"] = "G2"
        self.check("D527_GAP_BASELINE_REJECTED_FAIL_CLOSED", m=m)

    def test_unknown_g2_or_g6_case_rejected(self):
        for item, value in (("g2_simulation", "ACCOUNT_VERIFIED"),
                            ("g6_failure", "REAL_DISK_OK")):
            with self.subTest(item=item):
                c = scenario()
                c[item] = value
                self.check("D527_SYNTHETIC_CASE_REJECTED_FAIL_CLOSED", s=c)

    def test_case_boolean_schema_rejected(self):
        c = scenario()
        c["schema_version"] = True
        self.check("D527_SYNTHETIC_CASE_REJECTED_FAIL_CLOSED", s=c)

    def test_case_non_boolean_release_flag_rejected(self):
        c = scenario()
        c["simulated_stop_release_claim"] = 1
        self.check("D527_SYNTHETIC_CASE_REJECTED_FAIL_CLOSED", s=c)

    def test_case_extra_real_permission_field_rejected(self):
        c = scenario()
        c["human_approval_verified"] = True
        self.check("D527_SYNTHETIC_CASE_REJECTED_FAIL_CLOSED", s=c)

    def test_missing_or_invalid_case_rejected(self):
        for invalid in (None, [], {}, "LIVE"):
            with self.subTest(value=repr(invalid)):
                self.check("D527_SYNTHETIC_CASE_REJECTED_FAIL_CLOSED",
                           s=invalid)

    def test_missing_or_invalid_design_rejected(self):
        for invalid in (None, [], {}, "LIVE"):
            with self.subTest(value=repr(invalid)):
                self.check("D527_DESIGN_REJECTED_FAIL_CLOSED",
                           d=invalid)

    def test_inputs_are_not_modified_by_audit(self):
        d, old, m, s = design(), original(), matrix(), scenario()
        saved = copy.deepcopy((d, old, m, s))
        self.denied(audit_d527_offline_preflight(d, old, m, s))
        self.assertEqual((d, old, m, s), saved)

    def test_repeated_calls_do_not_retain_real_permission(self):
        d, old, m = design(), original(), matrix()
        valid = scenario(g2="SYNTHETIC_CONSISTENT")
        self.denied(audit_d527_offline_preflight(d, old, m, valid))
        claimed = scenario(g2="SYNTHETIC_CONSISTENT", release=True)
        self.check("D527_STOP_RELEASE_CLAIM_DENIED_NO_GO",
                   d=d, old=old, m=m, s=claimed)
        self.check("D527_G2_UNRECONCILED_NO_GO",
                   d=d, old=old, m=m)

    def test_real_world_gap_matrix_and_status_still_blocked(self):
        status = load("specs/p0_01_d5_27_status.json")
        self.assertEqual(status["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.assertEqual(status["phase_1"], "BLOCKED")
        self.assertEqual(status["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(status["verified_values"])
        self.assertIs(status["broker_verified"], False)
        self.assertIs(status["terminal_execution_approved"], False)
        self.assertIs(status["forward_trading_enabled"], False)


if __name__ == "__main__":
    unittest.main()
