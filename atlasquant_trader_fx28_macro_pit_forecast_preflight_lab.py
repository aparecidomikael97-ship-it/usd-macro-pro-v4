"""FX28 NY17 macro PIT -> prospective forecast preregistration preflight (LAB).

Connects the pre-existing eight-currency CPI/policy-rate *claims* to the
28-pair pre-event batch contract. Requires an exact 28-pair inventory.
Where either currency lacks valid as-of metadata or matching original local
bytes, a directional claim is rejected and an explicit ABSTAIN is required.

Matching SHA-256 only proves that *caller-supplied* original bytes match a
caller-supplied receipt; it does not authenticate an issuer or numeric data.
A complete locally reconciled batch is not a true market forecast, real
pre-event witness, signal, calibrated probability or live trading approval.
No network, broker, files, GitHub comment post or scheduling.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_macro_matrix_pit_lab import inspect_g8_macro_matrix_pit_lab
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import _nominal_windows
from atlasquant_trader_fx28_ny17_forecast_witness_lab import (
    PairForecastClaim, prepare_window_witness_body_lab,
)

SCHEMA = "ATLASQUANT_FX28_MACRO_PIT_PRE_EVENT_FORECAST_PREFLIGHT_LAB_V1"
REQUIRED = frozenset(("CPI_YOY", "POLICY_RATE"))
MAX_SOURCE_BYTES = 512_000
MAX_TOTAL_BYTES = 8_200_000
HEX = re.compile(r"[a-f0-9]{64}\Z")


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    try:
        return value.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_PIT_FORECAST_PREFLIGHT_BLOCKED",
        "reason": reason, "horizon": None, "window_start_utc": None,
        "window_end_utc": None, "forecast_claims_received": 0,
        "macro_metadata_claim_complete_pairs": 0,
        "macro_local_bytes_complete_pairs": 0,
        "macro_missing_or_unverifiable_pairs": 0,
        "directional_claims_research_only": 0,
        "explicit_abstentions": 0,
        "pair_diagnostics": {},
        "source_bytes_hash_matched_claims": 0,
        "source_bytes_mismatched_or_missing_claims": 0,
        "all_28_forecasts_locally_reconciled": False,
        "anchor_comment_body_unposted": None,
        "canonical_forecast_json_unposted": None,
        "forecast_roster_sha256_unposted": None,
        "original_issuer_bytes_authenticated": False,
        "publisher_first_release_timestamp_verified": False,
        "macro_point_in_time_independently_authenticated": False,
        "forecast_witnessed_before_session": False,
        "historical_pepperstone_prices_verified": False,
        "out_of_sample_accuracy_validated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR",
        "publishable": False, "live_alert_allowed": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False, "http_requests": 0,
        "file_writes": 0, "new_cost_brl": 0, "research_only": True,
    }


def inspect_fx28_macro_pit_forecast_preflight_lab(
    *, horizon: Any, window_start_at: Any, window_end_at: Any,
    feature_cutoff_at: Any, prepared_at: Any,
    receipts_by_currency: Any, raw_source_bytes_by_currency: Any,
    forecast_roster: Any,
) -> dict[str, Any]:
    """Prepare only a locally self-consistent, unattested pre-event cohort.

    The source bytes & receipt timestamps are claims; issuer verification
    must happen independently. Reject the WHOLE batch if even one of its 28
    forecasts tries to go directional without bilateral CPI + policy receipt
    chronology and local body hashes. Never silently drop that pair.
    """
    out = _blocked("INVALID_SESSION_CUTOFF_OR_FORECAST_ROSTER")
    cutoff, prepared, start, end = tuple(_utc(x) for x in (
        feature_cutoff_at, prepared_at, window_start_at, window_end_at))
    if (horizon not in ("D1", "W1")
            or any(x is None for x in (cutoff, prepared, start, end))
            or not cutoff <= prepared < start
            or (start, end) not in _nominal_windows(horizon)
            or not isinstance(forecast_roster, tuple)
            or len(forecast_roster) != 28
            or not isinstance(receipts_by_currency, dict)
            or set(receipts_by_currency) != set(CURRENCIES)
            or not isinstance(raw_source_bytes_by_currency, dict)
            or set(raw_source_bytes_by_currency) != set(CURRENCIES)
            or len(OFFICIAL_PAIRS) != 28):
        return out

    by_pair: dict[str, PairForecastClaim] = {}
    for row in forecast_roster:
        if (not isinstance(row, PairForecastClaim)
                or row.pair not in OFFICIAL_PAIRS or row.pair in by_pair
                or _utc(row.feature_cutoff_at) != cutoff
                or _utc(row.forecast_issued_at) is None
                or not cutoff <= _utc(row.forecast_issued_at) <= prepared):
            out["reason"] = "FORECAST_INCOMPLETE_DUPLICATE_OR_NOT_AT_SHARED_PIT_CUTOFF"
            return out
        by_pair[row.pair] = row
    if set(by_pair) != set(OFFICIAL_PAIRS):
        out["reason"] = "FORECAST_NOT_EXACTLY_ALL_28_CANONICAL_PAIRS"
        return out

    matched = 0
    mismatched = 0
    byte_ready: dict[str, bool] = {}
    total_size = 0
    for currency in CURRENCIES:
        records = receipts_by_currency[currency]
        source_bodies = raw_source_bytes_by_currency[currency]
        if (not isinstance(records, list) or len(records) > 12
                or not isinstance(source_bodies, dict)
                or not set(source_bodies) <= REQUIRED):
            out["reason"] = "INVALID_CURRENCY_RECEIPT_OR_BODY_ENVELOPE"
            return out
        by_indicator: dict[str, dict[str, Any]] = {}
        ambiguous: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                out["reason"] = "INVALID_CURRENCY_RECEIPT_TYPE"
                return out
            indicator = record.get("indicator")
            if not isinstance(indicator, str) or indicator not in REQUIRED:
                out["reason"] = "UNSUPPORTED_CURRENCY_INDICATOR"
                return out
            if indicator in by_indicator:
                ambiguous.add(indicator)
            by_indicator[indicator] = record
        local = True
        for indicator in REQUIRED:
            raw = source_bodies.get(indicator)
            if raw is not None:
                if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_SOURCE_BYTES:
                    out["reason"] = "INVALID_OR_OVERSIZED_ORIGINAL_MACRO_BYTES"
                    return out
                total_size += len(raw)
                if total_size > MAX_TOTAL_BYTES:
                    out["reason"] = "TOTAL_ORIGINAL_MACRO_BYTES_LIMIT_EXCEEDED"
                    return out
            rec = by_indicator.get(indicator)
            sha_claim = rec.get("source_sha256") if rec else None
            check = (raw is not None and indicator not in ambiguous
                     and isinstance(sha_claim, str)
                     and HEX.fullmatch(sha_claim) is not None
                     and sha256(raw).hexdigest() == sha_claim)
            matched += int(bool(check))
            mismatched += int(not check)
            local = local and bool(check)
        byte_ready[currency] = local

    macro = inspect_g8_macro_matrix_pit_lab(
        receipts_by_currency, horizon=horizon,
        decision_at_utc=cutoff, evaluated_at_utc=prepared)
    if (macro.get("schema") != "ATLASQUANT_TRADER_G8_MACRO_MATRIX_PIT_LAB_V1"
            or macro.get("state") == "LAB_BLOCKED"
            or macro.get("horizon") != horizon
            or macro.get("pair_count") != 28
            or set(macro.get("pairs", {})) != set(OFFICIAL_PAIRS)):
        out["reason"] = "G8_PIT_MACRO_MATRIX_REJECTED_OR_INCOMPLETE_SCHEMA"
        return out

    diagnostics = {}
    claim_complete = local_complete = missing_pairs = directional = abstained = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        p = macro["pairs"][pair]
        status = p.get("metadata_claim_state")
        metadata_complete = status == "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED"
        local_complete_for_pair = metadata_complete and byte_ready[base] and byte_ready[quote]
        claim_complete += int(metadata_complete)
        local_complete += int(local_complete_for_pair)
        missing_pairs += int(not local_complete_for_pair)
        forecast = by_pair[pair]
        if forecast.direction not in ("UP", "DOWN", "ABSTAIN"):
            out["reason"] = "INVALID_FORECAST_DIRECTION"
            return out
        if local_complete_for_pair:
            if forecast.direction == "ABSTAIN" and forecast.abstain_reason in (
                    "MISSING_MACRO", "UNVERIFIED_SOURCE"):
                out["reason"] = "MISLEADING_MISSING_MACRO_REASON_FOR_COMPLETE_LOCAL_PAIR"
                return out
        else:
            required_reason = ("MISSING_MACRO" if status in (
                "NO_RECEIPTS_FOR_EITHER_CURRENCY",
                "LAB_PAIR_MACRO_METADATA_INCOMPLETE_UNATTESTED",
            ) else "UNVERIFIED_SOURCE")
            if (forecast.direction != "ABSTAIN"
                    or forecast.abstain_reason != required_reason):
                out["reason"] = "UNSUPPORTED_DIRECTION_OR_WRONG_MISSING_MACRO_REASON"
                return out
        directional += int(forecast.direction != "ABSTAIN")
        abstained += int(forecast.direction == "ABSTAIN")
        diagnostics[pair] = {
            "local_macro_metadata_claim_complete": metadata_complete,
            "two_currency_original_bytes_match_local_receipt_hashes":
                local_complete_for_pair,
            "missing_or_stale_claims": list(p.get("missing_or_stale", [])),
            "macro_pair_rejection_reason": p.get("rejection_reason"),
            "forecast_direction_unattested": forecast.direction,
            "abstain_reason": forecast.abstain_reason,
            "research_only_not_live": True,
        }

    ordered = tuple(by_pair[p] for p in OFFICIAL_PAIRS)
    prepared_witness = prepare_window_witness_body_lab(
        horizon=horizon, start_at=start, end_at=end,
        forecast_roster=ordered, prepared_at=prepared)
    if prepared_witness.get("state") != "LAB_WITNESS_BODY_PREPARED_NOT_POSTED":
        out["reason"] = "PROSPECTIVE_PRECOMMIT_CONTRACT_REJECTED"
        return out

    out.update({
        "state": "LAB_MACRO_PIT_28FX_FORECAST_RESEARCH_ONLY_UNATTESTED",
        "reason": "LOCAL_BYTES_NOT_ISSUER_AUTHENTICATION_OR_FORECAST_ACCURACY",
        "horizon": horizon, "window_start_utc": start.isoformat(),
        "window_end_utc": end.isoformat(),
        "forecast_claims_received": 28,
        "macro_metadata_claim_complete_pairs": claim_complete,
        "macro_local_bytes_complete_pairs": local_complete,
        "macro_missing_or_unverifiable_pairs": missing_pairs,
        "directional_claims_research_only": directional,
        "explicit_abstentions": abstained,
        "pair_diagnostics": diagnostics,
        "source_bytes_hash_matched_claims": matched,
        "source_bytes_mismatched_or_missing_claims": mismatched,
        "all_28_forecasts_locally_reconciled": True,
        "anchor_comment_body_unposted": prepared_witness["body"],
        "canonical_forecast_json_unposted": prepared_witness["canonical_forecast_json"],
        "forecast_roster_sha256_unposted":
            prepared_witness["forecast_roster_sha256"],
    })
    return out


__all__ = ("SCHEMA", "inspect_fx28_macro_pit_forecast_preflight_lab")
