"""Dry-run first FX28 NY17 forecast-abstention packets vs GitHub comment list.

This pure function never posts to GitHub or invokes a broker. It checks that
the first D1 and W1 windows (15 Nov 2026) have a caller-provided, exact
28-ABSTAIN macro-missing packet and counts matching raw canonical JSON.
It accepts normalized GitHub *comment snapshots*, where created_at/updated_at
may be null. A hash or purported timestamp alone is NOT trusted: never
represent a comment as independently pre-event authenticated here.

User-supplied report JSON, hashes, source timestamps and issue comments can
all be forged. No direction, calibrated probability, model validity, PIT,
broker calendar, execution or market outcome is authorized.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, _nominal_windows,
)
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    SCHEMA as FORECAST_SCHEMA, HEADER as WITNESS_HEADER,
)

SCHEMA = "ATLASQUANT_FX28_FIRST_D1_W1_ABSTAIN_PRECOMMIT_READINESS_LAB_V1"
PREFLIGHT_SCHEMA = "ATLASQUANT_FX28_MACRO_PIT_PRE_EVENT_FORECAST_PREFLIGHT_LAB_V1"
PREFLIGHT_STATE = "LAB_MACRO_PIT_28FX_FORECAST_RESEARCH_ONLY_UNATTESTED"
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE_NUMBER = 1884
MAX_COMMENT_ROWS = 300
MAX_BODY_CHARS = 16_000


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FIRST_ABSTAIN_PREFLIGHT_BLOCKED",
        "reason": reason, "campaign_id": CAMPAIGN_ID,
        "calendar_issue_url": CALENDAR_ISSUE,
        "first_nominal_window_start_utc": "2026-11-15T22:00:00+00:00",
        "expected_horizons": ["D1", "W1"],
        "expected_pair_horizon_slots": 56,
        "prepared_dry_run_abstentions": 0,
        "directional_forecasts": 0,
        "comment_body_matches_found": 0,
        "matching_comments_with_missing_timestamps": 0,
        "horizon_details": {},
        "no_forecasts_or_abstentions_posted_by_this_function": True,
        "github_comment_created_at_independently_authenticated": False,
        "pre_event_witness_independently_attested": False,
        "canonical_bytes_independently_retained": False,
        "original_macro_source_issuer_authenticated": False,
        "macro_first_release_timestamp_attested": False,
        "broker_m15_history_point_in_time_authenticated": False,
        "native_w1_used_as_ny17_label": False,
        "forecast_accuracy_validated": False,
        "directional_probability": None,
        "directional_bias": None, "operational_bias": "AGUARDAR",
        "trade_authorized": False, "live_alert_allowed": False,
        "publishable": False, "worker_enabled": False,
        "scheduler_enabled": False, "network_calls": 0,
        "files_written": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _json_canonical(packet: Any, *, horizon: str,
                    start: datetime, end: datetime,
                    now: datetime) -> bool:
    if not isinstance(packet, str) or not 1 <= len(packet) <= 50_000:
        return False
    try:
        obj = json.loads(packet)
    except (json.JSONDecodeError, ValueError, TypeError):
        return False
    if (type(obj) is not dict
            or obj.get("schema") != FORECAST_SCHEMA
            or obj.get("campaign_id") != CAMPAIGN_ID
            or obj.get("horizon") != horizon
            or obj.get("start_utc") != start.isoformat().replace("+00:00", "Z")
            or obj.get("end_utc") != end.isoformat().replace("+00:00", "Z")):
        return False
    # Compare byte-for-byte canonical representation, not merely parsed
    # values: otherwise two JSON encodings can conceal different digests.
    try:
        canonical = json.dumps(obj, sort_keys=True, ensure_ascii=True,
                               separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, OverflowError):
        # JSON syntax can include nonstandard NaN/Infinity under the
        # standard decoder; never allow a malformed caller packet to
        # crash the readiness preflight.
        return False
    if canonical != packet:
        return False
    pairs = obj.get("pairs")
    if type(pairs) is not list or len(pairs) != 28:
        return False
    names = [row.get("pair") for row in pairs if type(row) is dict]
    if names != sorted(OFFICIAL_PAIRS):
        return False
    expected_keys = frozenset((
        "pair", "direction_claim", "abstain_reason",
        "feature_cutoff_claim_utc", "forecast_issued_claim_utc",
        "model_sha256_claim", "evidence_sha256_claim",
    ))
    for row in pairs:
        if type(row) is not dict or set(row) != expected_keys:
            return False
        if (row["direction_claim"] != "ABSTAIN"
                or row["abstain_reason"] not in ("MISSING_MACRO", "UNVERIFIED_SOURCE")
                or not isinstance(row["model_sha256_claim"], str)
                or not SHA64.fullmatch(row["model_sha256_claim"])
                or not isinstance(row["evidence_sha256_claim"], str)
                or not SHA64.fullmatch(row["evidence_sha256_claim"])):
            return False
        try:
            cutoff = datetime.fromisoformat(
                row["feature_cutoff_claim_utc"].replace("Z", "+00:00"))
            issued = datetime.fromisoformat(
                row["forecast_issued_claim_utc"].replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            return False
        cc, ii = _utc(cutoff), _utc(issued)
        if (cc is None or ii is None or
                not cc <= ii <= now or not ii < start):
            return False
    return True


def inspect_first_fx28_pre_event_abstain_readiness_lab(
    *, preflight_reports_by_horizon: Any,
    github_issue_comment_snapshots: Any, inspected_at_utc: Any,
) -> dict[str, Any]:
    result = _base("INVALID_INPUT_OR_CURRENT_CLOCK")
    now = _utc(inspected_at_utc)
    if (now is None or not isinstance(preflight_reports_by_horizon, dict)
            or set(preflight_reports_by_horizon) != {"D1", "W1"}
            or not isinstance(github_issue_comment_snapshots, (list, tuple))
            or len(github_issue_comment_snapshots) > MAX_COMMENT_ROWS):
        return result
    if now >= _nominal_windows("D1")[0][0]:
        result["reason"] = "FIRST_NY17_SESSION_STARTED_CANNOT_PREPARE_NOW"
        return result

    # No source can claim real proof of pre-event publication here; this is
    # a conservative readiness classification. The GitHub connector may
    # OMIT created_at and updated_at even on genuine comments.
    normalized = []
    for item in github_issue_comment_snapshots:
        if type(item) is not dict:
            result["reason"] = "GITHUB_COMMENT_SNAPSHOT_INVALID"
            return result
        body = item.get("body")
        if not isinstance(body, str) or len(body) > MAX_BODY_CHARS:
            result["reason"] = "COMMENT_BODY_INVALID_OR_OVERSIZED"
            return result
        normalized.append(item)

    details = {}
    for horizon in ("D1", "W1"):
        start, end = _nominal_windows(horizon)[0]
        report = preflight_reports_by_horizon[horizon]
        if (type(report) is not dict
                or report.get("schema") != PREFLIGHT_SCHEMA
                or report.get("state") != PREFLIGHT_STATE
                or report.get("horizon") != horizon
                or report.get("window_start_utc") != start.isoformat()
                or report.get("window_end_utc") != end.isoformat()
                or report.get("forecast_claims_received") != 28
                or report.get("explicit_abstentions") != 28
                or report.get("directional_claims_research_only") != 0
                or report.get("macro_metadata_claim_complete_pairs") != 0
                or report.get("macro_local_bytes_complete_pairs") != 0
                or report.get("macro_missing_or_unverifiable_pairs") != 28
                or report.get("all_28_forecasts_locally_reconciled") is not True
                or report.get("original_issuer_bytes_authenticated") is not False
                or report.get("forecast_witnessed_before_session") is not False
                or report.get("trade_authorized") is not False):
            result["reason"] = "NOT_A_28_PAIR_NO_MACRO_ABSTAIN_ONLY_PREFLIGHT"
            return result
        packet = report.get("canonical_forecast_json_unposted")
        body = report.get("anchor_comment_body_unposted")
        digest = report.get("forecast_roster_sha256_unposted")
        if (not _json_canonical(
                    packet, horizon=horizon, start=start, end=end, now=now)
                or not isinstance(digest, str) or SHA64.fullmatch(digest) is None
                or sha256(packet.encode("ascii")).hexdigest() != digest):
            result["reason"] = "CANONICAL_28_ABSTAIN_JSON_OR_DIGEST_INVALID"
            return result
        expected_body = "\n".join((
            WITNESS_HEADER, "campaign_id=" + CAMPAIGN_ID,
            "horizon=" + horizon,
            "start_utc=" + start.isoformat().replace("+00:00", "Z"),
            "end_utc=" + end.isoformat().replace("+00:00", "Z"),
            "pairs=28", "roster_sha256=" + digest,
            "research_only=true", "trade_authorized=false",
        ))
        if body != expected_body:
            result["reason"] = "ABSTAIN_GITHUB_COMMENT_BODY_MISMATCH"
            return result
        comment_matches = [c for c in normalized if c["body"] == expected_body]
        if len(comment_matches) > 1:
            result["reason"] = "DUPLICATE_WITNESS_COMMENTS_REJECTED"
            return result
        status = "PREPARED_UNPOSTED"
        if comment_matches:
            c = comment_matches[0]
            comment_id = c.get("id")
            url = c.get("url")
            if (type(comment_id) is not int or comment_id < 1
                    or url != (f"https://github.com/{REPO}/issues/{ISSUE_NUMBER}"
                               f"#issuecomment-{comment_id}")):
                result["reason"] = "COMMENT_ID_OR_ISSUE_LOCATION_INVALID"
                return result
            result["comment_body_matches_found"] += 1
            created = c.get("created_at")
            updated = c.get("updated_at")
            if created is None or updated is None:
                status = "COMMENT_EXISTS_BUT_SERVER_TIMESTAMPS_UNAVAILABLE"
                result["matching_comments_with_missing_timestamps"] += 1
            else:
                # Even accurate-looking caller fields cannot grant external
                # witness status; would need server-authenticated immutable
                # API fetch and first-seen receipt outside this pure function.
                if not isinstance(created, str) or not isinstance(updated, str):
                    result["reason"] = "COMMENT_TIMESTAMP_FIELDS_INVALID"
                    return result
                try:
                    cc = _utc(datetime.fromisoformat(created.replace("Z", "+00:00")))
                    uu = _utc(datetime.fromisoformat(updated.replace("Z", "+00:00")))
                except ValueError:
                    cc = uu = None
                if cc is None or uu is None or not cc <= uu <= now:
                    result["reason"] = "COMMENT_SERVER_TIMESTAMP_CLAIMS_INCOHERENT"
                    return result
                status = ("COMMENT_FIELDS_CLAIM_PRESTART_UNATTESTED"
                          if uu < start else
                          "COMMENT_LATE_OR_EDITED_NOT_A_PRESTART_WITNESS")
        details[horizon] = {
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "abstention_claims": 28, "directional_claims": 0,
            "macro_sources_provided_for_dry_run": 0,
            "roster_sha256_claim": digest,
            "github_comment_status": status,
            "actual_github_server_timestamp_verified": False,
            "real_pre_event_witness_attested": False,
        }
        result["prepared_dry_run_abstentions"] += 28

    result["horizon_details"] = details
    if result["comment_body_matches_found"] == 0:
        result["state"] = "LAB_FIRST_FX28_ABSTAIN_PREPARED_BUT_NOT_POSTED_NO_GO"
        result["reason"] = "EXACT_56_DRY_RUN_ABSTENTIONS_NO_LIVE_PRE_EVENT_WITNESS"
    else:
        result["state"] = "LAB_FIRST_FX28_ABSTAIN_COMMENT_SNAPSHOT_UNATTESTED_NO_GO"
        result["reason"] = "COMMENT_BODY_OR_TIMESTAMP_CANNOT_PROVE_INDEPENDENT_GITHUB_WITNESS"
    return result


__all__ = ("SCHEMA", "inspect_first_fx28_pre_event_abstain_readiness_lab")
