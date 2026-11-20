"""Bounded two-model JPY worst-case API cost calculator (NO dispatch).

Declared prices, USD/JPY ceiling and output-token limits are operator
evidence, not provider-authenticated rates. No renewals, token billing,
resets, API calls or live-trade permissions can be created by this review.
"""
from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path

from research.offline_backtest import InputError

SCHEMA = "fx_final_paper_two_model_api_cost_envelope_v1"
CAP_JPY = Decimal("3000")
NUMBER = re.compile(r"^(0|[1-9][0-9]{0,7})(\.[0-9]{1,8})?$")
REQ_KEYS = {
    "schema", "first_model", "second_model", "usd_jpy_ceiling",
    "monthly_billed_jpy_operator_reported", "first_input_usd_per_million",
    "first_output_usd_per_million", "second_input_usd_per_million",
    "second_output_usd_per_million", "first_input_tokens_cap",
    "first_output_tokens_cap", "second_input_tokens_cap",
    "second_output_tokens_cap", "provider_prices_independently_attested",
    "exchange_ceiling_independently_attested",
    "provider_billing_independently_attested",
}


def _decimal(value: object, *, positive: bool = False) -> Decimal:
    if type(value) is not str or NUMBER.fullmatch(value) is None:
        raise InputError("invalid monetary cost envelope")
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise InputError("invalid monetary cost envelope") from exc
    if not d.is_finite() or d < 0 or (positive and d <= 0):
        raise InputError("invalid monetary cost envelope")
    return d


def estimate(record: dict) -> dict:
    if type(record) is not dict or set(record) != REQ_KEYS or (
        record["schema"] != SCHEMA
        or type(record["first_model"]) is not str
        or type(record["second_model"]) is not str
        or not 1 <= len(record["first_model"]) <= 80
        or not 1 <= len(record["second_model"]) <= 80
        or record["first_model"] == record["second_model"]
        or any(record[k] is not False for k in (
            "provider_prices_independently_attested",
            "exchange_ceiling_independently_attested",
            "provider_billing_independently_attested"))
    ):
        raise InputError("unverified API cost assumptions")
    fx = _decimal(record["usd_jpy_ceiling"], positive=True)
    billed = _decimal(record["monthly_billed_jpy_operator_reported"])
    if fx > 500 or billed > CAP_JPY:
        raise InputError("cost envelope exceeds safe limits")
    usd = Decimal("0")
    for prefix in ("first", "second"):
        i = record[prefix + "_input_tokens_cap"]
        o = record[prefix + "_output_tokens_cap"]
        if (type(i) is not int or type(o) is not int
                or not 1 <= i <= 1_000_000
                or not 1 <= o <= 100_000):
            raise InputError("unbounded token budget")
        ip = _decimal(record[prefix + "_input_usd_per_million"],positive=True)
        op = _decimal(record[prefix + "_output_usd_per_million"],positive=True)
        usd += (ip * Decimal(i) + op * Decimal(o))/Decimal(1_000_000)
    reserve = (usd * fx).quantize(Decimal(".01"), rounding=ROUND_CEILING)
    headroom = CAP_JPY - billed
    return {
        "schema": SCHEMA,
        "status": "API_TWO_MODEL_COST_SCENARIO_ONLY_NO_GO",
        "model_count": 2,
        "monthly_cap_jpy": "3000.00",
        "monthly_billed_jpy_operator_reported": str(billed),
        "two_call_worst_case_reserved_jpy_operator_assumed": str(reserve),
        "unreserved_jpy_operator_assumed": str(headroom),
        "arithmetic_fits_3000_jpy": reserve > 0 and reserve <= headroom,
        "provider_rates_verified": False,
        "usd_jpy_ceiling_verified": False,
        "actual_invoice_verified": False,
        "paid_calls_renewal_authorized": False,
        "actual_api_cost_guarantee": False,
        "new_paid_ai_calls_permitted": False,
        "new_virtual_positions_permitted": False,
        "broker_orders_permitted": False,
        "real_orders_permitted": False,
        "runtime_go_no_go": "NO_GO",
    }


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description="Offline only API cost ceiling scenario")
    p.add_argument("--assumptions", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args=p.parse_args(argv)
    try:
        file=args.assumptions
        if (not file.is_file() or file.is_symlink()
                or not 0 < file.stat().st_size <= 8192):
            raise InputError("invalid cost assumptions")
        record=json.loads(file.read_text("utf-8-sig"))
        result=estimate(record)
        if (args.out.exists() or args.out.is_symlink()
                or not args.out.parent.is_dir()
                or args.out.parent.is_symlink()):
            raise InputError("output path exists")
        with args.out.open("x",encoding="utf-8") as output:
            json.dump(result,output,ensure_ascii=False,indent=2)
        print(json.dumps(result,ensure_ascii=False))
        return 0
    except (InputError,KeyError,ValueError,TypeError,OSError,
            UnicodeError,OverflowError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"API_COST_ENVELOPE_FAIL_CLOSED_NO_GO",
            "new_paid_ai_calls_permitted":False,
            "new_virtual_positions_permitted":False,
            "broker_orders_permitted":False,
            "real_orders_permitted":False,
            "runtime_go_no_go":"NO_GO",
        }))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
