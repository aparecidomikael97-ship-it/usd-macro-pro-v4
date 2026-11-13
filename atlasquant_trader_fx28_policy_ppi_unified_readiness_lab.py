"""Motor A: ONE read-only source diagnostic for 8-bank policy + US PPI.

Real codepaths, NOT intermediate mock reports:
  local issuer files + SHA -> 8-bank typed parser -> 28-pair coverage
  local BLS original.html + receipt.json -> PPI Table-1 4/49104/49116
  -> 28 source-readiness rows. Seven USD-leg pairs can reference the
  exact same PPI source once; 21 other crosses must NOT count it as
  independent domestic CPI or an FX signal.

The October PPI report is AFTER release (Nov 13). This check does NOT
authenticate a source's true first-seen, date of policy decision, bilateral
CPI, policy expectations, broker M15, independent forecast or model.
A recently captured receipt is NOT a live interest rate.

No network, files written, broker, MT5, workers, orders, paid APIs,
calibrated odds, or GBP/JPY/etc "impact" invented from US-only PPI.

Pure by default; CLI requires explicit --audit and reads only
LOCALAPPDATA/AtlasQuant/LAB/official_macro_receipts. Optional --ppi-archive
is the exact basename emitted by the PPI original collector, not a path.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS, split_pair
from atlasquant_trader_fx28_28pair_source_readiness_manual_lab import (
    SCHEMA as POLICY_REPORT_SCHEMA,
    inspect_28pair_source_readiness_once_lab,
)
from atlasquant_trader_us_ppi_oct2026_original_capture_lab import (
    SCHEMA as PPI_REPORT_SCHEMA,
    replay_oct2026_bls_original_capture_lab,
)

SCHEMA = "ATLASQUANT_TRADER_FX28_POLICY_PPI_UNIFIED_READINESS_LAB_V1"
_ACCEPTED_POLICY = "LAB_FX28_28PAIR_MANUAL_SOURCE_READINESS_NO_GO"
_ACCEPTED_PPI = "LAB_US_PPI_OCT2026_BLS_RAW_BYTES_REPLAYED_LOCAL_ONLY_NO_GO"
_PPI_CODES = ("4", "49104", "49116")
_PPI_LABELS = (
    "Final demand",
    "Final demand less foods and energy",
    "Final demand less foods, energy, and trade services",
)


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None or value.microsecond:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "state": "LAB_FX28_POLICY_PPI_UNIFIED_READINESS_BLOCKED_NO_GO",
        "reason": reason,
        "expected_fx28_pairs": 28,
        "fx28_pairs_reported": 0,
        "per_pair": [],
        "policy_source_audit_state": "NOT_RUN",
        "policy_source_audit_reason": None,
        "policy_source_documents_locally_checked": 0,
        "policy_source_recent_local_receipt_claims": 0,
        "policy_pairs_with_two_originals": 0,
        "policy_pairs_with_two_recent_local_receipt_claims": 0,
        "policy_source_integrity_checked_not_first_seen": True,
        "policy_local_recency_is_not_realtime_economic_freshness": True,
        "ppi_source_replay_state": "NOT_REQUESTED",
        "ppi_source_replay_reason": None,
        "ppi_source_replay_attempted": False,
        "ppi_documentary_series": [],
        "ppi_documentary_series_count": 0,
        "ppi_source_raw_sha256": None,
        "ppi_direct_usd_leg_pairs": 7,
        "ppi_direct_usd_leg_pairs_with_source_replayed": 0,
        "non_usd_leg_pairs_without_direct_usd_ppi_attachment": 21,
        "ppi_is_one_shared_catalyst_not_seven_independent_news": True,
        "ppi_oct2026_is_post_release_documentary_context": True,
        "ppi_can_be_fx28_directional_factor": False,
        "evidence_dependency_independently_authenticated": False,
        "central_bank_issuer_first_seen_independently_authenticated": False,
        "bls_first_seen_independently_authenticated": False,
        "historical_macro_point_in_time_authenticated": False,
        "bilateral_cpi_for_eight_currencies_authenticated": False,
        "policy_expectations_authenticated": False,
        "broker_m15_authenticated": False,
        "pre_event_fx28_rosters_independently_witnessed": False,
        "model_calibrated_for_fx28": False,
        "economic_impact_points": None,
        "usd_strength_score": None,
        "fx28_probability": None,
        "directional_bias": None,
        "validated_hit_rate": None,
        "operational_bias": "AGUARDAR",
        "trade_authorized": False,
        "publishable": False,
        "live_alert_allowed": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
        "http_requests": 0,
        "file_writes": 0,
        "new_cost_brl": 0,
        "research_only": True,
    }


def _valid_policy(report: Any) -> bool:
    if (type(report) is not dict
            or report.get("schema") != POLICY_REPORT_SCHEMA
            or report.get("state") != _ACCEPTED_POLICY
            or report.get("mode") != "audit"
            or report.get("pairs_explained") != 28
            or report.get("operational_bias") != "AGUARDAR"
            or report.get("trade_authorized") is not False
            or report.get("publishable") is not False
            or report.get("first_seen_pit_authenticated") is not False
            or report.get("broker_m15_verified") is not False
            or report.get("source_coverage_is_not_currency_strength") is not True):
        return False
    rows = report.get("per_pair")
    if (type(rows) is not list or len(rows) != len(OFFICIAL_PAIRS)
            or [r.get("pair") if type(r) is dict else None for r in rows]
                != list(OFFICIAL_PAIRS)):
        return False
    for row in rows:
        if (row.get("bias") != "AGUARDAR"
                or row.get("trade_authorized") is not False
                or type(row.get("local_policy_source_for_both")) is not bool
                or type(row.get("both_policy_recent_capture_claims_only")) is not bool
                or row["both_policy_recent_capture_claims_only"]
                   and not row["local_policy_source_for_both"]
                or row.get("base_currency") != split_pair(row["pair"])[0]
                or row.get("quote_currency") != split_pair(row["pair"])[1]):
            return False
    return True


def _valid_ppi(report: Any) -> bool:
    if (type(report) is not dict
            or report.get("schema") != PPI_REPORT_SCHEMA
            or report.get("state") != _ACCEPTED_PPI
            or report.get("raw_bytes_and_receipt_replayed") is not True
            or report.get("source_original_locally_retained_claim_only") is not True
            or report.get("ppi_can_feed_research_only") is not True
            or report.get("ppi_can_feed_fx28_directional_model") is not False
            or report.get("trade_authorized") is not False
            or report.get("publishable") is not False
            or report.get("bls_issuer_independently_authenticated") is not False
            or report.get("release_first_seen_independently_verified") is not False
            or report.get("usd_directional_bias") is not None
            or report.get("economic_impact_points") is not None
            or report.get("calibrated_probability") is not None
            or type(report.get("raw_document_sha256")) is not str
            or len(report["raw_document_sha256"]) != 64
            or report.get("documentary_series_count") != 3):
        return False
    series = report.get("documentary_series")
    if type(series) is not list or len(series) != 3:
        return False
    for i, row in enumerate(series):
        if (type(row) is not dict
                or row.get("issuer") != "BLS"
                or row.get("country") != "US"
                or row.get("fd_commodity_code") != _PPI_CODES[i]
                or row.get("series_label") != _PPI_LABELS[i]
                or row.get("reference_period") != "2026-10"
                or row.get("comparison_period") != "2026-09"
                or row.get("change_type") != "MONTH_OVER_MONTH"
                or row.get("seasonal_adjustment") != "SA"
                or row.get("unit") != "PERCENT_CHANGE"
                or row.get("actual_body_sha256") != report["raw_document_sha256"]
                or type(row.get("actual_pct_local_documentary_claim")) is not str
                or row.get("pre_event_consensus_pct") is not None
                or row.get("surprise_percentage_points") is not None
                or row.get("economic_impact_points") is not None
                or row.get("issuer_first_seen_independently_attested") is not False
                or row.get("pre_event_consensus_independently_attested") is not False):
            return False
    return True


def inspect_fx28_policy_ppi_readiness_lab(
    *, local_appdata: Any, decision_at_utc: Any,
    ppi_archive_basename: Any = None,
) -> dict[str, Any]:
    """Only real read-only replay functions are called; no 'PASS' injection."""
    out = _base("INVALID_DECISION_CLOCK_OR_SOURCE_ROOT")
    now = _utc(decision_at_utc)
    if (now is None or type(local_appdata) is not str
            or not local_appdata
            or type(ppi_archive_basename) not in (str, type(None))
            or ppi_archive_basename == ""):
        return out
    try:
        root = Path(local_appdata)
        if (not root.is_absolute() or not root.is_dir()
                or any(x.is_symlink() for x in (root, *root.parents))
                or any((root / sub).is_symlink() for sub in (
                    "AtlasQuant", "AtlasQuant/LAB",
                    "AtlasQuant/LAB/official_macro_receipts"))):
            return out
    except (OSError, TypeError, ValueError, RuntimeError):
        return out

    # The policy auditor can be BLOCKED when there is no folder. Do not
    # quietly claim all eight source files are absent on the real AM12.
    policy = inspect_28pair_source_readiness_once_lab(
        mode="audit", local_appdata=local_appdata,
        decision_clock=lambda: now,
    )
    policy_ok = _valid_policy(policy)
    out["policy_source_audit_state"] = (
        policy.get("state") if type(policy) is dict else "INVALID_REPORT")
    out["policy_source_audit_reason"] = (
        policy.get("reason") if type(policy) is dict else "INVALID_REPORT")

    if policy_ok:
        out.update({
            "policy_source_documents_locally_checked":
                policy["local_policy_sources_checked_count"],
            "policy_source_recent_local_receipt_claims":
                policy["local_policy_recent_capture_claim_count"],
            "policy_pairs_with_two_originals":
                policy["pairs_with_two_policy_sources_locally_checked"],
            "policy_pairs_with_two_recent_local_receipt_claims":
                policy["pairs_with_two_recent_local_capture_claims"],
        })
    else:
        # Missing/invalid policy files are UNKNOWN, not evidence of
        # 0 actual central-bank documents in the user's computer.
        out["policy_source_audit_reason"] = (
            "POLICY_LOCAL_ARCHIVE_UNAVAILABLE_NOT_EIGHT_SOURCE_ABSENCE"
        )

    ppi_ok = False
    if ppi_archive_basename is not None:
        out["ppi_source_replay_attempted"] = True
        ppi = replay_oct2026_bls_original_capture_lab(
            local_appdata=local_appdata,
            archive_basename=ppi_archive_basename,
            observed_at_utc=now,
        )
        out["ppi_source_replay_state"] = (
            ppi.get("state") if type(ppi) is dict else "INVALID_REPORT")
        out["ppi_source_replay_reason"] = (
            ppi.get("reason") if type(ppi) is dict else "INVALID_REPORT")
        ppi_ok = _valid_ppi(ppi)
        if ppi_ok:
            out["ppi_documentary_series"] = ppi["documentary_series"]
            out["ppi_documentary_series_count"] = 3
            out["ppi_source_raw_sha256"] = ppi["raw_document_sha256"]

    # 7 direct USD legs for eight-currency/28-pair universe. One PPI is
    # ONE catalyst, not seven statistically independent observations.
    per_pair = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        raw = None
        if policy_ok:
            raw = policy["per_pair"][len(per_pair)]
        usd = "USD" in (base, quote)
        pair_policy = (raw["local_policy_source_for_both"]
                       if raw is not None else False)
        pair_recent = (raw["both_policy_recent_capture_claims_only"]
                       if raw is not None else False)
        missing = (raw["missing_policy_currencies"]
                   if raw is not None else [])
        rejected = (raw["rejected_policy_currencies"]
                    if raw is not None else {})
        if not policy_ok:
            reason = "POLICY_ARCHIVE_UNAVAILABLE_OR_UNVERIFIED"
        elif not pair_policy:
            reason = "ONE_OR_BOTH_POLICY_DOCUMENTS_MISSING_OR_REJECTED"
        elif not pair_recent:
            reason = "POLICY_SOURCES_STALE_UNSTAMPED_OR_UNTRUSTED"
        else:
            reason = "NEED_BILATERAL_CPI_EXPECTATIONS_PIT_PRICE_AND_CALIBRATION"
        per_pair.append({
            "pair": pair,
            "base_currency": base,
            "quote_currency": quote,
            "two_policy_originals_locally_checked": pair_policy,
            "two_policy_recent_local_receipt_claims": pair_recent,
            "policy_missing_currency_codes": missing,
            "policy_rejected_currency_codes": rejected,
            "ppi_direct_usd_issuer_leg": usd,
            "ppi_direct_usd_issuer_leg_documentary_context_replayed":
                usd and ppi_ok,
            "ppi_postrelease_source_sha256_for_direct_usd_leg_only":
                out["ppi_source_raw_sha256"] if usd and ppi_ok else None,
            "ppi_counts_as_independent_issuer_catalyst_for_this_pair": False,
            "ppi_validated_pre_event_consensus_available": False,
            "ppi_fx_impact_calculated": False,
            "source_readiness_blocking_reason": reason,
            "need_bilateral_cpi_point_in_time": True,
            "need_expectations_point_in_time": True,
            "need_broker_m15_authenticated": True,
            "need_model_calibration": True,
            "directional_bias": None,
            "calibrated_probability": None,
            "bias": "AGUARDAR",
            "trade_authorized": False,
        })
    out.update({
        "fx28_pairs_reported": len(per_pair),
        "per_pair": per_pair,
        "ppi_direct_usd_leg_pairs_with_source_replayed": (
            sum(x["ppi_direct_usd_issuer_leg_documentary_context_replayed"]
                for x in per_pair)),
        "state": "LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO",
        "reason": (
            "BOTH_LOCAL_SOURCE_READERS_CHECKED_RESEARCH_ONLY"
            if policy_ok and ppi_ok else
            "SOURCES_PARTIAL_UNAVAILABLE_OR_HISTORICAL_NO_DIRECTION"
        ),
    })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Motor A: offline 8-bank policy + BLS PPI documentary audit")
    parser.add_argument("--audit", action="store_true",
                        help="Explicit read-only audit; never fetch or trade")
    parser.add_argument("--ppi-archive", default=None, metavar="NAME",
                        help="Exact BLS PPI archive directory name; no paths")
    args = parser.parse_args(argv)
    if not args.audit:
        out = _base("EXPLICIT_READONLY_AUDIT_FLAG_REQUIRED")
    else:
        out = inspect_fx28_policy_ppi_readiness_lab(
            local_appdata=os.environ.get("LOCALAPPDATA", ""),
            decision_at_utc=_now(), ppi_archive_basename=args.ppi_archive)
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    # Exit 0 means read-only AUDIT produced 28 rows, NEVER a trade GO.
    return 0 if (out["state"] ==
                 "LAB_FX28_POLICY_PPI_COMBINED_READONLY_NO_GO") else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("SCHEMA", "inspect_fx28_policy_ppi_readiness_lab", "main")
