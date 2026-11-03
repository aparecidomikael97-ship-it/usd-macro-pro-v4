"""COPOM 04/11/2026 B3 session-aware WIN/WDO event-study gate.

Prepared BEFORE the decision. B3 circular 050/2026-VNC schedule is
documentary, not a verified market tape or a holiday/exceptions calendar.
Only SYNTHETIC fixture returns can be calculated. This makes the crucial
after-market event separation testable but does not imply any live data,
trade, market prediction, source attestation, Render or worker access.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from hashlib import sha1
import json
import re
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from atlasquant_trader_copom_pre_event_lock_lab import (
    EXPECTED as PRE_EVENT_CONTENT,
    EARLIEST_RELEASE,
)

SCHEMA = "ATLASQUANT_TRADER_COPOM_B3_SESSION_REACTION_LAB_V1"
PENDING = "LAB_COPOM_B3_PRICE_REACTION_PENDING_REAL_QUOTES"
SYNTHETIC = "LAB_COPOM_B3_SYNTHETIC_REACTION_ONLY"
DENIED = "LAB_COPOM_B3_SESSION_REACTION_REFUSED"
PRE_EVENT_COMMIT = "1281f21860211e9b6f784c649396aa56d17ecdf5"
PRE_EVENT_BLOB = "4f6ff11f05b78d6361b2c1e313ce2e394acfff63"
B3_SCHEDULE_SOURCE = (
    "https://www.b3.com.br/data/files/99/B7/82/67/8A631A103BBB511AAC094EA8/"
    "OC%20050-2026-VNC%20NOVOS%20HORARIOS%20DE%20NEGOCIACAO_PT.pdf"
)
TZ_BRT = ZoneInfo("America/Sao_Paulo")
CUT = datetime(2026, 11, 3, 15, tzinfo=timezone.utc)
SESSION_START = datetime(2026, 11, 4, 9, 0, tzinfo=TZ_BRT)
PROPOSED_NEXT_START = datetime(2026, 11, 5, 9, 0, tzinfo=TZ_BRT)
SCHEDULE = {
    "WIN": {"b3_ticker": "FUT WIN", "brasilia_close": "18:25",
            "pre_window_end": datetime(2026, 11, 4, 18, 25, tzinfo=TZ_BRT),
            "next_window_end": datetime(2026, 11, 5, 18, 25, tzinfo=TZ_BRT),
            "synthetic_symbol": "SIM_WIN",
            "synthetic_contract": "SIM_WIN_FAKE_SINGLE_EXPIRY"},
    "WDO": {"b3_ticker": "FUT WDO", "brasilia_close": "18:30",
            "pre_window_end": datetime(2026, 11, 4, 18, 30, tzinfo=TZ_BRT),
            "next_window_end": datetime(2026, 11, 5, 18, 30, tzinfo=TZ_BRT),
            "synthetic_symbol": "SIM_WDO",
            "synthetic_contract": "SIM_WDO_FAKE_SINGLE_EXPIRY"},
}
OBS_FIELDS = frozenset((
    "instrument", "contract_symbol", "fixture_mode", "pre_price_points",
    "post_price_points", "pre_trade_at_utc", "post_trade_at_utc",
    "pre_contract_id", "post_contract_id", "pre_quote_kind", "post_quote_kind",
    "original_b3_quotes_verified", "market_data_use_rights_verified",
))


def _base(status: str, reason: str | None) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": status, "reason": reason,
        "pre_event_commit": PRE_EVENT_COMMIT,
        "pre_event_blob": PRE_EVENT_BLOB,
        "pre_event_original_bytes_matched": False,
        "b3_schedule_source_url": B3_SCHEDULE_SOURCE,
        "release_earliest_at_utc": EARLIEST_RELEASE.isoformat(),
        "announcement_actual_timestamp_verified": False,
        "b3_holiday_and_exception_calendar_verified": False,
        "next_business_session_guaranteed": False,
        "b3_raw_quotes_archived": False,
        "b3_quotes_origins_verified": False,
        "same_real_contract_verified": False,
        "real_contract_maturity_verified": False,
        "pre_quote_is_last_regular_trade_verified": False,
        "post_quote_is_first_regular_trade_verified": False,
        "overnight_external_events_excluded": False,
        "gap_causally_attributable_to_copom": False,
        "real_market_reaction_measured": False,
        "pre_event_directional_forecast_found": False,
        "trade_pnl_measured": False,
        "predictive_accuracy_proven": False,
        "fx_win_wdo_bias": "AGUARDAR",
        "probability_calibrated": None,
        "trading_authorized": False, "can_feed_live_radar": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "render_configuration_changed": False, "paid_provider_approved": False,
        "schedule_rows": [], "price_rows": [],
    }


def _as_utc(value: Any) -> datetime | None:
    if (not isinstance(value, str) or not value.endswith("Z")
            or len(value) > 40):
        return None
    try:
        d = datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, OverflowError):
        return None
    return d.astimezone(timezone.utc)


def _price(value: Any) -> Decimal | None:
    if (not isinstance(value, str)
            or re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,4})?", value) is None):
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if Decimal("0") < number <= Decimal("100000000") else None


def build_copom_b3_session_reaction_lab(
    frozen_json_bytes: Any, *, evaluated_at: datetime,
    synthetic_observations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Plan correct B3 after-close windows, test returns on synthetic inputs.

    WIN regular futures end 18:25 BRT and WDO regular futures end 18:30
    BRT. BCB says announcement from 18:30 BRT. Thus the next opening is a
    *candidate* time, not proof that a real quote was available.
    """
    if (not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError("Evaluation time needs timezone")
    now = evaluated_at.astimezone(timezone.utc)
    if now < CUT:
        return _base(DENIED, "Do not backdate B3 session planning before research")
    if not isinstance(frozen_json_bytes, bytes):
        return _base(DENIED, "Missing pre-event original archived byte stream")
    actual_blob = sha1(
        b"blob " + str(len(frozen_json_bytes)).encode("ascii") + b"\x00"
        + frozen_json_bytes
    ).hexdigest()
    if actual_blob != PRE_EVENT_BLOB:
        return _base(DENIED, "Frozen scenario bytes differ from archived Git blob")
    try:
        checkpoint = json.loads(frozen_json_bytes.decode("utf-8"))
    except (ValueError, UnicodeError):
        return _base(DENIED, "Unreadable original frozen checkpoint")
    if (not isinstance(checkpoint, Mapping)
            or set(checkpoint) != set(PRE_EVENT_CONTENT)
            or any(type(checkpoint[k]) is not type(v) or checkpoint[k] != v
                   for k, v in PRE_EVENT_CONTENT.items())):
        return _base(DENIED, "Pre-event scenario or source no longer matches original")
    result = {
        **_base(PENDING, None), "pre_event_original_bytes_matched": True,
        "reaction_session_date_candidate": "2026-11-05",
        "pre_event_trading_date": "2026-11-04",
        "session_timezone": "America/Sao_Paulo",
        "first_regular_next_session_open_candidate_utc":
            PROPOSED_NEXT_START.astimezone(timezone.utc).isoformat(),
        "prices_source_category_required": "AUTHENTICATED_B3_INSTRUMENT_SPECIFIC_HISTORY",
        "real_quote_eligibility_conditions": [
            "CHECK_B3_CALENDAR_AND_EXCEPTION_SESSIONS",
            "DOCUMENT_SAME_ACTUAL_CONTRACT_MATURITY_PRE_AND_POST",
            "VERIFY_TIMESTAMPED_LAST_REAL_TRADE_BEFORE_CLOSE",
            "VERIFY_TIMESTAMPED_FIRST_REAL_TRADE_AFTER_NEXT_OPEN",
            "VERIFY_RELIABLE_B3_SOURCE_AND_DATA_RIGHTS",
            "CHECK_OVERNIGHT_USD_DI_NEWS_AND_OTHER_CONFOUNDERS",
        ],
        "announcement_after_win_close": True,
        "announcement_at_or_after_wdo_close": True,
        "market_effect_not_observed": True,
        "context_note": (
            "BCB Copom announcement is scheduled no earlier than 18:30 BRT; "
            "WIN regular session ends 18:25 BRT and WDO at 18:30 BRT. "
            "First next-session time is a proposed calendar candidate; "
            "no actual B3 calendar/quotes have been verified."
        ),
    }
    for instrument, info in SCHEDULE.items():
        result["schedule_rows"].append({
            "instrument": instrument, "b3_ticker": info["b3_ticker"],
            "normal_regular_session_end_brt": info["brasilia_close"],
            "pre_event_session_close_utc":
                info["pre_window_end"].astimezone(timezone.utc).isoformat(),
            "next_regular_open_candidate_utc":
                PROPOSED_NEXT_START.astimezone(timezone.utc).isoformat(),
            "next_regular_close_candidate_utc":
                info["next_window_end"].astimezone(timezone.utc).isoformat(),
            "event_released_during_regular_trading": False,
            "first_next_session_liquidity_verified": False,
            "price_reaction_observed": False,
        })
    if synthetic_observations is None:
        return result
    if (now < PROPOSED_NEXT_START.astimezone(timezone.utc)
            or not isinstance(synthetic_observations, (tuple, list))
            or not 1 <= len(synthetic_observations) <= 2):
        return _base(DENIED, "Synthetic reaction cannot be evaluated before next candidate session")
    prices: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in synthetic_observations:
        if not isinstance(entry, Mapping) or set(entry) != OBS_FIELDS:
            return _base(DENIED, "Unknown source fields in synthetic quote fixture")
        instrument = entry["instrument"]
        if type(instrument) is not str or instrument not in SCHEDULE or instrument in seen:
            return _base(DENIED, "Unknown or repeated B3 instrument")
        seen.add(instrument)
        info = SCHEDULE[instrument]
        if (entry["fixture_mode"] != "SYNTHETIC_TEST_ONLY"
                or entry["contract_symbol"] != info["synthetic_symbol"]
                or type(entry["pre_contract_id"]) is not str
                or type(entry["post_contract_id"]) is not str
                or entry["pre_contract_id"] != info["synthetic_contract"]
                or entry["post_contract_id"] != info["synthetic_contract"]
                or entry["pre_quote_kind"] != "SIMULATED_REGULAR_TRADE_TICK"
                or entry["post_quote_kind"] != "SIMULATED_REGULAR_TRADE_TICK"
                or entry["original_b3_quotes_verified"] is not False
                or entry["market_data_use_rights_verified"] is not False):
            return _base(DENIED, "Real source attribution or contract identity is not allowed")
        pre, post = _as_utc(entry["pre_trade_at_utc"]), _as_utc(entry["post_trade_at_utc"])
        old, new = _price(entry["pre_price_points"]), _price(entry["post_price_points"])
        if any(v is None for v in (pre, post, old, new)):
            return _base(DENIED, "Invalid timestamps or price values")
        if not (SESSION_START.astimezone(timezone.utc) <= pre
                < info["pre_window_end"].astimezone(timezone.utc)
                <= EARLIEST_RELEASE):
            return _base(DENIED, "Pre-event quote outside previous regular session")
        if not (PROPOSED_NEXT_START.astimezone(timezone.utc) <= post
                < info["next_window_end"].astimezone(timezone.utc)
                and post <= now):
            return _base(DENIED, "Post-event quote outside proposed next session or from future")
        pct = (new / old - 1) * Decimal("100")
        prices.append({
            "instrument": instrument,
            "contract_symbol": info["synthetic_symbol"],
            "synthetic_contract_identity_pre_post_equal": True,
            "same_actual_b3_contract_proven": False,
            "pre_post_observations_are_settlement_prices": False,
            "pre_time_utc": pre.isoformat(), "post_time_utc": post.isoformat(),
            "pre_price_points_synthetic": str(old),
            "post_price_points_synthetic": str(new),
            "synthetic_percent_change": str(pct.quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_EVEN)),
            "synthetic_price_direction": (
                "ALTA" if pct > 0 else "BAIXA" if pct < 0 else "NEUTRO"),
            "is_real_market_price": False,
            "can_count_for_prediction_accuracy": False,
        })
    return {
        **result, "state": SYNTHETIC,
        "price_rows": prices, "synthetic_observations_count": len(prices),
        "market_effect_not_observed": True,
        "context_note": ("Only arithmetic over self-identified synthetic test "
                         "prices. No real Copom market reaction inferred."),
    }


__all__ = [
    "SCHEMA", "PENDING", "SYNTHETIC", "DENIED", "SCHEDULE",
    "PRE_EVENT_COMMIT", "PRE_EVENT_BLOB",
    "build_copom_b3_session_reaction_lab",
]
