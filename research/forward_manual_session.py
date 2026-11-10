"""FWD-048/049/050: audit a bounded manual three-pair observation session.

Requires existing immutable operator-selected capture folders from FWD-043.
Never starts MT4, polls a terminal, schedules work, imports a trading journal,
runs external commands or sends orders. A valid local session is never GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research.forward_manual_handoff import verify_capture
from research.offline_backtest import InputError, PAIRS, timestamp

SCHEMA = "fx_forward_manual_session_v1"
MAX_CAPTURES = 1500
LEVEL1_SECONDS = 60
LEVEL2_SECONDS = 600


def assess(folders: list[Path], *, asof_utc: str,
           gap_seconds: int = 300) -> dict:
    at = timestamp(asof_utc)
    if (type(folders) is not list or not 1 <= len(folders) <= MAX_CAPTURES or
            type(gap_seconds) is not int or not 1 <= gap_seconds <= 86400):
        raise InputError("invalid session limits")
    pairs = {p: [] for p in PAIRS}
    seen_ids = set()
    seen_folders = set()
    for path in folders:
        if not isinstance(path, Path):
            raise InputError("invalid local capture path")
        resolved = path.resolve(strict=True)
        if resolved in seen_folders:
            raise InputError("repeated folder")
        seen_folders.add(resolved)
        item = verify_capture(path)
        captured = timestamp(item["asof_utc"])
        observed = timestamp(item["observed_at_utc"])
        if captured > at or observed > at:
            raise InputError("future capture in session")
        cid = item["capture_id"]
        if cid in seen_ids:
            raise InputError("reused capture ID")
        seen_ids.add(cid)
        pair = item["pair"]
        if pair not in pairs:
            raise InputError("unexpected pair")
        pairs[pair].append((observed, captured, item["csv_sha256"], cid))
    findings = []
    timeline = {}
    for pair in PAIRS:
        seq = sorted(pairs[pair], key=lambda r: (r[0], r[1], r[3]))
        breaks = []
        repeats = []
        previous = None
        for tick in seq:
            if previous:
                interval = (tick[0] - previous[0]).total_seconds()
                if interval <= 0:
                    repeats.append(tick[3])
                elif interval > gap_seconds:
                    breaks.append({"prior_capture_id": previous[3],
                                   "capture_id": tick[3],
                                   "seconds": interval})
                if tick[2] == previous[2]:
                    repeats.append(tick[3])
            previous = tick
        age = (at - seq[-1][0]).total_seconds() if seq else None
        if age is None:
            level = "LEVEL2"
            findings.append("NO_CAPTURES_" + pair.replace("/", "_"))
        elif age >= LEVEL2_SECONDS:
            level = "LEVEL2"
        elif age >= LEVEL1_SECONDS:
            level = "LEVEL1"
        else:
            level = "NONE"
        if breaks:
            findings.append("GAP_" + pair.replace("/", "_"))
        if repeats:
            findings.append("REPEAT_" + pair.replace("/", "_"))
        if level != "NONE":
            findings.append(level + "_INACTIVITY_" + pair.replace("/", "_"))
        timeline[pair] = {
            "capture_count": len(seq),
            "latest_observed_at_utc": (
                seq[-1][0].isoformat().replace("+00:00", "Z") if seq else None),
            "last_capture_id": seq[-1][3] if seq else None,
            "quote_age_seconds": age,
            "research_interruption_level": level,
            "gap_count": len(breaks),
            "gaps": breaks[:100],
            "replay_or_duplicate_capture_ids": sorted(set(repeats))[:100],
            "source_authenticated": False,
            "broker_executable_quote": False,
        }
    findings.extend(("BROKER_ACCOUNT_NOT_AUTHENTICATED",
                     "NO_INDEPENDENT_TICK_SERVER_CLOCK",
                     "NO_REAL_LONG_RUNNING_CAPTURE_VERIFICATION",
                     "DATA_LICENSE_NOT_VERIFIED"))
    return {
        "schema": SCHEMA,
        "status": "MANUAL_SESSION_RESEARCH_HOLD_NO_GO",
        "asof_utc": asof_utc,
        "capture_count": len(folders),
        "by_pair": timeline,
        "blocking_reasons": sorted(set(findings)),
        "mt4_terminal_access_performed": False,
        "continuous_automated_collection_enabled": False,
        "restart_automatically_permitted": False,
        "demo_order_execution_enabled": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def _load_manifest(manifest: dict, directory: Path) -> list[Path]:
    if (type(manifest) is not dict or
            set(manifest) != {"schema", "capture_folders"} or
            manifest["schema"] != SCHEMA or
            type(manifest["capture_folders"]) is not list or
            not 1 <= len(manifest["capture_folders"]) <= MAX_CAPTURES):
        raise InputError("invalid session manifest")
    folders = []
    for name in manifest["capture_folders"]:
        if (type(name) is not str or
                not __import__("re").fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", name)):
            raise InputError("unsafe local capture name")
        folders.append(directory / name)
    return folders


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Audit existing manual MT4 observations; no MT4 IO")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--captures-dir", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if (a.out.exists() or not a.out.parent.is_dir()
                or not a.captures_dir.is_dir() or
                not a.manifest.is_file() or
                a.manifest.stat().st_size > 200000):
            raise InputError("unsafe session input/output path")
        doc = json.loads(a.manifest.read_text(encoding="utf-8-sig"))
        report = assess(_load_manifest(doc, a.captures_dir),
                        asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "capture_count": report["capture_count"],
            "blocking_reasons": report["blocking_reasons"],
            "runtime_go_no_go": "NO_GO", "real_orders_permitted": False}))
        return 0
    except (InputError, OSError, ValueError, TypeError,
            KeyError, UnicodeError, ArithmeticError):
        print(json.dumps({"status": "FAIL_CLOSED",
                          "reason": "INVALID_MANUAL_OBSERVATION_SESSION",
                          "runtime_go_no_go": "NO_GO",
                          "safety_hold_latched": True,
                          "real_orders_permitted": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
