"""P0-01 D5-30: fail-closed G2 collection SOP and G6 architecture tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.p0_01_d5_30_architecture_review import (
    _FALSE_FLAGS, review_d530_offline_architecture,
)

_ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def load(name):
    with (_ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def plan():
    return load("p0_01_d5_30_collection_persistence_architecture.json")


def ledger():
    return load("p0_01_d5_17_evidence_reconciliation_status.json")


def gaps():
    return load("p0_01_d5_25_gap_verification_matrix.json")


def fixture():
    return {
        "origin": "SYNTHETIC_ONLY",
        "schema_version": 1,
        "g2_simulated_privacy": "SYNTHETIC_REDACTED_METADATA_ONLY",
        "g6_simulated_recovery": "SYNTHETIC_DESIGN_SELF_CONSISTENT",
        "requested_operation": "NONE",
        "simulated_only": True,
        "future_approval_claim": False,
    }


class D530OfflineArchitectureTests(unittest.TestCase):
    def denied(self, r):
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(r["verified_values"])
        self.assertIs(r["safety_hold_latched"], True)
        self.assertEqual(r["effective_approved_actions"], [])
        self.assertIs(type(r["effective_approved_actions"]), list)
        self.assertEqual(r["account_identity_consistency"], "NOT_RECONCILED")
        for key in ("current_positions", "current_pending_orders",
                    "current_ea_state"):
            self.assertEqual(r[key], "UNKNOWN")
        for key in _FALSE_FLAGS:
            self.assertIs(r[key], False, key)
        self.assertEqual(
            set(r),
            {"status", "effective_approved_actions", "safety_hold_latched",
             "account_identity_consistency", "current_positions",
             "current_pending_orders", "current_ea_state", "phase_1",
             "runtime_go_no_go", "verified_values"} | set(_FALSE_FLAGS),
        )
        return r

    def check(self, expected, p=_UNSET, old=_UNSET, gap=_UNSET, c=_UNSET):
        r = review_d530_offline_architecture(
            plan() if p is _UNSET else p,
            ledger() if old is _UNSET else old,
            gaps() if gap is _UNSET else gap,
            fixture() if c is _UNSET else c,
        )
        self.denied(r)
        self.assertEqual(r["status"], expected)
        return r

    def test_base_synthetic_design_coherent_never_authorized(self):
        self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED")

    def test_even_matching_design_does_not_authenticate_g2(self):
        r = self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED")
        self.assertIs(r["account_identity_verified"], False)
        self.assertIs(r["evidence_provenance_authenticated"], False)

    def test_even_matching_design_does_not_implement_g6(self):
        r = self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED")
        for key in ("independent_trust_anchor_verified",
                    "atomic_persistence_verified", "revocation_durable_verified",
                    "recovery_verified"):
            self.assertIs(r[key], False)

    def test_g2_eight_checks_remain_unperformed(self):
        p = plan()
        self.assertEqual(len(p["g2"]["collection_steps"]), 8)
        for step in p["g2"]["collection_steps"]:
            self.assertEqual(step["state"], "NOT_PERFORMED")
            self.assertIs(step["operation_performed"], False)
            self.assertIs(step["evidence_collected"], False)
            self.assertIs(step["future_manual_approval_required"], True)
        self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED", p=p)

    def test_g2_receipts_never_created(self):
        p = plan()
        self.assertIs(p["g2"]["real_receipt_created"], False)
        self.assertIs(p["g2"]["redaction_review_performed"], False)
        self.assertIs(p["g2"]["local_private_storage_implemented"], False)
        self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED", p=p)

    def test_g2_private_categories_cover_real_identifiers(self):
        names = plan()["g2"]["private_only_categories"]
        self.assertIn("ACCOUNT_NUMBER", names)
        self.assertIn("RAW_MT4_LOG", names)
        self.assertIn("SCREENSHOT_BYTES", names)
        self.assertIn("API_KEY_OR_SECRET", names)
        self.assertIn("REAL_OBSERVATION_TIMESTAMP", names)

    def test_g2_git_fields_metadata_only(self):
        names = plan()["g2"]["git_allowed_metadata_fields"]
        self.assertEqual(names, ["check_id", "design_state", "simulation_only"])
        self.assertIs(plan()["g2"]["git_raw_evidence_allowed"], False)

    def test_g2_prior_user_reports_unchanged(self):
        old = ledger()
        self.assertEqual(old["account_identity_consistency"], "NOT_RECONCILED")
        self.assertEqual(old["positions_status"], "UNKNOWN")
        self.assertEqual(old["pending_orders_status"], "UNKNOWN")
        self.assertEqual(old["ea_running_status"], "UNKNOWN")
        self.assertEqual([v["id"] for v in old["evidence"]],
                         ["EV-OLD", "EV-NEW"])
        self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED",
                   old=old)

    def test_g2_cannot_mark_step_completed(self):
        p = plan()
        p["g2"]["collection_steps"][0]["state"] = "COMPLETED"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_cannot_claim_action_performed(self):
        p = plan()
        p["g2"]["collection_steps"][0]["operation_performed"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_cannot_claim_evidence_collected(self):
        p = plan()
        p["g2"]["collection_steps"][0]["evidence_collected"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_future_approval_cannot_be_removed(self):
        p = plan()
        p["g2"]["collection_steps"][0]["future_manual_approval_required"] = False
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_step_id_duplicate_rejected(self):
        p = plan()
        p["g2"]["collection_steps"][1]["id"] = "D530-G2-01"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_step_order_change_rejected(self):
        p = plan()
        p["g2"]["collection_steps"].reverse()
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_eight_categories_cannot_be_reduced(self):
        p = plan()
        p["g2"]["private_only_categories"].pop()
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_git_cannot_publish_account_numbers(self):
        p = plan()
        p["g2"]["git_allowed_metadata_fields"].append("account_number")
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_git_raw_evidence_cannot_be_enabled(self):
        p = plan()
        p["g2"]["git_raw_evidence_allowed"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_local_storage_not_implicitly_implemented(self):
        p = plan()
        p["g2"]["local_private_storage_implemented"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_cannot_claim_reconciliation(self):
        p = plan()
        p["g2"]["account_identity_consistency"] = "RECONCILED"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_cannot_mark_pending_orders_absent(self):
        p = plan()
        p["g2"]["current_pending_orders"] = "ABSENT"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_cannot_mark_ea_state_absent(self):
        p = plan()
        p["g2"]["current_ea_state"] = "ABSENT"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g2_missing_or_extra_step_rejected(self):
        p = plan()
        p["g2"]["collection_steps"].pop()
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)
        p = plan()
        p["g2"]["collection_steps"][0]["account_number"] = "SECRET"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_nine_components_all_design_only(self):
        p = plan()
        self.assertEqual(len(p["g6"]["components"]), 9)
        for c in p["g6"]["components"]:
            self.assertEqual(c["implementation_state"], "DESIGN_ONLY")
            self.assertIs(c["real_world_verified"], False)
        self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED", p=p)

    def test_g6_components_distinct_anchor_and_writer(self):
        names = [x["name"] for x in plan()["g6"]["components"]]
        self.assertIn("INDEPENDENT_MONOTONIC_ANCHOR", names)
        self.assertIn("SINGLE_WRITER_FENCE", names)
        self.assertIn("REVOCATION_TOMBSTONES", names)
        self.assertIn("MONOTONIC_CLOCK_ADAPTER", names)

    def test_g6_commit_stops_before_writing(self):
        steps = plan()["g6"]["commit_sequence"]
        self.assertEqual(steps[0], "LATCH_STOP_BEFORE_ACTION")
        self.assertLess(steps.index("FLUSH_DURABLE_LOCAL_STATE"),
                        steps.index("PUBLISH_INDEPENDENT_ANCHOR"))
        self.assertLess(steps.index("PUBLISH_INDEPENDENT_ANCHOR"),
                        steps.index("VERIFY_RECOVERY_WITH_STOP_STILL_LATCHED"))

    def test_g6_coordinated_attack_remains_undetectable(self):
        limits = plan()["g6"]["critical_limits"]
        self.assertIs(limits["coordinated_forgery_detectable"], False)
        self.assertIs(limits["actual_monotonic_anchor_available"], False)

    def test_g6_external_cross_resource_atomicity_not_promised(self):
        self.assertIs(
            plan()["g6"]["critical_limits"]["cross_resource_atomicity_guaranteed"],
            False,
        )

    def test_g6_all_ten_faults_require_future_proof(self):
        faults = plan()["g6"]["failure_scenarios"]
        self.assertEqual(len(faults), 10)
        for fault in faults:
            self.assertEqual(fault["design_outcome"], "STOP_LATCHED_NO_GO")
            self.assertIs(fault["real_fault_injected"], False)
            self.assertIs(fault["independent_proof_required"], True)

    def test_g6_component_cannot_claim_real_implementation(self):
        p = plan()
        p["g6"]["components"][0]["implementation_state"] = "IMPLEMENTED"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_component_cannot_claim_real_verification(self):
        p = plan()
        p["g6"]["components"][0]["real_world_verified"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_component_order_cannot_change(self):
        p = plan()
        p["g6"]["components"][0], p["g6"]["components"][1] = (
            p["g6"]["components"][1], p["g6"]["components"][0])
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_component_name_cannot_be_renamed(self):
        p = plan()
        p["g6"]["components"][1]["name"] = "AUTO_TRADING_ON"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_commit_cannot_publish_anchor_before_flush(self):
        p = plan()
        steps = p["g6"]["commit_sequence"]
        steps[2], steps[4] = steps[4], steps[2]
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_commit_step_cannot_be_removed(self):
        p = plan()
        p["g6"]["commit_sequence"].remove("LATCH_STOP_BEFORE_ACTION")
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_actual_anchor_cannot_be_claimed(self):
        p = plan()
        p["g6"]["critical_limits"]["actual_monotonic_anchor_available"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_signatures_cannot_be_claimed_available(self):
        p = plan()
        p["g6"]["critical_limits"][
            "actual_cryptographic_signatures_available"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_host_io_cannot_be_claimed_implemented(self):
        p = plan()
        p["g6"]["host_io_implemented"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_host_io_cannot_be_approved(self):
        p = plan()
        p["g6"]["host_io_approved"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_stop_release_cannot_be_approved(self):
        p = plan()
        p["g6"]["stop_release_approved"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_fault_cannot_change_outcome_to_go(self):
        p = plan()
        p["g6"]["failure_scenarios"][0]["design_outcome"] = "GO"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_fault_cannot_claim_real_injection(self):
        p = plan()
        p["g6"]["failure_scenarios"][0]["real_fault_injected"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_future_independent_proof_cannot_be_waived(self):
        p = plan()
        p["g6"]["failure_scenarios"][0]["independent_proof_required"] = False
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_fault_duplicate_or_missing_rejected(self):
        p = plan()
        p["g6"]["failure_scenarios"][1]["threat"] = "ATOMIC_COMMIT_TORN"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)
        p = plan()
        p["g6"]["failure_scenarios"].pop()
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_g6_recovery_policy_cannot_auto_resume(self):
        p = plan()
        p["g6"]["recovery_policy"] = "AUTOMATIC_STOP_RELEASE"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_every_permission_flag_blocks_true_and_integer_zero(self):
        for k in plan()["approvals"]:
            with self.subTest(k=k):
                p = plan()
                p["approvals"][k] = True
                self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)
                p = plan()
                p["approvals"][k] = 0
                self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_approval_extra_operation_rejected(self):
        p = plan()
        p["approvals"]["create_second_demo"] = False
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_top_scope_cannot_enable_runtime(self):
        p = plan()
        p["scope"] = "REAL_BROKER_READY"
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_top_go_and_verified_values_rejected(self):
        for k, v in (("runtime_go_no_go", "GO"), ("verified_values", {}),
                     ("phase_1", "READY")):
            with self.subTest(k=k):
                p = plan()
                p[k] = v
                self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_top_bool_schema_rejected(self):
        p = plan()
        p["schema_version"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_top_extra_permission_rejected(self):
        p = plan()
        p["live_orders"] = True
        self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=p)

    def test_source_old_report_current_state_cannot_be_forged(self):
        old = ledger()
        old["positions_status"] = "ABSENT"
        self.check("D530_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_source_old_timestamp_cannot_be_invented(self):
        old = ledger()
        old["evidence"][0]["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D530_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_source_prior_macd_sample_cannot_be_converted_to_current(self):
        old = ledger()
        old["evidence"][0]["current_state_verified"] = True
        self.check("D530_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_gap_g2_cannot_be_resolved(self):
        gap = gaps()
        next(x for x in gap["gaps"] if x["id"] == "G2")[
            "real_world_verified"] = True
        self.check("D530_GAP_BASELINE_REJECTED_FAIL_CLOSED", gap=gap)

    def test_gap_g6_cannot_release_blocker(self):
        gap = gaps()
        next(x for x in gap["gaps"] if x["id"] == "G6")[
            "release_blocker"] = False
        self.check("D530_GAP_BASELINE_REJECTED_FAIL_CLOSED", gap=gap)

    def test_gap_other_gates_cannot_be_implicitly_resolved(self):
        gap = gaps()
        next(x for x in gap["gaps"] if x["id"] == "G9")[
            "implementation_status"] = "RESOLVED"
        self.check("D530_GAP_BASELINE_REJECTED_FAIL_CLOSED", gap=gap)

    def test_case_g2_raw_secret_detection_denied(self):
        c = fixture()
        c["g2_simulated_privacy"] = "SYNTHETIC_RAW_SECRET_PRESENT"
        self.check("D530_G2_CAPTURE_OR_PRIVACY_UNSAFE_NO_GO", c=c)

    def test_case_g2_unknown_provenance_denied(self):
        c = fixture()
        c["g2_simulated_privacy"] = "SYNTHETIC_UNKNOWN_PROVENANCE"
        self.check("D530_G2_CAPTURE_OR_PRIVACY_UNSAFE_NO_GO", c=c)

    def test_case_g2_scope_mismatch_denied(self):
        c = fixture()
        c["g2_simulated_privacy"] = "SYNTHETIC_ACCOUNT_SCOPE_MISMATCH"
        self.check("D530_G2_CAPTURE_OR_PRIVACY_UNSAFE_NO_GO", c=c)

    def test_case_g2_time_missing_denied(self):
        c = fixture()
        c["g2_simulated_privacy"] = "SYNTHETIC_TIME_MISSING"
        self.check("D530_G2_CAPTURE_OR_PRIVACY_UNSAFE_NO_GO", c=c)

    def test_case_all_g6_faults_denied(self):
        states = (
            "SYNTHETIC_TORN_COMMIT", "SYNTHETIC_REFERENCE_ROLLBACK",
            "SYNTHETIC_CO_EDITED", "SYNTHETIC_REVOCATION_ERASED",
            "SYNTHETIC_WRITER_CONFLICT", "SYNTHETIC_CLOCK_RESTART",
            "SYNTHETIC_KEY_TAMPER", "SYNTHETIC_STORAGE_FAILURE",
            "SYNTHETIC_STALE_BACKUP",
        )
        for state in states:
            with self.subTest(state=state):
                c = fixture()
                c["g6_simulated_recovery"] = state
                self.check("D530_G6_RECOVERY_UNTRUSTED_NO_GO", c=c)

    def test_case_operation_claims_denied_each(self):
        ops = ("VISUAL_REVIEW", "MT4_LAUNCH", "ACCOUNT_LOGIN", "MT4_READ_ONLY",
               "HOST_IO", "EA_EX4", "ORDER", "STOP_RELEASE",
               "LIVE_TRADING", "MESSAGE_SEND")
        for op in ops:
            with self.subTest(op=op):
                c = fixture()
                c["requested_operation"] = op
                self.check("D530_UNAUTHORIZED_OPERATION_DENIED_NO_GO", c=c)

    def test_case_unverified_future_approval_claim_denied(self):
        c = fixture()
        c["future_approval_claim"] = True
        self.check("D530_UNAUTHORIZED_OPERATION_DENIED_NO_GO", c=c)

    def test_case_operation_prioritized_over_simulated_faults(self):
        c = fixture()
        c["g2_simulated_privacy"] = "SYNTHETIC_RAW_SECRET_PRESENT"
        c["requested_operation"] = "ORDER"
        self.check("D530_UNAUTHORIZED_OPERATION_DENIED_NO_GO", c=c)

    def test_case_unknown_privacy_enum_rejected(self):
        c = fixture()
        c["g2_simulated_privacy"] = "REAL_REDACTION_APPROVED"
        self.check("D530_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_unknown_restore_enum_rejected(self):
        c = fixture()
        c["g6_simulated_recovery"] = "HOST_IO_SUCCESS"
        self.check("D530_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_invalid_origin_and_schema_rejected(self):
        for k, v in (("origin", "LIVE"), ("schema_version", True),
                     ("schema_version", 2)):
            with self.subTest(k=k):
                c = fixture()
                c[k] = v
                self.check("D530_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_real_evidence_field_rejected(self):
        c = fixture()
        c["raw_mt4_log"] = "SENSITIVE"
        self.check("D530_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_false_simulation_flag_rejected(self):
        c = fixture()
        c["simulated_only"] = False
        self.check("D530_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_case_integer_future_approval_claim_rejected(self):
        c = fixture()
        c["future_approval_claim"] = 1
        self.check("D530_CASE_REJECTED_FAIL_CLOSED", c=c)

    def test_invalid_input_types_fail_closed(self):
        for value in (None, {}, [], "LIVE", True):
            with self.subTest(value=repr(value)):
                self.check("D530_CASE_REJECTED_FAIL_CLOSED", c=value)
                self.check("D530_DESIGN_REJECTED_FAIL_CLOSED", p=value)

    def test_pure_audit_does_not_mutate_any_inputs(self):
        p, old, gap, c = plan(), ledger(), gaps(), fixture()
        before = copy.deepcopy((p, old, gap, c))
        self.denied(review_d530_offline_architecture(p, old, gap, c))
        self.assertEqual((p, old, gap, c), before)

    def test_pure_audit_no_actual_file_access_or_network(self):
        p, old, gap, c = plan(), ledger(), gaps(), fixture()
        with patch("builtins.open", side_effect=AssertionError("I/O prohibited")):
            self.denied(review_d530_offline_architecture(p, old, gap, c))

    def test_repeated_calls_do_not_retain_an_approval(self):
        p, old, gap = plan(), ledger(), gaps()
        self.denied(review_d530_offline_architecture(p, old, gap, fixture()))
        c = fixture()
        c["requested_operation"] = "LIVE_TRADING"
        self.check("D530_UNAUTHORIZED_OPERATION_DENIED_NO_GO",
                   p=p, old=old, gap=gap, c=c)
        self.check("D530_ARCHITECTURE_DESIGN_COHERENT_NEVER_AUTHORIZED",
                   p=p, old=old, gap=gap)

    def test_d530_status_all_gates_still_unresolved(self):
        status = load("p0_01_d5_30_status.json")
        self.assertEqual(status["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.assertEqual(status["phase_1"], "BLOCKED")
        self.assertEqual(status["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(status["verified_values"])
        for key in ("broker_verified", "terminal_execution_approved",
                    "forward_trading_enabled", "g2_real_world_resolved",
                    "g6_real_world_resolved", "g6_host_io_approved"):
            self.assertIs(status[key], False)


if __name__ == "__main__":
    unittest.main()
