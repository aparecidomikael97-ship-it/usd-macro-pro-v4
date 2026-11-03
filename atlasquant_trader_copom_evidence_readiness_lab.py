"""Read-only evidence readiness for the Nov 4, 2026 Copom WIN/WDO study.

No actual Copom outcome or B3 quotes were known when this LAB module was
created. It ties three already built offline validators into one conservative
research view. Matching an official-looking URL, timestamps or checksums
NEVER authenticates a source. No network, browser scraping, paid API, Worker,
Render, order, dashboard publication or production operation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from atlasquant_trader_copom_post_event_compare_lab import (
    assess_copom_post_event_candidate_lab,
    PENDING as OUTCOME_PENDING,
    CANDIDATE as OUTCOME_CANDIDATE,
    DENIED as OUTCOME_DENIED,
)
from atlasquant_trader_copom_b3_session_reaction_lab import (
    build_copom_b3_session_reaction_lab,
    PENDING as SESSION_PENDING,
    DENIED as SESSION_DENIED,
)
from atlasquant_trader_b3_offline_export_intake_lab import (
    inspect_b3_offline_price_export_lab,
    PENDING as CSV_UNATTESTED,
    SYNTHETIC as CSV_SYNTHETIC,
    DENIED as CSV_DENIED,
)

SCHEMA = "ATLASQUANT_TRADER_COPOM_EVIDENCE_READINESS_LAB_V1"
PENDING = "LAB_COPOM_EVIDENCE_INCOMPLETE"
CANDIDATES = "LAB_COPOM_EVIDENCE_CANDIDATES_ONLY"
DENIED = "LAB_COPOM_EVIDENCE_REFUSED"
PRE_EVENT_COMMIT = "1281f21860211e9b6f784c649396aa56d17ecdf5"
SOURCE_KINDS = (
    "FROZEN_EXPECTATIONS_GIT_CONTENT",
    "POST_EVENT_BCB_COMMUNIQUE",
    "B3_REGULAR_SESSION_PLAN",
    "B3_TRADE_EXPORT",
)
MISSING_EVIDENCE = (
    "ATTEST_GITHUB_PRE_EVENT_SERVER_RECEIPT_OR_INDEPENDENT_TIMESTAMP",
    "ATTEST_ORIGINAL_BCB_COMMUNIQUE_AND_RELEASE_TIME",
    "VERIFY_B3_CALENDAR_AND_SESSION_EXCEPTION_RULES",
    "VERIFY_AUTHORIZED_B3_QUOTE_PROVIDER_AND_REUSE_RIGHTS",
    "VERIFY_EXACT_SAME_CONTRACT_LAST_PRE_AND_FIRST_POST_TRADE",
    "CHECK_WIDER_OVERNIGHT_MARKET_NEWS_AND_REPRICING",
    "PRE_REGISTER_AND_VALIDATE_REAL_MARKET_DIRECTIONAL_FORECAST",
)


def _base(state: str, reason: str | None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": state,
        "reason": reason,
        "pre_event_git_commit": PRE_EVENT_COMMIT,
        "pre_event_source_content_matches_original": False,
        "pre_event_independent_timestamp_verified": False,
        "decision_status": "UNASSESSED",
        "session_status": "UNASSESSED",
        "quote_status": "UNASSESSED",
        "decision_candidate_scenario": None,
        "outcome_rate_independently_verified": False,
        "bcb_release_time_independently_verified": False,
        "b3_schedule_exception_calendar_verified": False,
        "b3_quotes_and_licensing_independently_verified": False,
        "market_session_gap_verified": False,
        "economic_causality_proven": False,
        "trader_directional_forecast_pre_registered": False,
        "trader_predictive_accuracy_proven": False,
        "market_implied_copom_probability": None,
        "win_wdo_direction": "AGUARDAR",
        "can_feed_live_radar": False,
        "can_feed_real_oos": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "render_configuration_changed": False,
        "paid_provider_approved": False,
        "missing_independent_evidence": list(MISSING_EVIDENCE),
        "audit_rows": [],
    }


def build_copom_evidence_readiness_lab(
    frozen_json_bytes: Any, *, evaluated_at: datetime,
    claimed_bcb_result: Any = None,
    price_export_csv: Any = None,
    price_export_manifest: Any = None,
) -> dict[str, Any]:
    """Summarize strict evidence status; never promotes untrusted input to fact.

    A caller may submit a self-reported official release or manual price
    export; both remain UNATTESTED even if their internal formats pass. The
    CSV is never forwarded to a live radar or trade. Generated rows contain
    only provenance classes, NOT input prices or unverified provider claims.
    """
    if (not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None
            or evaluated_at.utcoffset() is None):
        raise ValueError("Explicit timezone required for evidence evaluation")
    when = evaluated_at.astimezone(timezone.utc)
    result = _base(PENDING, None)

    # Validate the exact original Git bytes with existing independent
    # validators, not a reconstructed or reformatted copy of the snapshot.
    policy = assess_copom_post_event_candidate_lab(
        frozen_json_bytes, claimed_bcb_result, evaluated_at=when)
    session = build_copom_b3_session_reaction_lab(
        frozen_json_bytes, evaluated_at=when)
    if (policy["state"] == OUTCOME_DENIED or
            session["state"] == SESSION_DENIED or
            session["state"] != SESSION_PENDING or
            not policy["original_pre_event_snapshot_matched"] or
            not session["pre_event_original_bytes_matched"]):
        return _base(DENIED, "Frozen evidence, clocks, claimed result or session planning refused")

    result["pre_event_source_content_matches_original"] = True
    result["session_status"] = "REGULAR_HOURS_DOCUMENTARY_ONLY"
    result["decision_status"] = (
        "NO_AUTHENTICATED_RESULT" if policy["state"] == OUTCOME_PENDING
        else "CALLER_SUPPLIED_BCB_CANDIDATE_UNATTESTED")
    if policy["state"] not in (OUTCOME_PENDING, OUTCOME_CANDIDATE):
        return _base(DENIED, "Unsupported policy comparison state")

    if (price_export_csv is None) != (price_export_manifest is None):
        return _base(DENIED, "Incomplete CSV and rights/provenance manifest pair")

    if price_export_csv is None:
        result["quote_status"] = "NO_AUTHENTICATED_PRICE_DATA"
    else:
        audit = inspect_b3_offline_price_export_lab(
            price_export_csv, price_export_manifest, evaluated_at=when)
        if audit["state"] == CSV_DENIED:
            return _base(DENIED, "Offline CSV source, contract, session or provenance refused")
        if audit["state"] not in (CSV_UNATTESTED, CSV_SYNTHETIC):
            return _base(DENIED, "Unknown CSV validation state")
        if (not audit["csv_fields_valid"] or
                not audit["csv_integrity_matches_claim"] or
                audit["market_reaction_real_verified"] or
                audit["market_data_access_rights_independently_verified"] or
                audit["can_feed_live_radar"]):
            return _base(DENIED, "Untrusted price export attempted to claim real verification")
        result["quote_status"] = ("SYNTHETIC_TEST_ONLY" if audit["state"] == CSV_SYNTHETIC
                                  else "MANUAL_EXPORT_CANDIDATE_UNATTESTED")
        result["claimed_price_pairs"] = audit["matched_pairs"]

    # The scenario is a classification of a self-reported candidate, NOT
    # an authenticated decision or a calibrated rate-surprise prediction.
    if policy["state"] == OUTCOME_CANDIDATE:
        result["decision_candidate_scenario"] = policy["result_scenario"]

    result["audit_rows"] = [
        {"source_kind": SOURCE_KINDS[0], "status": "GIT_CONTENT_PINNED",
         "independently_authenticated": False,
         "usable_as_real_trade_evidence": False},
        {"source_kind": SOURCE_KINDS[1], "status": result["decision_status"],
         "independently_authenticated": False,
         "usable_as_real_trade_evidence": False},
        {"source_kind": SOURCE_KINDS[2], "status": result["session_status"],
         "independently_authenticated": False,
         "usable_as_real_trade_evidence": False},
        {"source_kind": SOURCE_KINDS[3], "status": result["quote_status"],
         "independently_authenticated": False,
         "usable_as_real_trade_evidence": False},
    ]
    if (policy["state"] == OUTCOME_CANDIDATE or price_export_csv is not None):
        result["state"] = CANDIDATES
    result["why_not_ready"] = (
        "Git content pinning does not attest original publication timing. "
        "Self-reported BCB text and B3 prices cannot verify independent "
        "source, market data rights, actual first/last trades, causality or "
        "any preregistered FX/WIN/WDO market forecast. No real OOS allowed."
    )
    return result


__all__ = [
    "SCHEMA", "PENDING", "CANDIDATES", "DENIED", "MISSING_EVIDENCE",
    "build_copom_evidence_readiness_lab",
]
