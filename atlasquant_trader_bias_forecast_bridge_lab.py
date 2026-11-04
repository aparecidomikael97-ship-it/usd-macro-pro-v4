"""LAB: connect synthetic G8 currency strength to timestamped FX bias research.

Two separate steps intentionally prevent a forecast issuer from reading future
price outcomes: issue_synthetic_bias_batch_lab(books, at), and evaluate supplied
batches after independently provided synthetic settlements. This is NOT a
durable seal, live forecast, credentialed data source or trading permission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping, Sequence

from atlasquant_fx_universe import OFFICIAL_PAIRS
from atlasquant_trader_bias_oos_lab import evaluate_bias_out_of_sample_lab
from atlasquant_trader_fx_strength_from_quotes_lab import (
    METHOD, build_fx_strength_from_quotes_lab,
)

SCHEMA = "ATLASQUANT_FX_BIAS_FORECAST_BRIDGE_LAB_V1"
FIXED_METHOD = METHOD + "_D1W1_CONFIRM_V1"
BATCH_RE = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
HORIZONS = ("D1", "W1", "MN1")
SIDES = ("ALTA", "BAIXA", "NEUTRO", "AGUARDAR")
# Caller-provided batches must still have the exact shape issued by this LAB.
# Otherwise forged "market_verified" or extra probability fields can survive
# into a synthetic evaluation snapshot and be mistaken for real evidence.
BATCH_FIELDS = frozenset((
    "schema", "state", "batch_key", "issued_at_utc", "method_id", "forecasts",
    "counts", "no_settlements_seen_by_issuer", "durable_provenance_verified",
    "market_data_verified", "trade_authorized", "worker_enabled",
    "scheduler_enabled",
))
FORECAST_FIELDS = frozenset((
    "forecast_id", "state", "pair", "horizon", "bias", "method_id",
    "issued_at_utc", "evidence_at_utc", "evidence_kind", "reason",
    "market_verified", "trade_authorized",
))


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return stamp.astimezone(timezone.utc) if stamp.tzinfo else None


def issue_synthetic_bias_batch_lab(
    books: Mapping[str, Any] | None, *, at: datetime, batch_key: str,
) -> dict[str, Any]:
    """Produce 28 x 3 synthetic time-stamped forecasts, without outcomes.

    The D1 *observational* candidate requires both daily direction and W1
    confirmation. The W1 and MN1 bias evaluations stay independent, so
    testing their conditional utility does not silently reuse D1 labels.
    """
    if not isinstance(at, datetime) or at.tzinfo is None:
        raise ValueError("Issuance instant must be timezone aware")
    if not isinstance(batch_key, str) or not BATCH_RE.fullmatch(batch_key):
        raise ValueError("Invalid synthetic batch key")
    now = at.astimezone(timezone.utc)
    summary = build_fx_strength_from_quotes_lab(books, at=now)
    matrix = summary["bias_matrix"]
    statuses = summary["diagnostics"]
    issued = []
    for row in matrix["rows"]:
        for horizon in HORIZONS:
            bias = row["horizons"][horizon]["bias"]
            reason = "Direção sintética para avaliação observacional."
            if horizon == "D1":
                if bias == "NEUTRO":
                    reason = "Diário neutro: não inventar direção."
                elif not row["observational_candidate"]:
                    bias = "AGUARDAR"
                    reason = "Direção diária sem confirmação semanal; bloqueio observacional."
            status = statuses[horizon]
            snapshot = status["strength_snapshot"] if status["state"] == "LAB_COMPUTED" else None
            evidence = _datetime(snapshot["as_of"]) if snapshot else None
            if horizon == "D1" and bias in ("ALTA", "BAIXA"):
                week = statuses["W1"]
                if week["state"] != "LAB_COMPUTED":
                    bias = "AGUARDAR"
                    reason = "Sem evidência da confirmação semanal."
                    evidence = None
                else:
                    week_at = _datetime(week["strength_snapshot"]["as_of"])
                    if evidence is None or week_at is None:
                        bias = "AGUARDAR"
                        reason = "Horário da evidência indisponível."
                    else:
                        evidence = max(evidence, week_at)
            # Explicit abstentions from missing evidence are stamped at issue
            # time as a policy decision, never pretending a market data read.
            if bias == "AGUARDAR" and evidence is None:
                evidence = now
            if evidence is None or evidence > now or bias not in SIDES:
                raise ValueError("Synthetic evidence boundary unexpectedly invalid")
            name = row["pair"].replace("/", "")
            fid = f"{batch_key}-{horizon}-{name}"
            issued.append({
                "forecast_id": fid,
                "state": "LAB_SYNTHETIC_BIAS",
                "pair": row["pair"], "horizon": horizon, "bias": bias,
                "method_id": FIXED_METHOD,
                "issued_at_utc": now.isoformat(),
                "evidence_at_utc": evidence.isoformat(),
                "evidence_kind": ("SYNTHETIC_INPUT" if snapshot else "ABSENT_POLICY"),
                "reason": reason,
                "market_verified": False, "trade_authorized": False,
            })
    if len(issued) != 84 or len({r["forecast_id"] for r in issued}) != 84:
        raise RuntimeError("Canonical G8/28-pair forecast invariant broken")
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_ISSUED",
        "batch_key": batch_key, "issued_at_utc": now.isoformat(),
        "method_id": FIXED_METHOD, "forecasts": issued,
        "counts": {
            h: {side: sum(1 for r in issued
                          if r["horizon"] == h and r["bias"] == side)
                for side in SIDES}
            for h in HORIZONS
        },
        "no_settlements_seen_by_issuer": True,
        "durable_provenance_verified": False,
        "market_data_verified": False,
        "trade_authorized": False, "worker_enabled": False,
        "scheduler_enabled": False,
    }


def evaluate_synthetic_bias_batches_lab(
    batches: Sequence[Mapping[str, Any]] | None,
    settlements: Sequence[Mapping[str, Any]] | None, *,
    split_at: datetime, at: datetime, min_train: int = 30,
    min_test: int = 30, min_test_days: int = 5,
) -> dict[str, Any]:
    """Bridge separately issued synthetic batches to synthetic OOS evaluation.

    Not a ledger: batches/settlements supplied by caller are untrusted.
    Prevents duplicate batches on one issue instant even under different keys.
    """
    if not isinstance(batches, (list, tuple)) or not batches or len(batches) > 100:
        raise ValueError("A bounded collection of synthetic batches is required")
    all_forecasts = []
    keys = set()
    issued_at = set()
    previous = None
    for batch in batches:
        if (not isinstance(batch, Mapping) or set(batch) != BATCH_FIELDS
                or batch.get("schema") != SCHEMA
                or batch.get("state") != "LAB_SYNTHETIC_ISSUED"
                or batch.get("method_id") != FIXED_METHOD
                or batch.get("no_settlements_seen_by_issuer") is not True
                or any(batch.get(flag) is not False for flag in (
                    "durable_provenance_verified", "market_data_verified",
                    "trade_authorized", "worker_enabled", "scheduler_enabled",
                ))):
            raise ValueError("Invalid or falsely verified synthetic forecast batch")
        key = batch.get("batch_key")
        clock = _datetime(batch.get("issued_at_utc"))
        records = batch.get("forecasts")
        if (not isinstance(key, str) or not BATCH_RE.fullmatch(key) or
                key in keys or clock is None or clock in issued_at or
                (previous is not None and clock <= previous) or
                not isinstance(records, list) or len(records) != 84):
            raise ValueError("Duplicate or disordered batch")
        rows = {(row.get("pair"), row.get("horizon")) for row in records
                if isinstance(row, Mapping)}
        if len(rows) != 84 or rows != {(pair, h) for pair in OFFICIAL_PAIRS for h in HORIZONS}:
            raise ValueError("Incomplete canonical batch")
        expected_counts = {
            h: {side: sum(row.get("horizon") == h and row.get("bias") == side
                          for row in records) for side in SIDES}
            for h in HORIZONS
        }
        if batch.get("counts") != expected_counts:
            raise ValueError("Stated category counts differ from issued research rows")
        for row in records:
            evidence = _datetime(row.get("evidence_at_utc"))
            if (set(row) != FORECAST_FIELDS
                    or row.get("issued_at_utc") != clock.isoformat()
                    or row.get("method_id") != FIXED_METHOD
                    or row.get("state") != "LAB_SYNTHETIC_BIAS"
                    or row.get("forecast_id") !=
                    f"{key}-{row['horizon']}-{row['pair'].replace('/', '')}"
                    or row.get("bias") not in SIDES
                    or row.get("market_verified") is not False
                    or row.get("trade_authorized") is not False
                    or row.get("evidence_kind") not in ("SYNTHETIC_INPUT", "ABSENT_POLICY")
                    or (row.get("evidence_kind") == "ABSENT_POLICY"
                        and (row.get("bias") != "AGUARDAR" or evidence != clock))
                    or evidence is None or evidence > clock
                    or not isinstance(row.get("reason"), str)
                    or not 8 <= len(row["reason"].strip()) <= 400):
                raise ValueError("Forecast row has forged provenance, extras or chronology")
        all_forecasts.extend(records)
        previous = clock
        keys.add(key)
        issued_at.add(clock)
    verdict = evaluate_bias_out_of_sample_lab(
        all_forecasts, settlements, split_at=split_at, at=at,
        min_train=min_train, min_test=min_test,
        min_test_days=min_test_days,
    )
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_EVALUATION_ONLY",
        "batch_count": len(batches), "forecast_count": len(all_forecasts),
        "evaluation": verdict,
        "oos_real_proven": False, "immutable_forecasts_verified": False,
        "historical_prices_verified": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


__all__ = [
    "SCHEMA", "FIXED_METHOD", "issue_synthetic_bias_batch_lab",
    "evaluate_synthetic_bias_batches_lab",
]
