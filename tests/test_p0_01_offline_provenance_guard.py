"""D4-1 fail-closed synthetic-only contract tests."""
import copy
import unittest
from scripts.p0_01_offline_provenance_guard import (
    check_candidate, EXPECTED_UNITS, REVIEW, INCOMPLETE, PENDING,
)
from scripts.p0_01_offline_five_field_mock import PAIRS


def candidate():
    return {
        "origin": "MANUAL_UNVERIFIED", "observed_at": "2026-10-28T00:00:00+00:00",
        "evidence_kind": "MANUAL_SCREEN_NOTE_UNVERIFIED",
        "account_currency": "JPY", "contract_basis_confirmed": False,
        "symbols": [{"symbol": pair,
                     "properties": {"min_lot": "0.1", "lot_step": "0.01",
                                    "point_quote": "0.001", "tick_size_points": "1",
                                    "tick_value_deposit_currency": "10"},
                     "units": dict(EXPECTED_UNITS)} for pair in PAIRS],
    }


NOW = "2026-10-28T01:00:00+00:00"


class OfflineProvenanceTests(unittest.TestCase):
    def test_candidate_remains_unverified(self):
        result = check_candidate(candidate(), NOW)
        self.assertEqual(result["status"], PENDING)
        self.assertFalse(result["broker_verified"])
        self.assertFalse(result["production_usable"])
        self.assertFalse(result["orders_generated"])
        self.assertFalse(result["forward_trading_enabled"])
        self.assertEqual(result["phase_1"], "BLOCKED")

    def test_origin_forgery_rejected(self):
        for origin in ("SYNTHETIC", "BROKER_VERIFIED", "", None, True):
            d = candidate()
            d["origin"] = origin
            self.assertEqual(check_candidate(d, NOW)["status"], REVIEW)

    def test_units_and_symbol_issues(self):
        for field in EXPECTED_UNITS:
            d = candidate()
            d["symbols"][0]["units"][field] = "wrong_unit"
            self.assertEqual(check_candidate(d, NOW)["status"], REVIEW)
        d = candidate()
        d["symbols"][1]["symbol"] = d["symbols"][0]["symbol"]
        self.assertEqual(check_candidate(d, NOW)["status"], REVIEW)

    def test_naive_future_and_old_timestamps_rejected(self):
        for stamp in ("2026-10-28T00:00:00", "2026-10-30T00:00:00+00:00",
                      "2026-10-20T00:00:00+00:00", "bad"):
            d = candidate()
            d["observed_at"] = stamp
            self.assertEqual(check_candidate(d, NOW)["status"], REVIEW)

    def test_missing_evidence_incomplete(self):
        for field in ("observed_at", "evidence_kind", "account_currency"):
            d = candidate()
            d[field] = None
            self.assertEqual(check_candidate(d, NOW)["status"], INCOMPLETE)
        d = candidate()
        d["symbols"][0]["properties"]["min_lot"] = None
        self.assertEqual(check_candidate(d, NOW)["status"], INCOMPLETE)

    def test_false_claim_of_contract_confirmation_rejected(self):
        d = candidate()
        d["contract_basis_confirmed"] = True
        self.assertEqual(check_candidate(d, NOW)["status"], REVIEW)

    def test_invalid_precedes_missing(self):
        d = candidate()
        d["symbols"][0]["properties"]["min_lot"] = None
        d["symbols"][1]["units"]["point_quote"] = "tick"
        self.assertEqual(check_candidate(d, NOW)["status"], REVIEW)

    def test_secret_never_appears_in_result(self):
        d = candidate()
        d["evidence_kind"] = "SECRET_INPUT_PAYLOAD"
        self.assertNotIn("SECRET_INPUT_PAYLOAD", repr(check_candidate(d, NOW)))

    def test_root_schema_and_reference_time_fail_closed(self):
        for d in (None, {}, [], "SECRET", 1):
            self.assertEqual(check_candidate(d, NOW)["status"], REVIEW)
        self.assertEqual(check_candidate(candidate(), "bad")["status"], REVIEW)

    def test_never_import_io_or_trading_runtime(self):
        import inspect
        import scripts.p0_01_offline_provenance_guard as mod
        source = inspect.getsource(mod)
        for forbidden in ("import socket", "import requests", "import subprocess",
                          "import MetaTrader5", "OrderSend(", "MarketInfo(",
                          "open(", "read_text(", "write_text("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
