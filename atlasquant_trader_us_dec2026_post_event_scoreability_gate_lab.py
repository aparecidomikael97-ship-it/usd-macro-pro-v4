"""December-2026 CPI/PPI post-event archive readiness, NOT FX win-rate.

One immutable two-release research denominator, one canonical seven-cross
USD cohort per release, and a sealed ABSTAIN-only frozen protocol.
Separates:
- SOURCE documents available at a decision cutoff (local claims only);
- AFTERMATH BLS/price archive receipts available after their actual capture;
- genuinely authenticated, independently timestamped directional FORECASTS
  (none were made; zero trials, forever, under this particular protocol).

Missing releases, prices, spreads, confounders, consensus and forecasts never
drop an event or get silently scored as successes. Seven correlated crosses
and the M15/H1/H4 windows are descriptions of ONE economic release.

No calls to GitHub, internet, filesystem, MT5, Pepperstone, scheduler or
trade engines. This gate DOES NOT validate BLS html or broker quote bytes:
it reports local receipt claims, not independently attested outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from typing import Any

from atlasquant_trader_ppi_usd_fx_forward_reaction_lab import USD_FX, WINDOWS
from atlasquant_trader_us_dec2026_pre_event_consensus_custody_lab import EVENTS
from atlasquant_trader_us_dec2026_frozen_evaluation_protocol_lab import (
    PINNED_PLAN_SHA256, inspect_frozen_dec2026_evaluation_protocol_lab,
)

SCHEMA = "ATLASQUANT_US_DEC2026_POST_EVENT_SCOREABILITY_READINESS_LAB_V1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FX = tuple(USD_FX)
_HORIZONS = tuple(name for name, _ in WINDOWS)
_EVENT_BY_ROOT = {root: (period, release)
                  for root, _, period, release in EVENTS}
_ALLOWED_ACTUAL_KIND = "BLS_POST_RELEASE_ORIGINAL_LOCAL_CLAIM_ONLY"
_ALLOWED_PRICE_KIND = "PEPPERSTONE_MT5_M15_CSV_LOCAL_CLAIM_ONLY"


@dataclass(frozen=True)
class UntrustedAftermathArchiveClaim:
    event_root: str
    actual_original_sha256_claim: str
    actual_locally_captured_at_utc: datetime
    price_original_sha256_claim: str
    price_locally_captured_at_utc: datetime
    price_pairs: tuple[str, ...]
    horizons: tuple[str, ...]
    actual_archive_kind: str = _ALLOWED_ACTUAL_KIND
    price_archive_kind: str = _ALLOWED_PRICE_KIND
    spread_rows_present_claim_only: bool = False
    competing_news_review_claim_only: bool = False


def _utc(dt: Any) -> datetime | None:
    if type(dt) is not datetime or dt.tzinfo is None:
        return None
    try:
        offset = dt.utcoffset()
        return dt.astimezone(timezone.utc) if offset is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_DEC2026_SCOREABILITY_GATE_BLOCKED_HARD_NO_GO",
        "reason": reason,
        "frozen_dec2026_economic_event_denominator": 2,
        "pre_registered_plan_sha256": None,
        "event_rows": [
            {
                "event_root_id": root,
                "reference_period": period,
                "release_utc": release.isoformat(),
                "status": "UNVERIFIED",
                "local_source_snapshot_count_claim_only": 0,
                "post_event_archive_claim_visible": False,
                "actual_original_sha256_local_claim": None,
                "price_archive_sha256_local_claim": None,
                "price_pairs_observed_claim_only": 0,
                "horizons_observed_claim_only": [],
                "spreads_originals_independently_attested": False,
                "competing_news_independently_ruled_out": False,
                "forecast_precommitted_before_news": False,
                "independent_scoreable_prediction": False,
            }
            for root, _, period, release in EVENTS
        ],
        "post_event_archive_claims_visible_count": 0,
        "local_source_snapshots_visible_count": 0,
        "seven_correlated_crosses_are_not_seven_macro_trials": True,
        "three_price_horizons_are_not_three_independent_macro_trials": True,
        "missing_events_retained_and_no_outcome_based_selection": True,
        "pre_registered_directional_predictions": 0,
        "independent_forecast_trials_verified": 0,
        "out_of_sample_trials_scoreable": 0,
        "winner_count": None,
        "loser_count": None,
        "win_rate": None,
        "calibrated_fx_probability": None,
        "directional_usd_bias": None,
        "causal_fx_reaction_identified": False,
        "source_first_seen_independently_attested": False,
        "github_witness_timestamp_independently_verified": False,
        "bls_first_print_independently_attested": False,
        "broker_prices_bid_ask_and_slippage_independently_attested": False,
        "publishable": False,
        "trade_authorized": False,
        "operational_bias": "AGUARDAR",
        "fx28_original_672_slots_changed": False,
        "http_requests": 0, "file_writes": 0, "mt5_calls": 0,
        "new_cost_brl": 0,
    }


def audit_dec2026_scoreability_readiness_lab(
    *, inspected_at_utc: Any, aftermath_archive_claims: Any = (),
    pre_event_source_snapshots: Any = (),
    submitted_frozen_plan: Any = None,
) -> dict[str, Any]:
    """After-the-fact evidence may be DOCUMENTED, never scored as prediction."""
    out = _blocked("INVALID_CLOCK_OR_EVIDENCE_CLAIMS")
    now = _utc(inspected_at_utc)
    if (now is None
            or type(aftermath_archive_claims) not in (tuple, list)
            or len(aftermath_archive_claims) > len(EVENTS)):
        return out
    p = inspect_frozen_dec2026_evaluation_protocol_lab(
        inspected_at_utc=now, source_snapshots=pre_event_source_snapshots,
        submitted_plan=submitted_frozen_plan,
    )
    if (p.get("state") != "LAB_DEC2026_FROZEN_DESCRIPTIVE_PROTOCOL_RECONCILED_NO_GO"
            or p.get("frozen_plan_sha256") != PINNED_PLAN_SHA256
            or p.get("frozen_economic_event_denominator") != len(EVENTS)
            or p.get("prospective_directional_forecasts_registered") != 0
            or p.get("independent_testable_out_of_sample_trials") != 0
            or p.get("trade_authorized") is not False
            or p.get("publishable") is not False):
        out["reason"] = "FROZEN_PROTOCOL_OR_PRE_EVENT_CUSTODY_INVALID"
        return out
    claims: dict[str, UntrustedAftermathArchiveClaim] = {}
    for item in aftermath_archive_claims:
        if (type(item) is not UntrustedAftermathArchiveClaim
                or item.event_root not in _EVENT_BY_ROOT
                or item.event_root in claims):
            out["reason"] = "DUPLICATE_FOREIGN_OR_INJECTED_AFTER_EVENT_COHORT"
            return out
        claims[item.event_root] = item

    # Do not inspect or disclose future-payload hashes, prices, receipts,
    # spreads or claimed outcome. Only release and cutoff are used.
    rows = []
    encountered_hashes: set[str] = set()
    count = 0
    for item in p["events"]:
        root = item["event_root"]
        period, release = _EVENT_BY_ROOT[root]
        row = next(r.copy() for r in out["event_rows"]
                   if r["event_root_id"] == root)
        row["local_source_snapshot_count_claim_only"] = (
            item["source_snapshot_hash_count_locally_claimed_only"]
        )
        candidate = claims.get(root)
        if now < release:
            row["status"] = "FUTURE_BLS_RELEASE_NO_ACTUAL_OR_PRICE_AVAILABLE"
        elif candidate is None:
            row["status"] = "NO_POST_RELEASE_ORIGINALS_SUBMITTED"
        else:
            actual_at = _utc(candidate.actual_locally_captured_at_utc)
            price_at = _utc(candidate.price_locally_captured_at_utc)
            if actual_at is None or price_at is None:
                return _blocked("AFTERMATH_CAPTURE_CLOCK_NOT_AN_AWARE_DATETIME")
            if actual_at > now or price_at > now:
                row["status"] = "POST_RELEASE_ARCHIVE_NOT_YET_VISIBLE_AT_CUTOFF"
            elif (actual_at < release or price_at < release + timedelta(hours=4)
                    or candidate.actual_archive_kind != _ALLOWED_ACTUAL_KIND
                    or candidate.price_archive_kind != _ALLOWED_PRICE_KIND
                    or type(candidate.price_pairs) is not tuple
                    or candidate.price_pairs != _FX
                    or type(candidate.horizons) is not tuple
                    or candidate.horizons != _HORIZONS
                    or type(candidate.spread_rows_present_claim_only) is not bool
                    or type(candidate.competing_news_review_claim_only) is not bool
                    or type(candidate.actual_original_sha256_claim) is not str
                    or type(candidate.price_original_sha256_claim) is not str
                    or _SHA.fullmatch(candidate.actual_original_sha256_claim) is None
                    or _SHA.fullmatch(candidate.price_original_sha256_claim) is None
                    or candidate.actual_original_sha256_claim ==
                       candidate.price_original_sha256_claim
                    or candidate.actual_original_sha256_claim in encountered_hashes
                    or candidate.price_original_sha256_claim in encountered_hashes):
                return _blocked("CLAIMED_ORIGINAL_RECEIPTS_PRICE_COHORT_OR_CLOCK_INVALID")
            else:
                encountered_hashes.add(candidate.actual_original_sha256_claim)
                encountered_hashes.add(candidate.price_original_sha256_claim)
                row.update({
                    "status": "POST_EVENT_ORIGINAL_ARCHIVE_CLAIMS_ONLY_NO_SCORE",
                    "post_event_archive_claim_visible": True,
                    "actual_original_sha256_local_claim":
                        candidate.actual_original_sha256_claim,
                    "price_archive_sha256_local_claim":
                        candidate.price_original_sha256_claim,
                    "price_pairs_observed_claim_only": len(_FX),
                    "horizons_observed_claim_only": list(_HORIZONS),
                })
                count += 1
        rows.append(row)
    out.update({
        "state": "LAB_DEC2026_TWO_EVENT_AFTER_EVIDENCE_RECONCILED_HARD_NO_GO",
        "reason": "UNTRUSTED_POST_EVENT_ORIGINAL_CLAIMS_NO_PRECOMMITTED_DIRECTIONAL_MODEL",
        "pre_registered_plan_sha256": PINNED_PLAN_SHA256,
        "event_rows": rows,
        "post_event_archive_claims_visible_count": count,
        "local_source_snapshots_visible_count":
            p["locally_replayed_source_snapshots"],
    })
    return out


__all__ = (
    "SCHEMA", "UntrustedAftermathArchiveClaim",
    "audit_dec2026_scoreability_readiness_lab",
)
