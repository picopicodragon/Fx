"""FWD-036: manifest construction for reproducible offline evidence bundles.

This is local-file hashing, not provenance verification. No network/MT4/
orders. An existing output is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research.forward_offline_batch import SCHEMA, INPUTS, STATUSES, _load
from research.offline_backtest import InputError, timestamp


def build(reports_dir: Path, names: dict, *, asof_utc: str) -> dict:
    cutoff = timestamp(asof_utc)
    if type(names) is not dict or set(names) != set(INPUTS):
        raise InputError("incomplete bundle")
    manifest = {}
    seen = set()
    for key in INPUTS:
        filename = names[key]
        if (type(filename) is not str or
                not __import__("re").fullmatch(
                    r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\.json", filename) or
                filename in seen):
            raise InputError("duplicate or invalid filename")
        seen.add(filename)
        report, digest = _load(reports_dir / filename)
        if (report.get("status") != STATUSES[key] or
                report.get("runtime_go_no_go") != "NO_GO" or
                report.get("safety_hold_latched") is not True or
                report.get("real_orders_permitted") is not False):
            raise InputError("report not an approved research-only format")
        if "asof_utc" in report and timestamp(report["asof_utc"]) > cutoff:
            raise InputError("report from future")
        manifest[key] = {"filename": filename, "sha256": digest}
    return {"schema": SCHEMA, "asof_utc": asof_utc, "artifacts": manifest}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Offline FWD research manifest construction")
    p.add_argument("--reports-dir", required=True, type=Path)
    p.add_argument("--asof-utc", required=True)
    for key in INPUTS:
        p.add_argument("--" + key, required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if (args.out.exists() or not args.out.parent.is_dir()
                or not args.reports_dir.is_dir()):
            raise InputError("unsafe paths")
        manifest = build(args.reports_dir,
                         {key: getattr(args, key) for key in INPUTS},
                         asof_utc=args.asof_utc)
        with args.out.open("x", encoding="utf-8") as out:
            json.dump(manifest, out, ensure_ascii=False, indent=2)
        print(json.dumps({"status": "FORWARD_MANIFEST_CREATED_NO_GO",
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, TypeError, OSError, ValueError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_RESEARCH_MANIFEST_INPUTS",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
