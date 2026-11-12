"""FWD-245..252 synthetic one-shot offline forward macro readiness board."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from research import forward_bls_calendar as bls
from research import forward_macro_pre_release_capture as forecast
from research import forward_macro_integrated_readiness as board
from research import forward_observation as obs
from research.forward_mt4_v2_quote import COLUMNS
from research.offline_backtest import InputError

ASOF="2026-11-10T08:00:00Z"
PAIRS={"USDJPY":"USD/JPY","EURJPY":"EUR/JPY","EURUSD":"EUR/USD"}


def prices(root):
    path=root/"quotes";path.mkdir()
    start=datetime(2026,11,10,6,0,tzinfo=timezone.utc)
    for minute in range(4):
        now=start+timedelta(minutes=minute)
        obs_utc=now.strftime("%Y-%m-%dT%H:%M:%SZ")
        suffix=now.strftime("%Y%m%d_%H%M%S")
        srv=(now+timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
        tick=(now+timedelta(hours=2,seconds=-1)).strftime(
            "%Y-%m-%dT%H:%M:%S")
        usdbid=150+0.01*minute
        for sym,pair in PAIRS.items():
            bid,ask= (
                (f"{usdbid:.3f}",f"{usdbid+0.005:.3f}")
                if pair=="USD/JPY" else
                ("170.000","170.010") if pair=="EUR/JPY" else
                ("1.12000","1.12005"))
            to_jpy=f"{usdbid:.5f}" if pair=="EUR/USD" else "1.00000"
            fields=[obs_utc,pair,bid,ask,to_jpy,tick,srv,"1","DEMO",
                    "MANUAL_MT4_DEMO_V2_UNVERIFIED"]
            (path/f"FxFwdV3_{sym}_{suffix}.csv").write_text(
                ",".join(COLUMNS)+"\n"+",".join(fields)+"\n",
                encoding="utf-8")
    return path


def calendar():
    xml=(b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
         b"BEGIN:VEVENT\r\nDTSTART:20261110T090000Z\r\n"
         b"SUMMARY:Consumer Price Index\r\n"
         b"END:VEVENT\r\nEND:VCALENDAR\r\n")
    return bls.parse_calendar(xml,asof_utc=ASOF)


def archive(calendar_obj):
    t="Research-only synthetic 2.1 percent"
    sub={
        "schema":forecast.FORM,
        "event_title":"Consumer Price Index",
        "scheduled_at_utc":"2026-11-10T09:00:00Z",
        "pair":"USD/JPY",
        "unit":"percent",
        "value":"2.1",
        "source_text":t,
        "source_sha256":hashlib.sha256(t.encode()).hexdigest(),
        "source_url":"https://example.org/consensus",
        "source_published_at_utc":"2026-11-10T07:00:00Z",
    }
    rec=forecast.validate_submission(sub,calendar_obj,captured_at_utc=ASOF)
    return {"record":rec,"record_sha256":forecast.sha(rec)}


class IntegratedForwardBoardTests(unittest.TestCase):
    def test_existing_quote_session_has_no_invented_macro_news(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);d=prices(root);store=root/"journal"
            obs.initialize(store,"empty_macro_research",
                           now=datetime.fromisoformat(
                               ASOF.replace("Z","+00:00")))
            r=board.inspect([("s1",d)],asof_utc=ASOF,store=store)
            self.assertEqual(r["price_csv_count"],12)
            self.assertEqual(r["complete_cycle_count"],4)
            self.assertEqual(r["macro_event_count"],0)
            self.assertFalse(r["calendar_supplied"])
            self.assertFalse(r["pre_release_forecast_archive_supplied"])
            self.assertIn("ARCHIVE_POINT_IN_TIME_CONSENSUS_BEFORE_BLACKOUT",
                          r["next_research_actions"])
            self.assertEqual(r["API_calls_this_run"],0)
            self.assertFalse(r["real_orders_permitted"])

    def test_calendar_and_forecast_archive_consistent(self):
        with tempfile.TemporaryDirectory() as t:
            d=prices(Path(t));cal=calendar()
            r=board.inspect([("s1",d)],asof_utc=ASOF,
                            calendar=cal,forecast_archive=archive(cal))
            self.assertTrue(r["forecast_archive_matches_current_schedule"])
            self.assertEqual(r["scheduled_bls_event_count"],1)
            self.assertFalse(r["calendar_current_within_24h"] is False)
            self.assertEqual(r["descriptive_post_review_marks"],0)
            self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_calendar_revision_does_not_silently_accept_old_forecast(self):
        with tempfile.TemporaryDirectory() as t:
            d=prices(Path(t));cal=calendar()
            a=archive(cal)
            changed=dict(cal);changed["calendar_sha256"]="a"*64
            r=board.inspect([("s1",d)],asof_utc=ASOF,
                            calendar=changed,forecast_archive=a)
            self.assertFalse(r["forecast_archive_matches_current_schedule"])
            self.assertIn("CONSENSUS_ARCHIVE_CALENDAR_IDENTITY_CHANGED",
                          r["unresolved_holds"])

    def test_archive_without_schedule_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            d=prices(Path(t));cal=calendar()
            with self.assertRaises(InputError):
                board.inspect([("s1",d)],asof_utc=ASOF,
                              forecast_archive=archive(cal))

    def test_stale_calendar_flag_is_not_safe_resume(self):
        with tempfile.TemporaryDirectory() as t:
            d=prices(Path(t));cal=calendar()
            r=board.inspect([("s1",d)],
                            asof_utc="2026-11-11T09:00:00Z",
                            calendar=cal)
            self.assertFalse(r["calendar_current_within_24h"])
            self.assertIn("RECHECK_BLS_CALENDAR_STALE",
                          r["next_research_actions"])
            self.assertFalse(r["demo_orders_permitted"])

    def test_one_shot_cli_write_only_outside_quote_folder(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);d=prices(root)
            out=root/"board.json"
            args=["--session",f"s1={d}","--asof-utc",ASOF,
                  "--out",str(out)]
            self.assertEqual(board.main(args),0)
            self.assertEqual(board.main(args),2)
            self.assertEqual(json.loads(out.read_text())["API_calls_this_run"],0)


if __name__=="__main__":
    unittest.main()
