"""Safe D1/W1/MN1 read model: relative strength vs macro hypothesis.

This joins two SYNTHETIC LAB books without promoting either to a real FX
forecast. Macro, micro, geopolitics, news and calendar evidence remain
unverified until independently attested point-in-time inputs are available.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, evaluate_pair, split_pair

SCHEMA = "ATLASQUANT_TRADER_BIAS_PRIORITY_BRIDGE_LAB_V1"
RELATIVE_SCHEMA = "ATLASQUANT_TRADER_BIAS_HORIZONS_LAB_V1"
MACRO_SCHEMA = "ATLASQUANT_TRADER_EXANTE_MACRO_SCENARIOS_LAB_V1"
HORIZONS = ("D1", "W1", "MN1")
LABELS = frozenset({"ALTA", "BAIXA", "NEUTRO", "AGUARDAR"})


def _clock(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 20 <= len(value) <= 40:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None and dt.utcoffset() is not None else None


def _refuse(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "pair_count": len(OFFICIAL_PAIRS),
        "rows": [{"pair": pair, "D1": "AGUARDAR", "W1": "AGUARDAR",
                  "MN1": "AGUARDAR"} for pair in OFFICIAL_PAIRS],
        "relative_currency_rankings": {},
        "required_dimensions": ["MACRO", "MICRO", "GEOPOLITICA", "NOTICIAS",
                                "CALENDARIO_ECONOMICO", "FORCA_RELATIVA"],
        "real_sources_attested": False, "historical_vintage_attested": False,
        "market_forecast_verified": False, "probability_calibrated": None,
        "accuracy_90_proven": False, "can_feed_live_radar": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "publishable": False,
    }


def build_bias_priority_bridge_lab(
    relative: Any, macro: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Explain 28 × 3 synthetic comparisons without ever issuing a live bias.

    The relative-strength book must not be evaluated AFTER the macro book was
    frozen, otherwise a future price-derived index could leak into the story.
    """
    if (not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError("A avaliação exige horário com fuso")
    now = evaluated_at.astimezone(timezone.utc)
    if not isinstance(relative, Mapping) or not isinstance(macro, Mapping):
        return _refuse("REQUIRED_BOOKS_MISSING")
    if (relative.get("schema") != RELATIVE_SCHEMA
            or relative.get("state") != "LAB_SIMULACAO_NAO_HOMOLOGADA"
            or macro.get("schema") != MACRO_SCHEMA
            or macro.get("state") != "LAB_EXANTE_CONDITIONAL_HYPOTHESES_ONLY"):
        return _refuse("ONLY_UNPROMOTED_LAB_BOOKS_SUPPORTED")
    # Spoofed claims of readiness must not pass through a bridge.
    if (relative.get("real_data_verified") is not False
            or relative.get("trade_authorized") is not False
            or macro.get("actual_market_forecast_verified") is not False
            or macro.get("real_macro_sources_verified") is not False
            or macro.get("real_historical_receipt_verified") is not False
            or macro.get("trade_authorized") is not False
            or macro.get("can_feed_live_radar") is not False):
        return _refuse("FORGED_OR_UNSUPPORTED_AUTHORITY")
    evaluated = _clock(relative.get("at_utc"))
    issued = _clock(macro.get("issued_at_utc"))
    if (evaluated is None or issued is None or evaluated > issued
            or issued > now or (now - issued) > timedelta(days=45)):
        return _refuse("CLOCK_OR_HINDSIGHT_CONFLICT")
    periods = relative.get("periods")
    if not isinstance(periods, Mapping) or set(periods) != set(HORIZONS):
        return _refuse("THREE_HORIZONS_REQUIRED")
    rankings = {}
    checked_scores: dict[str, dict[str, float]] = {}
    for horizon in HORIZONS:
        period = periods[horizon]
        if not isinstance(period, Mapping):
            return _refuse("INVALID_PERIOD_EVIDENCE")
        if period.get("state") == "LAB_PRONTO":
            stamp = _clock(period.get("as_of"))
            if stamp is None or stamp > evaluated:
                return _refuse("PERIOD_POSTDATES_FROZEN_STRENGTH")
            strongest, weakest = period.get("strongest"), period.get("weakest")
            scores = period.get("scores")
            if not isinstance(scores, Mapping) or set(scores) != set(CURRENCIES):
                return _refuse("RANKING_NOT_REPRODUCIBLE")
            try:
                score_copy = {c: float(scores[c]) for c in CURRENCIES
                              if type(scores[c]) in (float, int)}
            except (TypeError, ValueError, OverflowError):
                return _refuse("RANKING_NOT_REPRODUCIBLE")
            if (len(score_copy) != len(CURRENCIES)
                    or any(not isfinite(x) or not 0 <= x <= 100
                           for x in score_copy.values())):
                return _refuse("RANKING_NOT_REPRODUCIBLE")
            ordered = sorted(CURRENCIES, key=lambda code: (-score_copy[code], code))
            if strongest != ordered[0] or weakest != ordered[-1]:
                return _refuse("RANKING_NOT_REPRODUCIBLE")
            checked_scores[horizon] = score_copy
            rankings[horizon] = {"state": "SINTETICO", "strongest": strongest,
                                 "weakest": weakest}
        elif period.get("state") == "INDISPONIVEL":
            rankings[horizon] = {"state": "AGUARDAR", "strongest": None,
                                 "weakest": None}
        else:
            return _refuse("INVALID_PERIOD_STATE")
    rr = relative.get("rows")
    mr = macro.get("pair_hypotheses")
    if (relative.get("pair_count") != len(OFFICIAL_PAIRS)
            or not isinstance(rr, list) or not isinstance(mr, list)
            or len(rr) != 28 or len(mr) != 84):
        return _refuse("INCOMPLETE_PAIR_COVERAGE")
    if any(not isinstance(x, Mapping) for x in rr + mr):
        return _refuse("MALFORMED_PAIR_ROW")
    if (any(not isinstance(x.get("pair"), str) or x.get("pair") not in OFFICIAL_PAIRS
            for x in rr + mr)
            or any(not isinstance(x.get("horizon"), str)
                   or x.get("horizon") not in HORIZONS for x in mr)):
        return _refuse("PAIR_OR_HORIZON_DUPLICATED_OR_MISSING")
    by_pair = {x.get("pair"): x for x in rr}
    by_macro = {(x.get("pair"), x.get("horizon")): x for x in mr}
    expected = {(pair, horizon) for pair in OFFICIAL_PAIRS for horizon in HORIZONS}
    if (set(by_pair) != set(OFFICIAL_PAIRS) or len(by_pair) != len(rr)
            or set(by_macro) != expected or len(by_macro) != len(mr)):
        return _refuse("PAIR_OR_HORIZON_DUPLICATED_OR_MISSING")

    rows = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        r = by_pair[pair]
        horizon_rows = r.get("horizons")
        if (r.get("entry_signal") is not False
                or r.get("trade_authorized") is not False
                or not isinstance(horizon_rows, Mapping)
                or set(horizon_rows) != set(HORIZONS)):
            return _refuse("UNSAFE_RELATIVE_ROW")
        comparisons = {}
        for horizon in HORIZONS:
            strength_row = horizon_rows[horizon]
            macro_row = by_macro[(pair, horizon)]
            if not isinstance(strength_row, Mapping):
                return _refuse("INVALID_RELATIVE_HORIZON")
            s, m = strength_row.get("bias"), macro_row.get("bias_hypothesis")
            if (s not in LABELS or m not in LABELS
                    or macro_row.get("trade_authorized") is not False
                    or _clock(macro_row.get("issued_at_utc")) != issued):
                return _refuse("UNSAFE_MACRO_HYPOTHESIS")
            if horizon in checked_scores:
                generated = evaluate_pair(pair, checked_scores[horizon]).side
                expected = {"BUY": "ALTA", "SELL": "BAIXA", "NEUTRAL": "NEUTRO"}[generated]
            else:
                expected = "AGUARDAR"
            if s != expected:
                return _refuse("STRENGTH_BIAS_CONTRADICTS_SCORES")
            if s == "AGUARDAR" or m == "AGUARDAR":
                status = "DADOS_INCOMPLETOS"
            elif s == m and s in ("ALTA", "BAIXA"):
                status = "HIPOTESES_SINTETICAS_CONCORDAM"
            elif s == "NEUTRO" or m == "NEUTRO":
                status = "NEUTRALIDADE_OU_DIVERGENCIA"
            else:
                status = "CONFLITO_ENTRE_HIPOTESES"
            comparisons[horizon] = {
                "relative_strength_hypothesis": s,
                "macro_conditional_hypothesis": m,
                "comparison": status,
                "operational_bias": "AGUARDAR",
                "why_wait": ("Pontuações e hipóteses declaradas em LAB, sem evidência "
                             "macro/notícias/calendário com custódia temporal nem OOS."),
                "as_of_utc": issued.isoformat(),
                "evidence_ready": {
                    "macro": False, "micro": False, "geopolitics": False,
                    "news": False, "economic_calendar": False,
                    "relative_strength_origin": False,
                },
            }
        rows.append({"pair": pair, "base": base, "quote": quote,
                     "horizons": comparisons, "trade_authorized": False})
    out = _refuse("SYNTHETIC_EXPLANATION_NOT_REAL_BIAS")
    out.update({"state": "LAB_EXPLANATION_ONLY", "rows": rows,
                "relative_currency_rankings": rankings,
                "issued_at_utc": issued.isoformat(),
                "periods": HORIZONS,
                "why_not": "Até validar fatos, expectativas, notícias, calendário, origem e OOS, todos os vieses operacionais ficam AGUARDAR."})
    return out


__all__ = ["SCHEMA", "HORIZONS", "build_bias_priority_bridge_lab"]
