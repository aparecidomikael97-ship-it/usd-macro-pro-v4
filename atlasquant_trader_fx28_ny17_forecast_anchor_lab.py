"""NY17 FX28 pre-event forecast commitment for the predeclared 2026 campaign.

Pure offline preparation and DOCUMENTARY verification of externally supplied
GitHub comment metadata. No GitHub API calls are made. A caller can forge an
entire comment object; no independently authenticated timestamp is returned.

Unlike the old generic W1 precommit contract (7-10 calendar days), an FX
NY17 weekly window runs Sun 17:00 NY -> Fri 17:00 NY (five local days).
Use the exact _nominal_windows() calendar, NOT the legacy W1 day range.

A digest anchor is only meaningful if the full canonical forecast_json is
preserved and later independently compared with an actual unedited GitHub
comment created before the start. Never post invented forecasts or treat
this as proof of predictive accuracy. No prices, orders or live signals.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx_ny17_forecast_outcome_join_lab import (
    Ny17ForecastClaim, ABSTAIN_REASONS,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, _nominal_windows,
)
from atlasquant_trader_fx_census_github_anchor_lab import GitHubCommentClaim

SCHEMA = "ATLASQUANT_FX28_NY17_PROSPECTIVE_PRE_EVENT_ANCHOR_LAB_V1"
HEADER = "ATLASQUANT_FX28_NY17_FORECAST_PRE_EVENT_COMMIT_LAB_V1"
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE_NUMBER = 1884
SHA64 = re.compile(r"[a-f0-9]{64}\Z")
ID_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,79}\Z")
SIDES = {"UP", "DOWN", "ABSTAIN"}


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_NY17_PRE_EVENT_ANCHOR_BLOCKED",
        "reason": reason, "campaign_id": CAMPAIGN_ID,
        "horizon": None, "pair_count": 0,
        "directional_claims": 0, "abstentions": 0,
        "forecast_json": None, "forecast_sha256": None,
        "anchor_comment_body": None,
        "comment_chronology_documentary_consistent": False,
        "forecast_scope_locally_complete": False,
        "github_comment_independently_authenticated": False,
        "real_forecast_generated_by_model_verified": False,
        "forecast_external_pre_event_witness_verified": False,
        "macro_information_point_in_time_verified": False,
        "broker_prices_independently_authenticated": False,
        "forecast_accuracy_validated": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def prepare_ny17_full_forecast_anchor_lab(
    *, claims: Any, horizon: Any, start_at_utc: Any,
    end_at_utc: Any, plan_declared_at_utc: Any,
    prepared_at_utc: Any,
) -> dict[str, Any]:
    """Build complete 28-slot *candidate* forecast payload and comment text.

    This function does NOT produce its own predictions. It rejects 27/28,
    late predictions, duplicate pairs and non-canonical weekly ranges.
    """
    out = _blocked("INVALID_NY17_PRE_EVENT_COHORT_OR_CLOCK")
    start, end, plan, prepared = (
        _utc(x) for x in (start_at_utc, end_at_utc,
                          plan_declared_at_utc, prepared_at_utc)
    )
    if (horizon not in ("D1", "W1") or start is None or end is None
            or plan is None or prepared is None or not plan <= prepared < start
            or (start, end) not in _nominal_windows(horizon)
            or not isinstance(claims, (list, tuple)) or len(claims) != 28
            or len(set(OFFICIAL_PAIRS)) != 28):
        return out

    by_pair: dict[str, dict[str, Any]] = {}
    opportunity_ids: set[str] = set()
    abstained = 0
    for row in claims:
        if not isinstance(row, Ny17ForecastClaim):
            out["reason"] = "INVALID_FORECAST_RECORD_TYPE"
            return out
        cutoff, issued, cstart, cend = (
            _utc(x) for x in (row.features_cutoff_at,
                              row.forecast_issued_at,
                              row.outcome_start_at, row.outcome_end_at)
        )
        if (not isinstance(row.opportunity_id, str)
                or ID_PATTERN.fullmatch(row.opportunity_id) is None
                or row.opportunity_id in opportunity_ids
                or row.pair not in OFFICIAL_PAIRS or row.pair in by_pair
                or row.horizon != horizon
                or row.direction_claim not in SIDES
                or cstart != start or cend != end
                or cutoff is None or issued is None
                or not plan <= cutoff <= issued <= prepared < start
                or not isinstance(row.model_sha256_claim, str)
                or SHA64.fullmatch(row.model_sha256_claim) is None
                or not isinstance(row.evidence_sha256_claim, str)
                or SHA64.fullmatch(row.evidence_sha256_claim) is None
                or (row.direction_claim == "ABSTAIN"
                    and row.abstain_reason not in ABSTAIN_REASONS)
                or (row.direction_claim != "ABSTAIN"
                    and row.abstain_reason is not None)):
            out["reason"] = "DUPLICATE_MISSING_LATE_OR_INCONSISTENT_FORECAST_CLAIM"
            return out
        opportunity_ids.add(row.opportunity_id)
        abstained += row.direction_claim == "ABSTAIN"
        by_pair[row.pair] = {
            "opportunity_id": row.opportunity_id,
            "pair": row.pair,
            "direction_claim_unattested": row.direction_claim,
            "abstain_reason": row.abstain_reason,
            "features_cutoff_utc_claim": _stamp(cutoff),
            "issued_utc_claim": _stamp(issued),
            "model_sha256_claim": row.model_sha256_claim,
            "evidence_sha256_claim": row.evidence_sha256_claim,
        }

    if set(by_pair) != set(OFFICIAL_PAIRS):
        out["reason"] = "MISSING_OR_EXTRA_FX28_PAIR_FORECASTS"
        return out
    payload = {
        "schema": SCHEMA,
        "campaign_id": CAMPAIGN_ID,
        "horizon": horizon,
        "start_utc": _stamp(start),
        "end_utc": _stamp(end),
        "prepared_utc_claim": _stamp(prepared),
        "pairs": [by_pair[pair] for pair in OFFICIAL_PAIRS],
    }
    frozen_json = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    )
    digest = sha256(frozen_json.encode("ascii")).hexdigest()
    body = "\n".join((
        HEADER,
        "repository=" + REPO,
        "issue_number=" + str(ISSUE_NUMBER),
        "campaign_id=" + CAMPAIGN_ID,
        "horizon=" + horizon,
        "window_start_utc=" + _stamp(start),
        "window_end_utc=" + _stamp(end),
        "slots=28",
        "directional_claims=" + str(28 - abstained),
        "abstentions=" + str(abstained),
        "forecast_json_sha256=" + digest,
        "research_only=true",
        "trade_authorized=false",
    ))
    out.update({
        "state": "LAB_NY17_FORECAST_ANCHOR_TEXT_PREPARED_NOT_POSTED",
        "reason": "UNPOSTED_PAYLOAD_AND_GITHUB_COMMENT_NOT_INDEPENDENT_EVIDENCE",
        "horizon": horizon, "pair_count": 28,
        "directional_claims": 28 - abstained, "abstentions": abstained,
        "forecast_json": frozen_json, "forecast_sha256": digest,
        "anchor_comment_body": body,
        "forecast_scope_locally_complete": True,
    })
    return out


def inspect_ny17_forecast_github_comment_claim_lab(
    *, prepared: Any, start_at_utc: Any,
    comment: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Documentary check only; actual GitHub connector data is mandatory.

    A fabricated GitHubCommentClaim can pass this pure test. We deliberately
    NEVER mark external attestation, accuracy or live readiness as true.
    """
    out = _blocked("INVALID_PREPARED_FORECAST_OR_GITHUB_COMMENT")
    target, now = _utc(start_at_utc), _utc(inspected_at_utc)
    if (not isinstance(prepared, dict)
            or prepared.get("state") !=
                "LAB_NY17_FORECAST_ANCHOR_TEXT_PREPARED_NOT_POSTED"
            or prepared.get("schema") != SCHEMA
            or target is None or now is None
            or not isinstance(comment, GitHubCommentClaim)):
        return out
    try:
        payload_raw = prepared["forecast_json"]
        digest = prepared["forecast_sha256"]
        payload = json.loads(payload_raw)
        start = _utc(datetime.fromisoformat(payload["start_utc"].replace("Z", "+00:00")))
        body = prepared["anchor_comment_body"]
        if (not isinstance(payload_raw, str) or not isinstance(digest, str)
                or SHA64.fullmatch(digest) is None
                or sha256(payload_raw.encode("ascii")).hexdigest() != digest
                or not isinstance(payload, dict)
                or len(payload["pairs"]) != 28
                or start != target or not isinstance(body, str)
                or "forecast_json_sha256=" + digest not in body):
            out["reason"] = "TAMPERED_FROZEN_FORECAST_JSON_OR_DIGEST"
            return out
    except (ValueError, KeyError, TypeError, UnicodeError, OverflowError):
        out["reason"] = "TAMPERED_FROZEN_FORECAST_JSON_OR_DIGEST"
        return out

    if (type(comment.comment_id) is not int or not 1 <= comment.comment_id <= 10**15
            or comment.body != body
            or comment.api_url !=
                f"https://api.github.com/repos/{REPO}/issues/comments/{comment.comment_id}"
            or comment.html_url !=
                f"https://github.com/{REPO}/issues/{ISSUE_NUMBER}#issuecomment-{comment.comment_id}"):
        out["reason"] = "WRONG_ISSUE_COMMENT_OR_BODY"
        return out
    created, updated, retrieved = (
        _utc(x) for x in (comment.created_at, comment.updated_at,
                          comment.retrieved_at)
    )
    prepared_claim = _utc(datetime.fromisoformat(
        payload["prepared_utc_claim"].replace("Z", "+00:00")))
    if (created is None or updated is None or retrieved is None
            or prepared_claim is None
            or not prepared_claim <= created <= retrieved <= now
            or not retrieved < target
            or updated != created):
        out["reason"] = "COMMENT_LATE_UNOBSERVED_OR_EDITED"
        return out

    out.update({
        "state": "LAB_NY17_GITHUB_FORECAST_COMMENT_CHRONOLOGY_CLAIM_ONLY",
        "reason": "CALLER_CAN_FORGE_COMMENT_METADATA_EXTERNAL_PROOF_PENDING",
        "pair_count": 28, "horizon": payload["horizon"],
        "directional_claims": prepared["directional_claims"],
        "abstentions": prepared["abstentions"],
        "forecast_json": payload_raw, "forecast_sha256": digest,
        "anchor_comment_body": body,
        "forecast_scope_locally_complete": True,
        "comment_chronology_documentary_consistent": True,
    })
    return out


__all__ = (
    "SCHEMA", "HEADER", "ISSUE_NUMBER",
    "prepare_ny17_full_forecast_anchor_lab",
    "inspect_ny17_forecast_github_comment_claim_lab",
)
