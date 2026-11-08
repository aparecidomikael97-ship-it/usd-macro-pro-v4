"""LAB: pre-news estimate conditioned on a verified *previous* release vintage.

The original AtlasQuant nowcast conditions analogs on a leading-signal score.
This isolated experiment also conditions on the gap between consensus and the
previous published figure. It NEVER issues a pair bias or an order.

All snapshots, including the prior figure and historical outcomes, must have
evidence that was available at the historical forecast cutoff. This module
does not itself verify the authenticity of an external document or timestamp.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
import re
from typing import Any, Iterable

from atlasquant_news_nowcast import OUTCOMES, classify_surprise


SCHEMA = "ATLASQUANT_NEWS_PREVIOUS_CONTEXT_LAB_V1"
_SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")
_MONTH = re.compile(r"(\d{4})-(0[1-9]|1[0-2])\Z")


def _utc(label: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label}: fuso horário explícito obrigatório")
    return value.astimezone(timezone.utc)


def _number(label: str, value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: número obrigatório") from exc
    if not isfinite(out):
        raise ValueError(f"{label}: número não finito")
    return out


def _previous_month(target: str) -> str:
    match = _MONTH.fullmatch(target)
    if not match:
        raise ValueError("target_period deve ser YYYY-MM; outra periodicidade ainda não foi validada")
    year, month = int(match.group(1)), int(match.group(2))
    return f"{year-1}-12" if month == 1 else f"{year}-{month-1:02d}"


@dataclass(frozen=True)
class PreReleaseSnapshot:
    country: str
    indicator: str
    metric: str
    unit: str
    target_period: str
    previous_period: str
    scheduled_at: datetime
    captured_at: datetime
    consensus: float
    previous: float
    previous_published_at: datetime
    previous_captured_at: datetime
    previous_source_url: str
    previous_sha256: str
    previous_original_verified: bool
    signal_score: float
    tolerance: float = 0.0


@dataclass(frozen=True)
class PastOutcome:
    snapshot: PreReleaseSnapshot
    actual: float
    actual_available_at: datetime
    actual_sha256: str
    actual_original_verified: bool


def validate_snapshot(snapshot: PreReleaseSnapshot) -> None:
    for label in ("country", "indicator", "metric", "unit"):
        if not str(getattr(snapshot, label) or "").strip():
            raise ValueError(f"{label}: identificação obrigatória")
    if snapshot.previous_period != _previous_month(snapshot.target_period):
        raise ValueError("previous_period não corresponde ao mês anterior")
    scheduled = _utc("scheduled_at", snapshot.scheduled_at)
    captured = _utc("captured_at", snapshot.captured_at)
    prior_published = _utc("previous_published_at", snapshot.previous_published_at)
    prior_captured = _utc("previous_captured_at", snapshot.previous_captured_at)
    if not prior_published <= prior_captured <= captured < scheduled:
        raise ValueError("valor anterior não comprovadamente disponível antes da previsão")
    if not str(snapshot.previous_source_url).startswith("https://"):
        raise ValueError("previous_source_url deve identificar fonte HTTPS")
    if type(snapshot.previous_original_verified) is not bool:
        raise ValueError("previous_original_verified deve ser booleano explícito")
    if (snapshot.previous_original_verified or str(snapshot.previous_sha256 or "")) and not _SHA256.fullmatch(
        str(snapshot.previous_sha256)
    ):
        raise ValueError("previous_sha256 deve identificar os bytes originais, nunca ser inventado")
    _number("consensus", snapshot.consensus)
    _number("previous", snapshot.previous)
    score = _number("signal_score", snapshot.signal_score)
    tolerance = _number("tolerance", snapshot.tolerance)
    if not -1 <= score <= 1 or tolerance < 0:
        raise ValueError("signal_score ou tolerance inválido")


def validate_outcome(row: PastOutcome) -> None:
    validate_snapshot(row.snapshot)
    _number("actual", row.actual)
    available = _utc("actual_available_at", row.actual_available_at)
    if available < _utc("scheduled_at", row.snapshot.scheduled_at):
        raise ValueError("actual disponível antes do horário de divulgação declarado")
    if type(row.actual_original_verified) is not bool:
        raise ValueError("actual_original_verified deve ser booleano explícito")
    if (row.actual_original_verified or str(row.actual_sha256 or "")) and not _SHA256.fullmatch(
        str(row.actual_sha256)
    ):
        raise ValueError("actual_sha256 deve identificar os bytes originais, nunca ser inventado")


def _waiting(snapshot: PreReleaseSnapshot, reason: str, *, history_samples: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": reason,
        "indicator": snapshot.indicator,
        "target_period": snapshot.target_period,
        "history_samples": history_samples,
        "analog_samples": 0,
        "estimate": None,
        "probabilities": None,
        "previous": float(snapshot.previous),
        "consensus": float(snapshot.consensus),
        "consensus_minus_previous": float(snapshot.consensus) - float(snapshot.previous),
        "confidence_0_to_10": None,
        "pair_bias": None,
        "automatic_execution": False,
        "calibrated": False,
        "research_only": True,
        "lookahead_used": False,
    }


def estimate_with_previous_context(
    snapshot: PreReleaseSnapshot,
    history: Iterable[PastOutcome],
    *,
    gap_scale: float,
    min_history: int = 40,
    min_analogs: int = 20,
    alpha: float = 1.0,
) -> dict[str, Any]:
    """Use prior-value gap only as an *experimental* analog-matching feature.

    `gap_scale` must be chosen per indicator/metric/unit from training data;
    it is not a cross-country constant and is not learned from future outcomes.
    """
    validate_snapshot(snapshot)
    scale = _number("gap_scale", gap_scale)
    smoothing = _number("alpha", alpha)
    if scale <= 0 or smoothing <= 0 or min_history < 2 or min_analogs < 2:
        raise ValueError("parâmetros de pesquisa inválidos")
    if not snapshot.previous_original_verified:
        return _waiting(snapshot, "WAIT_PREVIOUS_ORIGINAL")

    cutoff = _utc("captured_at", snapshot.captured_at)
    key = (snapshot.country, snapshot.indicator, snapshot.metric, snapshot.unit)
    eligible: list[PastOutcome] = []
    seen_periods: set[str] = set()
    for row in history:
        validate_outcome(row)
        previous = row.snapshot
        row_key = (previous.country, previous.indicator, previous.metric, previous.unit)
        if row_key != key:
            continue
        if _utc("scheduled_at", previous.scheduled_at) >= cutoff:
            continue
        if _utc("actual_available_at", row.actual_available_at) > cutoff:
            continue
        if not previous.previous_original_verified or not row.actual_original_verified:
            continue
        if previous.target_period in seen_periods:
            return _waiting(snapshot, "WAIT_DUPLICATE_HISTORY", history_samples=len(eligible))
        seen_periods.add(previous.target_period)
        eligible.append(row)

    if len(eligible) < min_history:
        return _waiting(snapshot, "INSUFFICIENT_VERIFIED_HISTORY", history_samples=len(eligible))

    target_gap = (snapshot.consensus - snapshot.previous) / scale

    def distance(row: PastOutcome) -> tuple[float, datetime]:
        prior = row.snapshot
        gap = (prior.consensus - prior.previous) / scale
        return (
            abs(prior.signal_score - snapshot.signal_score) + abs(gap - target_gap),
            _utc("scheduled_at", prior.scheduled_at),
        )

    nearest = sorted(eligible, key=distance)[: min(min_analogs, len(eligible))]
    counts = {label: 0 for label in OUTCOMES}
    for row in nearest:
        counts[classify_surprise(row.actual, row.snapshot.consensus, row.snapshot.tolerance)] += 1
    denominator = len(nearest) + smoothing * len(OUTCOMES)
    probabilities = {label: (counts[label] + smoothing) / denominator for label in OUTCOMES}
    residual = sum(row.actual - row.snapshot.consensus for row in nearest) / len(nearest)
    max_prob = max(probabilities.values())
    winners = [label for label, probability in probabilities.items() if abs(probability - max_prob) < 1e-12]
    result = _waiting(snapshot, "RESEARCH_ESTIMATE", history_samples=len(eligible))
    result.update({
        "analog_samples": len(nearest),
        "estimate": round(snapshot.consensus + residual, 6),
        "probabilities": probabilities,
        "top_class": winners[0] if len(winners) == 1 else "TIE",
        "gap_scale": scale,
        "analog_method": "NEAREST_SCORE_PLUS_PREVIOUS_GAP_UNCALIBRATED",
        "previous_feature_used": True,
        "profit_probability": None,
        "market_reaction_predicted": False,
    })
    return result


def walk_forward_previous_context(
    history: Iterable[PastOutcome],
    *,
    gap_scale: float,
    min_history: int = 40,
    min_analogs: int = 20,
) -> dict[str, Any]:
    """Compare frozen earlier forecasts with consensus and previous baselines."""
    rows = list(history)
    for row in rows:
        validate_outcome(row)
    rows.sort(key=lambda row: _utc("scheduled_at", row.snapshot.scheduled_at))
    forecasts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in rows:
        result = estimate_with_previous_context(
            row.snapshot, rows, gap_scale=gap_scale,
            min_history=min_history, min_analogs=min_analogs,
        )
        if result["state"] != "RESEARCH_ESTIMATE":
            skipped.append({"period": row.snapshot.target_period, "reason": result["state"]})
            continue
        estimated = float(result["estimate"])
        actual = float(row.actual)
        forecasts.append({
            "period": row.snapshot.target_period,
            "captured_at": _utc("captured_at", row.snapshot.captured_at).isoformat(),
            "actual": actual,
            "estimate": estimated,
            "consensus": row.snapshot.consensus,
            "previous": row.snapshot.previous,
            "estimate_abs_error": abs(estimated - actual),
            "consensus_abs_error": abs(row.snapshot.consensus - actual),
            "previous_abs_error": abs(row.snapshot.previous - actual),
            "lookahead_used": False,
        })

    def mae(field: str) -> float | None:
        return (round(sum(row[field] for row in forecasts) / len(forecasts), 6)
                if forecasts else None)

    return {
        "schema": SCHEMA,
        "forecast_samples": len(forecasts),
        "skipped_samples": len(skipped),
        "mae_estimate": mae("estimate_abs_error"),
        "mae_consensus": mae("consensus_abs_error"),
        "mae_previous": mae("previous_abs_error"),
        "forecasts": forecasts,
        "skipped": skipped,
        "historical_advantage_proven": False,
        "calibrated": False,
        "pair_bias": None,
        "automatic_execution": False,
        "lookahead_used": False,
        "interpretation": "Comparação apenas de pesquisa; exige originais P-I-T reais e validação fora da amostra.",
    }


__all__ = [
    "SCHEMA", "PreReleaseSnapshot", "PastOutcome", "validate_snapshot", "validate_outcome",
    "estimate_with_previous_context", "walk_forward_previous_context",
]
