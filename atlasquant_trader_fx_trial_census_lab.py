"""AtlasQuant: full 28-FX x D1/W1 prospective trial census (offline LAB).

Local hashes and caller-provided times are NOT an independent timestamp witness.
No price feed, macro evidence, directional inference, broker/MT5 IO, or trading.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any

from atlasquant_fx_universe import OFFICIAL_PAIRS

ROSTER_SCHEMA = "ATLASQUANT_FX_TRIAL_ROSTER_LAB_V1"
CENSUS_SCHEMA = "ATLASQUANT_FX_FROZEN_DIRECTION_CENSUS_LAB_V1"
HORIZONS = ("D1", "W1")
DURATIONS = {"D1": timedelta(days=1), "W1": timedelta(days=7)}
SIDES = frozenset(("ALTA", "BAIXA", "AGUARDAR"))
WAIT_REASONS = frozenset((
    "MISSING_DATA", "STALE_DATA", "W1_D1_CONFLICT", "MACRO_CONTRADICTION",
    "EVENT_BLACKOUT", "REGIME_VETO", "INSUFFICIENT_CONFIDENCE",
    "UNVERIFIED_SOURCE", "OTHER_RESEARCH_ONLY",
))
_HEX = re.compile(r"[a-f0-9]{64}\Z")
_ID = re.compile(r"[A-Z0-9][A-Z0-9_-]{3,31}\Z")
_VERSION = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{1,63}\Z")


@dataclass(frozen=True)
class FrozenBlob:
    canonical_json: str
    sha256: str


@dataclass(frozen=True)
class TrialDecision:
    opportunity_id: str
    side: str
    recorded_at: datetime
    evidence_cutoff_at: datetime
    baseline_eligible: bool
    regime_veto: bool | None
    abstention_reason: str | None
    evidence_sha256_claim: str | None
    model_version: str


def _clock(value: Any) -> datetime | None:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        return None
    return value.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 35:
        return None
    try:
        return _clock(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, TypeError, OverflowError):
        return None


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def _pack(value: dict[str, Any]) -> FrozenBlob:
    raw = _json(value)
    return FrozenBlob(raw, sha256(raw.encode("ascii")).hexdigest())


def _base(schema: str, reason: str) -> dict[str, Any]:
    return {
        "schema": schema, "state": "LAB_BLOCKED", "reason": reason,
        "frozen": None, "sha256": None, "slots_expected": 56,
        "slots_recorded": 0, "awaiting_count": 0,
        "hypotheses_count": 0, "baseline_eligible_count": 0,
        "regime_veto_count": 0, "per_horizon": {},
        "full_28fx_d1_w1_roster_checked": False,
        "hash_consistent_local_only": False,
        "external_precommit_timestamp_verified": False,
        "source_vintages_authenticated": False,
        "real_market_outcomes_loaded": False,
        "directional_accuracy_validated": False,
        "validated_accuracy": None, "calibrated_direction_probability": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _roster_payload(cohort_id: Any, periods: Any, plan_frozen_at: Any,
                    rule_version: Any) -> tuple[dict[str, Any] | None, str]:
    at = _clock(plan_frozen_at)
    if (not isinstance(cohort_id, str) or _ID.fullmatch(cohort_id) is None
            or not isinstance(rule_version, str) or _VERSION.fullmatch(rule_version) is None
            or at is None or not isinstance(periods, dict)
            or set(periods) != set(HORIZONS)
            or len(OFFICIAL_PAIRS) != 28 or len(set(OFFICIAL_PAIRS)) != 28):
        return None, "INVALID_ROSTER_SCOPE_OR_CLOCK"
    openings: dict[str, str] = {}
    targets: dict[str, tuple[datetime, datetime]] = {}
    for tf in HORIZONS:
        item = periods[tf]
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            return None, "INVALID_TARGET_WINDOW"
        start, end = _clock(item[0]), _clock(item[1])
        if start is None or end is None or not at < start or end - start != DURATIONS[tf]:
            return None, "INVALID_TARGET_WINDOW"
        targets[tf] = (start, end)
        openings[tf] = _stamp(start)
    slots = [
        {"id": f"{cohort_id}_{asset.replace('/', '')}_{tf}",
         "asset": asset, "horizon": tf,
         "target_open_utc": openings[tf],
         "target_close_utc": _stamp(targets[tf][1])}
        for tf in HORIZONS for asset in OFFICIAL_PAIRS
    ]
    if len({row["id"] for row in slots}) != 56:
        return None, "DUPLICATE_OPPORTUNITY_ID"
    return {
        "schema": ROSTER_SCHEMA, "cohort_id": cohort_id,
        "rule_version": rule_version,
        "plan_frozen_utc_claim": _stamp(at), "slots": slots,
    }, "OK"


def freeze_fx_trial_roster_lab(*, cohort_id: Any, target_windows_by_horizon: Any,
                                plan_frozen_at: Any, rule_version: Any) -> dict[str, Any]:
    """Declare ALL 56 future candle targets before recording any outcomes."""
    out = _base(ROSTER_SCHEMA, "INVALID_ROSTER")
    obj, reason = _roster_payload(cohort_id, target_windows_by_horizon,
                                  plan_frozen_at, rule_version)
    if obj is None:
        out["reason"] = reason
        return out
    blob = _pack(obj)
    out.update({"state": "LAB_ROSTER_HASHED_UNATTESTED",
                "reason": "ROSTER_HASH_IS_NOT_AN_EXTERNAL_PRECOMMITMENT",
                "frozen": blob, "sha256": blob.sha256,
                "full_28fx_d1_w1_roster_checked": True,
                "hash_consistent_local_only": True})
    return out


def _verified_roster(blob: Any) -> dict[str, Any] | None:
    if (not isinstance(blob, FrozenBlob) or not isinstance(blob.canonical_json, str)
            or len(blob.canonical_json) > 30000 or not isinstance(blob.sha256, str)
            or _HEX.fullmatch(blob.sha256) is None):
        return None
    try:
        obj = json.loads(blob.canonical_json)
        if (_json(obj) != blob.canonical_json
                or sha256(blob.canonical_json.encode("ascii")).hexdigest() != blob.sha256
                or not isinstance(obj, dict) or set(obj) != {
                    "schema", "cohort_id", "rule_version", "plan_frozen_utc_claim", "slots"}
                or obj["schema"] != ROSTER_SCHEMA or not isinstance(obj["slots"], list)
                or len(obj["slots"]) != 56):
            return None
        targets = {}
        for tf in HORIZONS:
            first = obj["slots"][0 if tf == "D1" else 28]
            targets[tf] = (_parse(first["target_open_utc"]),
                           _parse(first["target_close_utc"]))
        canonical, status = _roster_payload(
            obj["cohort_id"], targets,
            _parse(obj["plan_frozen_utc_claim"]), obj["rule_version"])
        if status != "OK" or _pack(canonical) != blob:
            return None
        return obj
    except (ValueError, TypeError, UnicodeEncodeError, KeyError, IndexError,
            OverflowError, RecursionError):
        return None


def _valid_decision(d: Any, *, expected_id: str, planned_at: datetime,
                    frozen_at: datetime, target_open_at: datetime,
                    rule_version: str) -> dict[str, Any] | None:
    if (not isinstance(d, TrialDecision) or not isinstance(d.opportunity_id, str)
            or d.opportunity_id != expected_id):
        return None
    recorded, evidence = _clock(d.recorded_at), _clock(d.evidence_cutoff_at)
    if (recorded is None or evidence is None or not planned_at <= recorded <= frozen_at
            or not evidence <= recorded or not frozen_at < target_open_at
            or d.model_version != rule_version
            or not isinstance(d.side, str) or d.side not in SIDES
            or type(d.baseline_eligible) is not bool
            or (d.regime_veto is not None and type(d.regime_veto) is not bool)
            or (d.abstention_reason is not None and
                (not isinstance(d.abstention_reason, str)
                 or d.abstention_reason not in WAIT_REASONS))
            or (d.evidence_sha256_claim is not None and
                (not isinstance(d.evidence_sha256_claim, str)
                 or _HEX.fullmatch(d.evidence_sha256_claim) is None))):
        return None
    if d.side == "AGUARDAR":
        if d.baseline_eligible or d.regime_veto is not None or d.abstention_reason is None:
            return None
    else:
        if d.evidence_sha256_claim is None:
            return None
        if d.baseline_eligible:
            if d.regime_veto is None or d.abstention_reason is not None:
                return None
        elif d.regime_veto is not None or d.abstention_reason is None:
            return None
    return {
        "id": expected_id, "side": d.side, "recorded_utc_claim": _stamp(recorded),
        "evidence_cutoff_utc_claim": _stamp(evidence),
        "baseline_eligible": d.baseline_eligible,
        "regime_veto": d.regime_veto, "abstention_reason": d.abstention_reason,
        "evidence_sha256_claim": d.evidence_sha256_claim,
        "model_version": d.model_version,
    }


def freeze_full_fx_direction_census_lab(roster: Any, decisions: Any, *,
                                         census_frozen_at: Any) -> dict[str, Any]:
    """Lock a complete declared opportunity denominator; zero inferred FX sides."""
    out = _base(CENSUS_SCHEMA, "INVALID_ROSTER_OR_CENSUS_CLOCK")
    plan, now = _verified_roster(roster), _clock(census_frozen_at)
    if plan is None or now is None or not isinstance(decisions, (tuple, list)):
        return out
    plan_at = _parse(plan["plan_frozen_utc_claim"])
    if now < plan_at or len(decisions) != 56:
        out["reason"] = "MISSING_OR_EXTRA_CENSUS_SLOT"
        return out
    by_id = {}
    for d in decisions:
        if (not isinstance(d, TrialDecision) or not isinstance(d.opportunity_id, str)
                or d.opportunity_id in by_id):
            out["reason"] = "DUPLICATE_OR_INVALID_SLOT_DECISION"
            return out
        by_id[d.opportunity_id] = d
    expected = {slot["id"] for slot in plan["slots"]}
    if set(by_id) != expected:
        out["reason"] = "CENSUS_IDS_DIFFER_FROM_PREDECLARED_ROSTER"
        return out
    validated = []
    for slot in plan["slots"]:
        row = _valid_decision(
            by_id[slot["id"]], expected_id=slot["id"], planned_at=plan_at,
            frozen_at=now, target_open_at=_parse(slot["target_open_utc"]),
            rule_version=plan["rule_version"])
        if row is None:
            out["reason"] = "INVALID_OR_LATE_DECISION_OR_EVIDENCE"
            return out
        validated.append(row)
    document = {
        "schema": CENSUS_SCHEMA, "roster_sha256": roster.sha256,
        "cohort_id": plan["cohort_id"], "census_frozen_utc_claim": _stamp(now),
        "decisions": validated,
    }
    blob = _pack(document)
    counts = {tf: {"AGUARDAR": 0, "ALTA": 0, "BAIXA": 0} for tf in HORIZONS}
    for planned, decision in zip(plan["slots"], validated):
        counts[planned["horizon"]][decision["side"]] += 1
    out.update({
        "state": "LAB_FULL_CENSUS_HASHED_UNATTESTED",
        "reason": "CENSUS_COMPLETE_BUT_TIMESTAMPS_AND_SOURCE_CLAIMS_UNATTESTED",
        "frozen": blob, "sha256": blob.sha256,
        "slots_recorded": len(validated),
        "awaiting_count": sum(d["side"] == "AGUARDAR" for d in validated),
        "hypotheses_count": sum(d["side"] != "AGUARDAR" for d in validated),
        "baseline_eligible_count": sum(d["baseline_eligible"] for d in validated),
        "regime_veto_count": sum(d["regime_veto"] is True for d in validated),
        "per_horizon": counts,
        "full_28fx_d1_w1_roster_checked": True,
        "hash_consistent_local_only": True,
    })
    return out


def verify_frozen_fx_census_lab(roster: Any, census: Any) -> dict[str, Any]:
    """Recreate exact bytes and semantics; hashes never prove actual creation time."""
    out = _base(CENSUS_SCHEMA, "BAD_OR_CHANGED_CENSUS_BYTES")
    plan = _verified_roster(roster)
    if (plan is None or not isinstance(census, FrozenBlob)
            or not isinstance(census.canonical_json, str)
            or len(census.canonical_json) > 50000
            or not isinstance(census.sha256, str)
            or _HEX.fullmatch(census.sha256) is None):
        return out
    try:
        doc = json.loads(census.canonical_json)
        if (not isinstance(doc, dict) or set(doc) != {
                "schema", "roster_sha256", "cohort_id",
                "census_frozen_utc_claim", "decisions"}
                or doc["schema"] != CENSUS_SCHEMA
                or doc["roster_sha256"] != roster.sha256
                or doc["cohort_id"] != plan["cohort_id"]
                or _json(doc) != census.canonical_json
                or _pack(doc) != census
                or not isinstance(doc["decisions"], list)
                or len(doc["decisions"]) != 56):
            return out
        restored = []
        for d in doc["decisions"]:
            if not isinstance(d, dict) or set(d) != {
                    "id", "side", "recorded_utc_claim", "evidence_cutoff_utc_claim",
                    "baseline_eligible", "regime_veto", "abstention_reason",
                    "evidence_sha256_claim", "model_version"}:
                return out
            restored.append(TrialDecision(
                opportunity_id=d["id"], side=d["side"],
                recorded_at=_parse(d["recorded_utc_claim"]),
                evidence_cutoff_at=_parse(d["evidence_cutoff_utc_claim"]),
                baseline_eligible=d["baseline_eligible"],
                regime_veto=d["regime_veto"],
                abstention_reason=d["abstention_reason"],
                evidence_sha256_claim=d["evidence_sha256_claim"],
                model_version=d["model_version"],
            ))
        rerun = freeze_full_fx_direction_census_lab(
            roster, restored, census_frozen_at=_parse(doc["census_frozen_utc_claim"]))
        if rerun["frozen"] != census:
            return out
        return rerun
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError,
            UnicodeEncodeError):
        return out


__all__ = [
    "ROSTER_SCHEMA", "CENSUS_SCHEMA", "HORIZONS", "WAIT_REASONS",
    "FrozenBlob", "TrialDecision", "freeze_fx_trial_roster_lab",
    "freeze_full_fx_direction_census_lab", "verify_frozen_fx_census_lab",
]
