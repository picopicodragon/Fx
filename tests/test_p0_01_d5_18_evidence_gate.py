"""D5-18: offline source ranking, contradiction and missingness regression."""
import copy
import json
from pathlib import Path
import unittest

from scripts.p0_01_d5_18_evidence_gate import (
    evaluate_d517_evidence_ledger as ledger_check,
    evaluate_synthetic_evidence_records as records_check,
)


def fixture():
    return {
        "origin": "SYNTHETIC_ONLY",
        "schema_version": 1,
        "account_scope": "SYNTHETIC_ACCOUNT_A",
        "records": [
            {"evidence_id": "EVID_A", "source_kind": "USER_REPORT",
             "account_scope": "SYNTHETIC_ACCOUNT_A",
             "observed_at_utc": "2026-07-01T00:00:00Z",
             "positions": "ABSENT", "pending_orders": "ABSENT",
             "ea_running": "ABSENT"},
            {"evidence_id": "EVID_B", "source_kind": "VISUAL_OBSERVATION",
             "account_scope": "SYNTHETIC_ACCOUNT_A",
             "observed_at_utc": "2026-07-01T00:00:00Z",
             "positions": "ABSENT", "pending_orders": "ABSENT",
             "ea_running": "ABSENT"},
        ],
    }


def ledger():
    with (Path(__file__).resolve().parents[1] /
          "specs/p0_01_d5_17_evidence_reconciliation_status.json").open(
              encoding="utf-8") as f:
        return json.load(f)


