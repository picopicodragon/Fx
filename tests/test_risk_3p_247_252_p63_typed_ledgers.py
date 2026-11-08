"""RISK-3P-247..252: G1 3x5 blank cross-ledger typed input regressions.

These are artificial offline inputs; no terminal, broker, orders or secrets.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from scripts import audit_risk_3p_63_g1_ledger_alignment as p63

CANARY = "SIMULATED_P63_PRIVATE_CANARY"


class EvilKey:
    def __hash__(self):
        return 630001

    def __eq__(self, other):
        raise AssertionError(CANARY)


class EvilText(str):
    def __eq__(self, other):
        raise AssertionError(CANARY)


class EvilList(list):
    def __eq__(self, other):
        raise AssertionError(CANARY)


class EvilValue:
    def __eq__(self, other):
        raise AssertionError(CANARY)


class G1TypedCrossLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {name: p63._read(p63.ROOT, name) for name in p63.FILES}

    def denied(self, change, expected):
        docs = copy.deepcopy(self.docs)
        change(docs)
        result = p63.snapshot(injected=docs)
        self.assertEqual(result["status"], "FAIL_CLOSED", result)
        self.assertIn(expected, result["errors"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")
        self.assertIs(result["safety_hold_latched"], True)
        self.assertIs(result["real_mt4_access_authorized"], False)
        self.assertIs(result["real_order_or_ea_action_authorized"], False)
        self.assertEqual(result["real_g1_verified"], 0)
        self.assertEqual(result["p05_real_accepted"], 0)
        self.assertNotIn(CANARY, str(result))

    def test_247_current_public_spec_is_blank_offline_only(self):
        self.assertEqual(p63.audit(), [])
        result = p63.snapshot()
        self.assertEqual(result["status"], "PASS_BLANK_G1_LEDGER_ALIGNMENT_ONLY")
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_247_untrusted_root_key_never_compared(self):
        self.denied(lambda d: d.update({EvilKey(): CANARY}),
                    "P63_MISSING_OR_MALFORMED_PUBLIC_SPEC")

    def test_248_source_row_hostile_key_not_compared(self):
        self.denied(lambda d: d[p63.G1]["g1_entries"][0].update(
            {EvilKey(): CANARY}), "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:1")

    def test_248_handoff_row_hostile_key_not_compared(self):
        self.denied(lambda d: d[p63.HANDOFF]["g1_rows"][0].update(
            {EvilKey(): CANARY}), "P63_HANDOFF_ITEM_FAKE_OR_MISORDERED:1")

    def test_248_nested_permission_hostile_key_not_compared(self):
        self.denied(lambda d: d[p63.HANDOFF]["permission"].update(
            {EvilKey(): CANARY}), "P63_HANDOFF_REAL_EVIDENCE_FORGED")

    def test_249_source_scope_custom_comparison_not_invoked(self):
        self.denied(lambda d: d[p63.G1].update(target_pairs=EvilList(
            ["USD/JPY", "EUR/JPY", "EUR/USD"])), "P63_SOURCE_G1_SCOPE_DRIFT")

    def test_249_handoff_pair_custom_comparison_not_invoked(self):
        self.denied(lambda d: d[p63.HANDOFF]["g1_rows"][0].update(
            pair=EvilValue()), "P63_HANDOFF_ITEM_FAKE_OR_MISORDERED:1")

    def test_249_source_field_str_subclass_denied(self):
        self.denied(lambda d: d[p63.G1]["g1_entries"][0].update(
            field=EvilText("min_lot")), "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:1")

    def test_250_int_zero_not_boolean_false_for_real_evidence(self):
        self.denied(lambda d: d[p63.HANDOFF]["permission"].update(
            g1_fifteen_fields_verified=False),
                    "P63_HANDOFF_REAL_EVIDENCE_FORGED")

    def test_250_bool_true_not_int_one_for_total(self):
        self.denied(lambda d: d[p63.G1].update(required_items=True),
                    "P63_SOURCE_G1_SCOPE_DRIFT")

    def test_250_nested_g1_counter_false_rejected(self):
        self.denied(lambda d: d[p63.P05_DAG]["state"].update(
            g1_real_verified=False), "P63_CROSS_DOCUMENT_APPROVAL_DRIFT")

    def test_251_malformed_handoff_permission_denied(self):
        self.denied(lambda d: d[p63.HANDOFF].update(permission=[]),
                    "P63_HANDOFF_REAL_EVIDENCE_FORGED")

    def test_251_malformed_source_safety_denied(self):
        self.denied(lambda d: d[p63.G1].update(safety={EvilKey(): CANARY}),
                    "P63_SOURCE_G1_SCOPE_DRIFT")

    def test_252_unexpected_public_read_exception_is_fixed_code(self):
        with patch.object(p63, "_read", side_effect=RuntimeError(CANARY)):
            result = p63.snapshot()
        self.assertEqual(result["status"], "FAIL_CLOSED")
        self.assertIn("P63_OFFLINE_SOURCE_READ_FAILURE", result["errors"])
        self.assertNotIn(CANARY, str(result))

    def test_252_failure_does_not_mutate_originals(self):
        before = copy.deepcopy(self.docs)
        self.denied(lambda d: d[p63.G1]["g1_entries"][0].update(value=CANARY),
                    "P63_SOURCE_ITEM_FAKE_OR_MISORDERED:1")
        self.assertEqual(self.docs, before)


if __name__ == "__main__":
    unittest.main()
