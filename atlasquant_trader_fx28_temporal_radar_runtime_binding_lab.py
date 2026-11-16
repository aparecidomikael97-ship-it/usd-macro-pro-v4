"""Fail-closed, read-only AM12-local FX28 Sunday M15 -> Radar summary.

For machines with LOCALAPPDATA and a previously sealed fixed local archive,
inspect that archive and ledger via pre-existing pure LAB auditor. No tick,
MetaTrader5, price-level, filenames, paths, account details or historical
pseudo-UTC guess is forwarded to UI. The first-15m archive is NOT an
independent broker timestamp or source. An absent cloud archive is UNKNOWN.

Called only after role access to Trader Radar. Never opens terminals,
schedules work, writes files, changes 672 slots, or authorizes trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atlasquant_trader_fx28_first_m15_672_slot_outcome_quarantine_lab import (
    inspect_first_m15_672_slot_outcome_quarantine_lab,
)

SCHEMA = "ATLASQUANT_FX28_RADAR_LOCAL_TEMPORAL_ARCHIVE_BINDING_LAB_V1"
STATE = "LAB_FX28_LOCAL_FIRST56_QUARANTINED_SOURCE_UNATTESTED_NO_GO"
SOURCE_STATE = "LAB_FX28_FIRST_M15_56_OUTCOMES_QUARANTINED_NO_GO"
SUBPATH = ("AtlasQuant", "LAB", "FX28_NY17_M15")


def inspect_fx28_local_temporal_radar_binding_lab(
    *, local_appdata: Any, inspected_at_utc: Any,
) -> dict[str, Any] | None:
    """Project a minimal UI status, or None when local proof is unavailable.

    None is important: cloud server without AM12 disk is not an 'all clear'.
    """
    if (type(local_appdata) is not str or not local_appdata.strip()
            or not isinstance(inspected_at_utc, datetime)
            or inspected_at_utc.tzinfo is None
            or inspected_at_utc.utcoffset() is None
            or inspected_at_utc.microsecond):
        return None
    try:
        root=Path(local_appdata)
        if (not root.is_absolute() or not root.is_dir()
                or root.is_symlink()):
            return None
        cursor=root
        for part in SUBPATH:
            cursor=cursor/part
            if cursor.is_symlink() or not cursor.is_dir():
                return None
        archive=cursor
        evidence=inspect_first_m15_672_slot_outcome_quarantine_lab(
            archive_root=archive,window_claims=(),
            inspected_at_utc=inspected_at_utc.astimezone(timezone.utc))
    except (OSError,ValueError,TypeError,KeyError,RuntimeError,OverflowError):
        return None

    rows=evidence.get("first_window_rows")
    if (evidence.get("state") != SOURCE_STATE
            or evidence.get("ledger_slots_accounted") != 672
            or evidence.get("first_window_pair_horizon_slots") != 56
            or evidence.get("first_window_d1_slots") != 28
            or evidence.get("first_window_w1_slots") != 28
            or evidence.get("quarantined_first_window_slots") != 56
            or evidence.get("missing_distinct_nominal_m15_start_prices") != 28
            or evidence.get("other_frozen_slots_not_assessed") != 616
            or type(rows) is not list or len(rows) != 56
            or any(row.get("scored_as_hit") is not False
                   or row.get("scored_as_miss") is not False
                   or row.get("scored_as_trade") is not False
                   for row in rows)
            or evidence.get("broker_price_source_independently_authenticated") is True
            or evidence.get("validated_accuracy") is not None
            or evidence.get("trade_authorized") is not False
            or (evidence.get("mt5_calls"),evidence.get("file_writes"),
                evidence.get("http_requests")) != (0,0,0)):
        return None

    return {
        "schema":SCHEMA,"state":STATE,
        "frozen_total_slots":672,
        "first_nominal_window_slots_quarantined":56,
        "first_nominal_window_distinct_m15_prices_missing":28,
        "remaining_original_slots_unevaluated":616,
        "first_window_horizons":{"D1":28,"W1":28},
        "clock_p0_documentary_historical_claims_checked":False,
        "broker_source_independently_authenticated":False,
        "github_pre_event_witness_independently_authenticated":False,
        "verified_directional_accuracy":None,
        "calibrated_probability":None,
        "score_allowed":False,
        "trade_authorized":False,
        "publishable":False,
        "has_local_price_data_exposed":False,
        "file_writes":0,"mt5_calls":0,"http_requests":0,
        "operational_bias":"AGUARDAR",
    }


__all__ = ("SCHEMA","STATE","inspect_fx28_local_temporal_radar_binding_lab")
