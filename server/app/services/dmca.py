from __future__ import annotations

from datetime import datetime, timedelta


TAKEDOWN_STATUS_PENDING = "pending"
TAKEDOWN_STATUS_DISABLED = "disabled"
TAKEDOWN_STATUS_REJECTED = "rejected"
TAKEDOWN_STATUS_COUNTER_RECEIVED = "counter_received"
TAKEDOWN_STATUS_RESTORED = "restored"
TAKEDOWN_STATUS_LAWSUIT_HOLD = "lawsuit_hold"

ACTIVE_DMCA_STATUSES = {
    TAKEDOWN_STATUS_DISABLED,
    TAKEDOWN_STATUS_COUNTER_RECEIVED,
    TAKEDOWN_STATUS_LAWSUIT_HOLD,
}


def add_business_days(start: datetime, business_days: int) -> datetime:
    current = start
    added = 0
    while added < max(0, business_days):
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current
