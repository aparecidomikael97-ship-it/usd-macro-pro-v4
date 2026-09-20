"""AtlasQuant Quarterly Context Engine.

Deterministic research layer inspired by ICT-style time partitioning.
It divides the New York trading day into four 6-hour quarters and observes
whether the current quarter sweeps/reclaims the previous quarter range.

Important:
- quarter labels are time partitions, not a prediction model;
- phase names are educational hints, never assumptions about what price "must" do;
- output is observational and never changes Gate, Score Mestre, weights or orders.
"""
from __future__ import annotations

from typing import Any
import math
import pandas as pd

SCHEMA = "ATLASQUANT_QUARTERLY_CONTEXT_V1"
DEFAULT_TZ = "America/New_York"
MIN_PREVIOUS_CANDLES = 8

_PHASES = {
    1: "REFERÊNCIA / CONSTRUÇÃO",
    2: "EXPANSÃO / VARREDURA POSSÍVEL",
    3: "DISTRIBUIÇÃO / CONTINUAÇÃO POSSÍVEL",
    4: "CONCLUSÃO / REPRECIFICAÇÃO POSSÍVEL",
}


def _frame(candles: Any) -> pd.DataFrame:
    if candles is None:
        return pd.DataFrame()
    try:
        d = candles.copy() if isinstance(candles, pd.DataFrame) else pd.DataFrame(list(candles))
    except Exception:
        return pd.DataFrame()
    if d.empty or "datetime" not in d.columns:
        return pd.DataFrame()
    d["datetime"] = pd.to_datetime(d["datetime"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close"):
        if col not in d.columns:
            return pd.DataFrame()
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["datetime", "open", "high", "low", "close"]).sort_values("datetime")
    return d.reset_index(drop=True)


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else float(default)
    except Exception:
        return float(default)


def build_quarterly_snapshot(
    candles: Any,
    side: str = "WAIT",
    *,
    timezone: str = DEFAULT_TZ,
) -> dict[str, Any]:
    d = _frame(candles)
    if d.empty:
        return {
            "schema": SCHEMA,
            "available": False,
            "quarter": None,
            "direction": "INDISPONÍVEL",
            "quality": 0.0,
            "decision_effect": False,
            "detail": "Sem candles válidos para calcular o contexto Quarterly.",
        }

    try:
        local = d["datetime"].dt.tz_convert(timezone)
    except Exception:
        return {
            "schema": SCHEMA,
            "available": False,
            "quarter": None,
            "direction": "INDISPONÍVEL",
            "quality": 0.0,
            "decision_effect": False,
            "detail": "Timezone inválido para o contexto Quarterly.",
        }

    latest = local.iloc[-1]
    minute_of_day = int(latest.hour) * 60 + int(latest.minute)
    quarter = min(4, max(1, minute_of_day // 360 + 1))
    day_anchor = latest.normalize()
    q_start = day_anchor + pd.Timedelta(hours=(quarter - 1) * 6)
    q_end = q_start + pd.Timedelta(hours=6)
    prev_start = q_start - pd.Timedelta(hours=6)

    work = d.copy()
    work["_local"] = local
    previous = work[(work["_local"] >= prev_start) & (work["_local"] < q_start)].copy()
    current = work[(work["_local"] >= q_start) & (work["_local"] < q_end)].copy()

    if len(previous) < MIN_PREVIOUS_CANDLES or current.empty:
        return {
            "schema": SCHEMA,
            "available": False,
            "quarter": quarter,
            "quarter_label": f"Q{quarter}",
            "phase_hint": _PHASES[quarter],
            "phase_is_predictive": False,
            "direction": "INDISPONÍVEL",
            "quality": 0.0,
            "decision_effect": False,
            "detail": "Histórico insuficiente para comparar o quarter atual com o quarter anterior.",
        }

    prev_high = float(previous["high"].max())
    prev_low = float(previous["low"].min())
    current_high = float(current["high"].max())
    current_low = float(current["low"].min())
    last_close = float(current.iloc[-1]["close"])

    sweep_high = current_high > prev_high
    sweep_low = current_low < prev_low
    reclaim_high = sweep_high and last_close < prev_high
    reclaim_low = sweep_low and last_close > prev_low

    conflict = reclaim_high and reclaim_low
    if conflict:
        direction = "NEUTRO"
        event = "VARREDURA DOS DOIS LADOS"
        vote = 0
    elif reclaim_low:
        direction = "COMPRA"
        event = "SSL VARRIDA + RECLAIM"
        vote = 1
    elif reclaim_high:
        direction = "VENDA"
        event = "BSL VARRIDA + RECLAIM"
        vote = -1
    elif sweep_low:
        direction = "NEUTRO"
        event = "SSL VARRIDA — RECLAIM PENDENTE"
        vote = 0
    elif sweep_high:
        direction = "NEUTRO"
        event = "BSL VARRIDA — RECLAIM PENDENTE"
        vote = 0
    else:
        direction = "NEUTRO"
        event = "SEM VARREDURA CONFIRMADA"
        vote = 0

    coverage = min(1.0, len(previous) / 24.0)
    current_coverage = min(1.0, len(current) / 24.0)
    quality = 100.0 * (0.70 * coverage + 0.30 * max(0.25, current_coverage))
    if conflict:
        quality *= 0.70

    side_u = str(side or "").upper()
    side_alignment = (
        "ALINHADO" if (side_u == "BUY" and vote > 0) or (side_u == "SELL" and vote < 0)
        else "CONTRÁRIO" if (side_u == "BUY" and vote < 0) or (side_u == "SELL" and vote > 0)
        else "NEUTRO"
    )

    return {
        "schema": SCHEMA,
        "available": True,
        "quarter": quarter,
        "quarter_label": f"Q{quarter}",
        "phase_hint": _PHASES[quarter],
        "phase_is_predictive": False,
        "quarter_start": q_start.isoformat(),
        "quarter_end": q_end.isoformat(),
        "previous_quarter_start": prev_start.isoformat(),
        "previous_high": prev_high,
        "previous_low": prev_low,
        "current_high": current_high,
        "current_low": current_low,
        "last_close": last_close,
        "sweep_high": bool(sweep_high),
        "sweep_low": bool(sweep_low),
        "reclaim_high": bool(reclaim_high),
        "reclaim_low": bool(reclaim_low),
        "event": event,
        "direction": direction,
        "direction_vote": vote,
        "side_alignment": side_alignment,
        "quality": round(max(0.0, min(100.0, quality)), 1),
        "previous_candles": int(len(previous)),
        "current_candles": int(len(current)),
        "decision_effect": False,
        "changes_gate": False,
        "changes_score_mestre": False,
        "real_orders_enabled": False,
        "detail": (
            "Quarterly é usado como leitura temporal/liqüidez: divide o dia em quatro janelas "
            "de 6h em Nova York e observa sweep/reclaim do range anterior. "
            "A fase não presume comportamento futuro."
        ),
    }


__all__ = ["SCHEMA", "DEFAULT_TZ", "build_quarterly_snapshot"]
