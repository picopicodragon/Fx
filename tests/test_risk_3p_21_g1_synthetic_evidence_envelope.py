"""RISK-3P-21: hypothetical G1 evidence-envelope shape, never actual broker proof."""
from dataclasses import replace
import unittest

from scripts.review_g1_synthetic_evidence_envelope import (
    ExampleEnvelope, Review, UNITS, review_synthetic_metadata,
)


def example(pair="EUR/USD", field="tick_value_deposit_currency"):
    return ExampleEnvelope(
        pair=pair, field=field, terminal_symbol=pair.replace("/", ""),
        synthetic_account_alias="SYNTHETIC_ACCOUNT_ALPHA",
        primary_source_id="SYNTHETIC_SOURCE_TERMINAL",
        crosscheck_source_id="SYNTHETIC_SOURCE_RULEBOOK",
        primary_issuer="SYNTHETIC_ISSUER_TERMINAL",
        crosscheck_issuer="SYNTHETIC_ISSUER_RULEBOOK",
        observed_at_utc="2026-11-04T04:00:00Z",
        crosscheck_at_utc="2026-11-04T04:00:00Z",
        unit_claim=UNITS[field], synthetic_only=True,
        independent_unit_checked_claim=True,
        same_account_claim=True, contract_version_rechecked_claim=True,
        freshness_policy_defined_claim=False,
        confidential_payload_present=False,
    )


class G1SyntheticMetadataTests(unittest.TestCase):
    def remains_no_go(self, r):
        self.assertIs(type(r), Review)
        self.assertEqual(r.runtime_go_no_go, "NO_GO")
        self.assertEqual(r.phase_1, "BLOCKED")
        self.assertTrue(r.safety_hold_latched)
        for field in (
            "independent_issuer_proven", "observed_contract_value_proven",
            "account_identity_proven", "timestamp_freshness_proven",
            "broker_access_authorized", "g1_acceptance_approved",
            "owner_approval_recorded", "order_allowed",
            "stop_release_allowed", "automatic_retry_allowed",
            "production_authorized",
        ):
            self.assertIs(getattr(r, field), False)
        self.assertIsNone(r.verified_values)

    def denied(self, case, reason):
        r = review_synthetic_metadata(case)
        self.assertEqual(r.reason, reason)
        self.assertFalse(r.metadata_shape_consistent)
        self.remains_no_go(r)

    def test_all_fifteen_synthetic_shapes_are_never_g1_acceptance(self):
        for pair in ("USD/JPY", "EUR/JPY", "EUR/USD"):
            for field in UNITS:
                with self.subTest(pair=pair, field=field):
                    r = review_synthetic_metadata(example(pair, field))
                    self.assertTrue(r.metadata_shape_consistent)
                    self.assertEqual(
                        r.reason, "SYNTHETIC_METADATA_SHAPE_ONLY_NOT_G1_EVIDENCE")
                    self.remains_no_go(r)

    def test_reused_same_source_id_and_same_issuer_rejected(self):
        self.denied(replace(example(),
                            crosscheck_source_id="SYNTHETIC_SOURCE_TERMINAL"),
                    "SAME_SOURCE_OR_ISSUER_CANNOT_BE_INDEPENDENT")
        self.denied(replace(example(),
                            crosscheck_issuer="SYNTHETIC_ISSUER_TERMINAL"),
                    "SAME_SOURCE_OR_ISSUER_CANNOT_BE_INDEPENDENT")

    def test_source_strings_are_synthetic_only_and_cannot_carry_account_values(self):
        for field, value in (
            ("primary_source_id", "LIVE_SECRET_ID"),
            ("crosscheck_source_id", None),
            ("primary_issuer", "SYNTHETIC_a"),
            ("crosscheck_issuer", 24),
        ):
            with self.subTest(field=field):
                self.denied(replace(example(), **{field: value}),
                            "FAKE_SOURCE_IDENTIFIER_INVALID")
        for value in ("real-acc-123", "", None):
            self.denied(replace(example(), synthetic_account_alias=value),
                        "SYNTHETIC_ACCOUNT_ALIAS_REQUIRED")

    def test_actual_values_and_confidential_payloads_not_allowed(self):
        self.denied(replace(example(), raw_contract_value="0.01"),
                    "REAL_VALUE_OR_CONFIDENTIAL_PAYLOAD_FORBIDDEN")
        self.denied(replace(example(), confidential_payload_present=True),
                    "REAL_VALUE_OR_CONFIDENTIAL_PAYLOAD_FORBIDDEN")
        self.denied(replace(example(), synthetic_only=False),
                    "REAL_EVIDENCE_SUBMISSION_NOT_SUPPORTED")

    def test_pair_and_symbol_mismatch(self):
        self.denied(replace(example(), pair="GBP/USD"),
                    "PAIR_OR_FIELD_NOT_IN_THREE_PAIR_G1_SCOPE")
        self.denied(replace(example(), field="spread"),
                    "PAIR_OR_FIELD_NOT_IN_THREE_PAIR_G1_SCOPE")
        self.denied(replace(example(), terminal_symbol="GBPUSD"),
                    "ILLUSTRATIVE_TERMINAL_SYMBOL_SHAPE_INVALID")
        self.denied(replace(example(), terminal_symbol=None),
                    "ILLUSTRATIVE_TERMINAL_SYMBOL_SHAPE_INVALID")

    def test_unknown_or_misleading_units(self):
        self.denied(replace(example(), unit_claim="PIP"),
                    "EXPLICIT_UNIT_SHAPE_MISSING_OR_WRONG")
        self.denied(replace(example(), unit_claim="JPY"),
                    "EXPLICIT_UNIT_SHAPE_MISSING_OR_WRONG")
        self.denied(replace(example("EUR/USD", "point_quote"), unit_claim="POINT"),
                    "EXPLICIT_UNIT_SHAPE_MISSING_OR_WRONG")

    def test_missing_or_different_provenance_utc(self):
        self.denied(replace(example(), crosscheck_at_utc="2026-11-04T04:00:01Z"),
                    "CROSSCHECK_SNAPSHOT_TIMESTAMP_MISMATCH")
        for value in ("invalid", "2026-11-04T13:00:00+09:00", None,
                      "2026-11-04T24:00:00Z"):
            with self.subTest(timestamp=value):
                self.denied(replace(example(), observed_at_utc=value),
                            "CROSSCHECK_SNAPSHOT_TIMESTAMP_MISMATCH")

    def test_unknown_account_consistency_and_change_review_refuses(self):
        for key, reason in (
            ("independent_unit_checked_claim",
             "UNIT_NOT_INDEPENDENTLY_CHECKED_IN_FIXTURE"),
            ("same_account_claim",
             "ACCOUNT_PROVENANCE_INCONSISTENT_IN_FIXTURE"),
            ("contract_version_rechecked_claim",
             "CONTRACT_CHANGE_NOT_CHECKED_IN_FIXTURE"),
        ):
            for value in (False, None, 1, "yes"):
                with self.subTest(field=key, value=value):
                    self.denied(replace(example(), **{key: value}), reason)

    def test_do_not_fabricate_approved_source_ttl(self):
        for value in (True, None, "yes", 1):
            with self.subTest(value=value):
                self.denied(replace(example(), freshness_policy_defined_claim=value),
                            "FALSE_FRESHNESS_POLICY_APPROVAL")

    def test_malformed_inputs_never_authorize(self):
        for value in (None, {}, "BUY", True, object()):
            with self.subTest(input_type=type(value).__name__):
                self.denied(value, "INVALID_ENVELOPE")


if __name__ == "__main__":
    unittest.main()
