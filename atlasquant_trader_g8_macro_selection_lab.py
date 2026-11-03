"""AtlasQuant Trader: predeclared G8 macro indicator choice (LAB synthetic).

An indicator-selection plan is chosen before the synthetic research window
and is required to match every supplied event, without cherry-picking
alternatives after observing macro figures or future FX prices.

No source custody, live market data, economic direction, portfolio signal,
API, scheduler, worker or transaction is permitted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from atlasquant_fx_universe import CURRENCIES, OFFICIAL_PAIRS
from atlasquant_trader_macro_surprise_pit_lab import INDICATORS, UNITS
from atlasquant_trader_g8_macro_context_lab import (
    GROUPS, GROUP_BY_INDICATOR, compare_g8_macro_coverage_lab,
)

SCHEMA = "ATLASQUANT_TRADER_G8_MACRO_SELECTION_POLICY_LAB_V1"
METHOD = "SYNTHETIC_PRESPECIFIED_ONE_INDICATOR_PER_CURRENCY_GROUP_V1"
MAX_PLAN_ITEMS = len(CURRENCIES) * len(GROUPS)
IDENTIFIER = re.compile(r"^[A-Za-z0-9:_-]{3,90}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
POLICY_FIELDS = frozenset((
    "state", "method_id", "policy_id", "registered_at_utc",
    "experiment_start_at_utc", "selections",
))
SELECTION_FIELDS = frozenset((
    "currency", "group", "indicator_id", "unit", "rationale",
))
FREEZE_FIELDS = frozenset((
    "schema", "state", "policy_document", "policy_digest",
    "lab_declared_freeze_at_utc", "custody_independent_verified",
    "real_precommit_time_verified", "trade_authorized",
    "worker_enabled", "scheduler_enabled",
))


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 60:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _deny(reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "state": "LAB_MACRO_POLICY_REJECTED",
        "reason": reason, "policy_digest": None,
        "currency_selection_matrix": {},
        "pair_comparisons": {},
        "real_precommit_time_verified": False,
        "real_historical_data_verified": False,
        "actual_macro_predictive_uplift_proven": False,
        "currency_direction_inferred": False,
        "trade_authorized": False,
        "worker_enabled": False,
        "scheduler_enabled": False,
    }


def _validate_policy(policy: Any) -> tuple[dict[str, Any], datetime, datetime] | str:
    if not isinstance(policy, Mapping) or set(policy) != POLICY_FIELDS:
        return "Missing or extra policy fields"
    if policy.get("state") != "LAB_SYNTHETIC_G8_MACRO_POLICY":
        return "Only synthetic policies are supported"
    if policy.get("method_id") != METHOD:
        return "Unsupported selection method"
    identity = policy.get("policy_id")
    if not isinstance(identity, str) or not IDENTIFIER.fullmatch(identity):
        return "Invalid research policy ID"
    registered = _utc(policy.get("registered_at_utc"))
    start = _utc(policy.get("experiment_start_at_utc"))
    if registered is None or start is None or registered >= start:
        return "Policy registration must precede the synthetic study window"
    selections = policy.get("selections")
    if not isinstance(selections, list) or len(selections) != MAX_PLAN_ITEMS:
        return "Exactly 32 pre-selected G8 group indicators are required"
    expected = {(c, g) for c in CURRENCIES for g in GROUPS}
    seen = set()
    normalized = []
    for item in selections:
        if not isinstance(item, Mapping) or set(item) != SELECTION_FIELDS:
            return "Missing or extra preselected indicator fields"
        c, group, indicator, unit = (
            item.get("currency"), item.get("group"),
            item.get("indicator_id"), item.get("unit"),
        )
        rationale = item.get("rationale")
        if (not all(isinstance(x, str) for x in (c, group, indicator, unit))
                or c not in CURRENCIES or group not in GROUPS
                or indicator not in INDICATORS or unit not in UNITS
                or GROUP_BY_INDICATOR.get(indicator) != group):
            return "Indicator, currency, unit or fundamental group is invalid"
        if (not isinstance(rationale, str)
                or not 12 <= len(rationale.strip()) <= 250):
            return "Rationale must be bounded and declared before results"
        if (c, group) in seen:
            return "Duplicate indicator-selection slot"
        seen.add((c, group))
        normalized.append({
            "currency": c, "group": group, "indicator_id": indicator,
            "unit": unit, "rationale": rationale.strip(),
        })
    if seen != expected:
        return "Incomplete canonical 8 by 4 research selection"
    doc = {
        "state": "LAB_SYNTHETIC_G8_MACRO_POLICY",
        "method_id": METHOD, "policy_id": identity,
        "registered_at_utc": registered.isoformat(),
        "experiment_start_at_utc": start.isoformat(),
        "selections": sorted(
            normalized, key=lambda x: (x["currency"], x["group"])
        ),
    }
    return doc, registered, start


def _digest(doc: dict[str, Any]) -> str:
    return sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True,
                             allow_nan=False, separators=(",", ":"))
                  .encode("utf-8")).hexdigest()


def freeze_g8_macro_indicator_policy_lab(
    policy: Any, *, research_at: datetime,
) -> dict[str, Any]:
    """Freeze a synthetic plan before a synthetic test window (not trusted custody)."""
    if not isinstance(research_at, datetime) or research_at.tzinfo is None:
        raise ValueError("LAB research clock must include timezone")
    parsed = _validate_policy(policy)
    if isinstance(parsed, str):
        return _deny(parsed)
    document, registered, start = parsed
    research_now = research_at.astimezone(timezone.utc)
    if not registered <= research_now < start:
        return _deny("Synthetic policy freeze not in pre-experiment window")
    return {
        "schema": SCHEMA, "state": "LAB_SYNTHETIC_POLICY_CONTENT_FROZEN",
        "policy_document": document, "policy_digest": _digest(document),
        "lab_declared_freeze_at_utc": research_now.isoformat(),
        "custody_independent_verified": False,
        "real_precommit_time_verified": False,
        "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
    }


def compare_preselected_g8_macro_lab(
    frozen_policy: Any, events: Any, *,
    forecast_issued_at: datetime, evaluated_at: datetime,
    freshness_days: int = 90,
) -> dict[str, Any]:
    """Accept only exactly selected macro fixtures; no fallback or signals."""
    if (not isinstance(forecast_issued_at, datetime)
            or forecast_issued_at.tzinfo is None
            or not isinstance(evaluated_at, datetime)
            or evaluated_at.tzinfo is None):
        raise ValueError("Forecast and audit clocks require timezone")
    issued = forecast_issued_at.astimezone(timezone.utc)
    audit = evaluated_at.astimezone(timezone.utc)
    if issued > audit:
        return _deny("Forecast cannot be evaluated before issuance")
    if (not isinstance(frozen_policy, Mapping)
            or set(frozen_policy) != FREEZE_FIELDS
            or frozen_policy.get("schema") != SCHEMA
            or frozen_policy.get("state") != "LAB_SYNTHETIC_POLICY_CONTENT_FROZEN"
            or any(frozen_policy.get(x) is not False for x in (
                "custody_independent_verified", "real_precommit_time_verified",
                "trade_authorized", "worker_enabled", "scheduler_enabled",
            ))):
        return _deny("Policy is not an isolated LAB predeclared artifact")
    parsed = _validate_policy(frozen_policy.get("policy_document"))
    if isinstance(parsed, str):
        return _deny(parsed)
    doc, registered, start = parsed
    published = frozen_policy.get("policy_digest")
    declared_freeze = _utc(frozen_policy.get("lab_declared_freeze_at_utc"))
    if (not isinstance(published, str) or not SHA.fullmatch(published)
            or published != _digest(doc) or declared_freeze is None
            or not registered <= declared_freeze < start <= issued):
        return _deny("Policy hash or pre-experiment research clock does not match")
    if not isinstance(events, (list, tuple)) or not 1 <= len(events) <= MAX_PLAN_ITEMS:
        return _deny("No bounded synthetic event list")
    by_slot = {(x["currency"], x["group"]): x for x in doc["selections"]}
    observed = set()
    for item in events:
        if not isinstance(item, Mapping) or set(item) != {"preliminary", "actual_release"}:
            return _deny("Unexpected macro event fields")
        pre = item.get("preliminary")
        if not isinstance(pre, Mapping):
            return _deny("Missing pre-release macro event")
        ccy, indicator, unit = (
            pre.get("currency"), pre.get("indicator_id"), pre.get("unit"),
        )
        if not isinstance(ccy, str) or not isinstance(indicator, str):
            return _deny("Invalid macro currency or indicator")
        group = GROUP_BY_INDICATOR.get(indicator)
        key = (ccy, group)
        selected = by_slot.get(key)
        if (selected is None or not isinstance(unit, str)
                or indicator != selected["indicator_id"]
                or unit != selected["unit"] or key in observed):
            return _deny("Macro event not in original policy or duplicated")
        observed.add(key)
    lower = compare_g8_macro_coverage_lab(
        events, forecast_issued_at=issued, evaluated_at=audit,
        freshness_days=freshness_days,
    )
    if lower["state"] != "LAB_SYNTHETIC_G8_MACRO_CONTEXT_ONLY":
        return _deny("Underlying point-in-time macro comparison failed: "
                     + lower["reason"])
    matrix = {}
    for ccy in CURRENCIES:
        groups = {}
        for group in GROUPS:
            selection = by_slot[(ccy, group)]
            measured = lower["currency_matrix"][ccy]["groups"][group]
            groups[group] = {
                **selection,
                "evidence_state": (
                    measured["state"] if measured else "SELECTED_INDICATOR_NOT_REPORTED"
                ),
                "no_post_hoc_substitution": True,
                "macro_direction": "UNDETERMINED",
            }
        matrix[ccy] = groups
    return {
        "schema": SCHEMA, "state": "LAB_PRESELECTED_G8_CONTEXT_ONLY",
        "policy_id": doc["policy_id"],
        "method_id": METHOD,
        "predeclared_policy_digest": published,
        "predeclared_indicator_slots": MAX_PLAN_ITEMS,
        "reported_synthetic_events": len(events),
        "currency_count": len(CURRENCIES), "pair_count": len(OFFICIAL_PAIRS),
        "currency_selection_matrix": matrix,
        "pair_comparisons": lower["pair_comparisons"],
        "synthetic_freeze_evidences": lower["synthetic_freeze_evidences"],
        "automatic_macro_vetoes": [],
        "market_direction": "UNDETERMINED",
        "real_precommit_time_verified": False,
        "real_historical_data_verified": False,
        "actual_macro_predictive_uplift_proven": False,
        "currency_direction_inferred": False,
        "trade_authorized": False,
        "worker_enabled": False, "scheduler_enabled": False,
        "why_not": "This preselection hash is caller-produced and cannot "
                   "prove historical custody, model validation or market edge.",
    }


__all__ = [
    "SCHEMA", "METHOD", "freeze_g8_macro_indicator_policy_lab",
    "compare_preselected_g8_macro_lab",
]
