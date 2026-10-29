"""D5-9 in-memory sequence continuity and stop protection."""
import copy
import unittest
from scripts.p0_01_d5_9_snapshot_chain import audit_synthetic_snapshot_chain as check

def chain():
    return [
        {"origin": "SYNTHETIC_ONLY", "schema_version": 1,
         "trading_day_start_ny_date": "2026-07-01",
         "daily_stop_latched": True, "last_status": "DAILY_STOP", "sequence": 10},
        {"origin": "SYNTHETIC_ONLY", "schema_version": 1,
         "trading_day_start_ny_date": "2026-07-02",
         "daily_stop_latched": True, "last_status": "NEXT_DAY_REVIEW_PENDING", "sequence": 11},
    ]

class D59SnapshotChainTests(unittest.TestCase):
    def denied(self, result):
        self.assertEqual(result["phase_1"], "BLOCKED")
        for key in ("broker_verified","production_usable","orders_generated",
                    "terminal_execution_approved","forward_trading_enabled"):
            self.assertIs(result[key], False)

    def rejected(self, snapshots):
        r=check(snapshots,"2026-07-02")
        self.assertEqual(r["status"],"CHAIN_REJECTED_FAIL_CLOSED")
        self.assertIs(r["daily_stop_latched"],True)
        self.denied(r)

    def test_contiguous_stopped_chain(self):
        r=check(chain(),"2026-07-02")
        self.assertEqual(r["status"],"CHAIN_CONSISTENT_STOP_LATCHED_SYNTHETIC_ONLY")
        self.assertIs(r["daily_stop_latched"],True)
        self.denied(r)

    def test_gap_rejected(self):
        items=chain();items[1]["sequence"]=12
        self.rejected(items)

    def test_rollback_or_duplicate_rejected(self):
        for seq in (9,10):
            items=chain();items[1]["sequence"]=seq
            self.rejected(items)

    def test_rollback_of_day_rejected(self):
        items=chain();items[0]["trading_day_start_ny_date"]="2026-07-02"
        items[1]["trading_day_start_ny_date"]="2026-07-01"
        self.rejected(items)

    def test_stopped_to_unstopped_rejected(self):
        items=chain();items[1]["daily_stop_latched"]=False
        items[1]["last_status"]="SYNTHETIC_MONITORING_ONLY"
        self.rejected(items)

    def test_hard_stop_downgrade_rejected(self):
        items=chain();items[0]["last_status"]="HARD_STOP_DD5"
        self.rejected(items)

    def test_corruption_and_injection_rejected(self):
        items=chain();items[1]["approval"]=True
        self.rejected(items)
        items=chain();items[1]["schema_version"]=2
        self.rejected(items)
        items=chain();items[1]["sequence"]=True
        self.rejected(items)

    def test_valid_nonstopped_still_never_authorized(self):
        items=chain()[:1]
        items[0]["daily_stop_latched"]=False
        items[0]["last_status"]="SYNTHETIC_MONITORING_ONLY"
        r=check(items,"2026-07-02")
        self.assertEqual(r["status"],"CHAIN_CONSISTENT_NEVER_AUTHORIZED")
        self.denied(r)

    def test_empty_missing_invalid_rejected(self):
        for value in ([],None,{},True,"private",object()):
            self.rejected(value)
        self.assertEqual(check(chain(),"2026-02-30")["status"],"CHAIN_REJECTED_FAIL_CLOSED")

    def test_no_mutation_or_secrets_echo(self):
        items=chain();before=copy.deepcopy(items)
        self.denied(check(items,"2026-07-02"))
        self.assertEqual(items,before)
        items[1]["last_status"]="PRIVATE_SECRET"
        self.assertNotIn("PRIVATE_SECRET",repr(check(items,"2026-07-02")))

if __name__=="__main__":
    unittest.main()
