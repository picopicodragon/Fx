"""P0-01 D5-4: synthetic-only risk boundary evaluator, never order authority.

Explicit decimal yen strings only; no account/terminal/IO/network/clock access.
This checks hypothetical limits, not executable sizing or broker execution safety.
"""
from __future__ import annotations

from decimal import Decimal, localcontext
from scripts.p0_01_offline_five_field_mock import parse_positive_token


def _nonnegative_yen(value: object) -> Decimal | None:
    """Zero is valid for hypothetical loss/risk only, never for equity."""
    if type(value) is str and value == "0":
        return Decimal(0)
    return parse_positive_token(value)

LIMITS = {"trade": Decimal("0.005"), "aggregate": Decimal("0.01"),
          "daily": Decimal("0.015"), "drawdown": Decimal("0.05")}
FIELDS = frozenset(("origin", "equity_jpy", "peak_equity_jpy",
                    "single_trade_risk_jpy", "aggregate_risk_jpy",
                    "daily_loss_jpy"))
BLOCKED = "BLOCKED"
REVIEW = "REVIEW_REQUIRED"


def evaluate_synthetic_limits(fixture: object) -> dict[str, object]:
    """Only fixed status flags returned. Invalid/missing means fail-closed."""
    status = REVIEW
    try:
        if type(fixture) is dict and set(fixture) == FIELDS and fixture["origin"] == "SYNTHETIC_ONLY":
            v = {name: (parse_positive_token(fixture[name]) if name in ("equity_jpy", "peak_equity_jpy")
                        else _nonnegative_yen(fixture[name]))
                 for name in FIELDS - {"origin"}}
            if all(x is not None for x in v.values()) and v["peak_equity_jpy"] >= v["equity_jpy"]:
                with localcontext() as ctx:
                    ctx.prec = 48
                    trade_limit = v["equity_jpy"] * LIMITS["trade"]
                    aggregate_limit = v["equity_jpy"] * LIMITS["aggregate"]
                    daily_limit = v["equity_jpy"] * LIMITS["daily"]
                    drawdown = (v["peak_equity_jpy"] - v["equity_jpy"]) / v["peak_equity_jpy"]
                if drawdown >= LIMITS["drawdown"]:
                    status = "HARD_STOP_DD5"
                elif v["daily_loss_jpy"] >= daily_limit:
                    status = "DAILY_STOP"
                elif v["single_trade_risk_jpy"] > trade_limit or v["aggregate_risk_jpy"] > aggregate_limit:
                    status = "RISK_LIMIT_EXCEEDED"
                else:
                    status = "SYNTHETIC_WITHIN_LIMITS_NEVER_AUTHORIZED"
    except Exception:
        status = REVIEW
    return {"status": status, "broker_verified": False, "production_usable": False,
            "orders_generated": False, "terminal_execution_approved": False,
            "forward_trading_enabled": False, "phase_1": BLOCKED}
