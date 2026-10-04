"""AION V2.19 provider-neutral model gateway.

Provider-neutral planning and fallback selection for model endpoints. The core
gateway never imports or calls a concrete provider SDK/adapter. External
execution remains delegated to later adapter/execution layers.

The registry supports multiple providers plus a required local/offline fallback.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping, Sequence

SCHEMA = "ATLASQUANT_AION_MODEL_GATEWAY_V2"
HEALTH_SCHEMA = "ATLASQUANT_AION_MODEL_ENDPOINT_HEALTH_V1"
REGISTRY_SCHEMA = "ATLASQUANT_AION_PROVIDER_NEUTRAL_MODEL_REGISTRY_V1"

LANES = ("LOCAL_DETERMINISTIC", "EXTERNAL_FAST", "EXTERNAL_REASONING")
HEALTH_STATES = ("HEALTHY", "DEGRADED", "UNAVAILABLE")
TASK_CLASSES = ("GENERAL", "FAST", "REASONING", "PRIVATE", "OFFLINE")


def _clean(value: Any, limit: int = 256) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())[:limit]


def _exact_bool(value: Any, name: str) -> bool:
    if value is not True and value is not False:
        raise ValueError(f"{name} must be an exact boolean")
    return value is True


def _money(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        number = float(value)
    except Exception as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class ModelEndpoint:
    provider_id: str
    model_id: str
    lane: str
    health_state: str
    local: bool
    zero_cost: bool
    enabled: bool
    priority: int
    capabilities: tuple[str, ...]
    estimated_request_cost_usd: float

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["capabilities"] = list(self.capabilities)
        return row


def endpoint_from_mapping(raw: Mapping[str, Any]) -> ModelEndpoint:
    if not isinstance(raw, Mapping):
        raise ValueError("endpoint mapping required")
    provider = _clean(raw.get("provider_id"), 120)
    model = _clean(raw.get("model_id"), 160)
    lane = _clean(raw.get("lane"), 40).upper()
    health = _clean(raw.get("health_state"), 40).upper()
    if not provider or not model:
        raise ValueError("provider_id/model_id required")
    if lane not in LANES:
        raise ValueError("invalid model lane")
    if health not in HEALTH_STATES:
        raise ValueError("invalid health state")

    local = _exact_bool(raw.get("local"), "local")
    zero_cost = _exact_bool(raw.get("zero_cost"), "zero_cost")
    enabled = _exact_bool(raw.get("enabled"), "enabled")
    priority = raw.get("priority")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 10_000:
        raise ValueError("invalid endpoint priority")

    capabilities_raw = raw.get("capabilities")
    if not isinstance(capabilities_raw, (list, tuple)):
        raise ValueError("capabilities must be a list/tuple")
    capabilities: list[str] = []
    for item in capabilities_raw:
        value = _clean(item, 120).lower()
        if not value or value in capabilities:
            raise ValueError("invalid/duplicate capability")
        capabilities.append(value)

    cost = _money(raw.get("estimated_request_cost_usd"), "estimated_request_cost_usd")
    if local:
        if lane != "LOCAL_DETERMINISTIC":
            raise ValueError("local endpoint must use LOCAL_DETERMINISTIC")
        if zero_cost is not True or cost != 0:
            raise ValueError("local endpoint must be zero-cost in V2.19")
    else:
        if lane == "LOCAL_DETERMINISTIC":
            raise ValueError("external endpoint cannot use local lane")

    return ModelEndpoint(
        provider_id=provider,
        model_id=model,
        lane=lane,
        health_state=health,
        local=local,
        zero_cost=zero_cost,
        enabled=enabled,
        priority=priority,
        capabilities=tuple(sorted(capabilities)),
        estimated_request_cost_usd=round(cost, 6),
    )


class ProviderNeutralModelRegistry:
    def __init__(self, endpoints: Sequence[ModelEndpoint | Mapping[str, Any]]):
        rows: list[ModelEndpoint] = []
        seen = set()
        for item in list(endpoints or []):
            endpoint = item if isinstance(item, ModelEndpoint) else endpoint_from_mapping(item)
            key = (endpoint.provider_id, endpoint.model_id, endpoint.lane)
            if key in seen:
                raise ValueError("duplicate endpoint identity")
            seen.add(key)
            rows.append(endpoint)
        if not rows:
            raise ValueError("at least one model endpoint required")
        self._rows = tuple(rows)

    def endpoints(self) -> tuple[ModelEndpoint, ...]:
        return self._rows

    def local_endpoints(self) -> tuple[ModelEndpoint, ...]:
        return tuple(x for x in self._rows if x.local)

    def external_endpoints(self) -> tuple[ModelEndpoint, ...]:
        return tuple(x for x in self._rows if not x.local)


def evaluate_endpoint_health(
    *,
    success_count: Any,
    failure_count: Any,
    consecutive_failures: Any,
    heartbeat_age_seconds: Any,
    stale_after_seconds: Any = 300,
) -> dict[str, Any]:
    successes = _nonnegative_int(success_count, "success_count")
    failures = _nonnegative_int(failure_count, "failure_count")
    consecutive = _nonnegative_int(consecutive_failures, "consecutive_failures")
    if isinstance(heartbeat_age_seconds, bool):
        raise ValueError("heartbeat_age_seconds must be numeric")
    if isinstance(stale_after_seconds, bool):
        raise ValueError("stale_after_seconds must be numeric")
    try:
        age = float(heartbeat_age_seconds)
        stale = float(stale_after_seconds)
    except Exception as exc:
        raise ValueError("health timing must be numeric") from exc
    if not math.isfinite(age) or age < 0 or not math.isfinite(stale) or stale <= 0:
        raise ValueError("invalid health timing")

    total = successes + failures
    success_rate = (successes / total * 100.0) if total else None
    reasons: list[str] = []

    if age > stale:
        state = "UNAVAILABLE"
        reasons.append("HEARTBEAT_STALE")
    elif consecutive >= 3:
        state = "UNAVAILABLE"
        reasons.append("CONSECUTIVE_FAILURE_LIMIT")
    elif total == 0:
        state = "DEGRADED"
        reasons.append("NO_REQUEST_EVIDENCE")
    elif success_rate is not None and success_rate < 90:
        state = "DEGRADED"
        reasons.append("SUCCESS_RATE_DEGRADED")
    else:
        state = "HEALTHY"

    return {
        "schema": HEALTH_SCHEMA,
        "state": state,
        "success_count": successes,
        "failure_count": failures,
        "success_rate_pct": round(success_rate, 4) if success_rate is not None else None,
        "consecutive_failures": consecutive,
        "heartbeat_age_seconds": age,
        "stale_after_seconds": stale,
        "reasons": reasons,
        "provider_called": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def provider_independence_audit(registry: ProviderNeutralModelRegistry) -> dict[str, Any]:
    if not isinstance(registry, ProviderNeutralModelRegistry):
        raise TypeError("ProviderNeutralModelRegistry required")
    locals_ = list(registry.local_endpoints())
    externals = list(registry.external_endpoints())
    provider_ids = sorted({x.provider_id for x in registry.endpoints()})
    healthy_local = [
        x for x in locals_
        if x.enabled and x.health_state == "HEALTHY"
    ]
    blockers = []
    if not locals_:
        blockers.append("LOCAL_FALLBACK_NOT_CONFIGURED")
    if not healthy_local:
        blockers.append("HEALTHY_LOCAL_FALLBACK_UNAVAILABLE")
    return {
        "schema": REGISTRY_SCHEMA,
        "state": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "endpoint_count": len(registry.endpoints()),
        "provider_ids": provider_ids,
        "provider_count": len(provider_ids),
        "external_provider_count": len({x.provider_id for x in externals}),
        "local_endpoint_count": len(locals_),
        "healthy_local_fallback_count": len(healthy_local),
        "supports_multiple_providers": True,
        "routing_contract_provider_neutral": True,
        "local_fallback_required": True,
        "concrete_provider_adapter_called": False,
        "provider_called": False,
        "execution_allowed": False,
        "executes_action": False,
    }


def _required_lane(task_class: str) -> str:
    if task_class in {"PRIVATE", "OFFLINE"}:
        return "LOCAL_DETERMINISTIC"
    if task_class == "REASONING":
        return "EXTERNAL_REASONING"
    return "EXTERNAL_FAST"


def route_model_request(
    registry: ProviderNeutralModelRegistry,
    *,
    task_class: Any,
    required_capabilities: Sequence[Any] = (),
    privacy_sensitive: Any = False,
    offline_required: Any = False,
    external_models_enabled: Any = False,
    budget_remaining_usd: Any = 0.0,
    max_request_cost_usd: Any = 0.0,
    preferred_provider: Any = "",
    excluded_providers: Sequence[Any] = (),
) -> dict[str, Any]:
    """Plan one deterministic model route without calling any provider."""
    if not isinstance(registry, ProviderNeutralModelRegistry):
        raise TypeError("ProviderNeutralModelRegistry required")

    task = _clean(task_class, 40).upper()
    if task not in TASK_CLASSES:
        raise ValueError("invalid task class")
    private = _exact_bool(privacy_sensitive, "privacy_sensitive")
    offline = _exact_bool(offline_required, "offline_required")
    external_enabled = _exact_bool(external_models_enabled, "external_models_enabled")
    budget = _money(budget_remaining_usd, "budget_remaining_usd")
    max_cost = _money(max_request_cost_usd, "max_request_cost_usd")
    preferred = _clean(preferred_provider, 120)

    capabilities = {
        _clean(x, 120).lower()
        for x in list(required_capabilities or [])
        if _clean(x, 120)
    }
    excluded = {
        _clean(x, 120)
        for x in list(excluded_providers or [])
        if _clean(x, 120)
    }

    force_local = private or offline or not external_enabled
    target_lane = "LOCAL_DETERMINISTIC" if force_local else _required_lane(task)

    def capable(endpoint: ModelEndpoint) -> bool:
        return capabilities.issubset(set(endpoint.capabilities))

    def budget_ok(endpoint: ModelEndpoint) -> bool:
        if endpoint.local:
            return endpoint.estimated_request_cost_usd == 0
        return (
            endpoint.estimated_request_cost_usd <= max_cost
            and endpoint.estimated_request_cost_usd <= budget
        )

    candidates = [
        endpoint
        for endpoint in registry.endpoints()
        if endpoint.enabled
        and endpoint.provider_id not in excluded
        and capable(endpoint)
        and budget_ok(endpoint)
    ]

    healthy = [x for x in candidates if x.health_state == "HEALTHY"]
    degraded = [x for x in candidates if x.health_state == "DEGRADED"]

    def sort_key(endpoint: ModelEndpoint):
        preferred_rank = 0 if preferred and endpoint.provider_id == preferred else 1
        return (
            preferred_rank,
            endpoint.priority,
            endpoint.provider_id,
            endpoint.model_id,
        )

    primary_pool = sorted([x for x in healthy if x.lane == target_lane], key=sort_key)
    fallback_local = sorted(
        [x for x in healthy if x.local and x.lane == "LOCAL_DETERMINISTIC"],
        key=sort_key,
    )
    degraded_local = sorted(
        [x for x in degraded if x.local and x.lane == "LOCAL_DETERMINISTIC"],
        key=sort_key,
    )

    selected: ModelEndpoint | None = primary_pool[0] if primary_pool else None
    route_state = "ROUTE_READY"

    if selected is None and target_lane != "LOCAL_DETERMINISTIC" and fallback_local:
        selected = fallback_local[0]
        route_state = "LOCAL_FALLBACK"
    elif selected is None and target_lane == "LOCAL_DETERMINISTIC" and fallback_local:
        selected = fallback_local[0]
        route_state = "ROUTE_READY"
    elif selected is None and degraded_local:
        selected = degraded_local[0]
        route_state = "DEGRADED_LOCAL_FALLBACK"
    elif selected is None:
        route_state = "BLOCKED"

    fallback_chain = []
    for endpoint in sorted(healthy + degraded, key=sort_key):
        if selected is not None and (
            endpoint.provider_id,
            endpoint.model_id,
            endpoint.lane,
        ) == (
            selected.provider_id,
            selected.model_id,
            selected.lane,
        ):
            continue
        if endpoint.local or endpoint.lane == target_lane:
            fallback_chain.append(endpoint.as_dict())

    blockers = []
    if selected is None:
        blockers.append("NO_ELIGIBLE_MODEL_ROUTE")
    if force_local and selected is not None and not selected.local:
        blockers.append("LOCAL_ROUTE_REQUIRED")
    if selected is not None and not selected.local and not external_enabled:
        blockers.append("EXTERNAL_MODELS_DISABLED")

    selected_row = selected.as_dict() if selected is not None else None
    external_selected = bool(selected is not None and not selected.local)

    return {
        "schema": SCHEMA,
        "state": "BLOCKED" if blockers else route_state,
        "blockers": blockers,
        "task_class": task,
        "target_lane": target_lane,
        "privacy_sensitive": private,
        "offline_required": offline,
        "external_models_enabled": external_enabled,
        "required_capabilities": sorted(capabilities),
        "preferred_provider": preferred,
        "excluded_providers": sorted(excluded),
        "budget_remaining_usd": budget,
        "max_request_cost_usd": max_cost,
        "selected": selected_row,
        "fallback_chain": fallback_chain,
        "external_adapter_required": external_selected,
        "local_fallback_selected": bool(selected is not None and selected.local),
        "provider_called": False,
        "billing_executed": False,
        "execution_allowed": False,
        "executes_action": False,
    }


__all__ = [
    "SCHEMA",
    "HEALTH_SCHEMA",
    "REGISTRY_SCHEMA",
    "LANES",
    "HEALTH_STATES",
    "TASK_CLASSES",
    "ModelEndpoint",
    "endpoint_from_mapping",
    "ProviderNeutralModelRegistry",
    "evaluate_endpoint_health",
    "provider_independence_audit",
    "route_model_request",
]
