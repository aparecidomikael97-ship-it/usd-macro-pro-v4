"""LAB-only fixed daily observation protocol for G8/28-pair FX bias.

Freezes ONE synthetic daily research observation at 07:00 America/Cuiaba
as a *candidate*, not a user-approved live scheduling decision. It proves
only consistency of caller-supplied clocks, not actual historical receipt,
provider entitlements, sources, macro analysis or forecast success.

No I/O, HTTP, APIs, schedulers, orders, background work or account changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_bias_forecast_bridge_lab import (
    SCHEMA as FORECAST_SCHEMA, FIXED_METHOD,
)

SCHEMA = "ATLASQUANT_TRADER_DAILY_BIAS_FREEZE_LAB_V1"
PROTOCOL = "FX_DAILY_0700_AMERICA_CUIABA_CANDIDATE_V1"
ZONE = ZoneInfo("America/Cuiaba")
FIXED_HOUR, FIXED_MINUTE = 7, 0
HORIZONS = ("D1", "W1", "MN1")
SIDES = ("ALTA", "BAIXA", "NEUTRO", "AGUARDAR")
ID = re.compile(r"^[A-Za-z0-9:_-]{3,100}$")
MAX_EVIDENCE = 100
VETO_POLICY_ID = "MANUAL_PREDECLARED_MACRO_VETO_D1_LAB_V1"


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 60:
        return None
    try:
        value = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return value.astimezone(timezone.utc) if value.tzinfo is not None else None


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_REJECTED_DAILY_OBSERVATION",
        "reason": reason, "protocol_candidate": PROTOCOL,
        "frozen_observation_digest": None, "forecast_rows": 0,
        "real_market_sources_verified": False,
        "real_historical_capture_verified": False,
        "real_oos_accuracy_proven": False,
        "can_feed_live_bias": False, "can_feed_real_backtest": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def freeze_daily_bias_observation_lab(
    batch: Any, evidences: Any, *, checked_at: datetime,
    macro_vetoes: Any = None,
) -> dict[str, Any]:
    """Check exact clock, G8 coverage, 84 rows and pre-release macro handling.

    This does NOT validate the mathematical quality of synthetic strengths.
    An untrusted caller can fabricate a time or digest. Only real immutable
    source receipts and independent review could support historical claims.
    """
    if not isinstance(checked_at, datetime) or checked_at.tzinfo is None:
        raise ValueError("Audit clock requires explicit timezone")
    now = checked_at.astimezone(timezone.utc)
    if not isinstance(batch, Mapping) or batch.get("schema") != FORECAST_SCHEMA or (
        batch.get("state") != "LAB_SYNTHETIC_ISSUED"
    ) or batch.get("method_id") != FIXED_METHOD:
        return _deny("Wrong or non-synthetic bias batch")
    issued = _time(batch.get("issued_at_utc"))
    if issued is None or issued > now:
        return _deny("Missing or future forecast issuance")
    local = issued.astimezone(ZONE)
    if (local.hour, local.minute, local.second, local.microsecond) != (
        FIXED_HOUR, FIXED_MINUTE, 0, 0,
    ) or local.weekday() >= 5:
        return _deny("Forecast not at pre-defined weekday 07:00 Cuiaba LAB cutoff")
    if batch.get("batch_key") is None or not isinstance(batch["batch_key"], str) or (
        not ID.fullmatch(batch["batch_key"])
    ):
        return _deny("Invalid batch identity")
    if not isinstance(batch.get("forecasts"), list) or len(batch["forecasts"]) != 84:
        return _deny("All 28 pairs x three horizons required")
    expected = {(pair, horizon) for pair in OFFICIAL_PAIRS for horizon in HORIZONS}
    observed = set()
    for forecast in batch["forecasts"]:
        if not isinstance(forecast, Mapping):
            return _deny("Malformed forecast")
        pair, horizon = forecast.get("pair"), forecast.get("horizon")
        instant = _time(forecast.get("issued_at_utc"))
        evidence_time = _time(forecast.get("evidence_at_utc"))
        if (not isinstance(pair, str) or not isinstance(horizon, str) or
                pair not in OFFICIAL_PAIRS or horizon not in HORIZONS or
                (pair, horizon) in observed or instant != issued or
                evidence_time is None or evidence_time > issued or
                forecast.get("state") != "LAB_SYNTHETIC_BIAS" or
                forecast.get("method_id") != FIXED_METHOD or
                forecast.get("bias") not in SIDES or
                forecast.get("forecast_id") != (
                    batch["batch_key"] + "-" + horizon + "-" + pair.replace("/", "")
                ) or forecast.get("trade_authorized") is not False):
            return _deny("Forecast identity or point-in-time contract invalid")
        observed.add((pair, horizon))
    if observed != expected:
        return _deny("Incomplete canonical 28 x 3 forecast matrix")

    if not isinstance(evidences, (list, tuple)) or (
        not 1 <= len(evidences) <= MAX_EVIDENCE
    ):
        return _deny("At least one bounded research evidence record required")
    seen = set()
    strength_count = 0
    release_count = 0
    scheduled_count = 0
    captured_ids = []
    known_macro = {}
    predeclared = []
    for item in evidences:
        if not isinstance(item, Mapping) or item.get("state") != "LAB_SYNTHETIC_EVIDENCE":
            return _deny("Evidence is not an explicit synthetic fixture")
        name, source = item.get("evidence_id"), item.get("source")
        kind = item.get("kind")
        available = _time(item.get("captured_at_utc"))
        as_of = _time(item.get("data_as_of_utc"))
        if (not isinstance(name, str) or not ID.fullmatch(name) or name in seen or
                not isinstance(source, str) or not 2 <= len(source.strip()) <= 160 or
                available is None or as_of is None or
                as_of > available or available > issued):
            return _deny("Missing, duplicate, future or post-cutoff evidence receipt")
        seen.add(name)
        captured_ids.append(name)
        if kind == "G8_STRENGTH_REFERENCE":
            currencies = item.get("currencies")
            if (not isinstance(currencies, (list, tuple)) or
                    len(currencies) != len(CURRENCIES) or
                    any(not isinstance(c, str) for c in currencies) or
                    set(currencies) != set(CURRENCIES) or
                    "actual" in item):
                return _deny("No full G8 source metadata or fabricated macro value")
            strength_count += 1
        elif kind == "MACRO_ACTUAL_RELEASED":
            released = _time(item.get("released_at_utc"))
            actual = item.get("actual")
            if (released is None or not released <= as_of <= available or
                    isinstance(actual, bool) or not isinstance(actual, (int, float))):
                return _deny("Actual macro value did not exist by frozen cutoff")
            try:
                valid_actual = isfinite(actual) and abs(actual) <= 1e9
            except (TypeError, ValueError, OverflowError):
                valid_actual = False
            if not valid_actual:
                return _deny("Actual macro number is unbounded or invalid")
            release_count += 1
            known_macro[name] = item
        elif kind == "MACRO_SCHEDULE_ONLY":
            released = _time(item.get("released_at_utc"))
            if (released is None or released <= issued or
                    released > issued + timedelta(days=30) or
                    "actual" in item or "surprise" in item):
                return _deny("Future macro event cannot contain actual/surprise")
            scheduled_count += 1
        else:
            return _deny("Unknown evidence kind")
    if strength_count != 1:
        return _deny("Exactly one complete synthetic G8 strength source required")
    # The candidate macro plan MUST be present in the frozen content hash,
    # not supplied separately at evaluation time after future price labels.
    if macro_vetoes is None:
        macro_vetoes = []
    if not isinstance(macro_vetoes, (list, tuple)) or len(macro_vetoes) > len(OFFICIAL_PAIRS):
        return _deny("Invalid number of macro policy decisions")
    forecast_index = {f["forecast_id"]: f for f in batch["forecasts"]}
    seen_veto_forecasts = set()
    for veto in macro_vetoes:
        allowed = {"state", "forecast_id", "decided_at_utc", "evidence_ids",
                   "rationale", "trade_authorized", "policy_id"}
        if (not isinstance(veto, Mapping) or set(veto) != allowed
                or veto.get("state") != "LAB_SYNTHETIC_MACRO_VETO"
                or veto.get("policy_id") != VETO_POLICY_ID
                or veto.get("trade_authorized") is not False):
            return _deny("Veto schema or frozen methodology is invalid")
        fid = veto.get("forecast_id")
        row = forecast_index.get(fid) if isinstance(fid, str) else None
        if (row is None or row["horizon"] != "D1"
                or row["bias"] not in ("ALTA", "BAIXA")
                or fid in seen_veto_forecasts or _time(veto.get("decided_at_utc")) != issued):
            return _deny("Macro decision must be unique and fixed at D1 issue cutoff")
        rationale, ids = veto.get("rationale"), veto.get("evidence_ids")
        if (not isinstance(rationale, str) or not 5 <= len(rationale.strip()) <= 300
                or not isinstance(ids, (list, tuple)) or not 1 <= len(ids) <= 5
                or any(not isinstance(x, str) for x in ids)
                or len(set(ids)) != len(ids)):
            return _deny("Veto requires a bounded rationale and unique macro sources")
        base, quote = split_pair(row["pair"])
        for eid in ids:
            ev = known_macro.get(eid)
            if ev is None or ev.get("currency") not in (base, quote):
                return _deny("Veto cites unavailable or unrelated macro event")
            released, received = _time(ev.get("released_at_utc")), _time(ev.get("captured_at_utc"))
            if released is None or received is None or released > received or received > issued:
                return _deny("Macro event was not known by forecast issue cutoff")
        seen_veto_forecasts.add(fid)
        predeclared.append(veto)
    # Deterministic digest is only a local content identifier; there is no
    # signature, independent witness, durable storage or trusted time authority.
    try:
        canonical = json.dumps(
            {"batch": batch, "evidences": sorted(evidences, key=lambda e: e["evidence_id"]),
             "macro_veto_policy": VETO_POLICY_ID,
             "macro_vetoes": sorted(predeclared, key=lambda v: v["forecast_id"]),
             "protocol": PROTOCOL},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError):
        return _deny("Unserializable or non-finite research evidence")
    fingerprint = sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "schema": SCHEMA, "state": "LAB_FROZEN_SYNTHETIC_OBSERVATION",
        "protocol_candidate": PROTOCOL,
        "protocol_approved_for_live_use": False,
        "research_zone": "America/Cuiaba",
        "research_cutoff_local": "07:00",
        "issued_at_utc": issued.isoformat(),
        "session_label_lab": local.date().isoformat(),
        "forecast_rows": len(observed), "covered_pairs": len(OFFICIAL_PAIRS),
        "evidence_ids": sorted(captured_ids),
        "macro_actuals_before_cutoff": release_count,
        "macro_future_schedules_without_actual": scheduled_count,
        "macro_veto_policy_lab": VETO_POLICY_ID,
        "predeclared_macro_vetoes": len(predeclared),
        "macro_plan_included_in_digest": True,
        "frozen_observation_digest": fingerprint,
        "digest_is_independent_custody": False,
        "real_market_sources_verified": False,
        "real_historical_capture_verified": False,
        "real_oos_accuracy_proven": False,
        "can_feed_live_bias": False, "can_feed_real_backtest": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
        "why_not": "07:00 is an unapproved LAB research choice; caller timestamps "
                   "and digest cannot prove original availability or historic accuracy.",
    }


__all__ = ["SCHEMA", "PROTOCOL", "VETO_POLICY_ID",
           "freeze_daily_bias_observation_lab"]
