"""Conservative CME public settlement dissemination floors (offline LAB).

This enforces *earliest plausible availability* for a source channel. Passing
NEVER authenticates actual issuer bytes, first-seen timestamps, a license,
contract-specific liquidity, nor CME's exact exchange-holiday calendar.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA = 'ATLASQUANT_CME_PUBLIC_SETTLEMENT_RELEASE_GATE_LAB_V1'
CME_CT = ZoneInfo('America/Chicago')
CHANNELS = {
    'CME_PUBLIC_WEBSITE_SETTLEMENT': time(0, 0),
    'CME_DAILY_BULLETIN_PRELIM': time(0, 0),
    'CME_DAILY_BULLETIN_FINAL': time(10, 0),
}


def _next_weekday(day: date) -> date:
    following = day + timedelta(days=1)
    while following.weekday() >= 5:
        following += timedelta(days=1)
    return following


def conservative_first_public_floor_utc(trade_date: Any, channel: Any) -> datetime | None:
    """Next *weekday* public dissemination floor; holidays not certified.

    Friday->Monday is deliberately conservative. The CME may post particular
    settlement tables earlier; absent a captured original, never infer this.
    """
    if type(trade_date) is not date or trade_date.weekday() >= 5 or channel not in CHANNELS:
        return None
    local = datetime.combine(_next_weekday(trade_date), CHANNELS[channel], tzinfo=CME_CT)
    return local.astimezone(timezone.utc)


def inspect_cme_settlement_release_gate_lab(*, trade_date: Any, channel: Any,
                                             published_at_utc: Any, captured_at_utc: Any,
                                             as_of_utc: Any) -> dict[str, Any]:
    """Reject impossible public-source timing; never mark a quote verified."""
    report = {
        'schema': SCHEMA, 'state': 'BLOCKED_INVALID_EVIDENCE',
        'earliest_notional_public_floor_utc': None,
        'floor_is_official_release_timestamp': False,
        'exchange_holiday_calendar_attested': False,
        'actual_first_seen_independently_attested': False,
        'issuer_payload_archived': False,
        'licensed_reuse_verified': False,
        'eligible_as_authenticated_market_quote': False,
        'operational_bias': 'AGUARDAR', 'trade_authorized': False,
        'http_requests': 0, 'file_writes': 0, 'new_cost_brl': 0,
    }
    floor = conservative_first_public_floor_utc(trade_date, channel)
    values = (published_at_utc, captured_at_utc, as_of_utc)
    if floor is None or any(not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None for v in values):
        return report
    pub, cap, now = (v.astimezone(timezone.utc) for v in values)
    report['earliest_notional_public_floor_utc'] = floor.isoformat()
    if pub < floor or cap < floor or now < floor:
        report['state'] = 'BLOCKED_BEFORE_PUBLIC_DISSEMINATION_FLOOR'
        return report
    if not (pub <= cap <= now):
        report['state'] = 'BLOCKED_INVALID_TIME_SEQUENCE'
        return report
    report['state'] = 'SELF_CLAIMED_PUBLIC_TIMING_PLAUSIBLE_NOT_AUTHENTICATED'
    return report