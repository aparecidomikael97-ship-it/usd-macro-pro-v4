"""Read-only GitHub API receipt inspection for the FX28 NY17 prospective campaign.

The campaign has 24 nominal windows (20 D1, four W1), each with 28 slots.
This adapter can GET actual issue comments over HTTPS, never POST/EDIT them.
A GitHub comment hash is not a forecast; independently preserve the matching
canonical forecast JSON before the window to later prove what was predicted.

There is NO directional inference, market data, trade, schedule or output file.
Tests inject JSON pages; therefore a pure parser's success is documentary only.
Even a live HTTPS retrieval does NOT authenticate macro sources, forecasts,
prices, independence, or predictive accuracy. NO-GO always.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)

SCHEMA = "ATLASQUANT_FX28_NY17_GITHUB_RECEIPT_READER_LAB_V1"
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE_NUMBER = 1884
HEADER = "ATLASQUANT_FX28_NY17_WINDOW_PRE_EVENT_COMMITMENT_LAB_V1"
API = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/comments"
MAX_PAGES = 5
PAGE_SIZE = 100
MAX_PAGE_BYTES = 512_000
SHA = re.compile(r"[a-f0-9]{64}\Z")
PUBLICATION_CLAIM = datetime(2026, 11, 12, 18, 21, 59, tzinfo=timezone.utc)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 35:
        return None
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    y = _utc(x)
    return y if y is not None and not y.microsecond else None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_GITHUB_RECEIPT_READER_BLOCKED",
        "reason": reason, "campaign_id": CAMPAIGN_ID,
        "expected_nominal_windows": 24,
        "expected_pair_horizon_slots": 672,
        "received_comment_count": 0, "unrelated_comments": 0,
        "accepted_pre_event_comment_claims": 0,
        "rejected_late_or_edited_comment_claims": 0,
        "future_pair_slots": 0, "due_missing_witness_pair_slots": 0,
        "due_pre_event_comment_claim_pair_slots": 0,
        "future_pre_event_comment_claim_pair_slots": 0,
        "per_horizon": {}, "windows": [],
        "pages_inspected": 0, "observed_at_utc": None,
        "local_comment_fields_checked": False,
        "actual_https_get_completed": False,
        "source_page_sha256_claims": [],
        "external_comment_witness_independently_verified": False,
        "full_forecast_payload_digest_verified": False,
        "original_macro_sources_authenticated": False,
        "pepperstone_price_source_authenticated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "file_writes": 0,
        "new_cost_brl": 0, "http_requests": 0, "research_only": True,
    }


def _anchor(body: str) -> tuple[tuple[str, datetime], str] | None:
    """Parse the exact immutable batch-hash comment schema used by PR #1886."""
    if not isinstance(body, str) or len(body) > 1500:
        return None
    parts = body.split("\n")
    keys = ("campaign_id", "horizon", "start_utc", "end_utc",
            "pairs", "roster_sha256", "research_only", "trade_authorized")
    if len(parts) != len(keys) + 1 or parts[0] != HEADER:
        return None
    fields: dict[str, str] = {}
    for item, key in zip(parts[1:], keys):
        if not item.startswith(key + "="):
            return None
        fields[key] = item[len(key) + 1:]
    if (fields["campaign_id"] != CAMPAIGN_ID
            or fields["horizon"] not in ("D1", "W1")
            or fields["pairs"] != "28"
            or SHA.fullmatch(fields["roster_sha256"]) is None
            or fields["research_only"] != "true"
            or fields["trade_authorized"] != "false"):
        return None
    start, end = _parse_utc(fields["start_utc"]), _parse_utc(fields["end_utc"])
    if (start is None or end is None
            or (start, end) not in _nominal_windows(fields["horizon"])):
        return None
    return (fields["horizon"], start), fields["roster_sha256"]


