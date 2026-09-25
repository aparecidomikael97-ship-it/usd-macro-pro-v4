"""AION Source Intelligence Mesh.

Converts evidence already produced by AtlasQuant into normalized source
observations for Reliability Guardian. This module does not fetch the internet,
use API keys, mutate data, change scores, switch providers or enable trading.

The mesh only reports what the caller supplies from existing runtime state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import math
import re

SCHEMA = "ATLASQUANT_AION_SOURCE_MESH_V1"

_FRED_MAX_AGE_DAYS = {
    "juros do fed": 45.0,
    "ipc anual": 50.0,
    "ipc núcleo anual": 50.0,
    "ipc nucleo anual": 50.0,
    "pce anual": 50.0,
    "pce núcleo anual": 50.0,
    "pce nucleo anual": 50.0,
    "payroll — variação mensal": 50.0,
    "payroll - variação mensal": 50.0,
    "payroll variação mensal (mil)": 50.0,
    "desemprego": 50.0,
    "pib": 130.0,
    "treasury 2 anos": 5.0,
    "treasury 10 anos": 5.0,
    "índice amplo do dólar": 10.0,
    "indice amplo do dolar": 10.0,
}

_HIGH_MACRO = {
    "juros do fed",
    "ipc anual",
    "ipc núcleo anual",
    "ipc nucleo anual",
    "pce anual",
    "pce núcleo anual",
    "pce nucleo anual",
    "payroll — variação mensal",
    "payroll - variação mensal",
    "payroll variação mensal (mil)",
    "desemprego",
}


def _clean(value: Any, limit: int = 500) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _slug(value: Any) -> str:
    text = _clean(value, 180).casefold()
    text = re.sub(r"[^a-z0-9à-ÿ]+", "_", text, flags=re.I)
    return text.strip("_") or "unknown"


def _parse_time(value: Any) -> datetime | None:
    text = _clean(value, 120)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_minutes(value: Any, *, now: datetime | None = None) -> float | None:
    dt = _parse_time(value)
    if dt is None:
        return None
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    minutes = (current.astimezone(timezone.utc) - dt).total_seconds() / 60.0
    return round(max(0.0, minutes), 2)


def _obs(
    source: str,
    claim: str,
    value: Any,
    *,
    truth_state: str,
    available: bool | None,
    healthy: bool | None,
    criticality: str,
    age: float | None = None,
    max_age: float | None = None,
    detail: str = "",
    cost_state: str = "UNKNOWN",
    quota_remaining_pct: float | None = None,
    family: str = "runtime",
) -> dict[str, Any]:
    return {
        "source": _clean(source, 160),
        "claim": _clean(claim, 180),
        "value": value,
        "truth_state": truth_state,
        "available": available,
        "healthy": healthy,
        "criticality": criticality,
        "age_minutes": age,
        "max_age_minutes": max_age,
        "detail": _clean(detail, 700),
        "cost_state": _clean(cost_state, 80).upper() or "UNKNOWN",
        "quota_remaining_pct": quota_remaining_pct,
        "family": _clean(family, 80).lower() or "runtime",
    }


def fred_macro_observations(
    macro_us: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    data = dict(macro_us or {})
    audit = [
        dict(x) for x in list(data.get("_auditoria", []) or [])
        if isinstance(x, Mapping)
    ]
    out: list[dict[str, Any]] = []
    for row in audit:
        label = _clean(row.get("Indicador"), 180)
        normalized = label.casefold()
        source_text = _clean(row.get("Fonte"), 180)
        is_fred = source_text.upper().startswith("FRED")
        age_days = _finite(row.get("Idade (dias)"))
        age = None if age_days is None else round(max(0.0, age_days) * 1440.0, 2)
        max_days = _FRED_MAX_AGE_DAYS.get(normalized, 60.0)
        max_age = max_days * 1440.0
        healthy = bool(is_fred and (age is None or age <= max_age))
        out.append(_obs(
            source=source_text or "macro_us",
            claim=f"macro:{_slug(label)}",
            value=row.get("Valor"),
            truth_state="CONFIRMED" if is_fred else "UNKNOWN",
            available=True if is_fred else False,
            healthy=healthy if is_fred else False,
            criticality="HIGH" if normalized in _HIGH_MACRO else "MEDIUM",
            age=age,
            max_age=max_age,
            detail=(
                f"Última observação {row.get('Última observação')}."
                if is_fred
                else "Valor de segurança/fallback; não representa observação atual confirmada."
            ),
            family="macro_fred",
        ))
    return out


def calendar_observations(
    next_event: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    event = dict(next_event or {})
    available = bool(event.get("disponivel", False))
    source = _clean(event.get("fonte"), 180) or "economic_calendar"
    impact = _clean(event.get("impacto"), 80).upper()
    value = {
        "evento": _clean(event.get("evento"), 180),
        "data": _clean(event.get("data_txt") or event.get("data"), 100),
        "dias": event.get("dias"),
        "impacto": impact,
        "tipo": _clean(event.get("tipo"), 100),
    }
    criticality = "HIGH" if impact in {"MÁXIMO", "MAXIMO", "ALTO", "HIGH"} else "MEDIUM"
    return [_obs(
        source=source,
        claim="economic_calendar_next_event",
        value=value,
        truth_state="CONFIRMED" if available and bool(source) else "UNKNOWN",
        available=available,
        healthy=available,
        criticality=criticality,
        detail=(
            "Próximo evento macro fornecido pelo motor de calendário."
            if available else
            "Próximo evento macro não confirmado nesta execução."
        ),
        family="calendar",
    )]


def _quota_pct(budget: Mapping[str, Any] | None) -> float | None:
    raw = dict(budget or {})
    limit = _finite(raw.get("limit"))
    remaining = _finite(raw.get("remaining"))
    if limit is None:
        limit = _finite(raw.get("daily_limit"))
    if remaining is None and limit is not None:
        used = _finite(raw.get("used"))
        if used is not None:
            remaining = max(0.0, limit - used)
    if limit is None or remaining is None or limit <= 0:
        return None
    return round(max(0.0, min(100.0, remaining / limit * 100.0)), 2)


def autopilot_observations(
    status: Mapping[str, Any] | None,
    *,
    provenance: Any = "",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    s = dict(status or {})
    if not s:
        return [_obs(
            "autopilot_runtime",
            "autopilot_cycle_health",
            "UNKNOWN",
            truth_state="UNKNOWN",
            available=False,
            healthy=False,
            criticality="HIGH",
            detail="Status persistido do Autopilot não foi fornecido.",
            family="autopilot",
        )]

    prov = _clean(provenance, 200)
    confirmed_provenance = prov.startswith("GitHub:")
    last_age = age_minutes(s.get("last_run"), now=now)
    market_open = bool(s.get("forex_market_open", False))
    max_runtime_age = 180.0 if market_open else 720.0
    explicit_healthy = s.get("healthy") if isinstance(s.get("healthy"), bool) else None
    app_ok = s.get("app_headless_ok") if isinstance(s.get("app_headless_ok"), bool) else None
    runtime_healthy = explicit_healthy if explicit_healthy is not None else app_ok

    rows = [_obs(
        "Autopilot Runtime",
        "autopilot_cycle_health",
        {
            "healthy": runtime_healthy,
            "operational_readiness": s.get("operational_readiness"),
            "version": s.get("version"),
        },
        truth_state="CONFIRMED" if confirmed_provenance else "UNKNOWN",
        available=True,
        healthy=runtime_healthy,
        criticality="HIGH",
        age=last_age,
        max_age=max_runtime_age,
        detail=f"Proveniência: {prov or 'não confirmada'}.",
        family="autopilot",
    )]

    blocked = bool(s.get("twelve_daily_blocked", False))
    rate_safe = s.get("twelve_rate_safe")
    rate_safe_bool = rate_safe if isinstance(rate_safe, bool) else None
    budget = s.get("twelve_budget") if isinstance(s.get("twelve_budget"), Mapping) else {}
    quota_pct = _quota_pct(budget)
    twelve_known = any(
        key in s
        for key in (
            "twelve_daily_blocked",
            "twelve_calls_this_run",
            "twelve_rate_safe",
            "twelve_budget",
        )
    )
    rows.append(_obs(
        "Twelve Data",
        "twelve_data_runtime",
        {
            "blocked": blocked,
            "block_type": _clean(s.get("twelve_block_type"), 100),
            "calls_this_run": s.get("twelve_calls_this_run"),
            "cache_hits": s.get("twelve_cache_hits"),
        },
        truth_state="CONFIRMED" if confirmed_provenance and twelve_known else "UNKNOWN",
        available=True if twelve_known else None,
        healthy=(not blocked and rate_safe_bool is not False) if twelve_known else None,
        criticality="HIGH",
        age=last_age,
        max_age=max_runtime_age,
        detail=_clean(s.get("twelve_daily_block_reason"), 500),
        cost_state="BLOCKED" if blocked else "CONTROLLED",
        quota_remaining_pct=quota_pct,
        family="market_data",
    ))

    scanner_fresh = int(_finite(s.get("scanner_fresh")) or 0)
    scanner_ready = s.get("scanner_ready")
    scanner_healthy = (
        bool(scanner_ready)
        if isinstance(scanner_ready, bool)
        else (scanner_fresh >= 5 if market_open else True)
    )
    rows.append(_obs(
        "Autopilot Scanner",
        "technical_scanner_freshness",
        scanner_fresh,
        truth_state="CONFIRMED" if confirmed_provenance else "UNKNOWN",
        available=True,
        healthy=scanner_healthy,
        criticality="HIGH",
        age=last_age,
        max_age=max_runtime_age,
        detail="Quantidade de pares técnicos considerados frescos no status persistido.",
        family="technical",
    ))

    map_fresh = int(_finite(s.get("market_map_fresh")) or 0)
    map_ready = s.get("market_map_ready")
    map_healthy = (
        bool(map_ready)
        if isinstance(map_ready, bool)
        else (map_fresh >= 5 if market_open else True)
    )
    rows.append(_obs(
        "Autopilot Market Map",
        "market_map_freshness",
        map_fresh,
        truth_state="CONFIRMED" if confirmed_provenance else "UNKNOWN",
        available=True,
        healthy=map_healthy,
        criticality="HIGH",
        age=last_age,
        max_age=max_runtime_age,
        family="technical",
    ))

    news_at = s.get("news_updated_at")
    news_age = age_minutes(news_at, now=now)
    news_known = bool(news_at) or "news_unique_stories" in s
    rows.append(_obs(
        "Currency News Runtime",
        "currency_news_freshness",
        {
            "updated_at": news_at,
            "unique_stories": s.get("news_unique_stories"),
        },
        truth_state="CONFIRMED" if confirmed_provenance and news_known else "UNKNOWN",
        available=True if news_known else None,
        healthy=(news_age is not None and news_age <= 120.0) if news_known else None,
        criticality="MEDIUM",
        age=news_age,
        max_age=120.0,
        family="news",
    ))

    nowcast = s.get("news_nowcast_v1") if isinstance(s.get("news_nowcast_v1"), Mapping) else {}
    if nowcast:
        runtime_state = _clean(nowcast.get("runtime_state"), 100).upper()
        provider_status = (
            nowcast.get("provider_status")
            if isinstance(nowcast.get("provider_status"), Mapping)
            else {}
        )
        provider_reason = _clean(
            nowcast.get("provider_retry_reason") or provider_status.get("reason"),
            100,
        ).upper()
        bad_states = {
            "AUTH_ERROR", "AUTH_COOLDOWN", "RATE_LIMITED", "RATE_LIMIT_COOLDOWN",
            "PROVIDER_UNAVAILABLE", "PROVIDER_COOLDOWN", "NETWORK_ERROR",
            "SYNC_ERROR", "PROVIDER_ERROR", "PROVIDER_PAYLOAD_ERROR",
            "TRUNCATED_PROVIDER_DATA",
        }
        healthy_states = {"CAPTURED", "THROTTLED"}
        available = runtime_state not in {"AUTH_ERROR", "AUTH_COOLDOWN", "PROVIDER_UNAVAILABLE"}
        healthy = runtime_state in healthy_states and provider_reason not in bad_states
        rows.append(_obs(
            "EODHD Economic Events",
            "eodhd_nowcast_runtime",
            {
                "runtime_state": runtime_state,
                "provider_reason": provider_reason,
                "snapshots": nowcast.get("snapshots"),
                "events": nowcast.get("events"),
            },
            truth_state="CONFIRMED" if confirmed_provenance else "UNKNOWN",
            available=available,
            healthy=healthy,
            criticality="HIGH",
            age=last_age,
            max_age=max_runtime_age,
            detail=(
                f"Retry após ~{int(_finite(nowcast.get('provider_retry_after_min')) or 0)} min."
                if _finite(nowcast.get("provider_retry_after_min")) is not None
                else ""
            ),
            cost_state=(
                "BLOCKED" if runtime_state in {"RATE_LIMITED", "RATE_LIMIT_COOLDOWN"}
                else "CONTROLLED"
            ),
            family="calendar_nowcast",
        ))
    return rows


def persisted_news_observations(
    payload: Mapping[str, Any] | None,
    *,
    provenance: Any = "",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    p = dict(payload or {})
    if not p:
        return []
    prov = _clean(provenance, 200)
    updated = p.get("updated_at")
    age = age_minutes(updated, now=now)
    stories = _finite(p.get("global_unique_stories"))
    return [_obs(
        "Currency News Intelligence",
        "currency_news_persisted",
        {
            "updated_at": updated,
            "unique_stories": stories,
            "shared_story_ratio": p.get("shared_story_ratio"),
        },
        truth_state="CONFIRMED" if prov.startswith("GitHub:") else "UNKNOWN",
        available=True,
        healthy=age is not None and age <= 120.0,
        criticality="MEDIUM",
        age=age,
        max_age=120.0,
        detail=f"Proveniência: {prov or 'não confirmada'}.",
        family="news",
    )]


def pair_matrix_observations(
    status: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    s = dict(status or {})
    ready = bool(s.get("ready", False))
    live_ready = bool(s.get("live_ready", False))
    source = _clean(s.get("source"), 100) or "none"
    fallback_age = _finite(s.get("fallback_age_minutes"))
    expected = int(_finite(s.get("pairs_expected")) or 7)
    built = int(_finite(s.get("pairs_built")) or 0)
    healthy = bool(ready and live_ready and built >= expected)
    return [_obs(
        "Pair Matrix Core",
        "pair_matrix_readiness",
        {
            "ready": ready,
            "live_ready": live_ready,
            "source": source,
            "pairs_built": built,
            "pairs_expected": expected,
        },
        truth_state="CONFIRMED",
        available=ready,
        healthy=healthy,
        criticality="CRITICAL",
        age=fallback_age if source == "runtime_snapshot" else None,
        max_age=120.0 if source == "runtime_snapshot" else None,
        detail=_clean(s.get("reason"), 500),
        family="decision_core",
    )]


def source_mesh_snapshot(
    *,
    macro_us: Mapping[str, Any] | None = None,
    next_event: Mapping[str, Any] | None = None,
    autopilot_status: Mapping[str, Any] | None = None,
    autopilot_provenance: Any = "",
    persisted_news: Mapping[str, Any] | None = None,
    news_provenance: Any = "",
    pair_matrix_status: Mapping[str, Any] | None = None,
    extra_observations: Sequence[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    rows.extend(fred_macro_observations(macro_us))
    rows.extend(calendar_observations(next_event))
    rows.extend(autopilot_observations(
        autopilot_status,
        provenance=autopilot_provenance,
        now=now,
    ))
    rows.extend(persisted_news_observations(
        persisted_news,
        provenance=news_provenance,
        now=now,
    ))
    rows.extend(pair_matrix_observations(pair_matrix_status))

    for raw in list(extra_observations or [])[:100]:
        if isinstance(raw, Mapping):
            item = dict(raw)
            item.setdefault("family", "extra")
            rows.append(item)

    family_counts: dict[str, int] = {}
    confirmed = 0
    unknown = 0
    fallbacks = 0
    for row in rows:
        family = _clean(row.get("family"), 80).lower() or "unknown"
        family_counts[family] = family_counts.get(family, 0) + 1
        if str(row.get("truth_state") or "").upper() == "CONFIRMED":
            confirmed += 1
        else:
            unknown += 1
        if row.get("available") is False or "fallback" in _clean(row.get("detail")).casefold():
            fallbacks += 1

    by_claim = {
        str(row.get("claim") or ""): row
        for row in rows
        if isinstance(row, Mapping)
    }
    auto = by_claim.get("autopilot_cycle_health", {})
    twelve = by_claim.get("twelve_data_runtime", {})
    scanner = by_claim.get("technical_scanner_freshness", {})
    market_map = by_claim.get("market_map_freshness", {})
    pair_matrix = by_claim.get("pair_matrix_readiness", {})
    market_open = bool(dict(autopilot_status or {}).get("forex_market_open", False))
    live_components = (auto, twelve, scanner, market_map, pair_matrix)
    live_truth_confirmed = all(
        str(item.get("truth_state") or "").upper() == "CONFIRMED"
        for item in live_components
    )
    live_healthy = all(item.get("healthy") is True for item in live_components)
    market_live_confirmed = bool(market_open and live_truth_confirmed and live_healthy)
    if market_live_confirmed:
        market_state = "LIVE_CONFIRMED"
    elif not market_open and str(auto.get("truth_state") or "").upper() == "CONFIRMED":
        market_state = "MARKET_CLOSED"
    elif any(item.get("available") is False for item in live_components):
        market_state = "DEGRADED"
    elif rows:
        market_state = "UNCONFIRMED"
    else:
        market_state = "UNKNOWN"

    return {
        "schema": SCHEMA,
        "observations": rows,
        "observation_count": len(rows),
        "confirmed_observations": confirmed,
        "unknown_observations": unknown,
        "fallback_or_unavailable": fallbacks,
        "families": family_counts,
        "market_state": market_state,
        "market_open": market_open,
        "market_live_confirmed": market_live_confirmed,
        "market_live_rule": (
            "Requires confirmed and healthy Autopilot, Twelve Data, scanner, market map and live Pair Matrix while market is open."
        ),
        "performs_network_request": False,
        "changes_market_scores": False,
        "automatic_source_switch": False,
        "automatic_paid_fallback": False,
        "real_orders_enabled": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "age_minutes",
    "fred_macro_observations",
    "calendar_observations",
    "autopilot_observations",
    "persisted_news_observations",
    "pair_matrix_observations",
    "source_mesh_snapshot",
]
