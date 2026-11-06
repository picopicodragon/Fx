"""P05-01/02/04/05/03 synthetic gates: fail-closed regression tests."""
from __future__ import annotations

import copy
import unittest

from scripts import risk_3p_38_synthetic_session_identity as identity
from scripts import risk_3p_39_synthetic_ea_no_interference as ea
from scripts import risk_3p_40_synthetic_p05_interlock_matrix as matrix


class SessionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.doc = identity.fixture()

    def reject(self, change, code):
        value = copy.deepcopy(self.doc)
        change(value)
        r = identity.evaluate(value)
        self.assertEqual(r["status"], "FAIL_CLOSED", r)
        self.assertIn(code, r["errors"])
        self.assertFalse(r["real_account_identity_verified"])
        self.assertFalse(r["real_single_session_verified"])
        self.assertFalse(r["mt4_login_authorized"])
        self.assertFalse(r["parallel_session_authorized"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(r["safety_hold_latched"])

    def test_fictional_match_not_identity_proof(self):
        r = identity.evaluate(self.doc)
        self.assertEqual(r["status"], "PASS_SIMULATED_IDENTIFIERS_ONLY")
        self.assertTrue(r["simulated_match"])
        self.assertFalse(r["p05_01_accepted"])
        self.assertFalse(r["p05_04_accepted"])

    def test_wrong_account_and_account_type_refused(self):
        for source in ("terminal", "mock_server"):
            for key, value in (
                ("account_alias", "SIM_OTHER"),
                ("account_class", "SIM_LIVE"),
                ("account_class", None),
                ("session_alias", "SIM_SECOND_SESSION"),
                ("status", "SIM_DISCONNECTED"),
                ("origin", "SIM_WRONG_SOURCE"),
                ("observed_at_token", "REAL_UTC_2026"),
            ):
                with self.subTest(source=source, key=key, value=value):
                    self.reject(lambda p, s=source, k=key, v=value:
                                p[s].update({k: v}),
                                "P38_IDENTITY_OR_SESSION_UNVERIFIED:" + source)

    def test_owner_display_not_broker_identity(self):
        self.reject(lambda p: p.update(
            owner_ui="BROKER_IDENTITY_CONFIRMED"),
            "P38_OWNER_UI_PROMOTED_TO_IDENTITY")
        self.reject(lambda p: p.update(
            classification="REAL_BROKER_EVIDENCE"),
            "P38_OWNER_UI_PROMOTED_TO_IDENTITY")

    def test_single_session_safety_cannot_enable_login(self):
        for field in identity.SAFETY:
            with self.subTest(field=field):
                update = (not identity.SAFETY[field]
                          if type(identity.SAFETY[field]) is bool else
                          (1 if field == "p05_passed" else "GO"))
                self.reject(lambda p, k=field, v=update:
                            p["safety"].update({k: v}),
                            "P38_FORGED_LOGIN_OR_TRADE_PERMISSION")

    def test_login_and_account_identifiers_cannot_be_injected(self):
        self.reject(lambda p: p.update(
            account_number="SECRET_ACCOUNT_ID"),
            "P38_INVALID_OR_EXTRA_FIELDS")
        self.reject(lambda p: p["terminal"].update(
            password="DONT_STORE"),
            "P38_IDENTITY_OR_SESSION_UNVERIFIED:terminal")
        self.reject(lambda p: p["mock_server"].update(
            session_count=2),
            "P38_IDENTITY_OR_SESSION_UNVERIFIED:mock_server")

    def test_malformed_inputs_refuse_with_no_payload_echo(self):
        for inp in (None, [], {}, "", 1, True, {
                "password": "SECRET_TO_NOT_ECHO"}):
            r = identity.evaluate(inp)
            self.assertEqual(r["status"], "FAIL_CLOSED")
            self.assertNotIn("SECRET_TO_NOT_ECHO", str(r))


class EAInterferenceTests(unittest.TestCase):
    def setUp(self):
        self.doc = ea.fixture()

    def reject(self, change, code):
        p = copy.deepcopy(self.doc)
        change(p)
        r = ea.evaluate(p)
        self.assertEqual(r["status"], "FAIL_CLOSED", r)
        self.assertIn(code, r["errors"], r)
        self.assertFalse(r["p05_02_accepted"])
        self.assertFalse(r["p05_05_accepted"])
        self.assertFalse(r["terminal_interaction_permitted"])
        self.assertFalse(r["actual_ea_runtime_verified"])
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(r["safety_hold_latched"])

    def test_sad_face_autotrading_off_like_are_only_owner_ui_reports(self):
        r = ea.evaluate(self.doc)
        self.assertEqual(r["status"],
                         "PASS_OFFLINE_NON_INTERFERENCE_PLAN_ONLY")
        self.assertFalse(r["actual_autotrading_off_verified"])
        self.assertFalse(r["actual_order_absence_verified"])

    def test_visible_ea_never_proves_execution_stopped(self):
        for field in ("ea_execution_proven", "unknown_ea_excluded",
                      "positions_or_orders_reconciled"):
            with self.subTest(field=field):
                self.reject(lambda p, k=field:
                            p["simulation"].update({k: True}),
                            "P39_UNVERIFIED_EA_ACTIVITY_OR_ORDERS_CLAIMED")

    def test_sad_face_and_autotrading_can_be_ambiguous(self):
        for key, value in (("ea_visible", "SIM_NOT_PRESENT"),
                           ("autotrading_display", "SIM_ON_LIKE"),
                           ("face_display", "SIM_HAPPY_FACE")):
            self.reject(lambda p, k=key, v=value:
                        p["simulation"].update({k: v}),
                        "P39_UNVERIFIED_EA_ACTIVITY_OR_ORDERS_CLAIMED")

    def test_interactions_are_forbidden_even_with_fictional_data(self):
        for action in ("SIM_CLICK_AUTOTRADING", "SIM_REMOVE_EA",
                       "SIM_START_SCRIPT", "SIM_CLOSE_ORDER",
                       "SIM_LOGIN_SECOND_TERMINAL", "SIM_DISMISS_DIALOG"):
            with self.subTest(action=action):
                self.reject(lambda p, v=action:
                            p["simulation"].update(proposed_interaction=v),
                            "P39_UNAUTHORIZED_INTERACTION_OR_FALSE_PROOF")
        self.reject(lambda p: p["simulation"].update(
            interaction_side_effect_proven_absent=True),
            "P39_UNAUTHORIZED_INTERACTION_OR_FALSE_PROOF")

    def test_no_execution_permission_can_be_forged(self):
        for key, value in ea.SAFETY.items():
            with self.subTest(key=key):
                changed = (not value if type(value) is bool else
                           (1 if key == "p05_passed" else "GO"))
                self.reject(lambda p, k=key, v=changed:
                            p["safety"].update({k: v}),
                            "P39_FORGED_EA_OR_ORDER_PERMISSION")

    def test_unknown_fields_and_private_logs_refused(self):
        self.reject(lambda p: p.update(
            account_number="PRIVATE_ACCOUNT"),
            "P39_SCHEMA_OR_SECRET_FIELD_INVALID")
        self.reject(lambda p: p["simulation"].update(
            raw_mt4_log="CONFIDENTIAL"),
            "P39_SIMULATION_MISSING_OR_EXTRA_FIELDS")

    def test_malformed_inputs_refuse(self):
        for inp in (None, [], {}, "", 42, True):
            r = ea.evaluate(inp)
            self.assertEqual(r["status"], "FAIL_CLOSED")
            self.assertEqual(r["runtime_go_no_go"], "NO_GO")


class CompositeInterlocksTests(unittest.TestCase):
    def setUp(self):
        self.package = matrix.fixture()

    def reject(self, change, code):
        p = copy.deepcopy(self.package)
        change(p)
        r = matrix.evaluate(p)
        self.assertEqual(r["status"], "FAIL_CLOSED", r)
        self.assertIn(code, r["errors"], r)
        self.assertFalse(r["real_broker_orders_absent_verified"])
        self.assertFalse(r["real_mt4_read_authorized"])
        self.assertFalse(r["broker_order_or_ea_action_authorized"])
        self.assertFalse(r["human_p05_08_signoff"])
        self.assertEqual(r["real_p05_passed"], 0)
        self.assertEqual(r["runtime_go_no_go"], "NO_GO")
        self.assertTrue(r["safety_hold_latched"])

    def test_zero_and_exposure_fixtures_have_no_real_approval(self):
        for exposure in (False, True):
            with self.subTest(exposure=exposure):
                r = matrix.evaluate(
                    matrix.fixture(simulated_exposure=exposure))
                self.assertEqual(r["status"], "PASS_SYNTHETIC_MATRIX_ONLY")
                self.assertEqual(r["simulated_checks_integrated"], 3)
                self.assertEqual(r["real_p05_passed"], 0)
                self.assertEqual(r["runtime_go_no_go"], "NO_GO")

    def test_each_component_failure_propagates(self):
        self.reject(lambda p: p["account_identity"]["mock_server"].update(
            session_alias="SIM_SECOND_SESSION"),
            "P40_IDENTITY_SIMULATION_BLOCKED")
        self.reject(lambda p: p["ea_no_interference"]["simulation"].update(
            proposed_interaction="SIM_CHANGE_ORDER"),
            "P40_EA_SIMULATION_BLOCKED")
        self.reject(lambda p: p["orders"]["server"]["rows"][3].update(
            open_positions=1),
            "P40_ORDERS_SIMULATION_BLOCKED")

    def test_no_p05_gate_can_be_upgraded_from_simulation(self):
        for key, original in matrix.EXPECTED_SAFETY.items():
            with self.subTest(key=key):
                changed = (not original if type(original) is bool else
                           (1 if key == "p05_passed" else "GO"))
                self.reject(lambda p, k=key, v=changed:
                            p["safety"].update({k: v}),
                            "P40_RUNTIME_OR_P05_APPROVAL_FORGED")

    def test_real_data_claim_or_secret_leak_refused(self):
        self.reject(lambda p: p.update(
            classification="REAL_MT4_EVIDENCE"),
            "P40_SYNTHETIC_SCOPE_PROMOTED")
        self.reject(lambda p: p.update(
            account_id="DONT_ECHO_PRIVATE_VALUE"),
            "P40_INVALID_OR_SECRET_FIELDS")
        self.reject(lambda p: p["orders"].update(
            private_account_id="HIDDEN"),
            "P40_ORDERS_SIMULATION_BLOCKED")

    def test_malformed_composite_fails_closed(self):
        for bad in (None, [], {}, "", 10, True,
                    {"raw_secret": "SECRET"}):
            result = matrix.evaluate(bad)
            self.assertEqual(result["status"], "FAIL_CLOSED")
            self.assertFalse(result["real_mt4_read_authorized"])
            self.assertEqual(result["runtime_go_no_go"], "NO_GO")
            self.assertNotIn("SECRET", str(result))
