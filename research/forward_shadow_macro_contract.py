"""FWD-126..132: two-stage macro-hypothesis provenance contract (offline).

All metadata is user-supplied and unauthenticated. No LLM call or macro
research is performed. 'APPROVED' means *self-reported review disposition*,
never live-trading authorization or independent evidence attestation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from research.offline_backtest import InputError, timestamp

SCHEMA = "fx_fwd_offline_macro_hypothesis_contract_v1"
REQUIRED = frozenset({
    "hypothesis_id", "pair", "direction", "source_records",
    "constructed_at_utc", "reviewed_at_utc", "decision_at_utc",
    "builder_id", "reviewer_id", "review_status",
    "macro_thesis", "counter_thesis", "expected_catalyst",
    "invalidation_conditions",
})
SOURCE_FIELDS = frozenset({
    "source_label", "published_at_utc", "accessed_at_utc", "content_sha256",
})
PAIRS = ("USD/JPY", "EUR/JPY", "EUR/USD")
REVIEWS = ("APPROVED", "REVISION", "REJECTED", "PENDING")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_DOCUMENT = 16000


def _text(value: object, field: str, *, limit: int = 800) -> str:
    if (type(value) is not str or not 1 <= len(value) <= limit
            or not value.strip() or value != value.strip()
            or any(ord(c) < 32 and c not in "\n\t" for c in value)):
        raise InputError("invalid " + field)
    return value


def inspect(record: dict, *, asof_utc: str) -> dict:
    cutoff = timestamp(asof_utc)
    if type(record) is not dict or set(record) != REQUIRED:
        raise InputError("invalid macro hypothesis shape")
    for key in ("hypothesis_id", "builder_id", "reviewer_id"):
        if not IDENT.fullmatch(_text(record[key], key, limit=80)):
            raise InputError("invalid macro identifier")
    if record["builder_id"] == record["reviewer_id"]:
        raise InputError("builder and verifier cannot be identical")
    if (record["pair"] not in PAIRS or
            record["direction"] not in ("LONG", "SHORT", "HOLD") or
            record["review_status"] not in REVIEWS):
        raise InputError("unsupported pair/direction/review")
    for field in ("macro_thesis", "counter_thesis", "expected_catalyst",
                  "invalidation_conditions"):
        _text(record[field], field)
    built = timestamp(record["constructed_at_utc"])
    reviewed = timestamp(record["reviewed_at_utc"])
    decision = timestamp(record["decision_at_utc"])
    if not built <= reviewed <= decision <= cutoff:
        raise InputError("hypothesis/review/decision chronology broken")
    sources = record["source_records"]
    if (type(sources) is not list or not 1 <= len(sources) <= 8
            or any(type(s) is not dict or set(s) != SOURCE_FIELDS
                   for s in sources)):
        raise InputError("invalid macro source set")
    labels = []
    for source in sources:
        label = _text(source["source_label"], "source_label", limit=100)
        if not SHA.fullmatch(_text(source["content_sha256"],
                                  "content_sha256", limit=64)):
            raise InputError("invalid source hash shape")
        published = timestamp(source["published_at_utc"])
        accessed = timestamp(source["accessed_at_utc"])
        if not published <= accessed <= built:
            raise InputError("macro source was not available before build")
        labels.append(label)
    if len(set(labels)) != len(labels):
        raise InputError("duplicate evidence labels")
    return {
        "schema": SCHEMA,
        "status": "MACRO_HYPOTHESIS_CONTRACT_RESEARCH_NO_GO",
        "hypothesis_id": record["hypothesis_id"],
        "pair": record["pair"],
        "direction": record["direction"],
        "review_disposition_self_reported": record["review_status"],
        "source_count": len(sources),
        "source_identifiers": labels,
        "source_publication_chronology_consistent": True,
        "builder_reviewer_separated_by_id": True,
        "decision_at_utc": record["decision_at_utc"],
        "hypothetical_replay_allowed_by_document_only":
            record["review_status"] == "APPROVED"
            and record["direction"] in ("LONG", "SHORT"),
        "source_content_verified": False,
        "actual_llm_verification_performed": False,
        "reviewer_identity_authenticated": False,
        "market_prediction_validated": False,
        "trading_authorized": False,
        "runtime_go_no_go": "NO_GO",
        "safety_hold_latched": True,
        "real_orders_permitted": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Audit offline macro evidence; no AI/MT4")
    p.add_argument("--hypothesis", type=Path, required=True)
    p.add_argument("--asof-utc", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if (not a.hypothesis.is_file() or a.hypothesis.is_symlink()
                or not 0 < a.hypothesis.stat().st_size <= MAX_DOCUMENT
                or a.out.exists() or a.out.is_symlink()
                or not a.out.parent.is_dir()):
            raise InputError("unsafe hypothesis/report files")
        proposal = json.loads(a.hypothesis.read_text("utf-8-sig"))
        report = inspect(proposal, asof_utc=a.asof_utc)
        with a.out.open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(json.dumps({
            "status": report["status"],
            "review_disposition_self_reported":
                report["review_disposition_self_reported"],
            "source_content_verified": False,
            "runtime_go_no_go": "NO_GO",
            "real_orders_permitted": False,
        }))
        return 0
    except (InputError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, ArithmeticError, OverflowError):
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "reason": "MACRO_HYPOTHESIS_CONTRACT_UNVERIFIED",
            "runtime_go_no_go": "NO_GO",
            "safety_hold_latched": True,
            "real_orders_permitted": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
