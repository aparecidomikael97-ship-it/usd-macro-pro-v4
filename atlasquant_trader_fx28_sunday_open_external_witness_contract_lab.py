"""Offline GitHub witness protocol for future FX28 Sunday M15 poll cohorts.

A GitHub-hosted digest may make retrospective rewriting detectable IF an
external party actually observes a matching, unedited comment at the right
time. Caller-supplied GitHub JSON is NEVER independent proof. The comment
contains no OHLC or account details, and neither a SHA digest nor GitHub
created_at authenticates Pepperstone, MT5 first-seen, or market hours.

No GET/POST, no network, MT5, filesystem, scheduler, predictions or orders.
After Nov-Dec frozen campaign only; no retries or retiming of 2026-11-15.
"""
from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse
import json
import re

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_fx28_sunday_open_poll_bracket_contract_lab import (
    LocalM15PollClaim,
    inspect_fx28_sunday_open_two_poll_bracket_lab,
)

SCHEMA = "ATLASQUANT_FX28_SUNDAY_OPEN_EXTERNAL_WITNESS_PROTOCOL_LAB_V1"
HEADER = "ATLASQUANT_FX28_SUNDAY_OPEN_TWO_POLL_METADATA_WITNESS_V1"
REPO = "aparecidomikael97-ship-it/usd-macro-pro-v4"
ISSUE = 1884
HEX = re.compile(r"[a-f0-9]{64}\Z")
ACCEPTED = "LAB_FX28_SUNDAY_OPEN_28_PAIR_TWO_POLL_DOCUMENTARY_ONLY_NO_GO"
COHORTS = ("PRIOR", "LATER")
UTC = timezone.utc


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(UTC)
    except (TypeError, OverflowError, ValueError):
        return None


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SUNDAY_OPEN_WITNESS_BLOCKED_NO_GO",
        "reason": reason,
        "cohort_claims_canonicalized": 0,
        "metadata_digests": {},
        "prepared_comment_bodies": {},
        "comment_metadata_structurally_matched": False,
        "prior_witness_claim_created_before_later_poll": False,
        "matching_hash_cannot_prove_witness_created_then": True,
        "caller_supplied_github_data_not_live_api": True,
        "github_comment_source_independently_authenticated": False,
        "external_first_seen_witness_independently_verified": False,
        "pepperstone_broker_authenticated": False,
        "market_open_time_authenticated": False,
        "mt5_poll_times_independently_verified": False,
        "original_672_campaign_slots_modified": False,
        "original_20261115_m15_retried": False,
        "raw_prices_published": False,
        "calibrated_probability": None,
        "validated_accuracy": None,
        "trade_authorized": False,
        "publishable": False,
        "scheduler_enabled": False,
        "operational_bias": "AGUARDAR",
        "http_requests": 0,
        "mt5_calls": 0,
        "file_writes": 0,
    }


