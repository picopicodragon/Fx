"""Optional one-time provider COSTS read via OpenAI organization Admin API.

Requires an admin API key in the LOCAL PC environment and explicit network
opt-in. Makes only a GET to official /organization/costs, never inference,
orders, account changes, budget renewal, or a virtual-entry decision.
The returned provider USD total is organization-wide and cannot prove
the exact FX-system charge or a live JPY monthly spend ceiling.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

SCHEMA = "fx_final_paper_openai_provider_cost_read_v1"
ENDPOINT = "https://api.openai.com/v1/organization/costs"
MAX_BODY = 300_000


class CostEvidenceError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CostEvidenceError("COST_PROVIDER_REDIRECT_REJECTED")


def parse_costs(obj: dict) -> str:
    if (type(obj) is not dict or type(obj.get("data")) is not list
            or obj.get("has_more") is not False
            or not 1 <= len(obj["data"]) <= 31):
        raise CostEvidenceError("COST_PROVIDER_PAGINATION_UNVERIFIED")
    total = Decimal("0")
    for bucket in obj["data"]:
        if (type(bucket) is not dict
                or type(bucket.get("results")) is not list):
            raise CostEvidenceError("COST_PROVIDER_BUCKET_INVALID")
        for item in bucket["results"]:
            if (type(item) is not dict
                    or item.get("object") != "organization.costs.result"):
                raise CostEvidenceError("COST_PROVIDER_RECORD_INVALID")
            amount = item.get("amount")
            if (type(amount) is not dict
                    or amount.get("currency") != "usd"
                    or type(amount.get("value")) not in (float, int)):
                raise CostEvidenceError("COST_PROVIDER_NON_USD")
            value = Decimal(str(amount["value"]))
            if not value.is_finite() or value < 0:
                raise CostEvidenceError("COST_PROVIDER_AMOUNT_INVALID")
            total += value
    if total > Decimal("10000000"):
        raise CostEvidenceError("COST_PROVIDER_AMOUNT_OUT_OF_RANGE")
    return format(total, "f")


def run(out: Path, *, allow_network: bool = False,
        now: datetime | None = None, fetch=None) -> dict:
    if not allow_network:
        raise CostEvidenceError("COST_EXPLICIT_NETWORK_OPT_IN_REQUIRED")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise CostEvidenceError("COST_CLOCK_UNSAFE")
    now_utc = current.astimezone(timezone.utc)
    if (out.exists() or out.is_symlink()
            or not out.parent.is_dir() or out.parent.is_symlink()):
        raise CostEvidenceError("COST_OUTPUT_NOT_NEW")
    key = os.environ.get("OPENAI_ADMIN_KEY", "")
    if len(key) < 15 or len(key) > 4096 or any(c.isspace() for c in key):
        raise CostEvidenceError("COST_ADMIN_KEY_MISSING")
    start = datetime(now_utc.year, now_utc.month, 1, tzinfo=timezone.utc)
    begin = int(start.timestamp())
    finish = int(now_utc.timestamp())
    if finish <= begin:
        raise CostEvidenceError("COST_TIME_RANGE_INVALID")
    query = urlencode({
        "start_time": begin, "end_time": finish,
        "bucket_width": "1d", "limit": 31,
    })
    req = urllib.request.Request(
        ENDPOINT + "?" + query,
        method="GET",
        headers={"Authorization": "Bearer " + key,
                 "Accept": "application/json"},
    )
    if fetch is None:
        opener = urllib.request.build_opener(NoRedirect)
        fetch = opener.open
    with fetch(req, timeout=20) as result:
        if result.geturl().split("?")[0] != ENDPOINT:
            raise CostEvidenceError("COST_ORIGIN_UNVERIFIED")
        raw = result.read(MAX_BODY+1)
        if not 0 < len(raw) <= MAX_BODY:
            raise CostEvidenceError("COST_RESPONSE_OVERSIZE")
    try:
        obj = json.loads(raw)
        total = parse_costs(obj)
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CostEvidenceError("COST_RESPONSE_INVALID") from exc
    record = {
        "schema": SCHEMA,
        "status": "PROVIDER_ORGANIZATION_COST_READ_ONLY_USD_NO_GO",
        "month_utc": now_utc.strftime("%Y-%m"),
        "period_start_epoch_utc": begin,
        "period_end_epoch_utc": finish,
        "provider_reported_organization_cost_usd": total,
        "currency": "USD",
        "provider_costs_endpoint_used": True,
        "organization_wide_not_fx_project_scoped": True,
        "source_data_complete_first_page": True,
        "captured_at_utc_pc_unattested": now_utc.isoformat(),
        "usd_to_jpy_independently_verified": False,
        "fx_project_cost_isolated": False,
        "monthly_3000_jpy_compliance_verified": False,
        "further_paid_api_calls_approved": False,
        "previous_6_calls_reset": False,
        "new_virtual_positions_permitted": False,
        "demo_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
    }
    with out.open("x", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    return record


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only organization costs, no AI inference")
    p.add_argument("--allow-network", action="store_true")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        output = run(args.out, allow_network=args.allow_network)
        print(json.dumps(output, ensure_ascii=False))
        return 0
    except (CostEvidenceError, ValueError, TypeError, OSError,
            urllib.error.URLError, UnicodeError):
        print(json.dumps({
            "status": "PROVIDER_COSTS_READ_FAIL_CLOSED_NO_GO",
            "additional_paid_ai_permitted": False,
            "new_virtual_positions_permitted": False,
            "demo_orders_permitted": False,
            "real_orders_permitted": False,
            "runtime_go_no_go": "NO_GO",
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
