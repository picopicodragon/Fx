"""FWD-881..960: real saved event/consensus source files, fail-closed tests."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_regional_source_intake as intake
from research import forward_global_macro_evidence as macro
from research.offline_backtest import InputError

ASOF = "2026-11-13T04:00:00Z"
OBSERVED = "2026-11-13T03:00:00Z"
EVENT = "2026-11-20T15:00:00Z"
CAL = "Original calendar: Consumer Price Index released Nov 20 at 10 AM ET."
FC = "Original market consensus forecast 2.7 percent before release."


def fixture(root: Path, *, forecasts=True, currency="USD",
            event_time=EVENT, observed=OBSERVED):
    cal = root / "calendar.txt"
    cal.write_text(CAL, encoding="utf-8")
    fore = root / "forecast.txt"
    fore.write_text(FC, encoding="utf-8")
    urls = {
        "USD": "https://www.bls.gov/schedule/news_release/cpi.htm",
        "EUR": "https://www.ecb.europa.eu/press/calendars/",
        "JPY": "https://www.boj.or.jp/en/mopo/",
    }
    sources = [{
        "source_id": "official",
        "source_kind": "OFFICIAL_SCHEDULE",
        "filename": "calendar.txt",
        "source_url": urls[currency],
        "sha256": hashlib.sha256(CAL.encode()).hexdigest(),
        "published_at_utc": "2026-11-12T12:00:00Z",
        "captured_at_utc": "2026-11-13T02:00:00Z",
    }]
    if forecasts:
        sources.append({
            "source_id": "consensus",
            "source_kind": "PRE_RELEASE_CONSENSUS",
            "filename": "forecast.txt",
            "source_url": "https://market.example.org/survey",
            "sha256": hashlib.sha256(FC.encode()).hexdigest(),
            "published_at_utc": "2026-11-12T15:00:00Z",
            "captured_at_utc": "2026-11-13T02:30:00Z",
        })
    manifest = {
        "schema": intake.SCHEMA,
        "observed_at_utc": observed,
        "horizon_days": 14,
        "sources": sources,
        "events": [{
            "event_id": currency.lower() + "-cpi-20261120",
            "currency": currency,
            "event_type": "INFLATION",
            "title": "Consumer Price Index",
            "scheduled_at_utc": event_time,
            "calendar_source_id": "official",
            "calendar_excerpt": CAL,
            "consensus": ({
                "source_id": "consensus",
                "excerpt": FC,
                "value": "2.7",
                "unit": "percent",
            } if forecasts else None),
        }],
    }
    path = root / "original_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def mutate(path: Path, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data), encoding="utf-8")


class RawSourceIntakeTests(unittest.TestCase):
    def test_official_calendar_and_consensus_bytes_to_global_macro_contract(self):
        with tempfile.TemporaryDirectory() as td:
            path = fixture(Path(td))
            payload, report = intake.load(path, asof_utc=ASOF)
        self.assertEqual(payload["schema"], macro.SCHEMA)
        self.assertEqual(report["source_file_count"], 2)
        self.assertEqual(report["event_observations_count"], 1)
        self.assertEqual(report["pre_release_consensus_count"], 1)
        self.assertEqual(report["missing_pre_release_consensus_count"], 0)
        self.assertEqual(payload["events"][0]["calendar_source"][
            "source_sha256"], hashlib.sha256(CAL.encode()).hexdigest())
        self.assertEqual(payload["events"][0]["consensus"][
            "source"]["source_sha256"],
            hashlib.sha256(FC.encode()).hexdigest())
        self.assertFalse(report[
            "source_hosts_genuine_origin_authenticated"])
        self.assertFalse(report[
            "market_consensus_independently_verified"])
        self.assertFalse(report["real_orders_permitted"])
        self.assertFalse(report["demo_orders_permitted"])
        self.assertTrue(report["safety_hold_latched"])

    def test_eur_and_jpy_official_calendars_accepted_with_no_consensus(self):
        for cur in ("EUR", "JPY"):
            with self.subTest(currency=cur):
                with tempfile.TemporaryDirectory() as td:
                    p = fixture(Path(td), forecasts=False, currency=cur)
                    data, report = intake.load(p, asof_utc=ASOF)
                self.assertEqual(report["source_file_count"], 1)
                self.assertEqual(report["missing_pre_release_consensus_count"], 1)
                self.assertEqual(data["events"][0]["currency"], cur)
                self.assertEqual(report["runtime_go_no_go"], "NO_GO")

    def test_forecast_missing_never_invented(self):
        with tempfile.TemporaryDirectory() as td:
            path = fixture(Path(td), forecasts=False)
            data, report = intake.load(path, asof_utc=ASOF)
        self.assertIsNone(data["events"][0]["consensus"])
        self.assertEqual(report["pre_release_consensus_count"], 0)
        self.assertFalse(report["complete_fx_calendar_coverage_verified"])

    def test_calendar_original_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = fixture(root)
            (root/"calendar.txt").write_text(CAL+" ALTERED")
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_forecast_original_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = fixture(root)
            (root/"forecast.txt").write_text(FC+" ALTERED")
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_calendar_excerpt_must_be_from_exact_original(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["events"][0].__setitem__(
                "calendar_excerpt", "invented official timestamp"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_consensus_excerpt_must_be_from_exact_original(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["events"][0]["consensus"].__setitem__(
                "excerpt", "invented consensus 2.7"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_consensus_number_must_be_in_actual_excerpt(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["events"][0]["consensus"].__setitem__(
                "value", "9.3"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_number_substring_in_12_7_must_not_match_2_7(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=fixture(root)
            raw="Official surveyed market forecast 12.7 percent."
            (root/"forecast.txt").write_text(raw)
            mutate(p, lambda d: (
                d["sources"][1].__setitem__("sha256", hashlib.sha256(
                    raw.encode()).hexdigest()),
                d["events"][0]["consensus"].__setitem__("excerpt", raw)))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_wrong_currency_official_host_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td), currency="USD")
            mutate(p, lambda d: d["sources"][0].__setitem__(
                "source_url", "https://www.ecb.europa.eu/press/calendar.html"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_official_schedule_cannot_come_from_untrusted_website(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["sources"][0].__setitem__(
                "source_url", "https://bls.gov.evil.example/test"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_http_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["sources"][0].__setitem__(
                "source_url", "http://www.bls.gov/calendar"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_cannot_claim_forecast_source_as_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["events"][0].__setitem__(
                "calendar_source_id", "consensus"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_15min_pre_release_forecast_capture_boundary_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td), observed="2026-11-20T14:50:01Z")
            mutate(p, lambda d: d["sources"][1].__setitem__(
                "captured_at_utc", "2026-11-20T14:45:00Z"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc="2026-11-20T14:50:01Z")

    def test_too_late_official_calendar_observation_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td), observed="2026-11-20T15:00:00Z")
            with self.assertRaises(InputError):
                intake.load(p, asof_utc="2026-11-20T15:01:00Z")

    def test_capture_claim_after_observation_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["sources"][0].__setitem__(
                "captured_at_utc", "2026-11-14T03:00:00Z"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_duplicate_original_file_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["sources"][1].__setitem__(
                "filename", "calendar.txt"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_unused_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["events"][0].__setitem__(
                "consensus", None))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_path_traversal_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["sources"][0].__setitem__(
                "filename", "../outside.txt"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_absolute_source_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["sources"][0].__setitem__(
                "filename", str(Path(td)/"calendar.txt")))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_future_manifest_observation_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d.__setitem__(
                "observed_at_utc", "2026-11-15T03:00:00Z"))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_symlink_original_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=fixture(root)
            (root/"calendar.txt").rename(root/"real.txt")
            try:
                (root/"calendar.txt").symlink_to(root/"real.txt")
            except (OSError, NotImplementedError):
                self.skipTest("host forbids symlinks")
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_unknown_event_attribute_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = fixture(Path(td))
            mutate(p, lambda d: d["events"][0].__setitem__(
                "real_orders_permitted", True))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_duplicate_event_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=fixture(Path(td))
            mutate(p, lambda d: d["events"].append(
                copy.deepcopy(d["events"][0])))
            with self.assertRaises(InputError):
                intake.load(p, asof_utc=ASOF)

    def test_cli_no_output_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=fixture(root)
            before={x.name:x.read_bytes() for x in root.iterdir()}
            with patch("sys.stdout", new_callable=io.StringIO) as out:
                code=intake.main(["--manifest", str(p), "--asof-utc",ASOF])
            self.assertEqual(code,0)
            self.assertEqual(
                {x.name:x.read_bytes() for x in root.iterdir()},before)
            self.assertFalse(json.loads(out.getvalue())["demo_orders_permitted"])

    def test_cli_export_valid_external_interchange_not_orders(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            originals=root/"original"
            originals.mkdir()
            p=fixture(originals)
            out=root/"external.json"
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                code=intake.main([
                    "--manifest",str(p), "--asof-utc",ASOF,
                    "--emit-observations", str(out)])
            self.assertEqual(code,0)
            data=json.loads(out.read_text(encoding="utf-8"))
            macro_report=macro.inspect_observations(data, asof_utc=ASOF)
            self.assertEqual(macro_report[
                "external_event_observations_supplied"],1)
            self.assertFalse(macro_report["real_orders_permitted"])
            self.assertEqual(json.loads(stream.getvalue())[
                "network_calls_this_run"],0)

    def test_cli_cannot_overwrite_observation_export(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            orig=root/"original"
            orig.mkdir()
            p=fixture(orig)
            out=root/"export.json"
            out.write_text("keep")
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                code=intake.main([
                    "--manifest",str(p),"--asof-utc",ASOF,
                    "--emit-observations",str(out)])
            self.assertEqual(code,2)
            self.assertEqual(out.read_text(),"keep")
            self.assertEqual(json.loads(stream.getvalue())[
                "runtime_go_no_go"],"NO_GO")

    def test_cli_never_writes_into_source_original_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=fixture(root)
            out=root/"export.json"
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                code=intake.main([
                    "--manifest",str(p),"--asof-utc",ASOF,
                    "--emit-observations",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertIn("FAIL_CLOSED_NO_GO",stream.getvalue())

    def test_cli_invalid_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=fixture(root)
            p.write_text("{not valid json")
            with patch("sys.stdout", new_callable=io.StringIO) as stream:
                code=intake.main(["--manifest",str(p),"--asof-utc",ASOF])
            self.assertEqual(code,2)
            self.assertFalse(json.loads(stream.getvalue())["real_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
