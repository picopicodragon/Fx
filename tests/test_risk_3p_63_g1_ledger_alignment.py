"""P05/G1 zero-provenance cross-doc alignment must preserve all 15 identities."""
from __future__ import annotations

import copy
import unittest

from scripts import audit_risk_3p_63_g1_ledger_alignment as mod


class ExactG1AlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: mod._read(mod.ROOT, name) for name in mod.FILES}

    def reject(self, path, mutate, expected):
        docs = copy.deepcopy(self.docs)
        mutate(docs[path])
        result = mod.snapshot(injected=docs)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(expected, result["errors"], result)
        self.assertEqual(result["real_g1_verified"], 0)
        self.assertEqual(result["p05_real_accepted"], 0)
        self.assertFalse(result["real_broker_sources_confirmed"])
        self.assertFalse(result["real_mt4_access_authorized"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertTrue(result["safety_hold_latched"])

    def test_all_fifteen_sources_and_handoff_rows_align_blank(self):
        self.assertEqual(mod.audit(), [])
        s = mod.snapshot()
        self.assertEqual(s["status"], "PASS_BLANK_G1_LEDGER_ALIGNMENT_ONLY")
        self.assertEqual(s["required_real_g1_rows"], 15)
        self.assertFalse(s["human_p05_signoff"])

    def test_each_g1_source_pair_or_field_swap_refused(self):
        for i in range(15):
            with self.subTest(row=i):
                self.reject(mod.G1,
                            lambda x, n=i: x["g1_entries"][n].update(
                                field="WRONG_FIELD"),
                            "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:" + str(i + 1))

    def test_each_handoff_pair_or_field_swap_refused(self):
        for i in range(15):
            with self.subTest(row=i):
                self.reject(mod.HANDOFF,
                            lambda x, n=i: x["g1_rows"][n].update(pair="GBP/USD"),
                            "P63_HANDOFF_ITEM_FAKE_OR_MISORDERED:" + str(i + 1))

    def test_g1_real_values_and_primary_evidence_refs_remain_null(self):
        self.reject(mod.G1,
                    lambda x: x["g1_entries"][3].update(value="0.01"),
                    "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:4")
        self.reject(mod.G1,
                    lambda x: x["g1_entries"][0].update(
                        primary_source_ref="FAKE_SERVER_EVIDENCE"),
                    "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:1")
        self.reject(mod.HANDOFF,
                    lambda x: x["g1_rows"][14].update(real_broker_value="0.01"),
                    "P63_HANDOFF_ITEM_FAKE_OR_MISORDERED:15")

    def test_source_total_and_field_schema_remain_exact(self):
        self.reject(mod.G1,
                    lambda x: x.update(required_items=20),
                    "P63_SOURCE_G1_SCOPE_DRIFT")
        self.reject(mod.G1,
                    lambda x: x["g1_entries"][0].update(
                        private_mt4_login="CANARY_63"),
                    "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:1")

    def test_handoff_real_broker_authorization_stays_false(self):
        self.reject(mod.HANDOFF,
                    lambda x: x["permission"].update(
                        real_mt4_session_read_authorized=True),
                    "P63_HANDOFF_REAL_EVIDENCE_FORGED")

    def test_owner_p05_signoff_cannot_be_inferred_from_g1_or_storage(self):
        self.reject(mod.DEBT,
                    lambda x: x["safety"].update(p05_passed=8),
                    "P63_CROSS_DOCUMENT_APPROVAL_DRIFT")
        self.reject(mod.P05_DAG,
                    lambda x: x["state"].update(g1_real_verified=15),
                    "P63_CROSS_DOCUMENT_APPROVAL_DRIFT")

    def test_missing_reordered_or_duplicate_rows_are_rejected(self):
        self.reject(mod.G1,
                    lambda x: x["g1_entries"].reverse(),
                    "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:1")
        self.reject(mod.HANDOFF,
                    lambda x: x["g1_rows"].pop(),
                    "P63_EXPECTED_BOTH_FIFTEEN_ROWS")

    def test_malformed_or_secret_data_never_echoed(self):
        d = copy.deepcopy(self.docs)
        d[mod.G1] = {"secret": "CANARY_63"}
        result = mod.snapshot(injected=d)
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertNotIn("CANARY_63", str(result))
        d = copy.deepcopy(self.docs)
        d.pop(mod.G1)
        self.assertIn("P63_OFFLINE_SOURCE_READ_FAILURE",
                      mod.audit(injected=d))


if __name__ == "__main__":
    unittest.main()
