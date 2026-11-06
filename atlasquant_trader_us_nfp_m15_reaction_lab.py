"""LAB-only claimed M15 *post-NFP* price arithmetic, never a prediction.

Consumes the fixed BLS/Reuters documentary case and a user-supplied MT5
copy_rates_range-shaped export. Both existing validators run first. The
numeric return is a BROKER-CLAIMED first-hour after-event calculation, not
validated reaction, market causality, trade profit, D1/W1 bias or OOS hit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
import json
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_m15_offline_price_window_lab import (
    inspect_fx_m15_event_window_lab,
)
from atlasquant_trader_us_nfp_prepost_pit_lab import (
    inspect_us_nfp_oct2026_prepost_lab,
)

SCHEMA = "ATLASQUANT_TRADER_NFP_M15_FIRST_HOUR_REACTION_ARITHMETIC_LAB_V1"
EVENT_AT = datetime(2026, 11, 6, 13, 30, tzinfo=timezone.utc)
BAR_SECONDS = 900
RESEARCH_REACTION_BPS_CAP = Decimal("1000")  # sanity only, NOT a risk limit
NFP_AFTER = "LAB_POST_RELEASE_SURVEY_GAP_ARITHMETIC_UNATTESTED"
M15_COMPLETE = "LAB_M15_EVENT_WINDOW_STRUCTURALLY_COMPLETE_UNVERIFIED"


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "fixed_event_at_utc": EVENT_AT.isoformat(),
        "pair": None, "usd_side": None,
        "nfp_casebook_sha256": None, "mt5_claimed_export_sha256": None,
        "nfp_documentary_chronology_passed": False,
        "m15_closed_window_structurally_passed": False,
        "pre_event_reference_close_at_utc": None,
        "post_event_first_hour_close_at_utc": None,
        "post_nfp_pair_return_bps_unverified": None,
        "usd_oriented_post_nfp_return_bps_unverified": None,
        "market_source_and_broker_identity_authenticated": False,
        "broker_timestamp_and_price_side_independently_verified": False,
        "historical_price_vintage_independently_verified": False,
        "reuters_consensus_vintage_independently_witnessed": False,
        "reaction_attributable_to_nfp_verified": False,
        "bid_ask_spread_slippage_execution_verified": False,
        "d1_w1_forecast_registered_before_event": False,
        "directional_backtest_accuracy_verified": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "usd_macro_strength": None, "fx_bias": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "can_feed_live_radar": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0,
    }


def inspect_us_nfp_m15_reaction_lab(
    *, nfp_casebook_raw: Any, mt5_m15_raw: Any,
    expected_pair: Any, captured_at_utc: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Report unverified close/close bps 13:30→14:30 UTC, never a signal.

    Broker OHLC `close` is not independently verified bid/ask and the first
    hour after a report is not evidence of predicting the report beforehand.
    """
    out = _blocked("CLOCK_OR_USD_PAIR_INVALID")
    capture, now = _clock(captured_at_utc), _clock(as_of_utc)
    if (capture is None or now is None or capture > now
            or not isinstance(expected_pair, str)
            or expected_pair not in OFFICIAL_PAIRS):
        return out
    base, quote = split_pair(expected_pair)
    if "USD" not in (base, quote):
        return out
    nfp = inspect_us_nfp_oct2026_prepost_lab(nfp_casebook_raw, as_of_utc=now)
    if (nfp["state"] != NFP_AFTER
            or nfp["nfp_result_minus_reuters_survey_persons_unverified"] != "100000"
            or nfp["bls_nfp_result_after_release_document_present"] is not True):
        out["reason"] = "NFP_DOCUMENTARY_RELEASE_NOT_AVAILABLE_OR_CHANGED"
        return out
    window = inspect_fx_m15_event_window_lab(
        mt5_m15_raw, expected_symbol=expected_pair.replace("/", ""),
        captured_at_utc=capture, as_of_utc=now, event_at_utc=EVENT_AT)
    if (window["state"] != M15_COMPLETE
            or window["pre_event_closed_bars"] != 4
            or window["post_event_closed_bars"] != 4
            or window["excluded_event_straddling_bar"] is not False):
        out["reason"] = "BROKER_M15_EXPORTED_WINDOW_INVALID_OR_INCOMPLETE"
        return out
    # Original exact bytes have already passed strict JSON, OHLC and UTC-bar
    # validation; use them again rather than caller-supplied passed reports.
    bars = json.loads(mt5_m15_raw)["bars"]
    by_start = {b["time"]: b for b in bars}
    event_second = int(EVENT_AT.timestamp())
    pre_bar_start = event_second - BAR_SECONDS
    post_final_start = event_second + 3 * BAR_SECONDS
    # This exact event is on an M15 boundary. The baseline is the last
    # *completed* pre-event bar, never the first bar after the announcement.
    pre = Decimal(by_start[pre_bar_start]["close"])
    post = Decimal(by_start[post_final_start]["close"])
    bps = ((post / pre - 1) * 10000).quantize(Decimal("0.01"),
                                             rounding=ROUND_HALF_EVEN)
    if abs(bps) > RESEARCH_REACTION_BPS_CAP:
        out["reason"] = "OUTLIER_CLAIMED_FIRST_HOUR_FX_MOVE_NEEDS_SOURCE_REVIEW"
        return out
    # When USD is the quote, calculate the exact reciprocal-rate return:
    # USD/EUR is 1/(EUR/USD). Merely negating the rounded pair bps is an
    # approximation and can differ even within a one-hour window.
    oriented = (bps if base == "USD" else (
        (pre / post - 1) * 10000).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN))
    out.update({
        "state": "LAB_POST_NFP_M15_CLAIMED_PRICE_ARITHMETIC_ONLY",
        "reason": "BROKER_REPORTED_CLOSES_UNATTESTED_AND_NOT_PREDICTIVE",
        "pair": expected_pair, "usd_side": "BASE" if base == "USD" else "QUOTE",
        "nfp_casebook_sha256": nfp["casebook_sha256"],
        "mt5_claimed_export_sha256": window["raw_sha256"],
        "nfp_documentary_chronology_passed": True,
        "m15_closed_window_structurally_passed": True,
        "pre_event_reference_close_at_utc": EVENT_AT.isoformat(),
        "post_event_first_hour_close_at_utc": datetime.fromtimestamp(
            post_final_start + BAR_SECONDS, timezone.utc).isoformat(),
        "post_nfp_pair_return_bps_unverified": format(bps, ".2f"),
        "usd_oriented_post_nfp_return_bps_unverified": format(oriented, ".2f"),
    })
    return out


__all__ = ["SCHEMA", "EVENT_AT", "inspect_us_nfp_m15_reaction_lab"]
