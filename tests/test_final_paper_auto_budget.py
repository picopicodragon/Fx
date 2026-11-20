"""Final automatic paid research: budget bounds and unknown-bill crash safety."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

from research import final_paper_auto_budget as budget
from research import final_demo_periodic_ai as ai
from research.offline_backtest import InputError

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
BIND="a"*64
ANALYST="gpt-6-analyst"
REVIEWER="gpt-6-reviewer"


class AutoPaidBudgetTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.journal=self.root/"auto_budget_journal"
        self.journal.mkdir()
        (self.root/"provider_pricing_proof.txt").write_bytes(
            b"OPERATOR-REVIEWED-PROVIDER-PRICE-REFERENCE")
        self.auth=self.root/"new_budget.json"
        self.policy_data={
            "schema":budget.SCHEMA,
            "scope":budget.SCOPE,
            "operator_approval":budget.APPROVAL,
            "approved_at_utc":(NOW-timedelta(minutes=1)).isoformat(),
            "expires_at_utc":(NOW+timedelta(hours=5)).isoformat(),
            "month_utc":"2026-11",
            "bound_journal_sha256":BIND,
            "previous_paid_calls_acknowledged":6,
            "analyst_model":ANALYST,
            "reviewer_model":REVIEWER,
            "max_incremental_calls":6,
            "max_incremental_jpy":1200,
            "reserve_jpy_per_two_model_decision":400,
            "model_rates_jpy_per_million":{
                ANALYST:{"input":"1000","output":"3000"},
                REVIEWER:{"input":"1000","output":"3000"},
            },
            "pricing_original_basename":"provider_pricing_proof.txt",
            "pricing_original_sha256":hashlib.sha256(
                (self.root/"provider_pricing_proof.txt").read_bytes()
            ).hexdigest(),
            "previous_provider_billing_reviewed_by_operator":True,
            "cost_projection_not_provider_spend_cap_acknowledged":True,
        }
        self._save()
        self.policy=budget.policy(self.auth,now=NOW,
                                  session_binding_sha=BIND,
                                  analyst_model=ANALYST,
                                  reviewer_model=REVIEWER)

    def _save(self):
        self.auth.write_text(json.dumps(self.policy_data),encoding="utf-8")

    def _complete_ledger(self,packet):
        folder=self.root/"auto_ai_research"
        folder.mkdir(exist_ok=True)
        ledger=folder/"ai_USDJPY_100_20261120_100000.json"
        state={
            "schema":ai.SCHEMA,
            "packet_sha256":packet,
            "analyst_model":ANALYST,
            "reviewer_model":REVIEWER,
            "stage":"COMPLETE","pending_role":None,
            "analyst":{"action":"LONG","hypothesis":"macro cause",
                       "counterevidence":"possible failure"},
            "reviewer":{"verdict":"APPROVED","rationale":"confirmed source"},
            "execution_authorized":False,
            "real_orders_permitted":False,
        }
        ledger.write_text(json.dumps(state),encoding="utf-8")
        return ledger

    def test_reserve_persisted_before_request_and_cannot_auto_retry_unknown(self):
        packet="c"*64
        reserve=budget.reserve(self.policy,self.journal,
                               journal_reserve_shas=[],
                               pair="USD/JPY",packet_sha=packet,now=NOW)
        self.assertEqual(len(list(self.journal.glob("*.json"))),1)
        state=budget._load(self.journal)
        self.assertIn(reserve,state["pending_reservations"])
        self.assertEqual(state["spent_or_reserved_calls"],2)
        self.assertEqual(state["spent_or_reserved_jpy"],400)
        with self.assertRaises(InputError):
            budget.check(self.policy,self.journal,journal_reserve_shas=[])
        with self.assertRaises(InputError):
            budget.reserve(self.policy,self.journal,
                           journal_reserve_shas=[],pair="EUR/JPY",
                           packet_sha="d"*64,now=NOW)
        self.assertEqual(len(list(self.journal.glob("*.json"))),1)

    def test_two_models_complete_and_paper_receipt_reconciles_without_old_reset(self):
        packet="c"*64
        reserve=budget.reserve(self.policy,self.journal,
                               journal_reserve_shas=[],
                               pair="USD/JPY",packet_sha=packet,now=NOW)
        budget.settle(self.journal,reserve_sha=reserve,
                      ledger=self._complete_ledger(packet),now=NOW)
        result=budget.check(self.policy,self.journal,
                            journal_reserve_shas=[reserve])
        self.assertEqual(result["settled_reserve_shas"],[reserve])
        self.assertEqual(result["spent_or_reserved_calls"],2)
        self.assertEqual(result["spent_or_reserved_jpy"],400)
        self.assertEqual(budget.reserve_status(self.policy,self.journal)[
            "old_historical_paid_calls_preserved"],6)
        with self.assertRaises(InputError):
            budget.check(self.policy,self.journal,journal_reserve_shas=[])

    def test_out_of_packet_settlement_fails_closed_and_keeps_reservation(self):
        packet="c"*64
        reserve=budget.reserve(self.policy,self.journal,
                               journal_reserve_shas=[],
                               pair="USD/JPY",packet_sha=packet,now=NOW)
        with self.assertRaises(InputError):
            budget.settle(self.journal,reserve_sha=reserve,
                          ledger=self._complete_ledger("d"*64),now=NOW)
        self.assertEqual(budget._load(self.journal)["sequence"],1)

    def test_budget_usage_capped_even_if_operator_asks_more_than_3000(self):
        self.policy_data["max_incremental_jpy"]=3001
        self._save()
        with self.assertRaises(InputError):
            budget.policy(self.auth,now=NOW,
                          session_binding_sha=BIND,
                          analyst_model=ANALYST,
                          reviewer_model=REVIEWER)
        self.policy_data["max_incremental_jpy"]=1200
        self.policy_data["reserve_jpy_per_two_model_decision"]=10
        self._save()
        with self.assertRaises(InputError):
            budget.policy(self.auth,now=NOW,
                          session_binding_sha=BIND,
                          analyst_model=ANALYST,
                          reviewer_model=REVIEWER)

    def test_approval_bound_to_month_models_and_existing_six_calls(self):
        for field,value in (
            ("previous_paid_calls_acknowledged",0),
            ("month_utc","2026-12"),
            ("operator_approval","FORGED"),
            ("bound_journal_sha256","0"*64),
            ("analyst_model",REVIEWER),
            ("previous_provider_billing_reviewed_by_operator",False),
        ):
            with self.subTest(field=field):
                original=self.policy_data[field]
                self.policy_data[field]=value
                self._save()
                with self.assertRaises(InputError):
                    budget.policy(self.auth,now=NOW,
                                  session_binding_sha=BIND,
                                  analyst_model=ANALYST,
                                  reviewer_model=REVIEWER)
                self.policy_data[field]=original

    def test_tampered_or_missing_price_original_blocked(self):
        (self.root/"provider_pricing_proof.txt").write_bytes(b"changed")
        with self.assertRaises(InputError):
            budget.policy(self.auth,now=NOW,
                          session_binding_sha=BIND,
                          analyst_model=ANALYST,
                          reviewer_model=REVIEWER)

    def test_budget_journal_hash_tamper_fails_closed(self):
        budget.reserve(self.policy,self.journal,journal_reserve_shas=[],
                       pair="EUR/USD",packet_sha="e"*64,now=NOW)
        path=self.journal/"00000001.json"
        data=json.loads(path.read_text("utf-8"))
        data["reserve_jpy"]=1
        path.write_text(json.dumps(data),encoding="utf-8")
        with self.assertRaises(InputError):
            budget._load(self.journal)


if __name__=="__main__":
    unittest.main()
