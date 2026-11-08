"""Read-only G8 policy-expectations change versus proposed D1/W1 direction.

Policy-path moves are *documentary hypotheses*: none of the caller-supplied
quotes, times, or fingerprints are independently authenticated. Even an
alignment is never a probability, trading bias, or proof of predictive edge.
Always returns operational AGUARDAR and zero network/filesystem effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS, split_pair

SCHEMA = "ATLASQUANT_TRADER_POLICY_EXPECTATIONS_CONTRADICTION_LAB_V1"
TENOR_MONTHS = 3  # uniform research comparison; not equal CB policy meeting dates
METHODOLOGY = "IMPLIED_POLICY_RATE_3M_BPS_RESEARCH_CLAIM"
MIN_RELATIVE_CHANGE_BPS = Decimal("5")  # hypothesis threshold, NOT calibrated
MAX_CAPTURE_LAG = timedelta(hours=4)
MAX_CROSS_CURRENCY_SKEW = timedelta(hours=6)
MIN_VINTAGE_GAP = timedelta(hours=24)
MAX_VINTAGE_GAP = timedelta(days=14)
MAX_NEW_VINTAGE_AGE = {"D1": timedelta(days=3), "W1": timedelta(days=10)}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])\Z")
_ID = re.compile(r"[A-Z0-9_.:-]{3,80}\Z")


@dataclass(frozen=True)
class RateExpectationVintage:
    currency: str
    observed_at: datetime
    captured_at: datetime
    target_month: str
    tenor_months: int
    expected_policy_rate_bps: str
    instrument_id: str
    methodology_claim: str
    source_sha256_claim: str


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _num(value: Any) -> Decimal | None:
    if not isinstance(value, str) or not 1 <= len(value) <= 24:
        return None
    try:
        n = Decimal(value)
    except InvalidOperation:
        return None
    return n if n.is_finite() and abs(n) <= Decimal("5000") else None


def _base(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_RATE_EXPECTATION_INPUT_BLOCKED",
        "reason": reason, "horizon": None, "as_of_utc": None,
        "currency_states": {}, "pair_rows": [], "pair_count": 0,
        "documentary_contradictions": 0, "documentary_alignments": 0,
        "pair_context_unavailable": 0,
        "market_implied_quotes_independently_authenticated": False,
        "instrument_comparability_independently_verified": False,
        "point_in_time_vintages_independently_verified": False,
        "news_surprise_independently_authenticated": False,
        "regime_state_independently_verified": False,
        "historical_predictive_increment_validated": False,
        "directional_accuracy_validated": None,
        "calibrated_direction_probability": None,
        "fx_bias": None, "index_bias": None,
        "operational_bias": "AGUARDAR", "publishable": False,
        "live_alert_allowed": False, "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "http_requests": 0, "file_writes": 0, "new_cost_brl": 0,
        "research_only": True,
    }


def _check_two_vintages(rows: Any, currency: str, asof: datetime, horizon: str) -> dict[str, Any]:
    failed = {"status": "MISSING_INVALID_STALE_OR_UNVERIFIED_RATE_PATH", "change_bps": None}
    if not isinstance(rows, (tuple, list)) or len(rows) != 2:
        return failed
    prior, current = rows
    if not all(isinstance(x, RateExpectationVintage) for x in rows):
        return failed
    if any(x.currency != currency or type(x.tenor_months) is not int
           or x.tenor_months != TENOR_MONTHS or x.methodology_claim != METHODOLOGY
           or not isinstance(x.instrument_id, str) or _ID.fullmatch(x.instrument_id) is None
           or not isinstance(x.target_month, str) or _MONTH.fullmatch(x.target_month) is None
           or not isinstance(x.source_sha256_claim, str) or _SHA.fullmatch(x.source_sha256_claim) is None
           for x in rows):
        return failed
    if (prior.instrument_id != current.instrument_id or prior.target_month != current.target_month
            or prior.source_sha256_claim == current.source_sha256_claim):
        return failed
    # A fixed target-month must not already have expired before the newer quote.
    if current.target_month < asof.strftime("%Y-%m"):
        return failed
    old_observed, new_observed = _utc(prior.observed_at), _utc(current.observed_at)
    old_capture, new_capture = _utc(prior.captured_at), _utc(current.captured_at)
    if any(x is None for x in (old_observed, new_observed, old_capture, new_capture)):
        return failed
    if (not old_observed <= old_capture < new_observed <= new_capture <= asof
            or old_capture - old_observed > MAX_CAPTURE_LAG
            or new_capture - new_observed > MAX_CAPTURE_LAG
            or not MIN_VINTAGE_GAP <= new_observed - old_observed <= MAX_VINTAGE_GAP
            or asof - new_capture > MAX_NEW_VINTAGE_AGE[horizon]):
        return failed
    old_n, new_n = _num(prior.expected_policy_rate_bps), _num(current.expected_policy_rate_bps)
    if old_n is None or new_n is None:
        return failed
    return {"status": "TWO_VINTAGES_DOCUMENTARY_ONLY_UNATTESTED",
            "change_bps": str(new_n - old_n),
            "old_capture_utc": old_capture.isoformat(),
            "new_capture_utc": new_capture.isoformat(),
            "old_observed_utc": old_observed.isoformat(),
            "new_observed_utc": new_observed.isoformat(),
            "target_month": current.target_month,
            "instrument_id": current.instrument_id}


def inspect_policy_expectation_contradictions_lab(
    snapshots_by_currency: Any, *, horizon: Any, as_of_utc: Any,
    candidate_directions: Any = None,
) -> dict[str, Any]:
    """Inspect relative changes of claimed 3-month policy-rate expectations.

    If a proposed pair ALTA/BAIXA opposes a sufficiently clear shift in
    (base - quote) expectation change, expose a *research contradiction*.
    Agreement never validates a signal. No data here is authenticated.
    """
    out = _base("INVALID_UNIVERSE_HORIZON_CLOCK_OR_CURRENCY_MAP")
    now = _utc(as_of_utc)
    if (now is None or not isinstance(horizon, str) or horizon not in MAX_NEW_VINTAGE_AGE
            or not isinstance(snapshots_by_currency, dict)
            or set(snapshots_by_currency) != set(CURRENCIES)
            or len(CURRENCIES) != 8 or len(OFFICIAL_PAIRS) != 28):
        return out
    if candidate_directions is None:
        candidate_directions = {}
    if (not isinstance(candidate_directions, Mapping)
            or any(p not in OFFICIAL_PAIRS or d not in ("ALTA", "BAIXA", "NEUTRO")
                   or type(p) is not str or type(d) is not str
                   for p, d in candidate_directions.items())):
        return _base("INVALID_RESEARCH_CANDIDATES")
    c_states = {c: _check_two_vintages(snapshots_by_currency[c], c, now, horizon)
                for c in CURRENCIES}
    contradictions = alignments = unavailable = 0
    pair_rows: list[dict[str, Any]] = []
    for pair in OFFICIAL_PAIRS:
        base, quote = split_pair(pair)
        b, q = c_states[base], c_states[quote]
        candidate = candidate_directions.get(pair)
        delta = None
        comparison = "RATE_PATH_EVIDENCE_UNAVAILABLE"
        if b["change_bps"] is not None and q["change_bps"] is not None:
            old_skew = abs(datetime.fromisoformat(b["old_observed_utc"]) - datetime.fromisoformat(q["old_observed_utc"]))
            new_skew = abs(datetime.fromisoformat(b["new_observed_utc"]) - datetime.fromisoformat(q["new_observed_utc"]))
            if b["target_month"] != q["target_month"] or old_skew > MAX_CROSS_CURRENCY_SKEW or new_skew > MAX_CROSS_CURRENCY_SKEW:
                comparison = "CURRENCY_QUOTE_WINDOWS_OR_TARGET_MONTH_INCOMPARABLE"
            else:
                shift = Decimal(b["change_bps"]) - Decimal(q["change_bps"])
                delta = str(shift)
                if candidate is None or candidate == "NEUTRO":
                    comparison = "NO_DIRECTIONAL_RESEARCH_CANDIDATE"
                elif abs(shift) < MIN_RELATIVE_CHANGE_BPS:
                    comparison = "DIFFERENTIAL_SHIFT_TOO_SMALL_RESEARCH_ONLY"
                elif ((candidate == "ALTA" and shift < 0)
                      or (candidate == "BAIXA" and shift > 0)):
                    comparison = "DOCUMENTARY_RATE_EXPECTATION_CONTRADICTION"
                    contradictions += 1
                else:
                    comparison = "DOCUMENTARY_RATE_EXPECTATION_ALIGNMENT_NOT_PROOF"
                    alignments += 1
        if comparison in ("RATE_PATH_EVIDENCE_UNAVAILABLE", "CURRENCY_QUOTE_WINDOWS_OR_TARGET_MONTH_INCOMPARABLE"):
            unavailable += 1
        pair_rows.append({
            "pair": pair, "base": base, "quote": quote,
            "horizon": horizon, "candidate_direction_claim": candidate,
            "base_expected_policy_rate_change_bps_claim": b["change_bps"],
            "quote_expected_policy_rate_change_bps_claim": q["change_bps"],
            "base_minus_quote_change_bps_documentary": delta,
            "comparison": comparison,
            "contradiction_veto_for_research_only": comparison == "DOCUMENTARY_RATE_EXPECTATION_CONTRADICTION",
            "source_independently_attested": False,
            "D1": "AGUARDAR", "W1": "AGUARDAR",
            "operational_bias": "AGUARDAR", "trade_authorized": False,
        })
    out.update({
        "state": "LAB_28FX_POLICY_EXPECTATION_CONTRADICTION_DIAGNOSTIC_NO_GO",
        "reason": "RATE_PATH_CLAIMS_NOT_SOURCE_ATTESTED_OR_CALIBRATED",
        "horizon": horizon, "as_of_utc": now.isoformat(),
        "currency_states": c_states, "pair_rows": pair_rows, "pair_count": len(pair_rows),
        "documentary_contradictions": contradictions,
        "documentary_alignments": alignments, "pair_context_unavailable": unavailable,
    })
    return out


def inspect_policy_expectations_d1_w1_lab(
    *, snapshots_by_horizon: Any, decision_at_by_horizon: Any,
    candidate_directions_by_horizon: Any, as_of_utc: Any,
) -> dict[str, Any]:
    """Review D1/W1 at *their separate* historical cutoffs, never at wall time.

    Only explicit per-horizon vintages are allowed: a later D1 capture must
    never be reused as evidence for a previous weekly cutoff. This helper
    prepares an audit-facing pair matrix, not a publishing feed.
    """
    out = _base("INVALID_D1_W1_SNAPSHOT_OR_DECISION_TIMELINE")
    now = _utc(as_of_utc)
    if (now is None or not all(isinstance(x, dict) and set(x) == {"D1", "W1"}
                              for x in (snapshots_by_horizon, decision_at_by_horizon,
                                        candidate_directions_by_horizon))):
        return out
    daily = _utc(decision_at_by_horizon["D1"])
    weekly = _utc(decision_at_by_horizon["W1"])
    if daily is None or weekly is None or not weekly <= daily <= now:
        return out
    reports = {}
    for horizon, cutoff in (("W1", weekly), ("D1", daily)):
        report = inspect_policy_expectation_contradictions_lab(
            snapshots_by_horizon[horizon], horizon=horizon, as_of_utc=cutoff,
            candidate_directions=candidate_directions_by_horizon[horizon],
        )
        if report["state"] != "LAB_28FX_POLICY_EXPECTATION_CONTRADICTION_DIAGNOSTIC_NO_GO":
            out["reason"] = f"{horizon}_RATE_PATH_RESEARCH_INPUT_INVALID"
            return out
        reports[horizon] = report
    w, d = reports["W1"], reports["D1"]
    rows = []
    for week, day in zip(w["pair_rows"], d["pair_rows"]):
        if week["pair"] != day["pair"]:
            return out
        conflicted = (week["contradiction_veto_for_research_only"]
                      or day["contradiction_veto_for_research_only"])
        unassessable = any(row["comparison"] in (
            "RATE_PATH_EVIDENCE_UNAVAILABLE",
            "CURRENCY_QUOTE_WINDOWS_OR_TARGET_MONTH_INCOMPARABLE",
        ) for row in (week, day))
        rows.append({
            "pair": week["pair"], "W1_comparison": week["comparison"],
            "D1_comparison": day["comparison"],
            "research_contradiction_in_either_horizon": conflicted,
            "rate_data_unavailable_or_incomparable_in_either_horizon": unassessable,
            "research_candidate_requires_review": conflicted or unassessable,
            "operational_bias": "AGUARDAR", "publishable": False,
        })
    out.update({
        "state": "LAB_D1_W1_POLICY_EXPECTATION_REVIEW_NO_GO",
        "reason": "HISTORICAL_VINTAGES_ARE_CLAIMED_NOT_INDEPENDENTLY_ATTESTED",
        "horizon": "D1_AND_W1", "as_of_utc": now.isoformat(),
        "pair_count": len(rows), "pair_rows": rows,
        "D1_decision_utc": daily.isoformat(), "W1_decision_utc": weekly.isoformat(),
        "documentary_contradictions": sum(r["research_contradiction_in_either_horizon"] for r in rows),
        "pair_context_unavailable": sum(r["rate_data_unavailable_or_incomparable_in_either_horizon"] for r in rows),
        "by_horizon": reports,
    })
    return out


__all__ = ["SCHEMA", "RateExpectationVintage", "inspect_policy_expectation_contradictions_lab",
           "inspect_policy_expectations_d1_w1_lab"]
