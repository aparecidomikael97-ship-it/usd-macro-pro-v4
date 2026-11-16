"""Hash-only GitHub time witness for future December CPI/PPI consensus originals.

A private TD/TE original.html and receipt.json are first checked by the
existing STRICT physical replay. Only their SHA-256 and capture time enter
the proposed public GitHub comment. A separate one-GET read-only verifier
can compare that body with GitHub REST server timestamps BEFORE the frozen
one-hour pre-event cutoff. Never upload licensed HTML or receipts.

Critical distinction:
- Locally supplied comment JSON can be FORGED; positive pure tests are MOCKS.
- Live GitHub API created_at / updated_at and an observation made BEFORE
  the freeze are evidence of a hash-only commitment, not an unchangeable
  third-party first-seen, publisher methodology or an actual forecast.
- This module NEVER posts a comment, captures a provider page, computes
  numeric consensus, unlocks signals or authorizes operations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any, Callable
from urllib.request import Request, HTTPRedirectHandler, build_opener
import json
import os
import re

from atlasquant_trader_us_dec2026_consensus_original_one_get_lab import (
    replay_dec2026_one_get_original_lab,
)
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import (
    EVENTS, SOURCE_NAMES,
)

SCHEMA = "ATLASQUANT_DEC2026_CONSENSUS_GITHUB_HASH_WITNESS_LAB_V1"
HEADER = "ATLASQUANT_DEC2026_PRIVATE_SOURCE_HASH_ONLY_PRE_EVENT_LAB_V1"
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE_NUMBER = 2005
UTC = timezone.utc
HEX = re.compile(r"[0-9a-f]{64}\Z")
ISO_GITHUB = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
SOURCE_END_ISO = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}\+00:00\Z")
EVENT_MAP = {root: release for root, _, _, release in EVENTS}
API_ROOT = f"https://api.github.com/repos/{REPO}"
WITNESS_LINE_NAMES = (
    "event_root", "provider", "source_html_sha256",
    "source_receipt_sha256", "source_capture_finished_utc",
    "official_release_utc", "freeze_deadline_utc",
    "research_only", "trade_authorized",
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _utc(value: Any) -> datetime | None:
    if type(value) is not datetime or value.tzinfo is None:
        return None
    try:
        return value.astimezone(UTC) if value.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def _utc_source(raw: Any) -> datetime | None:
    if type(raw) is not str or SOURCE_END_ISO.fullmatch(raw) is None:
        return None
    try:
        result = datetime.fromisoformat(raw)
        return result if result.tzinfo == UTC else None
    except (ValueError, TypeError, OverflowError):
        return None


def _utc_github(raw: Any) -> datetime | None:
    if type(raw) is not str or ISO_GITHUB.fullmatch(raw) is None:
        return None
    try:
        result = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        return result if result.strftime("%Y-%m-%dT%H:%M:%SZ") == raw else None
    except (ValueError, TypeError, OverflowError):
        return None


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_GITHUB_JSON_KEY")
        out[key] = value
    return out


def _blocked(reason: str, *, requests: int = 0) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_DEC2026_PRE_EVENT_GITHUB_DIGEST_WITNESS_BLOCKED_HARD_NO_GO",
        "reason": reason,
        "original_and_receipt_local_replay_accepted": False,
        "public_hash_only_body_ready": False,
        "exact_hash_only_github_comment_locally_reconciled": False,
        "github_comment_id": None,
        "github_rest_gets_attempted": requests,
        "github_live_200_pre_freeze_observed": False,
        "github_metadata_only_not_crypto_first_seen": True,
        "publisher_first_seen_independently_authenticated": False,
        "consensus_numeric_semantics_authenticated": False,
        "economic_consensus_eligible_for_fx_prediction": False,
        "registered_forecasts": 0,
        "out_of_sample_accuracy": None,
        "calibrated_probability": None,
        "usd_bias": None,
        "trade_authorized": False,
        "publishable": False,
        "operational_bias": "AGUARDAR",
        "original_fx28_672_slots_modified": False,
        "file_writes": 0,
        "mt5_calls": 0,
        "broker_calls": 0,
        "new_cost_brl": 0,
    }


def prepare_dec2026_source_hash_only_commitment_lab(
    *, archive_root: Any, archive_basename: Any, research_cutoff_utc: Any,
) -> dict[str, Any]:
    """Reopen private bytes in prior physical replay, expose only hash text."""
    out = _blocked("PRIVATE_SOURCE_OR_RECEIPT_NOT_REPLAYED")
    now = _utc(research_cutoff_utc)
    if now is None:
        return out
    proof = replay_dec2026_one_get_original_lab(
        output_root=archive_root, archive_basename=archive_basename,
        research_cutoff_utc=now,
    )
    if (proof.get("state") != "LAB_DEC2026_ONE_GET_ORIGINAL_LOCALLY_REPLAYED_NO_GO"
            or proof.get("original_replayed_from_disk") is not True
            or proof.get("trade_authorized") is not False):
        return out
    root = proof.get("event_root")
    provider = proof.get("provider")
    end_raw = proof.get("local_receipt_finished_utc_claim")
    captured = _utc_source(end_raw)
    html_sha = proof.get("source_original_sha256")
    receipt_sha = proof.get("source_receipt_sha256")
    if (type(root) is not str or root not in EVENT_MAP
            or type(provider) is not str or provider not in SOURCE_NAMES
            or captured is None or captured > now
            or type(html_sha) is not str or HEX.fullmatch(html_sha) is None
            or type(receipt_sha) is not str or HEX.fullmatch(receipt_sha) is None
            or html_sha == receipt_sha):
        return out
    release = EVENT_MAP[root]
    freeze = release - timedelta(hours=1)
    if not release - timedelta(days=7) <= captured < freeze:
        return _blocked("PRIVATE_SOURCE_NOT_WITHIN_PRECOMMITTED_FREEZE_WINDOW")
    vals = (
        root, provider, html_sha, receipt_sha, end_raw,
        release.isoformat(), freeze.isoformat(), "true", "false",
    )
    body = HEADER + "\n" + "\n".join(
        name + "=" + value for name, value in zip(WITNESS_LINE_NAMES, vals)
    )
    if len(body) > 1200 or len(body.splitlines()) != 10:
        return out
    out.update({
        "state": "LAB_DEC2026_HASH_ONLY_BODY_PREPARED_FROM_PRIVATE_BYTES_NO_GO",
        "reason": "LOCAL_SHA256_READY_NOT_POSTED_OR_WITNESSED",
        "original_and_receipt_local_replay_accepted": True,
        "public_hash_only_body_ready": True,
        "proposed_comment_body_hash_only": body,
        "event_root": root, "provider": provider,
        "local_source_capture_finished_utc_claim": end_raw,
        "freeze_deadline_utc": freeze.isoformat(),
        "source_html_sha256": html_sha,
        "source_receipt_sha256": receipt_sha,
    })
    return out


def inspect_dec2026_hash_only_github_response_lab(
    *, archive_root: Any, archive_basename: Any, raw_github_comment_json: Any,
    observed_at_utc: Any, expected_comment_id: Any,
) -> dict[str, Any]:
    """Parser of caller-supplied REST bytes; alone NEVER authenticates REST."""
    out = _blocked("GITHUB_RESPONSE_OR_PRIVATE_SOURCE_NOT_RECONCILED")
    observed = _utc(observed_at_utc)
    if (observed is None or type(expected_comment_id) is not int
            or expected_comment_id < 1 or expected_comment_id >= 2**63
            or type(raw_github_comment_json) is not bytes
            or not 100 <= len(raw_github_comment_json) <= 16_384):
        return out
    proof = prepare_dec2026_source_hash_only_commitment_lab(
        archive_root=archive_root, archive_basename=archive_basename,
        research_cutoff_utc=observed,
    )
    if proof["public_hash_only_body_ready"] is not True:
        out["reason"] = "PRIVATE_PHYSICAL_REPLAY_REJECTED_OR_FUTURE"
        return out
    freeze = datetime.fromisoformat(proof["freeze_deadline_utc"])
    capture = _utc_source(proof["local_source_capture_finished_utc_claim"])
    if capture is None or observed >= freeze:
        out["reason"] = "GITHUB_WITNESS_FIRST_OBSERVED_AFTER_PRE_EVENT_FREEZE"
        return out
    try:
        entry = json.loads(raw_github_comment_json.decode("utf-8", "strict"),
                           object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               ValueError("NONFINITE_JSON_NOT_ALLOWED")))
    except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError):
        out["reason"] = "MALFORMED_OR_DUPLICATE_GITHUB_JSON"
        return out
    url = f"{API_ROOT}/issues/comments/{expected_comment_id}"
    html_url = f"https://github.com/{REPO}/issues/{ISSUE_NUMBER}#issuecomment-{expected_comment_id}"
    created, updated = (_utc_github(entry.get("created_at")),
                        _utc_github(entry.get("updated_at"))) if type(entry) is dict else (None, None)
    # The REST API rounds timestamps to the nearest earlier second.
    # A comment made in the same integer second as a precise source receipt
    # is NOT adequate evidence that the bytes had already been captured.
    safe_comment_earliest = capture.replace(microsecond=0)
    if capture.microsecond:
        safe_comment_earliest += timedelta(seconds=1)
    if (type(entry) is not dict
            or entry.get("id") != expected_comment_id
            or type(entry.get("id")) is not int
            or entry.get("url") != url
            or entry.get("issue_url") != f"{API_ROOT}/issues/{ISSUE_NUMBER}"
            or entry.get("html_url") != html_url
            or type(entry.get("body")) is not str
            or entry["body"] != proof["proposed_comment_body_hash_only"]
            or type(entry.get("user")) is not dict
            or entry["user"].get("login") not in (
                "aparecidomikael97-ship-it", "github-actions[bot]")
            or created is None or updated != created
            or not safe_comment_earliest <= created <= observed
            or created >= freeze):
        out["reason"] = "GITHUB_HASH_BODY_ID_AUTHOR_OR_SERVER_CLOCK_NOT_PRECOMMITTED"
        return out
    out.update({
        "state": "LAB_DEC2026_GITHUB_DIGEST_AND_LOCAL_ORIGINAL_MATCHED_CLAIM_ONLY_NO_GO",
        "reason": "PRE_FREEZE_LOCAL_REST_METADATA_COMPARISON_NOT_SOURCE_FIRST_SEEN",
        "original_and_receipt_local_replay_accepted": True,
        "public_hash_only_body_ready": True,
        "exact_hash_only_github_comment_locally_reconciled": True,
        "github_comment_id": expected_comment_id,
        "github_created_at_utc_api_claim": created.isoformat(),
        "github_observed_at_utc_local_claim": observed.isoformat(),
        "event_root": proof["event_root"],
        "provider": proof["provider"],
        "source_html_sha256": proof["source_html_sha256"],
        "source_receipt_sha256": proof["source_receipt_sha256"],
        "public_commitment_body_sha256": sha256(entry["body"].encode()).hexdigest(),
    })
    return out


def read_once_and_check_dec2026_github_hash_witness_lab(
    *, allow_explicit_read_only_get: Any, expected_comment_id: Any,
    archive_root: Any, archive_basename: Any,
    request_open: Callable[..., Any] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """One optional GET to fixed GitHub comment; no POST, no scheduler."""
    out = _blocked("EXPLICIT_GITHUB_WITNESS_READ_OPT_IN_REQUIRED")
    if allow_explicit_read_only_get is not True:
        return out
    if (type(expected_comment_id) is not int
            or not 1 <= expected_comment_id < 2**63):
        return _blocked("GITHUB_COMMENT_ID_INVALID")
    opener = request_open or build_opener(_NoRedirect()).open
    read_clock = clock or (lambda: datetime.now(UTC))
    if not callable(opener) or not callable(read_clock):
        return _blocked("INVALID_GITHUB_REQUEST_OR_CLOCK")
    start = _utc(read_clock())
    if start is None:
        return _blocked("INVALID_GITHUB_READ_START_UTC")
    proof = prepare_dec2026_source_hash_only_commitment_lab(
        archive_root=archive_root, archive_basename=archive_basename,
        research_cutoff_utc=start,
    )
    if proof["public_hash_only_body_ready"] is not True:
        return _blocked("PRIVATE_ORIGINAL_NOT_REPLAYED_BEFORE_GITHUB_GET")
    freeze = datetime.fromisoformat(proof["freeze_deadline_utc"])
    if start >= freeze:
        return _blocked("GITHUB_READ_STARTS_AFTER_FROZEN_PRE_EVENT_CUTOFF")
    api = f"{API_ROOT}/issues/comments/{expected_comment_id}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AtlasQuantTrader-LAB-DecConsensusHashOnlyReader",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        if len(token) > 2048 or "\r" in token or "\n" in token:
            return _blocked("INVALID_GITHUB_TOKEN_NO_GET")
        headers["Authorization"] = "Bearer " + token
    request = Request(api, headers=headers, method="GET")
    out["github_rest_gets_attempted"] = 1
    try:
        with opener(request, timeout=12) as resp:
            status, final_url = resp.status, resp.geturl()
            mime = resp.headers.get("Content-Type", "")
            http_date = resp.headers.get("Date", "")
            raw = resp.read(16_385)
        end = _utc(read_clock())
        try:
            api_date = _utc(parsedate_to_datetime(http_date))
        except (ValueError, TypeError, IndexError, OverflowError):
            api_date = None
        if (end is None or end < start or end >= freeze
                or (end - start).total_seconds() > 120
                or status != 200 or type(status) is not int
                or final_url != api or type(mime) is not str
                or mime.split(";")[0].strip().lower() != "application/json"
                or api_date is None
                or not start - timedelta(minutes=2) <= api_date
                <= end + timedelta(seconds=5)
                or type(raw) is not bytes or not 100 <= len(raw) <= 16_384):
            return _blocked("GITHUB_HTTP_DATE_STATUS_URL_OR_FREEZE_INVALID", requests=1)
        result = inspect_dec2026_hash_only_github_response_lab(
            archive_root=archive_root, archive_basename=archive_basename,
            raw_github_comment_json=raw, observed_at_utc=end,
            expected_comment_id=expected_comment_id,
        )
        result["github_rest_gets_attempted"] = 1
        if result["exact_hash_only_github_comment_locally_reconciled"]:
            result["github_live_200_pre_freeze_observed"] = True
            result["reason"] = (
                "LIVE_GITHUB_REST_BODY_OBSERVED_BEFORE_FREEZE_NO_INDEPENDENT_FIRST_SEEN"
            )
        return result
    except (OSError, ValueError, TypeError, RuntimeError, UnicodeError,
            OverflowError):
        return _blocked("GITHUB_HTTPS_ONE_READ_FAILED_NO_RETRY", requests=1)


__all__ = (
    "SCHEMA", "HEADER", "REPO", "ISSUE_NUMBER",
    "prepare_dec2026_source_hash_only_commitment_lab",
    "inspect_dec2026_hash_only_github_response_lab",
    "read_once_and_check_dec2026_github_hash_witness_lab",
)
