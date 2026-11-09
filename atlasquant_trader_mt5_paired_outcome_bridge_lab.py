"""P0 LAB: read-only link from recorded FX hypotheses to archived MT5 outcomes.

This is a *documentary* bridge, not a retroactive prediction source. All
opportunity fields and freeze times are asserted by the caller; hashes and
chronology checks cannot establish an independent pre-event timestamp. Do not
feed live Radar, issue trades, or quote results as validated accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_mt5_closedbar_outcome_lab import inspect_mt5_closedbar_outcome_lab
from atlasquant_trader_regime_increment_benchmark_lab import (
    DirectionalCase, PredeclaredWindow, evaluate_regime_increment_lab,
)

SCHEMA = "ATLASQUANT_MT5_FORECAST_OUTCOME_PAIRED_BRIDGE_LAB_V1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,79}\Z")
MAX_CASES = 2000


@dataclass(frozen=True)
class RecordedFxHypothesis:
    opportunity_id: str
    asset: str
    horizon: str
    candidate_direction: str
    prediction_locked_at: datetime
    decided_at: datetime
    regime_observed_at: datetime
    target_open_epoch: int
    baseline_eligible: bool
    regime_veto: bool
    decision_sha256_claim: str
    regime_source_sha256_claim: str


def _utc(v: Any) -> datetime | None:
    if not isinstance(v, datetime) or v.tzinfo is None or v.utcoffset() is None:
        return None
    return v.astimezone(timezone.utc)


def _blocked(reason: str, *, count: int = 0, detail: str | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_PAIRED_OUTCOME_BRIDGE_BLOCKED",
        "reason": reason, "detail_documentary": detail,
        "expected_opportunities": count, "resolved_outcomes": 0,
        "benchmark": None, "full_declared_manifest_reconciled": False,
        "per_target_local_snapshot_hash_checked": False,
        "original_source_broker_verified": False,
        "historical_price_available_at_prediction_verified": False,
        "predictions_externally_precommitted": False,
        "opportunity_manifest_externally_precommitted": False,
        "regime_rules_precommitted": False,
        "validated_directional_accuracy": None,
        "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "new_cost_brl": 0, "file_writes": 0,
        "research_only": True,
    }


def evaluate_paired_mt5_outcomes_lab(
    hypotheses: Any, *, expected_opportunity_ids: Any,
    predeclared_windows: Any, archive_root: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Resolve ALL declared D1/W1 trials from verified local archive bytes.

    Fail closed on any absent/altered target. The supplied forecast manifest,
    directions, regime classifications, cutoff times and windows are NOT
    independently fixed or verified; retrospective cherry-picking remains a
    risk even if the local outcome labels and paired arithmetic are valid.
    """
    now = _utc(as_of_utc)
    if (now is None or not isinstance(hypotheses, (tuple, list))
            or not isinstance(expected_opportunity_ids, (tuple, list))
            or not isinstance(predeclared_windows, (tuple, list))
            or not 1 <= len(expected_opportunity_ids) <= MAX_CASES
            or len(hypotheses) != len(expected_opportunity_ids)
            or not isinstance(archive_root, (str, Path))):
        return _blocked("INVALID_MANIFEST_OR_INPUT")
    ids = list(expected_opportunity_ids)
    if (len(set(ids)) != len(ids)
            or any(not isinstance(x, str) or ID.fullmatch(x) is None for x in ids)):
        return _blocked("DUPLICATE_OR_INVALID_EXPECTED_IDS")
    out = _blocked("UNRESOLVED", count=len(ids))
    if any(not isinstance(h, RecordedFxHypothesis) for h in hypotheses):
        out["reason"] = "INVALID_HYPOTHESIS_TYPE"
        return out
    if len({h.opportunity_id for h in hypotheses}) != len(hypotheses) or {
        h.opportunity_id for h in hypotheses
    } != set(ids):
        out["reason"] = "MANIFEST_MISMATCH_NO_SILENT_OMISSION"
        return out
    asset, horizon = hypotheses[0].asset, hypotheses[0].horizon
    if (asset not in OFFICIAL_PAIRS or horizon not in ("D1", "W1")
            or any(h.asset != asset or h.horizon != horizon for h in hypotheses)):
        out["reason"] = "MIXED_OR_UNSUPPORTED_ASSET_HORIZON"
        return out
    symbol = asset.replace("/", "")
    expected_target_epochs: set[int] = set()
    for h in hypotheses:
        if (h.candidate_direction not in ("ALTA", "BAIXA")
                or type(h.baseline_eligible) is not bool
                or type(h.regime_veto) is not bool
                or type(h.target_open_epoch) is not int or h.target_open_epoch <= 0
                or any(not isinstance(x, str) or HEX64.fullmatch(x) is None
                       for x in (h.decision_sha256_claim, h.regime_source_sha256_claim))):
            out["reason"] = "INVALID_FROZEN_HYPOTHESIS_SEMANTICS"
            return out
        locked, decided, regime = (
            _utc(h.prediction_locked_at), _utc(h.decided_at),
            _utc(h.regime_observed_at),
        )
        if (locked is None or decided is None or regime is None
                or not locked <= decided <= now or not regime <= decided
                or not regime <= locked):
            out["reason"] = "INVALID_OR_FUTURE_PREDICTION_TIMESTAMPS"
            return out
        if h.target_open_epoch in expected_target_epochs:
            out["reason"] = "DUPLICATE_TARGET_CANDLE"
            return out
        expected_target_epochs.add(h.target_open_epoch)

    cases: list[DirectionalCase] = []
    # Intentionally resolve every target against the immutable-by-hash local
    # CSV manifest; no missing outcome is silently removed from denominator.
    for h in hypotheses:
        single = inspect_mt5_closedbar_outcome_lab(
            archive_root=archive_root, symbol=symbol, horizon=horizon,
            target_open_epoch=h.target_open_epoch, decided_at=h.decided_at,
            prediction_locked_at=h.prediction_locked_at, as_of_utc=now,
            prediction_sha256_claim=h.decision_sha256_claim,
        )
        if (single["state"] != "LAB_ARCHIVED_BAR_DOCUMENTARY_ONLY_NO_GO"
                or not single["raw_csv_sha256_verified"]):
            out["reason"] = "UNRESOLVED_DECLARED_OUTCOME_NO_SUBSETTING"
            out["detail_documentary"] = single["reason"]
            return out
        cases.append(DirectionalCase(
            opportunity_id=h.opportunity_id, asset=h.asset,
            horizon=h.horizon, candidate_direction=h.candidate_direction,
            decided_at=h.decided_at, regime_observed_at=h.regime_observed_at,
            target_open_at=datetime.fromisoformat(single["target_open_utc"]),
            target_close_at=datetime.fromisoformat(single["target_close_utc"]),
            actual_observed_at=datetime.fromisoformat(single["manifest_observed_at_utc"]),
            start_price=single["start_price_documentary"],
            end_price=single["end_price_documentary"],
            baseline_eligible=h.baseline_eligible, regime_veto=h.regime_veto,
            decision_sha256_claim=h.decision_sha256_claim,
            regime_source_sha256_claim=h.regime_source_sha256_claim,
            price_source_sha256_claim=single["raw_csv_sha256"],
        ))

    benchmark = evaluate_regime_increment_lab(
        cases, expected_opportunity_ids=ids,
        predeclared_windows=predeclared_windows, as_of_utc=now,
    )
    if (benchmark["state"] not in (
            "LAB_PAIRED_COMPARISON_DESCRIPTIVE_UNATTESTED_NO_GO",
            "LAB_SAMPLE_INSUFFICIENT_FOR_DESCRIPTIVE_COMPARISON",
    )):
        out["reason"] = "PAIRED_BENCHMARK_REJECTED"
        out["detail_documentary"] = benchmark["reason"]
        return out
    out.update({
        "state": "LAB_MATCHED_MT5_OUTCOMES_DOCUMENTARY_NO_GO",
        "reason": "ARCHIVED_PRICE_BYTES_MATCH_ONLY_FORECASTS_AND_REGIME_UNATTESTED",
        "resolved_outcomes": len(cases),
        "benchmark": benchmark,
        "full_declared_manifest_reconciled": True,
        "per_target_local_snapshot_hash_checked": True,
    })
    return out


__all__ = ["SCHEMA", "RecordedFxHypothesis", "evaluate_paired_mt5_outcomes_lab"]
