"""AtlasQuant LAB: two-stage prospective 28-FX D1/W1 census GitHub anchor.

Pure offline validation. GitHub comment fields are caller-supplied and NOT
independently authenticated in this module. Never infer a trading signal,
market edge, externally verified timestamp or successful publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any

from atlasquant_trader_fx_trial_census_lab import (
    FrozenBlob, verify_frozen_fx_census_lab, _verified_roster,
)

SCHEMA = "ATLASQUANT_FX_TWO_STAGE_GITHUB_CENSUS_ANCHOR_LAB_V1"
REPO_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
STAGES = ("ROSTER", "CENSUS")


@dataclass(frozen=True)
class GitHubCommentClaim:
    """Untrusted fields *claimed* to be returned by GitHub's issue comments API."""
    comment_id: int
    api_url: str
    html_url: str
    body: str
    created_at: datetime
    updated_at: datetime
    retrieved_at: datetime


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    if v.microsecond:  # GitHub timestamp precision is seconds here.
        return None
    return v.astimezone(timezone.utc)


def _parse(v: Any) -> datetime | None:
    if not isinstance(v, str) or len(v) > 35:
        return None
    try:
        return _utc(datetime.fromisoformat(v.replace("Z", "+00:00")))
    except (ValueError, TypeError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_GITHUB_CENSUS_ANCHOR_BLOCKED",
        "reason": reason, "roster_anchor_body": None,
        "census_anchor_body": None,
        "roster_comment_id_claim": None, "census_comment_id_claim": None,
        "earliest_target_open_utc": None,
        "roster_precedes_first_decision_claim": False,
        "census_precedes_target_claim": False,
        "comment_unchanged_since_creation_claim": False,
        "comment_fields_crosschecked_documentary_only": False,
        "github_comment_fields_independently_authenticated": False,
        "external_precommitment_verified": False,
        "point_in_time_market_information_verified": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _source(roster: Any, census: Any) -> tuple[dict, dict, datetime, datetime, datetime] | None:
    plan = _verified_roster(roster)
    if plan is None or not isinstance(census, FrozenBlob):
        return None
    checked = verify_frozen_fx_census_lab(roster, census)
    if checked["state"] != "LAB_FULL_CENSUS_HASHED_UNATTESTED":
        return None
    try:
        doc = json.loads(census.canonical_json)
        if not isinstance(doc, dict) or len(doc["decisions"]) != 56:
            return None
        planned_at = _parse(plan["plan_frozen_utc_claim"])
        census_at = _parse(doc["census_frozen_utc_claim"])
        first_decision = min(_parse(d["recorded_utc_claim"]) for d in doc["decisions"])
        first_target = min(_parse(s["target_open_utc"]) for s in plan["slots"])
        if any(x is None for x in (planned_at, census_at, first_decision, first_target)):
            return None
        if not planned_at <= first_decision <= census_at < first_target:
            return None
        return plan, doc, first_decision, first_target, census_at
    except (KeyError, IndexError, TypeError, ValueError, RecursionError):
        return None


def _valid_target(repo: Any, number: Any) -> bool:
    return (isinstance(repo, str) and REPO_PATTERN.fullmatch(repo) is not None
            and type(number) is int and 1 <= number <= 1_000_000_000)


def _body(stage: str, repo: str, number: int, roster: FrozenBlob,
          census: FrozenBlob, plan: dict, first_target: datetime) -> str:
    # Hash references only, NO raw predictions / trading or customer data.
    lines = [
        "ATLASQUANT_FX_PROSPECTIVE_ANCHOR_LAB_V1",
        "stage=" + stage,
        "repository=" + repo,
        "issue_number=" + str(number),
        "cohort_id=" + plan["cohort_id"],
        "rule_version=" + plan["rule_version"],
        "roster_sha256=" + roster.sha256,
        "slots_expected=56",
        "first_target_open_utc=" + first_target.isoformat().replace("+00:00", "Z"),
    ]
    if stage == "CENSUS":
        lines.append("census_sha256=" + census.sha256)
    lines.extend(("research_only=true", "trade_authorized=false"))
    return "\n".join(lines)


def prepare_roster_github_anchor_lab(
    *, roster: Any, repository_full_name: Any, issue_number: Any,
    prepared_at: Any,
) -> dict[str, Any]:
    """Prepare the roster comment BEFORE the first prediction is recorded.

    A roster can and must be anchored without requiring a future census.
    Caller is responsible for posting and subsequently checking the comment.
    """
    out = _blocked("INVALID_ROSTER_TARGET_OR_CLOCK")
    plan, now = _verified_roster(roster), _utc(prepared_at)
    if plan is None or now is None or not _valid_target(repository_full_name, issue_number):
        return out
    first_target = min(_parse(s["target_open_utc"]) for s in plan["slots"])
    frozen = _parse(plan["plan_frozen_utc_claim"])
    if not frozen <= now < first_target:
        out["reason"] = "ROSTER_ANCHOR_PREPARATION_OUTSIDE_FUTURE_WINDOW"
        return out
    out.update({
        "state": "LAB_ROSTER_ANCHOR_TEXT_PREPARED_NOT_POSTED",
        "reason": "ROSTER_COMMENT_NOT_POSTED_OR_VERIFIED",
        "roster_anchor_body": _body("ROSTER", repository_full_name, issue_number,
                                    roster, None, plan, first_target),
        "earliest_target_open_utc": first_target.isoformat(),
    })
    return out


def prepare_census_github_anchor_lab(
    *, roster: Any, census: Any, repository_full_name: Any,
    issue_number: Any, prepared_at: Any,
) -> dict[str, Any]:
    """Prepare the later 56-decision census comment before market outcomes."""
    out = _blocked("INVALID_ROSTER_CENSUS_TARGET_OR_CLOCK")
    source, now = _source(roster, census), _utc(prepared_at)
    if source is None or now is None or not _valid_target(repository_full_name, issue_number):
        return out
    plan, _, _, first_target, census_at = source
    if not census_at <= now < first_target:
        out["reason"] = "CENSUS_ANCHOR_PREPARATION_OUTSIDE_FUTURE_WINDOW"
        return out
    out.update({
        "state": "LAB_CENSUS_ANCHOR_TEXT_PREPARED_NOT_POSTED",
        "reason": "CENSUS_COMMENT_NOT_POSTED_OR_VERIFIED",
        "census_anchor_body": _body("CENSUS", repository_full_name, issue_number,
                                    roster, census, plan, first_target),
        "earliest_target_open_utc": first_target.isoformat(),
    })
    return out


def _comment_matches(
    claim: Any, *, repo: str, number: int, body: str,
    earliest: datetime, latest: datetime, checked_at: datetime,
) -> bool:
    if (not isinstance(claim, GitHubCommentClaim)
            or type(claim.comment_id) is not int
            or not 1 <= claim.comment_id <= 10**15
            or not isinstance(claim.api_url, str)
            or not isinstance(claim.html_url, str)
            or claim.body != body):
        return False
    created, updated, retrieved = (_utc(claim.created_at), _utc(claim.updated_at),
                                   _utc(claim.retrieved_at))
    if (created is None or updated is None or retrieved is None
            or not earliest <= created <= latest
            or updated != created  # Edited comments must not retroactively replace a lock.
            or not created <= retrieved <= checked_at):
        return False
    api = f"https://api.github.com/repos/{repo}/issues/comments/{claim.comment_id}"
    html_root = f"https://github.com/{repo}"
    html = {f"{html_root}/pull/{number}#issuecomment-{claim.comment_id}",
            f"{html_root}/issues/{number}#issuecomment-{claim.comment_id}"}
    return claim.api_url == api and claim.html_url in html


def inspect_two_stage_github_anchor_claims_lab(
    *, roster: Any, census: Any, repository_full_name: Any,
    issue_number: Any, roster_comment: Any, census_comment: Any,
    inspected_at: Any,
) -> dict[str, Any]:
    """Check documentary consistency of two alleged GitHub comments.

    An actual GitHub connector read at the relevant times is required for
    external attestation. Never return `external_precommitment_verified=True`.
    """
    out = _blocked("INVALID_SOURCE_TARGET_OR_INSPECTION_CLOCK")
    source, now = _source(roster, census), _utc(inspected_at)
    if source is None or now is None or not _valid_target(repository_full_name, issue_number):
        return out
    plan, _, first_decision, first_target, census_at = source
    body_roster = _body("ROSTER", repository_full_name, issue_number,
                        roster, census, plan, first_target)
    body_census = _body("CENSUS", repository_full_name, issue_number,
                        roster, census, plan, first_target)
    out["roster_anchor_body"] = body_roster
    out["census_anchor_body"] = body_census
    out["earliest_target_open_utc"] = first_target.isoformat()
    if not _comment_matches(
            roster_comment, repo=repository_full_name,
            number=issue_number, body=body_roster,
            earliest=_parse(plan["plan_frozen_utc_claim"]),
            latest=first_decision, checked_at=now):
        out["reason"] = "ROSTER_ANCHOR_MISSING_LATE_EDITED_OR_MISMATCHED"
        return out
    # Equal-second timestamps do not establish the roster came first.
    if _utc(roster_comment.created_at) >= first_decision:
        out["reason"] = "ROSTER_NOT_STRICTLY_BEFORE_FIRST_DECISION"
        return out
    out["roster_precedes_first_decision_claim"] = True
    if not _comment_matches(
            census_comment, repo=repository_full_name,
            number=issue_number, body=body_census,
            earliest=census_at, latest=first_target, checked_at=now):
        out["reason"] = "CENSUS_ANCHOR_MISSING_LATE_EDITED_OR_MISMATCHED"
        return out
    if (roster_comment.comment_id == census_comment.comment_id
            or _utc(census_comment.created_at) <= _utc(roster_comment.created_at)
            or _utc(census_comment.created_at) == first_target):
        out["reason"] = "REUSED_COMMENT_OR_INVALID_ANCHOR_ORDER"
        return out
    # Require contemporaneous retrieval before the first bar started.
    if (_utc(roster_comment.retrieved_at) >= first_target
            or _utc(census_comment.retrieved_at) >= first_target):
        out["reason"] = "ANCHOR_NOT_OBSERVED_BEFORE_FIRST_TARGET"
        return out
    out.update({
        "state": "LAB_GITHUB_TWO_ANCHOR_CHRONOLOGY_CLAIM_ONLY",
        "reason": "CALLER_GITHUB_FIELDS_NOT_INDEPENDENTLY_ATTESTED",
        "roster_comment_id_claim": roster_comment.comment_id,
        "census_comment_id_claim": census_comment.comment_id,
        "census_precedes_target_claim": True,
        "comment_unchanged_since_creation_claim": True,
        "comment_fields_crosschecked_documentary_only": True,
    })
    return out


__all__ = ["SCHEMA", "GitHubCommentClaim", "prepare_roster_github_anchor_lab",
           "prepare_census_github_anchor_lab",
           "inspect_two_stage_github_anchor_claims_lab"]
