"""Point-in-time macro release VINTAGES: synthetic, offline LAB only.

A revised macro figure belongs to its own publication/receipt clock. The
original actual/consensus surprise cannot be rewritten with that revision.
All archival timestamps are caller supplied: strict sequence checks prove
only internal logic, NEVER independent historical availability.

No HTTP, fetching, real FX bias, trading, scheduler, worker or costs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping, Sequence

from atlasquant_trader_macro_surprise_pit_lab import (
    build_macro_point_in_time_evidence_lab,
)

SCHEMA = "ATLASQUANT_TRADER_MACRO_VINTAGES_ASOF_LAB_V1"
VINTAGE_KEYS = frozenset((
    "state", "event_id", "revision_sequence", "release_stage",
    "actual", "released_at_utc", "captured_at_utc", "source",
))
MAX_VINTAGES = 24


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        stamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo is not None else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    try:
        out = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return out if isfinite(out) and abs(out) <= 1e9 else None


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_VINTAGE_REFUSED",
        "reason": reason, "original_release_evidence": None,
        "revision_context_asof": None, "forecast_safe_evidence": None,
        "real_timestamps_attested": False, "original_source_attested": False,
        "macro_prediction_accuracy_proven": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def inspect_macro_vintages_asof_lab(
    preliminary: Any, vintages: Any, *, forecast_issued_at: datetime,
    evaluated_at: datetime,
) -> dict[str, Any]:
    """Choose only the last *received* revision before forecast cutoff.

    Initial publication remains intact, with its initial surprise. A later
    revised value is a separately labeled CONTEXT, not a retroactively
    improved original macro surprise. This function never produces an
    automatic directional macro veto or valid real backtest sample.
    """
    if (not isinstance(forecast_issued_at, datetime)
            or forecast_issued_at.tzinfo is None
            or not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None):
        raise ValueError("Research/evaluation clocks require a timezone")
    issued = forecast_issued_at.astimezone(timezone.utc)
    audit = evaluated_at.astimezone(timezone.utc)
    if issued > audit:
        return _deny("Forecast is later than research evaluation")
    if not isinstance(vintages, (list, tuple)) or not 1 <= len(vintages) <= MAX_VINTAGES:
        return _deny("Exactly one original and at most 23 revisions required")
    checked = []
    event_id = None
    prior_publication = None
    prior_capture = None
    for index, raw in enumerate(vintages):
        if not isinstance(raw, Mapping) or set(raw) != VINTAGE_KEYS:
            return _deny("Unexpected field or incomplete archive vintage")
        if raw.get("state") != "LAB_SYNTHETIC_MACRO_VINTAGE":
            return _deny("Only explicitly synthetic archive vintages allowed")
        if type(raw.get("revision_sequence")) is not int or raw["revision_sequence"] != index:
            return _deny("Nonsequential or duplicate revision number")
        stage = raw.get("release_stage")
        if stage != ("INITIAL" if index == 0 else "REVISED"):
            return _deny("Original and revision stages must be distinguished")
        ident = raw.get("event_id")
        if not isinstance(ident, str) or not ident or (
            event_id is not None and ident != event_id
        ):
            return _deny("Archive has conflicting release identities")
        event_id = ident
        published = _utc(raw.get("released_at_utc"))
        captured = _utc(raw.get("captured_at_utc"))
        if (published is None or captured is None or captured < published
                or captured > audit
                or prior_publication is not None and (
                    published <= prior_publication or captured <= prior_capture
                )):
            return _deny("Vintage publications/receipts are invalid or retroactive")
        source = raw.get("source")
        actual = _number(raw.get("actual"))
        if (not isinstance(source, str) or not 2 <= len(source.strip()) <= 120
                or actual is None):
            return _deny("Vintage source or numeric reading is invalid")
        checked.append({
            "seq": index, "stage": stage, "published": published,
            "captured": captured, "actual": actual, "source": source.strip(),
        })
        prior_publication = published
        prior_capture = captured
    # Validate initial event against the established PIT surprise contract;
    # use audit as validator clock, not historical forecast cutoff.
    initial = checked[0]
    init_payload = {
        "state": "LAB_SYNTHETIC_MACRO_ACTUAL", "event_id": event_id,
        "actual": initial["actual"],
        "released_at_utc": initial["published"].isoformat(),
        "captured_at_utc": initial["captured"].isoformat(),
        "source": initial["source"],
    }
    source_check = build_macro_point_in_time_evidence_lab(
        preliminary, init_payload, forecast_issued_at=audit, evaluated_at=audit,
    )
    if source_check["state"] != "LAB_MACRO_RELEASED_SYNTHETIC":
        return _deny("Original release or pre-release consensus does not pass PIT validation")
    # Pre-release information must also be known at the historical issue
    # instant. It is not safe to inherit a later consensus capture.
    pre_consensus = _utc(preliminary.get("consensus_captured_at_utc"))
    pre_previous = _utc(preliminary.get("previous_captured_at_utc"))
    if pre_consensus is None or pre_previous is None or (
        pre_previous > issued or pre_consensus > issued
    ):
        return _deny("Preliminary/consensus was not captured by forecast cutoff")
    original = source_check["freeze_evidence"]
    chosen = [row for row in checked if row["captured"] <= issued]
    if not chosen:
        scheduled = _utc(preliminary.get("scheduled_release_at_utc"))
        if scheduled is None:
            return _deny("Scheduled time is missing")
        if scheduled <= issued:
            # No proof of any completed value at that historical instant.
            return _deny("Original publication expected but no received value by cutoff")
        schedule = build_macro_point_in_time_evidence_lab(
            preliminary, forecast_issued_at=issued, evaluated_at=audit,
        )
        if schedule["state"] != "LAB_MACRO_FUTURE_SCHEDULE_ONLY":
            return _deny("No valid pre-cutoff schedule without actual")
        return {
            **_deny(""), "state": "LAB_MACRO_SCHEDULE_ASOF_ONLY", "reason": "",
            "original_release_evidence": None,
            "revision_context_asof": None,
            "forecast_safe_evidence": schedule["freeze_evidence"],
            "selected_stage": "SCHEDULE_ONLY",
            "earliest_evidence_at_utc": pre_consensus.isoformat(),
            "future_revision_values_exposed": False,
        }
    latest = chosen[-1]
    revision_context = None
    if latest["seq"] > 0:
        revision_context = {
            "state": "LAB_SYNTHETIC_REVISION_CONTEXT_ONLY",
            "event_id": event_id, "revision_sequence": latest["seq"],
            "release_stage": latest["stage"],
            "actual_revised_asof": latest["actual"],
            "initial_actual_unchanged": initial["actual"],
            "revision_delta_vs_initial": latest["actual"] - initial["actual"],
            "released_at_utc": latest["published"].isoformat(),
            "captured_at_utc": latest["captured"].isoformat(),
            "source": latest["source"],
            "original_consensus_surprise_is_not_revised": True,
            "can_feed_as_initial_surprise": False,
            "can_feed_macro_veto_directly": False,
            "real_market_available_time_verified": False,
        }
    # An original release is the only price-independent surprise fixture
    # accepted by the existing daily-freeze contract. Later revisions stay
    # separate to prevent the revised value being mislabeled as initial.
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_VINTAGE_ASOF_CONTEXT",
        "forecast_issued_at_utc": issued.isoformat(),
        "selected_stage": latest["stage"],
        "selected_revision_sequence": latest["seq"],
        "selected_actual_asof": latest["actual"],
        "selected_captured_at_utc": latest["captured"].isoformat(),
        "original_surprise_vs_pre_release_consensus": source_check["surprise"],
        "original_release_evidence": original,
        "revision_context_asof": revision_context,
        "forecast_safe_evidence": original,
        "future_revision_values_exposed": False,
        "vintage_clock_proven_by_witness": False,
        "real_timestamps_attested": False,
        "original_source_attested": False,
        "macro_prediction_accuracy_proven": False,
        "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "why_not": "Synthetic archive observations can be backdated by the "
                   "caller. Revisions are not initial surprises and no "
                   "independent historical receipts have been validated.",
    }


__all__ = ["SCHEMA", "inspect_macro_vintages_asof_lab"]
