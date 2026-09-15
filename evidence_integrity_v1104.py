"""USD Macro Pro V11.0.4 — Evidence Integrity & No-Trade State.

Pure helpers: no API calls and no Streamlit dependency.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

SWEEP_MAX_AGE_MIN = 360.0


def tf_is_fresh(readiness: Mapping[str, Any] | None, tf: str) -> bool:
    r = dict(readiness or {})
    tfs = dict(r.get("timeframes", {}) or {})
    return bool((tfs.get(str(tf).lower(), {}) or {}).get("fresh", False))


def masked_technical_status(
    status: Any,
    tf: str,
    readiness: Mapping[str, Any] | None,
) -> tuple[str, bool]:
    """Old technical reads stay visible as history, never as current evidence."""
    raw = str(status or "—")
    if tf_is_fresh(readiness, tf):
        return raw, True
    return f"⏳ {str(tf).upper()} ANTIGO — NÃO USAR", False


def _parse_dt(value: Any) -> datetime | None:
    if value in (None, "", 0, 0.0):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def age_minutes(value: Any, now: datetime | None = None) -> float | None:
    dt = _parse_dt(value)
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return max(0.0, (ref.astimezone(timezone.utc) - dt).total_seconds() / 60.0)


def sweep_freshness(
    sweep_time: Any,
    *,
    now: datetime | None = None,
    max_age_min: float = SWEEP_MAX_AGE_MIN,
) -> dict[str, Any]:
    age = age_minutes(sweep_time, now)
    current = age is not None and age <= float(max_age_min)
    if age is None:
        label = "⚪ SWEEP SEM TIMESTAMP — HISTÓRICO"
    elif current:
        label = f"🟢 SWEEP RECENTE · {age:.0f} min"
    else:
        label = f"⏳ SWEEP ANTIGO · {age:.0f} min — NÃO USAR COMO CONFIRMAÇÃO"
    return {"age_minutes": age, "current": bool(current), "label": label}


def select_operational_context(packs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Never calls a blocked/zero-priority pair the best opportunity."""
    rows = list(packs or [])
    executable = [p for p in rows if bool(p.get("executable", False))]
    if executable:
        best = max(executable, key=lambda p: float(p.get("priority", 0) or 0))
        return {"no_trade": False, "best": best, "label": str(best.get("pair", "—"))}

    candidates = [
        p for p in rows
        if not str(p.get("state", "")).startswith("🔴")
        and str(p.get("side", "WAIT")) != "WAIT"
        and float(p.get("priority", 0) or 0) > 0
    ]
    if candidates:
        best = max(candidates, key=lambda p: float(p.get("priority", 0) or 0))
        return {"no_trade": False, "best": best, "label": str(best.get("pair", "—"))}

    fallback = max(rows, key=lambda p: float(p.get("priority", 0) or 0)) if rows else None
    return {
        "no_trade": True,
        "best": fallback,
        "label": "NENHUM SETUP",
        "state": "🚫 NO-TRADE",
        "reason": "Nenhum dos 7 pares passou pelos hard gates/frescor para execução agora.",
    }
