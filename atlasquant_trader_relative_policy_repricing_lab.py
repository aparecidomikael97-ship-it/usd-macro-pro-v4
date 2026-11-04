"""Counterfactual matched-tenor G8 policy-path revisions (LAB; synthetic only).

Compare *changes* in expected rate paths at the same future tenor, not
different central-bank policy LEVELS. A positive gap is only a hypothetical
relative policy pressure, not a forecast of currency appreciation. Risk
premia, growth, positioning and geopolitics can reverse the relationship.

No original OIS quotes, independent receipts, prices, orders or live signals.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_G8_MATCHED_POLICY_REPRICING_LAB_V1"
METHOD = "SYNTHETIC_MATCHED_TENOR_POLICY_REPRICING_V1"
HORIZONS = ("D1", "W1", "MN1")
TARGET_DAYS = {"D1": (0.5, 1.5), "W1": (4, 10), "MN1": (18, 42)}
FIXED_NEUTRAL_BAND_BP = Decimal("5")
FIELDS = frozenset((
    "currency", "horizon", "measure", "unit", "data_state",
    "window_start_utc", "window_end_utc", "target_at_utc",
    "captured_at_utc", "path_revision_bp", "macro_rationale",
    "micro", "geopolitics",
))
BOOK_FIELDS = frozenset(("state", "method_id", "issued_at_utc", "observations"))
ALIGNMENTS = frozenset(("ALINHADO", "CONTRA", "DESCONHECIDO"))
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
DECIMAL_BP = re.compile(r"^-?(?:0|[1-9]\d{0,2})(?:\.\d{1,2})?$")


def _utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not STAMP.fullmatch(raw):
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.utcoffset() == timedelta(0) else None


def _bp(raw: Any) -> Decimal | None:
    if not isinstance(raw, str) or not DECIMAL_BP.fullmatch(raw):
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if not value.is_finite() or not -250 <= value <= 250:
        return None
    return value


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_POLICY_REPRICING_REFUSED",
        "reason": reason, "currency_horizons": {},
        "pair_hypotheses": [], "currency_count": 0, "pair_count": 0,
        "hypothesis_count": 0, "probability_calibrated": None,
        "market_quotes_verified": False, "independent_receipts_verified": False,
        "directional_accuracy_oos_proven": False, "accuracy_90_proven": False,
        "can_feed_live_radar": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def build_matched_policy_repricing_lab(
    book: Any, *, evaluated_at: datetime,
) -> dict[str, Any]:
    """Compute 84 *research-only* relative repricing hypotheses.

    Every rate-path delta is an explicitly synthetic fixture. It is not
    possible to promote the output to a real FX bias through this API.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError("Timezone-aware evaluation required")
    if not isinstance(book, Mapping) or set(book) != BOOK_FIELDS:
        return _deny("Exact synthetic research-book fields required")
    if (book["state"] != "LAB_SYNTHETIC_POLICY_REPRICING_BOOK"
            or book["method_id"] != METHOD):
        return _deny("No real or unreviewed policy-curve input accepted")
    issued = _utc(book["issued_at_utc"])
    if issued is None or issued > evaluated_at.astimezone(timezone.utc):
        return _deny("Invalid or future issue timestamp")
    raw = book["observations"]
    if not isinstance(raw, (tuple, list)) or len(raw) != 24:
        return _deny("All eight currencies at all three horizons required")

    observed: dict[tuple[str, str], dict[str, Any]] = {}
    anchors: dict[str, tuple[datetime, datetime, datetime]] = {}
    for entry in raw:
        if not isinstance(entry, Mapping) or set(entry) != FIELDS:
            return _deny("Unexpected, missing, or retrospectively added field")
        ccy, horizon = entry["currency"], entry["horizon"]
        if (not isinstance(ccy, str) or ccy not in CURRENCIES
                or not isinstance(horizon, str) or horizon not in HORIZONS):
            return _deny("Noncanonical currency/horizon")
        key = (ccy, horizon)
        if key in observed:
            return _deny("Duplicate currency/horizon")
        if (entry["measure"] != "EXPECTED_POLICY_PATH_REVISION"
                or entry["unit"] != "BASIS_POINTS"
                or entry["data_state"] != "LAB_SYNTHETIC_UNVERIFIED"):
            return _deny("Only explicitly synthetic changes in expected path allowed")
        delta = _bp(entry["path_revision_bp"])
        if delta is None:
            return _deny("Finite, bounded decimal basis-point revision required")
        start = _utc(entry["window_start_utc"])
        end = _utc(entry["window_end_utc"])
        captured = _utc(entry["captured_at_utc"])
        target = _utc(entry["target_at_utc"])
        if any(x is None for x in (start, end, captured, target)):
            return _deny("Precise UTC sampling/capture/target timestamps required")
        if (not start < end <= captured <= issued < target
                or end - start > timedelta(hours=72)
                or issued - end > timedelta(hours=24)):
            return _deny("No future leakage, stale sample, or invalid observation window")
        min_days, max_days = TARGET_DAYS[horizon]
        if not min_days <= (target - issued).total_seconds() / 86400 <= max_days:
            return _deny("The target date does not match the research horizon")
        anchor = (start, end, target)
        if horizon in anchors and anchors[horizon] != anchor:
            return _deny("Currencies must use identical observation window and target")
        anchors[horizon] = anchor
        if (entry["micro"] not in ALIGNMENTS or
                entry["geopolitics"] not in ALIGNMENTS):
            return _deny("Micro/geopolitical review must be explicit")
        rationale = entry["macro_rationale"]
        if (not isinstance(rationale, str)
                or not 12 <= len(rationale.strip()) <= 300):
            return _deny("Bounded ex-ante synthetic rationale required")
        observed[key] = {
            "path_revision_bp": delta, "micro": entry["micro"],
            "geopolitics": entry["geopolitics"],
            "macro_rationale": rationale,
        }

    if len(observed) != len(CURRENCIES) * len(HORIZONS):
        return _deny("Missing expected currency/tenor cell")

    grid, pair_rows = {}, []
    for horizon in HORIZONS:
        grid[horizon] = {
            ccy: {
                "synthetic_path_revision_bp": format(observed[(ccy, horizon)]["path_revision_bp"], "f"),
                "micro": observed[(ccy, horizon)]["micro"],
                "geopolitics": observed[(ccy, horizon)]["geopolitics"],
                "macro_rationale": observed[(ccy, horizon)]["macro_rationale"],
                "quote_verified": False,
            }
            for ccy in CURRENCIES
        }
        for pair in OFFICIAL_PAIRS:
            base, quote = split_pair(pair)
            a, b = observed[(base, horizon)], observed[(quote, horizon)]
            diff = a["path_revision_bp"] - b["path_revision_bp"]
            reviews = (a["micro"], a["geopolitics"],
                       b["micro"], b["geopolitics"])
            if "CONTRA" in reviews:
                mechanism = "VETO_MICRO_GEOPOLITICO"
            elif "DESCONHECIDO" in reviews:
                mechanism = "VETO_EVIDENCIA_INCOMPLETA"
            elif diff > FIXED_NEUTRAL_BAND_BP:
                mechanism = "PRESSAO_RELATIVA_POSITIVA_HIPOTETICA"
            elif diff < -FIXED_NEUTRAL_BAND_BP:
                mechanism = "PRESSAO_RELATIVA_NEGATIVA_HIPOTETICA"
            else:
                mechanism = "PRESSAO_RELATIVA_NEUTRA_HIPOTETICA"
            pair_rows.append({
                "pair": pair, "horizon": horizon, "base": base, "quote": quote,
                "synthetic_relative_revision_bp": format(diff, "f"),
                "research_mechanism": mechanism,
                "directional_bias": "AGUARDAR",
                "probability_calibrated": None, "real_prices_verified": False,
                "trade_authorized": False,
            })
    return {
        **_deny(""), "state": "LAB_SYNTHETIC_MATCHED_POLICY_REPRICING_ONLY",
        "reason": "Counterfactual revision gap; neither authenticated OIS observations nor FX predictive edge",
        "method_id": METHOD, "issued_at_utc": issued.isoformat(),
        "currency_horizons": grid, "pair_hypotheses": pair_rows,
        "currency_count": len(CURRENCIES), "pair_count": len(OFFICIAL_PAIRS),
        "hypothesis_count": len(pair_rows),
        "unit": "BASIS_POINTS", "neutral_band_bp_lab": str(FIXED_NEUTRAL_BAND_BP),
        "same_reference_tenors_required": True,
        "nominal_rate_level_comparison_used": False,
        "input_state": "LAB_SYNTHETIC_UNVERIFIED",
        "why_not": "Risk premia, growth, geopolitics, verified market curves, independent FX prices and genuine OOS validation absent.",
    }


__all__ = ["SCHEMA", "METHOD", "HORIZONS", "build_matched_policy_repricing_lab"]
