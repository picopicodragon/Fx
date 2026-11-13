"""FWD-1041..1120: one-shot real local original package and fail-closed cases."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research import forward_regional_original_bundle as pack
from research import forward_regional_source_intake as intake
from research.offline_backtest import InputError

OBS="2026-11-13T03:00:00Z"
ASOF="2026-11-13T04:00:00Z"
EVENT="2026-11-20T15:00:00Z"
SCHEDULE="Official test release: CPI event at Nov 20, 10 AM ET (unverified)."
SURVEY="Survey: consensus 2.7 percent before release (unverified)."


def make(root: Path, *, forecasts=True):
    original=root/"source_inputs"
    original.mkdir()
    (original/"calendar.txt").write_text(SCHEDULE,encoding="utf-8")
    (original/"survey.txt").write_text(SURVEY,encoding="utf-8")
    sources=[{
        "source_id":"official",
        "source_kind":"OFFICIAL_SCHEDULE",
        "source_file":"calendar.txt",
        "source_url":"https://www.bls.gov/schedule/news_release/",
        "published_at_utc":"2026-11-12T12:00:00Z",
        "captured_at_utc":"2026-11-13T02:00:00Z",
    }]
    if forecasts:
        sources.append({
            "source_id":"survey",
            "source_kind":"PRE_RELEASE_CONSENSUS",
            "source_file":"survey.txt",
            "source_url":"https://research.example.org/forecast",
            "published_at_utc":"2026-11-12T20:00:00Z",
            "captured_at_utc":"2026-11-13T02:20:00Z",
        })
    spec={
        "schema":pack.SCHEMA,
        "observed_at_utc":OBS,
        "horizon_days":14,
        "sources":sources,
        "events":[{
            "event_id":"cpi-20261120",
            "currency":"USD",
            "event_type":"INFLATION",
            "title":"Consumer Price Index",
            "scheduled_at_utc":EVENT,
            "calendar_source_id":"official",
            "calendar_excerpt":SCHEDULE,
            "consensus":({
                "source_id":"survey",
                "excerpt":SURVEY,
                "value":"2.7",
                "unit":"percent",
            } if forecasts else None),
        }],
    }
    path=original/"request.json"
    path.write_text(json.dumps(spec,ensure_ascii=False),encoding="utf-8")
    out_parent=root/"packages"
    out_parent.mkdir()
    return path,out_parent/"bundle"


def mutate(spec:Path,fn):
    obj=json.loads(spec.read_text(encoding="utf-8"))
    fn(obj)
    spec.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")


def command(args):
    with patch("sys.stdout",new_callable=io.StringIO) as output:
        code=pack.main(args)
    return code,json.loads(output.getvalue())


class SavedOriginalPackagingTests(unittest.TestCase):
    def test_preflight_does_not_write_any_file(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            before={p.name:p.read_bytes() for p in req.parent.iterdir()}
            code,report=command(["--request",str(req),"--asof-utc",ASOF])
            self.assertEqual(code,0)
            self.assertEqual(report["source_file_count"],2)
            self.assertEqual(report["event_evidence_count"],1)
            self.assertEqual(report["pre_release_consensus_evidence_count"],1)
            self.assertEqual(report["files_written_this_run"],0)
            self.assertFalse(out.exists())
            self.assertEqual({p.name:p.read_bytes() for p in req.parent.iterdir()},
                             before)
            self.assertFalse(report["real_orders_permitted"])
            self.assertFalse(report["demo_orders_permitted"])

    def test_real_bytes_copied_with_computed_hash_and_verified_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            code,r=command(["--request",str(req),"--asof-utc",ASOF,
                            "--out-dir",str(out)])
            self.assertEqual(code,0)
            self.assertEqual(r["status"],
                             "ORIGINAL_PACKAGE_SAVED_AND_RECHECKED_HOLD_NO_GO")
            self.assertEqual(r["files_written_this_run"],3)
            self.assertTrue(r["output_manifest_written_last"])
            manifest=json.loads((out/pack.MANIFEST).read_text())
            self.assertEqual([x["filename"] for x in manifest["sources"]],
                             ["original_001.txt","original_002.txt"])
            self.assertEqual((out/"original_001.txt").read_text(),SCHEDULE)
            self.assertEqual((out/"original_002.txt").read_text(),SURVEY)
            self.assertEqual(manifest["sources"][0]["sha256"],
                             hashlib.sha256(SCHEDULE.encode()).hexdigest())
            derived,report=intake.load(out/pack.MANIFEST,asof_utc=ASOF)
            self.assertEqual(report["source_file_count"],2)
            self.assertEqual(derived["events"][0]["consensus"]["value"],"2.7")
            self.assertFalse(report["source_hosts_genuine_origin_authenticated"])
            self.assertFalse(r["source_authenticity_independently_verified"])
            self.assertEqual(r["runtime_go_no_go"],"NO_GO")

    def test_new_bundle_never_changes_original_files(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            originals={p.name:p.read_bytes() for p in req.parent.iterdir()}
            pack.save(req,out,asof_utc=ASOF)
            self.assertEqual({p.name:p.read_bytes() for p in req.parent.iterdir()},
                             originals)

    def test_two_invocations_never_overwrite_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            self.assertEqual(command(["--request",str(req),
                         "--asof-utc",ASOF,"--out-dir",str(out)])[0],0)
            manifest=(out/pack.MANIFEST).read_bytes()
            code,r=command(["--request",str(req),
                             "--asof-utc",ASOF,"--out-dir",str(out)])
            self.assertEqual(code,2)
            self.assertEqual(manifest,(out/pack.MANIFEST).read_bytes())
            self.assertFalse(r["real_orders_permitted"])

    def test_missing_forecast_never_backfilled(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td),forecasts=False)
            result=pack.save(req,out,asof_utc=ASOF)
            derived,_=intake.load(out/pack.MANIFEST,asof_utc=ASOF)
            self.assertEqual(result["pre_release_consensus_evidence_count"],0)
            self.assertIsNone(derived["events"][0]["consensus"])
            self.assertEqual(result["auto_filled_event_or_forecast_count"],0)

    def test_source_file_absence_fails_closed_before_out_created(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            (req.parent/"calendar.txt").unlink()
            code,r=command(["--request",str(req),"--asof-utc",ASOF,
                            "--out-dir",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertEqual(r["status"],"ORIGINAL_PACKAGE_FAIL_CLOSED_NO_GO")

    def test_original_excerpt_not_in_actual_file_fails_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["events"][0].__setitem__(
                "calendar_excerpt","invented source text"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_wrong_consensus_number_fails_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["events"][0]["consensus"].__setitem__(
                "value","9.3"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_forecast_at_15min_cutoff_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:(
                d.__setitem__("observed_at_utc","2026-11-20T14:50:00Z"),
                d["sources"][1].__setitem__(
                    "captured_at_utc","2026-11-20T14:45:00Z")))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc="2026-11-20T14:50:00Z")
            self.assertFalse(out.exists())

    def test_captured_after_future_event_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:(
                d.__setitem__("observed_at_utc","2026-11-20T15:10:00Z"),
                d["sources"][0].__setitem__(
                    "captured_at_utc","2026-11-20T15:02:00Z")))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc="2026-11-20T15:10:00Z")
            self.assertFalse(out.exists())

    def test_source_published_after_capture_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["sources"][0].__setitem__(
                "published_at_utc","2026-11-13T02:30:00Z"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_future_observed_at_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d.__setitem__(
                "observed_at_utc","2026-11-14T03:00:00Z"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_wrong_official_host_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["sources"][0].__setitem__(
                "source_url","https://www.ecb.europa.eu/press/"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_unknown_source_kind_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["sources"][0].__setitem__(
                "source_kind","LIVE_TRADE_SIGNAL"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_source_path_outside_input_via_traversal_can_be_explicit(self):
        # Explicit operator-chosen relative paths work, but never
        # blindly glob an arbitrary folder.
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            req,out=make(root)
            external=root/"independent_capture"
            external.mkdir()
            target=external/"independent_capture.txt"
            target.write_text(SCHEDULE)
            mutate(req,lambda d:d["sources"][0].__setitem__(
                "source_file","../independent_capture/independent_capture.txt"))
            report=pack.save(req,out,asof_utc=ASOF)
            self.assertEqual(report["source_file_count"],2)
            self.assertFalse(report["source_authenticity_independently_verified"])

    def test_duplicate_original_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["sources"][1].__setitem__(
                "source_file","calendar.txt"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_unknown_source_path_glob_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["sources"][0].__setitem__(
                "source_file","*.txt"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_unused_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["events"][0].__setitem__("consensus",None))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_source_file_same_as_request_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["sources"][0].__setitem__(
                "source_file","request.json"))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_unknown_event_attribute_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["events"][0].__setitem__(
                "demo_orders_permitted",True))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_output_inside_original_input_folder_forbidden(self):
        with tempfile.TemporaryDirectory() as td:
            req,_=make(Path(td))
            out=req.parent/"bundle"
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_missing_parent_dir_refused(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            missing=out/"nested_bundle"
            with self.assertRaises(InputError):
                pack.save(req,missing,asof_utc=ASOF)
            self.assertFalse(missing.exists())

    def test_binary_or_oversized_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            (req.parent/"calendar.txt").write_bytes(b"\x00" + b"x"*100)
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)
            self.assertFalse(out.exists())

    def test_source_symlink_refused_when_supported(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            raw=req.parent/"calendar.txt"
            raw.rename(req.parent/"real.txt")
            try:
                raw.symlink_to(req.parent/"real.txt")
            except (OSError,NotImplementedError):
                self.skipTest("host prohibits symlinks")
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_duplicate_event_identity_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["events"].append(
                copy.deepcopy(d["events"][0])))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_request_schema_unknown_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d.__setitem__("live_order",True))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_100k_request_cap_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            req.write_bytes(b"x"*(pack.MAX_SPEC+1))
            with self.assertRaises(InputError):
                pack.save(req,out,asof_utc=ASOF)

    def test_no_implicit_network_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            with patch("urllib.request.urlopen",
                       side_effect=AssertionError("network unexpected")):
                result=pack.save(req,out,asof_utc=ASOF)
            self.assertEqual(result["network_calls_this_run"],0)

    def test_cli_unknown_bad_source_fails_with_no_go(self):
        with tempfile.TemporaryDirectory() as td:
            req,out=make(Path(td))
            mutate(req,lambda d:d["sources"][0].__setitem__(
                "source_url","http://evil.invalid"))
            code,response=command([
                "--request",str(req),"--asof-utc",ASOF,
                "--out-dir",str(out)])
            self.assertEqual(code,2)
            self.assertFalse(out.exists())
            self.assertEqual(response["runtime_go_no_go"],"NO_GO")
            self.assertFalse(response["demo_orders_permitted"])


if __name__ == "__main__":
    unittest.main()
