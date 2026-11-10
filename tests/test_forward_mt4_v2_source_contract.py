"""FWD-057 independent static contract regression for undeployed MQL4 v2."""
import unittest
from pathlib import Path

from research.forward_mt4_v2_source_contract import review


def source():
    return (Path(__file__).resolve().parents[1] /
            "research/mt4_readonly/FxForwardReadOnlyQuoteV2.mq4").read_bytes()


class SourceContractV2Tests(unittest.TestCase):
    def test_repo_v2_script_has_required_contract(self):
        result = review(source())
        self.assertEqual(result["static_failures"], [])
        self.assertTrue(result["static_contract_passed"])
        self.assertFalse(result["metaeditor_compilation_verified"])
        self.assertFalse(result["real_orders_permitted"])

    def test_trade_api_added_fails(self):
        result = review(source() + b"\nvoid danger(){OrderSend();}")
        self.assertFalse(result["static_contract_passed"])

    def test_missing_demo_guard_fails(self):
        result = review(source().replace(b"IsDemo()", b"IsSomethingElse()"))
        self.assertFalse(result["static_contract_passed"])

    def test_missing_server_time_rejected(self):
        result = review(source().replace(b"MODE_TIME", b"MODE_SPREAD"))
        self.assertFalse(result["static_contract_passed"])

    def test_missing_pair_rejected(self):
        result = review(source().replace(b'symbol == "EURUSD"',
                                         b'symbol == "GBPUSD"'))
        self.assertFalse(result["static_contract_passed"])

    def test_no_network_api_allowed(self):
        result = review(source() + b"\nWebRequest();")
        self.assertFalse(result["static_contract_passed"])


if __name__ == "__main__":
    unittest.main()
