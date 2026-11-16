"""One compact truthful FX28 Motor A readiness readout from REAL local modules.

Consolidates the existing eight-issuer original-byte archive replay, 32-factor
source admission, and 672-slot prospective accounting into a simple readout.
This does NOT make any economic directional forecast or claim independent
issuer/first-seen/broker authentication. Raw rate levels and paths are never
returned. On malformed/incoherent reports the WHOLE panel stays blocked.

A caller-supplied empty witness set means no witness was supplied to THIS
process, never that GitHub contains no forecasts. There is no GitHub read
here. No network, orders, MT5, file writes, scheduler, alerts or deployment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import os
import json
import argparse
from typing import Any

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_fx28_policy_local_archive_replay_lab import (
    SCHEMA as POLICY_SCHEMA,
    inspect_fx28_official_policy_archive_replay_lab,
)
from atlasquant_trader_fx28_32_factor_source_admission_lab import (
    SCHEMA as FACTOR_SCHEMA,
    inspect_fx28_32_factor_source_admission_lab,
)
from atlasquant_trader_us_ppi_sep2026_two_real_vintages_lab import (
    SEP_HASH as PPI_SEP_ORIGINAL_SHA,
    OCT_HASH as PPI_OCT_ORIGINAL_SHA,
)
from atlasquant_trader_fx28_ny17_672_slot_issuance_ledger_lab import (
    SCHEMA as LEDGER_SCHEMA,
    inspect_fx28_ny17_672_slot_issuance_ledger_lab,
)
from atlasquant_trader_fx28_ny17_prospective_campaign_lab import (
    FROZEN_START_UTC, EXPECTED_PAIR_HORIZON_SLOTS, _nominal_windows,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_SINGLE_READINESS_PANEL_LAB_V1"
# A deliberately conservative CURRENT LOCAL-CAPTURE claim threshold, not
# release-time authenticity, source correctness, or economic-policy freshness.
LOCAL_CAPTURE_RECENCY = timedelta(hours=24)
_RECEIPT_STAMP = re.compile(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_POLICY_STATES = frozenset((
    "LAB_FX28_POLICY_ARCHIVE_EIGHT_ORIGINALS_LOCAL_ONLY_NO_GO",
    "LAB_FX28_POLICY_ARCHIVE_PARTIAL_OR_REJECTED_NO_GO",
))
_SOURCE_URLS = {
    "CHF": "https://www.snb.ch/en/srv/current_interest_exchange_rates",
    "JPY": "https://www.boj.or.jp/en/",
    "NZD": "https://www.rbnz.govt.nz/monetary-policy/about-monetary-policy/the-official-cash-rate",
}


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _local_receipt_age_status(
    *, checked_currencies: list[str], archive_status: Any,
    inspected_at_utc: datetime,
) -> tuple[dict[str, str], list[str], list[str], list[str]] | None:
    """Classify local capture-clock CLAIMS, not issuer first-published time.

    The upstream file replay must already have SHA, filename, receipt shape
    and issuer parser consistency. Missing metadata is UNKNOWN, never recent.
    A claimed timestamp from the future or malformed present metadata is
    an inconsistency and blocks the combined panel.
    """
    if type(archive_status) is not dict:
        return None
    rows: dict[str, str] = {}
    recent: list[str] = []
    stale: list[str] = []
    unknown: list[str] = []
    for currency in sorted(checked_currencies):
        record = archive_status.get(currency)
        if record is None:
            rows[currency] = "LOCAL_RECEIPT_CLOCK_UNKNOWN_NOT_FRESH"
            unknown.append(currency)
            continue
        if type(record) is not dict:
            return None
        stamp = record.get("selected_local_capture_utc_claim")
        if stamp is None:
            rows[currency] = "LOCAL_RECEIPT_CLOCK_UNKNOWN_NOT_FRESH"
            unknown.append(currency)
            continue
        if type(stamp) is not str or _RECEIPT_STAMP.fullmatch(stamp) is None:
            return None
        try:
            captured = datetime.strptime(
                stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        age = inspected_at_utc - captured
        if age < timedelta(0):
            return None
        if age <= LOCAL_CAPTURE_RECENCY:
            rows[currency] = "RECENT_24H_LOCAL_RECEIPT_CLAIM_NOT_ISSUER_VINTAGE"
            recent.append(currency)
        else:
            rows[currency] = "STALE_OVER_24H_LOCAL_RECEIPT_CLAIM"
            stale.append(currency)
    return rows, recent, stale, unknown


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_SINGLE_READINESS_PANEL_BLOCKED_NO_GO",
        "reason": reason,
        "issuer_policy_document_count": 0,
        "issuer_policy_currencies_locally_checked": [],
        "issuer_policy_missing_currencies": [],
        "issuer_policy_rejected_currencies": [],
        "pairs_with_both_policy_documents": 0,
        "pairs_lacking_policy_document": 28,
        "missing_issuer_reference_urls": {},
        "local_capture_age_threshold_hours": 24,
        "recent_24h_local_receipt_claim_currencies": [],
        "stale_over_24h_local_receipt_claim_currencies": [],
        "unknown_local_receipt_clock_currencies": [],
        "recent_24h_local_receipt_claim_count": 0,
        "recent_24h_bilateral_policy_pair_count": 0,
        "local_document_capture_age_status_by_currency": {},
        "capture_recency_is_not_rate_freshness_or_issuer_first_seen": True,
        "stale_policy_document_is_still_documentary_not_current": True,
        "factors_expected": 32,
        "factors_with_any_relevant_local_document": 0,
        "ppi_original_local_replayed_for_context": False,
        "cpi_original_local_replayed_for_context": False,
        "ppi_cpi_documents_are_not_signed_usd_impacts": True,
        "ppi_sep2026_vintage_input_requested": False,
        "ppi_sep2026_locally_verified_original_count": 0,
        "ppi_sep2026_revision_documentary_summary": None,
        "ppi_sep2026_revision_available_to_oct15_model": False,
        "ppi_sep2026_revision_is_not_signed_fx_impact": True,
        "factors_with_independently_accepted_signed_effect": 0,
        "factors_with_independent_pre_event_consensus": 0,
        "factors_with_calibrated_directional_effect": 0,
        "slots_expected": EXPECTED_PAIR_HORIZON_SLOTS,
        "slots_accounted": 0,
        "slots_future_no_supplied_witness": 0,
        "slots_past_no_supplied_witness": 0,
        "slots_with_unattested_witness": 0,
        "next_frozen_start_utc": None,
        "first_frozen_start_utc": FROZEN_START_UTC.isoformat(),
        "source_page_link_is_not_source_byte_capture": True,
        "policy_rate_is_not_policy_expectation": True,
        "document_count_is_not_signed_forecast_count": True,
        "empty_witness_input_does_not_prove_external_absence": True,
        "witnesses_independently_authenticated": False,
        "issuer_identity_and_first_seen_independently_authenticated": False,
        "broker_m15_independently_authenticated": False,
        "model_direction_calibrated": False,
        "validated_fx28_accuracy": None,
        "calibrated_probability": None,
        "directional_bias": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "http_requests": 0,
        "file_writes": 0,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "new_cost_brl": 0,
        "research_only": True,
    }


def inspect_fx28_single_readiness_panel_lab(
    *, local_appdata: Any, inspected_at_utc: Any,
    ppi_archive_basename: Any = None, cpi_archive_basename: Any = None,
    ppi_sep2026_two_vintage_originals: Any = None,
) -> dict[str, Any]:
    """Read only local originals, then reconcile coverage and future slots.

    No accepted user-supplied "GO" flag. The ledger receives an empty
    witness set on purpose, and its missing statuses mean ONLY no witness
    was supplied to this execution; GitHub is not inspected here.
    """
    out = _base("INVALID_LOCAL_ROOT_CLOCK_OR_FROZEN_SCOPE")
    now = _utc(inspected_at_utc)
    if (now is None or not isinstance(local_appdata, str)
            or not local_appdata
            or type(ppi_archive_basename) not in (str, type(None))
            or ppi_archive_basename == ""
            or type(cpi_archive_basename) not in (str, type(None))
            or cpi_archive_basename == ""
            or (ppi_sep2026_two_vintage_originals is not None
                and (type(ppi_sep2026_two_vintage_originals) is not tuple
                     or len(ppi_sep2026_two_vintage_originals) != 2
                     or any(type(blob) is not bytes
                            or not 100_000 <= len(blob) <= 4_194_304
                            for blob in ppi_sep2026_two_vintage_originals)))
            or len(OFFICIAL_PAIRS) != 28
            or len(CURRENCIES) != 8
            or EXPECTED_PAIR_HORIZON_SLOTS != 672):
        return out
    try:
        policy = inspect_fx28_official_policy_archive_replay_lab(
            local_appdata=local_appdata, decision_at_utc=now)
        factors = inspect_fx28_32_factor_source_admission_lab(
            local_appdata=local_appdata, decision_at_utc=now,
            ppi_archive_basename=ppi_archive_basename,
            cpi_archive_basename=cpi_archive_basename,
            hypothetical_factors=None,
            ppi_sep2026_two_vintage_originals=ppi_sep2026_two_vintage_originals)
        ledger = inspect_fx28_ny17_672_slot_issuance_ledger_lab(
            window_claims=(), inspected_at_utc=now)
    except (OSError, TypeError, ValueError, KeyError, RuntimeError,
            OverflowError, RecursionError):
        out["reason"] = "LOCAL_SOURCE_OR_LEDGER_READER_EXCEPTION"
        return out
    if (type(policy) is not dict or policy.get("schema") != POLICY_SCHEMA
            or policy.get("state") not in _POLICY_STATES
            or policy.get("trade_authorized") is not False
            or policy.get("publishable") is not False
            or policy.get("operational_bias") != "AGUARDAR"
            or policy.get("source_current_issuer_identity_independently_verified")
                is not False
            or policy.get("historical_point_in_time_vintage_verified")
                is not False):
        out["reason"] = "POLICY_ARCHIVE_NOT_ADMISSIBLE_AS_DOCUMENTARY_REPORT"
        return out
    accepted = policy.get("currencies_locally_checked")
    missing = policy.get("currencies_missing")
    rejected = policy.get("currencies_rejected")
    pair_count = policy.get("pairs_with_both_policy_originals_locally_checked")
    if (type(accepted) is not list or type(missing) is not list
            or type(rejected) is not dict
            or not all(type(x) is str for x in accepted + missing)
            or len(set(accepted)) != len(accepted)
            or len(set(missing)) != len(missing)
            or any(type(k) is not str for k in rejected)
            or (set(accepted) | set(missing) | set(rejected))
               != set(CURRENCIES)
            or (set(accepted) & set(missing)
                or set(accepted) & set(rejected)
                or set(missing) & set(rejected))
            or type(pair_count) is not int
            or pair_count != len(accepted) * (len(accepted) - 1) // 2
            or policy.get("currencies_with_local_original_bytes_validated")
               != len(accepted)
            or policy.get("pairs_lacking_at_least_one_policy_original")
               != 28 - pair_count):
        out["reason"] = "POLICY_CURRENCY_SET_OR_PAIR_COVERAGE_INCOHERENT"
        return out
    # Do not present an old local HTML/CSV screenshot as CURRENT source
    # just because the issuer parser accepted its content months ago.
    # Sources may be old yet remain valid documentary historical context.
    aged = _local_receipt_age_status(
        checked_currencies=accepted,
        archive_status=policy.get("currency_archive_status"),
        inspected_at_utc=now,
    )
    if aged is None:
        out["reason"] = "POLICY_LOCAL_CAPTURE_RECEIPT_CLOCK_INCONSISTENT"
        return out
    age_rows, recent, stale, unknown = aged

    if (type(factors) is not dict or factors.get("schema") != FACTOR_SCHEMA
            or factors.get("state")
                != "LAB_FX28_32_FACTOR_DOCUMENTARY_GAP_RECONCILED_NO_GO"
            or factors.get("source_audit_state")
                != "LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO"
            or factors.get("locally_replayed_policy_issuer_count")
                != len(accepted)
            or factors.get("locally_replayed_ppi_document_count")
               != int(ppi_archive_basename is not None)
            or factors.get("locally_replayed_cpi_u_nsa_document_count")
               != int(cpi_archive_basename is not None)
            or factors.get("factor_slots_inspected") != 32
            or factors.get("factor_slots_with_any_relevant_local_document")
               != (len(accepted) + int(
                   ppi_archive_basename is not None
                   or cpi_archive_basename is not None))
            or factors.get("factor_slots_with_signed_impact_independently_admissible")
                != 0
            or factors.get("factor_slots_with_pre_event_consensus_verified") != 0
            or factors.get("factor_slots_with_calibrated_directional_effect") != 0
            or factors.get("real_directional_forecast_authorized") is not False
            or factors.get("calibrated_probability") is not None
            or factors.get("trade_authorized") is not False
            or factors.get("operational_bias") != "AGUARDAR"):
        out["reason"] = "FACTORS_DISAGREE_WITH_REAL_LOCAL_POLICY_SOURCE_COVERAGE"
        return out
    # Source-backed revision proof MUST be reconciled in the same reader
    # as the 32-factor admission. Displaying a caller-written "PASS" would
    # silently make revised values appear historically available.
    revision_requested = ppi_sep2026_two_vintage_originals is not None
    verified_revision_count = factors.get(
        "ppi_sep2026_verified_original_count_at_local_cutoff")
    revision_present = factors.get(
        "ppi_sep2026_first_release_and_revision_reconciled_local_only")
    vintage = factors.get("ppi_sep2026_vintage_research_context")
    if (factors.get("ppi_sep2026_vintage_context_requested")
            is not revision_requested
            or type(verified_revision_count) is not int
            or verified_revision_count not in (0, 1, 2)
            or type(revision_present) is not bool
            or factors.get("ppi_sep2026_vintage_context_in_usd_inflation_slot_only")
               is not True
            or factors.get("ppi_sep2026_vintage_context_is_not_new_signed_impact")
               is not True
            or factors.get("ppi_sep2026_revision_never_backfilled_to_october_decision")
               is not True
            or (not revision_requested
                and (verified_revision_count != 0
                     or revision_present or vintage is not None))
            or (revision_requested and
                ((revision_present and verified_revision_count != 2)
                 or (not revision_present and
                     (verified_revision_count == 2 or vintage is not None))))):
        out["reason"] = "PPI_VINTAGE_FACTOR_STATUS_OR_PIT_CONTEXT_INCOHERENT"
        return out
    summary = None
    if revision_present:
        if (type(vintage) is not dict
                or vintage.get("currency") != "USD"
                or vintage.get("reference_period") != "2026-09"
                or vintage.get("measure") != "MOM_SA_PERCENT_CHANGE"
                or vintage.get("headline_series_code") != "FD/4"
                or vintage.get("core_ex_food_energy_series_code") != "FD/49104"
                or vintage.get("both_documents_first_seen_by_local_lab_after_their_release")
                   is not True
                or vintage.get("backtest_as_if_2026_10_15_known") is not False
                or vintage.get("can_derive_signed_inflation_impact") is not False
                or vintage.get("headline_revision_percentage_points") != "0.1"
                or vintage.get("core_revision_percentage_points") != "0.1"):
            out["reason"] = "PPI_VINTAGE_DOCUMENTARY_CONTEXT_MALFORMED"
            return out
        initial, revised = vintage.get("initial_release"), vintage.get("later_release_revision")
        if (type(initial) is not dict or type(revised) is not dict
                or initial.get("release_date") != "2026-10-15"
                or revised.get("release_date") != "2026-11-13"
                or tuple(initial.get(k) for k in ("headline_pct", "core_ex_food_energy_pct",
                                                 "original_html_sha256"))
                   != ("1.3", "0.7", PPI_SEP_ORIGINAL_SHA)
                or tuple(revised.get(k) for k in ("headline_pct", "core_ex_food_energy_pct",
                                                 "original_html_sha256"))
                   != ("1.4", "0.8", PPI_OCT_ORIGINAL_SHA)):
            out["reason"] = "PPI_VINTAGE_REPORT_EDITION_OR_SHA_CHANGED"
            return out
        factor_slots = factors.get("factor_slots")
        if (type(factor_slots) is not list or len(factor_slots) != 32
                or any(type(slot) is not dict for slot in factor_slots)):
            out["reason"] = "PPI_VINTAGE_FACTOR_SLOT_ROSTER_INVALID"
            return out
        attached = [slot for slot in factor_slots
                    if slot.get("ppi_sep2026_historical_two_release_revision_context")
                       is not None]
        if (len(attached) != 1
                or attached[0].get("currency") != "USD"
                or attached[0].get("category") != "inflation_impact"
                or attached[0].get("ppi_sep2026_historical_two_release_revision_context")
                   != vintage
                or attached[0].get("signed_impact_points_admitted") is not None):
            out["reason"] = "PPI_VINTAGE_ATTACHED_TO_WRONG_FACTOR_OR_DUPLICATED"
            return out
        # A compact factual diagnostic with separate dates; no source HTML,
        # issuer-access claim, ticker signal, confidence or live advice.
        summary = {
            "reference_period": "2026-09",
            "currency": "USD",
            "unit": "PERCENT_CHANGE_MOM_SA",
            "initial_release_date": "2026-10-15",
            "initial_headline_pct": "1.3",
            "initial_core_ex_food_energy_pct": "0.7",
            "revised_release_date": "2026-11-13",
            "revised_headline_pct": "1.4",
            "revised_core_ex_food_energy_pct": "0.8",
            "headline_revision_percentage_points": "0.1",
            "core_revision_percentage_points": "0.1",
            "original_source_sha256_pair": [
                PPI_SEP_ORIGINAL_SHA, PPI_OCT_ORIGINAL_SHA,
            ],
            "first_seen_by_model_on_original_release_date_authenticated": False,
            "research_only_postrelease_local_capture": True,
            "contributes_calibrated_signed_macro_impact": False,
        }
    elif revision_requested:
        # With a partial window (0/1 evidence) the panel intentionally
        # reports NO revised numerical value, rather than showing 1.4 too
        # early or claiming that mere elapsed time validates an original.
        factor_slots = factors.get("factor_slots")
        if (type(factor_slots) is not list or len(factor_slots) != 32
                or any(type(slot) is not dict or
                       slot.get("ppi_sep2026_historical_two_release_revision_context")
                       is not None for slot in factor_slots)):
            out["reason"] = "PPI_VINTAGE_PREMATURE_FACTOR_SLOT_EXPOSURE"
            return out
    if (type(ledger) is not dict or ledger.get("schema") != LEDGER_SCHEMA
            or ledger.get("state")
                != "LAB_FX28_672_SLOTS_ACCOUNTED_UNATTESTED_NO_GO"
            or ledger.get("slots_accounted") != 672
            or ledger.get("independently_authenticated_forecasts") != 0
            or ledger.get("absence_of_github_witness_independently_verified")
                is not False
            or ledger.get("github_comments_fetched") is not False
            or ledger.get("trade_authorized") is not False
            or ledger.get("operational_bias") != "AGUARDAR"
            or (ledger.get("slots_future_no_supplied_witness") is not None
                and ledger.get("slots_future_no_supplied_witness") != 0)
            or ledger.get("slots_with_unattested_witness") is not None):
        out["reason"] = "PROSPECTIVE_SLOT_ACCOUNTING_MALFORMED"
        return out
    future = ledger.get("not_yet_due_slots")
    past = ledger.get("not_issued_before_window_slots")
    if (type(future) is not int or type(past) is not int
            or future + past != 672
            or ledger.get("future_unattested_claim_slots") != 0
            or ledger.get("past_unattested_claim_slots") != 0):
        out["reason"] = "PROSPECTIVE_SLOT_TOTALS_OR_WITNESS_STATUS_INCOHERENT"
        return out
    next_open = [start for horizon in ("D1", "W1")
                 for start, end in _nominal_windows(horizon)
                 if start > now]
    out.update({
        "state": "LAB_FX28_SINGLE_READINESS_PANEL_RECONCILED_NO_GO",
        "reason": "DOCUMENTARY_GAPS_AND_PRE_EVENT_ACCOUNTABILITY_VISIBLE_NO_DIRECTION",
        "issuer_policy_document_count": len(accepted),
        "issuer_policy_currencies_locally_checked": sorted(accepted),
        "issuer_policy_missing_currencies": sorted(missing),
        "issuer_policy_rejected_currencies": sorted(rejected),
        "pairs_with_both_policy_documents": pair_count,
        "pairs_lacking_policy_document": 28 - pair_count,
        "missing_issuer_reference_urls": {
            code: _SOURCE_URLS[code] for code in sorted(set(missing) | set(rejected))
            if code in _SOURCE_URLS
        },
        "recent_24h_local_receipt_claim_currencies": recent,
        "stale_over_24h_local_receipt_claim_currencies": stale,
        "unknown_local_receipt_clock_currencies": unknown,
        "recent_24h_local_receipt_claim_count": len(recent),
        "recent_24h_bilateral_policy_pair_count":
            len(recent) * (len(recent) - 1) // 2,
        "local_document_capture_age_status_by_currency": age_rows,
        "factors_with_any_relevant_local_document":
            factors["factor_slots_with_any_relevant_local_document"],
        "ppi_original_local_replayed_for_context":
            ppi_archive_basename is not None,
        "cpi_original_local_replayed_for_context":
            cpi_archive_basename is not None,
        "ppi_sep2026_vintage_input_requested": revision_requested,
        "ppi_sep2026_locally_verified_original_count": verified_revision_count,
        "ppi_sep2026_revision_documentary_summary": summary,
        "slots_accounted": 672,
        "slots_future_no_supplied_witness": future,
        "slots_past_no_supplied_witness": past,
        "next_frozen_start_utc": min(next_open).isoformat()
            if next_open else None,
    })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FX28 single-source read-only lab report; never a signal")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--ppi-archive", default=None, metavar="BASENAME")
    parser.add_argument("--cpi-archive", default=None, metavar="BASENAME")
    args = parser.parse_args(argv)
    report = (
        inspect_fx28_single_readiness_panel_lab(
            local_appdata=os.environ.get("LOCALAPPDATA", ""),
            inspected_at_utc=datetime.now(timezone.utc).replace(microsecond=0),
            ppi_archive_basename=args.ppi_archive,
            cpi_archive_basename=args.cpi_archive)
        if args.audit else _base("EXPLICIT_AUDIT_FLAG_REQUIRED"))
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 2  # Always NO-GO; never mistaken for authorization


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("SCHEMA", "inspect_fx28_single_readiness_panel_lab", "main")
