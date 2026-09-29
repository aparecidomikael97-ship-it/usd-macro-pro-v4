"""AtlasQuant / AION System Health Center V1.

Read-only aggregation for the administrative Núcleo. It normalizes already
computed subsystem health into one strict, fail-closed view covering sources,
runtime, notifications, workers, queues and critical screens.

This module does not probe providers, start workers, send notifications, drain
queues, refresh market data, change feature flags, deploy, merge or authorize
trading. A healthy-looking label is only accepted as HEALTHY when the upstream
snapshot explicitly marks itself confirmed.
"""
from __future__ import annotations

from typing import Any, Mapping
import math
import re

from atlasquant_data_freshness import CURRENT as FRESH_CURRENT, assess_freshness


SCHEMA = "ATLASQUANT_AION_SYSTEM_HEALTH_CENTER_V1"

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
BLOCKED = "BLOCKED"
UNKNOWN = "UNKNOWN"

DOMAINS = (
    "sources",
    "runtime",
    "notifications",
    "workers",
    "queues",
    "screens",
)

DOMAIN_LABELS = {
    "sources": "Fontes",
    "runtime": "Runtime",
    "notifications": "Notificações",
    "workers": "Workers",
    "queues": "Filas",
    "screens": "Telas críticas",
}

_HEALTHY_TOKENS = frozenset({
    "OK",
    "HEALTHY",
    "READY",
    "CURRENT",
    "OPERATIONAL",
    "RUNNING",
    "AVAILABLE",
})
_DEGRADED_TOKENS = frozenset({
    "DEGRADED",
    "WARNING",
    "WARN",
    "PARTIAL",
    "STALE",
    "ATTENTION",
    "LIMITED",
    "RATE_LIMITED",
})
_BLOCKED_TOKENS = frozenset({
    "BLOCKED",
    "ERROR",
    "FAILED",
    "FAIL",
    "UNAVAILABLE",
    "CRITICAL",
    "STOPPED",
})
_SECRET_TOKENS = (
    "secret",
    "token",
    "password",
    "credential",
    "api_key",
    "apikey",
)


def _clean_text(value: Any, limit: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.split())
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32)
    return cleaned[:limit]


_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|token|password|secret|credential)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)


def _redact_text(value: Any, limit: int = 240) -> str:
    text = _clean_text(value, limit=max(limit * 2, 512))
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text[:limit]


def _state_token(value: Any) -> str:
    token = _clean_text(value, 80).upper().replace("-", "_").replace(" ", "_")
    if token in _HEALTHY_TOKENS:
        return HEALTHY
    if token in _DEGRADED_TOKENS:
        return DEGRADED
    if token in _BLOCKED_TOKENS:
        return BLOCKED
    if token in {HEALTHY, DEGRADED, BLOCKED, UNKNOWN}:
        return token
    return UNKNOWN


def _safe_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return None
    return int(number)


def _secret_like_key(name: Any) -> bool:
    token = str(name or "").casefold().replace("-", "_")
    return any(part in token for part in _SECRET_TOKENS)


