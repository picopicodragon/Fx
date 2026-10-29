"""D5-6 pure NY17 trading-day labeling for synthetic UTC timestamps only.

No clock reads, file IO, broker queries, orders, or terminal interactions.
"""
from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
REVIEW = "REVIEW_REQUIRED"
VALID = "SYNTHETIC_TRADING_DAY_LABELED_NEVER_AUTHORIZED"


def label_synthetic_ny17(timestamp: object) -> dict[str, object]:
    status = REVIEW
    trading_day = None
    try:
        if type(timestamp) is str and 20 <= len(timestamp) <= 35:
            parsed = datetime.fromisoformat(timestamp)
            if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                # Input is an absolute UTC instant only. This avoids ambiguous
                # or nonexistent local wall times at DST transitions.
                if parsed.utcoffset() == timedelta(0):
                    instant = parsed.astimezone(timezone.utc)
                    local = instant.astimezone(NY)
                    boundary_date = local.date() if local.time() >= time(17) else local.date() - timedelta(days=1)
                    trading_day = boundary_date.isoformat()
                    status = VALID
    except (ValueError, TypeError, OverflowError):
        status = REVIEW
    return {
        "status": status, "trading_day_start_ny_date": trading_day,
        "broker_verified": False, "production_usable": False,
        "orders_generated": False, "terminal_execution_approved": False,
        "forward_trading_enabled": False, "phase_1": "BLOCKED",
    }
