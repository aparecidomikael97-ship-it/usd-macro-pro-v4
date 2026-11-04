"""Link an offline macro-event fixture to the correct official research page.

String equality with an official page does NOT attest an original release,
consensus, historical publication, licensed use, or an FX directional bias.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from atlasquant_trader_g8_country_macro_catalog_lab import (
    build_g8_country_macro_candidate_catalog_lab,
)
from atlasquant_trader_g8_macro_context_lab import GROUP_BY_INDICATOR
from atlasquant_trader_macro_surprise_pit_lab import (
    build_macro_point_in_time_evidence_lab,
)

SCHEMA = "ATLASQUANT_TRADER_MACRO_PIT_DOCUMENTATION_LINK_LAB_V1"


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "event": None, "currency": None, "fundamental_group": None,
        "official_landing_page_identified": False,
        "source_content_authenticated": False,
        "release_and_consensus_vintages_attested": False,
        "provider_license_verified": False,
        "macro_direction": "UNDETERMINED",
        "operational_bias": {"D1": "AGUARDAR", "W1": "AGUARDAR", "MN1": "AGUARDAR"},
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False,
    }


def inspect_macro_pit_documentation_link_lab(
    preliminary: Any, actual_release: Any = None, *,
    documentation_url: Any, forecast_issued_at: datetime,
    evaluated_at: datetime,
) -> dict[str, Any]:
    """Audit a stated source identity AFTER PIT validation of one event.

    Any future actual carried into a pre-release book is rejected by the PIT
    engine. A matching official webpage is still ONLY a research lead.
    """
    result = build_macro_point_in_time_evidence_lab(
        preliminary, actual_release, forecast_issued_at=forecast_issued_at,
        evaluated_at=evaluated_at,
    )
    if result["state"] not in (
        "LAB_MACRO_FUTURE_SCHEDULE_ONLY", "LAB_MACRO_RELEASED_SYNTHETIC",
    ):
        return _refuse("PIT_REFUSED: " + str(result["reason"]))
    evidence = result["freeze_evidence"]
    currency, indicator = evidence["currency"], evidence["indicator_id"]
    group = GROUP_BY_INDICATOR.get(indicator)
    if group is None:
        return _refuse("INDICATOR_GROUP_UNSUPPORTED")
    catalog = build_g8_country_macro_candidate_catalog_lab()
    items = [x for x in catalog["candidates"]
             if x["currency"] == currency and x["group"] == group]
    if len(items) != 1:
        return _refuse("OFFICIAL_DOC_CATALOG_INCOMPLETE")
    selected = items[0]
    if (selected["indicator_id"] != indicator
            or selected["unit"] != evidence["unit"]):
        return _refuse("UNSELECTED_INDICATOR_OR_UNIT")
    if (not isinstance(documentation_url, str)
            or documentation_url != selected["source_info_url"]
            or not documentation_url.startswith("https://")):
        return _refuse("DOCUMENTATION_PAGE_DOES_NOT_MATCH_CURRENCY_AND_GROUP")
    if (selected["source_page_is_live_feed"] is not False
            or selected["allowed_for_live_bias"] is not False
            or selected["vintage_and_consensus_verified"] is not False
            or selected["license_for_automated_reuse_verified"] is not False):
        return _refuse("CATALOG_CLAIMS_UNSUPPORTED_AUTHORITY")
    linked = {
        "event_id": evidence["evidence_id"],
        "indicator": indicator, "unit": evidence["unit"],
        "kind": evidence["kind"],
        "previous_synthetic": evidence["previous"],
        "consensus_synthetic": evidence["consensus"],
        "actual_synthetic": evidence.get("actual"),
        "surprise_synthetic": evidence.get("surprise"),
        "surprise_relation_synthetic": evidence.get("surprise_comparison"),
        "scheduled_release_at_utc": evidence["scheduled_release_at_utc"],
        "data_as_of_utc": evidence["data_as_of_utc"],
        "research_documentation_url": documentation_url,
        "consensus_and_release_are_caller_supplied": True,
    }
    out = _refuse("DOCUMENTATION_LEAD_ONLY_NO_AUTHENTICATED_DATA")
    out.update({
        "state": "LAB_DOCUMENTATION_LINKED_UNATTESTED",
        "currency": currency, "fundamental_group": group,
        "official_landing_page_identified": True,
        "event": linked,
        "missing_before_bias": ["ORIGINAL_RELEASE_RECEIPT", "INDEPENDENT_VINTAGE",
                                "CONSENSUS_SOURCE", "LICENSE_AND_SERIES_METHOD",
                                "MACRO_POLICY_TRANSMISSION", "HISTORICAL_OOS"],
    })
    return out


__all__ = ["SCHEMA", "inspect_macro_pit_documentation_link_lab"]
