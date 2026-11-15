"""Pinned GitHub REST receipt inventory for future Sunday FX28 opening study.

The library has TWO isolated entry points:
- Pure parser over caller-supplied GitHub-shaped raw JSON pages (NOT external proof).
- Explicit, opt-in, read-only public HTTPS GET to a fixed issue endpoint,
  paginated one time per page, without retries, POSTs or writes.

A live REST response gives GitHub-reported metadata *at retrieval*, not
cryptographic publisher identity, independently witnessed first-seen time,
the underlying terminal observation, Pepperstone prices or market opening.
No code here touches the frozen 2026-11-15 capture or its 672 slots.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any, Callable
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from atlasquant_trader_fx28_sunday_open_external_witness_contract_lab import (
    HEADER, REPO, ISSUE, _github_utc,
)
from atlasquant_trader_fx28_sunday_open_research_protocol_lab import (
    FIRST_SEPARATE_SUNDAY,
)

SCHEMA = "ATLASQUANT_FX28_SUNDAY_OPEN_GITHUB_REST_INVENTORY_LAB_V1"
API = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments"
PAGE_SIZE = 100
MAX_PAGES = 5
MAX_PAGE_BYTES = 2_000_000
MAX_COMMENT_BODY = 100_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _dupes(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("DUPLICATE_JSON_OBJECT_KEYS")
        out[key] = value
    return out


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SUNDAY_GITHUB_REST_INVENTORY_BLOCKED_NO_GO",
        "reason": reason,
        "fixed_github_rest_endpoint": API,
        "pages_inspected": 0,
        "comments_inspected": 0,
        "header_exact_matches": 0,
        "prior_metadata_receipt_claims": 0,
        "later_metadata_receipt_claims": 0,
        "matched_pair_counts": 0,
        "completed_two_phase_metadata_sets": 0,
        "candidate_receipt_metadata": [],
        "raw_comment_bodies_exposed": False,
        "raw_ohlc_prices_exposed": False,
        "http_request_attempts": 0,
        "live_https_get_completed": False,
        "response_page_hashes_claim_only": [],
        "snapshot_origin_is_caller_supplied": True,
        "rest_server_created_at_is_not_independent_first_seen": True,
        "github_created_at_unedited_is_not_content_signature": True,
        "github_comments_independently_authenticated": False,
        "github_comment_first_seen_independently_witnessed": False,
        "pepperstone_source_authenticated": False,
        "broker_session_open_verified": False,
        "terminal_poll_time_authenticated": False,
        "prediction_precommit_verified": False,
        "forecast_accuracy_validated": False,
        "validated_accuracy": None,
        "trade_authorized": False,
        "publishable": False,
        "scheduler_enabled": False,
        "original_campaign_672_slots_modified": False,
        "original_20261115_m15_retried": False,
        "mt5_calls": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "operational_bias": "AGUARDAR",
    }


def _parse_receipt(body: str) -> tuple[datetime, str, str] | None:
    """Strict schema prevents extra lines or accidental price disclosure."""
    parts = body.split("\n")
    names = ("nominal_start_utc", "cohort", "pair_count", "metadata_sha256",
             "raw_prices_disclosed", "research_only", "trade_authorized")
    if len(parts) != len(names) + 1 or parts[0] != HEADER:
        return None
    values = []
    for item, name in zip(parts[1:], names):
        prefix = name + "="
        if not item.startswith(prefix):
            return None
        values.append(item[len(prefix):])
    start_raw, cohort, pairs, digest, prices, research, trade = values
    start = _github_utc(start_raw)
    if (start is None or start < FIRST_SEPARATE_SUNDAY
            or start.astimezone(NY).weekday() != 6
            or (start.astimezone(NY).hour,start.astimezone(NY).minute) != (17,0)
            or cohort not in ("PRIOR","LATER") or pairs != "28"
            or HEX64.fullmatch(digest) is None or digest == "0"*64
            or prices != "false" or research != "true" or trade != "false"):
        return None
    return start, cohort, digest


def inspect_sunday_open_github_rest_pages_lab(
    *, raw_pages: Any, observed_at_utc: Any,
) -> dict[str, Any]:
    """Pure parser. Passing arbitrary bytes NEVER authenticates an API read."""
    out = _base("INVALID_GITHUB_REST_PAGES_OR_INSPECTION_CLOCK")
    observed = _utc(observed_at_utc)
    if (observed is None or observed < FIRST_SEPARATE_SUNDAY
            or type(raw_pages) not in (tuple,list)
            or not 1 <= len(raw_pages) <= MAX_PAGES):
        return out
    try:
        pages = []
        for raw in raw_pages:
            if type(raw) is not bytes or not 2 <= len(raw) <= MAX_PAGE_BYTES:
                raise ValueError("GITHUB_PAGE_SIZE_INVALID")
            page = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_dupes,
                              parse_constant=lambda _: (_ for _ in ()).throw(
                                  ValueError("JSON_CONSTANT_DISALLOWED")))
            if type(page) is not list or len(page) > PAGE_SIZE:
                raise ValueError("PAGE_ARRAY_SIZE_INVALID")
            pages.append(page)
    except (UnicodeError, ValueError, RecursionError, TypeError, OverflowError):
        out["reason"] = "INVALID_DUPLICATE_OVERSIZED_OR_UNDECODABLE_GITHUB_PAGES"
        return out
    if any(len(page) != PAGE_SIZE for page in pages[:-1]) or len(pages[-1]) == PAGE_SIZE:
        out["reason"] = "INCOMPLETE_GITHUB_PAGINATION_NO_GO"
        return out

    last_id = 0
    matched = {}
    headers = 0
    comments = 0
    for page in pages:
        for item in page:
            comments += 1
            if type(item) is not dict:
                out["reason"] = "INVALID_GITHUB_COMMENT_ITEM"
                return out
            cid, body = item.get("id"), item.get("body")
            created, updated = _github_utc(item.get("created_at")), _github_utc(item.get("updated_at"))
            if (type(cid) is not int or cid <= last_id
                    or type(body) is not str or len(body) > MAX_COMMENT_BODY
                    or created is None or updated is None
                    or not created <= updated <= observed
                    or item.get("url") != f"https://api.github.com/repos/{REPO}/issues/comments/{cid}"
                    or item.get("html_url") != f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}"
                    or item.get("issue_url") != f"https://api.github.com/repos/{REPO}/issues/{ISSUE}"):
                out["reason"] = "GITHUB_ISSUE_COMMENT_ID_URL_CLOCK_OR_BODY_INVALID"
                return out
            last_id = cid
            if not body.startswith(HEADER):
                continue
            headers += 1
            found = _parse_receipt(body)
            if found is None:
                out["reason"] = "MALFORMED_OR_UNSAFE_SUNDAY_RECEIPT_BODY"
                return out
            nominal, phase, digest = found
            key = (nominal,phase)
            if key in matched:
                out["reason"] = "DUPLICATE_SUNDAY_COHORT_RECEIPT"
                return out
            if (created < nominal or created > nominal + timedelta(hours=5,minutes=15)
                    or created != updated):
                out["reason"] = "COMMENT_OUTSIDE_RESEARCH_WINDOW_OR_EDITED"
                return out
            matched[key] = {
                "nominal_start_utc":nominal.isoformat(),
                "cohort":phase,
                "comment_id":cid,
                "metadata_sha256_claim":digest,
                "rest_created_at_claim":created.isoformat(),
                "rest_updated_at_claim":updated.isoformat(),
                "comment_body_sha256":sha256(body.encode("utf-8")).hexdigest(),
                "independently_attested":False,
            }
    by_nominal: dict[datetime,set[str]] = {}
    for (nominal, phase) in matched:
        by_nominal.setdefault(nominal,set()).add(phase)
    for nominal,phases in by_nominal.items():
        if phases == {"PRIOR","LATER"}:
            prev = next(v for (d,p),v in matched.items() if d == nominal and p == "PRIOR")
            after = next(v for (d,p),v in matched.items() if d == nominal and p == "LATER")
            if prev["rest_created_at_claim"] >= after["rest_created_at_claim"]:
                out["reason"] = "REVERSED_TWO_PHASE_GITHUB_CREATED_CLOCK"
                return out

    out.update({
        "state":"LAB_FX28_SUNDAY_GITHUB_REST_RECEIPTS_METADATA_ONLY_NO_GO",
        "reason":"GITHUB_REST_METADATA_NOT_INDEPENDENT_BROKER_OR_FIRST_SEEN_PROOF",
        "pages_inspected":len(pages),
        "comments_inspected":comments,
        "header_exact_matches":headers,
        "prior_metadata_receipt_claims":sum(p=="PRIOR" for _,p in matched),
        "later_metadata_receipt_claims":sum(p=="LATER" for _,p in matched),
        "matched_pair_counts":sum(phases=={"PRIOR","LATER"} for phases in by_nominal.values()),
        "completed_two_phase_metadata_sets":sum(phases=={"PRIOR","LATER"} for phases in by_nominal.values()),
        "candidate_receipt_metadata":[matched[k] for k in sorted(matched)],
        "response_page_hashes_claim_only":[sha256(raw).hexdigest() for raw in raw_pages],
    })
    return out


def collect_sunday_open_public_github_once_lab(
    *, allow_read_public_github: Any,
    request_open: Callable[..., Any] = urlopen,
    observed_clock: Callable[[],datetime] | None = None,
) -> dict[str, Any]:
    """Read ONLY fixed public GitHub comments GET, explicit opt-in, no retries.

    Successful HTTPS GET is transport evidence for *this retrieval*, not
    cryptographic evidence of past first-seen or original market prices.
    """
    out = _base("EXPLICIT_PUBLIC_READ_AUTHORIZATION_REQUIRED")
    if allow_read_public_github is not True:
        return out
    if observed_clock is None:
        observed_clock = lambda: datetime.now(UTC).replace(microsecond=0)
    if not callable(request_open) or not callable(observed_clock):
        out["reason"] = "INVALID_INJECTED_HTTPS_OR_CLOCK"
        return out
    pages = []
    try:
        for number in range(1,MAX_PAGES+1):
            target = f"{API}?per_page={PAGE_SIZE}&page={number}"
            req = Request(target,headers={
                "Accept":"application/vnd.github+json",
                "User-Agent":"AtlasQuant-FX28-ReadOnly-LAB",
                "X-GitHub-Api-Version":"2022-11-28",
            },method="GET")
            out["http_request_attempts"] += 1
            with request_open(req,timeout=12) as response:
                status = response.status
                typ = response.headers.get("Content-Type","")
                final = response.geturl()
                raw = response.read(MAX_PAGE_BYTES+1)
            if (status != 200 or type(typ) is not str
                    or typ.split(";")[0].strip().lower() != "application/json"
                    or final != target or type(raw) is not bytes
                    or not 2 <= len(raw) <= MAX_PAGE_BYTES):
                out["reason"] = "UNTRUSTED_HTTPS_STATUS_TYPE_URL_OR_SIZE"
                return out
            pages.append(raw)
            parsed = json.loads(raw.decode("utf-8-sig"),object_pairs_hook=_dupes)
            if type(parsed) is not list or len(parsed)>PAGE_SIZE:
                out["reason"]="INVALID_HTTPS_JSON_ARRAY_SIZE"
                return out
            if len(parsed)<PAGE_SIZE:
                break
        checked=inspect_sunday_open_github_rest_pages_lab(
            raw_pages=tuple(pages),observed_at_utc=observed_clock())
        checked["http_request_attempts"] = out["http_request_attempts"]
        checked["live_https_get_completed"] = (
            checked["state"]=="LAB_FX28_SUNDAY_GITHUB_REST_RECEIPTS_METADATA_ONLY_NO_GO")
        checked["snapshot_origin_is_caller_supplied"] = not checked["live_https_get_completed"]
        return checked
    except (OSError,RuntimeError,ValueError,TypeError,UnicodeError,RecursionError,OverflowError):
        out["reason"]="PUBLIC_GITHUB_HTTPS_READ_FAILED_NO_RETRY"
        return out


__all__ = ("SCHEMA","API","HEADER","inspect_sunday_open_github_rest_pages_lab",
           "collect_sunday_open_public_github_once_lab")
