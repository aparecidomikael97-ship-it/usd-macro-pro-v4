"""Fail-closed, offline join: claimed forecast receipt -> next MT5 candle body.

This intentionally does not score a 'hit'. Neither the forecast timestamp nor
broker candle-open epochs are independently authenticated. Uses no I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
from numbers import Integral
from typing import Any

from atlasquant_trader_fx_forecast_precommit_lab import (
    ForecastPrecommitClaim, verify_fx_precommit_receipts_lab,
)
from atlasquant_trader_mt5_forward_label_gate_lab import (
    SECONDS, inspect_mt5_forward_label_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_FORECAST_PRICE_JOIN_LAB_V1"


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FORECAST_PRICE_JOIN_BLOCKED",
        "reason": reason, "opportunity_id": None, "pair": None,
        "horizon": None, "side_claim": None,
        "abstain_reason": None, "receipt_head_sha256_claim": None,
        "price_source_hash_self_consistent": False,
        "outcome_price_reference": None,
        "forward_body_move_bps_documentary": None,
        "observed_body_direction_only": None,
        "is_hit": None, "real_accuracy_count_increment": 0,
        "precommit_receipts_locally_match": False,
        "external_receipt_timestamp_authenticated": False,
        "macro_vintages_independently_authenticated": False,
        "mt5_broker_candle_utc_authenticated": False,
        "entry_price_known_at_prediction_time": False,
        "historical_point_in_time_verified": False,
        "costs_spreads_slippage_validated": False,
        "can_feed_validated_backtest": False,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "scheduler_enabled": False,
        "worker_enabled": False, "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0,
    }


def join_fx_forecast_to_next_mt5_bar_lab(
    records: Any, receipt_entries: Any, receipt_head_sha256: Any,
    *, opportunity_id: Any, manifest_record: Any,
    compressed_csv_gz: Any, entry_bar_open_epoch: Any,
    exit_bar_open_epoch: Any, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Associate one *claimed* prior forecast with a future bar open-to-close.

    The precommit window must be exactly the second candle's open-to-nominal
    close; the first candle is used only to establish an adjacent time segment.
    Crucially, its **close** is NOT an entry price known to the forecast.
    """
    out = _base("INVALID_ARGUMENTS_OR_EVALUATION_TIME")
    evaluation = _utc(evaluated_at_utc)
    if not isinstance(opportunity_id, str) or evaluation is None:
        return out
    pre = verify_fx_precommit_receipts_lab(
        records, receipt_entries, receipt_head_sha256,
        evaluated_at_utc=evaluated_at_utc)
    if pre["state"] != "LAB_PRECOMMIT_RECEIPTS_LOCALLY_MATCH_UNATTESTED":
        out["reason"] = "FORECAST_RECEIPTS_NOT_EVEN_LOCALLY_VERIFIED"
        return out
    out["precommit_receipts_locally_match"] = True
    out["receipt_head_sha256_claim"] = pre["head_sha256_claim"]
    matches = [r for r in records if isinstance(r, ForecastPrecommitClaim)
               and r.opportunity_id == opportunity_id]
    if len(matches) != 1:
        out["reason"] = "OPPORTUNITY_ID_NOT_FOUND"
        return out
    row = matches[0]
    out.update({"opportunity_id": opportunity_id, "pair": row.pair,
                "horizon": row.horizon, "side_claim": row.side,
                "abstain_reason": row.abstain_reason})
    if row.horizon not in ("D1", "W1"):
        out["reason"] = "MONTHLY_HORIZON_HAS_NO_ATTESTED_MT5_M1_LABEL"
        return out
    if (not isinstance(entry_bar_open_epoch, Integral)
            or isinstance(entry_bar_open_epoch, bool)
            or not isinstance(exit_bar_open_epoch, Integral)
            or isinstance(exit_bar_open_epoch, bool)):
        out["reason"] = "INVALID_SELECTED_CANDLE_EPOCHS"
        return out
    try:
        selected_exit_start = datetime.fromtimestamp(int(exit_bar_open_epoch), timezone.utc)
        selected_exit_end = datetime.fromtimestamp(
            int(exit_bar_open_epoch) + SECONDS[row.horizon], timezone.utc)
    except (OverflowError, ValueError, OSError):
        out["reason"] = "INVALID_SELECTED_CANDLE_EPOCHS"
        return out
    start = _utc(row.outcome_start_at)
    end = _utc(row.outcome_end_at)
    issued = _utc(row.prediction_issued_at)
    if (not issued < start == selected_exit_start
            or not end == selected_exit_end <= evaluation):
        out["reason"] = "FORECAST_WINDOW_OR_RESOLUTION_TIME_MISMATCH"
        return out
    label = inspect_mt5_forward_label_lab(
        pair=row.pair, timeframe=row.horizon,
        manifest_record=manifest_record, compressed_csv_gz=compressed_csv_gz,
        entry_bar_open_epoch=entry_bar_open_epoch,
        exit_bar_open_epoch=exit_bar_open_epoch)
    if label["state"] != "LAB_MT5_FORWARD_PRICE_LABEL_DOCUMENTARY_UNATTESTED":
        out["reason"] = "MT5_DOCUMENTARY_LABEL_BLOCKED_" + label["reason"]
        return out
    out.update({
        "state": "LAB_FORECAST_AND_FUTURE_BAR_DOCUMENTARY_JOIN_UNATTESTED",
        "reason": "LOCAL_CLAIM_AND_CANDLE_JOIN_ONLY_NO_PROVEN_PRE_EVENT_FORECAST",
        "price_source_hash_self_consistent": label["source_manifest_hash_self_consistent"],
        "outcome_price_reference": "NEXT_CANDLE_OPEN_TO_CLOSE_NOT_TRADE_FILL",
        "forward_body_move_bps_documentary": label["exit_bar_open_to_close_bps_documentary"],
        "observed_body_direction_only": label["observed_exit_bar_body_direction_only"],
    })
    return out


__all__ = ["SCHEMA", "join_fx_forecast_to_next_mt5_bar_lab"]
