"""Read-only, FAIL-CLOSED vetting of user-supplied FX quote books in LAB.

This checks structural completeness, time order, internal consistency and
triangular residuals for the 28 G8 spot pairs in D1/W1/MN1. It does NOT
attest source truth, historic capture, licensing or trading fitness.

Even a perfectly consistent synthetic or forged book can pass structural
checks. No result may be converted into a VALIDATED_DAILY UI contract.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite, log
from typing import Any, Mapping
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx_strength_from_quotes_lab import (
    AGE_SECONDS, MAX_DISAGREEMENT_BP_LAB, WINDOW_DAYS,
)

SCHEMA = "ATLASQUANT_TRADER_FX_QUOTE_INTAKE_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
QUOTE_FIELDS = frozenset(("source_id", "start", "end", "start_at_utc",
                          "end_at_utc", "captured_start_at_utc",
                          "captured_end_at_utc"))
BOOK_FIELDS = frozenset(("state", "data_kind", "source_id", "source_url",
                         "price_kind", "as_of_utc", "period_end", "pairs"))
MAX_CAPTURE_SKEW_SECONDS = 60


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or len(raw) > 60:
        return None
    try:
        v = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return v.astimezone(timezone.utc) if v.tzinfo is not None else None


def _price(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if isfinite(n) and 0 < n <= 1e8 else None


def _unavailable(reason: str) -> dict[str, Any]:
    return {"state": "QUARANTINED", "reason": reason,
            "coverage": 0, "triangular_residual_bp": None,
            "as_of_utc": None, "max_capture_skew_seconds": None}


def _check_one(book: Any, *, horizon: str, at: datetime) -> dict[str, Any]:
    if not isinstance(book, Mapping) or set(book) != BOOK_FIELDS:
        return _unavailable("Missing or extra quote book fields")
    if book["state"] != "LAB_UNVERIFIED_QUOTE_BOOK" or (
        book["data_kind"] != "UNVERIFIED_FX_SPOT_CANDIDATE" or
        book["price_kind"] != "SPOT_MID_UNVERIFIED"
    ):
        return _unavailable("Quote book must explicitly declare unverified research status")
    sid = book["source_id"]
    if not isinstance(sid, str) or not 3 <= len(sid.strip()) <= 100:
        return _unavailable("Provider identity absent or invalid")
    url = book["source_url"]
    if not isinstance(url, str) or len(url) > 500:
        return _unavailable("Source URL missing")
    try:
        parsed = urlsplit(url)
        valid_url = (parsed.scheme == "https" and bool(parsed.hostname)
                     and parsed.username is None and parsed.password is None
                     and not parsed.fragment and parsed.port in (None, 443))
    except ValueError:
        valid_url = False
    if not valid_url:
        return _unavailable("Source URL must be HTTPS without credentials/fragment")
    observed = _utc(book["as_of_utc"])
    if observed is None or not 0 <= (at - observed).total_seconds() <= AGE_SECONDS[horizon]:
        return _unavailable("Source timestamp is future or outside horizon freshness")
    pairs = book["pairs"]
    if not isinstance(pairs, Mapping) or set(pairs) != set(OFFICIAL_PAIRS):
        return _unavailable("Incomplete or noncanonical FX universe (exactly 28 required)")
    t_start = t_end = None
    observations = {}
    captures_start = []
    captures_end = []
    for pair in OFFICIAL_PAIRS:
        quote = pairs[pair]
        if not isinstance(quote, Mapping) or set(quote) != QUOTE_FIELDS:
            return _unavailable("Unrecognized or incomplete quote fields")
        if quote["source_id"] != sid:
            return _unavailable("Pair source identity differs from book")
        begin, end = _utc(quote["start_at_utc"]), _utc(quote["end_at_utc"])
        cbegin = _utc(quote["captured_start_at_utc"])
        cend = _utc(quote["captured_end_at_utc"])
        a, b = _price(quote["start"]), _price(quote["end"])
        if any(v is None for v in (begin, end, cbegin, cend, a, b)):
            return _unavailable("Quote timestamp or numeric spot price invalid")
        if not begin < end <= cend <= observed <= at or not begin <= cbegin <= cend:
            return _unavailable("Historical quote/capture timestamp impossible")
        if t_start is None:
            t_start, t_end = begin, end
        elif (begin, end) != (t_start, t_end):
            return _unavailable("FX legs not sampled on identical start/end instants")
        ret = log(b) - log(a)
        if abs(ret) > 0.5:
            return _unavailable("Implausible log return outside research bounds")
        observations[pair] = ret
        captures_start.append(cbegin)
        captures_end.append(cend)
    if book["period_end"] != t_end.date().isoformat():
        return _unavailable("Declared calendar period differs from UTC end")
    days = (t_end - t_start).total_seconds() / 86400
    low, high = WINDOW_DAYS[horizon]
    if not low <= days <= high:
        return _unavailable("Wrong D1/W1/MN1 historical sampling window")
    if (max(captures_start) - min(captures_start)).total_seconds() > MAX_CAPTURE_SKEW_SECONDS or (
        max(captures_end) - min(captures_end)).total_seconds() > MAX_CAPTURE_SKEW_SECONDS:
        return _unavailable("Source capture across 28 FX pairs is not synchronized")
    # Independent 28 pair input should be triangularly consistent.
    latent = {c: 0.0 for c in CURRENCIES}
    for pair, ret in observations.items():
        base, quote = split_pair(pair)
        latent[base] += ret
        latent[quote] -= ret
    latent = {c: value / len(CURRENCIES) for c, value in latent.items()}
    residual = max(abs(ret - (latent[split_pair(pair)[0]] -
                              latent[split_pair(pair)[1]]))
                   for pair, ret in observations.items()) * 10000
    if residual > MAX_DISAGREEMENT_BP_LAB:
        return _unavailable("Triangular cross-rate residual exceeds LAB tolerance")
    return {
        "state": "LAB_STRUCTURAL_CANDIDATE_UNVERIFIED",
        "reason": "Complete synchronized G8 graph; provider and archive NOT authenticated",
        "coverage": 28, "triangular_residual_bp": round(residual, 7),
        "as_of_utc": observed.isoformat(),
        "max_capture_skew_seconds": max(
            (max(captures_start) - min(captures_start)).total_seconds(),
            (max(captures_end) - min(captures_end)).total_seconds(),
        ),
        "start_utc": t_start.isoformat(), "end_utc": t_end.isoformat(),
    }


def audit_fx_quote_intake_lab(books: Any, *, at: datetime) -> dict[str, Any]:
    """Inspect local candidate evidence only. Never admit it to real Radar/OOS."""
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Evaluation instant must contain an explicit timezone")
    now = at.astimezone(timezone.utc)
    supplied = books if isinstance(books, Mapping) else {}
    if set(supplied) - set(HORIZONS):
        supplied = {}
    results = {h: (_check_one(supplied[h], horizon=h, at=now)
                   if h in supplied else _unavailable("Missing " + h + " quote snapshot"))
               for h in HORIZONS}
    all_ready = all(v["state"] == "LAB_STRUCTURAL_CANDIDATE_UNVERIFIED"
                    for v in results.values())
    return {
        "schema": SCHEMA,
        "state": ("LAB_THREE_HORIZONS_STRUCTURALLY_COMPLETE_UNTRUSTED"
                  if all_ready else "LAB_QUOTE_INTAKE_INCOMPLETE_QUARANTINED"),
        "evaluated_at_utc": now.isoformat(),
        "required_pairs": len(OFFICIAL_PAIRS),
        "required_currencies": len(CURRENCIES),
        "required_horizons": list(HORIZONS),
        "horizon_checks": results,
        "no_real_provider_authentication": True,
        "independent_capture_verified": False,
        "provider_license_verified": False,
        "market_quotes_verified": False,
        "oos_validated": False,
        "actual_currency_strength": None,
        "real_bias_28_pairs": None,
        "daily_ui_contract": None,
        "can_feed_live_radar": False,
        "can_feed_real_oos": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "why_not": "Structural timestamps/triangulation alone do not prove "
                   "provider receipts, real contemporaneous availability, "
                   "commercial reuse rights or predictive performance.",
    }


__all__ = ["SCHEMA", "HORIZONS", "audit_fx_quote_intake_lab"]
