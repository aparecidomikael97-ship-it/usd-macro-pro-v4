"""Offline, claim-only forecast hash chain for AtlasQuant Trader (LAB).

The chain detects edits against separately preserved receipts. It does NOT
prove that a forecast really existed at the claimed time: a caller can rewrite
the entire chain. No trading, scheduling, logging or score calibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS


SCHEMA = "ATLASQUANT_TRADER_FX_PRECOMMIT_CHAIN_LAB_V1"
HORIZON_DAYS = {"D1": (1, 4), "W1": (7, 10), "M1": (28, 35)}
SIDES = ("UP", "DOWN", "ABSTAIN")
ABSTAIN_REASONS = frozenset((
    "MISSING_BILATERAL_MACRO", "UNVERIFIED_SOURCE_TIME",
    "CONFLICTING_EVIDENCE", "LOW_QUALITY_SCORE", "CALENDAR_RISK",
    "STALE_MARKET_DATA", "NO_EDGE", "OTHER_DOCUMENTED_RISK",
))
_ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{2,63}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ISSUER = re.compile(r"[A-Z][A-Z0-9_]{1,31}\Z")
_ZERO_HASH = "0" * 64


@dataclass(frozen=True)
class MacroVintageClaim:
    currency: str
    issuer_code: str
    release_id: str
    published_at: datetime
    captured_at: datetime
    original_sha256_claim: str


@dataclass(frozen=True)
class ForecastPrecommitClaim:
    opportunity_id: str
    pair: str
    horizon: str
    side: str
    abstain_reason: str | None
    features_captured_at: datetime
    features_sha256_claim: str
    model_frozen_at: datetime
    model_sha256_claim: str
    prediction_issued_at: datetime
    outcome_start_at: datetime
    outcome_end_at: datetime
    macro_vintages: tuple[MacroVintageClaim, ...]


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sha(value: Any) -> bool:
    return isinstance(value, str) and _HEX.fullmatch(value) is not None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PRECOMMIT_CHAIN_BLOCKED",
        "reason": reason, "record_count": 0, "caller_claim_only_emitted": 0,
        "caller_claim_only_abstained": 0, "chain_entries": [],
        "head_sha256_claim": None, "local_hash_chain_self_consistent": False,
        "external_anchor_authenticated": False,
        "prediction_timestamp_independently_attested": False,
        "macro_source_issuer_authenticated": False,
        "features_point_in_time_verified": False,
        "precommitted_prediction_independently_proven": False,
        "can_feed_validated_backtest": False,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0,
    }


def _canonical_claim(row: ForecastPrecommitClaim, evaluated: datetime) -> dict[str, Any] | str:
    if (not isinstance(row, ForecastPrecommitClaim)
            or not isinstance(row.opportunity_id, str)
            or _ID.fullmatch(row.opportunity_id) is None
            or row.pair not in OFFICIAL_PAIRS
            or not isinstance(row.horizon, str)
            or row.horizon not in HORIZON_DAYS
            or not isinstance(row.side, str)
            or row.side not in SIDES
            or not _sha(row.features_sha256_claim)
            or not _sha(row.model_sha256_claim)
            or not isinstance(row.macro_vintages, tuple)
            or len(row.macro_vintages) > 2):
        return "INVALID_ID_PAIR_HORIZON_SIDE_OR_DIGEST"
    features, frozen, issued, outcome_start, outcome_end = (
        _utc(v) for v in (row.features_captured_at, row.model_frozen_at,
                          row.prediction_issued_at, row.outcome_start_at,
                          row.outcome_end_at))
    if any(v is None for v in (features, frozen, issued, outcome_start, outcome_end)):
        return "INVALID_FORECAST_CLOCKS"
    days_min, days_max = HORIZON_DAYS[row.horizon]
    if (not frozen <= features <= issued <= evaluated
            or not issued < outcome_start < outcome_end
            or not timedelta(days=days_min) <= outcome_end - outcome_start <= timedelta(days=days_max)):
        return "FUTURE_LEAKAGE_OR_HORIZON_DURATION_INVALID"

    if row.side == "ABSTAIN":
        if (not isinstance(row.abstain_reason, str)
                or row.abstain_reason not in ABSTAIN_REASONS):
            return "ABSTENTION_REASON_REQUIRED"
    elif row.abstain_reason is not None:
        return "EMITTED_FORECAST_CANNOT_HAVE_ABSTENTION_REASON"

    currencies = row.pair.split("/")
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for v in row.macro_vintages:
        if (not isinstance(v, MacroVintageClaim)
                or not isinstance(v.currency, str)
                or v.currency not in currencies or v.currency in seen
                or not isinstance(v.issuer_code, str)
                or _ISSUER.fullmatch(v.issuer_code) is None
                or not isinstance(v.release_id, str)
                or _ID.fullmatch(v.release_id) is None
                or not _sha(v.original_sha256_claim)):
            return "INVALID_OR_DUPLICATE_MACRO_CURRENCY_CLAIM"
        published, captured = _utc(v.published_at), _utc(v.captured_at)
        if (published is None or captured is None
                or not published <= captured <= features):
            return "MACRO_RELEASE_NOT_AVAILABLE_AT_FORECAST_FEATURE_TIME"
        seen.add(v.currency)
        refs.append({
            "currency": v.currency, "issuer_code_claim": v.issuer_code,
            "release_id": v.release_id, "published_at_claim": _stamp(published),
            "captured_at_claim": _stamp(captured),
            "original_sha256_claim": v.original_sha256_claim,
        })
    if row.side != "ABSTAIN" and seen != set(currencies):
        return "EMITTED_FORECAST_REQUIRES_BOTH_CURRENCY_MACRO_VINTAGES"

    return {
        "opportunity_id": row.opportunity_id, "pair": row.pair,
        "horizon": row.horizon, "side_claim": row.side,
        "abstain_reason": row.abstain_reason,
        "features_captured_at_claim": _stamp(features),
        "features_sha256_claim": row.features_sha256_claim,
        "model_frozen_at_claim": _stamp(frozen),
        "model_sha256_claim": row.model_sha256_claim,
        "prediction_issued_at_claim": _stamp(issued),
        "outcome_start_at_claim": _stamp(outcome_start),
        "outcome_end_at_claim": _stamp(outcome_end),
        "macro_vintages_claim": sorted(refs, key=lambda item: item["currency"]),
    }


def build_fx_precommit_chain_lab(
    records: Any, *, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Deterministically hash an in-memory set of unverified pre-event claims."""
    out = _blocked("INVALID_RECORD_SET_OR_EVALUATION_CLOCK")
    evaluated = _utc(evaluated_at_utc)
    if (evaluated is None or not isinstance(records, (list, tuple))
            or not 1 <= len(records) <= 10_000):
        return out
    previous = _ZERO_HASH
    prev_order: tuple[str, str] | None = None
    ids: set[str] = set()
    windows: dict[tuple[str, str], datetime] = {}
    entries: list[dict[str, Any]] = []
    emitted = 0
    for index, row in enumerate(records):
        canonical = _canonical_claim(row, evaluated)
        if isinstance(canonical, str):
            out["reason"] = canonical
            return out
        oid = canonical["opportunity_id"]
        if oid in ids:
            out["reason"] = "DUPLICATE_OPPORTUNITY_ID"
            return out
        ids.add(oid)
        issued = canonical["prediction_issued_at_claim"]
        order = (issued, oid)
        if prev_order is not None and order <= prev_order:
            out["reason"] = "NON_CHRONOLOGICAL_LEDGER_ORDER"
            return out
        prev_order = order
        key = (canonical["pair"], canonical["horizon"])
        start = _utc(row.outcome_start_at)
        end = _utc(row.outcome_end_at)
        if key in windows and start < windows[key]:
            out["reason"] = "OVERLAPPING_PAIR_HORIZON_OPPORTUNITIES"
            return out
        windows[key] = end

        payload = {"schema": SCHEMA, "sequence": index + 1,
                   "previous_sha256": previous, "forecast_claim": canonical}
        stable = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True).encode("utf-8")
        digest = sha256(stable).hexdigest()
        entries.append({"sequence": index + 1, "opportunity_id": oid,
                        "previous_sha256": previous, "entry_sha256_claim": digest})
        previous = digest
        emitted += row.side != "ABSTAIN"

    out.update({
        "state": "LAB_PRECOMMIT_LOCAL_HASH_CHAIN_CREATED_UNATTESTED",
        "reason": "CALLER_CAN_REWRITE_CHAIN_WITHOUT_EXTERNAL_TIMESTAMP_ANCHOR",
        "record_count": len(records), "caller_claim_only_emitted": emitted,
        "caller_claim_only_abstained": len(records) - emitted,
        "chain_entries": entries, "head_sha256_claim": previous,
        "local_hash_chain_self_consistent": True,
    })
    return out


