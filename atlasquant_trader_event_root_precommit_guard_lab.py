"""Fail-closed LAB: predeclare economic event roots before any FX prediction.

This is a *documentary* binding, NOT independent evidence of timestamps or
event causality. The caller may rewrite a plan and its locally held hash.
It prevents after-the-fact splitting of one named release into several
successfully scored event roots when a preserved pre-event plan is supplied.
No network, broker, file writes, scheduling, alerts, or trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from atlasquant_trader_selective_event_root_oos_audit_lab import (
    FrozenOpportunityManifest, ObservedOpportunity, ID, VERSION, MAX_SLOTS,
)
from atlasquant_trader_fx_forecast_precommit_lab import ForecastPrecommitClaim
from atlasquant_trader_selective_precommit_bridge_lab import (
    reconcile_precommit_event_root_oos_lab,
)

SCHEMA = "ATLASQUANT_TRADER_EVENT_ROOT_PRECOMMIT_BINDING_LAB_V1"
BLOCKED = "LAB_PRECOMMITTED_ROOT_BINDING_BLOCKED"
DOCUMENTARY = "LAB_ROOT_BINDING_DOCUMENTARY_ONLY_NO_GO"


@dataclass(frozen=True)
class PlannedEventRoot:
    opportunity_id: str
    source_event_id: str
    event_root_id: str


@dataclass(frozen=True)
class FrozenEventRootPlan:
    campaign_id: str
    rule_version: str
    frozen_at_utc: datetime
    assignments: tuple[PlannedEventRoot, ...]


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    return value.astimezone(timezone.utc)


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": BLOCKED, "reason": reason,
        "matched_slots": 0, "claimed_root_count": 0,
        "root_plan_sha256_documentary": None,
        "root_plan_matches_preserved_digest_claim": False,
        "pre_event_root_plan_independently_witnessed": False,
        "source_release_identity_independently_verified": False,
        "root_causality_or_independence_verified": False,
        "precommit_time_independently_verified": False,
        "validated_accuracy": None,
        "calibrated_probability": None,
        "audit": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _canonical_plan_bytes(plan: FrozenEventRootPlan) -> bytes:
    content = {
        "schema": SCHEMA, "campaign_id": plan.campaign_id,
        "rule_version": plan.rule_version,
        "frozen_at_utc_claim": _utc(plan.frozen_at_utc).isoformat().replace("+00:00", "Z"),
        "assignments": [
            {"opportunity_id": a.opportunity_id,
             "source_event_id": a.source_event_id,
             "event_root_id": a.event_root_id} for a in plan.assignments
        ],
    }
    return (json.dumps(content, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True) + "\n").encode("ascii")


def fingerprint_root_plan_lab(plan: Any) -> str | None:
    """Compute a *local* content checksum, not a timestamp certificate."""
    if not isinstance(plan, FrozenEventRootPlan):
        return None
    if (_utc(plan.frozen_at_utc) is None
            or not isinstance(plan.campaign_id, str)
            or ID.fullmatch(plan.campaign_id) is None
            or not isinstance(plan.rule_version, str)
            or VERSION.fullmatch(plan.rule_version) is None
            or not isinstance(plan.assignments, tuple)
            or not 1 <= len(plan.assignments) <= MAX_SLOTS):
        return None
    ids = set()
    sources = {}
    for a in plan.assignments:
        if (not isinstance(a, PlannedEventRoot)
                or any(not isinstance(s, str) or ID.fullmatch(s) is None
                       for s in (a.opportunity_id, a.source_event_id, a.event_root_id))
                or a.opportunity_id in ids
                or a.source_event_id in {"UNKNOWN", "UNVERIFIED", "NONE"}
                or (a.source_event_id in sources
                    and sources[a.source_event_id] != a.event_root_id)):
            return None
        ids.add(a.opportunity_id)
        sources[a.source_event_id] = a.event_root_id
    return sha256(_canonical_plan_bytes(plan)).hexdigest()


def inspect_precommitted_event_root_binding_lab(
    *, frozen_manifest: Any, root_plan: Any, preserved_root_plan_sha256: Any,
    forecast_records: Any, receipt_entries: Any, receipt_head_sha256: Any,
    observations: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Require original root names, slot coverage and local receipt consistency.

    Two opportunities with the same named source event MUST share one root.
    A caller can still invent source-event names or replace both the plan and
    the preserved checksum. No validated accuracy is ever returned.
    """
    now = _utc(inspected_at_utc)
    digest = fingerprint_root_plan_lab(root_plan)
    if (now is None or digest is None
            or not isinstance(frozen_manifest, FrozenOpportunityManifest)
            or not isinstance(preserved_root_plan_sha256, str)
            or preserved_root_plan_sha256 != digest
            or not isinstance(forecast_records, (tuple, list))
            or not isinstance(observations, (tuple, list))):
        return _deny("INVALID_PLAN_CLOCK_OR_PRESERVED_DIGEST_MISMATCH")

    expected = frozen_manifest.expected_opportunity_ids
    if (root_plan.campaign_id != frozen_manifest.campaign_id
            or root_plan.rule_version != frozen_manifest.rule_version
            or not isinstance(expected, tuple)
            or len(root_plan.assignments) != len(expected)
            or len(forecast_records) != len(expected)
            or len(observations) != len(expected)):
        return _deny("ROOT_PLAN_CENSUS_OR_CAMPAIGN_MISMATCH")

    freeze = _utc(root_plan.frozen_at_utc)
    manifest_freeze = _utc(frozen_manifest.frozen_at_utc)
    if manifest_freeze is None or not manifest_freeze <= freeze <= now:
        return _deny("ROOT_PLAN_FREEZE_OUTSIDE_MANIFEST_WINDOW")

    for expected_id, entry, forecast, observed in zip(
            expected, root_plan.assignments, forecast_records, observations):
        if (not isinstance(forecast, ForecastPrecommitClaim)
                or not isinstance(observed, ObservedOpportunity)
                or entry.opportunity_id != expected_id
                or forecast.opportunity_id != expected_id
                or observed.opportunity_id != expected_id):
            return _deny("ROOT_ASSIGNMENT_MISSING_REORDERED_OR_EXTRA")
        issued = _utc(forecast.prediction_issued_at)
        if issued is None or not freeze < issued:
            return _deny("ROOT_PLAN_NOT_FROZEN_BEFORE_FIRST_DECISION")
        if observed.event_root_id != entry.event_root_id:
            return _deny("EVENT_ROOT_RELABELED_AFTER_PRECOMMIT")

    joined = reconcile_precommit_event_root_oos_lab(
        frozen_manifest=frozen_manifest, forecast_records=forecast_records,
        receipt_entries=receipt_entries, receipt_head_sha256=receipt_head_sha256,
        observations=observations, inspected_at_utc=now)
    if joined["state"] != "LAB_PRECOMMIT_OOS_JOIN_DOCUMENTARY_ONLY_NO_GO":
        return _deny("PRECOMMIT_AND_OUTCOME_JOIN_REJECTED")

    result = _deny("LOCAL_ROOT_BINDING_AND_RECEIPTS_MATCH_BUT_NOT_INDEPENDENTLY_ATTESTED")
    result.update({
        "state": DOCUMENTARY, "matched_slots": len(expected),
        "claimed_root_count": len({a.event_root_id for a in root_plan.assignments}),
        "root_plan_sha256_documentary": digest,
        "root_plan_matches_preserved_digest_claim": True,
        "audit": joined,
    })
    return result


__all__ = ["SCHEMA", "PlannedEventRoot", "FrozenEventRootPlan",
           "fingerprint_root_plan_lab", "inspect_precommitted_event_root_binding_lab"]
