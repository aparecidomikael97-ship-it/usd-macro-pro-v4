"""AION V2.19 red-team for provider-neutral model gateway."""
from __future__ import annotations

import pytest

from atlasquant_aion_model_gateway_v2 import (
    ModelEndpoint,
    ProviderNeutralModelRegistry,
    endpoint_from_mapping,
    evaluate_endpoint_health,
    provider_independence_audit,
    route_model_request,
)


def endpoint(
    provider,
    model,
    lane,
    *,
    health="HEALTHY",
    local=False,
    zero_cost=False,
    enabled=True,
    priority=10,
    capabilities=("chat", "reasoning"),
    cost=0.0,
):
    return endpoint_from_mapping({
        "provider_id": provider,
        "model_id": model,
        "lane": lane,
        "health_state": health,
        "local": local,
        "zero_cost": zero_cost,
        "enabled": enabled,
        "priority": priority,
        "capabilities": list(capabilities),
        "estimated_request_cost_usd": cost,
    })


def registry():
    return ProviderNeutralModelRegistry([
        endpoint(
            "local-runtime",
            "local-safe",
            "LOCAL_DETERMINISTIC",
            local=True,
            zero_cost=True,
            priority=50,
            capabilities=("chat", "reasoning", "private"),
            cost=0.0,
        ),
        endpoint(
            "provider-a",
            "fast-a",
            "EXTERNAL_FAST",
            priority=10,
            capabilities=("chat",),
            cost=0.01,
        ),
        endpoint(
            "provider-b",
            "fast-b",
            "EXTERNAL_FAST",
            priority=20,
            capabilities=("chat",),
            cost=0.008,
        ),
        endpoint(
            "provider-b",
            "reason-b",
            "EXTERNAL_REASONING",
            priority=10,
            capabilities=("chat", "reasoning"),
            cost=0.02,
        ),
    ])


def route(reg=None, **overrides):
    kwargs = {
        "task_class": "GENERAL",
        "required_capabilities": ["chat"],
        "privacy_sensitive": False,
        "offline_required": False,
        "external_models_enabled": True,
        "budget_remaining_usd": 1.0,
        "max_request_cost_usd": 0.05,
        "preferred_provider": "",
        "excluded_providers": [],
    }
    kwargs.update(overrides)
    return route_model_request(reg or registry(), **kwargs)


def test_registry_is_provider_neutral_and_has_local_fallback():
    audit = provider_independence_audit(registry())
    assert audit["state"] == "READY"
    assert audit["provider_count"] == 3
    assert audit["external_provider_count"] == 2
    assert audit["healthy_local_fallback_count"] == 1
    assert audit["supports_multiple_providers"] is True
    assert audit["routing_contract_provider_neutral"] is True
    assert audit["concrete_provider_adapter_called"] is False
    assert audit["execution_allowed"] is False


def test_local_endpoint_must_be_local_lane_and_zero_cost():
    with pytest.raises(ValueError):
        endpoint(
            "local",
            "bad",
            "EXTERNAL_FAST",
            local=True,
            zero_cost=True,
        )
    with pytest.raises(ValueError):
        endpoint(
            "local",
            "bad",
            "LOCAL_DETERMINISTIC",
            local=True,
            zero_cost=False,
            cost=0.01,
        )


def test_external_endpoint_cannot_claim_local_lane():
    with pytest.raises(ValueError):
        endpoint(
            "provider-x",
            "bad",
            "LOCAL_DETERMINISTIC",
            local=False,
            zero_cost=False,
        )


@pytest.mark.parametrize("bad", ["provider-a", {"provider": "x"}, 123, None])
def test_registry_requires_explicit_endpoint_collection(bad):
    with pytest.raises(ValueError):
        ProviderNeutralModelRegistry(bad)


def test_registry_rejects_non_endpoint_entries():
    with pytest.raises(ValueError):
        ProviderNeutralModelRegistry([object()])


def test_duplicate_endpoint_identity_is_rejected():
    row = endpoint(
        "local",
        "m",
        "LOCAL_DETERMINISTIC",
        local=True,
        zero_cost=True,
    )
    with pytest.raises(ValueError):
        ProviderNeutralModelRegistry([row, row])


def test_health_is_healthy_with_fresh_success_evidence():
    result = evaluate_endpoint_health(
        success_count=100,
        failure_count=1,
        consecutive_failures=0,
        heartbeat_age_seconds=10,
        stale_after_seconds=300,
    )
    assert result["state"] == "HEALTHY"
    assert result["provider_called"] is False