def verify_fx_precommit_receipts_lab(
    records: Any, receipt_entries: Any, expected_head_sha256: Any,
    *, evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Detect changed claims *relative to* receipts preserved by the caller.

    A caller can fabricate records AND receipts. No timestamp is anchored here.
    """
    out = build_fx_precommit_chain_lab(records, evaluated_at_utc=evaluated_at_utc)
    if out["state"] == "LAB_PRECOMMIT_CHAIN_BLOCKED":
        return out
    if (not isinstance(receipt_entries, (list, tuple))
            or len(receipt_entries) != out["record_count"]
            or not _sha(expected_head_sha256)
            or any(type(x) is not dict for x in receipt_entries)
            or list(receipt_entries) != out["chain_entries"]
            or expected_head_sha256 != out["head_sha256_claim"]):
        return _blocked("CLAIMS_CHANGED_RELATIVE_TO_PROVIDED_RECEIPTS_OR_HEAD")
    out["state"] = "LAB_PRECOMMIT_RECEIPTS_LOCALLY_MATCH_UNATTESTED"
    out["reason"] = "RECEIPTS_MATCH_BUT_NEITHER_CREATION_TIME_NOR_SOURCE_ATTESTED"
    return out


__all__ = ["SCHEMA", "MacroVintageClaim", "ForecastPrecommitClaim",
           "build_fx_precommit_chain_lab", "verify_fx_precommit_receipts_lab"]
