"""Offline P0: freeze an FX research campaign BEFORE any cohort plan exists.

A hash is local integrity only. External timestamp witness remains mandatory;
no forecasts, MT5 access, price sources, HTTP, trades, or publishable biases.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_trader_fx_trial_census_lab import FrozenBlob, _verified_roster
from atlasquant_trader_fx_multicohort_ledger_lab import (
    FrozenFxCohort, MAX_COHORTS, build_full_fx_multicohort_ledger_lab,
)
from atlasquant_trader_w1_ny17_dst_guard_lab import w1_ny17_dst_crossing_lab

SCHEMA = "ATLASQUANT_FX_CAMPAIGN_SCHEDULE_PRECOMMIT_LAB_V1"
ANCHOR_HEADER = "ATLASQUANT_FX_CAMPAIGN_SCHEDULE_PRECOMMIT_HASH_LAB_V1"
_ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,31}\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}\Z")
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_DURATIONS = {"D1": timedelta(days=1), "W1": timedelta(days=7)}


@dataclass(frozen=True)
class PlannedFxCohort:
    cohort_id: str
    d1_open_at: datetime
    d1_close_at: datetime
    w1_open_at: datetime
    w1_close_at: datetime


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    return value.astimezone(timezone.utc)


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 35:
        return None
    try:
        return _utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (TypeError, ValueError, OverflowError):
        return None


def _fmt(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _pack(document: dict[str, Any]) -> FrozenBlob:
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False)
    return FrozenBlob(raw, sha256(raw.encode("ascii")).hexdigest())


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_CAMPAIGN_SCHEDULE_BLOCKED",
        "reason": reason, "frozen": None, "sha256": None,
        "scheduled_cohorts": 0, "declared_slots": 0,
        "anchor_body": None, "campaign_schedule_bound": False,
        "ledger": None, "external_campaign_precommitment_verified": False,
        "external_cohort_manifest_precommitted": False,
        "broker_calendar_authenticated": False,
        "genuine_forecasts_pre_event_verified": False,
        "source_vintages_authenticated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def freeze_fx_campaign_schedule_lab(*, campaign_id: Any, rule_version: Any,
                                    scheduled: Any, frozen_at: Any) -> dict[str, Any]:
    """Lock exact cohort IDs and D1/W1 target windows, without making them up.

    Does not certify that all tradable market dates are included: a campaign
    calendar and any excluded weeks must be externally precommitted/reviewed.
    """
    out = _blocked("INVALID_CAMPAIGN_ID_VERSION_CLOCK_OR_SIZE")
    frozen = _utc(frozen_at)
    if (not isinstance(campaign_id, str) or not _ID.fullmatch(campaign_id)
            or not isinstance(rule_version, str) or not _VERSION.fullmatch(rule_version)
            or frozen is None or not isinstance(scheduled, (tuple, list))
            or not 1 <= len(scheduled) <= MAX_COHORTS):
        return out
    records = []
    ids: set[str] = set()
    last_open: dict[str, datetime | None] = {"D1": None, "W1": None}
    last_close: dict[str, datetime | None] = {"D1": None, "W1": None}
    for item in scheduled:
        if (not isinstance(item, PlannedFxCohort)
                or not isinstance(item.cohort_id, str) or not _ID.fullmatch(item.cohort_id)
                or item.cohort_id in ids):
            out["reason"] = "INVALID_OR_DUPLICATED_COHORT_ID"
            return out
        ids.add(item.cohort_id)
        row = {"cohort_id": item.cohort_id}
        for horizon in ("D1", "W1"):
            start = _utc(getattr(item, horizon.lower() + "_open_at"))
            end = _utc(getattr(item, horizon.lower() + "_close_at"))
            if (start is None or end is None or not frozen < start
                    or end - start != _DURATIONS[horizon]
                    or last_open[horizon] is not None and start <= last_open[horizon]
                    or last_close[horizon] is not None and start < last_close[horizon]):
                out["reason"] = "INVALID_LATE_OVERLAPPING_OR_UNSORTED_TARGET_WINDOW"
                return out
            if horizon == "W1":
                dst = w1_ny17_dst_crossing_lab(start, end)
                if dst is None or dst:
                    out["reason"] = "W1_DST_OR_CLOCK_CONVENTION_REQUIRES_BROKER_REVIEW"
                    return out
            last_open[horizon], last_close[horizon] = start, end
            row[horizon] = {"open_utc": _fmt(start), "close_utc": _fmt(end)}
        records.append(row)
    blob = _pack({"schema": SCHEMA, "campaign_id": campaign_id,
                  "rule_version": rule_version,
                  "schedule_frozen_utc_claim": _fmt(frozen), "cohorts": records})
    out.update({"state": "LAB_CAMPAIGN_SCHEDULE_HASHED_UNATTESTED",
                "reason": "HASH_AND_COHORT_COVERAGE_NOT_EXTERNAL_TIMESTAMP_PROOF",
                "frozen": blob, "sha256": blob.sha256,
                "scheduled_cohorts": len(records), "declared_slots": 56 * len(records)})
    return out


def _verified(schedule: Any) -> tuple[dict[str, Any], datetime] | None:
    if (not isinstance(schedule, FrozenBlob)
            or not isinstance(schedule.canonical_json, str)
            or len(schedule.canonical_json) > 85000
            or not isinstance(schedule.sha256, str)
            or not _HEX.fullmatch(schedule.sha256)):
        return None
    try:
        doc = json.loads(schedule.canonical_json)
        if (not isinstance(doc, dict) or set(doc) != {
                "schema", "campaign_id", "rule_version", "schedule_frozen_utc_claim", "cohorts"}
                or doc["schema"] != SCHEMA or not isinstance(doc["cohorts"], list)):
            return None
        frozen = _parse(doc["schedule_frozen_utc_claim"])
        if frozen is None:
            return None
        rows = []
        for x in doc["cohorts"]:
            if (not isinstance(x, dict) or set(x) != {"cohort_id", "D1", "W1"}
                    or any(not isinstance(x.get(tf), dict) or set(x[tf]) != {"open_utc", "close_utc"}
                           for tf in ("D1", "W1"))):
                return None
            rows.append(PlannedFxCohort(
                x["cohort_id"], _parse(x["D1"]["open_utc"]), _parse(x["D1"]["close_utc"]),
                _parse(x["W1"]["open_utc"]), _parse(x["W1"]["close_utc"])))
        reproduced = freeze_fx_campaign_schedule_lab(
            campaign_id=doc["campaign_id"], rule_version=doc["rule_version"],
            scheduled=rows, frozen_at=frozen)
        if reproduced["frozen"] != schedule or _pack(doc) != schedule:
            return None
        return doc, frozen
    except (ValueError, KeyError, TypeError, RecursionError, OverflowError, UnicodeError):
        return None


def prepare_campaign_github_anchor_lab(schedule: Any, *, repository_full_name: Any,
                                       issue_number: Any, prepared_at: Any) -> dict[str, Any]:
    """Prepare a COMMENT BODY only; caller must publish/verify BEFORE first roster.

    No GitHub calls are made. This does not attest publication or timestamps.
    """
    out = _blocked("INVALID_OR_LATE_CAMPAIGN_ANCHOR_PREPARATION")
    original, now = _verified(schedule), _utc(prepared_at)
    if (original is None or now is None or not isinstance(repository_full_name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", repository_full_name)
            or type(issue_number) is not int or not 1 <= issue_number <= 1_000_000_000):
        return out
    doc, frozen = original
    first_target = min(_parse(x[tf]["open_utc"]) for x in doc["cohorts"]
                       for tf in ("D1", "W1"))
    if not frozen <= now < first_target:
        return out
    body = "\n".join([
        ANCHOR_HEADER,
        "repository=" + repository_full_name,
        "issue_number=" + str(issue_number),
        "campaign_id=" + doc["campaign_id"],
        "rule_version=" + doc["rule_version"],
        "cohort_count=" + str(len(doc["cohorts"])),
        "slots_expected=" + str(len(doc["cohorts"]) * 56),
        "schedule_sha256=" + schedule.sha256,
        "first_target_open_utc=" + _fmt(first_target),
        "research_only=true", "trade_authorized=false",
    ])
    out.update({"state": "LAB_CAMPAIGN_ANCHOR_TEXT_PREPARED_NOT_POSTED",
                "reason": "EXTERNAL_COMMENT_NOT_PUBLISHED_OR_AUTHENTICATED",
                "anchor_body": body, "sha256": schedule.sha256,
                "scheduled_cohorts": len(doc["cohorts"]),
                "declared_slots": 56 * len(doc["cohorts"])})
    return out


def bind_campaign_to_fx_ledger_lab(schedule: Any, cohorts: Any, *, as_of_utc: Any) -> dict[str, Any]:
    """Derive expected IDs FROM THE FROZEN schedule, never from caller subset.

    This is documentary; it cannot establish external campaign precommitment.
    """
    out = _blocked("INVALID_CAMPAIGN_SCHEDULE_OR_COHORT_PACKETS")
    parsed, now = _verified(schedule), _utc(as_of_utc)
    if (parsed is None or now is None or not isinstance(cohorts, (list, tuple))):
        return out
    doc, frozen = parsed
    planned = doc["cohorts"]
    out["scheduled_cohorts"] = len(planned)
    out["declared_slots"] = len(planned) * 56
    if len(cohorts) != len(planned):
        out["reason"] = "COHORT_MISSING_OR_EXTRA_VS_FROZEN_CAMPAIGN"
        return out
    for item, packet in zip(planned, cohorts):
        if not isinstance(packet, FrozenFxCohort):
            out["reason"] = "INVALID_COHORT_PACKET_TYPE"
            return out
        plan = _verified_roster(packet.roster)
        if plan is None or plan["cohort_id"] != item["cohort_id"]:
            out["reason"] = "COHORT_ID_OR_ROSTER_INVALID_AGAINST_FROZEN_CAMPAIGN"
            return out
        plan_at = _parse(plan["plan_frozen_utc_claim"])
        if plan_at is None or not frozen < plan_at:
            out["reason"] = "CAMPAIGN_NOT_FROZEN_BEFORE_FIRST_ROSTER"
            return out
        if plan["rule_version"] != doc["rule_version"]:
            out["reason"] = "COHORT_RULE_VERSION_DIFFERS_FROM_CAMPAIGN"
            return out
        expected_by_tf = {x["horizon"]: x for x in plan["slots"][:1] + plan["slots"][28:29]}
        for tf in ("D1", "W1"):
            actual = expected_by_tf[tf]
            if (actual["target_open_utc"] != item[tf]["open_utc"]
                    or actual["target_close_utc"] != item[tf]["close_utc"]):
                out["reason"] = "TARGET_WINDOW_CHANGED_SINCE_CAMPAIGN_SCHEDULE"
                return out
    ledger = build_full_fx_multicohort_ledger_lab(
        tuple(cohorts), expected_cohort_ids=tuple(x["cohort_id"] for x in planned),
        as_of_utc=now)
    if ledger["state"] != "LAB_ALL_DECLARED_FX_COHORTS_RECONCILED_DOCUMENTARY_NO_GO":
        out["reason"] = "CAMPAIGN_COHORT_LEDGER_REJECTED_" + str(ledger["reason"])
        return out
    out.update({"state": "LAB_FROZEN_CAMPAIGN_MATCHES_ALL_COHORTS_DOCUMENTARY_NO_GO",
                "reason": "LOCAL_SCHEDULE_AND_ROSTERS_RECONCILED_WITHOUT_EXTERNAL_ATTESTATION",
                "campaign_schedule_bound": True, "sha256": schedule.sha256,
                "ledger": ledger})
    return out


__all__ = ["SCHEMA", "PlannedFxCohort", "freeze_fx_campaign_schedule_lab",
           "prepare_campaign_github_anchor_lab", "bind_campaign_to_fx_ledger_lab"]
