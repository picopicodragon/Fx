"""FWD-017: journal-prefix proof without authenticating source data."""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path

from research.forward_cycle_chain_audit import verify
from research.offline_backtest import InputError
from tests.test_forward_multicycle import report


class CycleChainAuditTests(unittest.TestCase):
    def setUp(self):
        self.one = report("cycle1", "2026-11-10T22:00:00Z", 1, "0",
                          position=False)
        self.two = report("cycle2", "2026-11-10T22:01:00Z", 2, "0",
                          position=False)
        self.chain = [
            {"record_sha256": "a" * 64,
             "captured_at_utc": "2026-11-10T21:59:59Z"},
            {"record_sha256": "b" * 64,
             "captured_at_utc": "2026-11-10T22:00:20Z"},
        ]

    @patch("research.forward_cycle_chain_audit.records")
    def test_both_prefixes_are_verified_without_trade_permission(self, mock):
        mock.return_value = self.chain
        result = verify(Path("unused"), [self.one, self.two])
        self.assertEqual(result["status"], "FORWARD_CYCLE_CHAIN_VERIFIED_NO_GO")
        self.assertTrue(result["local_hash_chain_integrity_verified"])
        self.assertFalse(result["source_authenticity_verified"])
        self.assertFalse(result["real_orders_permitted"])
        self.assertEqual(result["anchored_cycles"][0][
            "last_observation_record_sha256"], "a" * 64)

    @patch("research.forward_cycle_chain_audit.records")
    def test_missing_earlier_observation_rejected(self, mock):
        mock.return_value = self.chain
        bad = copy.deepcopy(self.two)
        bad["quality"]["record_count"] = 1
        with self.assertRaises(InputError):
            verify(Path("unused"), [bad])

    @patch("research.forward_cycle_chain_audit.records")
    def test_future_record_in_prefix_rejected(self, mock):
        mock.return_value = self.chain
        bad = copy.deepcopy(self.one)
        bad["quality"]["record_count"] = 2
        with self.assertRaises(InputError):
            verify(Path("unused"), [bad])

    @patch("research.forward_cycle_chain_audit.records")
    def test_paper_references_must_exist_in_prefix(self, mock):
        mock.return_value = self.chain
        bad = report("cycle1", "2026-11-10T22:00:00Z", 1, "0")
        with self.assertRaises(InputError):
            verify(Path("unused"), [bad])

    @patch("research.forward_cycle_chain_audit.records")
    def test_empty_journal_is_allowed_only_for_empty_cycle(self, mock):
        mock.return_value = []
        empty = report("cycle0", "2026-11-10T22:00:00Z", 0, "0", position=False)
        out = verify(Path("unused"), [empty])
        self.assertEqual(out["anchored_cycles"][0][
            "last_observation_record_sha256"], "0" * 64)

    @patch("research.forward_cycle_chain_audit.records")
    def test_overreported_count_is_refused(self, mock):
        mock.return_value = self.chain
        bad = copy.deepcopy(self.one)
        bad["quality"]["record_count"] = 3
        with self.assertRaises(InputError):
            verify(Path("unused"), [bad])


if __name__ == "__main__":
    unittest.main()
