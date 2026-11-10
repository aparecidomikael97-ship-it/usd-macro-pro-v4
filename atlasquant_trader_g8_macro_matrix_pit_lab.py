"""One shared G8 macro receipt set -> 28 two-sided as-of claims (offline LAB).

Reuses the established pair-level publication/capture chronology gate. No
source authentication, live bias, probability, backtest approval or broker IO.
Run separately at each D1/W1 decision cutoff with receipts available THEN.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_macro_asof_lab import (
    ENVELOPE, EXPECTED, RECORD_FIELD_VARIANTS,
    inspect_g8_pair_macro_asof_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_MACRO_MATRIX_PIT_LAB_V1"
HORIZONS = ("D1", "W1")
MAX_RECORDS_PER_CURRENCY = 12
MAX_PAIR_ENVELOPE_BYTES = 48_000


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_BLOCKED", "reason": reason,
        "horizon": None, "decision_at_utc": None,
        "currency_count": 0, "pair_count": 0, "pairs": {},
        "claim_only_complete_pairs": 0, "incomplete_pairs": 0,
        "rejected_pairs": 0, "source_independently_authenticated": False,
        "historical_point_in_time_verified": False,
        "broker_price_source_verified": False, "backtest_approved": False,
        "validated_prediction_count": 0, "validated_accuracy": None,
        "directional_probability": None, "score_0_to_10": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "publishable": False, "http_requests": 0, "new_cost_brl": 0,
    }


def _clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def inspect_g8_macro_matrix_pit_lab(
    receipts_by_currency: Any, *, horizon: str,
    decision_at_utc: datetime, evaluated_at_utc: datetime,
) -> dict[str, Any]:
    """Audit identical currency evidence across all 28 canonical crosses.

    Claims must already be filtered to the selected historical decision. A
    future release/capture is rejected, not silently shifted or interpolated.
    Results describe *claimed metadata coverage*, never trustworthy values.
    """
    out = _blocked("INVALID_MATRIX_OR_CLOCK")
    decision, evaluated = _clock(decision_at_utc), _clock(evaluated_at_utc)
    if (decision is None or evaluated is None or decision > evaluated
            or horizon not in HORIZONS
            or not isinstance(receipts_by_currency, dict)
            or set(receipts_by_currency) != set(CURRENCIES)
            or len(OFFICIAL_PAIRS) != 28):
        return out

    seen = set()
    for currency in CURRENCIES:
        rows = receipts_by_currency[currency]
        if not isinstance(rows, list) or len(rows) > MAX_RECORDS_PER_CURRENCY:
            out["reason"] = "INVALID_CURRENCY_RECEIPT_COLLECTION"
            return out
        for row in rows:
            if (not isinstance(row, dict)
                    or frozenset(row) not in RECORD_FIELD_VARIANTS
                    or row.get("currency") != currency
                    or not isinstance(row.get("indicator"), str)
                    or not isinstance(row.get("observation_period"), str)
                    or ("publication_stage" in row and
                        not isinstance(row["publication_stage"], str))):
                out["reason"] = "CURRENCY_RECEIPT_SCHEMA_OR_OWNER_INVALID"
                return out
            # One FLASH plus one later FINAL may share a reference month;
            # duplicates of the *same stage* cannot be reused in 28 crosses.
            # The pair gate performs the final stage/chronology checks.
            key = (currency, row.get("indicator"), row.get("observation_period"),
                   row.get("publication_stage", "UNSPECIFIED"))
            if key in seen:
                out["reason"] = "AMBIGUOUS_DUPLICATE_VINTAGE"
                return out
            seen.add(key)

    pairs = {}
    complete = incomplete = rejected = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        rows = receipts_by_currency[base] + receipts_by_currency[quote]
        if not rows:
            status = "NO_RECEIPTS_FOR_EITHER_CURRENCY"
            missing = [f"{currency}:{indicator}:MISSING"
                       for currency in (base, quote) for indicator in EXPECTED]
            rejected_reason = None
            incomplete += 1
        else:
            envelope = {"schema": ENVELOPE, "pair": pair,
                        "decision_at_utc": decision.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "records": rows}
            try:
                raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                                 allow_nan=False).encode("utf-8")
            except (ValueError, TypeError, OverflowError):
                out["reason"] = "RECEIPT_NOT_SERIALIZABLE"
                return out
            if len(raw) > MAX_PAIR_ENVELOPE_BYTES:
                out["reason"] = "PAIR_RECEIPT_SIZE_EXCEEDED"
                return out
            gate = inspect_g8_pair_macro_asof_lab(raw, as_of_utc=evaluated)
            status = gate["state"]
            missing = list(gate.get("missing_or_stale", []))
            rejected_reason = gate["reason"] if status == "LAB_BLOCKED" else None
            if status == "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED":
                complete += 1
            elif status == "LAB_BLOCKED":
                rejected += 1
            else:
                incomplete += 1

        pairs[pair] = {
            "base": base, "quote": quote, "metadata_claim_state": status,
            "missing_or_stale": missing, "rejection_reason": rejected_reason,
            "economic_values_authenticated": False,
            "calendar_source_verified": False,
            "historical_point_in_time_verified": False,
            "backtest_approved": False, "operational_bias": "AGUARDAR",
        }

    out.update({
        "state": ("LAB_G8_MACRO_MATRIX_HAS_REJECTIONS" if rejected
                  else "LAB_G8_MACRO_MATRIX_CLAIMS_ONLY"),
        "reason": ("REJECTED_PAIR_MACRO_ASOF_OR_SOURCE_CLAIMS" if rejected
                   else "MISSING_OR_STALE_CURRENCY_CLAIMS" if incomplete
                   else "CURRENCY_RECEIPTS_REUSED_CONSISTENTLY_BUT_UNATTESTED"),
        "horizon": horizon, "decision_at_utc": decision.isoformat(),
        "currency_count": len(CURRENCIES), "pair_count": len(pairs),
        "pairs": pairs, "claim_only_complete_pairs": complete,
        "incomplete_pairs": incomplete, "rejected_pairs": rejected,
    })
    return out


__all__ = ["SCHEMA", "HORIZONS", "inspect_g8_macro_matrix_pit_lab"]
