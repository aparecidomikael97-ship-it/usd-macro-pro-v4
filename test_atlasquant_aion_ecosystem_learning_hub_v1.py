from atlasquant_aion_ecosystem_learning_hub_v1 import (
    DomainRegistration,
    learning_action_policy,
    owner_advisor_result,
    registry_snapshot,
)


def test_registry_aggregates_multiple_ecosystem_domains():
    snapshot = registry_snapshot([
        DomainRegistration("TRADER", ("ECONOMIC_CALENDAR", "ORDER_BLOCK")),
        DomainRegistration("BUSINESS", ("B2B", "CRM")),
        DomainRegistration("INVESTMENTS", ("DIVERSIFICATION",)),
        DomainRegistration("AION", ("MEMORY", "PERMISSIONS")),
    ])
    assert snapshot["state"] == "READY"
    assert set(snapshot["domains"]) == {"TRADER", "BUSINESS", "INVESTMENTS", "AION"}
    assert snapshot["dynamic_registration"] is True


def test_future_domain_can_register_without_core_change():
    snapshot = registry_snapshot([
        DomainRegistration("FUTURE_DOMAIN", ("TOPIC_A",)),
    ])
    assert "FUTURE_DOMAIN" in snapshot["domains"]


def test_learning_hub_blocks_live_trade():
    result = learning_action_policy(mode="VISUAL_EXPLAINER", action="TRADE_EXECUTE")
    assert result["state"] == "BLOCKED"
    assert "LIVE_ACTION_BLOCKED_IN_LEARNING_HUB" in result["blockers"]


def test_owner_advisor_never_executes_reserved_decision():
    result = owner_advisor_result(
        subject="CONTRACT_PRICE",
        known_facts=["margin calculated"],
        unknowns=["final implementation effort"],
        recommendation="review effort before accepting price",
        reserved_owner_decision=True,
    )
    assert result["reserved_owner_decision"] is True
    assert result["decision_executed"] is False
    assert result["executes_action"] is False
