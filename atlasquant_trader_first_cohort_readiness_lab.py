"""AtlasQuant P0: evidence-inventory gate for the first D1/W1 prospective cohort.

Offline research preflight. Caller-provided reports are NOT authenticated source
proof. This module deliberately never enables signals, scoring or trading.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import re

SCHEMA = "ATLASQUANT_FIRST_FX_COHORT_READINESS_LAB_V1"
HORIZONS = frozenset(("D1", "W1"))
CURRENCIES = frozenset(("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"))
HEX = re.compile(r"[a-f0-9]{64}\Z")


def _clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_FIRST_COHORT_BLOCKED",
        "reason": reason, "blockers": [], "reportable_coverage": {
            "expected_fx_pairs": 28, "expected_horizons": 2,
            "expected_slots": 56, "registered_slots": 0,
        },
        "archive_documentary_status": None,
        "roster_documentary_status": None,
        "census_documentary_status": None,
        "github_anchor_documentary_status": None,
        "macro_currencies_claimed": 0,
        "broker_session_source_authenticated": False,
        "macro_originals_authenticated": False,
        "github_comments_authenticated_here": False,
        "prospective_predictions_anchored_independently": False,
        "price_history_pit_authenticated": False,
        "out_of_sample_accuracy_validated": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0,
        "new_cost_brl": 0, "research_only": True,
    }


def inspect_first_cohort_readiness_lab(
    *, as_of_utc: Any, archive_audit: Any = None,
    broker_session: Any = None, macro_receipts: Any = None,
    roster_report: Any = None, census_report: Any = None,
    github_anchor_report: Any = None, decision_frozen_at: Any = None,
) -> dict[str, Any]:
    """Read-only inventory. A documentary 'complete' is NOT live readiness.

    `archive_audit` comes from atlasquant_mt5_backtest_gap_guard_lab.audit_archive.
    `roster_report` and `census_report` are outputs of the 56-slot census lab.
    `github_anchor_report` comes from the claimed two-comment inspector, not API.
    `broker_session` has keys {D1,W1} and each contains `observed_at_utc`,
    `document_sha256` and `target_open_utc`. `macro_receipts` is a mapping of
    eight currency IDs to alleged `published_at_utc`, `captured_at_utc`,
    `source_sha256` and `indicator`. All caller-provided, never attested here.
    """
    now = _clock(as_of_utc)
    out = _base("INVALID_AS_OF_CLOCK")
    if now is None:
        out["blockers"] = ["INVALID_AS_OF_CLOCK"]
        return out
    failures: list[str] = []
    freeze_at = _clock(decision_frozen_at)
    if freeze_at is None or freeze_at > now:
        failures.append("CENSUS_FREEZE_CLOCK_MISSING_OR_FUTURE")

    if not isinstance(archive_audit, dict) or archive_audit.get("schema") != "ATLASQUANT_MT5_BACKTEST_GAP_GUARD_LAB_V1":
        failures.append("AM12_ARCHIVE_NOT_REAUDITED")
    else:
        out["archive_documentary_status"] = archive_audit.get("status")
        if (archive_audit.get("pairs") != 28
                or archive_audit.get("files") != 84
                or archive_audit.get("bars") != 103600
                or archive_audit.get("errors") != []):
            failures.append("MT5_ARCHIVE_STRUCTURAL_EVIDENCE_INCOMPLETE")
        if (archive_audit.get("status") != "CALENDAR_CONTIGUOUS_UNATTESTED"
                or archive_audit.get("blocked_interval_counts") != {}):
            failures.append("BROKER_CALENDAR_GAPS_UNRESOLVED")
        # Even 'contiguous' does not prove source P-I-T or a broker calendar.

    targets = {}
    if not isinstance(broker_session, dict) or set(broker_session) != HORIZONS:
        failures.append("BROKER_D1_W1_CLOCK_EVIDENCE_MISSING")
    else:
        for tf in ("D1", "W1"):
            row = broker_session[tf]
            if not isinstance(row, dict) or set(row) != {
                "observed_at_utc", "target_open_utc", "document_sha256"
            }:
                failures.append(tf + "_BROKER_CLOCK_RECEIPT_INVALID")
                continue
            observed, target = _clock(row["observed_at_utc"]), _clock(row["target_open_utc"])
            if (observed is None or target is None or not observed <= now < target
                    or freeze_at is None or not observed <= freeze_at < target
                    or not _hash(row["document_sha256"])):
                failures.append(tf + "_BROKER_CLOCK_PIT_OR_HASH_INVALID")
            else:
                targets[tf] = target
        # Caller-supplied document references do NOT authenticate the broker.

    if not isinstance(macro_receipts, dict) or set(macro_receipts) != CURRENCIES:
        failures.append("EIGHT_CURRENCY_MACRO_RECEIPTS_MISSING")
    else:
        out["macro_currencies_claimed"] = len(macro_receipts)
        for cur in sorted(CURRENCIES):
            row = macro_receipts[cur]
            if not isinstance(row, dict) or set(row) != {
                "published_at_utc", "captured_at_utc", "source_sha256", "indicator"
            }:
                failures.append(cur + "_MACRO_RECEIPT_INVALID")
                continue
            published, captured = _clock(row["published_at_utc"]), _clock(row["captured_at_utc"])
            if (published is None or captured is None
                    or not published <= captured <= now
                    or freeze_at is None or captured > freeze_at
                    or not _hash(row["source_sha256"])
                    or not isinstance(row["indicator"], str)
                    or row["indicator"] not in {"CPI_YOY", "POLICY_RATE", "BOTH_DOCUMENTED"}):
                failures.append(cur + "_MACRO_RECEIPT_PIT_OR_SOURCE_INVALID")
        # This schema covers a preliminary inventory only, not two authenticated
        # macro families, genuine historical vintages or bilateral comparisons.

    roster_hash = None
    if (not isinstance(roster_report, dict)
            or roster_report.get("state") != "LAB_ROSTER_HASHED_UNATTESTED"
            or not _hash(roster_report.get("sha256"))
            or roster_report.get("full_28fx_d1_w1_roster_checked") is not True):
        failures.append("FROZEN_56_SLOT_ROSTER_MISSING")
    else:
        roster_hash = roster_report["sha256"]
        out["roster_documentary_status"] = roster_report["state"]

    census_hash = None
    if (not isinstance(census_report, dict)
            or census_report.get("state") != "LAB_FULL_CENSUS_HASHED_UNATTESTED"
            or not _hash(census_report.get("sha256"))
            or census_report.get("slots_recorded") != 56
            or census_report.get("full_28fx_d1_w1_roster_checked") is not True):
        failures.append("FROZEN_56_DECISION_CENSUS_MISSING")
    else:
        census_hash = census_report["sha256"]
        out["census_documentary_status"] = census_report["state"]
        out["reportable_coverage"]["registered_slots"] = 56
        if (type(census_report.get("awaiting_count")) is not int
                or not 0 <= census_report["awaiting_count"] <= 56
                or type(census_report.get("hypotheses_count")) is not int
                or census_report["hypotheses_count"] + census_report["awaiting_count"] != 56):
            failures.append("CENSUS_ABSTENTION_ACCOUNTING_INVALID")

    if not isinstance(github_anchor_report, dict) or github_anchor_report.get("state") != "LAB_GITHUB_TWO_ANCHOR_CHRONOLOGY_CLAIM_ONLY":
        failures.append("TWO_GITHUB_PRECOMMIT_ANCHORS_MISSING")
    else:
        out["github_anchor_documentary_status"] = github_anchor_report["state"]
        rb, cb = github_anchor_report.get("roster_anchor_body"), github_anchor_report.get("census_anchor_body")
        if (not isinstance(rb, str) or not isinstance(cb, str)
                or not roster_hash or not census_hash
                or "roster_sha256=" + roster_hash not in rb.splitlines()
                or "roster_sha256=" + roster_hash not in cb.splitlines()
                or "census_sha256=" + census_hash not in cb.splitlines()
                or "slots_expected=56" not in rb.splitlines()
                or "slots_expected=56" not in cb.splitlines()
                or github_anchor_report.get("roster_precedes_first_decision_claim") is not True
                or github_anchor_report.get("census_precedes_target_claim") is not True):
            failures.append("GITHUB_ANCHOR_HASHES_OR_CHRONOLOGY_INVALID")
        # GitHubCommentClaim is not a provider API result; independent attestation
        # still requires a separate authenticated network connector read.

    out["blockers"] = failures
    if failures:
        out["reason"] = "MISSING_OR_CONFLICTING_PROSPECTIVE_EVIDENCE"
    else:
        out["state"] = "LAB_DOCUMENTARY_INPUT_INVENTORY_COMPLETE_UNATTESTED"
        out["reason"] = "INDEPENDENT_BROKER_MACRO_AND_GITHUB_PROOF_STILL_REQUIRED"
    return out


__all__ = ["SCHEMA", "inspect_first_cohort_readiness_lab"]

if __name__ == "__main__":
    # No network or broker side effects. With no supplied evidence, this only
    # prints a reliable inventory of missing prerequisites.
    import json
    report = inspect_first_cohort_readiness_lab(
        as_of_utc=datetime.now(timezone.utc).replace(microsecond=0))
    print(json.dumps(report, indent=2, ensure_ascii=False))
