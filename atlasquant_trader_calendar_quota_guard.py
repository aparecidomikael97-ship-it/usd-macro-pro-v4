"""Conservative opt-in and per-process daily budget for economic-event reads.

This module is NOT a payment entitlement check: a real EODHD account owner must
verify Economic Events rights first. Default is disabled, even if a token exists.
The budget is an additional application cap, NOT a replacement for provider
account-level quotas, nor durable across app restarts / replicas. No background
tasks, writes to disk, external calls, AION Worker or orders.

Authorisation after manual entitlement confirmation:
    ATLASQUANT_CALENDAR_EODHD_ENABLED=1
Optional per-process cap (UTC daily; max 8):
    ATLASQUANT_CALENDAR_MAX_CALLS_PER_DAY=4

Using an account with automatic top-up / extra calls may still have external
cost implications. Leave disabled until account billing is reviewed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from threading import RLock
from typing import Any, Callable
import os

FEATURE_FLAG = "ATLASQUANT_CALENDAR_EODHD_ENABLED"
LIMIT_FLAG = "ATLASQUANT_CALENDAR_MAX_CALLS_PER_DAY"
DEFAULT_CAP = 4
HARD_CAP = 8
_LOCK = RLock()
_USED: dict[str, int] = {}
_RESPONSES: dict[tuple[str, str, int], dict[str, Any]] = {}


def permission_enabled(env: dict[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    return str(values.get(FEATURE_FLAG) or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def configured_cap(env: dict[str, str] | None = None) -> int:
    values = env if env is not None else os.environ
    raw = str(values.get(LIMIT_FLAG) or "").strip()
    try:
        n = int(raw) if raw else DEFAULT_CAP
    except (TypeError, ValueError):
        n = DEFAULT_CAP
    return min(HARD_CAP, max(1, n))


def guarded_read(
    token: str, day_brt: str, hour_utc: int, *,
    fetch: Callable[[str, str, int], dict[str, Any]],
    at: datetime | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Allow at most configured distinct requests per UTC day per process.

    No request if disabled. Fail closed when the budget is exhausted, but serve
    a prior matching hourly result without spending again. No token is stored
    in the cache key, only a fixed-length SHA-256 digest.
    """
    if not permission_enabled(env):
        return {"ok": False, "reason": "PROVIDER_NOT_AUTHORIZED", "data": []}
    if not isinstance(token, str) or not token.strip():
        return {"ok": False, "reason": "NO_EXISTING_TOKEN", "data": []}
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("UTC time must be timezone aware")
    now = now.astimezone(timezone.utc)
    epoch_hour = int(now.timestamp()) // 3600
    if isinstance(hour_utc, bool) or hour_utc != epoch_hour:
        return {"ok": False, "reason": "INVALID_CACHE_KEY", "data": []}
    utc_day = now.date().isoformat()
    token_digest = sha256(token.encode("utf-8")).hexdigest()
    key = (token_digest, day_brt, hour_utc)
    with _LOCK:
        if key in _RESPONSES:
            return dict(_RESPONSES[key])
        used = _USED.get(utc_day, 0)
        if used >= configured_cap(env):
            return {"ok": False, "reason": "ATLASQUANT_DAILY_CAP", "data": []}
        # Reserve BEFORE the request. Even a provider failure consumes this
        # app-side budget, preventing retry storms at 403/429 or timeouts.
        _USED[utc_day] = used + 1
        try:
            reply = fetch(token, day_brt, hour_utc)
        except Exception:
            reply = {"ok": False, "reason": "PROVIDER_UNAVAILABLE", "data": []}
        if not isinstance(reply, dict) or not isinstance(reply.get("ok"), bool):
            reply = {"ok": False, "reason": "INVALID_RESPONSE", "data": []}
        _RESPONSES[key] = dict(reply)
        # Bounded process memory. Old response buckets never become persistent.
        if len(_RESPONSES) > 64:
            oldest = next(iter(_RESPONSES))
            _RESPONSES.pop(oldest, None)
        if len(_USED) > 3:
            for prior in list(_USED):
                if prior != utc_day:
                    _USED.pop(prior, None)
        return dict(reply)


def quota_snapshot(*, at: datetime | None = None,
                   env: dict[str, str] | None = None) -> dict[str, Any]:
    """Safe status for display; never includes a key or raw provider body."""
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware time required")
    date_utc = now.astimezone(timezone.utc).date().isoformat()
    with _LOCK:
        count = _USED.get(date_utc, 0)
    return {
        "enabled": permission_enabled(env),
        "day_utc": date_utc,
        "used_process": count,
        "remaining_process": max(0, configured_cap(env) - count),
        "per_process_cap": configured_cap(env),
        "scope": "PROCESS_ONLY_NOT_PROVIDER_QUOTA",
    }


def _reset_for_tests() -> None:
    """Test-only reset; not exposed as a production UI action."""
    with _LOCK:
        _USED.clear()
        _RESPONSES.clear()


__all__ = ["FEATURE_FLAG", "LIMIT_FLAG", "guarded_read",
           "quota_snapshot", "permission_enabled", "configured_cap"]
