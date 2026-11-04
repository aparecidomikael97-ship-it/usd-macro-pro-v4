"""Source-document coverage for G8 bilateral FX macro context (OFFLINE LAB).

Uses existing G8 source catalog and manual receipt gate from PR #1803.
A claimed HTTPS URL, timestamp or SHA256 does NOT authenticate a publisher.
No market-direction model, HTTP, scheduling, paid data or trading permission.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_official_source_receipt_lab import (
    FAMILIES, SOURCES, inspect_claimed_macro_receipt_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_BILATERAL_RECEIPT_COVERAGE_LAB_V1"
MAX_RECEIPTS = 64
MAX_AGE_DAYS_LABEL_ONLY = 90
HORIZONS = ("D1", "W1", "MN1")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency_count": 0, "pair_count": 0,
        "currencies": {}, "pairs": [],
        "source_original_authenticated": False,
        "all_economic_events_verified": False,
        "macro_explanation_verified": False,
        "currency_strength_causation_verified": False,
        "spot_fx_price_verified": False,
        "counterevidence_verified": False,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "publishable": False,
        "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def audit_g8_bilateral_macro_receipts_lab(
    raw_receipts: Any, *, forecast_issued_at: datetime, evaluated_at: datetime,
) -> dict[str, Any]:
    """Show release-context documentation coverage; no real coverage claim."""
    if (not isinstance(forecast_issued_at, datetime)
            or forecast_issued_at.tzinfo is None
            or forecast_issued_at.utcoffset() is None
            or not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError("Timezone-aware issuance and evaluation required")
    issued = forecast_issued_at.astimezone(timezone.utc)
    evaluated = evaluated_at.astimezone(timezone.utc)
    if issued > evaluated:
        return _blocked("FORECAST_AFTER_EVALUATION")
    if (not isinstance(raw_receipts, (list, tuple))
            or len(raw_receipts) > MAX_RECEIPTS):
        return _blocked("UNBOUNDED_OR_INVALID_RECEIPT_LIST")

    source_pairs = {(s["currency"], s["family"]) for s in SOURCES.values()}
    if source_pairs != {(c, f) for c in CURRENCIES for f in FAMILIES}:
        return _blocked("SOURCE_CATALOG_NOT_G8_COMPLETE")
    found: dict[tuple[str, str], list[dict[str, Any]]] = {
        (c, f): [] for c in CURRENCIES for f in FAMILIES
    }
    event_keys: set[tuple[str, str]] = set()
    scheduled_claims = 0
    for item in raw_receipts:
        result = inspect_claimed_macro_receipt_lab(
            item, forecast_issued_at=issued, evaluated_at=evaluated)
        if (result.get("state") != "LAB_OFFICIAL_RECEIPT_QUARANTINED_UNATTESTED"
                or result.get("structural_asof_consistent") is not True
                or result.get("official_document_authenticity_verified") is not False
                or result.get("trade_authorized") is not False):
            return _blocked("SOURCE_RECEIPT_REJECTED_OR_FALSE_AUTHORITY")
        meta = result["receipt"]
        source_id, event_id = meta["source_id"], meta["event_id"]
        key = (source_id, event_id)
        if key in event_keys:
            return _blocked("DUPLICATE_SOURCE_EVENT_RECEIPT")
        event_keys.add(key)
        if meta["kind"] == "SCHEDULED":
            scheduled_claims += 1
            continue
        # Only release-context documents can provide a claimed historical
        # document; a scheduled date cannot masquerade as a released number.
        found[(meta["currency"], meta["family"])].append(meta)

    contexts: dict[str, dict[str, Any]] = {}
    for currency in CURRENCIES:
        families = {}
        for family in FAMILIES:
            items = found[(currency, family)]
            items.sort(key=lambda x: (x["published_at_utc"], x["event_id"]))
            fresh = [
                x for x in items
                if issued - datetime.fromisoformat(x["published_at_utc"])
                <= timedelta(days=MAX_AGE_DAYS_LABEL_ONLY)
            ]
            if fresh:
                state = "RECENT_RELEASE_DOCUMENT_CLAIM_ONLY"
            elif items:
                state = "OLDER_RELEASE_DOCUMENT_CLAIM_ONLY"
            else:
                state = "NO_RELEASE_DOCUMENT_CLAIM_SUPPLIED"
            families[family] = {
                "state": state,
                "source_lead_id": next(
                    k for k, v in SOURCES.items()
                    if v["currency"] == currency and v["family"] == family),
                "received_release_context_claim_count": len(items),
                "not_older_than_90_days_claim_count": len(fresh),
                "newest_claimed_publication_utc": (
                    items[-1]["published_at_utc"] if items else None),
                "claimed_event_ids": [x["event_id"] for x in items],
                "source_original_authenticated": False,
                "historical_timestamp_attested": False,
                "can_infer_inflation_or_policy_direction": False,
            }
        contexts[currency] = {
            "currency": currency, "families": families,
            "required_families": list(FAMILIES),
            "recent_release_family_claim_count": sum(
                v["state"] == "RECENT_RELEASE_DOCUMENT_CLAIM_ONLY"
                for v in families.values()),
            "complete_real_macro_context_verified": False,
            "missing_claims_do_not_mean_no_real_event": True,
        }

    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        family_checks = {}
        for family in FAMILIES:
            b = contexts[base]["families"][family]
            q = contexts[quote]["families"][family]
            family_checks[family] = {
                "base_document_claim_state": b["state"],
                "quote_document_claim_state": q["state"],
                "base_release_context_claim_count":
                    b["received_release_context_claim_count"],
                "quote_release_context_claim_count":
                    q["received_release_context_claim_count"],
                "both_currencies_have_recent_document_claims": (
                    b["state"] == "RECENT_RELEASE_DOCUMENT_CLAIM_ONLY"
                    and q["state"] == "RECENT_RELEASE_DOCUMENT_CLAIM_ONLY"),
                "independent_fundamental_comparison_verified": False,
            }
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "documentary_families": family_checks,
            "documented_family_count_claim_only": sum(
                x["both_currencies_have_recent_document_claims"]
                for x in family_checks.values()),
            "D1": "AGUARDAR", "W1": "AGUARDAR", "MN1": "AGUARDAR",
            "explanation_causality_verified": False,
            "trade_authorized": False,
        })
    out = _blocked("CLAIMED_DOCUMENT_COVERAGE_NOT_SOURCE_AUTHENTICATION")
    out.update({
        "state": "LAB_G8_BILATERAL_DOCUMENTARY_COVERAGE_ONLY",
        "as_of_utc": issued.isoformat(),
        "currency_count": len(contexts), "pair_count": len(pairs),
        "currencies": contexts, "pairs": pairs,
        "claimed_receipts_received": len(event_keys),
        "released_context_claims_received": sum(
            len(values) for values in found.values()),
        "scheduled_claims_not_counted_as_releases": scheduled_claims,
        "required_families": list(FAMILIES),
        "all_eight_currencies_have_two_recent_claims": all(
            data["recent_release_family_claim_count"] == len(FAMILIES)
            for data in contexts.values()),
        "complete_actual_calendar_coverage_proven": False,
        "news_geopolitics_microeconomics_verified": False,
        "three_daily_refreshes_running": False,
        "notice": ("Recebimento de excerto do chamador nao comprova "
                   "autenticidade, completude, direitos, expectativa "
                   "pre-evento ou direcao futura de nenhuma moeda."),
    })
    return out


__all__ = [
    "SCHEMA", "MAX_RECEIPTS", "audit_g8_bilateral_macro_receipts_lab",
]
