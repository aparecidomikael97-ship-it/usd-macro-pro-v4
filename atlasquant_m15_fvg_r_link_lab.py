"""Connect FVG formation to hypothetical M15 R replay without hindsight.

Offline-only research; no price feed, signal strategy, orders or profitability.
The caller must supply stop and target and assumed spread/slippage explicitly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_m15_fvg_causal_lab import SCHEMA as FVG_SCHEMA, scan_m15_fvg
from atlasquant_m15_execution_replay_lab import SCHEMA as REPLAY_SCHEMA, replay_m15_setup

SCHEMA = "ATLASQUANT_M15_FVG_TO_R_CAUSAL_LAB_V1"
OUTPUT_SCHEMA = "ATLASQUANT_M15_FVG_TO_R_RESULT_LAB_V1"


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": OUTPUT_SCHEMA, "state": "BLOCKED", "reason": reason,
        "fvg": None, "scenario": None,
        "fvg_formation_geometry_verified": False,
        "source_authenticated": False, "signal_causal_verified": False,
        "trend_verified": False, "spread_slippage_verified": False,
        "setup_accuracy_verified": False, "profitability_verified": False,
        "publishable": False, "trade_authorized": False,
    }


def link_fvg_to_r(payload: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Link a formed-on-index FVG to the next-bar-open *hypothetical* replay.

    Only bars through signal index are inspected for the FVG. Remaining bars
    are used solely to replay what would have followed, not to choose an FVG.
    """
    if not isinstance(payload, Mapping) or payload.get("schema") != SCHEMA:
        return _blocked("INVALID_CONTRACT")
    if payload.get("state") != "OFFLINE_RESEARCH" or payload.get("timeframe") != "M15":
        return _blocked("INVALID_CONTRACT")
    if payload.get("pair") not in OFFICIAL_PAIRS:
        return _blocked("INVALID_PAIR")
    if any(k in payload for k in ("api_key", "token", "authorization", "access_token")):
        return _blocked("SENSITIVE_FIELD_NOT_ALLOWED")
    allowed = {"schema", "state", "timeframe", "pair", "signal_bar_index",
               "fvg_filters", "risk_plan", "bars"}
    if set(payload) != allowed:
        return _blocked("UNEXPECTED_OR_MISSING_FIELD")
    bars = payload.get("bars")
    if not isinstance(bars, list) or not 4 <= len(bars) <= 500:
        return _blocked("INVALID_BAR_COUNT")
    index = payload.get("signal_bar_index")
    if type(index) is not int or not 2 <= index < len(bars) - 1:
        return _blocked("INVALID_FORMATION_INDEX")
    if not all(isinstance(b, Mapping) and b.get("complete") is True for b in bars):
        return _blocked("OPEN_BAR_NOT_ALLOWED")
    filters = payload.get("fvg_filters")
    risk = payload.get("risk_plan")
    if not isinstance(filters, Mapping) or not isinstance(risk, Mapping):
        return _blocked("MISSING_EXPLICIT_FILTERS_OR_RISK")
    if any(k in filters or k in risk for k in ("api_key", "token", "authorization", "access_token")):
        return _blocked("SENSITIVE_FIELD_NOT_ALLOWED")
    allowed_filters = {"point_size", "minimum_gap_points", "middle_body_min_fraction"}
    allowed_risk = {"stop_mid", "target_mid", "spread_points_assumed", "slippage_points_assumed"}
    if set(filters) != allowed_filters or set(risk) != allowed_risk:
        return _blocked("MISSING_EXPLICIT_FILTERS_OR_RISK")
    current = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    prefix = bars[:index + 1]
    fvg_input = {
        "schema": FVG_SCHEMA, "state": "OFFLINE_RESEARCH",
        "timeframe": "M15", "pair": payload["pair"],
        "bars": prefix, **filters,
    }
    formation = scan_m15_fvg(fvg_input, now=current)
    if formation["state"] != "RESEARCH_ONLY":
        return _blocked("FVG_PREFIX_" + formation["reason"])
    # The last closed candle of the prefix is the *only* admissible source of
    # formation, even if older active zones exist in the same history.
    creation_time = formation["as_of"]
    formed = [z for z in formation["zones"] if z["created_at"] == creation_time]
    if len(formed) != 1 or formed[0]["status"] != "ACTIVE":
        return _blocked("NO_FVG_FORMED_AT_SIGNAL_CLOSE")
    zone = formed[0]
    side = "BUY" if zone["direction"] == "BULLISH" else "SELL"
    replay_input = {
        "schema": REPLAY_SCHEMA, "state": "OFFLINE_RESEARCH", "timeframe": "M15",
        "pair": payload["pair"], "side": side, "setup_kind": "FVG",
        "signal_bar_index": index, "signal_confirmed_at": creation_time,
        "bars": bars, "point_size": filters["point_size"], **risk,
    }
    scenario = replay_m15_setup(replay_input, now=current)
    if scenario["state"] != "RESEARCH_ONLY":
        return _blocked("REPLAY_" + scenario["reason"])
    out = _blocked("SYNTHETIC_CAUSAL_GEOMETRY_ONLY")
    out.update({
        "state": "RESEARCH_ONLY", "pair": payload["pair"], "timeframe": "M15",
        "signal_bar_index": index, "fvg": zone, "scenario": scenario,
        "fvg_formation_geometry_verified": True,
        "notice": ("Geometry was formed without lookahead; this is NOT a "
                   "verified trading signal, entry rule or profitability estimate."),
    })
    return out


__all__ = ["SCHEMA", "OUTPUT_SCHEMA", "link_fvg_to_r"]
