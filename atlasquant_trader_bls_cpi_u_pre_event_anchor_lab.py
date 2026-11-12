"""CPI-U pre-event GitHub SHA witness proposal and local comment audit (LAB).

A local archive and a caller-supplied GitHub comment can be matched
cryptographically, with chronology checked against a future forecast cutoff.
Nothing here posts comments, talks to GitHub/BLS, authenticates first release,
or establishes when the BLS originally published observations.
A test-injected or caller-copied GitHub record is NEVER an authenticated
GitHub platform receipt. Use the existing read-only API pipeline separately.
All results remain research-only; no FX bias, trading, alerts or scheduler.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import re
from typing import Any
from zipfile import BadZipFile, ZipFile

from atlasquant_trader_bls_cpi_u_official_bytes_readonly_lab import SERIES
from atlasquant_trader_bls_cpi_u_zip_yoy_bridge_lab import (
    inspect_bls_cpi_u_archive_same_bytes_yoy_lab,
)

SCHEMA = "ATLASQUANT_TRADER_BLS_CPI_U_PRE_EVENT_GITHUB_SHA_ANCHOR_LAB_V1"
HEADER = "ATLASQUANT_TRADER_BLS_CPI_U_PRE_EVENT_ARCHIVE_SHA_WITNESS_LAB_V1"
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE = 1853
_MAX_ZIP_BYTES = 1_100_000
_GITHUB_UTC = re.compile(r"20\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\dZ\Z")


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _github_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or _GITHUB_UTC.fullmatch(value) is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_BLS_CPI_U_PRE_EVENT_SHA_WITNESS_BLOCKED",
        "reason": reason,
        "issue_url": f"https://github.com/{REPO}/issues/{ISSUE}",
        "anchor_body_unposted": None,
        "archive_zip_sha256_local": None,
        "original_source_sha256_local": None,
        "manifest_sha256_local": None,
        "claimed_capture_at_utc": None,
        "claim_prepared_at_utc": None,
        "forecast_cutoff_at_utc": None,
        "comment_id_documentary": None,
        "comment_fields_locally_matched_before_cutoff": False,
        "github_api_record_independently_authenticated": False,
        "github_first_observation_independently_attested": False,
        "bls_original_release_authenticated": False,
        "bls_historical_vintage_authenticated": False,
        "cpi_yoy_proven_point_in_time": False,
        "fx28_forecast_authorized": False,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False,
        "live_alert_allowed": False,
        "trade_authorized": False,
        "scheduler_enabled": False,
        "worker_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def prepare_bls_cpi_u_sha_witness_body_lab(
    *, archive_zip: Any, reference_period: Any, prepared_at_utc: Any,
    forecast_cutoff_at_utc: Any,
) -> dict[str, Any]:
    """Create exact text for *possible* future external pre-event posting.

    No posting is performed, even when this returns success. All clocks
    are caller-supplied claims. The archive is revalidated through #1892.
    """
    out = _blocked("INVALID_WITNESS_INPUT_OR_CLOCK")
    prepared = _utc(prepared_at_utc)
    cutoff = _utc(forecast_cutoff_at_utc)
    if (prepared is None or cutoff is None or prepared >= cutoff
            or not isinstance(archive_zip, bytes)
            or not 1 <= len(archive_zip) <= _MAX_ZIP_BYTES):
        return out
    parsed = inspect_bls_cpi_u_archive_same_bytes_yoy_lab(
        archive_zip=archive_zip, reference_period=reference_period,
        decision_at_utc=cutoff)
    if parsed["state"] != "LAB_ARCHIVED_BLS_CPI_U_TWO_LEVEL_YOY_UNATTESTED":
        out["reason"] = "ARCHIVE_OR_SAME_RESPONSE_YOY_NOT_READY_" + parsed["reason"]
        return out
    # The BLS capture clock can include microseconds. GitHub's created_at
    # is second-granular, but custody must retain the full original precision.
    try:
        captured_raw = datetime.fromisoformat(parsed["capture_utc_claim"])
        captured = (captured_raw.astimezone(timezone.utc)
                    if captured_raw.utcoffset() is not None else None)
    except (TypeError, ValueError, OverflowError):
        captured = None
    if captured is None or not captured <= prepared < cutoff:
        out["reason"] = "CAPTURE_PREPARATION_OR_CUTOFF_CHRONOLOGY_INVALID"
        return out
    try:
        with ZipFile(BytesIO(archive_zip), "r") as archive:
            manifest = archive.read("capture_manifest.json")
    except (OSError, ValueError, BadZipFile, KeyError):
        out["reason"] = "ARCHIVE_MANIFEST_UNREADABLE"
        return out
    manifest_sha = sha256(manifest).hexdigest()
    zipped_sha = sha256(archive_zip).hexdigest()
    raw_sha = parsed["original_response_sha256_local"]
    body = "\n".join((
        HEADER,
        f"series={SERIES}",
        f"reference_period={reference_period}",
        f"archive_zip_sha256={zipped_sha}",
        f"original_source_sha256={raw_sha}",
        f"manifest_sha256={manifest_sha}",
        f"claimed_capture_utc={_stamp(captured)}",
        f"prepared_utc={_stamp(prepared)}",
        f"forecast_cutoff_utc={_stamp(cutoff)}",
        "research_only=true",
        "point_in_time_authenticated=false",
        "fx_bias_authorized=false",
    ))
    out.update({
        "state": "LAB_BLS_CPI_U_SHA_WITNESS_TEXT_PREPARED_NOT_POSTED",
        "reason": "TEXT_ONLY_NOT_EXTERNAL_PROOF_OR_OFFICIAL_RELEASE",
        "anchor_body_unposted": body,
        "archive_zip_sha256_local": zipped_sha,
        "original_source_sha256_local": raw_sha,
        "manifest_sha256_local": manifest_sha,
        "claimed_capture_at_utc": _stamp(captured),
        "claim_prepared_at_utc": _stamp(prepared),
        "forecast_cutoff_at_utc": _stamp(cutoff),
    })
    return out


def inspect_bls_cpi_u_github_comment_claim_lab(
    *, archive_zip: Any, reference_period: Any, prepared_at_utc: Any,
    forecast_cutoff_at_utc: Any, github_comment: Any,
    first_observed_at_utc: Any,
) -> dict[str, Any]:
    """Strictly compare a *supplied* GitHub comment to sealed original bytes.

    A matching record is only a local documentary claim, not evidence that
    this function queried the GitHub API. First observation MUST be pre-cutoff.
    """
    out = prepare_bls_cpi_u_sha_witness_body_lab(
        archive_zip=archive_zip, reference_period=reference_period,
        prepared_at_utc=prepared_at_utc,
        forecast_cutoff_at_utc=forecast_cutoff_at_utc)
    if out["state"] != "LAB_BLS_CPI_U_SHA_WITNESS_TEXT_PREPARED_NOT_POSTED":
        return out
    cutoff = _utc(forecast_cutoff_at_utc)
    prepared = _utc(prepared_at_utc)
    observed = _utc(first_observed_at_utc)
    if (observed is None or not prepared <= observed < cutoff
            or not isinstance(github_comment, dict)):
        out["state"] = "LAB_BLS_CPI_U_PRE_EVENT_SHA_WITNESS_BLOCKED"
        out["reason"] = "FIRST_OBSERVATION_MISSING_OR_NOT_PRE_EVENT"
        return out
    cid = github_comment.get("id")
    created = _github_utc(github_comment.get("created_at"))
    updated = _github_utc(github_comment.get("updated_at"))
    if (type(cid) is not int or not 1 <= cid <= 10**15
            or created is None or updated is None
            or not prepared <= created <= observed
            or updated != created
            or github_comment.get("url") !=
                f"https://api.github.com/repos/{REPO}/issues/comments/{cid}"
            or github_comment.get("html_url") !=
                f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}"
            or github_comment.get("body") != out["anchor_body_unposted"]):
        out["state"] = "LAB_BLS_CPI_U_PRE_EVENT_SHA_WITNESS_BLOCKED"
        out["reason"] = "GITHUB_COMMENT_BODY_URL_OR_PRE_EVENT_CHRONOLOGY_MISMATCH"
        return out
    out.update({
        "state": "LAB_BLS_CPI_U_PRE_EVENT_GITHUB_FIELDS_MATCHED_CLAIM_ONLY",
        "reason": "LOCAL_COMMENT_FIELDS_MATCH_NOT_INDEPENDENT_GITHUB_OR_BLS_PROOF",
        "comment_id_documentary": cid,
        "comment_fields_locally_matched_before_cutoff": True,
    })
    return out


__all__ = (
    "SCHEMA", "HEADER", "REPO", "ISSUE",
    "prepare_bls_cpi_u_sha_witness_body_lab",
    "inspect_bls_cpi_u_github_comment_claim_lab",
)
