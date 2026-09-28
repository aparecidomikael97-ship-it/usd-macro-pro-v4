"""Single application clock for every AION greeting.

The zone comes from ATLASQUANT_TIMEZONE and defaults to America/Cuiaba.
Invalid names fall back to that zone. The server's local timezone is never read.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Cuiaba"


def application_timezone(configured: str | None = None) -> ZoneInfo:
    """Configured application zone. An invalid name falls back to Cuiabá."""
    if configured is None:
        configured = os.environ.get("ATLASQUANT_TIMEZONE", DEFAULT_TIMEZONE)
    name = " ".join(str(configured or "").split()) or DEFAULT_TIMEZONE
    for candidate in (name, DEFAULT_TIMEZONE):
        try:
            return ZoneInfo(candidate)
        except Exception:
            continue
    return ZoneInfo("UTC")


def greeting_period(now: datetime | None = None, *, timezone_name: str | None = None) -> str:
    """Bom dia 05:00–11:59, boa tarde 12:00–17:59, boa noite otherwise.

    Aware values are converted into the configured zone. Naive values are read
    as wall time in that zone, never as the Render server zone.
    """
    zone = application_timezone(timezone_name)
    if now is None:
        moment = datetime.now(timezone.utc).astimezone(zone)
    elif now.tzinfo is None:
        moment = now.replace(tzinfo=zone)
    else:
        moment = now.astimezone(zone)
    if 5 <= moment.hour < 12:
        return "Bom dia"
    if 12 <= moment.hour < 18:
        return "Boa tarde"
    return "Boa noite"


__all__ = [
    "DEFAULT_TIMEZONE",
    "application_timezone",
    "greeting_period",
]
