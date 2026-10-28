"""Safety checks for proposed (not authorized) Rakuten MT4 dual-demo architecture."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
NEW = ROOT / "specs/p0_01_isolated_demo_environment_design.json"
EXISTING = ROOT / "specs/p0_01_mt4_readonly_observation_plan.json"


class IsolatedRakutenMt4DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(NEW.read_text(encoding="utf-8"))
        cls.older = json.loads(EXISTING.read_text(encoding="utf-8"))

    def test_design_does_not_approve_any_environment_action(self):
        p = self.plan
        self.assertEqual(
            p["status"], "DESIGN_PROPOSAL_ONLY_UNAPPROVED_NO_ENVIRONMENT_ACTIONS"
        )
        for action in (
            "CREATE_DEMO_ACCOUNT", "INSTALL_OR_LAUNCH_SECOND_MT4",
            "SWITCH_OR_LOGIN_TO_ANY_MT4_ACCOUNT",
            "CHANGE_EXISTING_MACD_SAMPLE_OR_AUTOTRADING",
            "MODIFY_OR_CLOSE_EXISTING_POSITIONS_OR_PENDING_ORDERS",
            "MOVE_OR_EXECUTE_MQL4_EX4",
            "CALL_BROKER_MARKETINFO_FROM_TERMINAL",
            "PLACE_MODIFY_CANCEL_OR_CLOSE_TRADES",
        ):
            self.assertIn(action, p["forbidden_actions"])
        for flag in (
            "implementation_approved", "owner_approved_for_safety",
            "human_safety_approval", "forward_trading_enabled",
            "readonly_terminal_execution_approved",
            "broker_queried", "live_orders_enabled",
        ):
            self.assertIs(p["safety_gates"][flag], False)
        self.assertEqual(p["safety_gates"]["phase_1"], "BLOCKED")
        self.assertFalse(self.older["permissions"]["terminal_execution_approved"])
        self.assertFalse(self.older["safety_gates"]["forward_trading_enabled"])

    def test_existing_demo_is_never_overwritten_or_used_for_read_probe(self):
        a = self.plan["existing_environment_A"]
        self.assertEqual(
            a["account_type"], "DEMO_OWNER_VISUAL_REPORT"
        )
        self.assertEqual(
            a["open_positions_or_pending_orders"], "YES_OWNER_VISUAL_REPORT"
        )
        self.assertEqual(
            a["macd_sample_presence"],
            "CHART_ATTACHED_AND_NAVIGATOR_OWNER_VISUAL_REPORT",
        )
        self.assertFalse(a["use_for_readonly_probe"])
        self.assertEqual(
            a["operation_policy"],
            "NO_CHANGES_TO_EXISTING_TERMINAL_EA_ACCOUNTS_POSITIONS_ORDERS_OR_AUTOTRADING",
        )
        self.assertEqual(
            a["market_watch_exact_symbols"],
            ["USDJPY", "EURJPY", "GBPUSD", "AUDUSD"],
        )

    def test_broker_multiple_account_policy_is_explicitly_unverified(self):
        policy = self.plan["unresolved_broker_policy"]
        for field in (
            "concurrent_independent_demo_accounts_supported",
            "another_creation_replaces_or_invalidates_previous",
            "simultaneous_login_to_two_distinct_demo_accounts",
        ):
            self.assertEqual(
                policy[field], "UNVERIFIED_OFFICIAL_MT4_DEMO_SUPPORT_EXCLUDED"
            )
        self.assertFalse(policy["new_demo_opening_currently_authorized"])
        self.assertTrue(policy["no_account_creation_until_policy_confirmed"])
        choices = {x["id"]: x for x in self.plan["options"]}
        self.assertTrue(choices["A"]["recommended"])
        self.assertFalse(choices["A"]["runtime_allowed"])
        self.assertTrue(choices["B"]["recommended_as_fallback"])
        self.assertFalse(choices["C"]["recommended"])
        self.assertTrue(all(not x["runtime_allowed"] for x in choices.values()))

    def test_official_mt4_demo_support_exclusion_keeps_g1_blocked(self):
        policy = self.plan["unresolved_broker_policy"]
        self.assertEqual(
            policy["official_demo_support_policy"],
            "DEMO_ACCOUNT_USAGE_INQUIRIES_OUTSIDE_PUBLISHED_SUPPORT_SCOPE",
        )
        self.assertEqual(
            policy["official_support_policy_source"],
            "https://www.rakuten-sec.co.jp/web/support/cs/fx_mt4.html",
        )
        self.assertTrue(policy["official_public_documentation_still_required"])
        self.assertFalse(policy["new_demo_opening_currently_authorized"])
        self.assertEqual(
            policy["design_fallback"],
            "OFFLINE_MOCKS_NO_MT4_CONNECTION_NO_DEMO_ACCOUNT_CREATION",
        )
        self.assertEqual(
            self.plan["sequential_design_gates"][1]["status"],
            "BLOCKED_EXTERNAL_POLICY",
        )
        self.assertFalse(self.plan["safety_gates"]["readonly_terminal_execution_approved"])

    def test_isolated_terminal_cannot_share_live_server_or_trade(self):
        b = self.plan["candidate_B"]
        self.assertEqual(b["initial_deployment_status"], "NOT_INSTALLED")
        self.assertEqual(b["terminal_server_expected"], "RakutenSecurities-Demo")
        self.assertEqual(b["live_server_denied"], "RakutenSecurities-Live")
        self.assertEqual(b["experts"], "NO_ATTACHED_EA")
        self.assertEqual(b["open_positions_or_pending_orders"], "MUST_BE_ZERO")
        self.assertEqual(
            b["account_id_or_password_storage"], "NONE_IN_GITHUB_OR_CHAT_OR_SPEC_JSON"
        )
        self.assertFalse(b["credentials_required_from_user_for_design"])
        self.assertEqual(
            b["mq4_ex4_copy_to_mt4"], "PROHIBITED_UNTIL_SEPARATE_OWNER_APPROVAL"
        )
        self.assertEqual(
            b["script_execution"], "PROHIBITED_UNTIL_SEPARATE_OWNER_APPROVAL"
        )
        self.assertTrue(b["no_automatic_order_process"])
        self.assertTrue(b["no_python_ea_bridge"])
        self.assertEqual(b["symbol_names"],
                         ["USDJPY", "EURJPY", "GBPUSD", "AUDUSD"])

    def test_5m_demo_equity_must_not_be_100k_production_sizing(self):
        budget = self.plan["financial_constraints"]
        self.assertEqual(budget["rakuten_demo_initial_equity_jpy"], 5000000)
        self.assertEqual(budget["initial_actual_equity_jpy"], 100000)
        self.assertEqual(budget["rakuten_demo_max_leverage"], 25)
        self.assertFalse(budget["demo_orders_approved"])
        self.assertFalse(budget["equity_based_live_sizing_approved"])
        self.assertTrue(
            budget["tick_value_and_contract_unit_require_separate_form_01_and_form_03_verification"]
        )

    def test_gate_order_keeps_setup_and_runtime_separate(self):
        gates = self.plan["sequential_design_gates"]
        self.assertEqual([x["id"] for x in gates],
                         ["G0", "G1", "G2", "G3", "G4", "G5", "G6"])
        self.assertEqual(gates[1]["status"], "BLOCKED_EXTERNAL_POLICY")
        self.assertEqual(gates[2]["status"], "NOT_AUTHORIZED")
        self.assertEqual(gates[5]["status"], "NOT_AUTHORIZED")
        for gate in gates[2:]:
            self.assertTrue(gate["requires_human_approval"])


if __name__ == "__main__":
    unittest.main()