def normalize_health_domain(
    domain: str,
    snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalize one upstream declaration without upgrading unconfirmed health."""
    key = str(domain or "").strip()
    if key not in DOMAIN_LABELS:
        raise ValueError(f"unknown health domain: {key}")

    raw = dict(snapshot or {})
    has_secret_field = any(_secret_like_key(name) for name in raw)
    declared_state = _state_token(raw.get("state"))
    confirmed = raw.get("confirmed") is True

    if has_secret_field:
        state = BLOCKED
        reasons = ["SECRET_FIELD_REJECTED"]
        confirmed = False
    elif declared_state == HEALTHY and not confirmed:
        state = UNKNOWN
        reasons = ["HEALTH_NOT_CONFIRMED"]
    elif declared_state == UNKNOWN:
        state = UNKNOWN
        reasons = ["STATE_UNKNOWN"]
    else:
        state = declared_state
        reasons = []

    freshness_confirmed = False
    freshness_reason = ""
    if state == HEALTHY:
        attested = (
            raw.get("freshness_attested") is True
            and bool(_clean_text(raw.get("freshness_source"), 120))
        )
        temporal_declared = (
            raw.get("observed_at") not in (None, "")
            or raw.get("ttl_minutes") not in (None, "")
        )
        if temporal_declared:
            temporal = assess_freshness(
                {
                    "source": _clean_text(raw.get("freshness_source") or raw.get("source") or key, 120),
                    "observed_at": raw.get("observed_at"),
                    "available_at": raw.get("available_at"),
                    "ttl_minutes": raw.get("ttl_minutes"),
                },
                evaluated_at=raw.get("evaluated_at"),
            )
            freshness_confirmed = temporal.get("state") == FRESH_CURRENT
            freshness_reason = str(temporal.get("state") or "UNKNOWN")
        elif attested:
            freshness_confirmed = True
            freshness_reason = "UPSTREAM_ATTESTED"
        else:
            state = UNKNOWN
            confirmed = False
            reasons.append("FRESHNESS_NOT_CONFIRMED")
            freshness_reason = "UNKNOWN"

    unresolved = _safe_count(raw.get("unresolved"))
    total = _safe_count(raw.get("total"))
    affected = _safe_count(raw.get("affected"))

    if state == HEALTHY and unresolved not in (None, 0):
        state = DEGRADED
        reasons.append("UNRESOLVED_ITEMS_PRESENT")

    return {
        "id": key,
        "label": DOMAIN_LABELS[key],
        "state": state,
        "declared_state": declared_state,
        "confirmed": bool(confirmed and freshness_confirmed and state == HEALTHY),
        "freshness_confirmed": bool(freshness_confirmed),
        "freshness_reason": freshness_reason,
        "detail": _redact_text(raw.get("detail")),
        "observed_at": _clean_text(raw.get("observed_at"), 96),
        "total": total,
        "unresolved": unresolved,
        "affected": affected,
        "reasons": reasons,
        "read_only": True,
        "executes_action": False,
        "execution_authorized": False,
        "real_trading_enabled": False,
    }


def build_system_health_center(
    snapshots: Mapping[str, Mapping[str, Any] | None] | None,
) -> dict[str, Any]:
    """Build the six-domain administrative health view with strict precedence."""
    source = dict(snapshots or {})
    items = [
        normalize_health_domain(domain, source.get(domain))
        for domain in DOMAINS
    ]

    counts = {
        HEALTHY: 0,
        DEGRADED: 0,
        BLOCKED: 0,
        UNKNOWN: 0,
    }
    for item in items:
        counts[item["state"]] += 1

    if counts[BLOCKED]:
        state = BLOCKED
    elif counts[UNKNOWN]:
        state = UNKNOWN
    elif counts[DEGRADED]:
        state = DEGRADED
    else:
        state = HEALTHY

    unresolved_domains = [
        item["id"] for item in items if item["state"] != HEALTHY
    ]
    consistency_warnings: list[str] = []
    by_id = {item["id"]: item for item in items}
    if (
        by_id["workers"]["state"] == HEALTHY
        and by_id["queues"]["state"] in {DEGRADED, BLOCKED}
    ):
        consistency_warnings.append("WORKER_HEALTHY_WITH_QUEUE_ISSUES")
    if (
        by_id["runtime"]["state"] == HEALTHY
        and by_id["screens"]["state"] == BLOCKED
    ):
        consistency_warnings.append("RUNTIME_HEALTHY_WITH_BLOCKED_SCREEN")

    return {
        "schema": SCHEMA,
        "state": state,
        "items": items,
        "counts": counts,
        "total_domains": len(items),
        "healthy_domains": counts[HEALTHY],
        "unresolved_domains": unresolved_domains,
        "consistency_warnings": consistency_warnings,
        "all_confirmed_healthy": state == HEALTHY,
        "read_only": True,
        "executes_action": False,
        "automatic_repair": False,
        "automatic_restart": False,
        "automatic_notification": False,
        "feature_flag_changed": False,
        "execution_authorized": False,
        "real_trading_enabled": False,
        "interpretation": (
            "Centro de Saúde apenas resume evidência já declarada. "
            "Estado saudável não inicia ação e não autoriza trading."
        ),
    }


def system_health_rows(
    center: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Compact rows suitable for Admin presentation without exposing raw payloads."""
    out = []
    for item in list((center or {}).get("items", []) or []):
        if not isinstance(item, Mapping):
            continue
        out.append({
            "Área": _clean_text(item.get("label"), 80),
            "Estado": _state_token(item.get("state")),
            "Confirmado": item.get("confirmed") is True,
            "Pendências": _safe_count(item.get("unresolved")),
            "Detalhe": _clean_text(item.get("detail")),
        })
    return out


__all__ = [
    "SCHEMA",
    "HEALTHY",
    "DEGRADED",
    "BLOCKED",
    "UNKNOWN",
    "DOMAINS",
    "DOMAIN_LABELS",
    "normalize_health_domain",
    "build_system_health_center",
    "system_health_rows",
]