def test_health_without_request_evidence_is_degraded_not_fabricated_healthy():
    result = evaluate_endpoint_health(
        success_count=0,
        failure_count=0,
        consecutive_failures=0,
        heartbeat_age_seconds=10,
    )
    assert result["state"] == "DEGRADED"
    assert "NO_REQUEST_EVIDENCE" in result["reasons"]


def test_stale_or_repeated_failure_marks_endpoint_unavailable():
    stale = evaluate_endpoint_health(
        success_count=100,
        failure_count=0,
        consecutive_failures=0,
        heartbeat_age_seconds=301,
        stale_after_seconds=300,
    )
    failed = evaluate_endpoint_health(
        success_count=100,
        failure_count=3,
        consecutive_failures=3,
        heartbeat_age_seconds=1,
    )
    assert stale["state"] == "UNAVAILABLE"
    assert failed["state"] == "UNAVAILABLE"


@pytest.mark.parametrize("field,value", [
    ("success_count", True),
    ("failure_count", -1),
    ("heartbeat_age_seconds", float("nan")),
    ("stale_after_seconds", 0),
])
def test_invalid_health_evidence_is_rejected(field, value):
    kwargs = {
        "success_count": 1,
        "failure_count": 0,
        "consecutive_failures": 0,
        "heartbeat_age_seconds": 1,
        "stale_after_seconds": 300,
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        evaluate_endpoint_health(**kwargs)


def test_general_external_route_uses_best_priority_provider():
    result = route()
    assert result["state"] == "ROUTE_READY"
    assert result["selected"]["provider_id"] == "provider-a"
    assert result["selected"]["model_id"] == "fast-a"
    assert result["external_adapter_required"] is True
    assert result["provider_called"] is False
    assert result["billing_executed"] is False
    assert result["execution_allowed"] is False


def test_reasoning_route_selects_reasoning_lane():
    result = route(
        task_class="REASONING",
        required_capabilities=["reasoning"],
    )
    assert result["selected"]["provider_id"] == "provider-b"
    assert result["selected"]["lane"] == "EXTERNAL_REASONING"


def test_preferred_provider_can_win_between_eligible_peers():
    result = route(preferred_provider="provider-b")
    assert result["selected"]["provider_id"] == "provider-b"
    assert result["selected"]["model_id"] == "fast-b"


def test_excluded_provider_is_never_selected():
    result = route(excluded_providers=["provider-a"])
    assert result["selected"]["provider_id"] == "provider-b"


def test_privacy_sensitive_forces_local_even_when_external_is_healthy():
    result = route(
        privacy_sensitive=True,
        required_capabilities=["private"],
    )
    assert result["selected"]["provider_id"] == "local-runtime"
    assert result["selected"]["local"] is True
    assert result["target_lane"] == "LOCAL_DETERMINISTIC"
    assert result["provider_called"] is False


def test_offline_required_forces_local():
    result = route(offline_required=True)
    assert result["selected"]["local"] is True
    assert result["external_adapter_required"] is False


def test_external_feature_disabled_forces_local():
    result = route(external_models_enabled=False)
    assert result["selected"]["local"] is True
    assert result["provider_called"] is False


def test_external_cost_over_budget_falls_back_local():
    result = route(
        budget_remaining_usd=0.005,
        max_request_cost_usd=0.05,
    )
    assert result["state"] == "LOCAL_FALLBACK"
    assert result["selected"]["local"] is True


def test_external_cost_over_request_ceiling_falls_back_local():
    result = route(
        budget_remaining_usd=1.0,
        max_request_cost_usd=0.005,
    )
    assert result["state"] == "LOCAL_FALLBACK"
    assert result["selected"]["local"] is True


def test_unhealthy_external_provider_falls_back_to_other_or_local():
    reg = ProviderNeutralModelRegistry([
        endpoint(
            "local",
            "local",
            "LOCAL_DETERMINISTIC",
            local=True,
            zero_cost=True,
            priority=50,
            capabilities=("chat",),
        ),
        endpoint(
            "provider-a",
            "fast-a",
            "EXTERNAL_FAST",
            health="UNAVAILABLE",
            priority=1,
            capabilities=("chat",),
            cost=0.01,
        ),
    ])
    result = route(reg)
    assert result["state"] == "LOCAL_FALLBACK"
    assert result["selected"]["local"] is True


def test_healthy_second_provider_replaces_unavailable_first_provider():
    reg = ProviderNeutralModelRegistry([
        endpoint(
            "local",
            "local",
            "LOCAL_DETERMINISTIC",
            local=True,
            zero_cost=True,
            priority=50,
            capabilities=("chat",),
        ),
        endpoint(
            "vendor-one",
            "fast-one",
            "EXTERNAL_FAST",
            health="UNAVAILABLE",
            priority=1,
            capabilities=("chat",),
            cost=0.01,
        ),
        endpoint(
            "vendor-two",
            "fast-two",
            "EXTERNAL_FAST",
            health="HEALTHY",
            priority=50,
            capabilities=("chat",),
            cost=0.01,
        ),
    ])
    result = route(reg)
    assert result["state"] == "ROUTE_READY"
    assert result["selected"]["provider_id"] == "vendor-two"


def test_capability_requirement_is_enforced():
    result = route(required_capabilities=["vision"])
    assert result["state"] == "BLOCKED"
    assert "NO_ELIGIBLE_MODEL_ROUTE" in result["blockers"]


def test_no_local_fallback_blocks_provider_independence_audit():
    reg = ProviderNeutralModelRegistry([
        endpoint(
            "vendor",
            "fast",
            "EXTERNAL_FAST",
            capabilities=("chat",),
            cost=0.01,
        )
    ])
    audit = provider_independence_audit(reg)
    assert audit["state"] == "BLOCKED"
    assert "LOCAL_FALLBACK_NOT_CONFIGURED" in audit["blockers"]
    assert "HEALTHY_LOCAL_FALLBACK_UNAVAILABLE" in audit["blockers"]


def test_degraded_local_fallback_is_explicitly_degraded():
    reg = ProviderNeutralModelRegistry([
        endpoint(
            "local",
            "local",
            "LOCAL_DETERMINISTIC",
            local=True,
            zero_cost=True,
            health="DEGRADED",
            capabilities=("chat",),
        ),
        endpoint(
            "vendor",
            "fast",
            "EXTERNAL_FAST",
            health="UNAVAILABLE",
            capabilities=("chat",),
            cost=0.01,
        ),
    ])
    result = route(reg)
    assert result["state"] == "DEGRADED_LOCAL_FALLBACK"
    assert result["selected"]["local"] is True
    assert result["provider_called"] is False


def test_all_routes_unavailable_blocks_without_calling_provider():
    reg = ProviderNeutralModelRegistry([
        endpoint(
            "local",
            "local",
            "LOCAL_DETERMINISTIC",
            local=True,
            zero_cost=True,
            health="UNAVAILABLE",
            capabilities=("chat",),
        ),
        endpoint(
            "vendor",
            "fast",
            "EXTERNAL_FAST",
            health="UNAVAILABLE",
            capabilities=("chat",),
            cost=0.01,
        ),
    ])
    result = route(reg)
    assert result["state"] == "BLOCKED"
    assert result["selected"] is None
    assert result["provider_called"] is False
    assert result["execution_allowed"] is False


@pytest.mark.parametrize("field,value", [
    ("privacy_sensitive", 1),
    ("offline_required", "false"),
    ("external_models_enabled", None),
    ("budget_remaining_usd", -1),
    ("max_request_cost_usd", float("nan")),
])
def test_route_security_inputs_are_strict(field, value):
    with pytest.raises(ValueError):
        route(**{field: value})


@pytest.mark.parametrize("field,bad", [
    ("required_capabilities", "chat"),
    ("required_capabilities", {"chat": True}),
    ("excluded_providers", "provider-a"),
    ("excluded_providers", {"provider-a": True}),
])
def test_route_collections_reject_scalar_or_mapping(field, bad):
    with pytest.raises(ValueError):
        route(**{field: bad})


@pytest.mark.parametrize("field,bad", [
    ("required_capabilities", ["chat", "chat"]),
    ("excluded_providers", ["provider-a", "provider-a"]),
    ("required_capabilities", [""]),
    ("excluded_providers", [""]),
])
def test_route_collections_reject_duplicates_and_empty_items(field, bad):
    with pytest.raises(ValueError):
        route(**{field: bad})


def test_arbitrary_provider_names_prove_gateway_has_no_single_vendor_identity():
    reg = ProviderNeutralModelRegistry([
        endpoint(
            "on-prem-runtime",
            "small-local",
            "LOCAL_DETERMINISTIC",
            local=True,
            zero_cost=True,
            capabilities=("chat",),
        ),
        endpoint(
            "vendor-x",
            "x-fast",
            "EXTERNAL_FAST",
            priority=10,
            capabilities=("chat",),
            cost=0.01,
        ),
        endpoint(
            "vendor-y",
            "y-fast",
            "EXTERNAL_FAST",
            priority=20,
            capabilities=("chat",),
            cost=0.01,
        ),
    ])
    result = route(reg, preferred_provider="vendor-y")
    assert result["selected"]["provider_id"] == "vendor-y"
    assert result["provider_called"] is False


def test_route_plan_never_executes_model():
    result = route()
    assert result["provider_called"] is False
    assert result["billing_executed"] is False
    assert result["execution_allowed"] is False
    assert result["executes_action"] is False
