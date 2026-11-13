"""Read-only public GitHub issue #1884 snapshot audit, strict NO-GO.

Separate a REAL GitHub issue comment whose entire body matches the
predeclared 28-forecast HASH-ONLY syntax from ordinary issue comments that
merely quote the anchor header. Inspect GitHub REST created_at/updated_at,
window clock, owner, canonical URL, duplicate window, and pagination.

A SHA-256-only post does NOT reveal or preserve the 28 canonical forecasts.
Even an unedited pre-event GitHub comment with a correctly shaped hash is a
weak *digest claim*, NEVER an independently authenticated prediction,
model, data point-in-time provenance, broker observation or trade signal.

By default: zero I/O. With explicit CLI --audit-github-public, at most ONE
read-only HTTPS GET to the FIXED public GitHub REST endpoint. No token or
secrets. If paginated/incomplete: BLOCK, never claim no forecasts.
No GitHub writes, forecasts, worker, prices, MT5, trading or paid sources.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPRedirectHandler, Request, build_opener,
)

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    HEADER, CAMPAIGN_PUBLICATION_CLAIM_UTC,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    FROZEN_START_UTC, FROZEN_END_UTC, _nominal_windows,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_GITHUB_PUBLIC_WITNESS_AUDIT_LAB_V1"
OWNER = "aparecidomikael97-ship-it"
REPO = f"{OWNER}/usd-macro-pro-v4"
ISSUE = 1884
API = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments?per_page=100&page=1"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def _as_utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError, TypeError):
        return None


def _github_utc(value: Any) -> datetime | None:
    if type(value) is not str or _TS.fullmatch(value) is None:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
            return None
        return parsed.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def _anchor(body: Any) -> tuple[str, datetime, datetime, str] | None:
    """No quotes, markdown, examples, extra fields, CRs or modified bodies."""
    if (type(body) is not str or len(body) > 1024
            or "\r" in body or "\0" in body):
        return None
    lines = body.split("\n")
    if len(lines) != 9 or lines[0] != HEADER:
        return None
    fields = {}
    for line, key in zip(lines[1:], (
        "campaign_id", "horizon", "start_utc", "end_utc",
        "pairs", "roster_sha256", "research_only", "trade_authorized",
    )):
        prefix = key + "="
        if not line.startswith(prefix) or len(line) <= len(prefix):
            return None
        fields[key] = line[len(prefix):]
    horizon = fields["horizon"]
    start = _github_utc(fields["start_utc"])
    end = _github_utc(fields["end_utc"])
    digest = fields["roster_sha256"]
    if (fields["campaign_id"] != CAMPAIGN_ID
            or horizon not in ("D1", "W1")
            or start is None or end is None
            or (start, end) not in _nominal_windows(horizon)
            or fields["pairs"] != "28"
            or _HEX.fullmatch(digest) is None
            or digest == "0" * 64
            or fields["research_only"] != "true"
            or fields["trade_authorized"] != "false"):
        return None
    return horizon, start, end, digest


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_GITHUB_PUBLIC_WITNESS_AUDIT_BLOCKED",
        "reason": reason,
        "source_issue_url": CALENDAR_ISSUE,
        "source_public_api_url": API,
        "campaign_id": CAMPAIGN_ID,
        "first_nominal_window_start_utc": FROZEN_START_UTC.isoformat(),
        "last_nominal_window_end_utc": FROZEN_END_UTC.isoformat(),
        "observed_at_utc": None,
        "source_snapshot_complete_for_first_100_comments": False,
        "source_comments_scanned": 0,
        "marker_mentioned_in_prose_only_comments": 0,
        "strict_anchor_bodies_observed": 0,
        "rejected_anchor_metadata_or_ambiguous_window": 0,
        "strict_pre_event_hash_only_anchor_claims": 0,
        "unique_nominal_windows_with_hash_only_claim": 0,
        "claimed_pre_event_hash_only_windows": [],
        "nominal_windows_total": 24,
        "expected_pair_horizon_slots": 672,
        "due_nominal_slots": 0,
        "future_nominal_slots": 0,
        "due_slots_without_hash_only_anchor_in_snapshot": 0,
        "due_slots_with_hash_only_claim_in_snapshot": 0,
        "future_slots_with_hash_only_claim_in_snapshot": 0,
        "zero_matching_anchors_is_not_proof_of_no_other_forecasts": True,
        "hash_only_comment_is_not_preserved_canonical_28_forecasts": True,
        "github_server_metadata_is_not_independent_time_witness": True,
        "source_document_sha_was_independently_reproduced": False,
        "forecasts_pre_event_independently_authenticated": False,
        "broker_prices_independently_authenticated": False,
        "macro_vintage_point_in_time_authenticated": False,
        "calibrated_probability": None,
        "validated_accuracy": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_get_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def audit_fx28_public_github_witness_snapshot_lab(
    *, comments: Any, observed_at_utc: Any,
    response_complete: Any,
) -> dict[str, Any]:
    """Audit GitHub-API-shaped input; caller could still forge it.

    A structurally matching hash-only post is a WEAK claim. This function
    never fetches source, preserves original roster, or attests timestamps.
    """
    out = _base("INVALID_SNAPSHOT_CLOCK_OR_INCOMPLETE_API_PAGE")
    now = _as_utc(observed_at_utc)
    if (now is None or now < CAMPAIGN_PUBLICATION_CLAIM_UTC
            or response_complete is not True
            or type(comments) is not list or len(comments) > 100
            or len(OFFICIAL_PAIRS) != 28
            or EXPECTED_PAIR_HORIZON_SLOTS != 672):
        return out
    expected = {
        (horizon, start): end
        for horizon in ("D1", "W1")
        for start, end in _nominal_windows(horizon)
    }
    if len(expected) != 24:
        out["reason"] = "CAMPAIGN_WINDOW_UNIVERSE_INCONSISTENT"
        return out

    # Duplicate anchors to the SAME window are ambiguous, even with two
    # identical digests. Do not select the latest after seeing the price.
    seen_comment_ids: set[int] = set()
    anchors: dict[tuple[str, datetime], int] = {}
    duplicate_windows: set[tuple[str, datetime]] = set()
    marker_prose = strict = rejected = 0
    for comment in comments:
        if type(comment) is not dict:
            out["reason"] = "MALFORMED_GITHUB_COMMENT_SNAPSHOT"
            return out
        cid = comment.get("id")
        body = comment.get("body")
        created = _github_utc(comment.get("created_at"))
        updated = _github_utc(comment.get("updated_at"))
        if (type(cid) is not int or cid < 1 or cid in seen_comment_ids
                or type(body) is not str or len(body) > 100_000
                or created is None or updated is None
                or created > now or updated > now or updated < created):
            out["reason"] = "MALFORMED_GITHUB_COMMENT_SNAPSHOT"
            return out
        seen_comment_ids.add(cid)
        parsed = _anchor(body)
        if parsed is None:
            marker_prose += int(HEADER in body)
            continue
        strict += 1
        horizon, start, end, _digest = parsed
        user = comment.get("user")
        if (type(user) is not dict or user.get("login") != OWNER
                or comment.get("url") != (
                    f"https://api.github.com/repos/{REPO}/issues/comments/{cid}"
                )
                or comment.get("html_url") != (
                    f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}"
                )
                or not CAMPAIGN_PUBLICATION_CLAIM_UTC <= created < start
                or created != updated
                or expected.get((horizon, start)) != end):
            rejected += 1
            continue
        key = (horizon, start)
        if key in anchors:
            duplicate_windows.add(key)
        else:
            anchors[key] = cid

    # All conflicting windows rejected, regardless of which post is first.
    for key in duplicate_windows:
        anchors.pop(key, None)
    rejected += len(duplicate_windows)
    due = {key for key in expected if key[1] <= now}
    future = set(expected) - due
    good_due = set(anchors) & due
    good_future = set(anchors) & future
    out.update({
        "state": "LAB_FX28_GITHUB_PUBLIC_HASH_ONLY_CENSUS_NO_GO",
        "reason": ("NO_STRICT_PRE_EVENT_HASH_ONLY_ANCHORS_IN_SNAPSHOT"
                   if not anchors else "HASH_ONLY_ANCHOR_SHAPE_NOT_FULL_FORECAST_PROOF"),
        "observed_at_utc": now.isoformat(),
        "source_snapshot_complete_for_first_100_comments": True,
        "source_comments_scanned": len(comments),
        "marker_mentioned_in_prose_only_comments": marker_prose,
        "strict_anchor_bodies_observed": strict,
        "rejected_anchor_metadata_or_ambiguous_window": rejected,
        "strict_pre_event_hash_only_anchor_claims": len(anchors),
        "unique_nominal_windows_with_hash_only_claim": len(anchors),
        "claimed_pre_event_hash_only_windows": [
            {"horizon":horizon, "start_utc":start.isoformat(),
             "github_comment_id":anchors[(horizon, start)],
             "canonical_roster_bytes_retrieved":False}
            for horizon, start in sorted(anchors)
        ],
        "due_nominal_slots": len(due) * 28,
        "future_nominal_slots": len(future) * 28,
        "due_slots_without_hash_only_anchor_in_snapshot":
            (len(due) - len(good_due)) * 28,
        "due_slots_with_hash_only_claim_in_snapshot":len(good_due)*28,
        "future_slots_with_hash_only_claim_in_snapshot":len(good_future)*28,
    })
    return out


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch_public_issue_comments_once() -> tuple[list[dict[str, Any]], bool]:
    """Fixed public endpoint, 1 GET max, no secrets/tokens, no pagination."""
    req = Request(API, headers={
        "Accept":"application/vnd.github+json",
        "User-Agent":"AtlasQuantTrader-FX28-PublicWitness-Audit-LAB",
        "X-GitHub-Api-Version":"2022-11-28",
    }, method="GET")
    with build_opener(_NoRedirect()).open(req, timeout=12) as response:
        if response.getcode() != 200:
            raise ValueError("GITHUB_API_NOT_200")
        if not response.geturl().startswith(
                f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments?"):
            raise ValueError("GITHUB_API_REDIRECT_OR_URL_CHANGE")
        content_type = response.headers.get("Content-Type", "")
        if not content_type.startswith(("application/json", "application/vnd.github+json")):
            raise ValueError("GITHUB_API_WRONG_CONTENT_TYPE")
        if 'rel="next"' in response.headers.get("Link", ""):
            raise ValueError("GITHUB_COMMENTS_PAGINATED_INCOMPLETE_SNAPSHOT")
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError("GITHUB_API_RESPONSE_OVERSIZED")
    decoded = json.loads(body)
    if type(decoded) is not list or len(decoded) > 100:
        raise ValueError("GITHUB_API_MALFORMED_LIST")
    return decoded, True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One read-only public GitHub issue witness audit (NO-GO)")
    parser.add_argument("--audit-github-public", action="store_true",
                        help="Opt in to at most one fixed GitHub REST GET")
    args = parser.parse_args(argv)
    if not args.audit_github_public:
        print(json.dumps(_base("EXPLICIT_PUBLIC_GITHUB_AUDIT_FLAG_REQUIRED"),
                         ensure_ascii=False, indent=2))
        return 2
    out = _base("GITHUB_PUBLIC_API_UNAVAILABLE_NO_FALLBACK")
    out["http_get_requests"] = 1  # attempted; no retry or fallback
    try:
        comments, complete = _fetch_public_issue_comments_once()
        result = audit_fx28_public_github_witness_snapshot_lab(
            comments=comments,
            observed_at_utc=datetime.now(timezone.utc).replace(microsecond=0),
            response_complete=complete,
        )
        result["http_get_requests"] = 1
        out = result
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError,
            HTTPError, URLError):
        pass
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    # A successful READ is not permission to trade or a verification GO.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
