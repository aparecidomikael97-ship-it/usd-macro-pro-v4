"""Pinned ONS GBP/D7G7 historical archive download leads, offline only.

The ONS /previous listing labels these as *superseded* on given calendar
dates. That field is not a publication timestamp and says nothing about
intraday availability or the independent authenticity of downloaded bytes.
"""
from __future__ import annotations

from datetime import datetime, date, timezone
from typing import Any

SCHEMA = "ATLASQUANT_TRADER_ONS_GBP_PREVIOUS_VERSION_LEADS_LAB_V1"
LISTING_URL = (
    "https://www.ons.gov.uk/economy/inflationandpriceindices/"
    "timeseries/d7g7/mm23/previous"
)

# URLs and the exact /previous/v### identifiers were confirmed by following
# official ONS /previous page links on 2026-11-05. Binary CSV could not be
# downloaded in this environment. No payload bytes are bundled here.
_VERSIONS = (
    ("v131", "2026-10-21"),
    ("v130", "2026-09-16"),
    ("v129", "2026-08-19"),
    ("v128", "2026-07-22"),
)
_GENERATOR_PREFIX = (
    "https://www.ons.gov.uk/generator?format=csv&uri=%2Feconomy%2F"
    "inflationandpriceindices%2Ftimeseries%2Fd7g7%2Fmm23%2Fprevious%2F"
)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLOCKED",
        "reason": reason,
        "currency": "GBP",
        "series_id": "D7G7",
        "source_listing_url": LISTING_URL,
        "as_of_utc": None,
        "catalog_entries": [],
        "catalog_entries_count": 0,
        "source_bytes_downloaded": False,
        "original_archived_payload_verified": False,
        "official_origin_independently_verified": False,
        "individual_publication_instant_verified": False,
        "historical_point_in_time_available_verified": False,
        "commercial_redistribution_rights_verified": False,
        "usable_for_backtest": False,
        "fx_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "can_feed_live_radar": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "publishable": False,
        "external_http_requests": 0,
        "new_cost_brl": 0,
    }


def _utc(raw: Any) -> datetime | None:
    if (not isinstance(raw, datetime) or raw.tzinfo is None
            or raw.utcoffset() is None):
        return None
    return raw.astimezone(timezone.utc)


def plan_ons_gbp_archived_source_leads_lab(
    *, historical_as_of_utc: Any, evaluated_at_utc: Any,
    version_id: Any = None,
) -> dict[str, Any]:
    """Give exact official archive link leads, never grant point-in-time use."""
    out = _blocked("INVALID_CUTOFF_OR_VERSION")
    cutoff, evaluated = _utc(historical_as_of_utc), _utc(evaluated_at_utc)
    if (cutoff is None or evaluated is None or cutoff > evaluated
            or (version_id is not None and (
                not isinstance(version_id, str) or
                version_id not in {v for v, _ in _VERSIONS}
            ))):
        return out
    entries = []
    for version, superseded_str in _VERSIONS:
        if version_id is not None and version_id != version:
            continue
        superseded_day = date.fromisoformat(superseded_str)
        if cutoff.date() < superseded_day:
            # Upper bound ONLY. This archive might not yet have been released
            # at the cutoff, even if it was superseded on a later date.
            classification = "BEFORE_SUPERSESSION_UPPER_BOUND_ONLY_NO_PROOF"
        elif cutoff.date() == superseded_day:
            classification = "SUPERSESSION_DAY_INTRADAY_AMBIGUOUS_BLOCKED"
        else:
            classification = "AFTER_SUPERSESSION_NOT_CURRENT_VINTAGE"
        entries.append({
            "version_id": version,
            "superseded_on_calendar_date_only": superseded_str,
            "superseded_is_not_publication_instant": True,
            "official_archive_download_url_candidate": _GENERATOR_PREFIX + version,
            "source_listing_url": LISTING_URL,
            "status_relative_to_historical_cutoff": classification,
            "historical_availability_proven": False,
            "original_bytes_observed": False,
        })
    out.update({
        "state": "LAB_ONS_PREVIOUS_LINK_LEADS_QUARANTINED",
        "reason": "OFFICIAL_LINK_METADATA_ONLY_NO_ARCHIVED_BYTES_OR_ASOF_PROOF",
        "as_of_utc": cutoff.isoformat(),
        "catalog_entries": entries,
        "catalog_entries_count": len(entries),
    })
    return out


__all__ = ["SCHEMA", "LISTING_URL", "plan_ons_gbp_archived_source_leads_lab"]
