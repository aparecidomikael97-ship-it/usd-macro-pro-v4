"""Pre-event protocol for ONE October-2026 US PPI descriptive study (LAB).

Frozen in draft Git history before the scheduled 2026-11-13 PPI release:
No AtlasQuant pre-event directional forecast or calibrated model was registered.
Seven correlated Forex reactions are observations from ONE event, NEVER seven
forecast successes. Code-embedded SHA is not independently timestamped proof;
verify the real Git history externally before claiming chronology.
No network, broker, account, order, worker, alert or file I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, EVENT_UTC, LAST_REQUIRED_CLOSE_UTC,
    PRE_EVENT_CORE_CONSENSUS_MOM, PRE_EVENT_HEADLINE_CONSENSUS_MOM,
    TD_PRE_EVENT_HTML_SHA256, TE_PRE_EVENT_HTML_SHA256, USD_FX, WINDOWS,
)

SCHEMA = "ATLASQUANT_PPI_OCT2026_PRE_EVENT_RESEARCH_PROTOCOL_V1"
PINNED_PROTOCOL_SHA256 = "7905ca757f2a5c3faacb1de06b3e48a24c3115baf07bea5ebe55373ad6fb411f"
BEFORE = "LAB_PPI_PRE_EVENT_DESCRIPTIVE_PROTOCOL_LOCKED_ABSTAIN"
AFTER = "LAB_PPI_PRIOR_DESCRIPTIVE_PROTOCOL_RECONCILED_NO_FORECAST"
BLOCKED = "LAB_PPI_PRE_EVENT_PROTOCOL_BLOCKED"

# SHA-256 covers the entire canonical payload. Not a model prediction.
# The Git commit containing this code is the only prospective history claim.
FROZEN_PROTOCOL: dict[str, Any] = {
    "schema": SCHEMA,
    "event_root_id": "US_PPI_OCT2026",
    "release_utc": "2026-11-13T13:30:00+00:00",
    "reference_period": "2026-10",
    "target_measurement": "BLS_FINAL_DEMAND_PPI_SA_MOM",
    "secondary_measurement": "BLS_FINAL_DEMAND_LESS_FOODS_ENERGY_SA_MOM",
    "event_count": 1,
    "fx_symbols": list(USD_FX),
    "reaction_windows_minutes": [15, 60, 240],
    "baseline_candle_open_utc": "2026-11-13T13:15:00+00:00",
    "last_required_close_utc": "2026-11-13T17:30:00+00:00",
    "td_html_sha256": TD_PRE_EVENT_HTML_SHA256,
    "te_html_sha256": TE_PRE_EVENT_HTML_SHA256,
    "headline_consensus_mom_pct": PRE_EVENT_HEADLINE_CONSENSUS_MOM,
    "core_consensus_mom_pct": PRE_EVENT_CORE_CONSENSUS_MOM,
    "pre_event_research_direction": "ABSTAIN",
    "abstention_reason": "NO_VALIDATED_PRE_EVENT_PPI_DIRECTIONAL_MODEL",
    "model_version": None,
    "calibrated_probability": None,
    "directional_forecast_issued": False,
    "measure_only": "DESCRIPTIVE_SURPRISE_AND_SEVEN_FX_REACTION_NOT_ACCURACY",
}


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def canonical_protocol_bytes_lab(value: Any) -> bytes | None:
    if not isinstance(value, dict) or set(value) != set(FROZEN_PROTOCOL):
        return None
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError):
        return None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": BLOCKED, "reason": reason,
        "event_root_id": "US_PPI_OCT2026", "event_count": 1,
        "fx_observation_count_planned": len(USD_FX),
        "frozen_protocol_sha256": None,
        "frozen_consensus_source_hashes_consistent": False,
        "pre_event_declared_abstention": False,
        "pre_event_directional_forecasts_registered": 0,
        "independent_prediction_trials_verified": 0,
        "seven_pairs_not_seven_predictions": True,
        "descriptive_only": True,
        "forecast_or_probability_claim_allowed": False,
        "future_accuracy_metric_allowed": False,
        "external_pre_event_timestamp_witness_authenticated": False,
        "independent_broker_and_publisher_provenance_verified": False,
        "valid_prediction_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False, "live_alert_allowed": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_ppi_frozen_research_protocol_lab(
    *, as_of_utc: Any, submitted_protocol: Any = None,
) -> dict[str, Any]:
    """Compare the literal pinned pre-event protocol, not a post-event story.

    Passing means that code and submitted policy agree. This function alone
    cannot attest when the original Git commit was created by GitHub.
    """
    now = _utc(as_of_utc)
    if now is None:
        return _base("INVALID_INSPECTION_CLOCK")
    current = canonical_protocol_bytes_lab(FROZEN_PROTOCOL)
    if current is None or sha256(current).hexdigest() != PINNED_PROTOCOL_SHA256:
        return _base("CODE_PROTOCOL_DIFFERS_FROM_FROZEN_PIN")
    if submitted_protocol is not None:
        provided = canonical_protocol_bytes_lab(submitted_protocol)
        if provided is None or provided != current:
            return _base("SUBMITTED_POLICY_NOT_EQUAL_TO_PRE_EVENT_PROTOCOL")
    if (
        FROZEN_PROTOCOL["event_root_id"] != "US_PPI_OCT2026"
        or FROZEN_PROTOCOL["release_utc"] != EVENT_UTC.isoformat()
        or FROZEN_PROTOCOL["baseline_candle_open_utc"] != BASELINE_OPEN_UTC.isoformat()
        or FROZEN_PROTOCOL["last_required_close_utc"] != LAST_REQUIRED_CLOSE_UTC.isoformat()
        or FROZEN_PROTOCOL["fx_symbols"] != list(USD_FX)
        or FROZEN_PROTOCOL["reaction_windows_minutes"] != [minutes for _, minutes in WINDOWS]
        or FROZEN_PROTOCOL["td_html_sha256"] != TD_PRE_EVENT_HTML_SHA256
        or FROZEN_PROTOCOL["te_html_sha256"] != TE_PRE_EVENT_HTML_SHA256
        or FROZEN_PROTOCOL["headline_consensus_mom_pct"] != PRE_EVENT_HEADLINE_CONSENSUS_MOM
        or FROZEN_PROTOCOL["core_consensus_mom_pct"] != PRE_EVENT_CORE_CONSENSUS_MOM
        or FROZEN_PROTOCOL["event_count"] != 1
        or FROZEN_PROTOCOL["pre_event_research_direction"] != "ABSTAIN"
        or FROZEN_PROTOCOL["abstention_reason"] != "NO_VALIDATED_PRE_EVENT_PPI_DIRECTIONAL_MODEL"
        or FROZEN_PROTOCOL["model_version"] is not None
        or FROZEN_PROTOCOL["calibrated_probability"] is not None
        or FROZEN_PROTOCOL["directional_forecast_issued"] is not False
    ):
        return _base("PPI_EVENT_COHORT_CONSENSUS_OR_ABSTENTION_POLICY_CHANGED")
    out = _base("FROZEN_DESCRIPTIVE_STUDY_NOT_A_PRE_EVENT_PREDICTIVE_MODEL")
    out.update({
        "state": BEFORE if now < EVENT_UTC else AFTER,
        "reason": "NO_DIRECTIONAL_FORECAST_PRECOMMITTED_FOR_THIS_PPI_EVENT",
        "frozen_protocol_sha256": PINNED_PROTOCOL_SHA256,
        "frozen_consensus_source_hashes_consistent": True,
        "pre_event_declared_abstention": True,
    })
    return out


__all__ = ("SCHEMA", "PINNED_PROTOCOL_SHA256", "BEFORE", "AFTER",
           "canonical_protocol_bytes_lab", "inspect_ppi_frozen_research_protocol_lab")
