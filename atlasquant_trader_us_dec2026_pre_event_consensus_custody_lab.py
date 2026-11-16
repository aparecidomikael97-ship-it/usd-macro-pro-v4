"""Prospective December-2026 CPI/PPI consensus SOURCE custody, offline LAB.

Unlike retrospective September/October economic research, these scheduled
December releases are still in the future at branch creation. This gate
provides a fixed denominator and refuses to backdate HTML observations.
Source bytes and hashes are inspected ONLY once their captured-at CLAIM
would have been visible at a point-in-time research cutoff.

Important separation:
  1) Locally replayed source snapshots are not source FIRST-SEEN attestation.
  2) A hash-verified calendar page is not a parsed consensus or forecast.
  3) Neither consensus, actual, trading direction nor P&L is ever output.
  4) Future CPI/PPI event-specific semantic parsers must be created and
     separately audited before *any* numeric analyst consensus is admitted.

This is a PURE function. No HTTP, disks, GitHub, paid API, MT5, scheduler,
alerts, trading, broker session or FX28 campaign mutation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
import re
from typing import Any

SCHEMA = "ATLASQUANT_MOTOR_A_US_DEC2026_PROSPECTIVE_CONSENSUS_CUSTODY_LAB_V1"
UTC = timezone.utc
EVENTS = (
    ("US_CPI_NOV2026", "CPI", "2026-11",
     datetime(2026, 12, 10, 13, 30, tzinfo=UTC)),
    ("US_PPI_NOV2026", "PPI", "2026-11",
     datetime(2026, 12, 15, 13, 30, tzinfo=UTC)),
)
SOURCE_NAMES = ("TD_ECONOMICS", "TRADING_ECONOMICS")
_LOOKBACK = timedelta(days=7)
_FREEZE_BEFORE = timedelta(hours=1)
_MAX_HTTP_SECONDS = 180
_MAX_HTTP_DATE_STALE = timedelta(seconds=30)
_MAX_HTTP_DATE_FUTURE = timedelta(seconds=2)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TD_URL = re.compile(
    r"https://economics\.td\.com/domains/economics\.td\.com/documents/"
    r"reports/bottom-line/tables/20\d{2}-\d{2}-\d{2}/upcoming\.htm\Z")
_TE_URL = "https://tradingeconomics.com/united-states/calendar"
_MAX_BYTES = {"TD_ECONOMICS": 256*1024,
              "TRADING_ECONOMICS": 2*1024*1024}


@dataclass(frozen=True)
class OriginalPreEventSourceClaim:
    event_root: str
    provider: str
    source_url: str
    final_url: str
    html_original_bytes: bytes
    original_sha256_claim: str
    http_status: int
    http_content_type: str
    http_date_claim: str
    started_at_utc: datetime
    finished_at_utc: datetime


def _utc(t: Any) -> datetime | None:
    if type(t) is not datetime or t.tzinfo is None:
        return None
    try:
        return t.astimezone(UTC) if t.utcoffset() is not None else None
    except (TypeError, OverflowError, ValueError):
        return None


def _http_date(raw: Any) -> datetime | None:
    if type(raw) is not str or len(raw) > 96:
        return None
    try:
        return _utc(parsedate_to_datetime(raw))
    except (TypeError, IndexError, ValueError, OverflowError):
        return None


def _td_edition_in_capture_window(
    url: Any, *, release: datetime, captured_start: datetime,
) -> bool:
    """Reject stale/future TD weekly vintage even if URL and HTML look valid.

    The date in an archive URL is ONLY a publisher-edition claim; its
    presence is not an independently verified publication timestamp.
    """
    if type(url) is not str or _TD_URL.fullmatch(url) is None:
        return False
    match = re.search(r"/tables/(20\d{2}-\d{2}-\d{2})/upcoming\.htm\Z", url)
    if match is None:
        return False
    try:
        issue = date.fromisoformat(match.group(1))
    except ValueError:
        return False
    return ((release-_LOOKBACK).date() <= issue
            and issue <= captured_start.date()
            and issue <= release.date())


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_DEC2026_PRE_EVENT_SNAPSHOTS_BLOCKED_NO_GO",
        "reason": reason,
        "frozen_upcoming_economic_event_denominator": 2,
        "events": [
            {
                "root_id": root, "kind": kind, "reference_period": period,
                "official_scheduled_release_utc": release.isoformat(),
                "research_freeze_deadline_utc":
                    (release-_FREEZE_BEFORE).isoformat(),
                "snapshot_capture_window_starts_utc":
                    (release-_LOOKBACK).isoformat(),
                "locally_reconciled_source_count": 0,
                "source_provider_names": [],
                "archived_hashes_only": {},
                "locally_reconciled_two_sources": False,
                "source_first_seen_independently_verified": False,
                "numeric_consensus_parsed_from_source": None,
                "consensus_for_fx_prediction_eligible": False,
                "pre_event_forecast_committed": False,
            }
            for root,kind,period,release in EVENTS
        ],
        "locally_sha_reconciled_pre_event_source_documents": 0,
        "event_roots_with_two_local_source_hashes": 0,
        "economically_validated_pre_event_consensus_events": 0,
        "historically_independent_model_forecasts": 0,
        "validated_out_of_sample_trading_trials": 0,
        "scoreable_research_events": 0,
        "posterior_economic_actual_values": None,
        "directional_fx_bias": None,
        "validated_fx_accuracy": None,
        "calibrated_probability": None,
        "publisher_first_seen_and_capture_clock_independently_authenticated": False,
        "consensus_numeric_semantic_parser_approved": False,
        "bls_calendar_rechecked_after_this_snapshot": False,
        "event_schedule_may_change": True,
        "trade_authorized": False,
        "publishable": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "operational_bias": "AGUARDAR",
        "original_672_fx28_campaign_slots_modified": False,
        "http_requests": 0, "file_writes": 0, "mt5_calls": 0,
        "new_cost_brl": 0,
    }


def inspect_us_dec2026_pre_event_consensus_custody_lab(
    *, snapshots: Any, research_cutoff_utc: Any,
) -> dict[str, Any]:
    out = _base("INVALID_CUTOFF_OR_SOURCE_SNAPSHOT_ROSTER")
    now = _utc(research_cutoff_utc)
    if (now is None or type(snapshots) not in (list, tuple)
            or len(snapshots) > 4):
        return out
    event_map = {root: (index,release)
                 for index,(root,_,_,release) in enumerate(EVENTS)}
    seen: set[tuple[str,str]] = set()
    body_digests: set[str] = set()
    checked = 0
    for item in snapshots:
        if type(item) is not OriginalPreEventSourceClaim:
            return _base("SOURCE_SNAPSHOT_TYPE_UNRECOGNIZED")
        key = (item.event_root, item.provider)
        if (item.event_root not in event_map
                or item.provider not in SOURCE_NAMES
                or key in seen):
            return _base("UNEXPECTED_DUPLICATE_OR_FOREIGN_SOURCE_EVENT")
        seen.add(key)
        event_idx,release = event_map[item.event_root]
        start,end = _utc(item.started_at_utc),_utc(item.finished_at_utc)
        if start is None or end is None or start > end:
            return _base("UNTRUSTED_IMPOSSIBLE_LOCAL_CAPTURE_CLOCK")
        # CRITICAL: only inspect the body/hash of an observation that was
        # already captured by the research cutoff. No future HTML parsing.
        if end > now:
            continue
        earliest = release-_LOOKBACK
        latest = release-_FREEZE_BEFORE
        if (start < earliest or end > latest
                or (end-start).total_seconds() > _MAX_HTTP_SECONDS):
            return _base("SOURCE_NOT_CAPTURED_WITHIN_PRE_RELEASE_FREEZE_WINDOW")
        allowed = (
            (_td_edition_in_capture_window(
                item.source_url, release=release, captured_start=start)
             if item.provider == "TD_ECONOMICS"
             else item.source_url == _TE_URL))
        date = _http_date(item.http_date_claim)
        if (not allowed or item.final_url != item.source_url
                or type(item.http_status) is not int
                or item.http_status != 200
                or type(item.http_content_type) is not str
                or item.http_content_type.split(";")[0].strip().lower() != "text/html"
                or date is None
                or not (start-_MAX_HTTP_DATE_STALE <= date
                        <= end+_MAX_HTTP_DATE_FUTURE)
                or date > latest
                or type(item.html_original_bytes) is not bytes
                or not 100 <= len(item.html_original_bytes) <= _MAX_BYTES[item.provider]
                or type(item.original_sha256_claim) is not str
                or _SHA.fullmatch(item.original_sha256_claim) is None
                or sha256(item.html_original_bytes).hexdigest() != item.original_sha256_claim
                or item.original_sha256_claim in body_digests):
            return _base("HTML_PROVIDER_HTTP_DATE_SHA_OR_SOURCE_DUPLICATION_INVALID")
        body_digests.add(item.original_sha256_claim)
        row=out["events"][event_idx]
        row["source_provider_names"].append(item.provider)
        row["archived_hashes_only"][item.provider] = {
            "html_sha256_local_claim": item.original_sha256_claim,
            "html_bytes": len(item.html_original_bytes),
            "last_local_capture_utc_claim": end.isoformat(),
        }
        row["locally_reconciled_source_count"] += 1
        checked += 1
    pairs = 0
    for row in out["events"]:
        row["source_provider_names"].sort()
        if row["source_provider_names"] == sorted(SOURCE_NAMES):
            row["locally_reconciled_two_sources"] = True
            pairs += 1
    out.update({
        "state": "LAB_DEC2026_PRE_EVENT_SOURCE_CUSTODY_ONLY_NO_GO",
        "reason": "LOCAL_SOURCE_HASH_AND_CLOCK_CLAIMS_NOT_NUMERIC_CONSENSUS_OR_FX_FORECAST",
        "locally_sha_reconciled_pre_event_source_documents": checked,
        "event_roots_with_two_local_source_hashes": pairs,
    })
    return out


__all__ = (
    "SCHEMA", "EVENTS", "OriginalPreEventSourceClaim",
    "inspect_us_dec2026_pre_event_consensus_custody_lab",
)
