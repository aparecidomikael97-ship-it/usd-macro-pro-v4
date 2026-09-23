"""Compatibility bridge from the legacy AtlasQuant scanner state to P0 coverage.

Read-only: it does not fetch data, change strategy output or grant execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_instrument_registry import FX_28, normalize_fx_symbol
from atlasquant_scanner_coverage import PairCoverage, scanner_coverage

def _epoch(value: Any) -> datetime | None:
    if value in (None, "", 0, 0.0):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        text = str(value).strip()
        if text.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except Exception:
        return None

def legacy_pair_coverage(raw: Mapping[str, Any], *, now: datetime | None = None,
                         max_age_minutes: float = 60.0) -> PairCoverage:
    tech = dict(raw.get("tecnico", {}) or {})
    available = bool(tech.get("disponivel", False))
    stamp = _epoch(raw.get("m15_fetched_at", raw.get("processado_em")))
    current = now or datetime.now(timezone.utc)
    age = None if stamp is None else (current - stamp).total_seconds() / 60.0
    fresh = bool(age is not None and 0.0 <= age < float(max_age_minutes))
    # Existing scanner's normalized OHLC + availability is the minimum legacy
    # quality evidence. P0 Data Quality can replace this flag with stronger evidence.
    quality_ok = bool(available and raw.get("data_quality_ok", True))
    return PairCoverage(
        symbol=str(raw.get("_canonical_symbol", "")),
        analyzed=available,
        data_fresh=fresh,
        quality_ok=quality_ok,
        updated_at=stamp,
    )

def coverage_from_legacy_state(scanner_state: Mapping[str, Any] | None,
                               *, now: datetime | None = None,
                               max_age_minutes: float = 60.0) -> dict[str, object]:
    results = dict((scanner_state or {}).get("resultados", {}) or {})
    rows: dict[str, PairCoverage] = {}
    invalid_keys: list[str] = []
    for pair, raw in results.items():
        try:
            symbol = normalize_fx_symbol(str(pair))
        except ValueError:
            invalid_keys.append(str(pair))
            continue
        if symbol not in FX_28:
            continue
        payload = dict(raw or {})
        payload["_canonical_symbol"] = symbol
        rows[symbol] = legacy_pair_coverage(payload, now=now, max_age_minutes=max_age_minutes)
    summary = scanner_coverage(rows)
    summary["invalid_legacy_keys"] = sorted(invalid_keys)
    return summary