def inspect_github_campaign_comment_pages_lab(
    *, pages: Any, observed_at_utc: Any,
) -> dict[str, Any]:
    """Examine *caller-provided* GitHub JSON bytes; no auth or market claims.

    A late first observation does NOT retroactively count as a witnessed
    forecast even when a comment's alleged created_at precedes the market.
    """
    out = _base("INVALID_CAPTURE_OR_OBSERVATION_CLOCK")
    observed = _utc(observed_at_utc)
    if (observed is None or observed < PUBLICATION_CLAIM
            or not isinstance(pages, (list, tuple))
            or not 1 <= len(pages) <= MAX_PAGES):
        return out
    registry = {(h, a): b for h in ("D1", "W1")
                for a, b in _nominal_windows(h)}
    if len(registry) != 24:
        out["reason"] = "FROZEN_CALENDAR_MISSING_OR_CHANGED"
        return out
    receipts: dict[tuple[str, datetime], str] = {}
    rejected: set[tuple[str, datetime]] = set()
    ids: set[int] = set()
    unrelated = 0
    total = 0
    page_hashes = []
    for ix, raw in enumerate(pages):
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_PAGE_BYTES:
            out["reason"] = "INVALID_OR_OVERSIZED_GITHUB_RESPONSE_PAGE"
            return out
        try:
            items = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            out["reason"] = "INVALID_GITHUB_JSON_RESPONSE"
            return out
        if not isinstance(items, list) or len(items) > PAGE_SIZE:
            out["reason"] = "INVALID_GITHUB_COMMENT_PAGE_SHAPE"
            return out
        if ix < len(pages) - 1 and len(items) != PAGE_SIZE:
            out["reason"] = "EARLY_PAGE_END_CANNOT_HAVE_FOLLOWING_PAGE"
            return out
        if ix == MAX_PAGES - 1 and len(items) == PAGE_SIZE:
            out["reason"] = "TRUNCATED_PAGINATION_NOT_ALLOWED"
            return out
        page_hashes.append(sha256(raw).hexdigest())
        for item in items:
            total += 1
            if not isinstance(item, dict):
                out["reason"] = "INVALID_GITHUB_COMMENT_ITEM"
                return out
            body = item.get("body")
            if not isinstance(body, str):
                out["reason"] = "GITHUB_COMMENT_WITHOUT_TEXT_BODY"
                return out
            if not body.startswith(HEADER):
                unrelated += 1
                continue
            parsed = _anchor(body)
            if parsed is None:
                out["reason"] = "MALFORMED_OR_NONCANONICAL_FORECAST_ANCHOR"
                return out
            key, digest = parsed
            if key not in registry or key in receipts or key in rejected:
                out["reason"] = "DUPLICATE_OR_UNKNOWN_WINDOW_WITNESS"
                return out
            comment_id = item.get("id")
            created = _parse_utc(item.get("created_at"))
            updated = _parse_utc(item.get("updated_at"))
            if (type(comment_id) is not int or not 1 <= comment_id <= 10**15
                    or comment_id in ids
                    or created is None or updated is None
                    or not PUBLICATION_CLAIM <= created <= observed
                    or item.get("url") != (
                        f"https://api.github.com/repos/{REPO}/issues/comments/{comment_id}")
                    or item.get("html_url") != (
                        f"https://github.com/{REPO}/issues/{ISSUE_NUMBER}#issuecomment-{comment_id}")):
                out["reason"] = "INVALID_GITHUB_COMMENT_ID_URL_OR_TIMESTAMP"
                return out
            ids.add(comment_id)
            # First observed BEFORE target, originally created before target,
            # and unchanged: otherwise this session remains UNWITNESSED.
            if created < key[1] and updated == created and observed < key[1]:
                receipts[key] = digest
            else:
                rejected.add(key)

    if sum(len(p) for p in pages) > MAX_PAGES * MAX_PAGE_BYTES:
        out["reason"] = "EXCESSIVE_GITHUB_RESPONSE_BYTES"
        return out

    windows = []
    missing = due_claim = future = future_claim = 0
    per_horizon: dict[str, dict[str, int]] = {}
    for horizon in ("D1", "W1"):
        counts = {"windows": 0, "future_slots": 0, "due_missing_witness_slots": 0,
                  "due_pre_event_comment_claim_slots": 0}
        for start, end in _nominal_windows(horizon):
            key = (horizon, start)
            due = observed >= start
            eligible = key in receipts
            if due:
                due_claim += 28 * int(eligible)
                missing += 28 * int(not eligible)
                counts["due_missing_witness_slots"] += 28 * int(not eligible)
                counts["due_pre_event_comment_claim_slots"] += 28 * int(eligible)
            else:
                future += 28
                future_claim += 28 * int(eligible)
                counts["future_slots"] += 28
            counts["windows"] += 1
            windows.append({
                "horizon": horizon, "start_utc": start.isoformat(),
                "end_utc": end.isoformat(), "expected_pair_slots": 28,
                "comment_state": (
                    "PRE_EVENT_COMMENT_FIELDS_CLAIM_ONLY" if eligible else
                    "LATE_OR_EDITED_COMMENT_NOT_A_WITNESS" if key in rejected else
                    "NO_WITNESS_COMMENT_YET" if not due else
                    "DUE_MISSING_PRE_EVENT_WITNESS"
                ),
                "claimed_sha256_only": receipts.get(key),
                "full_forecast_payload_authenticated": False,
            })
        per_horizon[horizon] = counts
    if future + missing + due_claim != 672:
        out["reason"] = "CENSUS_ARITHMETIC_FAILED"
        return out
    out.update({
        "state": "LAB_GITHUB_WITNESS_RECEIPTS_DOCUMENTARY_ONLY_NO_GO",
        "reason": "COMMENTS_NOT_FORECASTS_AND_PAGES_NOT_AUTHENTICATED_HERE",
        "received_comment_count": total,
        "unrelated_comments": unrelated,
        "accepted_pre_event_comment_claims": len(receipts),
        "rejected_late_or_edited_comment_claims": len(rejected),
        "future_pair_slots": future, "due_missing_witness_pair_slots": missing,
        "due_pre_event_comment_claim_pair_slots": due_claim,
        "future_pre_event_comment_claim_pair_slots": future_claim,
        "per_horizon": per_horizon, "windows": windows,
        "pages_inspected": len(pages), "observed_at_utc": observed.isoformat(),
        "local_comment_fields_checked": bool(receipts or rejected),
        "source_page_sha256_claims": page_hashes,
    })
    return out


