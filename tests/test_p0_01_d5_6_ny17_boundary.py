"""D5-6 NY17 synthetic cutoff with US DST and fail-closed timestamps."""
import unittest
from scripts.p0_01_d5_6_ny17_boundary import label_synthetic_ny17 as check

class NY17BoundaryTests(unittest.TestCase):
    def assert_blocked(self, value):
        for k in ("broker_verified","production_usable","orders_generated",
                  "terminal_execution_approved","forward_trading_enabled"):
            self.assertIs(value[k],False)
        self.assertEqual(value["phase_1"],"BLOCKED")

    def test_summer_ny17_jst_0600(self):
        for stamp,day in (("2026-07-01T20:59:59+00:00","2026-06-30"),
                          ("2026-07-01T21:00:00+00:00","2026-07-01")):
            with self.subTest(stamp=stamp):
                self.assertEqual(check(stamp)["trading_day_start_ny_date"],day)

    def test_winter_ny17_jst_0700(self):
        for stamp,day in (("2026-01-15T21:59:59+00:00","2026-01-14"),
                          ("2026-01-15T22:00:00+00:00","2026-01-15")):
            with self.subTest(stamp=stamp):
                self.assertEqual(check(stamp)["trading_day_start_ny_date"],day)

    def test_dst_start_transition(self):
        for stamp,day in (("2026-03-08T20:59:59+00:00","2026-03-07"),
                          ("2026-03-08T21:00:00+00:00","2026-03-08")):
            with self.subTest(stamp=stamp):
                self.assertEqual(check(stamp)["trading_day_start_ny_date"],day)

    def test_dst_end_transition(self):
        for stamp,day in (("2026-11-01T21:59:59+00:00","2026-10-31"),
                          ("2026-11-01T22:00:00+00:00","2026-11-01")):
            with self.subTest(stamp=stamp):
                self.assertEqual(check(stamp)["trading_day_start_ny_date"],day)

    def test_invalid_and_non_utc_rejected(self):
        for value in (None,True,0,"bad","2026-07-01T21:00:00",
                      "2026-07-02T06:00:00+09:00","2026-07-01T17:00:00-04:00"):
            with self.subTest(value=repr(value)):
                result=check(value)
                self.assertEqual(result["status"],"REVIEW_REQUIRED")
                self.assertIsNone(result["trading_day_start_ny_date"])
                self.assert_blocked(result)

    def test_input_never_authorizes(self):
        for value in ("2026-01-15T22:00:00+00:00","2026-07-01T21:00:00+00:00"):
            result=check(value)
            self.assertEqual(result["status"],"SYNTHETIC_TRADING_DAY_LABELED_NEVER_AUTHORIZED")
            self.assert_blocked(result)

    def test_malformed_timestamp_never_echoed(self):
        result=check("SECRET_PRIVATE_DATE")
        self.assertNotIn("SECRET_PRIVATE_DATE",repr(result))
        self.assert_blocked(result)

    def test_consecutive_seconds_around_cutoff(self):
        before=check("2026-10-29T20:59:59+00:00")
        after=check("2026-10-29T21:00:00+00:00")
        self.assertEqual(before["trading_day_start_ny_date"],"2026-10-28")
        self.assertEqual(after["trading_day_start_ny_date"],"2026-10-29")

if __name__=="__main__":
    unittest.main()
