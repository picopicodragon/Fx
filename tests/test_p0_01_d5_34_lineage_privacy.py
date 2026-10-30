"""D5-34: G2 synthetic export and G6 witness lineage regression checks."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_34_lineage_privacy import (
    _FALSE, review_d534_lineage,
)

ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def read(name):
    with (ROOT / "specs" / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def contract():
    return read("p0_01_d5_34_lineage_contract.json")


def prev33():
    return read("p0_01_d5_33_proof_boundary_contract.json")


def prev32():
    return read("p0_01_d5_32_crash_matrix_contract.json")


def prev31():
    return read("p0_01_d5_31_protocol_privacy_contract.json")


def evidence():
    return read("p0_01_d5_17_evidence_reconciliation_status.json")


def gaps():
    return read("p0_01_d5_25_gap_verification_matrix.json")


def matrix():
    return read("p0_01_d5_32_synthetic_fixture.json")


def prior_case():
    return read("p0_01_d5_33_synthetic_fixture.json")


def scenario():
    return read("p0_01_d5_34_synthetic_fixture.json")


class D534LineageTests(TestCase):
    def check(self, expected, c=_UNSET, p33=_UNSET, p32=_UNSET, p31=_UNSET,
              ev=_UNSET, gs=_UNSET, mat=_UNSET, sc33=_UNSET, sc34=_UNSET):
        r = review_d534_lineage(
            contract() if c is _UNSET else c,
            prev33() if p33 is _UNSET else p33,
            prev32() if p32 is _UNSET else p32,
            prev31() if p31 is _UNSET else p31,
            evidence() if ev is _UNSET else ev,
            gaps() if gs is _UNSET else gs,
            matrix() if mat is _UNSET else mat,
            prior_case() if sc33 is _UNSET else sc33,
            scenario() if sc34 is _UNSET else sc34,
        )
        self.assertEqual(r["status"], expected)
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(r["verified_values"])
        self.assertIs(r["safety_hold_latched"], True)
        self.assertEqual(r["effective_approved_actions"], [])
        self.assertEqual(r["account_identity_consistency"], "NOT_RECONCILED")
        for k in ("current_positions", "current_pending_orders",
                  "current_ea_state"):
            self.assertEqual(r[k], "UNKNOWN")
        for k in _FALSE:
            self.assertIs(r[k], False, k)
        self.assertEqual(set(r), set(_FALSE) | {
            "status", "d533_status", "effective_approved_actions",
            "safety_hold_latched", "account_identity_consistency",
            "current_positions", "current_pending_orders",
            "current_ea_state", "phase_1", "runtime_go_no_go",
            "verified_values",
        })
        return r

    def test_baseline_lineage_is_only_synthetic_no_go(self):
        r = self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED")
        self.assertEqual(r["d533_status"],
                         "D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED")

    def test_baseline_has_three_distinct_role_names_but_not_real_trust(self):
        s = scenario()["lineage"]
        self.assertEqual((s["journal"]["issuer_id"], s["anchor"]["issuer_id"],
                          s["revocation"]["issuer_id"]),
                         ("SYNTHETIC_ISSUER_A",) * 3)
        r = self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED")
        self.assertIs(r["g6_issuer_authentication_real"], False)

    def test_only_fixed_public_json_is_carried_forward(self):
        s = scenario()
        self.assertEqual(s["public_export"]["public_json"],
                         prior_case()["public_json"])
        self.assertFalse(s["public_export"]["private_payload_attached"])
        self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED", sc34=s)

    def test_private_export_request_denied(self):
        s = scenario()
        s["public_export"]["private_export_requested"] = True
        self.check("D534_G2_EXPORT_BOUNDARY_DENIED_NO_GO", sc34=s)

    def test_raw_private_attachment_denied(self):
        s = scenario()
        s["public_export"]["private_payload_attached"] = True
        self.check("D534_G2_EXPORT_BOUNDARY_DENIED_NO_GO", sc34=s)

    def test_git_write_request_denied(self):
        s = scenario()
        s["public_export"]["git_write_requested"] = True
        self.check("D534_G2_EXPORT_BOUNDARY_DENIED_NO_GO", sc34=s)

    def test_fake_real_redaction_verified_denied(self):
        s = scenario()
        s["public_export"]["real_redaction_verified"] = True
        self.check("D534_G2_EXPORT_BOUNDARY_DENIED_NO_GO", sc34=s)

    def test_fake_real_operation_claim_denied(self):
        s = scenario()
        s["real_operation_claim"] = True
        self.check("D534_OPERATION_CLAIM_DENIED_NO_GO", sc34=s)

    def test_fake_stop_release_claim_denied(self):
        s = scenario()
        s["stop_release_claim"] = True
        self.check("D534_OPERATION_CLAIM_DENIED_NO_GO", sc34=s)

    def test_public_check_id_mismatch_denied(self):
        s = scenario()
        s["public_export"]["public_json"] = s["public_export"]["public_json"].replace(
            "D530-G2-01", "D530-G2-02")
        self.check("D534_G2_PUBLIC_PRIVATE_LINK_MISMATCH_NO_GO", sc34=s)

    def test_public_nested_account_number_denied(self):
        s = scenario()
        payload = json.loads(s["public_export"]["public_json"])
        payload["account_number"] = "SYNTHETIC_SECRET_ONLY"
        s["public_export"]["public_json"] = json.dumps(
            payload, sort_keys=True, separators=(",", ":"))
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_public_extra_free_text_denied(self):
        s = scenario()
        payload = json.loads(s["public_export"]["public_json"])
        payload["note"] = "SYNTHETIC_SECRET"
        s["public_export"]["public_json"] = json.dumps(
            payload, sort_keys=True, separators=(",", ":"))
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_public_json_duplicate_key_denied(self):
        s = scenario()
        s["public_export"]["public_json"] = s["public_export"]["public_json"].replace(
            '"schema_version":1', '"schema_version":1,"schema_version":1')
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_public_json_unicode_escape_denied(self):
        s = scenario()
        s["public_export"]["public_json"] = s["public_export"]["public_json"].replace(
            "SYNTHETIC_ONLY", "SYNTHETIC_\\u004fNLY")
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_private_reference_is_synthetic_only(self):
        s = scenario()
        s["public_export"]["private_reference_label"] = "REAL_ACCOUNT_123"
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_private_reference_cannot_be_a_free_text_secret(self):
        s = scenario()
        s["public_export"]["private_reference_label"] = (
            "SYNTHETIC_PRIVATE_REF_B\nsecret")
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_public_additional_secret_field_rejected(self):
        s = scenario()
        s["public_export"]["raw_mt4_log"] = "SYNTHETIC_LOG"
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_anchor_old_generation_even_when_timestamp_fresh(self):
        s = scenario()
        s["lineage"]["journal"]["generation"] = 2
        s["lineage"]["revocation"]["generation"] = 2
        s["lineage"]["anchor"]["generation"] = 1
        s["lineage"]["anchor"]["observed_tick"] = 100
        self.check("D534_G6_ANCHOR_BEHIND_NO_GO", sc34=s)

    def test_anchor_old_sequence_even_when_timestamp_fresh(self):
        s = scenario()
        s["lineage"]["journal"]["sequence"] = 4
        s["lineage"]["revocation"]["sequence"] = 4
        s["lineage"]["anchor"]["sequence"] = 3
        s["lineage"]["anchor"]["observed_tick"] = 100
        self.check("D534_G6_ANCHOR_BEHIND_NO_GO", sc34=s)

    def test_anchor_ahead_of_unconfirmed_journal(self):
        s = scenario()
        s["lineage"]["anchor"]["generation"] = 2
        self.check("D534_G6_ANCHOR_AHEAD_NO_GO", sc34=s)

    def test_revocation_register_ahead_of_journal(self):
        s = scenario()
        s["lineage"]["revocation"]["generation"] = 2
        self.check("D534_G6_REVOCATION_AHEAD_NO_GO", sc34=s)

    def test_revocation_sequence_ahead_of_journal(self):
        s = scenario()
        s["lineage"]["revocation"]["sequence"] = 4
        self.check("D534_G6_REVOCATION_AHEAD_NO_GO", sc34=s)

    def test_revocation_register_behind_journal(self):
        s = scenario()
        s["lineage"]["revocation"]["generation"] = 0
        self.check("D534_G6_REVOCATION_BEHIND_NO_GO", sc34=s)

    def test_revocation_sequence_behind_journal(self):
        s = scenario()
        s["lineage"]["revocation"]["sequence"] = 2
        self.check("D534_G6_REVOCATION_BEHIND_NO_GO", sc34=s)

    def test_issuer_rotation_claim_unverified_denied(self):
        s = scenario()
        s["lineage"]["rotation_claim"] = "SYNTHETIC_ROTATED"
        self.check("D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO", sc34=s)

    def test_issuer_rotation_marked_real_verified_denied(self):
        s = scenario()
        s["lineage"]["real_handoff_verified"] = True
        self.check("D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO", sc34=s)

    def test_independent_authentication_forged_denied(self):
        s = scenario()
        s["lineage"]["independent_witness_authenticated"] = True
        self.check("D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO", sc34=s)

    def test_previous_issuer_changed_denied(self):
        s = scenario()
        s["lineage"]["previous_issuer_id"] = "SYNTHETIC_ISSUER_B"
        self.check("D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO", sc34=s)

    def test_previous_issuer_epoch_changed_denied(self):
        s = scenario()
        s["lineage"]["previous_issuer_epoch"] = 2
        self.check("D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO", sc34=s)

    def test_all_issuers_changed_together_still_unverified(self):
        s = scenario()
        s["lineage"]["previous_issuer_id"] = "SYNTHETIC_ISSUER_B"
        for role in ("journal", "anchor", "revocation"):
            s["lineage"][role]["issuer_id"] = "SYNTHETIC_ISSUER_B"
        self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED", sc34=s)

    def test_all_epoch_values_changed_together_still_unverified(self):
        s = scenario()
        s["lineage"]["previous_issuer_epoch"] = 2
        for role in ("journal", "anchor", "revocation"):
            s["lineage"][role]["issuer_epoch"] = 2
        r = self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED",
                       sc34=s)
        self.assertIs(r["g6_independent_epoch_verified"], False)

    def test_reference_tick_mismatch_with_d533_denied(self):
        s = scenario()
        s["lineage"]["simulated_reference_tick"] = 101
        self.check("D534_G6_REFERENCE_TICK_SCOPE_MISMATCH_NO_GO", sc34=s)

    def test_simulated_clock_is_not_a_real_second(self):
        r = self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED")
        self.assertIs(r["g6_anchor_freshness_real"], False)

    def test_predecessor_witness_tick_mismatch_denied(self):
        s = scenario()
        s["lineage"]["anchor"]["observed_tick"] = 99
        self.check("D534_G6_PREDECESSOR_WITNESS_MISMATCH_NO_GO", sc34=s)

    def test_predecessor_witness_generation_mismatch_denied(self):
        p33 = prior_case()
        p33["synthetic_proofs"][1]["generation"] = 2
        self.check("D534_PREDECESSOR_NOT_COHERENT_NO_GO", sc33=p33)

    def test_predecessor_missing_private_scope_denied(self):
        p33 = prior_case()
        p33["private_envelope"]["account_identity_verified"] = True
        self.check("D534_PREDECESSOR_NOT_COHERENT_NO_GO", sc33=p33)

    def test_predecessor_old_account_state_cannot_be_reconciled(self):
        old = evidence()
        old["account_identity_consistency"] = "RECONCILED"
        self.check("D534_PREDECESSOR_NOT_COHERENT_NO_GO", ev=old)

    def test_gap_g6_claim_verified_does_not_allow_runtime(self):
        gs = gaps()
        next(x for x in gs["gaps"] if x["id"] == "G6")[
            "real_world_verified"] = True
        self.check("D534_PREDECESSOR_NOT_COHERENT_NO_GO", gs=gs)

    def test_invalid_plan_denied(self):
        for value in (None, [], {}, "READY", True):
            with self.subTest(value=repr(value)):
                self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=value)

    def test_invalid_scenario_denied(self):
        for value in (None, [], {}, "LIVE", True):
            with self.subTest(value=repr(value)):
                self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=value)

    def test_plan_g2_public_field_expansion_denied(self):
        c = contract()
        c["g2"]["allowed_public_fields"].append("account_number")
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_real_git_hook_claim_denied(self):
        c = contract()
        c["g2"]["real_git_hook_installed"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_real_file_scan_claim_denied(self):
        c = contract()
        c["g2"]["real_file_scan_performed"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_real_private_export_claim_denied(self):
        c = contract()
        c["g2"]["real_private_export_allowed"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_g6_role_change_denied(self):
        c = contract()
        c["g6"]["lineage_roles"][1] = "ACTUAL_BROKER"
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_g6_tick_limit_broadened_denied(self):
        c = contract()
        c["g6"]["synthetic_freshness_limit_ticks"] = 100
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_g6_actual_anchor_claim_denied(self):
        c = contract()
        c["g6"]["real_anchor_independent"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_g6_actual_revocation_durable_claim_denied(self):
        c = contract()
        c["g6"]["actual_revocation_durable"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_g6_actual_issuer_claim_denied(self):
        c = contract()
        c["g6"]["actual_issuer_authentication_verified"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_g6_actual_clock_claim_denied(self):
        c = contract()
        c["g6"]["actual_clock_validated"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_real_rollback_protection_claim_denied(self):
        c = contract()
        c["g6"]["real_rollback_protection"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_go_denied(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_verified_values_denied(self):
        c = contract()
        c["verified_values"] = {}
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_extra_order_approval_denied(self):
        c = contract()
        c["order_approved"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_bool_schema_denied(self):
        c = contract()
        c["schema_version"] = True
        self.check("D534_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_case_extra_real_log_field_denied(self):
        s = scenario()
        s["raw_mt4_log"] = "SYNTHETIC_EXAMPLE"
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_case_export_boolean_integer_denied(self):
        s = scenario()
        s["public_export"]["private_payload_attached"] = 0
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_case_invalid_issuer_name_denied(self):
        s = scenario()
        s["lineage"]["journal"]["issuer_id"] = "REAL_ISSUER"
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_case_boolean_epoch_denied(self):
        s = scenario()
        s["lineage"]["anchor"]["issuer_epoch"] = True
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_case_invalid_rotation_literal_denied(self):
        s = scenario()
        s["lineage"]["rotation_claim"] = "REAL_APPROVED"
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_case_invalid_reference_time_type_denied(self):
        s = scenario()
        s["lineage"]["simulated_reference_tick"] = "2026-10-30"
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_case_extra_nested_real_account_denied(self):
        s = scenario()
        s["lineage"]["journal"]["account_number"] = "SYNTHETIC_SECRET"
        self.check("D534_CASE_REJECTED_FAIL_CLOSED", sc34=s)

    def test_forged_child_go_denied(self):
        with patch(
            "scripts.p0_01_d5_34_lineage_privacy.review_d533_independent_proofs",
            return_value={"status":
                "D533_SYNTHETIC_PROOF_FORMAT_COHERENT_NEVER_AUTHORIZED",
                "runtime_go_no_go": "GO"},
        ):
            self.check("D534_CHILD_SAFETY_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_forged_child_broker_verified_denied(self):
        from scripts.p0_01_d5_33_proof_boundary import (
            review_d533_independent_proofs as original,
        )
        child = original(prev33(), prev32(), prev31(),
                         evidence(), gaps(), matrix(), prior_case())
        child["broker_verified"] = True
        with patch(
            "scripts.p0_01_d5_34_lineage_privacy.review_d533_independent_proofs",
            return_value=child,
        ):
            self.check("D534_CHILD_SAFETY_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_public_reference_does_not_leak_into_output(self):
        s = scenario()
        label = s["public_export"]["private_reference_label"]
        result = self.check(
            "D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED", sc34=s)
        self.assertNotIn(label, repr(result))

    def test_inputs_not_mutated(self):
        args = (contract(), prev33(), prev32(), prev31(), evidence(),
                gaps(), matrix(), prior_case(), scenario())
        snapshot = copy.deepcopy(args)
        review_d534_lineage(*args)
        self.assertEqual(args, snapshot)

    def test_runtime_validator_never_reads_os_files(self):
        args = (contract(), prev33(), prev32(), prev31(), evidence(),
                gaps(), matrix(), prior_case(), scenario())
        with patch("builtins.open", side_effect=AssertionError("NO FILE IO")):
            result = review_d534_lineage(*args)
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_repeated_calls_never_remember_authority(self):
        self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED")
        s = scenario()
        s["stop_release_claim"] = True
        self.check("D534_OPERATION_CLAIM_DENIED_NO_GO", sc34=s)
        self.check("D534_SYNTHETIC_LINEAGE_COHERENT_NEVER_AUTHORIZED")

    def test_status_all_gates_unresolved(self):
        s = read("p0_01_d5_34_status.json")
        self.assertEqual(s["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        for k in ("g2_real_world_resolved", "g6_real_world_resolved",
                  "broker_verified", "terminal_execution_approved",
                  "host_io_approved", "forward_trading_enabled"):
            self.assertIs(s[k], False)


# Each role is tested separately for eight classes of synthetic anomalies.
def _build_role_test(role, fault, expected):
    def _test(self):
        sc = scenario()
        item = sc["lineage"][role]
        if fault == "stale_tick":
            item["observed_tick"] = 94
        elif fault == "future_tick":
            item["observed_tick"] = 101
        elif fault == "issuer_switch":
            item["issuer_id"] = "SYNTHETIC_ISSUER_B"
        elif fault == "issuer_epoch":
            item["issuer_epoch"] = 2
        elif fault == "stop_lost":
            item["stop_latched"] = False
        elif fault == "revocation_lost":
            item["revocation_tombstone"] = False
        elif fault == "lower_sequence":
            item["sequence"] = 2
        elif fault == "higher_generation":
            item["generation"] = 2
        self.check(expected, sc34=sc)
    return _test


_ANOMALY_EXPECTATIONS = {
    "journal": (
        ("stale_tick", "D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO"),
        ("future_tick", "D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO"),
        ("issuer_switch", "D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO"),
        ("issuer_epoch", "D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO"),
        ("stop_lost", "D534_G6_STOP_OR_REVOCATION_LOST_NO_GO"),
        ("revocation_lost", "D534_G6_STOP_OR_REVOCATION_LOST_NO_GO"),
        ("lower_sequence", "D534_G6_ANCHOR_AHEAD_NO_GO"),
        ("higher_generation", "D534_G6_ANCHOR_BEHIND_NO_GO"),
    ),
    "anchor": (
        ("stale_tick", "D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO"),
        ("future_tick", "D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO"),
        ("issuer_switch", "D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO"),
        ("issuer_epoch", "D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO"),
        ("stop_lost", "D534_G6_STOP_OR_REVOCATION_LOST_NO_GO"),
        ("revocation_lost", "D534_G6_STOP_OR_REVOCATION_LOST_NO_GO"),
        ("lower_sequence", "D534_G6_ANCHOR_BEHIND_NO_GO"),
        ("higher_generation", "D534_G6_ANCHOR_AHEAD_NO_GO"),
    ),
    "revocation": (
        ("stale_tick", "D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO"),
        ("future_tick", "D534_G6_SYNTHETIC_STALE_OR_FUTURE_NO_GO"),
        ("issuer_switch", "D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO"),
        ("issuer_epoch", "D534_G6_ISSUER_HANDOFF_UNVERIFIED_NO_GO"),
        ("stop_lost", "D534_G6_STOP_OR_REVOCATION_LOST_NO_GO"),
        ("revocation_lost", "D534_G6_STOP_OR_REVOCATION_LOST_NO_GO"),
        ("lower_sequence", "D534_G6_REVOCATION_BEHIND_NO_GO"),
        ("higher_generation", "D534_G6_REVOCATION_AHEAD_NO_GO"),
    ),
}
for _role, _rows in _ANOMALY_EXPECTATIONS.items():
    for _fault, _expected in _rows:
        setattr(D534LineageTests, "test_role_" + _role + "_" + _fault,
                _build_role_test(_role, _fault, _expected))


if __name__ == "__main__":
    main()