def _canonical_cohort(rows: Any, phase: str, nominal: datetime) -> tuple[str, str] | None:
    if (phase not in COHORTS or not isinstance(rows, (tuple, list))
            or len(rows) != 28 or len(OFFICIAL_PAIRS) != 28):
        return None
    seen = {}
    for row in rows:
        if not isinstance(row, LocalM15PollClaim) or row.pair not in OFFICIAL_PAIRS:
            return None
        if row.pair in seen:
            return None
        encoded = {}
        for field in fields(LocalM15PollClaim):
            v = getattr(row, field.name)
            if isinstance(v, datetime):
                c = _utc(v)
                if c is None:
                    return None
                encoded[field.name] = _stamp(c)
            elif type(v) in (str, bool) or v is None:
                encoded[field.name] = v
            else:
                return None
        seen[row.pair] = encoded
    if set(seen) != set(OFFICIAL_PAIRS):
        return None
    raw = json.dumps({
        "schema": SCHEMA, "cohort": phase,
        "nominal_start_utc": _stamp(nominal),
        "records": [seen[pair] for pair in sorted(seen)],
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    digest = sha256(raw).hexdigest()
    body = "\n".join((
        HEADER,
        "nominal_start_utc=" + _stamp(nominal),
        "cohort=" + phase,
        "pair_count=28",
        "metadata_sha256=" + digest,
        "raw_prices_disclosed=false",
        "research_only=true",
        "trade_authorized=false",
    ))
    return digest, body


def inspect_fx28_sunday_open_external_witness_lab(
    *, research_sunday_start_utc: Any, prior_cohort: Any,
    later_cohort: Any, inspected_at_utc: Any,
    github_prior_comment: Any = None,
    github_later_comment: Any = None,
) -> dict[str, Any]:
    """Bind strict metadata to optional caller-supplied GitHub-shaped fields.

    Even if both comment records match, the result is documentary only:
    no actual HTTPS query, signature, trusted first-observed source, or
    authenticated external clock exists in this function.
    """
    out = _base("INVALID_OR_UNVERIFIED_TWO_POLL_RESEARCH")
    nominal = _utc(research_sunday_start_utc)
    now = _utc(inspected_at_utc)
    if nominal is None or now is None:
        return out
    audit = inspect_fx28_sunday_open_two_poll_bracket_lab(
        research_sunday_start_utc=nominal, prior_cohort=prior_cohort,
        later_cohort=later_cohort, inspected_at_utc=now)
    if (audit.get("state") != ACCEPTED
            or audit.get("mt5_calls") != 0 or audit.get("trade_authorized") is not False):
        return out
    before = _canonical_cohort(prior_cohort, "PRIOR", nominal)
    after = _canonical_cohort(later_cohort, "LATER", nominal)
    if before is None or after is None:
        out["reason"] = "UNCANONICAL_28_PAIR_METADATA_COHORT"
        return out
    out.update({
        "cohort_claims_canonicalized": 2,
        "metadata_digests": {"PRIOR":before[0], "LATER":after[0]},
        "prepared_comment_bodies": {"PRIOR":before[1], "LATER":after[1]},
        "state": "LAB_FX28_SUNDAY_OPEN_UNPUBLISHED_HASH_ONLY_NO_GO",
        "reason": "LOCAL_DOCUMENTARY_DIGEST_NOT_AN_EXTERNAL_WITNESS",
    })
    if github_prior_comment is None and github_later_comment is None:
        return out
    if type(github_prior_comment) is not dict or type(github_later_comment) is not dict:
        out["state"] = "LAB_FX28_SUNDAY_OPEN_WITNESS_BLOCKED_NO_GO"
        out["reason"] = "BOTH_GITHUB_COMMENT_RECORDS_REQUIRED"
        return out

    receipt_times = []
    ids: set[int] = set()
    for data, body in ((github_prior_comment, before[1]),
                       (github_later_comment, after[1])):
        cid = data.get("id")
        created = _utc(data.get("created_at"))
        updated = _utc(data.get("updated_at"))
        observed = _utc(data.get("locally_observed_at_utc"))
        if (type(cid) is not int or not 1 <= cid <= 10**15 or cid in ids
                or type(data.get("body")) is not str
                or data["body"] != body
                or data.get("url") !=
                    f"https://api.github.com/repos/{REPO}/issues/comments/{cid}"
                or data.get("html_url") !=
                    f"https://github.com/{REPO}/issues/{ISSUE}#issuecomment-{cid}"
                or created is None or updated is None or observed is None
                or not created == updated
                or not nominal < created <= observed <= now):
            out["state"] = "LAB_FX28_SUNDAY_OPEN_WITNESS_BLOCKED_NO_GO"
            out["reason"] = "COMMENT_HASH_ID_URL_OR_TIMESTAMP_CLAIM_MISMATCH"
            return out
        ids.add(cid)
        receipt_times.append((created, observed))

    first_end = max(_utc(r.finished_at_utc) for r in prior_cohort)
    later_start = min(_utc(r.started_at_utc) for r in later_cohort)
    last_end = max(_utc(r.finished_at_utc) for r in later_cohort)
    # Prior proof should have been visible BEFORE the later measurement.
    if not (first_end <= receipt_times[0][0]
            <= receipt_times[0][1] < later_start
            and last_end <= receipt_times[1][0]
            <= receipt_times[1][1]
            and receipt_times[0][0] < receipt_times[1][0]):
        out["state"] = "LAB_FX28_SUNDAY_OPEN_WITNESS_BLOCKED_NO_GO"
        out["reason"] = "GITHUB_WITNESS_CLAIM_NOT_IN_TWO_POLL_TIME_ORDER"
        return out
    out.update({
        "state": "LAB_FX28_SUNDAY_OPEN_TWO_GITHUB_METADATA_BINDINGS_CLAIM_ONLY_NO_GO",
        "reason": "MATCHED_UNTRUSTED_API_FIELDS_NOT_AN_INDEPENDENT_TIMESTAMP_OR_BROKER_ATTESTATION",
        "comment_metadata_structurally_matched": True,
        "prior_witness_claim_created_before_later_poll": True,
    })
    return out


__all__ = ("SCHEMA", "HEADER", "inspect_fx28_sunday_open_external_witness_lab")
