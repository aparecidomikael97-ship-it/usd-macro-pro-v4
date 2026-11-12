"""LAB-only strict join between local FX precommit receipts and event-root OOS census.

Local SHA receipts are NOT external timestamp witnesses. Caller may forge entire
chain and outcome ledger. This module only detects inconsistencies between the
separately supplied snapshots, and NEVER authorizes a forecast, publication or trade.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from atlasquant_trader_fx_forecast_precommit_lab import (
    ForecastPrecommitClaim, verify_fx_precommit_receipts_lab,
)
from atlasquant_trader_selective_event_root_oos_audit_lab import (
    FrozenOpportunityManifest, ObservedOpportunity,
    audit_selective_event_roots_lab,
)

SCHEMA = "ATLASQUANT_SELECTIVE_PRECOMMIT_EVENT_ROOT_JOIN_LAB_V1"
SIDE_MAP = {"UP": "ALTA", "DOWN": "BAIXA", "ABSTAIN": "AGUARDAR"}


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PRECOMMIT_OOS_JOIN_BLOCKED",
        "reason": reason, "descriptive_audit": None,
        "matched_opportunities": 0,
        "local_receipt_chain_matches": False,
        "original_decision_externally_attested": False,
        "external_time_witness_verified": False,
        "source_vintages_independently_verified": False,
        "event_root_independence_verified": False,
        "outcome_market_data_independently_verified": False,
        "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def reconcile_precommit_event_root_oos_lab(
    *, frozen_manifest: Any, forecast_records: Any,
    receipt_entries: Any, receipt_head_sha256: Any,
    observations: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Require every scored or abstained OOS slot to match its local precommit.

    In particular, never silently drop a losing row, flip its direction, change
    its decision time, or score an outcome before the committed target closes.
    Success means documentary consistency ONLY; not a verified forward trial.
    """
    now = _utc(inspected_at_utc)
    if (now is None or not isinstance(frozen_manifest, FrozenOpportunityManifest)
            or not isinstance(forecast_records, (tuple, list))
            or not isinstance(observations, (tuple, list))):
        return _deny("INVALID_PLAN_ROWS_OR_INSPECTION_CLOCK")
    expected = frozen_manifest.expected_opportunity_ids
    if (not isinstance(expected, tuple)
            or len(forecast_records) != len(expected)
            or len(observations) != len(expected)):
        return _deny("FORECAST_OR_OBSERVATION_CENSUS_INCOMPLETE")

    local = verify_fx_precommit_receipts_lab(
        forecast_records, receipt_entries, receipt_head_sha256,
        evaluated_at_utc=now)
    if local["state"] != "LAB_PRECOMMIT_RECEIPTS_LOCALLY_MATCH_UNATTESTED":
        return _deny("PRECOMMIT_RECEIPTS_MISSING_TAMPERED_OR_INVALID")

    for idx, (slot_id, forecast, actual) in enumerate(
            zip(expected, forecast_records, observations)):
        if (not isinstance(forecast, ForecastPrecommitClaim)
                or not isinstance(actual, ObservedOpportunity)
                or forecast.opportunity_id != slot_id
                or actual.opportunity_id != slot_id):
            return _deny("OPPORTUNITY_ID_OR_RECORD_ORDER_MISMATCH")
        issued = _utc(forecast.prediction_issued_at)
        decided = _utc(actual.decided_at_utc)
        target_end = _utc(forecast.outcome_end_at)
        outcome_seen = (_utc(actual.outcome_observed_at_utc)
                        if actual.outcome_observed_at_utc is not None else None)
        if (issued is None or decided != issued or target_end is None
                or actual.asset != forecast.pair
                or actual.horizon != forecast.horizon
                or actual.issued_direction != SIDE_MAP.get(forecast.side)):
            return _deny("PAIR_HORIZON_SIDE_OR_DECISION_TIME_CHANGED")
        if forecast.side == "ABSTAIN":
            if (actual.correct_direction is not None
                    or actual.outcome_observed_at_utc is not None
                    or actual.outcome_label is not None):
                return _deny("ABSTENTION_RELABELED_AS_A_WIN")
        elif outcome_seen is None or outcome_seen < target_end:
            return _deny("OUTCOME_NOT_OBSERVED_AFTER_PRECOMMITTED_TARGET_END")

    report = audit_selective_event_roots_lab(
        frozen_manifest=frozen_manifest, observations=observations,
        inspected_at_utc=now)
    if report["state"] == "LAB_EVENT_ROOT_OOS_ABSTAIN" and (
            report["reason"] != "NO_DIRECTIONAL_SIGNALS_OR_EVENT_ROOTS_TO_AUDIT"):
        return _deny("EVENT_ROOT_CENSUS_AUDIT_REJECTED_" + report["reason"])

    out = _deny("LOCAL_CONTENTS_MATCH_BUT_EXTERNAL_WITNESS_AND_MARKET_VINTAGE_UNVERIFIED")
    out.update({
        "state": "LAB_PRECOMMIT_OOS_JOIN_DOCUMENTARY_ONLY_NO_GO",
        "matched_opportunities": len(expected),
        "local_receipt_chain_matches": True,
        "descriptive_audit": report,
    })
    return out


__all__ = ["SCHEMA", "reconcile_precommit_event_root_oos_lab"]
