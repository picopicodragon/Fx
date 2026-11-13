"""FWD-601..616: re-verification of previously written forecast archive."""
from __future__ import annotations

import hashlib
import unittest

from research import forward_macro_pre_release_capture as forecasts
from research.offline_backtest import InputError

EVENT = "2026-11-20T15:00:00Z"
ASOF = "2026-11-20T14:46:00Z"
BASE = {
    "schema": forecasts.SCHEMA,
    "status": "PRE_RELEASE_CONSENSUS_CAPTURED_RESEARCH_NO_GO",
    "recorded_at_utc_local_clock_unattested": "2026-11-20T14:44:59Z",
    "event_title_unverified": "State Employment and Unemployment (Monthly)",
    "scheduled_at_utc_unverified": EVENT,
    "pair": "USD/JPY",
    "forecast_value_self_reported": "2.7",
    "unit": "percent",
    "source_url_unverified": "https://example.org/forecasts/early",
    "source_text_excerpt": "Forecast consensus 2.7 percent",
    "source_text_sha256": hashlib.sha256(
        b"Forecast consensus 2.7 percent").hexdigest(),
    "source_published_at_utc_self_reported": "2026-11-20T14:00:00Z",
    "calendar_report_sha256_self_reported": "a"*64,
    "source_truth_authenticated": False,
    "published_at_independently_attested": False,
    "forecast_poll_or_web_search_performed": False,
    "demo_orders_permitted": False,
    "real_orders_permitted": False,
    "runtime_go_no_go": "NO_GO",
    "safety_hold_latched": True,
}


def wrap(**changes):
    data = dict(BASE, **changes)
    return {"record": data, "record_sha256": forecasts.sha(data)}


class ForecastReplayBoundaryTests(unittest.TestCase):
    def test_15min_plus_one_second_early_accepted_but_not_authenticated(self):
        result = forecasts.verify_archive(wrap(), asof_utc=ASOF)
        self.assertFalse(result["source_truth_authenticated"])
        self.assertFalse(result["demo_orders_permitted"])
        self.assertEqual(result["runtime_go_no_go"], "NO_GO")

    def test_at_exact_start_of_15min_blackout_is_rejected(self):
        with self.assertRaisesRegex(InputError, "blackout"):
            forecasts.verify_archive(wrap(
                recorded_at_utc_local_clock_unattested=
                    "2026-11-20T14:45:00Z"), asof_utc=ASOF)

    def test_later_10min_pre_release_forged_rehash_is_rejected(self):
        with self.assertRaisesRegex(InputError, "blackout"):
            forecasts.verify_archive(wrap(
                recorded_at_utc_local_clock_unattested=
                    "2026-11-20T14:50:00Z"),
                asof_utc="2026-11-20T14:51:00Z")

    def test_after_release_rejected(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(
                recorded_at_utc_local_clock_unattested=
                    "2026-11-20T15:01:00Z"),
                asof_utc="2026-11-20T15:02:00Z")

    def test_after_capture_asof_rejected(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(), asof_utc="2026-11-20T14:40:00Z")

    def test_forecast_source_published_after_capture_rejected(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(
                source_published_at_utc_self_reported="2026-11-20T14:46:00Z"),
                asof_utc=ASOF)

    def test_forged_demo_order_permission_is_rejected_even_with_valid_sha(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(
                demo_orders_permitted=True), asof_utc=ASOF)

    def test_forged_independent_publisher_time_attestation_rejected(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(
                published_at_independently_attested=True), asof_utc=ASOF)

    def test_forged_automatic_polling_rejected(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(
                forecast_poll_or_web_search_performed=True), asof_utc=ASOF)

    def test_tampered_excerpt_hash_rejected(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(
                source_text_excerpt="Not the original forecast"), asof_utc=ASOF)

    def test_invalid_runbook_unattested_flag_is_not_enough_to_clear_no_go(self):
        with self.assertRaises(InputError):
            forecasts.verify_archive(wrap(
                real_orders_permitted=True), asof_utc=ASOF)


if __name__ == "__main__":
    unittest.main()
