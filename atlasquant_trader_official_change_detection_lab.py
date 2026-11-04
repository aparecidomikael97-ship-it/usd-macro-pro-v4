"""Pure LAB detection of scheduled-event changes in OFFLINE official snapshots.

Important: caller-supplied snapshots are NOT independent evidence of a live
publisher response, regardless of their HTTPS URL or timestamps. This is the
future monitor's change/alert contract, not a polling, news or trading service.
No network, schedules, writes, alerts, prices or orders are executed here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS

SCHEMA = "ATLASQUANT_TRADER_OFFICIAL_CALENDAR_CHANGE_DETECTION_LAB_V1"
EVENT_FIELDS = frozenset((
    "event_id", "event_kind", "scheduled_at_utc", "status", "source_url",
    "publisher_updated_at_utc", "claimed_document_sha256",
))
SNAPSHOT_FIELDS = frozenset((
    "source_id", "currency", "observed_at_utc", "coverage", "events",
    "original_source_bytes_attested", "live_feed_latency_proven",
))
EVENT_KINDS = frozenset((
    "POLICY_DECISION", "INFLATION", "EMPLOYMENT", "ACTIVITY",
    "FINANCIAL_STABILITY", "GEOPOLITICAL_OFFICIAL_NOTICE",
))
EVENT_STATUSES = frozenset(("SCHEDULED", "RELEASED", "CANCELLED"))
HEX64 = re.compile(r"^[0-9a-f]{64}$")
EVENT_ID = re.compile(r"^[A-Za-z0-9:_-]{4,80}$")
SOURCE_ID = re.compile(r"^[A-Z0-9_]{3,60}$")
OFFICIAL_HOSTS = {
    "USD": frozenset(("www.bls.gov", "www.federalreserve.gov", "www.bea.gov")),
    "EUR": frozenset(("www.ecb.europa.eu", "ec.europa.eu")),
    "GBP": frozenset(("www.bankofengland.co.uk", "www.ons.gov.uk")),
    "JPY": frozenset(("www.boj.or.jp", "www.stat.go.jp")),
    "CHF": frozenset(("www.snb.ch", "www.bfs.admin.ch")),
    "AUD": frozenset(("www.rba.gov.au", "www.abs.gov.au")),
    "CAD": frozenset(("www.bankofcanada.ca", "www.statcan.gc.ca",
                      "www150.statcan.gc.ca")),
    "NZD": frozenset(("www.rbnz.govt.nz", "www.stats.govt.nz")),
}


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    if dt.utcoffset() != timedelta(0):
        return None
    return dt.astimezone(timezone.utc)


def _official_url(value: Any, currency: str) -> bool:
    if not isinstance(value, str) or not 16 <= len(value) <= 800:
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and u.hostname in OFFICIAL_HOSTS[currency]
                and u.username is None and u.password is None
                and u.port in (None, 443) and not u.fragment
                and u.path not in ("", "/")
                and not any(x.isspace() for x in value))
    except ValueError:
        return False


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_REJECTED", "reason": reason,
        "changed_events": [], "missing_from_partial_current": [],
        "affected_pairs": [], "data_current": False,
        "source_authenticity_attested": False, "live_news": False,
        "realtime_delivery_verified": False, "notification_sent": False,
        "directional_forecast": None, "probability_calibrated": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "new_external_requests": 0, "new_cost_brl": 0,
    }


def _validated_book(raw: Any, now: datetime) -> tuple[dict, dict] | None:
    if not isinstance(raw, Mapping) or set(raw) != SNAPSHOT_FIELDS:
        return None
    ccy, sid = raw["currency"], raw["source_id"]
    if (not isinstance(ccy, str) or ccy not in CURRENCIES
            or not isinstance(sid, str) or SOURCE_ID.fullmatch(sid) is None
            or raw["coverage"] != "PARTIAL_OFFICIAL_MONITOR"
            or raw["original_source_bytes_attested"] is not False
            or raw["live_feed_latency_proven"] is not False):
        return None
    observed = _utc(raw["observed_at_utc"])
    if observed is None or observed > now:
        return None
    events = raw["events"]
    if not isinstance(events, list) or len(events) > 100:
        return None
    indexed = {}
    for ev in events:
        if not isinstance(ev, Mapping) or set(ev) != EVENT_FIELDS:
            return None
        eid = ev["event_id"]
        if (not isinstance(eid, str) or not EVENT_ID.fullmatch(eid)
                or eid in indexed
                or not isinstance(ev["event_kind"], str)
                or ev["event_kind"] not in EVENT_KINDS
                or not isinstance(ev["status"], str)
                or ev["status"] not in EVENT_STATUSES
                or not _official_url(ev["source_url"], ccy)
                or not isinstance(ev["claimed_document_sha256"], str)
                or HEX64.fullmatch(ev["claimed_document_sha256"]) is None):
            return None
        scheduled = _utc(ev["scheduled_at_utc"])
        published = _utc(ev["publisher_updated_at_utc"])
        if scheduled is None or published is None or published > observed:
            return None
        indexed[eid] = ev
    return dict(raw), indexed


def detect_official_calendar_changes_lab(
    previous: Any, current: Any, *, at: datetime,
) -> dict[str, Any]:
    """Detect *claimed* event revisions; do not infer cancellation from absence.

    The inputs represent two externally collected official-source snapshots;
    this function cannot prove they were actually collected or their latency.
    """
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Evaluation requires timezone-aware clock")
    now = at.astimezone(timezone.utc)
    old = _validated_book(previous, now)
    new = _validated_book(current, now)
    if old is None or new is None:
        return _refuse("INVALID_UNATTESTED_SNAPSHOT_STRUCTURE")
    past, past_by_id = old
    latest, latest_by_id = new
    if (past["source_id"] != latest["source_id"]
            or past["currency"] != latest["currency"]):
        return _refuse("SOURCE_ID_OR_CURRENCY_CHANGED")
    first = _utc(past["observed_at_utc"])
    last = _utc(latest["observed_at_utc"])
    if first is None or last is None or first >= last:
        return _refuse("SNAPSHOT_CLOCK_NOT_STRICTLY_INCREASING")
    age = int((now - last).total_seconds())
    ccy = latest["currency"]
    pairs = [pair for pair in OFFICIAL_PAIRS if ccy in pair.split("/")]
    changes = []
    for eid, newer in sorted(latest_by_id.items()):
        older = past_by_id.get(eid)
        fields = (["ADDED"] if older is None else
                  [name for name, field in (
                      ("DATE_RESCHEDULED", "scheduled_at_utc"),
                      ("STATUS_CHANGED", "status"),
                      ("DOCUMENT_REVISED", "claimed_document_sha256"),
                      ("PUBLISHER_TIMESTAMP_CHANGED", "publisher_updated_at_utc"),
                  ) if older[field] != newer[field]])
        if older is not None and (older["event_kind"] != newer["event_kind"]
                                 or older["source_url"] != newer["source_url"]):
            fields.append("SOURCE_OR_KIND_CHANGED_REVIEW_REQUIRED")
        if not fields:
            continue
        changes.append({
            "event_id": eid, "currency": ccy, "changed_fields": fields,
            "previous_scheduled_at_utc": older["scheduled_at_utc"] if older else None,
            "latest_scheduled_at_utc": newer["scheduled_at_utc"],
            "latest_status": newer["status"],
            "official_reference_url": newer["source_url"],
            "affected_pairs": pairs,
            "priority": ("REVISAR_IMEDIATAMENTE" if (
                "DATE_RESCHEDULED" in fields
                or newer["event_kind"] in ("POLICY_DECISION", "INFLATION", "EMPLOYMENT")
                or newer["status"] == "CANCELLED") else "REVISAR"),
            "human_confirmation_required": True,
            "no_direction_inferred": True,
        })
    # A partial feed may omit older records for pagination/retention. The
    # absence cannot be converted into cancellation or confirmed release.
    missing = sorted(set(past_by_id) - set(latest_by_id))
    result = _refuse("CLAIMED_SNAPSHOT_DIFF_NOT_PROVEN_LIVE")
    result.update({
        "state": "LAB_CHANGE_REVIEW_ONLY", "source_id": latest["source_id"],
        "currency": ccy, "observed_at_utc": last.isoformat(),
        "observation_age_seconds": age,
        "freshness_state": ("RECENT_OBSERVATION_NOT_PROOF_OF_LIVE_FEED"
                            if age <= 900 else "STALE_OBSERVATION"),
        "changed_events": changes,
        "changed_event_count": len(changes),
        "missing_from_partial_current": missing,
        "affected_pairs": pairs if changes else [],
        "data_current": False,
        "note": ("Mudanca documental exige auditoria de origem/recebimento "
                 "e revisao causal; calendario parcial nao prova cancelamento, "
                 "surpresa economica, direcao ou noticia em tempo real."),
    })
    return result


__all__ = ["SCHEMA", "OFFICIAL_HOSTS", "detect_official_calendar_changes_lab"]
