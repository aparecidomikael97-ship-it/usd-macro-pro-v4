"""Prospectively noted CPI nowcast, committed before scheduled BLS release.

This is a manually observed public-page research point. Its Git commit can
demonstrate the claim was written before the event, but it does not authenticate
the provider's HTML, historical API vintage, or market consensus.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping
from urllib.parse import urlsplit

SCHEMA = "ATLASQUANT_TRADER_FORWARD_CPI_NOWCAST_FREEZE_LAB_V1"
FIELDS = frozenset((
    "schema", "state", "observed_at_utc", "source_reported_update_day",
    "release_reference_month", "release_scheduled_utc", "source_url",
    "calendar_url", "acquisition_method", "measured_model_forecast",
    "forecast_type", "market_consensus", "official_release_actual",
    "model_updated_intraday_time_attested", "source_html_bytes_archived",
    "source_http_response_headers_archived", "provider_historical_vintage_attested",
    "independent_timestamp_attested", "rights_to_redistribute_source_html_verified",
    "real_oos_performance_verified", "trade_authorized",
))
MEASURES = frozenset(("CPI_MOM_SA_PCT", "CORE_CPI_MOM_SA_PCT",
                      "CPI_YOY_NSA_PCT", "CORE_CPI_YOY_NSA_PCT"))
ACTUAL_FIELDS = frozenset((
    "state", "source_url", "published_at_utc", "captured_at_utc",
    "cpi_mom_sa_pct", "core_cpi_mom_sa_pct",
))
FALSE_FLAGS = (
    "model_updated_intraday_time_attested", "source_html_bytes_archived",
    "source_http_response_headers_archived", "provider_historical_vintage_attested",
    "independent_timestamp_attested", "rights_to_redistribute_source_html_verified",
    "real_oos_performance_verified", "trade_authorized",
)


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        x = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return x.astimezone(timezone.utc) if x.utcoffset() == timezone.utc.utcoffset(x) else None


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (float, int)):
        return None
    try:
        value = float(raw)
    except (ValueError, OverflowError):
        return None
    return value if isfinite(value) and -50 <= value <= 100 else None


def _refused(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FORWARD_CPI_FREEZE_REFUSED",
        "reason": reason, "snapshot_sha256": None,
        "forecast": None, "later_actual": None, "absolute_error_pp": None,
        "official_source_html_verified": False,
        "market_consensus_verified": False, "real_oos_verified": False,
        "predictive_edge_proven": False, "accuracy_90_proven": False,
        "probability_calibrated": None, "directional_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def inspect_cpi_prospective_freeze_lab(
    snapshot: Any, *, evaluated_at: datetime, later_actual: Any = None,
) -> dict[str, Any]:
    """Separate pre-event observation, expired calendar and synthetic later test."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Explicit timezone-aware evaluation required")
    now = evaluated_at.astimezone(timezone.utc)
    if not isinstance(snapshot, Mapping) or set(snapshot) != FIELDS:
        return _refused("Snapshot fields invalid")
    if (snapshot["schema"] != SCHEMA
            or snapshot["state"] != "DOCUMENTARY_OBSERVATION_BEFORE_RELEASE_UNATTESTED"
            or snapshot["acquisition_method"] != "PUBLIC_WEB_DOCUMENT_TEXT_RESEARCH"
            or snapshot["forecast_type"] !=
            "CLEVELAND_FED_MODEL_NOWCAST_NOT_MARKET_CONSENSUS"):
        return _refused("Unsupported research state or false source classification")
    if any(snapshot[k] is not False for k in FALSE_FLAGS):
        return _refused("No independent timestamp, raw source or licence attestation")
    if snapshot["market_consensus"] is not None or snapshot["official_release_actual"] is not None:
        return _refused("Frozen pre-release snapshot cannot contain consensus or actual")
    if (snapshot["source_url"] !=
            "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
            or snapshot["calendar_url"] !=
            "https://www.bls.gov/schedule/news_release/cpi.htm"):
        return _refused("Not the documented official source/calendar")
    observed = _utc(snapshot["observed_at_utc"])
    release = _utc(snapshot["release_scheduled_utc"])
    try:
        update_day = date.fromisoformat(snapshot["source_reported_update_day"])
        period = date.fromisoformat(snapshot["release_reference_month"] + "-01")
    except (ValueError, TypeError):
        return _refused("Malformed update day or reference month")
    if (observed is None or release is None or not observed < release
            or update_day > observed.date() or period.year != update_day.year
            or snapshot["release_reference_month"] != "2026-10"
            or release.isoformat() != "2026-11-10T13:30:00+00:00"):
        return _refused("Snapshot or expected release chronology invalid")
    raw = snapshot["measured_model_forecast"]
    if not isinstance(raw, Mapping) or set(raw) != MEASURES:
        return _refused("Missing or swapped CPI measure/unit")
    values = {name: _number(raw[name]) for name in MEASURES}
    if any(v is None for v in values.values()):
        return _refused("Model values nonfinite, Boolean or unbounded")
    if now < observed:
        return _refused("Cannot claim prospectively observed model data in the past")
    digest = sha256(json.dumps(dict(snapshot), sort_keys=True, separators=(",", ":"),
                               ensure_ascii=True).encode("utf-8")).hexdigest()
    common = {
        **_refused(""), "snapshot_sha256": digest, "forecast": dict(values),
        "recorded_before_official_release": True,
        "source_reported_update_day": update_day.isoformat(),
        "observed_at_utc": observed.isoformat(),
        "cpi_scheduled_release_utc": release.isoformat(),
    }
    if now < release:
        if later_actual is not None:
            return _refused("Future release actual injected before scheduled event")
        return {
            **common, "state": "LAB_PROSPECTIVE_DOCUMENTARY_NOWCAST_PRE_EVENT",
            "reason": "Public-model observation logged pre-event, not source authenticated",
        }
    if later_actual is None:
        return {
            **common, "state": "LAB_CPI_EVENT_PASSED_OUTCOME_NOT_INGESTED",
            "reason": "Newly published BLS actual is required; never reuse model as actual",
        }
    if not isinstance(later_actual, Mapping) or set(later_actual) != ACTUAL_FIELDS:
        return _refused("Later actual must be a separate bounded record")
    if later_actual["state"] != "LAB_CALLER_SUPPLIED_ACTUAL_UNATTESTED":
        return _refused("No independently verified actual claimed")
    raw_url = later_actual["source_url"]
    if not isinstance(raw_url, str):
        return _refused("Actual source URL invalid")
    try:
        url = urlsplit(raw_url)
        valid_url = (url.scheme == "https" and url.hostname == "www.bls.gov"
                     and url.path.startswith("/news.release/archives/cpi_")
                     and url.username is None and url.password is None
                     and url.port in (None, 443) and not url.fragment)
    except ValueError:
        valid_url = False
    if not valid_url:
        return _refused("Later result needs BLS archived CPI document URL")
    published, captured = (_utc(later_actual["published_at_utc"]),
                           _utc(later_actual["captured_at_utc"]))
    if (published is None or captured is None
            or not release <= published <= captured <= now):
        return _refused("Post-release document was unavailable or time unproved")
    headline = _number(later_actual["cpi_mom_sa_pct"])
    core = _number(later_actual["core_cpi_mom_sa_pct"])
    if headline is None or core is None:
        return _refused("Later CPI actual invalid or not comparable in unit")
    return {
        **common, "state": "LAB_SYNTHETIC_FORWARD_ERROR_COMPARISON_ONLY",
        "reason": "Caller-supplied actual is not externally attested or real OOS",
        "later_actual": {"CPI_MOM_SA_PCT": headline, "CORE_CPI_MOM_SA_PCT": core},
        "absolute_error_pp": {
            "CPI_MOM_SA_PP": round(abs(values["CPI_MOM_SA_PCT"] - headline), 6),
            "CORE_CPI_MOM_SA_PP": round(abs(values["CORE_CPI_MOM_SA_PCT"] - core), 6),
        },
    }


__all__ = ["SCHEMA", "MEASURES", "inspect_cpi_prospective_freeze_lab"]
