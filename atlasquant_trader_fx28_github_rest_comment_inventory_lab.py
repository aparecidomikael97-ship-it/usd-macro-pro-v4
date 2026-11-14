"""Read-only issue #1884 public GitHub REST comment metadata and witness census.

Unlike the connected comment summary (which may omit created_at/updated_at),
the official REST API returns server-reported created_at, updated_at and raw
body for each comment. This module retrieves fixed issue comments via HTTPS
only on an EXPLICIT --read-public-github CLI flag and prints a sanitized,
bounded inventory. It never posts a comment, opens a trade, writes a file,
or claims a model forecast exists.

Important: an API-created timestamp retrieved after a window opened is
NOT independent proof someone actually OBSERVED that witness before the
window. Even a pre-event inventory still needs the canonical 28-pair roster
bytes to verify the displayed commitment digest. Caller-supplied JSON is
not authenticated; only a live HTTP fetch can attest the program actually
attempted an API read, and that alone is not cryptographic first-seen proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    HEADER, CAMPAIGN_PUBLICATION_CLAIM_UTC, REPO, ISSUE_NUMBER,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    CAMPAIGN_ID, CALENDAR_ISSUE, EXPECTED_PAIR_HORIZON_SLOTS,
    _nominal_windows,
)

SCHEMA = "ATLASQUANT_FX28_GITHUB_REST_COMMENT_INVENTORY_LAB_V1"
ENDPOINT = f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}/comments"
PAGE_SIZE = 100
MAX_PAGES = 5
MAX_PAGE_BYTES = 2_000_000
MAX_COMMENT_BODY_CHARS = 100_000
HEX = re.compile(r"[0-9a-f]{64}\Z")
ISO = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")


def _timestamp(value: Any) -> datetime | None:
    if type(value) is not str or ISO.fullmatch(value) is None:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("DUPLICATE_JSON_OBJECT_KEY")
        d[k] = v
    return d


def _reject(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_GITHUB_REST_COMMENT_INVENTORY_BLOCKED_NO_GO",
        "reason": reason,
        "campaign_id": CAMPAIGN_ID,
        "issue_url": CALENDAR_ISSUE,
        "api_endpoint_fixed": ENDPOINT,
        "observed_at_utc_local_claim": None,
        "pages_reconciled": 0,
        "comments_reconciled": 0,
        "exact_witness_headers_found": 0,
        "structural_prewindow_metadata_candidates": 0,
        "rejected_witness_like_comments": 0,
        "late_or_post_window_observed_candidates": 0,
        "candidate_witness_metadata": [],
        "rejected_candidate_reason_codes": {},
        "non_witness_comment_bodies_never_output": True,
        "comment_timestamps_are_rest_api_fields_not_immutable_witness": True,
        "pre_event_observation_is_required_for_a_real_witness": True,
        "canonical_28_pair_roster_bytes_reconciled": False,
        "issue_comments_absent_outside_this_source_proven": False,
        "publisher_and_first_seen_cryptographically_attested": False,
        "independently_authenticated_forecasts": 0,
        "validated_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests_started": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _body_claim(body: str) -> tuple[str, datetime, datetime, str] | None:
    """Validate only the exact 9-line hash-only body, never fabricate roster."""
    lines = body.splitlines()
    if len(lines) != 9 or lines[0] != HEADER:
        return None
    fields = [
        "campaign_id=", "horizon=", "start_utc=", "end_utc=",
        "pairs=", "roster_sha256=", "research_only=", "trade_authorized=",
    ]
    if any(not lines[i+1].startswith(fields[i]) for i in range(8)):
        return None
    pairs = [lines[i+1][len(fields[i]):] for i in range(8)]
    campaign, horizon, start_raw, end_raw, n, digest, research, trade = pairs
    start = _timestamp(start_raw)
    end = _timestamp(end_raw)
    if (campaign != CAMPAIGN_ID or horizon not in ("D1", "W1")
            or start is None or end is None
            or (start, end) not in _nominal_windows(horizon)
            or n != "28" or HEX.fullmatch(digest) is None
            or digest == "0" * 64
            or research != "true" or trade != "false"):
        return None
    return horizon, start, end, digest


def inspect_github_rest_comment_pages_lab(
    *, raw_pages: Any, observed_at_utc: Any,
) -> dict[str, Any]:
    """Pure parser: caller-controlled bytes are NOT API-authenticated."""
    out = _reject("INVALID_PAGES_OR_OBSERVATION_CLOCK")
    now = _utc(observed_at_utc)
    if (now is None or now < CAMPAIGN_PUBLICATION_CLAIM_UTC
            or type(raw_pages) not in (tuple, list)
            or not 1 <= len(raw_pages) <= MAX_PAGES
            or EXPECTED_PAIR_HORIZON_SLOTS != 672):
        return out
    parsed_pages = []
    try:
        for raw in raw_pages:
            if type(raw) is not bytes or not 2 <= len(raw) <= MAX_PAGE_BYTES:
                raise ValueError("PAGE_BYTES_MISSING_OR_TOO_LARGE")
            page = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_dupes,
                              parse_constant=lambda _: (_ for _ in ()).throw(
                                  ValueError("JSON_CONSTANT_DISALLOWED")))
            if type(page) is not list or len(page) > PAGE_SIZE:
                raise ValueError("PAGINATION_SHAPE_OR_PAGE_SIZE_INVALID")
            parsed_pages.append(page)
    except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError):
        out["reason"] = "MALFORMED_OR_UNBOUNDED_GITHUB_REST_COMMENT_JSON"
        return out

    if (any(len(p) != PAGE_SIZE for p in parsed_pages[:-1])
            or len(parsed_pages[-1]) == PAGE_SIZE):
        out["reason"] = "INCOMPLETE_OR_EXCESS_GITHUB_COMMENT_PAGINATION"
        return out

    seen: set[int] = set()
    last_id = 0
    candidates = []
    reject_counts: dict[str, int] = {}
    headers = 0
    potential = 0
    late = 0
    for page in parsed_pages:
        for comment in page:
            if type(comment) is not dict:
                out["reason"] = "GITHUB_COMMENT_METADATA_MALFORMED"
                return out
            comment_id = comment.get("id")
            body = comment.get("body")
            created = _timestamp(comment.get("created_at"))
            updated = _timestamp(comment.get("updated_at"))
            if (type(comment_id) is not int or comment_id <= last_id
                    or comment_id in seen or type(body) is not str
                    or len(body) > MAX_COMMENT_BODY_CHARS
                    or created is None or updated is None
                    or not CAMPAIGN_PUBLICATION_CLAIM_UTC <= created <= updated <= now
                    or comment.get("url") != (
                        f"https://api.github.com/repos/{REPO}/issues/comments/{comment_id}")
                    or comment.get("html_url") != (
                        f"https://github.com/{REPO}/issues/{ISSUE_NUMBER}"
                        f"#issuecomment-{comment_id}")
                    or comment.get("issue_url") != (
                        f"https://api.github.com/repos/{REPO}/issues/{ISSUE_NUMBER}")):
                out["reason"] = "GITHUB_COMMENT_METADATA_MALFORMED"
                return out
            last_id = comment_id
            seen.add(comment_id)
            if not body.startswith(HEADER):
                continue
            headers += 1
            claim = _body_claim(body)
            if claim is None:
                reason = "INVALID_EXACT_WITNESS_BODY"
            else:
                horizon, start, end, digest = claim
                if (not start-timedelta(hours=12) <= created < start
                        or updated != created):
                    reason = "COMMENT_CREATED_OUTSIDE_12H_OR_EDITED"
                elif now >= start:
                    # GitHub server's historical timestamp alone does not
                    # establish that THIS BODY was observed before open.
                    reason = "OBSERVED_ONLY_AFTER_WINDOW_START_NOT_PRECOMMIT_PROOF"
                    late += 1
                else:
                    reason = ""
                    potential += 1
                    candidates.append({
                        "comment_id": comment_id,
                        "horizon": horizon,
                        "start_utc": start.isoformat(),
                        "end_utc": end.isoformat(),
                        "created_at_utc_api_claim": created.isoformat(),
                        "updated_at_utc_api_claim": updated.isoformat(),
                        "roster_sha256_unverified_against_forecast_bytes": digest,
                        "comment_body_sha256_local": sha256(
                            body.encode("utf-8")).hexdigest(),
                        "pre_window_api_observation_clock_claim_only": True,
                        "not_independently_verified_forecast": True,
                    })
            if reason:
                reject_counts[reason] = reject_counts.get(reason, 0) + 1

    out.update({
        "state": "LAB_GITHUB_REST_COMMENT_INVENTORY_COMPLETE_METADATA_ONLY_NO_GO",
        "reason": "API_TIMES_AND_BODIES_STRUCTURAL_NOT_FORECAST_OR_FIRST_SEEN_AUTHENTICATION",
        "observed_at_utc_local_claim": now.isoformat(),
        "pages_reconciled": len(parsed_pages),
        "comments_reconciled": len(seen),
        "exact_witness_headers_found": headers,
        "structural_prewindow_metadata_candidates": potential,
        "rejected_witness_like_comments": sum(reject_counts.values()),
        "late_or_post_window_observed_candidates": late,
        "candidate_witness_metadata": candidates,
        "rejected_candidate_reason_codes": reject_counts,
    })
    return out


def collect_public_github_issue_snapshot_once_lab(
    *, inspect_public_github: Any, request_open: Callable[..., Any] = urlopen,
    observed_clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Read only exact public GitHub REST endpoint, once per page, no retry.

    A caller can inject a fake opener in tests. Only the normal CLI uses the
    standard HTTPS stack. No auth token is necessary for a public repository.
    If the repository is private or unavailable, fail closed.
    """
    out = _reject("EXPLICIT_PUBLIC_GITHUB_READ_FLAG_REQUIRED")
    if inspect_public_github is not True:
        return out
    if observed_clock is None:
        observed_clock = lambda: datetime.now(timezone.utc).replace(
            microsecond=0)
    if not callable(request_open) or not callable(observed_clock):
        out["reason"] = "INVALID_HTTP_OR_CLOCK_PROVIDER"
        return out

    raw_pages = []
    try:
        for page_number in range(1, MAX_PAGES+1):
            url = f"{ENDPOINT}?per_page={PAGE_SIZE}&page={page_number}"
            req = Request(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "AtlasQuant-FX28-ReadOnly-Witness-Audit",
                    "X-GitHub-Api-Version": "2026-03-10",
                },
                method="GET",
            )
            out["http_requests_started"] += 1
            with request_open(req, timeout=12) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                final_url = response.geturl()
                raw = response.read(MAX_PAGE_BYTES+1)
            if (type(status) is not int or status != 200
                    or type(content_type) is not str
                    or content_type.split(";")[0].strip().lower()
                       != "application/json"
                    or final_url != url or type(raw) is not bytes
                    or len(raw) > MAX_PAGE_BYTES):
                out["reason"] = "GITHUB_HTTPS_RESPONSE_URL_TYPE_SIZE_OR_STATUS_INVALID"
                return out
            raw_pages.append(raw)
            # Check page size to know whether another one MUST be fetched.
            data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_dupes)
            if type(data) is not list or len(data) > PAGE_SIZE:
                out["reason"] = "GITHUB_RESPONSE_PAGE_SHAPE_INVALID"
                return out
            if len(data) < PAGE_SIZE:
                break
        now = observed_clock()
        checked = inspect_github_rest_comment_pages_lab(
            raw_pages=tuple(raw_pages), observed_at_utc=now)
        checked["http_requests_started"] = out["http_requests_started"]
        return checked
    except (OSError, RuntimeError, ValueError, TypeError, UnicodeError,
            OverflowError, RecursionError):
        out["reason"] = "PUBLIC_GITHUB_HTTPS_FETCH_OR_JSON_FAILED_NO_FALLBACK"
        return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only official GitHub REST comment metadata for FX28")
    parser.add_argument("--read-public-github", action="store_true")
    args = parser.parse_args(argv)
    report = collect_public_github_issue_snapshot_once_lab(
        inspect_public_github=args.read_public_github)
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0 if report["state"] == (
        "LAB_GITHUB_REST_COMMENT_INVENTORY_COMPLETE_METADATA_ONLY_NO_GO"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "SCHEMA", "ENDPOINT", "inspect_github_rest_comment_pages_lab",
    "collect_public_github_issue_snapshot_once_lab", "main",
)
