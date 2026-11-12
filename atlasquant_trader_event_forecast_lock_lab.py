"""Pure LAB: freeze a pre-news research prediction, later score it unchanged.

The SHA digest detects *accidental* mutation of the supplied forecast payload.
It is NOT a signature, independently witnessed timestamp, source custody, or
proof of out-of-sample accuracy. All results are documentary research only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES
from atlasquant_trader_g8_event_relevance_lab import METRIC_UNITS

SCHEMA = "ATLASQUANT_TRADER_EVENT_FORECAST_LOCK_AND_SCORE_LAB_V1"
_ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{2,63}\Z")
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MODEL = re.compile(r"[A-Za-z0-9_.-]{2,64}\Z")


@dataclass(frozen=True)
class ForecastDraft:
    event_id: str
    currency: str
    metric: str
    target_period: str
    unit: str
    scheduled_release_at: datetime
    forecast_captured_at: datetime
    previous_value: str
    previous_available_at: datetime
    consensus_value: str
    consensus_available_at: datetime
    model_estimate: str | None
    model_version: str | None
    previous_source_sha256_claim: str | None
    consensus_source_sha256_claim: str | None


@dataclass(frozen=True)
class ForecastLock:
    canonical_payload_json: str
    payload_sha256: str


@dataclass(frozen=True)
class ActualClaim:
    event_id: str
    currency: str
    metric: str
    target_period: str
    unit: str
    value: str
    first_published_at: datetime
    captured_at: datetime
    source_sha256_claim: str | None = None


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _decimal(value: Any) -> Decimal | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 32:
        return None
    try:
        v = Decimal(value)
    except InvalidOperation:
        return None
    return v if v.is_finite() and abs(v) <= Decimal("1000000000") else None


def _hash_claim(value: Any) -> bool:
    return value is None or isinstance(value, str) and _HEX.fullmatch(value) is not None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FORECAST_BLOCKED", "reason": reason,
        "lock": None, "forecast_sha256": None, "scored_claim_sha256": None,
        "model_abs_error_documentary": None,
        "consensus_abs_error_documentary": None,
        "previous_abs_error_documentary": None,
        "actual_minus_consensus_documentary": None,
        "model_better_than_consensus_documentary": None,
        "forecast_origin_independently_witnessed": False,
        "source_originals_and_clock_independently_verified": False,
        "model_hyperparameters_frozen_independently_verified": False,
        "outcome_extracted_from_official_original_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "fx_bias": None, "index_bias": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def freeze_pre_event_forecast_lab(draft: Any, *, as_of_utc: Any) -> dict[str, Any]:
    """Create a hashable study snapshot only before its scheduled release."""
    out = _base("INVALID_DRAFT_OR_CLOCK")
    now = _utc(as_of_utc)
    if not isinstance(draft, ForecastDraft) or now is None:
        return out
    release, captured = _utc(draft.scheduled_release_at), _utc(draft.forecast_captured_at)
    previous_at = _utc(draft.previous_available_at)
    consensus_at = _utc(draft.consensus_available_at)
    if (release is None or captured is None or previous_at is None or consensus_at is None
            or not previous_at <= captured <= now < release
            or not consensus_at <= captured
            or not isinstance(draft.event_id, str) or _ID.fullmatch(draft.event_id) is None
            or draft.currency not in CURRENCIES
            or not isinstance(draft.metric, str)
            or METRIC_UNITS.get(draft.metric) != draft.unit
            or not isinstance(draft.target_period, str)
            or _MONTH.fullmatch(draft.target_period) is None
            or _decimal(draft.previous_value) is None
            or _decimal(draft.consensus_value) is None
            or not _hash_claim(draft.previous_source_sha256_claim)
            or not _hash_claim(draft.consensus_source_sha256_claim)):
        return out
    if draft.model_estimate is None:
        if draft.model_version is not None:
            return out
    elif (_decimal(draft.model_estimate) is None
          or not isinstance(draft.model_version, str)
          or _MODEL.fullmatch(draft.model_version) is None):
        return out
    record = {
        "schema": SCHEMA,
        "event_id": draft.event_id, "currency": draft.currency,
        "metric": draft.metric, "target_period": draft.target_period,
        "unit": draft.unit,
        "scheduled_release_utc": release.isoformat(),
        "forecast_captured_utc": captured.isoformat(),
        "previous_available_utc": previous_at.isoformat(),
        "consensus_available_utc": consensus_at.isoformat(),
        "previous_value": str(_decimal(draft.previous_value)),
        "consensus_value": str(_decimal(draft.consensus_value)),
        "model_estimate": (str(_decimal(draft.model_estimate))
                           if draft.model_estimate is not None else None),
        "model_version": draft.model_version,
        "previous_source_sha256_claim": draft.previous_source_sha256_claim,
        "consensus_source_sha256_claim": draft.consensus_source_sha256_claim,
    }
    raw = _canonical(record)
    digest = sha256(raw.encode("ascii")).hexdigest()
    out.update({
        "state": "LAB_PRE_EVENT_FORECAST_LOCKED_DOCUMENTARY_ONLY",
        "reason": "HASHED_FORECAST_NOT_AN_INDEPENDENT_TIMESTAMP_OR_MODEL_WITNESS",
        "lock": ForecastLock(raw, digest), "forecast_sha256": digest,
    })
    return out


def score_locked_forecast_lab(
    locked: Any, actual: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Score an unchanged pre-event snapshot against a later *claimed* actual."""
    out = _base("INVALID_LOCK_ACTUAL_OR_CLOCK")
    now = _utc(as_of_utc)
    if (not isinstance(locked, ForecastLock) or not isinstance(actual, ActualClaim)
            or now is None or not isinstance(locked.canonical_payload_json, str)
            or not isinstance(locked.payload_sha256, str)
            or _HEX.fullmatch(locked.payload_sha256) is None
            or len(locked.canonical_payload_json) > 4096
            or sha256(locked.canonical_payload_json.encode("utf-8")).hexdigest()
            != locked.payload_sha256):
        return out
    try:
        raw = json.loads(locked.canonical_payload_json)
        if (not isinstance(raw, dict) or _canonical(raw) != locked.canonical_payload_json
                or raw.get("schema") != SCHEMA):
            return out
    except (ValueError, TypeError, RecursionError):
        return out
    required = {
        "schema", "event_id", "currency", "metric", "target_period", "unit",
        "scheduled_release_utc", "forecast_captured_utc", "previous_available_utc",
        "consensus_available_utc", "previous_value", "consensus_value",
        "model_estimate", "model_version", "previous_source_sha256_claim",
        "consensus_source_sha256_claim",
    }
    if set(raw) != required:
        return out
    try:
        release = datetime.fromisoformat(raw["scheduled_release_utc"])
        captured = datetime.fromisoformat(raw["forecast_captured_utc"])
        previous_at = datetime.fromisoformat(raw["previous_available_utc"])
        consensus_at = datetime.fromisoformat(raw["consensus_available_utc"])
    except (ValueError, TypeError, KeyError):
        return out
    release, captured = _utc(release), _utc(captured)
    previous_at, consensus_at = _utc(previous_at), _utc(consensus_at)
    actual_published, actual_captured = _utc(actual.first_published_at), _utc(actual.captured_at)
    if (release is None or captured is None or previous_at is None or consensus_at is None
            or actual_published is None or actual_captured is None
            or not isinstance(raw["event_id"], str)
            or _ID.fullmatch(raw["event_id"]) is None
            or raw["currency"] not in CURRENCIES
            or not isinstance(raw["metric"], str)
            or METRIC_UNITS.get(raw["metric"]) != raw["unit"]
            or not isinstance(raw["target_period"], str)
            or _MONTH.fullmatch(raw["target_period"]) is None
            or not previous_at <= captured < release <= actual_published <= actual_captured <= now
            or not consensus_at <= captured
            or actual.event_id != raw["event_id"] or actual.currency != raw["currency"]
            or actual.metric != raw["metric"] or actual.target_period != raw["target_period"]
            or actual.unit != raw["unit"]
            or _decimal(actual.value) is None
            or _decimal(raw["previous_value"]) is None
            or _decimal(raw["consensus_value"]) is None
            or not _hash_claim(actual.source_sha256_claim)
            or not _hash_claim(raw["previous_source_sha256_claim"])
            or not _hash_claim(raw["consensus_source_sha256_claim"])):
        return out
    if raw["model_estimate"] is not None and (
            _decimal(raw["model_estimate"]) is None
            or not isinstance(raw["model_version"], str)
            or _MODEL.fullmatch(raw["model_version"]) is None):
        return out
    if raw["model_estimate"] is None and raw["model_version"] is not None:
        return out

    result = _decimal(actual.value)
    consensus = _decimal(raw["consensus_value"])
    previous = _decimal(raw["previous_value"])
    estimate = _decimal(raw["model_estimate"]) if raw["model_estimate"] is not None else None
    consensus_error = abs(result - consensus)
    model_error = abs(result - estimate) if estimate is not None else None
    out.update({
        "state": "LAB_POST_EVENT_DESCRIPTIVE_SCORE_UNATTESTED",
        "reason": "OUTCOME_AND_PRE_EVENT_SOURCE_ASSERTIONS_NOT_INDEPENDENTLY_VERIFIED",
        "forecast_sha256": locked.payload_sha256,
        "scored_claim_sha256": sha256(_canonical({
            "forecast_sha256": locked.payload_sha256,
            "actual_value": str(result),
            "actual_captured_utc": actual_captured.isoformat(),
            "actual_source_hash_claim": actual.source_sha256_claim,
        }).encode("ascii")).hexdigest(),
        "model_abs_error_documentary": str(model_error) if model_error is not None else None,
        "consensus_abs_error_documentary": str(consensus_error),
        "previous_abs_error_documentary": str(abs(result - previous)),
        "actual_minus_consensus_documentary": str(result - consensus),
        "model_better_than_consensus_documentary": (
            model_error < consensus_error if model_error is not None else None),
    })
    return out


__all__ = [
    "SCHEMA", "ForecastDraft", "ForecastLock", "ActualClaim",
    "freeze_pre_event_forecast_lab", "score_locked_forecast_lab",
]
