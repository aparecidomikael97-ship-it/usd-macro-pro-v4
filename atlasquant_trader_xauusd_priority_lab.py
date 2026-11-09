"""AtlasQuant Trader LAB — isolated XAU/USD research-priority contract.

XAUUSD is gold priced in USD, NOT a ninth G8 currency or a 29th FX cross.
This is a planning / evidence-inventory component, not a market signal.
No network, MT5, files, position access, or trading side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from atlasquant_instrument_registry import FX_28

SCHEMA = "ATLASQUANT_XAUUSD_PRIORITY_RESEARCH_LAB_V1"
XAU_SYMBOL = "XAUUSD"
XAU_CANONICAL_ID = "METAL:XAUUSD"
BIASES = ("D1", "W1")
CONTEXT = ("MN1",)
FX_PAIR_COUNT = 28
# These are analysis domains, not signed forecasts or a weighted model.
EVIDENCE_DOMAINS = (
    "USD_AND_DXY", "US_REAL_YIELDS", "FED_AND_RATE_EXPECTATIONS",
    "US_MACRO_RELEASES", "GOLD_FLOWS_AND_DEMAND", "GEOPOLITICAL_RISK",
    "XAUUSD_BROKER_PRICE_AND_SESSION", "XAUUSD_PROSPECTIVE_OUTCOMES",
)
_HEX = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class EvidenceReceipt:
    domain: str
    published_at_utc: datetime
    captured_at_utc: datetime
    sha256_claim: str


def _time(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def plan_xauusd_priority_lab() -> dict[str, Any]:
    """Stable P0 plan; never inserts XAUUSD into FX_28 or the 56-slot census."""
    return {
        "schema": SCHEMA,
        "canonical_id": XAU_CANONICAL_ID,
        "symbol": XAU_SYMBOL,
        "display_symbol": "XAU/USD",
        "market": "SPOT_GOLD_USD",
        "priority": "P0_RESEARCH_PRIORITY",
        "primary_bias_horizons": list(BIASES),
        "monthly_horizon": "CONTEXT_ONLY_NOT_VALIDATED",
        "context_horizons": list(CONTEXT),
        "evidence_domains": list(EVIDENCE_DOMAINS),
        "possible_biases": ["ALTA", "BAIXA", "AGUARDAR"],
        "fx_28_universe_unchanged": len(FX_28) == FX_PAIR_COUNT and XAU_SYMBOL not in FX_28,
        "fx_56_census_unchanged": True,
        "independent_metal_validation_required": True,
        "grade_0_to_10_is_probability": False,
        "operational_bias": "AGUARDAR",
        "validated_accuracy": None,
        "publishable": False,
        "trade_authorized": False,
        "research_only": True,
        "new_cost_brl": 0,
    }


def inspect_xauusd_evidence_lab(
    receipts: Any, *, as_of_utc: Any, decision_freeze_utc: Any,
) -> dict[str, Any]:
    """Validate *claimed* evidence coverage, never authorize a gold signal.

    Independent vendor/broker verification and a true prospective holdout are
    out of scope, even when all supplied receipts are structurally consistent.
    """
    result: dict[str, Any] = {
        "schema": SCHEMA, "canonical_id": XAU_CANONICAL_ID,
        "state": "LAB_XAUUSD_EVIDENCE_BLOCKED", "reason": "MISSING_EVIDENCE",
        "domain_count_expected": len(EVIDENCE_DOMAINS),
        "domain_count_accepted": 0, "missing_or_invalid_domains": list(EVIDENCE_DOMAINS),
        "source_originals_authenticated": False,
        "broker_symbol_and_session_authenticated": False,
        "prospective_outcomes_independently_verified": False,
        "accuracy_validated": False, "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "confidence_0_to_10_calibrated": False,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }
    now, freeze = _time(as_of_utc), _time(decision_freeze_utc)
    if now is None or freeze is None or freeze > now:
        result["reason"] = "INVALID_DECISION_OR_AUDIT_CLOCK"
        return result
    if not isinstance(receipts, (list, tuple)):
        return result
    accepted = set()
    for row in receipts:
        if not isinstance(row, EvidenceReceipt) or row.domain not in EVIDENCE_DOMAINS:
            result["reason"] = "INVALID_OR_UNSUPPORTED_DOMAIN"
            return result
        if row.domain in accepted:
            result["reason"] = "DUPLICATE_EVIDENCE_DOMAIN"
            return result
        published, captured = _time(row.published_at_utc), _time(row.captured_at_utc)
        if (published is None or captured is None
                or not published <= captured <= freeze
                or not isinstance(row.sha256_claim, str)
                or _HEX.fullmatch(row.sha256_claim) is None):
            result["reason"] = "INVALID_SOURCE_VINTAGE_OR_HASH_CLAIM"
            return result
        accepted.add(row.domain)
    missing = sorted(set(EVIDENCE_DOMAINS) - accepted)
    result["domain_count_accepted"] = len(accepted)
    result["missing_or_invalid_domains"] = missing
    if not missing:
        result["state"] = "LAB_XAUUSD_DOCUMENTARY_COVERAGE_UNATTESTED"
        result["reason"] = "ORIGINAL_BROKER_AND_PROSPECTIVE_EVIDENCE_NOT_AUTHENTICATED"
    return result


__all__ = ["SCHEMA", "XAU_SYMBOL", "XAU_CANONICAL_ID", "BIASES", "CONTEXT",
           "EVIDENCE_DOMAINS", "EvidenceReceipt", "plan_xauusd_priority_lab",
           "inspect_xauusd_evidence_lab"]
