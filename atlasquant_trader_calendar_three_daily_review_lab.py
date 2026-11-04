"""Three-slot official-calendar change review, from supplied OFFLINE snapshots.

This journal is not a collector, a cryptographic proof of publisher origin,
an alert sender, or a source of FX price direction. It aggregates changes
visible in at most three *claimed* Brasilia daily documentary observations.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_monitoring_cadence_lab import BRT, DAILY_FULL_REFRESH
from atlasquant_trader_g8_context_completeness_3x_lab import SLOTS
from atlasquant_trader_official_change_detection_lab import (
    _utc, _validated_book, detect_official_calendar_changes_lab,
)

SCHEMA = "ATLASQUANT_TRADER_CALENDAR_THREE_DAILY_REVIEW_LAB_V1"
CAPTURE_KEYS = frozenset(("slot", "captured_at_utc", "snapshots"))
MAX_SOURCES_PER_SLOT = 24
MAX_DOCUMENT_AGE = timedelta(hours=48)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "review_queue": [], "pair_cards": [], "planned_slots": [],
        "change_count": 0, "claimed_capture_count": 0,
        "source_authenticity_attested": False,
        "three_daily_updates_verified": False,
        "realtime_calendar_verified": False,
        "notifications_sent": False, "currency_bias": "AGUARDAR",
        "can_feed_live_radar": False, "trade_authorized": False,
        "scheduler_enabled": False, "worker_enabled": False,
        "external_http_requests": 0, "new_cost_brl": 0,
    }


def build_three_daily_calendar_review_lab(
    captures: Any, *, at: datetime,
) -> dict[str, Any]:
    """Build a human-only review queue for calendar changes, never trade bias."""
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timezone-aware evaluation clock required")
    now = at.astimezone(timezone.utc)
    day = now.astimezone(BRT).date()
    if not isinstance(captures, (list, tuple)) or len(captures) > 3:
        return _blocked("MAX_THREE_DOCUMENTARY_REVIEWS_PER_DAY")

    slots: dict[str, tuple[datetime, dict[str, dict]]] = {}
    claimed_source_currency: dict[str, str] = {}
    for capture in captures:
        if not isinstance(capture, Mapping) or set(capture) != CAPTURE_KEYS:
            return _blocked("INVALID_CAPTURE_ENVELOPE")
        slot = capture["slot"]
        stamp = _utc(capture["captured_at_utc"])
        if (not isinstance(slot, str) or slot not in SLOTS or slot in slots
                or stamp is None or stamp > now
                or stamp.astimezone(BRT).date() != day):
            return _blocked("INVALID_DUPLICATE_OR_FUTURE_SLOT")
        raw_snapshots = capture["snapshots"]
        if (not isinstance(raw_snapshots, list)
                or len(raw_snapshots) > MAX_SOURCES_PER_SLOT):
            return _blocked("UNBOUNDED_OR_INVALID_SOURCE_LIST")
        source_books: dict[str, dict] = {}
        for raw in raw_snapshots:
            validation = _validated_book(raw, now)
            if validation is None:
                return _blocked("INVALID_OR_UNATTESTED_OFFICIAL_SNAPSHOT")
            book, _ = validation
            source = book["source_id"]
            observed = _utc(book["observed_at_utc"])
            if (source in source_books or observed is None
                    or observed > stamp or source in claimed_source_currency
                    and claimed_source_currency[source] != book["currency"]):
                return _blocked("DUPLICATE_SOURCE_OR_INVALID_OBSERVATION_TIME")
            claimed_source_currency[source] = book["currency"]
            source_books[source] = book
        slots[slot] = stamp, source_books

    present_in_order = [slots[s][0] for s in SLOTS if s in slots]
    if any(x >= y for x, y in zip(present_in_order, present_in_order[1:])):
        return _blocked("CAPTURES_NOT_IN_CHRONOLOGICAL_ORDER")

    planned = []
    for index, slot in enumerate(SLOTS):
        target = datetime.combine(day, DAILY_FULL_REFRESH[index], tzinfo=BRT)
        supplied = slots[slot][0].astimezone(BRT) if slot in slots else None
        actual_sources = slots[slot][1] if slot in slots else {}
        planned.append({
            "slot": slot, "target_brt": target.isoformat(),
            "claimed_at_brt": supplied.isoformat() if supplied else None,
            "state": ("MISSING_DOCUMENTARY_CAPTURE" if not supplied else
                      "CLAIM_OUTSIDE_TARGET_WINDOW" if
                      supplied < target - timedelta(minutes=30)
                      or supplied > target + timedelta(minutes=90) else
                      "UNATTESTED_DOCUMENTARY_CAPTURE"),
            "source_count": len(actual_sources),
            "missing_g8_currencies": [currency for currency in CURRENCIES
                                      if currency not in {item["currency"]
                                                          for item in actual_sources.values()}],
            "independent_run_receipt_verified": False,
        })

    last_by_source: dict[str, tuple[str, dict]] = {}
    reviews = []
    missing_from_partial = []
    aging = []
    comparison_count = 0
    for slot in SLOTS:
        if slot not in slots:
            continue
        stamp, source_books = slots[slot]
        for source_id, book in sorted(source_books.items()):
            observed = _utc(book["observed_at_utc"])
            if observed is None:
                return _blocked("INVALID_SOURCE_OBSERVATION_TIME")
            if stamp - observed > MAX_DOCUMENT_AGE:
                aging.append({"slot": slot, "source_id": source_id,
                              "currency": book["currency"],
                              "claimed_source_older_than_48h": True})
            older = last_by_source.get(source_id)
            if older is not None:
                old_slot, old_book = older
                old_time = _utc(old_book["observed_at_utc"])
                if old_time is None or old_time >= observed:
                    return _blocked("SOURCE_OBSERVATION_NOT_INCREASING")
                diff = detect_official_calendar_changes_lab(old_book, book, at=now)
                if diff.get("state") != "LAB_CHANGE_REVIEW_ONLY":
                    return _blocked("CALENDAR_DIFF_REJECTED")
                comparison_count += 1
                for change in diff["changed_events"]:
                    reviews.append({
                        **change, "source_id": source_id,
                        "previous_slot": old_slot, "detected_in_claimed_slot": slot,
                        "source_original_bytes_verified": False,
                        "calendar_change_time_verified": False,
                        "notification_sent": False,
                    })
                if diff["missing_from_partial_current"]:
                    missing_from_partial.append({
                        "source_id": source_id, "previous_slot": old_slot,
                        "current_slot": slot,
                        "event_ids": list(diff["missing_from_partial_current"]),
                        "disappearance_is_cancellation": False,
                    })
            last_by_source[source_id] = (slot, book)

    reviews.sort(key=lambda item: (
        item["priority"] != "REVISAR_IMEDIATAMENTE",
        SLOTS.index(item["detected_in_claimed_slot"]),
        item["source_id"], item["event_id"],
    ))
    cards = []
    for pair in OFFICIAL_PAIRS:
        related = [change for change in reviews if pair in change["affected_pairs"]]
        cards.append({
            "pair": pair, "documentary_changes_for_review": len(related),
            "immediate_reviews": sum(x["priority"] == "REVISAR_IMEDIATAMENTE"
                                     for x in related),
            "event_ids_requiring_human_review": [x["event_id"] for x in related],
            "D1": "AGUARDAR", "W1": "AGUARDAR", "MN1": "AGUARDAR",
            "event_change_is_not_fx_direction": True, "trade_authorized": False,
        })

    result = _blocked("DOCUMENTARY_CHANGES_REQUIRE_SOURCE_AUTHENTICATION")
    result.update({
        "state": "LAB_THREE_DAILY_CALENDAR_REVIEW_ONLY",
        "date_brt": day.isoformat(), "as_of_utc": now.isoformat(),
        "planned_slots": planned, "claimed_capture_count": len(slots),
        "three_claimed_slots_seen": len(slots) == 3,
        "sources_ever_claimed": sorted(last_by_source),
        "source_comparison_count": comparison_count,
        "review_queue": reviews, "change_count": len(reviews),
        "omissions_not_cancellations": missing_from_partial,
        "aged_claimed_source_observations": aging,
        "pair_cards": cards, "pair_count": len(cards),
        "note": ("Revisoes e horarios fornecidos por terceiros sem autenticacao. "
                 "O desaparecimento de evento em calendario parcial nao "
                 "comprova cancelamento. Sem envio de alerta, atualizacao "
                 "automatica ou vies cambial confirmado."),
    })
    return result


__all__ = ["SCHEMA", "build_three_daily_calendar_review_lab"]