class D518EvidenceGateTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])
        self.assertEqual(result["account_identity_consistency"], "NOT_RECONCILED")
        for k in ("broker_verified", "production_usable", "orders_generated",
                  "read_only_ex4_execution_approved",
                  "terminal_execution_approved", "forward_trading_enabled"):
            self.assertIs(result[k], False)
        for k in ("positions_status", "pending_orders_status",
                  "ea_running_status"):
            self.assertEqual(result[k], "UNKNOWN")

    def test_actual_d517_unverified_ledger(self):
        r = ledger_check(ledger())
        self.assertEqual(r["status"], "D517_REPORTS_NOT_RECONCILED_NO_GO")
        self.assertEqual(r["records_reviewed"], 2)
        self.denied(r)

    def test_d517_no_mutation(self):
        v = ledger()
        old = copy.deepcopy(v)
        ledger_check(v)
        self.assertEqual(v, old)

    def test_d517_missing_or_bad_schema(self):
        for item in (None, [], {}, "data", {"schema_version": True}):
            with self.subTest(item=repr(item)):
                r = ledger_check(item)
                self.assertEqual(r["status"], "LEDGER_REJECTED_FAIL_CLOSED")
                self.denied(r)

    def test_d517_bad_report_sources_rejected(self):
        for field, value in (("source_type", "SYNTHETIC_SYSTEM_MEASUREMENT"),
                             ("positions_or_pending_orders", "ABSENT"),
                             ("scope_label", "EXISTING_RAKUTEN_ACCOUNT_UNSPECIFIED")):
            with self.subTest(field=field):
                v = ledger()
                v["evidence"][0][field] = value
                self.assertEqual(ledger_check(v)["status"],
                                 "LEDGER_REJECTED_FAIL_CLOSED")

    def test_d517_claim_of_broker_verification_rejected(self):
        for edit in (
            lambda v: v.update(broker_verified=True),
            lambda v: v["evidence"][1].update(current_state_verified=True),
            lambda v: v["evidence"][0].update(broker_confirmed=True),
            lambda v: v.update(verified_values={}),
            lambda v: v.update(runtime_go_no_go="GO"),
            lambda v: v.update(phase_1="OPEN"),
        ):
            with self.subTest(edit=repr(edit)):
                v = ledger()
                edit(v)
                r = ledger_check(v)
                self.assertEqual(r["status"], "LEDGER_REJECTED_FAIL_CLOSED")
                self.denied(r)

    def test_d517_claim_of_approval_rejected(self):
        v = ledger()
        v["approvals"]["visual_inspection"] = True
        self.assertEqual(ledger_check(v)["status"], "LEDGER_REJECTED_FAIL_CLOSED")

    def test_d517_claim_of_completed_review_rejected(self):
        v = ledger()
        v["check_states"][0]["status"] = "VERIFIED"
        self.assertEqual(ledger_check(v)["status"], "LEDGER_REJECTED_FAIL_CLOSED")

    def test_d517_no_missing_evidence_or_duplicate_ids(self):
        v = ledger()
        v["evidence"] = v["evidence"][:1]
        self.assertEqual(ledger_check(v)["status"], "LEDGER_REJECTED_FAIL_CLOSED")
        v = ledger()
        v["evidence"][1]["id"] = "EV-OLD"
        self.assertEqual(ledger_check(v)["status"], "LEDGER_REJECTED_FAIL_CLOSED")

    def test_consistent_synthetic_never_grants_authority(self):
        r = records_check(fixture())
        self.assertEqual(r["status"], "SYNTHETIC_INTERNALLY_CONSISTENT_NO_GO")
        self.assertEqual(r["records_reviewed"], 2)
        self.denied(r)

    def test_user_report_alone_never_counts_as_verified(self):
        v = fixture()
        v["records"] = v["records"][:1]
        r = records_check(v)
        self.assertEqual(r["status"], "EVIDENCE_INSUFFICIENT_NO_GO")
        self.denied(r)

    def test_system_measurement_label_only_synthetic(self):
        v = fixture()
        v["records"][1]["source_kind"] = "SYNTHETIC_SYSTEM_MEASUREMENT"
        r = records_check(v)
        self.assertEqual(r["status"], "SYNTHETIC_INTERNALLY_CONSISTENT_NO_GO")
        self.denied(r)

    def test_conflicting_position_at_same_instant(self):
        v = fixture()
        v["records"][1]["positions"] = "PRESENT"
        r = records_check(v)
        self.assertEqual(r["status"], "EVIDENCE_CONFLICT_NO_GO")
        self.denied(r)

    def test_conflicting_pending_order_at_same_instant(self):
        v = fixture()
        v["records"][1]["pending_orders"] = "PRESENT"
        self.assertEqual(records_check(v)["status"], "EVIDENCE_CONFLICT_NO_GO")

    def test_conflicting_ea_at_same_instant(self):
        v = fixture()
        v["records"][1]["ea_running"] = "PRESENT"
        self.assertEqual(records_check(v)["status"], "EVIDENCE_CONFLICT_NO_GO")

    def test_changed_state_on_different_dates_not_a_conflict(self):
        v = fixture()
        v["records"][1]["positions"] = "PRESENT"
        v["records"][1]["observed_at_utc"] = "2026-07-02T00:00:00Z"
        r = records_check(v)
        self.assertEqual(r["status"], "EVIDENCE_INSUFFICIENT_NO_GO")
        self.denied(r)

    def test_unknown_fields_do_not_become_absent(self):
        v = fixture()
        v["records"][0]["pending_orders"] = "UNKNOWN"
        v["records"][1]["pending_orders"] = "UNKNOWN"
        r = records_check(v)
        self.assertEqual(r["status"], "EVIDENCE_INSUFFICIENT_NO_GO")
        self.denied(r)

    def test_missing_observation_time_insufficient(self):
        v = fixture()
        v["records"][0]["observed_at_utc"] = None
        r = records_check(v)
        self.assertEqual(r["status"], "EVIDENCE_INSUFFICIENT_NO_GO")
        self.denied(r)

    def test_mixed_account_scope_never_comparable(self):
        v = fixture()
        v["records"][1]["account_scope"] = "SYNTHETIC_ACCOUNT_B"
        r = records_check(v)
        self.assertEqual(r["status"], "ACCOUNT_SCOPE_MISMATCH_NO_GO")
        self.denied(r)

    def test_duplicate_ids_rejected(self):
        v = fixture()
        v["records"][1]["evidence_id"] = "EVID_A"
        self.assertEqual(records_check(v)["status"],
                         "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")

    def test_bad_schema_or_origin_rejected(self):
        for bad in (None, {}, [], "bad", {"origin": "SYNTHETIC_ONLY"}):
            with self.subTest(bad=repr(bad)):
                self.assertEqual(records_check(bad)["status"],
                                 "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")
        for k, value in (("origin", "LIVE"), ("schema_version", True),
                         ("account_scope", "123456"), ("schema_version", 2)):
            v = fixture()
            v[k] = value
            self.assertEqual(records_check(v)["status"],
                             "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")

    def test_nonstandard_timestamp_rejected(self):
        for stamp in ("2026-02-30T00:00:00Z", "2026-13-01T00:00:00Z",
                      "2026-07-01T00:00:00+00:00", "2026-07-01T00:00:00",
                      "2026-07-01T99:00:00Z", "", 3, True):
            with self.subTest(stamp=stamp):
                v = fixture()
                v["records"][1]["observed_at_utc"] = stamp
                self.assertEqual(records_check(v)["status"],
                                 "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")

    def test_invalid_status_and_source_rejected(self):
        for key, value in (("positions", 0), ("positions", False),
                           ("pending_orders", "NONE"),
                           ("ea_running", "TRUE"), ("source_kind", "BROKER_VERIFIED"),
                           ("evidence_id", "123456789")):
            with self.subTest(key=key):
                v = fixture()
                v["records"][1][key] = value
                self.assertEqual(records_check(v)["status"],
                                 "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")

    def test_extra_or_missing_fields_rejected(self):
        v = fixture()
        v["records"][0]["is_authorized"] = True
        self.assertEqual(records_check(v)["status"],
                         "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")
        v = fixture()
        del v["records"][0]["pending_orders"]
        self.assertEqual(records_check(v)["status"],
                         "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")
        v = fixture()
        v["approved"] = True
        self.assertEqual(records_check(v)["status"],
                         "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")

    def test_empty_or_overlong_record_list_rejected(self):
        v = fixture()
        v["records"] = []
        self.assertEqual(records_check(v)["status"],
                         "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")
        v = fixture()
        v["records"] = v["records"] * 11
        self.assertEqual(records_check(v)["status"],
                         "SYNTHETIC_INPUT_REJECTED_FAIL_CLOSED")

    def test_no_input_mutation(self):
        v = fixture()
        before = copy.deepcopy(v)
        records_check(v)
        self.assertEqual(v, before)


if __name__ == "__main__":
    unittest.main()
