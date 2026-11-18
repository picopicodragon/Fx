"""Historical manual-stop attestation never grants trading or release privileges."""
from __future__ import annotations

import json
import unittest
from pathlib import Path


class PaperOperatorAttestationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        doc=(Path(__file__).resolve().parents[1] / "specs" /
            "final_paper_interruption_operator_attestation_20261118.json")
        cls.record=json.loads(doc.read_text(encoding="utf-8"))

    def test_specific_gap_classified_by_operator_statement(self):
        r=self.record
        self.assertEqual(r["classification"],
                         "OPERATOR_ATTESTED_INTENTIONAL_STOP")
        self.assertEqual(r["classification_basis"],
                         "EXPLICIT_OPERATOR_DECLARATION_IN_CONVERSATION")
        self.assertTrue(r["operator_declared_stop_was_manual_and_regular"])
        self.assertTrue(r["previous_unknown_root_cause_record_superseded_for_this_event"])
        gap=r["observation_gap"]
        self.assertEqual((gap["previous_journal_cycle"],
                          gap["next_journal_cycle"]), (106,107))
        self.assertEqual(gap["unobserved_seconds_pc_derived"],3420)
        self.assertEqual(gap["next_quote_epoch_pc_unattested"]-
                         gap["previous_quote_epoch_pc_unattested"],3420)
        self.assertFalse(gap["time_independently_attested"])

    def test_causality_not_inferred_from_wer1001(self):
        r=self.record
        self.assertEqual(r["windows_application_1001"]["count"],2)
        self.assertEqual(r["windows_application_1001"][
            "causally_related_to_python_process_exit"],"NOT_ESTABLISHED")
        self.assertFalse(r["windows_application_1001"][
            "force_python_crash_classification"])
        self.assertFalse(r["applicable_to_other_future_stops"])

    def test_manual_stop_does_not_unlatch_or_incur_costs(self):
        r=self.record
        self.assertFalse(r["existing_journal_may_be_modified"])
        self.assertFalse(r[
            "existing_communication_latch_may_be_cleared_from_attestation_alone"])
        self.assertFalse(r["reentry_authorized"])
        self.assertFalse(r["paid_ai_inference_renewal_authorized"])
        self.assertEqual(r["existing_paid_ai_call_limit"],6)
        self.assertFalse(r["broker_orders_permitted"])
        self.assertFalse(r["real_orders_permitted"])
        self.assertTrue(r["operational_no_go_maintained"])


if __name__=="__main__":
    unittest.main()
