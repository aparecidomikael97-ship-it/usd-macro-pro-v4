"""Prospective FX28 NY17 D1/W1 forecast-witness census, claim-only LAB.

A historical price matching a forecast typed after the session is not proof.
This module freezes the expected 672 pair-horizon opportunities in issue #1884
and separates NOT_YET_DUE from MISSED_NO_PRE_EVENT_WITNESS. For each nominal
session it optionally checks a *claimed* GitHub issue comment that anchors the
SHA-256 of all 28 prospective predictions (including ABSTAIN).

No actual GitHub API calls, broker data or predictive model are performed.
Comment fields and forecasts are supplied by caller and may be forged.
Even a fully populated witness census is NEVER verified external evidence,
directional accuracy or a trading signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    _nominal_windows,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_PROSPECTIVE_WITNESS_CENSUS_LAB_V1"
HEADER = "ATLASQUANT_FX28_NY17_WINDOW_PRE_EVENT_COMMITMENT_LAB_V1"
HEX = re.compile(r"[0-9a-f]{64}\Z")
DIRECTIONS = frozenset(("UP", "DOWN", "ABSTAIN"))
PREWINDOW_LOOKBACK = timedelta(hours=12)  # same frozen source-gate interval
ABSTAIN_REASONS = frozenset((
    "MISSING_MACRO", "CONFLICTING_EVIDENCE", "LOW_CONFIDENCE",
    "STALE_DATA", "EVENT_BLACKOUT", "UNVERIFIED_SOURCE", "OTHER",
))
# Publication date of fixed *calendar*, independently read in GitHub by
# the human agent. This code does not prove that API metadata is authentic.
CAMPAIGN_PUBLICATION_CLAIM_UTC = datetime(
    2026, 11, 12, 18, 21, 59, tzinfo=timezone.utc)
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE_NUMBER = 1884


@dataclass(frozen=True)
class PairForecastClaim:
    pair: str
    direction: str
    abstain_reason: str | None
    feature_cutoff_at: datetime
    forecast_issued_at: datetime
    model_sha256_claim: str
    evidence_sha256_claim: str


@dataclass(frozen=True)
class GithubWitnessClaim:
    comment_id: int
    comment_body: str
    api_url: str
    html_url: str
    created_at: datetime
    updated_at: datetime
    retrieved_at: datetime


@dataclass(frozen=True)
class WindowForecastWitnessClaim:
    horizon: str
    start_at: datetime
    end_at: datetime
    forecast_roster: tuple[PairForecastClaim, ...]
    github_witness: GithubWitnessClaim


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_WITNESS_CENSUS_BLOCKED",
        "reason": reason, "campaign_id": CAMPAIGN_ID,
        "calendar_issue_url": CALENDAR_ISSUE,
        "nominal_windows_expected": 24,
        "witness_must_be_created_in_final_12h": True,
        "forecast_and_feature_cutoff_must_be_in_final_12h": True,
        "early_body_dry_runs_are_not_witnesses": True,
        "witness_window_limit_hours": 12,
        "pair_horizon_slots_expected": EXPECTED_PAIR_HORIZON_SLOTS,
        "not_yet_due_slots": 0, "due_missing_witness_slots": 0,
        "due_witness_claim_only_slots": 0,
        "due_directional_claim_only_slots": 0,
        "due_abstention_claim_only_slots": 0,
        "future_witness_claim_only_slots": 0,
        "per_horizon": {}, "windows": [],
        "all_nominal_opportunities_accounted": False,
        "caller_comment_fields_crosschecked_locally": False,
        "github_comments_independently_authenticated": False,
        "pre_event_forecasts_independently_witnessed": False,
        "point_in_time_macro_authenticated": False,
        "broker_price_source_authenticated": False,
        "calibrated_direction_probability": None,
        "validated_directional_accuracy": None,
        "out_of_sample_accuracy_validated": False,
        "operational_bias": "AGUARDAR",
        "live_alert_allowed": False, "publishable": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _canonical_roster(
    claim: WindowForecastWitnessClaim, *, inspected_at: datetime,
    enforce_prewindow: bool = False,
) -> tuple[list[dict[str, str | None]], datetime] | None:
    start, end = _utc(claim.start_at), _utc(claim.end_at)
    if (start is None or end is None
            or not isinstance(claim.forecast_roster, tuple)
            or len(claim.forecast_roster) != 28):
        return None
    prewindow_open = start - PREWINDOW_LOOKBACK
    payload = []
    seen = set()
    last_issue = CAMPAIGN_PUBLICATION_CLAIM_UTC
    for record in claim.forecast_roster:
        if not isinstance(record, PairForecastClaim):
            return None
        cutoff = _utc(record.feature_cutoff_at)
        issued = _utc(record.forecast_issued_at)
        if (not isinstance(record.pair, str)
                or record.pair not in OFFICIAL_PAIRS or record.pair in seen
                or record.direction not in DIRECTIONS
                or not _digest(record.model_sha256_claim)
                or not _digest(record.evidence_sha256_claim)
                or cutoff is None or issued is None
                or not cutoff <= issued <= inspected_at
                or not CAMPAIGN_PUBLICATION_CLAIM_UTC <= issued < start
                or (enforce_prewindow and cutoff < prewindow_open)
                or (enforce_prewindow and issued < prewindow_open)
                or (record.direction == "ABSTAIN"
                    and record.abstain_reason not in ABSTAIN_REASONS)
                or (record.direction != "ABSTAIN"
                    and record.abstain_reason is not None)):
            return None
        seen.add(record.pair)
        last_issue = max(last_issue, issued)
        payload.append({
            "pair": record.pair, "direction_claim": record.direction,
            "abstain_reason": record.abstain_reason,
            "feature_cutoff_claim_utc": _stamp(cutoff),
            "forecast_issued_claim_utc": _stamp(issued),
            "model_sha256_claim": record.model_sha256_claim,
            "evidence_sha256_claim": record.evidence_sha256_claim,
        })
    if seen != set(OFFICIAL_PAIRS):
        return None
    return sorted(payload, key=lambda x: x["pair"]), last_issue


def prepare_window_witness_body_lab(
    *, horizon: Any, start_at: Any, end_at: Any,
    forecast_roster: Any, prepared_at: Any,
) -> dict[str, Any]:
    """Construct a hash-only anchor BODY, but NEVER publish it to GitHub."""
    out = {"state": "LAB_WITNESS_BODY_BLOCKED", "reason": "INVALID_WINDOW_OR_FORECASTS",
           "body": None, "forecast_roster_sha256": None,
           "canonical_forecast_json": None,
           "canonical_forecast_payload_retained_externally": False,
           "body_posted_on_github": False, "external_precommit_verified": False}
    now, start, end = _utc(prepared_at), _utc(start_at), _utc(end_at)
    # Early research dry-runs may prepare hashes, but they are never
    # a prospective GitHub witness. Only census acceptance enforces the
    # 12h pre-window contract. No external write occurs here.
    if now is None or start is None or end is None or not now < start:
        return out
    if horizon not in ("D1", "W1") or (start, end) not in _nominal_windows(horizon):
        return out
    provisional = WindowForecastWitnessClaim(horizon, start, end, forecast_roster, None)
    valid = _canonical_roster(provisional, inspected_at=now)
    if valid is None:
        return out
    roster, _ = valid
    # Preserve the exact canonical bytes behind the public digest. A GitHub
    # comment with only a SHA-256 is not enough if these bytes disappear.
    canonical_json = json.dumps({
        "schema": SCHEMA, "campaign_id": CAMPAIGN_ID,
        "horizon": horizon, "start_utc": _stamp(start),
        "end_utc": _stamp(end), "pairs": roster,
    }, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    digest = sha256(canonical_json.encode("ascii")).hexdigest()
    body = "\n".join((
        HEADER, "campaign_id=" + CAMPAIGN_ID,
        "horizon=" + horizon, "start_utc=" + _stamp(start),
        "end_utc=" + _stamp(end), "pairs=28",
        "roster_sha256=" + digest, "research_only=true",
        "trade_authorized=false",
    ))
    out.update(state="LAB_WITNESS_BODY_PREPARED_NOT_POSTED",
               reason="HASH_ONLY_DOES_NOT_PROVE_TIMESTAMP_OR_SOURCE",
               body=body, forecast_roster_sha256=digest,
               canonical_forecast_json=canonical_json)
    return out


def inspect_prospective_fx28_witness_census_lab(
    *, window_claims: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    """Reconcile every future/due slot; reject backdated/edited claims.

    All witness metadata are user-supplied. Even success proves only *local*
    consistency of those claims against the expected campaign.
    """
    out = _base("INVALID_COLLECTION_OR_CLOCK")
    now = _utc(inspected_at_utc)
    if (now is None or now < CAMPAIGN_PUBLICATION_CLAIM_UTC
            or not isinstance(window_claims, (tuple, list))
            or len(window_claims) > 24
            or len(OFFICIAL_PAIRS) != 28 or len(set(OFFICIAL_PAIRS)) != 28):
        return out
    windows = {(h, start): end for h in ("D1", "W1")
               for start, end in _nominal_windows(h)}
    if len(windows) != 24:
        out["reason"] = "FROZEN_CALENDAR_INVALID"
        return out

    seen: dict[tuple[str, datetime], tuple[int, int, int]] = {}
    comment_ids: set[int] = set()
    for claim in window_claims:
        if not isinstance(claim, WindowForecastWitnessClaim):
            out["reason"] = "INVALID_WINDOW_WITNESS_CLAIM_TYPE"
            return out
        start, end = _utc(claim.start_at), _utc(claim.end_at)
        key = (claim.horizon, start)
        if (start is None or end is None or key not in windows
                or windows[key] != end or key in seen):
            out["reason"] = "DUPLICATE_UNKNOWN_OR_WRONG_NY17_WINDOW"
            return out
        valid = _canonical_roster(claim, inspected_at=now,
                                  enforce_prewindow=True)
        if valid is None:
            out["reason"] = "INCOMPLETE_DUPLICATE_POST_EVENT_OR_INVALID_28FX_FORECASTS"
            return out
        roster, latest_issue = valid
        witness = claim.github_witness
        if not isinstance(witness, GithubWitnessClaim):
            out["reason"] = "MISSING_GITHUB_WITNESS_CLAIM"
            return out
        created, updated, retrieved = (_utc(x) for x in (
            witness.created_at, witness.updated_at, witness.retrieved_at))
        if (type(witness.comment_id) is not int
                or witness.comment_id < 1 or witness.comment_id in comment_ids
                or created is None or updated is None or retrieved is None
                or not max(latest_issue, start - PREWINDOW_LOOKBACK)
                    <= created < start
                or updated != created
                or not created <= retrieved < start
                or retrieved > now
                or witness.api_url != (
                    f"https://api.github.com/repos/{REPO}/issues/comments/{witness.comment_id}"
                )
                or witness.html_url != (
                    f"https://github.com/{REPO}/issues/{ISSUE_NUMBER}"
                    f"#issuecomment-{witness.comment_id}"
                )):
            out["reason"] = "LATE_EDITED_UNOBSERVED_OR_FAKE_GITHUB_COMMENT_FIELDS"
            return out
        prepared = prepare_window_witness_body_lab(
            horizon=claim.horizon, start_at=start, end_at=end,
            forecast_roster=claim.forecast_roster, prepared_at=created)
        if (prepared["state"] != "LAB_WITNESS_BODY_PREPARED_NOT_POSTED"
                or not isinstance(witness.comment_body, str)
                or witness.comment_body != prepared["body"]):
            out["reason"] = "COMMENT_BODY_NOT_BOUND_TO_ALL_28_FORECASTS"
            return out
        comment_ids.add(witness.comment_id)
        abstain = sum(v["direction_claim"] == "ABSTAIN" for v in roster)
        seen[key] = (28, 28 - abstain, abstain)

    horizon_total: dict[str, dict[str, int]] = {}
    details = []
    future = missing = witnessed = directional = abstained = future_witness = 0
    for horizon in ("D1", "W1"):
        counts = {"windows": 0, "slots_expected": 0,
                  "future_slots": 0, "due_no_witness_slots": 0,
                  "witness_claim_only_slots": 0}
        for start, end in _nominal_windows(horizon):
            key = (horizon, start)
            is_due = now >= start
            count, ndir, nabs = seen.get(key, (0, 0, 0))
            status = ("FUTURE_NOT_DUE" if not is_due and count == 0 else
                      "FUTURE_WITNESS_CLAIM_ONLY" if not is_due else
                      "DUE_MISSING_PRE_EVENT_WITNESS" if count == 0 else
                      "DUE_PRE_EVENT_WITNESS_CLAIM_ONLY")
            if is_due:
                witnessed += count
                missing += 28 - count
                directional += ndir
                abstained += nabs
                counts["due_no_witness_slots"] += 28 - count
                counts["witness_claim_only_slots"] += count
            else:
                future += 28
                counts["future_slots"] += 28
                future_witness += count
            counts["windows"] += 1
            counts["slots_expected"] += 28
            details.append({
                "horizon": horizon, "start_utc": _stamp(start),
                "end_utc": _stamp(end), "pair_slots": 28,
                "state": status,
                "witness_claim_only_slots": count,
                "witness_independently_authenticated": False,
            })
        horizon_total[horizon] = counts
    if future + missing + witnessed != 672:
        out["reason"] = "INTERNAL_PAIR_SLOT_CENSUS_NOT_RECONCILED"
        return out

    out.update({
        "state": "LAB_PROSPECTIVE_WITNESS_CENSUS_CLAIM_ONLY_NO_GO",
        "reason": "COMMENT_METADATA_NOT_INDEPENDENTLY_AUTHENTICATED",
        "not_yet_due_slots": future,
        "due_missing_witness_slots": missing,
        "due_witness_claim_only_slots": witnessed,
        "due_directional_claim_only_slots": directional,
        "due_abstention_claim_only_slots": abstained,
        "future_witness_claim_only_slots": future_witness,
        "per_horizon": horizon_total, "windows": details,
        "all_nominal_opportunities_accounted": True,
        "caller_comment_fields_crosschecked_locally": True,
    })
    return out


__all__ = (
    "SCHEMA", "PairForecastClaim", "GithubWitnessClaim",
    "WindowForecastWitnessClaim", "PREWINDOW_LOOKBACK",
    "prepare_window_witness_body_lab",
    "inspect_prospective_fx28_witness_census_lab",
)
