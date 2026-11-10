"""Two-slot XAUUSD D1/W1 predeclared forecast/outcome cohort (offline LAB).

This prevents *silent* omission within a declared gold cohort. Local SHA and
caller-provided dates do NOT establish an external pre-event timestamp, broker
authenticity, model performance or independently validated hit rates.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import re
from typing import Any

from atlasquant_mt5_xauusd_archive_audit_lab import (
    MAX_CSV_BYTES, audit_xauusd_closedbar_archive_lab,
)

SCHEMA = "ATLASQUANT_TRADER_XAUUSD_D1W1_PROSPECTIVE_COHORT_LAB_V1"
HORIZONS = ("D1", "W1")
SECONDS = {"D1": 86400, "W1": 604800}
SIDES = ("UP", "DOWN", "ABSTAIN")
ABSTAIN_REASONS = frozenset(("MISSING_DATA", "STALE_DATA", "MACRO_CONFLICT",
                             "EVENT_BLACKOUT", "UNVERIFIED_SOURCE",
                             "LOW_CONFIDENCE", "NO_EDGE", "OTHER_RESEARCH"))
ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,47}\Z")
VERSION = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{1,63}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_BLOB_BYTES = 12_000


@dataclass(frozen=True)
class GoldDecision:
    horizon: str
    side: str
    decided_at: datetime
    evidence_cutoff_at: datetime
    model_version: str
    evidence_sha256_claim: str | None
    abstention_reason: str | None


def _utc(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond != 0):
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _from_stamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z") or len(value) != 20:
        return None
    try:
        instant = _utc(datetime.fromisoformat(value[:-1] + "+00:00"))
        return instant if instant is not None and _stamp(instant) == value else None
    except (ValueError, OverflowError, TypeError):
        return None


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_GOLD_PROSPECTIVE_COHORT_BLOCKED",
        "reason": reason, "asset": "METAL:XAUUSD",
        "slots_expected": 2, "slots_verified": 0,
        "directional_claims": 0, "abstentions": 0,
        "local_precommit_json": None, "local_precommit_sha256": None,
        "local_forecast_hash_self_consistent": False,
        "external_prediction_timestamp_authenticated": False,
        "complete_opportunity_roster_externally_anchored": False,
        "source_vintages_authenticated": False,
        "broker_candles_authenticated": False,
        "broker_calendar_utc_authenticated": False,
        "historical_point_in_time_verified": False,
        "archived_gold_outcomes_checked": False,
        "documentary_outcomes_by_horizon": {},
        "documentary_directional_matches": None,
        "documentary_directional_trials": None,
        "out_of_sample_accuracy_validated": False,
        "validated_accuracy": None, "calibrated_probability": None,
        "operational_bias": "AGUARDAR", "can_feed_live_radar": False,
        "publishable": False, "trade_authorized": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
    }


def freeze_gold_two_horizon_cohort_lab(
    *, cohort_id: Any, target_windows: Any, decisions: Any,
    planned_at_utc: Any, frozen_at_utc: Any, model_version: Any,
) -> dict[str, Any]:
    """Freeze both future D1/W1 opportunities, INCLUDING abstentions.

    Fixed 24/168h are nominal bar windows only. This blocks DST/calendar
    anomalies until the broker's actual timestamps are independently checked.
    """
    out = _blocked("INVALID_COHORT_AND_FREEZE_FIELDS")
    planned, frozen = _utc(planned_at_utc), _utc(frozen_at_utc)
    if (not isinstance(cohort_id, str) or ID.fullmatch(cohort_id) is None
            or not isinstance(model_version, str) or VERSION.fullmatch(model_version) is None
            or planned is None or frozen is None or planned > frozen
            or not isinstance(target_windows, dict) or set(target_windows) != set(HORIZONS)
            or not isinstance(decisions, (list, tuple)) or len(decisions) != 2):
        return out
    by_horizon: dict[str, GoldDecision] = {}
    for item in decisions:
        if (not isinstance(item, GoldDecision) or item.horizon not in HORIZONS
                or item.horizon in by_horizon):
            out["reason"] = "DUPLICATE_OR_INVALID_GOLD_DECISION"
            return out
        by_horizon[item.horizon] = item
    if set(by_horizon) != set(HORIZONS):
        out["reason"] = "MISSING_GOLD_HORIZON_DECISION"
        return out
    rows = []
    for horizon in HORIZONS:
        window = target_windows[horizon]
        if not isinstance(window, (tuple, list)) or len(window) != 2:
            out["reason"] = "INVALID_TARGET_CANDLE_WINDOW"
            return out
        start, end = (_utc(t) for t in window)
        d = by_horizon[horizon]
        decided, evidence = _utc(d.decided_at), _utc(d.evidence_cutoff_at)
        if (start is None or end is None or end - start != timedelta(seconds=SECONDS[horizon])
                or not frozen < start or decided is None or evidence is None
                or not planned <= evidence <= decided <= frozen
                or d.model_version != model_version or d.side not in SIDES):
            out["reason"] = "TARGET_OR_FORECAST_AFTER_START_OR_EVIDENCE_LEAKAGE"
            return out
        if d.side == "ABSTAIN":
            if (not isinstance(d.abstention_reason, str)
                    or d.abstention_reason not in ABSTAIN_REASONS
                    or d.evidence_sha256_claim is not None):
                out["reason"] = "ABSTENTION_REASON_OR_HASH_INVALID"
                return out
        elif (d.abstention_reason is not None or not isinstance(d.evidence_sha256_claim, str)
              or HEX64.fullmatch(d.evidence_sha256_claim) is None):
            out["reason"] = "DIRECTIONAL_FORECAST_EVIDENCE_CLAIM_INVALID"
            return out
        rows.append({
            "opportunity_id": f"{cohort_id}_XAUUSD_{horizon}",
            "asset": "METAL:XAUUSD", "horizon": horizon, "side_claim": d.side,
            "target_open_utc_claim": _stamp(start), "target_close_utc_claim": _stamp(end),
            "decided_at_utc_claim": _stamp(decided),
            "evidence_cutoff_utc_claim": _stamp(evidence),
            "model_version": model_version,
            "evidence_sha256_claim": d.evidence_sha256_claim,
            "abstention_reason": d.abstention_reason,
        })
    payload = {
        "schema": SCHEMA, "cohort_id": cohort_id,
        "planned_at_utc_claim": _stamp(planned),
        "frozen_at_utc_claim": _stamp(frozen),
        "model_version": model_version, "slots": rows,
    }
    stable = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=True, allow_nan=False)
    digest = sha256(stable.encode("ascii")).hexdigest()
    out.update({
        "state": "LAB_GOLD_TWO_SLOT_FORECAST_FROZEN_UNATTESTED",
        "reason": "LOCAL_SHA_CANNOT_PROVE_FORECAST_EXISTED_BEFORE_TARGET",
        "slots_verified": 2,
        "directional_claims": sum(v.side != "ABSTAIN" for v in by_horizon.values()),
        "abstentions": sum(v.side == "ABSTAIN" for v in by_horizon.values()),
        "local_precommit_json": stable, "local_precommit_sha256": digest,
        "local_forecast_hash_self_consistent": True,
    })
    return out


def _reconstruct_frozen(value: Any, digest: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        return None
    if (len(encoded) > MAX_BLOB_BYTES
            or not isinstance(digest, str) or HEX64.fullmatch(digest) is None
            or sha256(encoded).hexdigest() != digest):
        return None
    try:
        payload = json.loads(value)
        if (not isinstance(payload, dict) or set(payload) != {
                "schema", "cohort_id", "planned_at_utc_claim",
                "frozen_at_utc_claim", "model_version", "slots"}
                or payload["schema"] != SCHEMA or not isinstance(payload["slots"], list)
                or len(payload["slots"]) != 2):
            return None
        windows = {}
        decisions = []
        for item in payload["slots"]:
            if (not isinstance(item, dict) or set(item) != {
                    "opportunity_id", "asset", "horizon", "side_claim",
                    "target_open_utc_claim", "target_close_utc_claim",
                    "decided_at_utc_claim", "evidence_cutoff_utc_claim",
                    "model_version", "evidence_sha256_claim", "abstention_reason"}
                    or item["asset"] != "METAL:XAUUSD"
                    or item["opportunity_id"] != f'{payload["cohort_id"]}_XAUUSD_{item["horizon"]}'):
                return None
            windows[item["horizon"]] = (
                _from_stamp(item["target_open_utc_claim"]),
                _from_stamp(item["target_close_utc_claim"]))
            decisions.append(GoldDecision(
                horizon=item["horizon"], side=item["side_claim"],
                decided_at=_from_stamp(item["decided_at_utc_claim"]),
                evidence_cutoff_at=_from_stamp(item["evidence_cutoff_utc_claim"]),
                model_version=item["model_version"],
                evidence_sha256_claim=item["evidence_sha256_claim"],
                abstention_reason=item["abstention_reason"],
            ))
        checked = freeze_gold_two_horizon_cohort_lab(
            cohort_id=payload["cohort_id"], target_windows=windows,
            decisions=decisions,
            planned_at_utc=_from_stamp(payload["planned_at_utc_claim"]),
            frozen_at_utc=_from_stamp(payload["frozen_at_utc_claim"]),
            model_version=payload["model_version"])
        if (checked["state"] != "LAB_GOLD_TWO_SLOT_FORECAST_FROZEN_UNATTESTED"
                or checked["local_precommit_json"] != value
                or checked["local_precommit_sha256"] != digest):
            return None
        return payload
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError,
            UnicodeError, RecursionError):
        return None


def assess_gold_two_horizon_outcomes_lab(
    frozen_json: Any, frozen_sha256: Any, *, outcome_archive: Any,
    evaluated_at_utc: Any,
) -> dict[str, Any]:
    """Resolve both declared targets from a later independently audited CSV set.

    This only compares self-consistent local claims with future candle bodies;
    results are NOT a validated hit rate without external precommit proof.
    """
    out = _blocked("LOCAL_PRECOMMIT_RECEIPT_INVALID_OR_CHANGED")
    plan = _reconstruct_frozen(frozen_json, frozen_sha256)
    evaluation = _utc(evaluated_at_utc)
    if plan is None or evaluation is None or not isinstance(outcome_archive, Path):
        return out
    out["slots_verified"] = 2
    out["local_forecast_hash_self_consistent"] = True
    out["directional_claims"] = sum(row["side_claim"] != "ABSTAIN" for row in plan["slots"])
    out["abstentions"] = 2 - out["directional_claims"]
    audit = audit_xauusd_closedbar_archive_lab(outcome_archive)
    if audit["status"] != "LOCAL_XAUUSD_ARCHIVE_INTEGRITY_PASS_UNATTESTED":
        out["reason"] = "FUTURE_GOLD_ARCHIVE_INTEGRITY_FAILED"
        return out
    try:
        captured = datetime.strptime(outcome_archive.name, "XAUUSD_%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc)
    except (ValueError, TypeError):
        out["reason"] = "OUTCOME_CAPTURE_CLOCK_INVALID"
        return out
    if evaluation < captured:
        out["reason"] = "OUTCOME_ARCHIVE_NOT_AVAILABLE_AT_EVALUATION"
        return out
    results = {}
    for row in plan["slots"]:
        tf = row["horizon"]
        target_start = _from_stamp(row["target_open_utc_claim"])
        target_end = _from_stamp(row["target_close_utc_claim"])
        if target_end is None or target_end > captured:
            out["reason"] = "TARGET_CANDLE_NOT_CLOSED_BEFORE_OUTCOME_CAPTURE"
            return out
        target_path = outcome_archive / f"XAUUSD_{tf}_closedbar.csv.gz"
        try:
            with gzip.open(target_path, "rb") as zipped:
                raw = zipped.read(MAX_CSV_BYTES + 1)
            if (len(raw) > MAX_CSV_BYTES or sha256(raw).hexdigest() !=
                    audit["timeframes"][tf]["sha256_uncompressed_csv"]):
                raise ValueError("ARCHIVE_CHANGED_AFTER_AUDIT")
            reader = csv.DictReader(StringIO(raw.decode("utf-8")))
            selected = [x for x in reader if int(x["time_utc_epoch"]) == int(target_start.timestamp())]
            if len(selected) != 1:
                raise ValueError("DECLARED_TARGET_NOT_FOUND_EXACTLY_ONCE")
            opening = Decimal(selected[0]["open"])
            closing = Decimal(selected[0]["close"])
            if (not opening.is_finite() or not closing.is_finite()
                    or opening <= 0 or closing <= 0):
                raise ValueError("TARGET_PRICE_INVALID")
        except (OSError, EOFError, TypeError, KeyError, ValueError,
                InvalidOperation, UnicodeError, OverflowError) as exc:
            out["reason"] = "DECLARED_GOLD_OUTCOME_UNRESOLVED:" + str(exc)[:55]
            return out
        observed = "UP" if closing > opening else "DOWN" if closing < opening else "FLAT"
        direction = row["side_claim"]
        results[tf] = {
            "target_open_utc_local_claim": row["target_open_utc_claim"],
            "declared_side_claim": direction,
            "observed_candle_body_documentary": observed,
            "body_move_bps_documentary": str(((closing / opening) - 1) * 10000),
            "documentary_match_only": None if direction == "ABSTAIN" else direction == observed,
            "csv_hash_locally_consistent": True,
            "outcome_timestamp_and_broker_identity_unattested": True,
        }
    out.update({
        "state": "LAB_GOLD_TWO_HORIZON_OUTCOMES_DOCUMENTARY_NO_GO",
        "reason": "COMPLETE_LOCAL_COHORT_ONLY_NO_EXTERNAL_FORECAST_TIMESTAMP_OR_BROKER_WITNESS",
        "archived_gold_outcomes_checked": True,
        "documentary_outcomes_by_horizon": results,
        "documentary_directional_trials": out["directional_claims"],
        "documentary_directional_matches": sum(
            item["documentary_match_only"] is True for item in results.values()),
    })
    return out


__all__ = ["SCHEMA", "GoldDecision", "freeze_gold_two_horizon_cohort_lab",
           "assess_gold_two_horizon_outcomes_lab"]
