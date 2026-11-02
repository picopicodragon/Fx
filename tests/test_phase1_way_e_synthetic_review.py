"""Q197-Q199 mock handoff and privacy denial tests, with no broker I/O."""
import copy
import unittest

from scripts.phase1_way_e_synthetic_review import review_mock_handoff


def fixture(phase="DISPATCHING", response="OUTCOME_UNKNOWN", match=None):
    return {
        "phase": phase,
        "response": response,
        "broker_match": match,
        "public_metadata": {
            "gate_id": "G4", "scenario_id": "P1-05-F03", "label": response,
        },
    }


class SyntheticHandoffTests(unittest.TestCase):
    def assert_no_authority(self, result):
        self.assertIs(result["dispatch_allowed"], False)
        self.assertIs(result["automatic_retry_allowed"], False)
        self.assertIs(result["stop_release_allowed"], False)
        self.assertIs(result["safety_hold_latched"], True)
        self.assertEqual(result["phase_1"], "BLOCKED")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIsNone(result["verified_values"])

    def test_unknown_or_missing_response_never_retries(self):
        for response in ("NO_RESPONSE", "OUTCOME_UNKNOWN"):
            with self.subTest(response=response):
                result = review_mock_handoff(fixture(response=response))
                self.assertEqual(result["reason"], "OUTCOME_UNKNOWN_NO_BLIND_RETRY")
                self.assertIs(result["independent_reconciliation_required"], True)
                self.assert_no_authority(result)

    def test_accepted_response_and_synthetic_match_are_not_execution_proof(self):
        for match in (None, False, True):
            with self.subTest(match=match):
                result = review_mock_handoff(fixture(response="RESPONSE_ACCEPTED",
                                                     match=match))
                self.assertEqual(result["reason"],
                                 "SYNTHETIC_RESPONSE_NOT_EXECUTION_PROOF")
                self.assert_no_authority(result)

    def test_prepared_state_cannot_claim_response(self):
        clean = fixture(phase="PREPARED", response="NO_RESPONSE")
        self.assertEqual(review_mock_handoff(clean)["reason"],
                         "PREPARED_NOT_DISPATCH_PROOF")
        contradiction = fixture(phase="PREPARED", response="RESPONSE_ACCEPTED")
        self.assertEqual(review_mock_handoff(contradiction)["reason"],
                         "PRE_DISPATCH_CONTRADICTION")
        self.assert_no_authority(review_mock_handoff(contradiction))

    def test_public_account_or_secret_fields_are_rejected(self):
        for name in ("account_id", "api_key", "password", "raw_log", "private_payload"):
            with self.subTest(field=name):
                record = fixture()
                record["public_metadata"][name] = "synthetic-canary"
                result = review_mock_handoff(record)
                self.assertEqual(result["reason"], "PUBLIC_METADATA_REJECTED")
                self.assertNotIn("synthetic-canary", str(result))
                self.assert_no_authority(result)

    def test_public_label_cannot_disagree_with_response(self):
        record = fixture(response="OUTCOME_UNKNOWN")
        record["public_metadata"]["label"] = "RESPONSE_ACCEPTED"
        self.assertEqual(review_mock_handoff(record)["reason"],
                         "PUBLIC_METADATA_REJECTED")

    def test_unapproved_or_malformed_states_fail_closed(self):
        base = fixture()
        for field, value in (("phase", "SENT"), ("response", "FILLED"),
                             ("broker_match", 1), ("public_metadata", None)):
            with self.subTest(field=field):
                record = copy.deepcopy(base)
                record[field] = value
                self.assert_no_authority(review_mock_handoff(record))
        record = copy.deepcopy(base)
        record["order_authorized"] = True
        self.assertEqual(review_mock_handoff(record)["reason"], "INVALID_RECORD")


if __name__ == "__main__":
    unittest.main()
