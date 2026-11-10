"""FWD-040/041: prepare a complete immutable local receipt-chain manifest.

Read-only input validation; output must not pre-exist. Does not create a
Windows task, recover a paused trading session, or access MT4/broker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from research.forward_receipt_chain import SCHEMA, MAX_RECEIPTS, MAX_FILE_BYTES, verify_chain
from research.offline_backtest import InputError

NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}[.]json$")


def build(folder: Path, filenames: list[str]) -> tuple[dict, dict]:
    if type(filenames) is not list or not 1 <= len(filenames) <= MAX_RECEIPTS:
        raise InputError("invalid manifest size")
    seen = set()
    entries = []
    receipts = []
    for name in filenames:
        if type(name) is not str or not NAME.fullmatch(name) or name in seen:
            raise InputError("unsafe repeated filename")
        seen.add(name)
        file = folder / name
        if not file.is_file() or not 0 < file.stat().st_size <= MAX_FILE_BYTES:
            raise InputError("missing/oversized receipt")
        raw = file.read_bytes()
        obj = json.loads(raw.decode("utf-8-sig"))
        if type(obj) is not dict:
            raise InputError("invalid receipt payload")
        entries.append({
            "filename": name, "sha256": hashlib.sha256(raw).hexdigest()})
        receipts.append(obj)
    # Validate the entire chain before writing the manifest.
    result = verify_chain(receipts)
    return {"schema": SCHEMA, "receipts": entries}, result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build verified local receipt manifest, NO_GO")
    p.add_argument("--receipts-dir", required=True, type=Path)
    p.add_argument("--receipt", action="append", required=True)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        if a.out.exists() or not a.out.parent.is_dir() or not a.receipts_dir.is_dir():
            raise InputError("output collision or missing directory")
        manifest, checked = build(a.receipts_dir, a.receipt)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(json.dumps({"status": "RECEIPT_MANIFEST_RESEARCH_NO_GO",
                          "receipt_count": checked["receipt_count"],
                          "gap_count": checked["oversized_gap_count"],
                          "runtime_go_no_go": "NO_GO",
                          "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, TypeError, ValueError, KeyError, UnicodeError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "RECEIPT_MANIFEST_CREATION_BLOCKED",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
