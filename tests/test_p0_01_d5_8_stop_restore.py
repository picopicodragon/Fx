"""D5-8 offline stop state restart and corruption tests."""
import unittest
from scripts.p0_01_d5_8_stop_restore import restore_synthetic_stop_state as check

def fixture():
    return dict(origin="SYNTHETIC_ONLY", schema_version=1,
                trading_day_start_ny_date="2026-07-01",
                daily_stop_latched=True, last_status="DAILY_STOP",
                sequence=7)

class D58RestoreTests(unittest.TestCase):
    def denied(self,r):
        self.assertEqual(r["phase_1"],"BLOCKED")
        for k in ("broker_verified","production_usable","orders_generated",
                  "terminal_execution_approved","forward_trading_enabled"):
            self.assertIs(r[k],False)

    def test_valid_stop_remains_stopped(self):
        r=check(fixture(),"2026-07-01",7)
        self.assertEqual(r["status"],"RESTORED_STOP_STILL_LATCHED")
        self.assertIs(r["daily_stop_latched"],True);self.denied(r)

    def test_rollover_cannot_clear_stop(self):
        r=check(fixture(),"2026-07-02",7)
        self.assertEqual(r["status"],"RESTORED_STOP_STILL_LATCHED");self.denied(r)

    def test_clean_state_still_blocks_runtime(self):
        f=fixture();f["daily_stop_latched"]=False;f["last_status"]="SYNTHETIC_MONITORING_ONLY"
        r=check(f,"2026-07-01",7)
        self.assertEqual(r["status"],"RESTORED_SYNTHETIC_ONLY_NO_RUNTIME_AUTHORITY")
        self.assertIs(r["daily_stop_latched"],False);self.denied(r)

    def test_missing_corrupted_and_extra_field(self):
        for key in ("origin","sequence","last_status","daily_stop_latched"):
            f=fixture();del f[key]
            self.assertEqual(check(f,"2026-07-01",7)["status"],"RESTORE_REJECTED_FAIL_CLOSED")
        f=fixture();f["approval"]=True
        self.assertEqual(check(f,"2026-07-01",7)["status"],"RESTORE_REJECTED_FAIL_CLOSED")

    def test_stale_sequence_fails_closed(self):
        r=check(fixture(),"2026-07-01",8)
        self.assertEqual(r["status"],"RESTORE_REJECTED_FAIL_CLOSED")
        self.assertIs(r["daily_stop_latched"],True)

    def test_future_snapshot_day_rejected(self):
        self.assertEqual(check(fixture(),"2026-06-30",7)["status"],"RESTORE_REJECTED_FAIL_CLOSED")

    def test_incompatible_version_and_sequence_types(self):
        for k,bad in (("schema_version",2),("schema_version",True),
                      ("sequence",True),("sequence",-1)):
            f=fixture();f[k]=bad
            self.assertEqual(check(f,"2026-07-01",7)["status"],"RESTORE_REJECTED_FAIL_CLOSED")

    def test_contradictory_stopped_status_rejected(self):
        f=fixture();f["daily_stop_latched"]=False
        r=check(f,"2026-07-01",7)
        self.assertEqual(r["status"],"RESTORE_REJECTED_FAIL_CLOSED")
        self.assertIs(r["daily_stop_latched"],True)

    def test_invalid_date_and_reference_sequence_rejected(self):
        for day in ("2026-02-30","2026-7-01",None):
            self.assertEqual(check(fixture(),day,7)["status"],"RESTORE_REJECTED_FAIL_CLOSED")
        for seq in (-1,True,"7",None):
            self.assertEqual(check(fixture(),"2026-07-01",seq)["status"],"RESTORE_REJECTED_FAIL_CLOSED")

    def test_bad_payload_and_secret_never_echoed(self):
        for payload in (None,True,[],{},object(),"PRIVATE_STOP_STATE"):
            r=check(payload,"2026-07-01",7)
            self.assertEqual(r["status"],"RESTORE_REJECTED_FAIL_CLOSED")
            self.denied(r)
        self.assertNotIn("PRIVATE_STOP_STATE",repr(check("PRIVATE_STOP_STATE","2026-07-01",7)))

if __name__=="__main__":
    unittest.main()
