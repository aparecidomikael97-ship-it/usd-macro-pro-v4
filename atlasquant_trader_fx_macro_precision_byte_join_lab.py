"""Offline join: G8 as-of macro receipt matrix + actual caller-supplied bytes + FX Precision Gate.

This is a structural custody audit, NOT official data authentication. Matching
SHA-256 protects local bytes from mismatched receipt claims but cannot prove
issuer identity, first publication, content interpretation or forecast skill.
Missing data must never be silently filled from historical hindsight.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair
from atlasquant_trader_g8_macro_matrix_pit_lab import inspect_g8_macro_matrix_pit_lab
from atlasquant_trader_precision_gate_orchestrator_lab import (
    ResearchPacket, inspect_fx_precision_orchestrator_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX_G8_MACRO_BYTES_PRECISION_JOIN_LAB_V1"
REQUIRED_INDICATORS = frozenset({"CPI_YOY", "POLICY_RATE"})
MACRO_PAIR_READY = "LAB_PAIR_MACRO_METADATA_COMPLETE_UNATTESTED"
PRECISION_RESEARCH_ONLY = "LAB_PRECISION_RESEARCH_CANDIDATE_UNATTESTED"
MAX_SOURCE_BODY_BYTES = 2_000_000
MAX_ALL_BODY_BYTES = 16_000_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_PRECISION_JOIN_BLOCKED",
        "reason": reason, "asset": None,
        "source_body_hashes_matched_local": 0,
        "source_body_hashes_supplied": 0,
        "currencies_locally_byte_bound": 0,
        "currency_byte_binding": {},
        "d1_macro_claim_complete_pairs": 0,
        "w1_macro_claim_complete_pairs": 0,
        "pairs_locally_byte_bound_both_sides": 0,
        "pair_count": 0, "pair_rows": {},
        "precision_stage_reports": {}, "precision_blocking_stages": [],
        "precision_research_candidate_without_macro": False,
        "research_candidate_direction": None,
        "official_publisher_bytes_authenticated": False,
        "source_tls_and_release_time_independently_verified": False,
        "economic_values_extracted_and_reconciled_to_body": False,
        "economic_measurements_and_policy_instruments_harmonized": False,
        "historical_point_in_time_independently_verified": False,
        "macroeconomic_direction_established": False,
        "predictive_accuracy_validated": None,
        "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "trade_authorized": False,
        "live_alert_allowed": False, "publishable": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def inspect_fx_macro_precision_bytes_lab(
    *, packet: Any,
    receipts_by_currency: Any,
    original_source_bytes_by_currency: Any,
    inspected_at_utc: Any,
) -> dict[str, Any]:
    """Re-run two G8 PIT matrices and seven precision guards; bind raw source bytes.

    Each currency/indicator currently accepts just ONE asserted receipt vintage.
    If FLASH and FINAL coexist, caller must first prepare a documented vintage
    selection at each cutoff; this function refuses to guess. Body matching
    does not verify that the *numeric value* is actually printed in the body.
    """
    now = _utc(inspected_at_utc)
    if not isinstance(packet, ResearchPacket) or now is None:
        return _blocked("INVALID_PRECISION_PACKET_OR_INSPECTION_CLOCK")
    candidate = getattr(packet, "candidate", None)
    asset = getattr(candidate, "asset", None)
    day = _utc(packet.daily_decision_at_utc)
    week = _utc(packet.weekly_decision_at_utc)
    issued = _utc(getattr(candidate, "evaluated_at", None))
    if (asset not in OFFICIAL_PAIRS or day is None or week is None or issued is None
            or not week <= day <= issued <= now
            or not isinstance(receipts_by_currency, dict)
            or not isinstance(original_source_bytes_by_currency, dict)
            or set(receipts_by_currency) != set(CURRENCIES)
            or set(original_source_bytes_by_currency) != set(CURRENCIES)):
        return _blocked("INVALID_G8_UNIVERSE_OR_DECISION_CUTOFF")

    # Reject malformed envelope, extra sources and total memory abuse upfront.
    size = 0
    submitted = matched = 0
    byte_checks: dict[str, dict[str, Any]] = {}
    for currency in CURRENCIES:
        rows = receipts_by_currency[currency]
        originals = original_source_bytes_by_currency[currency]
        if (not isinstance(rows, list) or len(rows) > 12
                or not isinstance(originals, dict)
                or not set(originals).issubset(REQUIRED_INDICATORS)):
            return _blocked("INVALID_SOURCE_BUNDLE_SCHEMA_OR_CURRENCY")
        for body in originals.values():
            if not isinstance(body, bytes) or not 0 < len(body) <= MAX_SOURCE_BODY_BYTES:
                return _blocked("INVALID_OR_OVERSIZED_ORIGINAL_BYTES")
            size += len(body)
            submitted += 1
            if size > MAX_ALL_BODY_BYTES:
                return _blocked("TOTAL_SOURCE_BYTES_LIMIT_EXCEEDED")

        indicators: dict[str, dict[str, Any]] = {}
        failure: str | None = None
        for row in rows:
            if not isinstance(row, dict) or row.get("currency") != currency:
                failure = "RECORD_CURRENCY_OWNER_OR_SCHEMA_INVALID"
                break
            indicator = row.get("indicator")
            if not isinstance(indicator, str) or indicator not in REQUIRED_INDICATORS:
                failure = "UNEXPECTED_INDICATOR_OR_RECORD"
                break
            if indicator in indicators:
                failure = "MULTIPLE_VINTAGES_UNRESOLVED"
                break
            indicators[indicator] = row
        if failure is None and set(indicators) != REQUIRED_INDICATORS:
            failure = "MISSING_CPI_OR_POLICY_RECORD"
        if failure is None and set(originals) != REQUIRED_INDICATORS:
            failure = "MISSING_CPI_OR_POLICY_SOURCE_BYTES"
        if failure is None:
            for indicator in sorted(REQUIRED_INDICATORS):
                raw = originals[indicator]
                digest = indicators[indicator].get("source_sha256")
                if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
                    failure = "MISSING_OR_INVALID_DECLARED_SOURCE_SHA256"
                    break
                if sha256(raw).hexdigest() != digest:
                    failure = "ORIGINAL_BYTES_HASH_MISMATCH"
                    break
                matched += 1
        byte_checks[currency] = {
            "state": "LAB_LOCAL_BYTES_MATCH_CLAIMS_UNATTESTED" if failure is None else "LAB_CURRENCY_BYTES_BLOCKED",
            "reason": failure or "NUMERIC_READING_NOT_EXTRACTED_OR_SOURCE_AUTHENTICATED",
            "local_source_bytes_bound": failure is None,
            "body_fields_claimed": len(originals),
        }

    try:
        daily = inspect_g8_macro_matrix_pit_lab(
            receipts_by_currency, horizon="D1",
            decision_at_utc=day, evaluated_at_utc=now)
        weekly = inspect_g8_macro_matrix_pit_lab(
            receipts_by_currency, horizon="W1",
            decision_at_utc=week, evaluated_at_utc=now)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return _blocked("MACRO_MATRIX_EXCEPTION_BLOCKED")
    if (daily.get("pair_count") != 28 or weekly.get("pair_count") != 28
            or set(daily.get("pairs", {})) != set(OFFICIAL_PAIRS)
            or set(weekly.get("pairs", {})) != set(OFFICIAL_PAIRS)):
        return _blocked("INCOMPLETE_OR_INVALID_G8_ASOF_MACRO_MATRICES")

    # Existing seven-stage gate re-runs independent structural checks, including
    # D1/W1 synthetic agreement, evidence roots and M15 costs. Passing here
    # cannot validate the original currencies' quantitative strength.
    try:
        precision = inspect_fx_precision_orchestrator_lab(
            packet=packet, inspected_at_utc=now)
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return _blocked("PRECISION_ORCHESTRATOR_EXCEPTION_BLOCKED")

    pair_rows = {}
    dcount = wcount = both_count = 0
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        d = daily["pairs"][pair]
        w = weekly["pairs"][pair]
        d_ok = d.get("metadata_claim_state") == MACRO_PAIR_READY
        w_ok = w.get("metadata_claim_state") == MACRO_PAIR_READY
        b_ok = byte_checks[base]["local_source_bytes_bound"] and byte_checks[quote]["local_source_bytes_bound"]
        dcount += int(d_ok)
        wcount += int(w_ok)
        both_count += int(b_ok)
        waiting = []
        if not d_ok:
            waiting.append("DAILY_CPI_POLICY_METADATA_INCOMPLETE_OR_INVALID")
        if not w_ok:
            waiting.append("WEEKLY_CPI_POLICY_METADATA_INCOMPLETE_OR_INVALID")
        if not byte_checks[base]["local_source_bytes_bound"]:
            waiting.append(f"{base}_ORIGINAL_BYTES_MISSING_OR_MISMATCHED")
        if not byte_checks[quote]["local_source_bytes_bound"]:
            waiting.append(f"{quote}_ORIGINAL_BYTES_MISSING_OR_MISMATCHED")
        pair_rows[pair] = {
            "state": "LAB_PAIR_MACRO_BYTES_LOCALLY_BOUND_UNATTESTED" if not waiting else "LAB_PAIR_MACRO_WAIT_EVIDENCE",
            "d1_receipt_metadata_claim_complete": d_ok,
            "w1_receipt_metadata_claim_complete": w_ok,
            "both_currency_source_bytes_hash_match": b_ok,
            "blocking_reasons": waiting,
            "operational_bias": "AGUARDAR",
        }

    passing_precision = (precision.get("state") == PRECISION_RESEARCH_ONLY
                         and precision.get("research_candidate_direction")
                         == getattr(candidate, "daily", None))
    macro_ready = pair_rows[asset]["state"] == "LAB_PAIR_MACRO_BYTES_LOCALLY_BOUND_UNATTESTED"
    eligible = macro_ready and passing_precision
    out = _blocked("MACRO_SOURCE_CLAIMS_AND_PRECISION_NEVER_ATTEST_OR_AUTHORIZE")
    out.update({
        "state": ("LAB_BYTES_BOUND_MACRO_PRECISION_RESEARCH_CANDIDATE_UNATTESTED" if eligible
                  else "LAB_MACRO_PRECISION_ABSTAIN"),
        "reason": ("LOCAL_SOURCE_BYTES_MATCH_BUT_ISSUER_OR_VALUES_UNATTESTED" if eligible
                   else "MACRO_RECEIPT_OR_SOURCE_BYTES_OR_PRECISION_GATE_BLOCKED"),
        "asset": asset,
        "source_body_hashes_supplied": submitted,
        "source_body_hashes_matched_local": matched,
        "currencies_locally_byte_bound": sum(x["local_source_bytes_bound"] for x in byte_checks.values()),
        "currency_byte_binding": byte_checks,
        "d1_macro_claim_complete_pairs": dcount,
        "w1_macro_claim_complete_pairs": wcount,
        "pairs_locally_byte_bound_both_sides": both_count,
        "pair_count": len(pair_rows), "pair_rows": pair_rows,
        "precision_stage_reports": precision.get("stage_reports", {}),
        "precision_blocking_stages": precision.get("blocking_stages", []),
        "precision_research_candidate_without_macro": passing_precision,
        "research_candidate_direction": (getattr(candidate, "daily", None) if eligible else None),
    })
    return out


__all__ = ("SCHEMA", "inspect_fx_macro_precision_bytes_lab")