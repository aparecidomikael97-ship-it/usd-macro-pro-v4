"""Verify locally frozen official PPI-day schedule pages, offline LAB only.

Three *partial* primary-source pages were captured on AM12 before release:
EIA natural-gas holiday schedule, Federal Reserve Board Bowman discussion and
San Francisco Fed Daly engagement. BLS page was HTTP-blocked on AM12 and is
NOT pretended archived. The originals are NOT bundled into GitHub.

SHA and textual schedule agreement do not independently authenticate
publication timing, unforeseen events, completeness, or market impact.
No network, MT5, API credentials, orders, alerts, file writes or scheduling.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from typing import Any

from atlasquant_trader_ppi_competing_calendar_lab import (
    CompetingEventClaim, PreEventCalendarClaim, audit_ppi_competing_calendar_lab,
)
from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import (
    BASELINE_OPEN_UTC, EVENT_UTC, LAST_REQUIRED_CLOSE_UTC,
)

SCHEMA = "ATLASQUANT_PPI_THREE_OFFICIAL_SCHEDULE_BYTES_CUSTODY_LAB_V1"
SNAPSHOT_SCHEMA = "ATLASQUANT_US_PPI_OFFICIAL_COMPETING_CALENDAR_CUSTODY_LAB_V1"
PINNED_SOURCES = {
    "EIA_NATGAS_HOLIDAY": {
        "sha": "b54595ec6784c11c95ab448fa21d3f115b03a2bcc02960cab589fb0ad4cc1e04",
        "url": "https://ir.eia.gov/ngs/schedule.html",
        "pattern": r"November 13, 2026.{0,160}Friday.{0,160}10:30 a[.]m[.]",
        "event_id": "US_EIA_NATGAS_STORAGE_20261113",
        "event_utc": datetime(2026, 11, 13, 15, 30, tzinfo=timezone.utc),
        "category": "MACRO_DATA",
    },
    "FED_BOARD_NOVEMBER": {
        "sha": "d5ebbecd6086b2d5a8f3958dc7b02a1903e9c3c69c6a9ad75103483a7bcf9383",
        "url": "https://www.federalreserve.gov/newsevents/2026-November.htm",
        "pattern": r"10:50 a[.]m[.].{0,300}Michelle W[.] Bowman.{0,300}13",
        "event_id": "US_FED_BOWMAN_DISCUSSION_20261113",
        "event_utc": datetime(2026, 11, 13, 15, 50, tzinfo=timezone.utc),
        "category": "POLICY_SPEECH",
    },
    "SF_FED_DALY_UNLV": {
        "sha": "fcb755bc8755d40bc802b77f4d00b9887b5548a87e372801b8f9f16c9d410ecb",
        "url": "https://www.frbsf.org/news-and-media/events/2026/11/conversation-mary-c-daly-unlv-2026-economic-forecast/",
        "pattern": r"Friday, Nov 13, 2026.{0,200}9:00 a[.]m[.] PT",
        "event_id": "US_SF_FED_DALY_UNLV_20261113",
        "event_utc": datetime(2026, 11, 13, 17, 0, tzinfo=timezone.utc),
        "category": "POLICY_SPEECH",
    },
}
MAX_BYTES = 250000
MAX_MANIFEST = 25000


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: Any) -> datetime | None:
    if type(value) is not str:
        return None
    try:
        return _utc(datetime.fromisoformat(value))
    except (ValueError, OverflowError):
        return None


def _no(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_OFFICIAL_CALENDAR_ARCHIVE_BLOCKED",
        "reason": reason, "files_with_pinned_original_sha": 0,
        "primary_source_partial_schedule_count": 0,
        "original_schedule_bytes_on_am12_only": True,
        "bls_schedule_file_not_locally_captured": True,
        "complete_forex_or_geopolitical_calendar_proven": False,
        "independently_attested_publication_clock": False,
        "documentary_schedule_and_event_effect_not_causal": True,
        "competing_window_audit": None,
        "calendar_claim": None,
        "validated_accuracy": None, "directional_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "publishable": False, "live_alert_allowed": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def _original_page_text(raw: bytes) -> str:
    # Minimal text extraction, not a substitute for structured official APIs.
    value = unescape(re.sub(r"<[^>]{0,3000}>", " ", raw.decode("utf-8", "strict")))
    return " ".join(value.split())


def inspect_ppi_three_official_schedule_files_lab(
    *, archive_root: Any, as_of_utc: Any,
) -> dict[str, Any]:
    now = _utc(as_of_utc)
    if now is None or not isinstance(archive_root, (str, Path)):
        return _no("INVALID_ARCHIVE_ROOT_OR_INSPECTION_CLOCK")
    root = Path(archive_root)
    if root.is_symlink() or not root.is_dir():
        return _no("MISSING_OR_UNSAFE_ARCHIVE_DIRECTORY")
    manifest_path = root / "OFFICIAL_SCHEDULE_SOURCE_MANIFEST.json"
    if (manifest_path.is_symlink() or not manifest_path.is_file()
            or manifest_path.stat().st_size > MAX_MANIFEST):
        return _no("ORIGINAL_SCHEDULE_MANIFEST_MISSING_OR_UNSAFE")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (manifest.get("schema") != SNAPSHOT_SCHEMA
                or manifest.get("whole_market_calendar_completeness_verified") is not False
                or manifest.get("local_clock_pre_event_claim_not_third_party_attested") is not True
                or manifest.get("operational_bias") != "AGUARDAR"
                or manifest.get("trade_authorized") is not False
                or manifest.get("publishable") is not False
                or not isinstance(manifest.get("sources"), list)):
            return _no("SNAPSHOT_MANIFEST_SAFETY_OR_SCHEMA_MISMATCH")
        sources = {}
        for item in manifest["sources"]:
            if not isinstance(item, dict) or not isinstance(item.get("source_id"), str):
                return _no("MALFORMED_SNAPSHOT_SOURCE_RECORD")
            if item["source_id"] in sources:
                return _no("DUPLICATED_SOURCE_ID")
            sources[item["source_id"]] = item
        if set(sources) != (set(PINNED_SOURCES) | {"BLS_NOVEMBER"}):
            return _no("EXPECTED_THREE_OFFICIAL_SOURCES_PLUS_BLS_FAILURE")
        bls = sources["BLS_NOVEMBER"]
        if (bls.get("source_bytes_saved_locally") is not False
                or bls.get("sha256_original_bytes") is not None):
            return _no("BLS_CAPTURE_STATUS_CONTRADICTS_SOURCE_MANIFEST")
        captures = []
        events = []
        hashes = []
        for key, info in PINNED_SOURCES.items():
            entry = sources[key]
            filename = root / (key + ".html")
            capture = _stamp(entry.get("captured_at_utc_local_clock_claim"))
            if (entry.get("status") != "ORIGINAL_BYTES_FROZEN_LOCAL_DOCUMENTARY"
                    or entry.get("source_bytes_saved_locally") is not True
                    or entry.get("url") != info["url"]
                    or entry.get("final_url") != info["url"]
                    or entry.get("http_status") != 200
                    or entry.get("raw_file_name") != filename.name
                    or entry.get("sha256_original_bytes") != info["sha"]
                    or capture is None or capture > now or capture >= EVENT_UTC
                    or filename.is_symlink() or not filename.is_file()
                    or filename.stat().st_size > MAX_BYTES):
                return _no("SOURCE_OR_CAPTURE_CLOCK_NOT_MATCHING_PRE_EVENT_MANIFEST")
            raw = filename.read_bytes()
            if len(raw) != entry.get("raw_byte_size") or sha256(raw).hexdigest() != info["sha"]:
                return _no("ORIGINAL_SOURCE_BYTES_DIFFER_FROM_PINNED_SHA256")
            text = _original_page_text(raw)
            if re.search(info["pattern"], text, flags=re.IGNORECASE) is None:
                return _no("ISSUER_SCHEDULE_DATE_TIME_CONTEXT_MISSING")
            captures.append(capture)
            hashes.append(info["sha"])
            events.append(CompetingEventClaim(
                root_id=info["event_id"],
                scheduled_at_utc=info["event_utc"],
                currency_or_global="USD", category=info["category"],
                impact_claim="UNASSESSED",
            ))
        # Composite receipt for the three original SHA values, not a
        # SHA of a global calendar; source coverage is explicitly PARTIAL.
        composite = sha256("|".join(hashes).encode("ascii")).hexdigest()
        partial = PreEventCalendarClaim(
            captured_at_utc=max(captures),
            covered_from_utc=BASELINE_OPEN_UTC,
            covered_until_utc=LAST_REQUIRED_CLOSE_UTC,
            source_sha256_claim=composite,
            claims_complete_for_covered_period=False,
            events=tuple(events),
        )
        calendar = audit_ppi_competing_calendar_lab(
            calendar=partial, as_of_utc=now)
        if (calendar["state"] !=
                "LAB_PPI_PARTIAL_COMPETING_ROOTS_DOCUMENTARY_REVIEW_REQUIRED"
                or calendar["candidate_competing_root_count_documentary"] != 3
                or calendar["candidate_competing_roots_by_reaction_window"]["H4"]
                   != sorted(info["event_id"] for info in PINNED_SOURCES.values())):
            return _no("DOWNSTREAM_PARTIAL_CALENDAR_AUDIT_DISAGREES")
        out = _no("PARTIAL_OFFICIAL_PUBLISHER_SCHEDULES_ARE_NOT_ALL_NEWS")
        out.update({
            "state": "LAB_PPI_THREE_OFFICIAL_SCHEDULES_LOCAL_SHA_MATCH_NO_GO",
            "reason": "THREE_PRE_EVENT_SCHEDULED_CONFOUNDER_CANDIDATES_ONLY",
            "files_with_pinned_original_sha": 3,
            "primary_source_partial_schedule_count": 3,
            "local_receipt_composite_sha256": composite,
            "latest_captured_at_utc_local_clock_claim": max(captures).isoformat(),
            "competing_window_audit": calendar,
            "calendar_claim": partial,
        })
        return out
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, json.JSONDecodeError):
        return _no("SOURCE_MANIFEST_PARSE_OR_IO_FAILURE")


__all__ = ("SCHEMA", "PINNED_SOURCES",
           "inspect_ppi_three_official_schedule_files_lab")