def fetch_github_campaign_receipts_readonly_lab(*, token: Any) -> dict[str, Any]:
    """Live GET only: GitHub Actions can call with read-only GITHUB_TOKEN.

    No supplied URLs, paths, repo or issue numbers. Never sends credentials to
    a non-GitHub host, writes files or creates/changes any GitHub comment.
    """
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        return _base("MISSING_OR_INVALID_GITHUB_READ_TOKEN_NO_HTTP")
    pages: list[bytes] = []
    requests = 0
    for number in range(1, MAX_PAGES + 1):
        url = f"{API}?per_page={PAGE_SIZE}&page={number}"
        request = Request(url, method="GET", headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AtlasQuant-Trader-ReadOnly-LAB",
            "Cache-Control": "no-store",
        })
        requests += 1
        try:
            with urlopen(request, timeout=10) as resp:
                if resp.getcode() != 200:
                    return _base("GITHUB_API_NON_200_RESPONSE")
                content_type = resp.headers.get("Content-Type", "").lower()
                if "json" not in content_type:
                    return _base("GITHUB_API_NOT_JSON")
                raw = resp.read(MAX_PAGE_BYTES + 1)
                server_date = resp.headers.get("Date")
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            return _base("GITHUB_API_READ_FAILED_NO_FALLBACK")
        if len(raw) > MAX_PAGE_BYTES:
            return _base("GITHUB_API_PAGE_TOO_LARGE")
        try:
            server_now = _utc(parsedate_to_datetime(server_date))
            local_now = datetime.now(timezone.utc)
            if (server_now is None or abs((local_now - server_now).total_seconds()) > 180):
                return _base("SERVER_DATE_OR_CLOCK_SKEW_UNVERIFIABLE")
            items = json.loads(raw.decode("utf-8"))
        except (ValueError, TypeError, UnicodeError, OverflowError):
            return _base("GITHUB_API_JSON_OR_TIME_UNREADABLE")
        if not isinstance(items, list) or len(items) > PAGE_SIZE:
            return _base("GITHUB_API_PAGE_NOT_A_COMMENT_LIST")
        pages.append(raw)
        if len(items) < PAGE_SIZE:
            break
    report = inspect_github_campaign_comment_pages_lab(
        pages=pages, observed_at_utc=datetime.now(timezone.utc))
    if report["state"] == "LAB_GITHUB_WITNESS_RECEIPTS_DOCUMENTARY_ONLY_NO_GO":
        # An authorized HTTPS GET is useful evidence of an actual API read.
        # It does not bind this read to a pre-event GitHub Actions log.
        report["actual_https_get_completed"] = True
        report["reason"] = "READ_ONLY_GITHUB_GET_COMPLETED_NO_FORECAST_ATTESTATION"
        report["http_requests"] = requests
    return report


__all__ = (
    "SCHEMA", "HEADER", "API", "inspect_github_campaign_comment_pages_lab",
    "fetch_github_campaign_receipts_readonly_lab",
)
