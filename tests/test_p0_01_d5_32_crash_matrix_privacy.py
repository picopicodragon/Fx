"""D5-32: synthetic G6 crash matrix and canonical G2 public JSON tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from scripts.p0_01_d5_31_protocol_privacy_gate import _STAGES, _THREATS
from scripts.p0_01_d5_32_crash_matrix_privacy import (
    _OUTPUT_FALSE, review_d532_crash_matrix,
)

_ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def read(name):
    with (_ROOT / "specs" / name).open(encoding="utf-8") as f:
        return json.load(f)


def contract():
    return read("p0_01_d5_32_crash_matrix_contract.json")


def d531():
    return read("p0_01_d5_31_protocol_privacy_contract.json")


def ledger():
    return read("p0_01_d5_17_evidence_reconciliation_status.json")


def gaps():
    return read("p0_01_d5_25_gap_verification_matrix.json")


def fixture():
    return read("p0_01_d5_32_synthetic_fixture.json")


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False)


class D532CrashMatrixPrivacyTests(TestCase):
    def check(self, expected, c=_UNSET, prev=_UNSET, old=_UNSET, gap=_UNSET,
              public=_UNSET, matrix=_UNSET):
        f = fixture()
        r = review_d532_crash_matrix(
            contract() if c is _UNSET else c,
            d531() if prev is _UNSET else prev,
            ledger() if old is _UNSET else old,
            gaps() if gap is _UNSET else gap,
            f["public_json"] if public is _UNSET else public,
            f["matrix"] if matrix is _UNSET else matrix,
        )
        self.assertEqual(r["status"], expected)
        self.assertEqual(r["phase_1"], "BLOCKED")
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(r["verified_values"])
        self.assertIs(r["safety_hold_latched"], True)
        self.assertEqual(r["effective_approved_actions"], [])
        self.assertEqual(r["account_identity_consistency"], "NOT_RECONCILED")
        for field in ("current_positions", "current_pending_orders",
                      "current_ea_state"):
            self.assertEqual(r[field], "UNKNOWN")
        for field in _OUTPUT_FALSE:
            self.assertIs(r[field], False, field)
        allowed = set(_OUTPUT_FALSE) | {
            "status", "synthetic_cutpoint_statuses", "effective_approved_actions",
            "safety_hold_latched", "account_identity_consistency",
            "current_positions", "current_pending_orders",
            "current_ea_state", "phase_1", "runtime_go_no_go",
            "verified_values",
        }
        self.assertEqual(set(r), allowed)
        return r

    def test_all_eight_synthetic_cutpoints_covered_never_authorized(self):
        r = self.check("D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED")
        self.assertEqual(len(r["synthetic_cutpoint_statuses"]), 8)
        self.assertEqual(r["synthetic_cutpoint_statuses"][:7],
                         ["D531_G6_PARTIAL_COMMIT_STOP_HELD_NO_GO"] * 7)
        self.assertEqual(r["synthetic_cutpoint_statuses"][-1],
                         "D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED")

    def test_matrix_exact_eight_rows_and_order(self):
        m = fixture()["matrix"]
        self.assertEqual(len(m), 8)
        self.assertEqual([r["id"] for r in m],
                         [f"D532-CUT-{i:02d}" for i in range(8)])
        for i, row in enumerate(m):
            self.assertEqual(row["recovery"]["completed_stages"],
                             list(_STAGES[:i]))

    def test_public_json_has_only_fixed_literals(self):
        self.assertEqual(fixture()["public_json"], canonical({
            "origin": "SYNTHETIC_ONLY",
            "schema_version": 1, "check_id": "D530-G2-01",
            "design_state": "NOT_PERFORMED", "simulation_only": True,
        }))

    def test_each_eight_check_ids_accepted_as_synthetic_only(self):
        for i in range(1, 9):
            with self.subTest(i=i):
                p = json.loads(fixture()["public_json"])
                p["check_id"] = f"D530-G2-{i:02d}"
                self.check(
                    "D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED",
                    public=canonical(p),
                )

    def test_complete_synthetic_claim_never_verifies_independent_anchor(self):
        r = self.check("D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED")
        self.assertIs(r["g6_independent_anchor_real"], False)
        self.assertIs(r["g6_actual_atomic_commit_verified"], False)

    def test_canonical_public_json_rejects_whitespace(self):
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=fixture()["public_json"] + " ")

    def test_canonical_public_json_rejects_newline(self):
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=fixture()["public_json"] + "\n")

    def test_canonical_public_json_rejects_reordered_fields(self):
        p = json.loads(fixture()["public_json"])
        noncanonical = json.dumps(dict(reversed(list(p.items()))),
                                  sort_keys=False, separators=(",", ":"))
        self.assertNotEqual(noncanonical, fixture()["public_json"])
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=noncanonical)

    def test_duplicate_key_in_json_text_rejected(self):
        p = fixture()["public_json"]
        attack = p.replace('"check_id":"D530-G2-01"',
                           '"check_id":"D530-G2-01","check_id":"D530-G2-01"')
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED", public=attack)

    def test_json_unicode_escape_obfuscation_rejected(self):
        p = fixture()["public_json"]
        attack = p.replace("SYNTHETIC_ONLY", "SYNTHETIC_\\u004fNLY")
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED", public=attack)

    def test_json_confusable_key_rejected(self):
        p = fixture()["public_json"]
        attack = p.replace("check_id", "check_іd")
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED", public=attack)

    def test_json_zero_width_injected_rejected(self):
        p = fixture()["public_json"]
        attack = p.replace("NOT_PERFORMED", "NOT_\u200bPERFORMED")
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED", public=attack)

    def test_extra_nested_secret_data_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["meta"] = {"account": ["SYNTHETIC_SECRET"]}
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_extra_free_text_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["notes"] = "SYNTHETIC_SECRET"
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_extra_account_number_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["account_number"] = "SYNTHETIC_SECRET"
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_extra_mt4_log_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["raw_mt4_log"] = "SYNTHETIC_LOG"
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_extra_api_key_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["api_key"] = "SYNTHETIC_SECRET"
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_extra_real_timestamp_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_nested_array_json_root_rejected(self):
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical([json.loads(fixture()["public_json"])]))

    def test_extra_json_object_rejected(self):
        p = fixture()["public_json"]
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=p + p)

    def test_json_utf8_bom_rejected(self):
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public="\ufeff" + fixture()["public_json"])

    def test_json_truncated_rejected(self):
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=fixture()["public_json"][:-1])

    def test_json_max_bytes_rejects_long_string(self):
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=" " * 385)

    def test_non_string_json_or_bytes_rejected(self):
        for value in (None, True, [], {}, b"{}"):
            with self.subTest(value=repr(value)):
                self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                           public=value)

    def test_json_nan_and_infinity_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                p = fixture()["public_json"].replace(
                    '"schema_version":1', f'"schema_version":{value}')
                self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED", public=p)

    def test_extra_permission_field_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["stop_release_authorized"] = True
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_public_status_cannot_be_marked_complete(self):
        p = json.loads(fixture()["public_json"])
        p["design_state"] = "COMPLETE"
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_public_schema_boolean_not_integer_rejected(self):
        p = json.loads(fixture()["public_json"])
        p["schema_version"] = True
        self.check("D532_G2_PUBLIC_JSON_REJECTED_FAIL_CLOSED",
                   public=canonical(p))

    def test_matrix_missing_cutpoint_rejected(self):
        m = fixture()["matrix"]
        m.pop()
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_extra_cutpoint_rejected(self):
        m = fixture()["matrix"]
        m.append(copy.deepcopy(m[-1]))
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_swapped_cutpoints_rejected(self):
        m = fixture()["matrix"]
        m[1], m[2] = m[2], m[1]
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_duplicate_cutpoint_id_rejected(self):
        m = fixture()["matrix"]
        m[1]["id"] = m[0]["id"]
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_extra_real_account_field_rejected(self):
        m = fixture()["matrix"]
        m[0]["account_number"] = "SYNTHETIC_ONLY"
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_wrong_number_of_stages_rejected(self):
        m = fixture()["matrix"]
        m[3]["recovery"]["completed_stages"] = list(_STAGES[:2])
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_source_record_mismatch_rejected(self):
        m = fixture()["matrix"]
        m[3]["recovery"]["before"]["record_id"] = "SYNTHETIC_RECORD_WRONG"
        self.check("D532_CRASH_MATRIX_SCOPE_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_source_generation_mismatch_rejected(self):
        m = fixture()["matrix"]
        m[5]["recovery"]["before"]["generation"] = 2
        self.check("D532_CRASH_MATRIX_SCOPE_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_recovery_extra_permission_rejected(self):
        m = fixture()["matrix"]
        m[1]["recovery"]["host_io_approved"] = True
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_recovery_real_flag_rejected(self):
        m = fixture()["matrix"]
        m[7]["recovery"]["simulated_only"] = False
        self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED", matrix=m)

    def test_matrix_invalid_outer_type_rejected(self):
        for value in (None, {}, [], "LIVE"):
            with self.subTest(value=repr(value)):
                self.check("D532_CRASH_MATRIX_REJECTED_FAIL_CLOSED",
                           matrix=value)

    def test_child_stop_release_claim_denied(self):
        m = fixture()["matrix"]
        m[6]["recovery"]["simulated_stop_release_claim"] = True
        r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
        self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                         "D531_UNAUTHORIZED_STOP_RELEASE_NO_GO")

    def test_child_stop_latch_lost_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["after"]["stop_latched"] = False
        r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
        self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                         "D531_G6_STOP_LATCH_LOST_NO_GO")

    def test_child_reference_rollback_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["after"]["sequence"] = 2
        r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
        self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                         "D531_G6_ROLLBACK_NO_GO")

    def test_child_tombstone_erasure_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["after"]["revocation_tombstone"] = False
        r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
        self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                         "D531_G6_REVOCATION_ERASURE_NO_GO")

    def test_child_anchor_mismatch_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["anchor_claim"] = "SYNTHETIC_MISMATCH"
        r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
        self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                         "D531_G6_UNTRUSTED_FAULT_NO_GO")

    def test_child_storage_failed_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["storage_claim"] = "SYNTHETIC_FAILED"
        self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)

    def test_child_writer_conflict_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["writer_claim"] = "SYNTHETIC_CONFLICT"
        self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)

    def test_child_clock_anomaly_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["clock_claim"] = "SYNTHETIC_CLOCK_ANOMALY"
        self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)

    def test_child_revocation_index_missing_denied(self):
        m = fixture()["matrix"]
        m[4]["recovery"]["revocation_claim"] = "SYNTHETIC_TOMBSTONE_MISSING"
        self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)

    def test_jointly_forged_all_hashes_do_not_prove_authenticity(self):
        m = fixture()["matrix"]
        for row in m:
            row["recovery"]["before"]["head_hash"] = "b" * 64
            row["recovery"]["after"]["head_hash"] = "b" * 64
        r = self.check("D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED",
                       matrix=m)
        self.assertIs(r["g6_real_revocation_verified"], False)

    def test_plan_no_real_trust_anchor_claim_allowed(self):
        c = contract()
        c["g6_independent_trust_anchor_verified"] = True
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_no_real_crash_test_claim_allowed(self):
        c = contract()
        c["g6_actual_crash_test_performed"] = True
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_no_host_io_approval_allowed(self):
        c = contract()
        c["host_io_approved"] = True
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_max_size_cannot_be_expanded(self):
        c = contract()
        c["g2_public_max_bytes"] = 4096
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_cannot_disable_canonical_check(self):
        c = contract()
        c["g2_canonical_json_required"] = False
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_required_cutpoint_cannot_be_removed(self):
        c = contract()
        c["g6_crash_cutpoints"].pop()
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_expected_status_cannot_be_changed_to_go(self):
        c = contract()
        c["g6_expected_healthy_statuses"][0] = "GO"
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_runtime_go_rejected(self):
        c = contract()
        c["runtime_go_no_go"] = "GO"
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_real_verified_values_rejected(self):
        c = contract()
        c["verified_values"] = {}
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_extra_permission_key_rejected(self):
        c = contract()
        c["order_authorized"] = True
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_plan_bool_schema_rejected(self):
        c = contract()
        c["schema_version"] = True
        self.check("D532_CONTRACT_REJECTED_FAIL_CLOSED", c=c)

    def test_old_user_evidence_real_current_claim_rejected(self):
        old = ledger()
        old["positions_status"] = "ABSENT"
        self.check("D532_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_old_user_evidence_invented_timestamp_rejected(self):
        old = ledger()
        old["evidence"][0]["observed_at_utc"] = "2026-10-30T00:00:00Z"
        self.check("D532_SOURCE_BASELINE_REJECTED_FAIL_CLOSED", old=old)

    def test_g2_gap_cannot_be_resolved(self):
        g = gaps()
        next(x for x in g["gaps"] if x["id"] == "G2")[
            "real_world_verified"] = True
        self.check("D532_GAP_BASELINE_REJECTED_FAIL_CLOSED", gap=g)

    def test_g6_gap_cannot_release_blocker(self):
        g = gaps()
        next(x for x in g["gaps"] if x["id"] == "G6")[
            "release_blocker"] = False
        self.check("D532_GAP_BASELINE_REJECTED_FAIL_CLOSED", gap=g)

    def test_d531_child_design_forged_approval_rejected(self):
        p = d531()
        p["approvals"]["orders"] = True
        self.check("D532_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED", prev=p)

    def test_child_forged_go_denied(self):
        with patch(
            "scripts.p0_01_d5_32_crash_matrix_privacy.review_d531_protocol",
            return_value={"status": "D531_SYNTHETIC_PROTOCOL_COHERENT_NEVER_AUTHORIZED",
                          "runtime_go_no_go": "GO"},
        ):
            self.check("D532_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_child_forged_broker_verified_denied(self):
        from scripts.p0_01_d5_31_protocol_privacy_gate import (
            review_d531_protocol as original,
        )
        f = fixture()
        p = json.loads(f["public_json"])
        prior = original(d531(), ledger(), gaps(), p, f["matrix"][0]["recovery"])
        prior["broker_verified"] = True
        with patch(
            "scripts.p0_01_d5_32_crash_matrix_privacy.review_d531_protocol",
            return_value=prior,
        ):
            self.check("D532_CHILD_DENIAL_INVARIANT_REJECTED_FAIL_CLOSED")

    def test_input_pure_no_file_io(self):
        c, prev, old, gap = contract(), d531(), ledger(), gaps()
        f = fixture()
        with patch("builtins.open", side_effect=AssertionError("I/O prohibited")):
            r = review_d532_crash_matrix(
                c, prev, old, gap, f["public_json"], f["matrix"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_input_unmodified(self):
        c, prev, old, gap = contract(), d531(), ledger(), gaps()
        f = fixture()
        before = copy.deepcopy((c, prev, old, gap, f))
        review_d532_crash_matrix(
            c, prev, old, gap, f["public_json"], f["matrix"])
        self.assertEqual((c, prev, old, gap, f), before)

    def test_repeated_calls_do_not_create_permissions(self):
        self.check("D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED")
        m = fixture()["matrix"]
        m[-1]["recovery"]["simulated_stop_release_claim"] = True
        self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
        self.check("D532_SYNTHETIC_CUTPOINT_COVERAGE_NEVER_AUTHORIZED")

    def test_status_ledger_still_all_gates_blocked(self):
        s = read("p0_01_d5_32_status.json")
        self.assertEqual(s["unresolved_gates"],
                         [f"G{i}" for i in range(1, 10)])
        self.assertEqual(s["phase_1"], "BLOCKED")
        self.assertEqual(s["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(s["verified_values"])
        for field in ("g2_real_world_resolved", "g6_real_world_resolved",
                      "broker_verified", "host_io_approved",
                      "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(s[field], False)


# Independent regression methods: each synthetic crash cut × each threat.
def _test_cut_00_fault_01(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_01 = _test_cut_00_fault_01

def _test_cut_00_fault_02(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_02 = _test_cut_00_fault_02

def _test_cut_00_fault_03(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_03 = _test_cut_00_fault_03

def _test_cut_00_fault_04(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_04 = _test_cut_00_fault_04

def _test_cut_00_fault_05(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_05 = _test_cut_00_fault_05

def _test_cut_00_fault_06(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_06 = _test_cut_00_fault_06

def _test_cut_00_fault_07(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_07 = _test_cut_00_fault_07

def _test_cut_00_fault_08(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_08 = _test_cut_00_fault_08

def _test_cut_00_fault_09(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_09 = _test_cut_00_fault_09

def _test_cut_00_fault_10(self):
    m = fixture()["matrix"]
    m[0]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][0],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_00_fault_10 = _test_cut_00_fault_10

def _test_cut_01_fault_01(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_01 = _test_cut_01_fault_01

def _test_cut_01_fault_02(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_02 = _test_cut_01_fault_02

def _test_cut_01_fault_03(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_03 = _test_cut_01_fault_03

def _test_cut_01_fault_04(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_04 = _test_cut_01_fault_04

def _test_cut_01_fault_05(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_05 = _test_cut_01_fault_05

def _test_cut_01_fault_06(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_06 = _test_cut_01_fault_06

def _test_cut_01_fault_07(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_07 = _test_cut_01_fault_07

def _test_cut_01_fault_08(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_08 = _test_cut_01_fault_08

def _test_cut_01_fault_09(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_09 = _test_cut_01_fault_09

def _test_cut_01_fault_10(self):
    m = fixture()["matrix"]
    m[1]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][1],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_01_fault_10 = _test_cut_01_fault_10

def _test_cut_02_fault_01(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_01 = _test_cut_02_fault_01

def _test_cut_02_fault_02(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_02 = _test_cut_02_fault_02

def _test_cut_02_fault_03(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_03 = _test_cut_02_fault_03

def _test_cut_02_fault_04(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_04 = _test_cut_02_fault_04

def _test_cut_02_fault_05(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_05 = _test_cut_02_fault_05

def _test_cut_02_fault_06(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_06 = _test_cut_02_fault_06

def _test_cut_02_fault_07(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_07 = _test_cut_02_fault_07

def _test_cut_02_fault_08(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_08 = _test_cut_02_fault_08

def _test_cut_02_fault_09(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_09 = _test_cut_02_fault_09

def _test_cut_02_fault_10(self):
    m = fixture()["matrix"]
    m[2]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][2],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_02_fault_10 = _test_cut_02_fault_10

def _test_cut_03_fault_01(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_01 = _test_cut_03_fault_01

def _test_cut_03_fault_02(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_02 = _test_cut_03_fault_02

def _test_cut_03_fault_03(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_03 = _test_cut_03_fault_03

def _test_cut_03_fault_04(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_04 = _test_cut_03_fault_04

def _test_cut_03_fault_05(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_05 = _test_cut_03_fault_05

def _test_cut_03_fault_06(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_06 = _test_cut_03_fault_06

def _test_cut_03_fault_07(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_07 = _test_cut_03_fault_07

def _test_cut_03_fault_08(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_08 = _test_cut_03_fault_08

def _test_cut_03_fault_09(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_09 = _test_cut_03_fault_09

def _test_cut_03_fault_10(self):
    m = fixture()["matrix"]
    m[3]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][3],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_03_fault_10 = _test_cut_03_fault_10

def _test_cut_04_fault_01(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_01 = _test_cut_04_fault_01

def _test_cut_04_fault_02(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_02 = _test_cut_04_fault_02

def _test_cut_04_fault_03(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_03 = _test_cut_04_fault_03

def _test_cut_04_fault_04(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_04 = _test_cut_04_fault_04

def _test_cut_04_fault_05(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_05 = _test_cut_04_fault_05

def _test_cut_04_fault_06(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_06 = _test_cut_04_fault_06

def _test_cut_04_fault_07(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_07 = _test_cut_04_fault_07

def _test_cut_04_fault_08(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_08 = _test_cut_04_fault_08

def _test_cut_04_fault_09(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_09 = _test_cut_04_fault_09

def _test_cut_04_fault_10(self):
    m = fixture()["matrix"]
    m[4]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][4],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_04_fault_10 = _test_cut_04_fault_10

def _test_cut_05_fault_01(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_01 = _test_cut_05_fault_01

def _test_cut_05_fault_02(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_02 = _test_cut_05_fault_02

def _test_cut_05_fault_03(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_03 = _test_cut_05_fault_03

def _test_cut_05_fault_04(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_04 = _test_cut_05_fault_04

def _test_cut_05_fault_05(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_05 = _test_cut_05_fault_05

def _test_cut_05_fault_06(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_06 = _test_cut_05_fault_06

def _test_cut_05_fault_07(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_07 = _test_cut_05_fault_07

def _test_cut_05_fault_08(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_08 = _test_cut_05_fault_08

def _test_cut_05_fault_09(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_09 = _test_cut_05_fault_09

def _test_cut_05_fault_10(self):
    m = fixture()["matrix"]
    m[5]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][5],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_05_fault_10 = _test_cut_05_fault_10

def _test_cut_06_fault_01(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_01 = _test_cut_06_fault_01

def _test_cut_06_fault_02(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_02 = _test_cut_06_fault_02

def _test_cut_06_fault_03(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_03 = _test_cut_06_fault_03

def _test_cut_06_fault_04(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_04 = _test_cut_06_fault_04

def _test_cut_06_fault_05(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_05 = _test_cut_06_fault_05

def _test_cut_06_fault_06(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_06 = _test_cut_06_fault_06

def _test_cut_06_fault_07(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_07 = _test_cut_06_fault_07

def _test_cut_06_fault_08(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_08 = _test_cut_06_fault_08

def _test_cut_06_fault_09(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_09 = _test_cut_06_fault_09

def _test_cut_06_fault_10(self):
    m = fixture()["matrix"]
    m[6]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][6],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_06_fault_10 = _test_cut_06_fault_10

def _test_cut_07_fault_01(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[0]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_01 = _test_cut_07_fault_01

def _test_cut_07_fault_02(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[1]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_02 = _test_cut_07_fault_02

def _test_cut_07_fault_03(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[2]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_03 = _test_cut_07_fault_03

def _test_cut_07_fault_04(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[3]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_04 = _test_cut_07_fault_04

def _test_cut_07_fault_05(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[4]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_05 = _test_cut_07_fault_05

def _test_cut_07_fault_06(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[5]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_06 = _test_cut_07_fault_06

def _test_cut_07_fault_07(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[6]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_07 = _test_cut_07_fault_07

def _test_cut_07_fault_08(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[7]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_08 = _test_cut_07_fault_08

def _test_cut_07_fault_09(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[8]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_09 = _test_cut_07_fault_09

def _test_cut_07_fault_10(self):
    m = fixture()["matrix"]
    m[7]["recovery"]["fault"] = _THREATS[9]
    r = self.check("D532_CRASH_MATRIX_INCONSISTENT_NO_GO", matrix=m)
    self.assertEqual(r["synthetic_cutpoint_statuses"][7],
                     "D531_G6_UNTRUSTED_FAULT_NO_GO")

D532CrashMatrixPrivacyTests.test_cut_07_fault_10 = _test_cut_07_fault_10


if __name__ == "__main__":
    main()
