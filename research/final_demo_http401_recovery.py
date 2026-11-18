"""Explicit read-only OpenAI authentication and manual HTTP401 ledger review.

No model inference, no order execution, no automatic API retry.
The original pending ledger is preserved byte-for-byte. Only a separately
created, hash-bound operator-attested HTTP401 review can exempt that specific
rejected analyst request from the next *explicitly opted-in* research cycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from research import final_demo_periodic_ai as periodic_ai
from research import ai_provider_comparison as providers
from research.offline_backtest import InputError

SCHEMA = "fx_final_demo_http401_operator_review_v1"
HTTP401 = "HTTP_401_INVALID_API_KEY"
MAX_LEDGER_BYTES = 30000
MAX_AUTH_REPLY_BYTES = 1_000_000


def _read_ledger(path: Path) -> tuple[dict, str]:
    if (not path.is_file() or path.is_symlink()
            or any(p.is_symlink() for p in path.parents)
            or not path.name.startswith("ai_")
            or not path.name.endswith(".json")):
        raise InputError("UNTRUSTED_OR_MISSING_LEDGER")
    raw = path.read_bytes()
    if not 0 < len(raw) <= MAX_LEDGER_BYTES:
        raise InputError("LEDGER_SIZE_INVALID")
    state = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(state, dict) or state.get("schema") != periodic_ai.SCHEMA:
        raise InputError("LEDGER_SCHEMA_INVALID")
    periodic_ai._valid(state, state)
    providers.ResearchRoleRegistry(
        analyst_model=state["analyst_model"],
        reviewer_model=state["reviewer_model"])
    return state, hashlib.sha256(raw).hexdigest()


def _review_path(ledger: Path) -> Path:
    return ledger.with_name("auth401_review_" + ledger.name)


def _valid_review(ledger: Path, digest: str, state: dict) -> bool:
    marker = _review_path(ledger)
    if not marker.is_file() or marker.is_symlink():
        return False
    if not 0 < marker.stat().st_size <= 10000:
        return False
    try:
        review = json.loads(marker.read_text("utf-8-sig"))
    except (ValueError, UnicodeError, OSError):
        return False
    return (
        type(review) is dict
        and review.get("schema") == SCHEMA
        and review.get("ledger_name") == ledger.name
        and review.get("ledger_sha256") == digest
        and review.get("analyst_model") == state["analyst_model"]
        and review.get("reviewer_model") == state["reviewer_model"]
        and review.get("rejected_failure") == HTTP401
        and review.get("operator_confirmed_http401") is True
        and review.get("read_only_auth_http") == 200
        and review.get("read_only_models_present") is True
        and review.get("api_inference_calls_during_review") == 0
        and review.get("trading_authorized") is False
        and state["stage"] == "ANALYST_PENDING"
        and state["pending_role"] == "analyst"
        and state["analyst"] is None
        and state["reviewer"] is None
    )


def check_directory(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise InputError("LEDGER_DIRECTORY_INVALID")
    count = 0
    reviewed = 0
    for ledger in sorted(folder.glob("ai_*.json")):
        state, digest = _read_ledger(ledger)
        count += 1
        if state["stage"] == "COMPLETE" and state["pending_role"] is None:
            continue
        if _valid_review(ledger, digest, state):
            reviewed += 1
            continue
        raise InputError("PAID_LEDGER_PENDING_OR_UNRECONCILED")
    return {
        "status": "PAID_LEDGER_PREFLIGHT_CLEAR_NO_ORDERS",
        "checked_ledgers": count,
        "operator_reviewed_http401": reviewed,
        "ai_inference_calls_this_run": 0,
        "real_orders_permitted": False,
    }


def _read_only_authentication(analyst: str, reviewer: str) -> bool:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise InputError("OPENAI_API_KEY_MISSING")
    request = urllib.request.Request(
        "https://api.openai.com/v1/models",
        method="GET",
        headers={"Authorization": "Bearer " + key,
                 "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise InputError("READ_ONLY_AUTH_REJECTED")
            body = response.read(MAX_AUTH_REPLY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Do not read or print provider reply: it may quote key material.
        if exc.code == 401:
            raise InputError("READ_ONLY_AUTH_401") from None
        if exc.code == 403:
            raise InputError("READ_ONLY_AUTH_403") from None
        raise InputError("READ_ONLY_AUTH_HTTP_FAILURE") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise InputError("READ_ONLY_AUTH_NETWORK_FAILURE") from None
    if len(body) > MAX_AUTH_REPLY_BYTES:
        raise InputError("READ_ONLY_AUTH_TOO_LARGE")
    try:
        result = json.loads(body)
        models = {item["id"] for item in result["data"]
                  if isinstance(item, dict) and isinstance(item.get("id"), str)}
    except (ValueError, KeyError, TypeError, UnicodeError):
        raise InputError("READ_ONLY_AUTH_RESPONSE_INVALID") from None
    if analyst not in models or reviewer not in models:
        raise InputError("READ_ONLY_MODELS_NOT_LISTED")
    return True


def review_http401(ledger: Path, *, operator_confirmed: bool) -> dict:
    if operator_confirmed is not True:
        raise InputError("EXPLICIT_HTTP401_ATTESTATION_REQUIRED")
    state, digest = _read_ledger(ledger)
    if not (state["stage"] == "ANALYST_PENDING"
            and state["pending_role"] == "analyst"
            and state["analyst"] is None
            and state["reviewer"] is None):
        raise InputError("ONLY_REJECTED_ANALYST_LEDGER_REVIEWABLE")
    if _review_path(ledger).exists():
        raise InputError("REVIEW_MARKER_ALREADY_EXISTS")
    _read_only_authentication(state["analyst_model"],
                              state["reviewer_model"])
    review = {
        "schema": SCHEMA,
        "ledger_name": ledger.name,
        "ledger_sha256": digest,
        "analyst_model": state["analyst_model"],
        "reviewer_model": state["reviewer_model"],
        "rejected_failure": HTTP401,
        "operator_confirmed_http401": True,
        "read_only_auth_http": 200,
        "read_only_models_present": True,
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
        "api_inference_calls_during_review": 0,
        "trading_authorized": False,
    }
    with _review_path(ledger).open("x", encoding="utf-8") as stream:
        json.dump(review, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    if not _valid_review(ledger, digest, state):
        raise InputError("REVIEW_MARKER_WRITE_FAILED")
    return {
        "status": "EXPLICIT_HTTP401_REVIEW_RECORDED_NO_INFERENCE",
        "ledger_preserved": True,
        "authentication_http": 200,
        "analyst_model_listed": True,
        "reviewer_model_listed": True,
        "api_inference_calls_this_run": 0,
        "trading_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Review definite HTTP401 rejection without API inference")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--check-directory", type=Path)
    choice.add_argument("--review-ledger", type=Path)
    parser.add_argument("--operator-confirmed-http401", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.check_directory is not None:
            if args.operator_confirmed_http401:
                raise InputError("INVALID_READ_ONLY_MODE")
            outcome = check_directory(args.check_directory)
        else:
            outcome = review_http401(
                args.review_ledger,
                operator_confirmed=args.operator_confirmed_http401)
        print(json.dumps(outcome, ensure_ascii=False))
        return 0
    except (InputError, ValueError, TypeError, KeyError, OSError,
            UnicodeError, OverflowError) as exc:
        allow = {
            "UNTRUSTED_OR_MISSING_LEDGER", "LEDGER_SIZE_INVALID",
            "LEDGER_SCHEMA_INVALID", "LEDGER_DIRECTORY_INVALID",
            "PAID_LEDGER_PENDING_OR_UNRECONCILED",
            "OPENAI_API_KEY_MISSING", "READ_ONLY_AUTH_401",
            "READ_ONLY_AUTH_403", "READ_ONLY_AUTH_HTTP_FAILURE",
            "READ_ONLY_AUTH_NETWORK_FAILURE",
            "READ_ONLY_AUTH_TOO_LARGE", "READ_ONLY_AUTH_REJECTED",
            "READ_ONLY_AUTH_RESPONSE_INVALID",
            "READ_ONLY_MODELS_NOT_LISTED",
            "EXPLICIT_HTTP401_ATTESTATION_REQUIRED",
            "ONLY_REJECTED_ANALYST_LEDGER_REVIEWABLE",
            "REVIEW_MARKER_ALREADY_EXISTS",
            "REVIEW_MARKER_WRITE_FAILED", "INVALID_READ_ONLY_MODE",
        }
        name = (exc.args[0] if isinstance(exc, InputError) and exc.args
                and type(exc.args[0]) is str else "")
        print(json.dumps({
            "status": "HTTP401_REVIEW_FAIL_CLOSED_NO_GO",
            "failure_reason_code": name if name in allow
            else "REVIEW_VALIDATION_FAILED",
            "api_inference_calls_this_run": 0,
            "trading_authorized": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
