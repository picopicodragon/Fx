"""D5-35: issuer/key-transition and G2 multi-surface deny-only tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_35_handoff_review import (
    _FALSE, review_d535_handoff,
)

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def c35(): return read("p0_01_d5_35_handoff_contract.json")
def c34(): return read("p0_01_d5_34_lineage_contract.json")
def c33(): return read("p0_01_d5_33_proof_boundary_contract.json")
def c32(): return read("p0_01_d5_32_crash_matrix_contract.json")
def c31(): return read("p0_01_d5_31_protocol_privacy_contract.json")
def old(): return read("p0_01_d5_17_evidence_reconciliation_status.json")
def gaps(): return read("p0_01_d5_25_gap_verification_matrix.json")
def f32(): return read("p0_01_d5_32_synthetic_fixture.json")
def f33(): return read("p0_01_d5_33_synthetic_fixture.json")
def f34(): return read("p0_01_d5_34_synthetic_fixture.json")
def f35(): return read("p0_01_d5_35_synthetic_fixture.json")


class D535HandoffTests(TestCase):
    def check(self, expected, plan=_DEFAULT, prior34=_DEFAULT,
              prior33=_DEFAULT, prior32=_DEFAULT, prior31=_DEFAULT,
              ledger=_DEFAULT, gap=_DEFAULT, snapshot32=_DEFAULT,
              snapshot33=_DEFAULT, snapshot34=_DEFAULT, case=_DEFAULT):
        r = review_d535_handoff(
            c35() if plan is _DEFAULT else plan,
            c34() if prior34 is _DEFAULT else prior34,
            c33() if prior33 is _DEFAULT else prior33,
            c32() if prior32 is _DEFAULT else prior32,
            c31() if prior31 is _DEFAULT else prior31,
            old() if ledger is _DEFAULT else ledger,
            gaps() if gap is _DEFAULT else gap,
            f32() if snapshot32 is _DEFAULT else snapshot32,
            f33() if snapshot33 is _DEFAULT else snapshot33,
            f34() if snapshot34 is _DEFAULT else snapshot34,
            f35() if case is _DEFAULT else case,
        )
        self.assertEqual(r["status"], expected)
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(r["verified_values"])
        self.assertIs(r["safety_hold_latched"], True)
        self.assertEqual(r["effective_approved_actions"], [])
        self.assertEqual(r["account_identity_consistency"], "NOT_RECONCILED")
        for k in ("current_positions", "current_pending_orders", "current_ea_state"):
            self.assertEqual(r[k], "UNKNOWN")
        for k in _FALSE:
            self.assertIs(r[k], False, k)
        self.assertEqual(set(r), set(_FALSE) | {
            "status", "d534_status", "effective_approved_actions",
            "safety_hold_latched", "account_identity_consistency",
            "current_positions", "current_pending_orders", "current_ea_state",
            "phase_1", "runtime_go_no_go", "verified_values",
        })
        return r

    def test_matching_synthetic_lifecycle_is_not_real_authority(self):
        r = self.check("D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["d534_status"],
                         "D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED")

    def test_all_three_public_surfaces_use_same_fixed_json(self):
        c = f35()
        self.assertEqual([x["surface"] for x in c["publication_surfaces"]],
                         ["DESIGN_RECORD", "STATUS_SUMMARY", "REVIEW_SUMMARY"])
        self.assertTrue(all(x["public_json"] == f34()["public_export"]["public_json"]
                            for x in c["publication_surfaces"]))
        self.check("D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED")

    def test_base_lineage_key_state_not_verified_as_real(self):
        r = self.check("D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED")
        for field in ("g6_actual_key_revocation_verified",
                      "g6_real_key_issuer_authenticated",
                      "g6_actual_signature_validated", "g6_real_key_store_verified"):
            self.assertIs(r[field], False)

    def test_explicit_rotation_denied(self):
        c = f35()
        c["transition"]["event"] = "ROTATION"
        self.check("D535_G6_UNVERIFIED_ISSUER_ROTATION_NO_GO", case=c)

    def test_rotation_with_new_issuer_denied(self):
        c = f35()
        c["transition"]["event"] = "ROTATION"
        c["transition"]["next_issuer"] = "SYNTHETIC_ISSUER_B"
        c["transition"]["next_epoch"] = 2
        self.check("D535_G6_UNVERIFIED_ISSUER_ROTATION_NO_GO", case=c)

    def test_explicit_key_revocation_denied(self):
        c = f35()
        c["transition"]["event"] = "KEY_REVOCATION"
        self.check("D535_G6_REVOCATION_EVENT_UNVERIFIED_NO_GO", case=c)

    def test_emergency_stop_event_still_no_go(self):
        c = f35()
        c["transition"]["event"] = "EMERGENCY_STOP"
        self.check("D535_G6_REVOCATION_EVENT_UNVERIFIED_NO_GO", case=c)

    def test_next_issuer_changed_without_rotation_denied(self):
        c = f35()
        c["transition"]["next_issuer"] = "SYNTHETIC_ISSUER_B"
        self.check("D535_G6_UNDECLARED_ISSUER_CHANGE_NO_GO", case=c)

    def test_next_epoch_changed_without_rotation_denied(self):
        c = f35()
        c["transition"]["next_epoch"] = 2
        self.check("D535_G6_UNDECLARED_ISSUER_CHANGE_NO_GO", case=c)

    def test_next_generation_advances_without_pin_denied(self):
        c = f35()
        c["transition"]["next_generation"] = 2
        self.check("D535_G6_UNPINNED_LINEAGE_ADVANCE_NO_GO", case=c)

    def test_next_sequence_advances_without_pin_denied(self):
        c = f35()
        c["transition"]["next_sequence"] = 4
        self.check("D535_G6_UNPINNED_LINEAGE_ADVANCE_NO_GO", case=c)

    def test_generation_rollback_denied(self):
        c = f35()
        c["transition"]["next_generation"] = 0
        self.check("D535_G6_EPOCH_OR_SEQUENCE_ROLLBACK_NO_GO", case=c)

    def test_sequence_rollback_denied(self):
        c = f35()
        c["transition"]["next_sequence"] = 2
        self.check("D535_G6_EPOCH_OR_SEQUENCE_ROLLBACK_NO_GO", case=c)

    def test_prior_generation_mismatch_denied(self):
        c = f35()
        c["transition"]["prior_generation"] = 2
        self.check("D535_G6_PREDECESSOR_SCOPE_MISMATCH_NO_GO", case=c)

    def test_prior_sequence_mismatch_denied(self):
        c = f35()
        c["transition"]["prior_sequence"] = 4
        self.check("D535_G6_PREDECESSOR_SCOPE_MISMATCH_NO_GO", case=c)

    def test_prior_epoch_mismatch_denied(self):
        c = f35()
        c["transition"]["prior_epoch"] = 2
        self.check("D535_G6_PREDECESSOR_SCOPE_MISMATCH_NO_GO", case=c)

    def test_prior_issuer_mismatch_denied(self):
        c = f35()
        c["transition"]["prior_issuer"] = "SYNTHETIC_ISSUER_B"
        self.check("D535_G6_PREDECESSOR_SCOPE_MISMATCH_NO_GO", case=c)

    def test_revocation_tombstone_erasure_denied(self):
        c = f35()
        c["transition"]["revocation_after"] = False
        self.check("D535_G6_REVOCATION_ERASURE_NO_GO", case=c)

    def test_revocation_prior_mismatch_denied(self):
        c = f35()
        c["transition"]["revocation_before"] = False
        self.check("D535_G6_PREDECESSOR_SCOPE_MISMATCH_NO_GO", case=c)

    def test_stop_latch_release_denied(self):
        c = f35()
        c["transition"]["stop_latched"] = False
        self.check("D535_G6_STOP_LATCH_LOST_NO_GO", case=c)

    def test_user_stop_release_claim_denied(self):
        c = f35()
        c["stop_release_claim"] = True
        self.check("D535_OPERATION_CLAIM_DENIED_NO_GO", case=c)

    def test_real_operation_claim_denied(self):
        c = f35()
        c["real_operation_claim"] = True
        self.check("D535_OPERATION_CLAIM_DENIED_NO_GO", case=c)

    def test_prior_key_active_claim_untrusted(self):
        c = f35()
        c["transition"]["prior_key_state"] = "SYNTHETIC_ACTIVE_CLAIM"
        self.check("D535_G6_PRIOR_KEY_STATE_UNTRUSTED_NO_GO", case=c)

    def test_prior_key_revoked_claim_untrusted(self):
        c = f35()
        c["transition"]["prior_key_state"] = "SYNTHETIC_REVOKED_CLAIM"
        self.check("D535_G6_PRIOR_KEY_STATE_UNTRUSTED_NO_GO", case=c)

    def test_next_key_active_claim_untrusted(self):
        c = f35()
        c["transition"]["next_key_state"] = "SYNTHETIC_ACTIVE_CLAIM"
        self.check("D535_G6_KEY_STATE_CHANGE_UNVERIFIED_NO_GO", case=c)

    def test_next_key_revoked_claim_untrusted(self):
        c = f35()
        c["transition"]["next_key_state"] = "SYNTHETIC_REVOKED_CLAIM"
        self.check("D535_G6_KEY_STATE_CHANGE_UNVERIFIED_NO_GO", case=c)

    def test_next_key_unknown_change_untrusted(self):
        c = f35()
        c["transition"]["next_key_state"] = "SYNTHETIC_UNKNOWN"
        self.check("D535_G6_KEY_STATE_CHANGE_UNVERIFIED_NO_GO", case=c)

    def test_synthetic_observation_stale_denied(self):
        c = f35()
        c["transition"]["observed_tick"] = 94
        self.check("D535_G6_SYNTHETIC_TICK_UNTRUSTED_NO_GO", case=c)

    def test_synthetic_observation_in_future_denied(self):
        c = f35()
        c["transition"]["observed_tick"] = 101
        self.check("D535_G6_SYNTHETIC_TICK_UNTRUSTED_NO_GO", case=c)

    def test_synthetic_tick_scope_mismatch_denied(self):
        c = f35()
        c["transition"]["simulated_reference_tick"] = 101
        self.check("D535_G6_SYNTHETIC_TICK_SCOPE_MISMATCH_NO_GO", case=c)

    def test_synthetic_max_boundary_still_not_authorized(self):
        c = f35()
        c["transition"]["observed_tick"] = 95
        self.check("D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED", case=c)

    def test_public_surface_swap_denied(self):
        c = f35()
        c["publication_surfaces"].reverse()
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_public_surface_missing_denied(self):
        c = f35()
        c["publication_surfaces"].pop()
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_public_surface_extra_denied(self):
        c = f35()
        c["publication_surfaces"].append(copy.deepcopy(c["publication_surfaces"][0]))
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_public_surface_extra_log_denied(self):
        c = f35()
        c["publication_surfaces"][0]["raw_mt4_log"] = "SYNTHETIC_LOG"
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_public_surface_duplicate_json_field_denied(self):
        c = f35()
        s = c["publication_surfaces"][0]
        s["public_json"] = s["public_json"].replace(
            '"schema_version":1', '"schema_version":1,"schema_version":1')
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_public_surface_nested_secret_denied(self):
        c = f35()
        p = json.loads(c["publication_surfaces"][0]["public_json"])
        p["extra"] = {"account_number": "SYNTHETIC_SECRET"}
        c["publication_surfaces"][0]["public_json"] = json.dumps(
            p, sort_keys=True, separators=(",", ":"))
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_public_surface_valid_different_check_id_denied(self):
        c = f35()
        c["publication_surfaces"][0]["public_json"] = (
            c["publication_surfaces"][0]["public_json"].replace(
                "D530-G2-01", "D530-G2-02"))
        self.check("D535_G2_PUBLIC_SURFACE_MISMATCH_NO_GO", case=c)

    def test_public_surface_bool_as_integer_denied(self):
        c = f35()
        c["publication_surfaces"][0]["private_payload_present"] = 0
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_contract_no_extra_public_surface_allowed(self):
        c = c35()
        c["g2"]["synthetic_public_surfaces"].append("REAL_GIT")
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_real_git_hook_claim(self):
        c = c35()
        c["g2"]["real_git_hook_implemented"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_real_secret_scan_claim(self):
        c = c35()
        c["g2"]["real_secret_scan_implemented"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_private_export_approval(self):
        c = c35()
        c["g2"]["private_export_authorized"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_real_key_authority(self):
        c = c35()
        c["g6"]["independent_key_authority_implemented"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_real_key_revocation(self):
        c = c35()
        c["g6"]["actual_revocation_proof_verified"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_real_issuer_handoff(self):
        c = c35()
        c["g6"]["actual_issuer_handoff_verified"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_real_epoch_pin(self):
        c = c35()
        c["g6"]["actual_epoch_pin_verified"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_real_storage_replay(self):
        c = c35()
        c["g6"]["real_storage_replay_checked"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_actual_signature(self):
        c = c35()
        c["g6"]["actual_signature_verified"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_actual_anchor(self):
        c = c35()
        c["g6"]["actual_anchor_available"] = True
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_runtime_go(self):
        c = c35()
        c["runtime_go_no_go"] = "GO"
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_verified_values(self):
        c = c35()
        c["verified_values"] = {}
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_contract_rejects_unapproved_event(self):
        c = c35()
        c["g6"]["handoff_states"].append("REAL_KEY_DEPLOYED")
        self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=c)

    def test_invalid_contract_types_denied(self):
        for obj in (None, True, [], {}, "LIVE"):
            with self.subTest(value=repr(obj)):
                self.check("D535_CONTRACT_REJECTED_FAIL_CLOSED", plan=obj)

    def test_invalid_case_types_denied(self):
        for obj in (None, False, [], {}, "LIVE"):
            with self.subTest(value=repr(obj)):
                self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=obj)

    def test_case_extra_sensitive_field_denied(self):
        c = f35()
        c["account_number"] = "SYNTHETIC_SECRET"
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_case_fake_issuer_type_denied(self):
        c = f35()
        c["transition"]["next_issuer"] = "REAL_ISSUER"
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_case_bool_generation_denied(self):
        c = f35()
        c["transition"]["next_generation"] = True
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_case_bool_epoch_denied(self):
        c = f35()
        c["transition"]["next_epoch"] = True
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_case_unknown_key_state_denied(self):
        c = f35()
        c["transition"]["next_key_state"] = "VERIFIED_ACTIVE"
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_case_unknown_transition_event_denied(self):
        c = f35()
        c["transition"]["event"] = "AUTO_RECOVERY_GO"
        self.check("D535_CASE_REJECTED_FAIL_CLOSED", case=c)

    def test_predecessor_g6_mismatch_does_not_promote(self):
        c = f34()
        c["lineage"]["anchor"]["generation"] = 2
        self.check("D535_PREDECESSOR_NOT_COHERENT_NO_GO", snapshot34=c)

    def test_predecessor_g2_private_export_denied(self):
        c = f34()
        c["public_export"]["private_export_requested"] = True
        self.check("D535_PREDECESSOR_NOT_COHERENT_NO_GO", snapshot34=c)

    def test_predecessor_old_user_account_not_reconciled(self):
        ev = old()
        ev["account_identity_consistency"] = "RECONCILED"
        self.check("D535_PREDECESSOR_NOT_COHERENT_NO_GO", ledger=ev)

    def test_predecessor_g1_g9_not_resolved(self):
        gap = gaps()
        next(x for x in gap["gaps"] if x["id"] == "G6")[
            "real_world_verified"] = True
        self.check("D535_PREDECESSOR_NOT_COHERENT_NO_GO", gap=gap)

    def test_child_forged_go_denied(self):
        with patch(
            "scripts.p0_01_d5_35_handoff_review.review_d534_lineage",
            return_value={"status":
                "D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED",
                "runtime_go_no_go": "GO"},
        ):
            self.check("D535_CHILD_SAFETY_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_child_forged_broker_verified_denied(self):
        from scripts.p0_01_d5_34_lineage_privacy import (
            review_d534_lineage as original,
        )
        child = original(c34(), c33(), c32(), c31(),
                         old(), gaps(), f32(), f33(), f34())
        child["broker_verified"] = True
        with patch(
            "scripts.p0_01_d5_35_handoff_review.review_d534_lineage",
            return_value=child,
        ):
            self.check("D535_CHILD_SAFETY_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_forged_child_coherent_but_wrong_status_denied(self):
        from scripts.p0_01_d5_34_lineage_privacy import (
            review_d534_lineage as original,
        )
        child = original(c34(), c33(), c32(), c31(),
                         old(), gaps(), f32(), f33(), f34())
        child["status"] = "SYNTHETIC_COMPLETED"
        with patch(
            "scripts.p0_01_d5_35_handoff_review.review_d534_lineage",
            return_value=child,
        ):
            self.check("D535_PREDECESSOR_NOT_COHERENT_NO_GO")

    def test_repeated_calls_do_not_inherit_approval(self):
        self.check("D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED")
        c = f35()
        c["stop_release_claim"] = True
        self.check("D535_OPERATION_CLAIM_DENIED_NO_GO", case=c)
        self.check("D535_SYNTHETIC_LIFECYCLE_COHERENT_NEVER_AUTHORIZED")

    def test_pure_review_does_not_read_local_files(self):
        args = (c35(), c34(), c33(), c32(), c31(), old(), gaps(),
                f32(), f33(), f34(), f35())
        with patch("builtins.open", side_effect=AssertionError("real IO forbidden")):
            r = review_d535_handoff(*args)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_pure_review_does_not_mutate_inputs(self):
        args = (c35(), c34(), c33(), c32(), c31(), old(), gaps(),
                f32(), f33(), f34(), f35())
        before = copy.deepcopy(args)
        review_d535_handoff(*args)
        self.assertEqual(args, before)

    def test_d535_state_g1_g9_all_unresolved(self):
        s = read("p0_01_d5_35_status.json")
        self.assertEqual(s["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        for key in ("g2_real_world_resolved", "g6_real_world_resolved",
                    "broker_verified", "terminal_execution_approved",
                    "host_io_approved", "forward_trading_enabled"):
            self.assertIs(s[key], False)


# Create independent unittest methods for every real-proof claim and
# each of the three hypothetical public surfaces.
def _fake_proof_test(field):
    def test(self):
        c = f35()
        c["transition"][field] = True
        self.check("D535_G6_FALSE_REAL_PROOF_CLAIM_NO_GO", case=c)
    return test


def _surface_flag_test(index, field):
    def test(self):
        c = f35()
        c["publication_surfaces"][index][field] = True
        self.check("D535_G2_PRIVATE_PUBLICATION_DENIED_NO_GO", case=c)
    return test


for _field in ("independent_handoff_attested",
               "independent_revocation_attested", "signature_verified",
               "epoch_pinned", "durable_tombstone_verified",
               "human_approved"):
    setattr(D535HandoffTests, "test_reject_fake_proof_" + _field,
            _fake_proof_test(_field))

for _i in range(3):
    for _field in ("private_payload_present", "private_export_requested",
                   "real_scan_claim"):
        setattr(D535HandoffTests, f"test_surface_{_i}_{_field}",
                _surface_flag_test(_i, _field))


if __name__ == "__main__":
    main()
