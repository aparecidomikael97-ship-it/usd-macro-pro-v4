"""ECB daily FX-reference forward *outcomes*, computed after the fact, LAB only.

This transforms a structurally consistent archived ECB CSV into ex-post
base/quote return labels for 28 FX pairs, not into directional forecasts.
An archive digest checks internal integrity but NOT independent ECB provenance,
point-in-time availability or market execution prices.

This module makes NO HTTP request, no file writes, no schedules, no orders,
and cannot feed verified OOS, live radar, probabilities or production.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_ecb_sdmx_archive_lab import (
    STATE as ARCHIVE_STATE, validate_ecb_archived_csv_lab,
)

SCHEMA = "ATLASQUANT_TRADER_ECB_REFERENCE_FORWARD_OUTCOMES_LAB_V1"
STATE = "LAB_ECB_REFERENCE_EXPOST_OUTCOMES"
DENIED = "LAB_ECB_REFERENCE_OUTCOMES_REFUSED"
HORIZONS = ("D1", "W1", "MN1")
# Predeclared calendar-day targets. The first ACTUAL official reference at or
# after each target is used, bounded to prevent arbitrary cherry-picking.
TARGET_CALENDAR_DAYS = {"D1": 1, "W1": 7, "MN1": 30}
MAX_CALENDAR_DAYS = {"D1": 4, "W1": 10, "MN1": 42}
DEADBAND_BP = Decimal("5")
EXTREME_MOVE_BP = Decimal("2500")
ROUND_BP = Decimal("0.01")


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": DENIED, "reason": reason,
        "rows": [], "counts_by_horizon": {},
        "reference_rate_origin_independently_verified": False,
        "historical_point_in_time_available_proven": False,
        "independent_broker_spot_quotes_verified": 0,
        "can_feed_live_bias": False, "can_feed_real_oos": False,
        "forecast_accuracy_proven": False, "probability_calibrated": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def _rate(references: dict[str, str], currency: str) -> Decimal:
    # ECB publishes C units per EUR, not EUR units per C.
    return Decimal("1") if currency == "EUR" else Decimal(references[currency])


def build_ecb_reference_forward_outcomes_lab(
    raw: bytes, manifest: Any, *, anchor_date: str, evaluated_at: datetime,
) -> dict[str, Any]:
    """Report what happened AFTER a historical anchor, never what to trade.

    The returned start and settlement references are retrospective observations.
    No attempt is made to prove the rates were knowable before a historical
    forecast, or that six daily samples validate D1/W1/MN1 predictability.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation clock must include a timezone")
    verified = validate_ecb_archived_csv_lab(
        raw, manifest, evaluated_at=evaluated_at,
    )
    if verified["state"] != ARCHIVE_STATE:
        return _refuse("Source archive rejected: " + str(verified["reason"]))
    if not isinstance(anchor_date, str) or len(anchor_date) != 10:
        return _refuse("Anchor must be an exact published YYYY-MM-DD reference date")
    try:
        anchor = date.fromisoformat(anchor_date)
    except ValueError:
        return _refuse("Invalid anchor date")
    if anchor.isoformat() != anchor_date:
        return _refuse("Non-canonical anchor date")
    references = verified["reference_quotes_by_date"]
    if anchor_date not in references:
        return _refuse("No actual ECB reference on requested anchor date")
    available = [date.fromisoformat(day) for day in verified["observation_dates"]]
    first = references[anchor_date]
    rows = []
    counts = {}
    for horizon in HORIZONS:
        target = anchor + timedelta(days=TARGET_CALENDAR_DAYS[horizon])
        maximum = anchor + timedelta(days=MAX_CALENDAR_DAYS[horizon])
        # Deterministic first qualifying publication only: no peeking at moves.
        settled = next((day for day in available if target <= day <= maximum), None)
        settled_rates = references[settled.isoformat()] if settled else None
        counts[horizon] = {"with_reference_outcome": 0, "awaiting_history": 0,
                           "needs_outlier_review": 0}
        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            row: dict[str, Any] = {
                "pair": pair, "horizon": horizon, "anchor_date": anchor_date,
                "predeclared_target_date": target.isoformat(),
                "last_permitted_reference_date": maximum.isoformat(),
                "actual_reference_date": settled.isoformat() if settled else None,
                "elapsed_calendar_days": (settled - anchor).days if settled else None,
                "source_type": "ECB_EUR_REFERENCE_NOT_EXECUTABLE_SPOT",
                "direction_is_forecast": False,
                "reference_return_bp": None, "realized_side": None,
                "state": "AGUARDANDO_HISTORICO",
            }
            if settled_rates is None:
                counts[horizon]["awaiting_history"] += 1
            else:
                with localcontext() as ctx:
                    ctx.prec = 40
                    original = _rate(first, quote) / _rate(first, base)
                    final = _rate(settled_rates, quote) / _rate(settled_rates, base)
                    move_bp = (final / original - 1) * Decimal("10000")
                    row["reference_return_bp"] = str(
                        move_bp.quantize(ROUND_BP, rounding=ROUND_HALF_EVEN)
                    )
                    if abs(move_bp) > EXTREME_MOVE_BP:
                        row["state"] = "EXPOST_EXTREME_MOVE_REVIEW_REQUIRED"
                        row["realized_side"] = None
                        counts[horizon]["needs_outlier_review"] += 1
                    else:
                        row["state"] = "EXPOST_REFERENCE_ONLY"
                        row["realized_side"] = (
                            "ALTA" if move_bp > DEADBAND_BP else
                            "BAIXA" if move_bp < -DEADBAND_BP else "NEUTRO"
                        )
                        counts[horizon]["with_reference_outcome"] += 1
            rows.append(row)
    return {
        **_refuse(""), "state": STATE, "reason": None,
        "anchor_date": anchor_date, "observation_dates": verified["observation_dates"],
        "archive_body_sha256": verified["body_sha256"],
        "raw_bytes_sha256_matched": True,
        "reference_original_eur_series": verified["original_eur_series"],
        "algebraic_crosses_not_independent": 21,
        "fixed_neutral_band_bp": str(DEADBAND_BP),
        "fixed_target_calendar_days": dict(TARGET_CALENDAR_DAYS),
        "rows": rows, "counts_by_horizon": counts,
        "research_note": (
            "Ex-post ECB informative reference comparisons only. The 21 non-EUR "
            "crosses are derived, not independent quote evidence. This CSV was "
            "captured retrospectively; neither historical availability nor "
            "predictive directional accuracy is independently proven."
        ),
    }


__all__ = ["SCHEMA", "STATE", "DENIED", "HORIZONS",
           "TARGET_CALENDAR_DAYS", "DEADBAND_BP",
           "build_ecb_reference_forward_outcomes_lab"]
