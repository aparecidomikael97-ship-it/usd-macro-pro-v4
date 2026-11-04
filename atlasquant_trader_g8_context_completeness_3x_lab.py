"""Three-daily documentary completeness for the 8 currencies / 28 FX pairs.

No source fetch, execution, signed receipt, market-price strength or trading.
Even a complete *claimed* set of links cannot prove macro causal direction.
The latest of up to three BRT snapshots is used to expose gaps, not signals.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_monitoring_cadence_lab import BRT, DAILY_FULL_REFRESH
from atlasquant_trader_official_change_detection_lab import _official_url

SCHEMA = "ATLASQUANT_TRADER_G8_CONTEXT_COMPLETENESS_3X_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
DIMENSIONS = (
    "INFLATION", "EMPLOYMENT", "ACTIVITY", "POLICY_RATE_EXPECTATIONS",
    "MICROECONOMICS", "GEOPOLITICS", "OFFICIAL_NEWS",
    "ECONOMIC_CALENDAR", "INDEPENDENT_RELATIVE_FX_STRENGTH",
)
SLOTS = ("PRE_MARKET", "MIDDAY", "CLOSE")
CAPTURE_FIELDS = frozenset((
    "slot", "captured_at_utc", "currency_dimensions",
    "original_source_receipts_attested", "real_data_verified",
    "live_price_verified", "trade_authorized",
))
EVIDENCE_FIELDS = frozenset((
    "status", "source_url", "source_checked_at_utc",
))
MAX_SOURCE_CHECK_AGE = timedelta(hours=48)


def _clock(raw: Any) -> datetime | None:
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


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "currency_contexts": {}, "pair_contexts": [],
        "three_daily_updates_verified": False, "sources_attested": False,
        "real_bias_verified": False, "probability_calibrated": None,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "paid_provider_charged": False, "new_external_requests": 0,
    }


def _validate_capture(raw: Any, now: datetime, day) -> tuple[datetime, dict] | None:
    if not isinstance(raw, Mapping) or set(raw) != CAPTURE_FIELDS:
        return None
    slot = raw["slot"]
    stamp = _clock(raw["captured_at_utc"])
    if (not isinstance(slot, str) or slot not in SLOTS
            or stamp is None or stamp > now
            or stamp.astimezone(BRT).date() != day
            or any(raw[key] is not False for key in (
                "original_source_receipts_attested", "real_data_verified",
                "live_price_verified", "trade_authorized"))):
        return None
    content = raw["currency_dimensions"]
    if not isinstance(content, Mapping) or set(content) != set(CURRENCIES):
        return None
    normalized = {}
    for currency in CURRENCIES:
        dims = content[currency]
        if not isinstance(dims, Mapping) or set(dims) != set(DIMENSIONS):
            return None
        normalized[currency] = {}
        for name in DIMENSIONS:
            item = dims[name]
            if not isinstance(item, Mapping) or set(item) != EVIDENCE_FIELDS:
                return None
            state = item["status"]
            if not isinstance(state, str):
                return None
            if state == "MISSING":
                if (item["source_url"] is not None
                        or item["source_checked_at_utc"] is not None):
                    return None
                normalized[currency][name] = "MISSING"
            elif state == "DOCUMENTARY_ONLY":
                observed = _clock(item["source_checked_at_utc"])
                if (observed is None or observed > stamp
                        or not _official_url(item["source_url"], currency)):
                    return None
                normalized[currency][name] = (
                    "LAST_CHECK_OLDER_THAN_48H"
                    if stamp - observed > MAX_SOURCE_CHECK_AGE
                    else "DOCUMENTARY_NOT_AUTHENTICATED"
                )
            else:
                return None
    return stamp, normalized


def audit_three_daily_g8_context_lab(
    captures: Any, *, at: datetime,
) -> dict[str, Any]:
    """Audit claimed evidence completeness, never infer which currency wins."""
    if (not isinstance(at, datetime) or at.tzinfo is None
            or at.utcoffset() is None):
        raise ValueError("Timezone-aware clock required")
    now = at.astimezone(timezone.utc)
    day = now.astimezone(BRT).date()
    if (not isinstance(captures, (list, tuple)) or len(captures) > 3):
        return _blocked("MAX_THREE_DOCUMENTARY_CAPTURES_PER_DAY")
    checked = {}
    for capture in captures:
        validation = _validate_capture(capture, now, day)
        if validation is None:
            return _blocked("INVALID_OR_FORGED_DOCUMENTARY_CAPTURE")
        stamp, snapshot = validation
        slot = capture["slot"]
        if slot in checked:
            return _blocked("DUPLICATE_DAILY_SLOT")
        checked[slot] = (stamp, snapshot)
    supplied_in_slot_order = [checked[slot][0] for slot in SLOTS if slot in checked]
    if any(a >= b for a, b in zip(supplied_in_slot_order,
                                  supplied_in_slot_order[1:])):
        return _blocked("CAPTURES_NOT_CHRONOLOGICAL")
    slot_info = []
    for index, slot in enumerate(SLOTS):
        scheduled = datetime.combine(day, DAILY_FULL_REFRESH[index], tzinfo=BRT)
        actual = checked[slot][0].astimezone(BRT) if slot in checked else None
        slot_info.append({
            "slot": slot, "scheduled_at_brt": scheduled.isoformat(),
            "observed_claimed_at_brt": actual.isoformat() if actual else None,
            "slot_state": ("NOT_PROVIDED" if actual is None else
                           "CAPTURED_OUTSIDE_TARGET_WINDOW" if
                           actual < scheduled - timedelta(minutes=30)
                           or actual > scheduled + timedelta(minutes=90)
                           else "DOCUMENTARY_CAPTURE_CLAIMED"),
            "independent_run_receipt_verified": False,
        })
    latest = checked[max(checked, key=lambda slot: checked[slot][0])][1] if checked else None
    contexts = {}
    for currency in CURRENCIES:
        dims = (latest[currency] if latest is not None
                else {name: "MISSING" for name in DIMENSIONS})
        missing = [name for name in DIMENSIONS if dims[name] == "MISSING"]
        aged = [name for name in DIMENSIONS if dims[name] == "LAST_CHECK_OLDER_THAN_48H"]
        contexts[currency] = {
            "dimensions": dict(dims), "missing_dimensions": missing,
            "older_than_48h_source_checks": aged,
            "context_complete_and_authentic": False,
            "currency_strength": "AGUARDAR",
            "why_wait": ("Sem fonte original autenticada, consenso/vintage "
                         "verificado, contraprovas e precos independentes OOS."),
        }
    pairs = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        gaps = {base: contexts[base]["missing_dimensions"],
                quote: contexts[quote]["missing_dimensions"]}
        aged = {base: contexts[base]["older_than_48h_source_checks"],
                quote: contexts[quote]["older_than_48h_source_checks"]}
        pairs.append({
            "pair": pair, "base": base, "quote": quote,
            "missing_by_currency": gaps, "older_checks_by_currency": aged,
            "D1": "AGUARDAR", "W1": "AGUARDAR", "MN1": "AGUARDAR",
            "reason_for_strength_difference_confirmed": False,
            "counterevidence_authenticated": False,
            "trade_authorized": False,
        })
    result = _blocked("DOCUMENTARY_COVERAGE_NOT_REAL_STRENGTH")
    result.update({
        "state": "LAB_COVERAGE_EXPLANATION_ONLY",
        "as_of_utc": now.isoformat(), "date_brt": day.isoformat(),
        "planned_slots": slot_info,
        "claimed_capture_slots": [x for x in SLOTS if x in checked],
        "claimed_capture_count": len(checked),
        "claimed_three_captures_seen": len(checked) == 3,
        "currency_contexts": contexts, "pair_contexts": pairs,
        "currency_count": len(contexts), "pair_count": len(pairs),
        "required_dimensions": list(DIMENSIONS),
        "note": ("Documentacao parcial por moeda, sem prova da fonte "
                 "ou execucao de tres coletas, sem vies negociavel. "
                 "Ultima consulta nao equivale a periodo macro atual."),
    })
    return result


__all__ = ["SCHEMA", "SLOTS", "DIMENSIONS", "audit_three_daily_g8_context_lab"]
