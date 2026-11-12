"""Pure LAB: prepare and check a *claimed* external pre-news hash anchor.

No GitHub calls, postings, verified external timestamps or operational signals.
An API-looking observation supplied by a caller is NOT authenticated evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_trader_event_forecast_lock_lab import (
    ForecastDraft, ForecastLock, freeze_pre_event_forecast_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FORECAST_GITHUB_COMMENT_ANCHOR_LAB_V1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")


@dataclass(frozen=True)
class AnchorTarget:
    repository_full_name: str
    issue_or_pr_number: int


@dataclass(frozen=True)
class ClaimedGitHubComment:
    comment_id: int
    api_url: str
    html_url: str
    body: str
    created_at: datetime
    updated_at: datetime
    fetched_at: datetime


def _utc(v: Any) -> datetime | None:
    if (not isinstance(v, datetime) or v.tzinfo is None
            or v.utcoffset() is None or v.microsecond != 0):
        return None
    return v.astimezone(timezone.utc)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_ANCHOR_BLOCKED", "reason": reason,
        "anchor_body_documentary": None, "forecast_sha256": None,
        "anchor_created_utc_claim": None, "anchor_updated_utc_claim": None,
        "anchor_comment_id_claim": None,
        "timestamp_order_self_consistent_only": False,
        "github_api_response_independently_authenticated": False,
        "github_server_clock_independently_verified": False,
        "pre_event_forecast_provenance_verified": False,
        "consensus_source_independently_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "fx_bias": None, "index_bias": None,
        "trade_authorized": False, "publishable": False,
        "live_alert_allowed": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def _target_ok(target: Any) -> bool:
    return (isinstance(target, AnchorTarget)
            and isinstance(target.repository_full_name, str)
            and _REPO.fullmatch(target.repository_full_name) is not None
            and type(target.issue_or_pr_number) is int
            and 1 <= target.issue_or_pr_number <= 1_000_000_000)


def _rebuild_lock(locked: Any) -> tuple[dict[str, Any], datetime, datetime] | None:
    """Require a syntactically valid lock that freeze() itself can reproduce."""
    if (not isinstance(locked, ForecastLock)
            or not isinstance(locked.canonical_payload_json, str)
            or not isinstance(locked.payload_sha256, str)
            or _SHA.fullmatch(locked.payload_sha256) is None
            or len(locked.canonical_payload_json) > 4096
            or sha256(locked.canonical_payload_json.encode("utf-8")).hexdigest()
            != locked.payload_sha256):
        return None
    try:
        raw = json.loads(locked.canonical_payload_json)
        if not isinstance(raw, dict):
            return None
        scheduled = datetime.fromisoformat(raw["scheduled_release_utc"])
        captured = datetime.fromisoformat(raw["forecast_captured_utc"])
        prior_at = datetime.fromisoformat(raw["previous_available_utc"])
        consensus_at = datetime.fromisoformat(raw["consensus_available_utc"])
        draft = ForecastDraft(
            event_id=raw["event_id"], currency=raw["currency"],
            metric=raw["metric"], target_period=raw["target_period"],
            unit=raw["unit"], scheduled_release_at=scheduled,
            forecast_captured_at=captured, previous_value=raw["previous_value"],
            previous_available_at=prior_at, consensus_value=raw["consensus_value"],
            consensus_available_at=consensus_at,
            model_estimate=raw["model_estimate"], model_version=raw["model_version"],
            previous_source_sha256_claim=raw["previous_source_sha256_claim"],
            consensus_source_sha256_claim=raw["consensus_source_sha256_claim"],
        )
        reproduced = freeze_pre_event_forecast_lab(draft, as_of_utc=captured)
        if reproduced["lock"] != locked:
            return None
        return raw, _utc(captured), _utc(scheduled)
    except (KeyError, TypeError, ValueError, OverflowError, UnicodeEncodeError,
            RecursionError):
        return None


def _body(locked: ForecastLock, raw: dict[str, Any]) -> str:
    # Deliberately excludes model estimate, prior, consensus and source payloads.
    return "\n".join((
        "ATLASQUANT_TRADER_RESEARCH_ONLY_PRE_EVENT_HASH_ANCHOR_V1",
        "schema=" + SCHEMA,
        "event_id=" + raw["event_id"],
        "scheduled_release_utc=" + raw["scheduled_release_utc"],
        "forecast_payload_sha256=" + locked.payload_sha256,
        "not_a_trading_signal=true",
    ))


def prepare_pre_event_anchor_lab(
    locked: Any, target: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Prepare text, without posting it; reject if release already reached."""
    out = _base("INVALID_LOCK_TARGET_OR_CLOCK")
    now, rebuilt = _utc(as_of_utc), _rebuild_lock(locked)
    if now is None or rebuilt is None or not _target_ok(target):
        return out
    raw, captured, release = rebuilt
    if not captured <= now < release:
        return out
    out.update({
        "state": "LAB_ANCHOR_TEXT_PREPARED_NOT_POSTED",
        "reason": "BODY_PREPARED_WITHOUT_EXTERNAL_PUBLICATION_OR_TIMESTAMP",
        "anchor_body_documentary": _body(locked, raw),
        "forecast_sha256": locked.payload_sha256,
    })
    return out


def assess_claimed_github_anchor_lab(
    locked: Any, target: Any, candidate: Any, *, as_of_utc: Any,
) -> dict[str, Any]:
    """Check chronology of caller-supplied GitHub fields; cannot verify GitHub."""
    out = _base("INVALID_LOCK_TARGET_COMMENT_OR_CLOCK")
    now, rebuilt = _utc(as_of_utc), _rebuild_lock(locked)
    if (now is None or rebuilt is None or not _target_ok(target)
            or not isinstance(candidate, ClaimedGitHubComment)
            or type(candidate.comment_id) is not int
            or not 1 <= candidate.comment_id <= 10**15):
        return out
    raw, captured, release = rebuilt
    created, updated, fetched = (_utc(candidate.created_at),
                                 _utc(candidate.updated_at),
                                 _utc(candidate.fetched_at))
    expected_api = (f"https://api.github.com/repos/{target.repository_full_name}"
                    f"/issues/comments/{candidate.comment_id}")
    expected_html = (
        f"https://github.com/{target.repository_full_name}"
        f"/pull/{target.issue_or_pr_number}#issuecomment-{candidate.comment_id}"
    )
    expected_issue_html = (
        f"https://github.com/{target.repository_full_name}"
        f"/issues/{target.issue_or_pr_number}#issuecomment-{candidate.comment_id}"
    )
    if (created is None or updated is None or fetched is None
            or not captured <= created <= updated < release
            or not updated <= fetched <= now
            or candidate.api_url != expected_api
            or candidate.html_url not in (expected_html, expected_issue_html)
            or candidate.body != _body(locked, raw)):
        return out
    out.update({
        "state": "LAB_COMMENT_ANCHOR_CHRONOLOGY_CANDIDATE_UNATTESTED",
        "reason": "CALLER_SUPPLIED_GITHUB_FIELDS_ARE_NOT_API_AUTHENTICATION",
        "forecast_sha256": locked.payload_sha256,
        "anchor_comment_id_claim": candidate.comment_id,
        "anchor_created_utc_claim": created.isoformat(),
        "anchor_updated_utc_claim": updated.isoformat(),
        "timestamp_order_self_consistent_only": True,
    })
    return out


__all__ = [
    "SCHEMA", "AnchorTarget", "ClaimedGitHubComment",
    "prepare_pre_event_anchor_lab", "assess_claimed_github_anchor_lab",
]
