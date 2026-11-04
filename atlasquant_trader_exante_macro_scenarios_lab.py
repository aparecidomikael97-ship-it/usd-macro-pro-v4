"""Ex-ante macro scenario fanout: G8/28 FX pairs and five indices, LAB only.

Manually declared SYNTHETIC macro hypotheses are compared before future
events. The model does NOT infer direction from raw statistics, price history
or headlines. It never claims real forecast probability or trading permission.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_EXANTE_MACRO_SCENARIOS_LAB_V1"
METHOD = "MANUAL_SYNTHETIC_PRE_EVENT_MACRO_HYPOTHESIS_V1"
HORIZONS = ("D1", "W1", "MN1")
INDICES = ("SPX500", "NAS100", "US30", "WIN", "WDO")
FACTORS = ("MACRO", "MICRO", "GEOPOLITICS")
CURRENCY_MACRO = {"FORTALECE": 1, "NEUTRO": 0, "ENFRAQUECE": -1, "DESCONHECIDO": None}
INDEX_MACRO = ("ALTA", "BAIXA", "NEUTRO", "AGUARDAR")
ALIGNMENT = ("ALINHADO", "CONTRA", "NEUTRO", "DESCONHECIDO")
BOOK_FIELDS = frozenset({"state", "method_id", "issued_at_utc", "evidences",
                         "currency_views", "index_views"})
EVIDENCE_FIELDS = frozenset({"state", "evidence_id", "category", "kind",
                             "event_at_utc", "published_at_utc",
                             "captured_at_utc", "source_url", "summary"})
VIEW_FIELDS = frozenset({"macro", "micro", "geopolitics", "evidence_by_factor", "rationale"})
IDENTITY = re.compile(r"[A-Za-z0-9:_-]{3,90}")


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not 20 <= len(raw) <= 40:
        return None
    if not (raw.endswith("Z") or raw.endswith("+00:00")):
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.utcoffset() != timedelta(0):
        return None
    return stamp.astimezone(timezone.utc)


def _reject(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_EXANTE_SCENARIO_REJECTED",
        "reason": reason, "pair_hypotheses": [], "index_hypotheses": [],
        "currency_views": {}, "scheduled_evidence_ids": [],
        "probability_calibrated": None, "accuracy_90_proven": False,
        "actual_market_forecast_verified": False,
        "real_macro_sources_verified": False,
        "real_historical_receipt_verified": False,
        "real_oos_verified": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "can_feed_live_radar": False,
    }


def _source_url(value: Any) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 500:
        return False
    try:
        u = urlsplit(value)
        return (u.scheme == "https" and bool(u.hostname)
                and u.username is None and u.password is None
                and u.port in (None, 443) and not u.fragment)
    except ValueError:
        return False


def _validate_evidences(raw: Any, issued: datetime) -> tuple[dict[str, str], list[str]] | str:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 200:
        return "One to 200 bounded synthetic evidence records required"
    found: dict[str, str] = {}
    scheduled = []
    for ev in raw:
        if not isinstance(ev, Mapping) or set(ev) != EVIDENCE_FIELDS:
            return "Unexpected evidence fields or retrospective actual"
        eid, kind, category = ev["evidence_id"], ev["kind"], ev["category"]
        if (ev["state"] != "LAB_SYNTHETIC_PREISSUE_EVIDENCE"
                or not isinstance(eid, str) or not IDENTITY.fullmatch(eid)
                or eid in found or category not in FACTORS
                or kind not in ("SCHEDULED", "RELEASED_CONTEXT")
                or not _source_url(ev["source_url"])
                or not isinstance(ev["summary"], str)
                or not 6 <= len(ev["summary"].strip()) <= 300):
            return "Evidence identity, category or source invalid"
        event = _utc(ev["event_at_utc"])
        published = _utc(ev["published_at_utc"])
        captured = _utc(ev["captured_at_utc"])
        if (event is None or published is None or captured is None
                or not published <= captured <= issued):
            return "Evidence receipt not proven before forecast issue cutoff"
        if kind == "SCHEDULED":
            if event <= issued:
                return "Scheduled event must still lie in the future"
            scheduled.append(eid)
        elif not event <= published:
            return "Released context cannot precede its own event"
        found[eid] = category
    return found, scheduled


def _check_view(raw: Any, allowed_macro: set[str], evidence: dict[str, str]) -> str | None:
    if not isinstance(raw, Mapping) or set(raw) != VIEW_FIELDS:
        return "Missing or extra hypothesis fields"
    if (not isinstance(raw["macro"], str) or not isinstance(raw["micro"], str)
            or not isinstance(raw["geopolitics"], str)
            or raw["macro"] not in allowed_macro or raw["micro"] not in ALIGNMENT
            or raw["geopolitics"] not in ALIGNMENT):
        return "Invalid categorical macro, micro or geopolitics hypothesis"
    if not isinstance(raw["rationale"], str) or not 8 <= len(raw["rationale"].strip()) <= 400:
        return "Hypothesis needs a bounded explanation"
    by_factor = raw["evidence_by_factor"]
    if not isinstance(by_factor, Mapping) or set(by_factor) != set(FACTORS):
        return "Every factor needs an explicit evidence list"
    for factor in FACTORS:
        refs = by_factor[factor]
        if (not isinstance(refs, list) or len(refs) > 5
                or len(refs) != len(set(str(x) for x in refs))
                or any(not isinstance(x, str) or evidence.get(x) != factor for x in refs)):
            return "Evidence reference missing, duplicate or from wrong category"
    if raw["macro"] not in ("DESCONHECIDO", "AGUARDAR") and not by_factor["MACRO"]:
        return "Directional or neutral macro hypothesis lacks evidence"
    for key, factor in (("micro", "MICRO"), ("geopolitics", "GEOPOLITICS")):
        if raw[key] in ("ALINHADO", "CONTRA") and not by_factor[factor]:
            return "Non-neutral micro/geopolitical claim lacks evidence"
    return None


def _decision(macro: str, channel: list[str]) -> tuple[str, str]:
    if macro in ("DESCONHECIDO", "AGUARDAR"):
        return "AGUARDAR", "Macro direction not declared before event"
    if "CONTRA" in channel:
        return "AGUARDAR", "Micro or geopolitics conflicts with macro hypothesis"
    if "DESCONHECIDO" in channel:
        return "AGUARDAR", "Incomplete micro/geopolitical review"
    return macro, "Synthetic conditional hypothesis, not calibrated direction"


def issue_macro_scenario_fanout_lab(book: Any, *, evaluated_at: datetime) -> dict[str, Any]:
    """Freeze a caller-declared, pre-event scenario and fan out to FX and indices."""
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Evaluation time requires timezone")
    if not isinstance(book, Mapping) or set(book) != BOOK_FIELDS:
        return _reject("Scenario book schema incomplete")
    if book["state"] != "LAB_SYNTHETIC_SCENARIO_BOOK" or book["method_id"] != METHOD:
        return _reject("No real or retrospectively relabeled scenario accepted")
    issued = _utc(book["issued_at_utc"])
    if issued is None or issued > evaluated_at.astimezone(timezone.utc):
        return _reject("Issue time is future, missing or not UTC")
    checked = _validate_evidences(book["evidences"], issued)
    if isinstance(checked, str):
        return _reject(checked)
    evidence, scheduled = checked
    currencies, indices = book["currency_views"], book["index_views"]
    if (not isinstance(currencies, Mapping) or set(currencies) != set(HORIZONS)
            or not isinstance(indices, Mapping) or set(indices) != set(HORIZONS)):
        return _reject("Exactly three independent horizon books required")
    for h in HORIZONS:
        if (not isinstance(currencies[h], Mapping) or set(currencies[h]) != set(CURRENCIES)
                or not isinstance(indices[h], Mapping) or set(indices[h]) != set(INDICES)):
            return _reject("Incomplete canonical eight currencies or five indices")
        for key, row in currencies[h].items():
            failure = _check_view(row, set(CURRENCY_MACRO), evidence)
            if failure:
                return _reject(f"{h} {key}: {failure}")
        for key, row in indices[h].items():
            failure = _check_view(row, set(INDEX_MACRO), evidence)
            if failure:
                return _reject(f"{h} {key}: {failure}")
    pair_rows, index_rows = [], []
    for horizon in HORIZONS:
        views = currencies[horizon]
        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            a, b = views[base], views[quote]
            levels = (CURRENCY_MACRO[a["macro"]], CURRENCY_MACRO[b["macro"]])
            if None in levels:
                raw_bias = "AGUARDAR"
            else:
                difference = levels[0] - levels[1]
                raw_bias = "ALTA" if difference > 0 else "BAIXA" if difference < 0 else "NEUTRO"
            bias, reason = _decision(raw_bias, [
                a["micro"], b["micro"], a["geopolitics"], b["geopolitics"],
            ])
            pair_rows.append({
                "pair": pair, "horizon": horizon, "bias_hypothesis": bias,
                "reason": reason, "macro_base": a["macro"], "macro_quote": b["macro"],
                "issued_at_utc": issued.isoformat(), "probability_calibrated": None,
                "entry_signal": False, "trade_authorized": False,
            })
        for symbol in INDICES:
            view = indices[horizon][symbol]
            bias, reason = _decision(view["macro"], [view["micro"], view["geopolitics"]])
            index_rows.append({
                "symbol": symbol, "horizon": horizon, "bias_hypothesis": bias,
                "reason": reason, "issued_at_utc": issued.isoformat(),
                "probability_calibrated": None, "trade_authorized": False,
            })
    return {
        **_reject(""), "state": "LAB_EXANTE_CONDITIONAL_HYPOTHESES_ONLY",
        "reason": "Synthetic views, not a learned macro forecasting model",
        "method_id": METHOD, "issued_at_utc": issued.isoformat(),
        "currency_views": currencies, "pair_hypotheses": pair_rows,
        "index_hypotheses": index_rows,
        "scheduled_evidence_ids": scheduled,
        "why_not": "The caller chooses synthetic macro expectations. A scenario "
                   "fanout is not an actual prediction or a 90% probability. "
                   "Independent point-in-time sources and walk-forward OOS are missing.",
    }


__all__ = ["SCHEMA", "METHOD", "HORIZONS", "INDICES", "issue_macro_scenario_fanout_lab"]
