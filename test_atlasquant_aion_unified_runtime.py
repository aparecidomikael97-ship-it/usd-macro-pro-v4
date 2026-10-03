"""Contracts for the thin unified AION runtime facade."""
from dataclasses import replace
import pytest

from atlasquant_aion_unified_runtime import (
    AionRequest,
    OFFICIAL_ROLES,
    official_roles_snapshot,
    prepare_checkpoint_export,
    process_aion_request,
    save_approved_checkpoint,
    select_official_role,
)


def req(**overrides):
    base = dict(
        request_id="REQ-1",
        conversation_id="CONV-1",
        owner_id="owner-a",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        user_message="Explique o estado atual.",
        requested_action="query",
        sector="central",
        source_context={},
        authorization_context={"role": "ADMIN"},
        evidence=(),
    )
    base.update(overrides)
    return AionRequest(**base)


def test_official_catalog_has_exactly_eight_shared_core_roles():
    snap = official_roles_snapshot()
    ids = [x["role_id"] for x in snap["roles"]]
    assert len(OFFICIAL_ROLES) == 8
    assert ids == [
        "orchestrator", "architect", "guardian", "prime",
        "shadow", "sentinel", "commercial", "educator",
    ]
    assert snap["single_shared_aion_core"] is True
    assert snap["execution_authority"] is False
    assert all(x["independent_ai"] is False for x in snap["roles"])
    assert snap["legacy_registry_preserved"] is True


@pytest.mark.parametrize(
    ("message", "action", "expected"),
    [
        ("status geral", "query", "orchestrator"),
        ("revise a arquitetura do núcleo", "query", "architect"),
        ("faça auditoria de segurança", "query", "guardian"),
        ("prepare o deploy", "deploy", "prime"),
        ("pesquise fontes confiáveis", "query", "shadow"),
        ("monitore incidentes e saúde", "query", "sentinel"),
        ("organize leads no CRM", "query", "commercial"),
        ("explique isso para treinamento", "query", "educator"),
    ],
)
def test_role_selection_maps_to_official_responsibilities(message, action, expected):
    selected, _ = select_official_role(req(user_message=message, requested_action=action))
    assert selected == expected


def test_read_only_request_never_executes_external_action():
    result = process_aion_request(req())
    assert result.authorization_class == "READ_ONLY"
    assert result.external_action_executed is False
    assert result.real_orders_enabled is False
    assert result.answer == ""
    assert "NO_MODEL_RESPONSE_GENERATED" in result.warnings
    assert result.model_lane == "LOCAL_DETERMINISTIC"
    assert result.execution_receipts
    assert result.execution_receipts[0]["executes_action"] is False


def test_deploy_requires_approval_but_still_never_executes():
    result = process_aion_request(req(requested_action="deploy", user_message="Faça deploy em produção."))
    assert result.authorization_class == "REQUIRES_APPROVAL"
    assert result.pending_approvals
    assert result.external_action_executed is False
    assert result.real_orders_enabled is False


def test_unknown_real_trade_action_is_blocked():
    result = process_aion_request(req(requested_action="real_trade", user_message="Execute uma ordem real."))
    assert result.authorization_class == "BLOCKED"
    assert "ACTION_BLOCKED" in result.warnings
    assert result.external_action_executed is False
    assert result.real_orders_enabled is False


def test_cross_tenant_source_context_is_rejected():
    request = req(source_context={
        "owner_id": "owner-a",
        "tenant_id": "tenant-b",
        "workspace_id": "workspace-a",
    })
    with pytest.raises(ValueError, match="crosses request scope"):
        process_aion_request(request)


def test_unverified_memory_events_are_only_proposals():
    result = process_aion_request(req(source_context={
        "memory_events": [{"kind": "confirmed_facts", "key": "x", "value": "claim"}],
    }))
    assert len(result.memory_updates) == 1
    proposal = result.memory_updates[0]
    assert proposal["state"] == "PROPOSED_ONLY"
    assert proposal["automatic_promotion"] is False
    assert proposal["requires_truth_validation"] is True
    assert proposal["requires_checkpoint_policy"] is True


def test_external_feature_without_ready_provider_is_explicitly_unavailable():
    result = process_aion_request(
        req(),
        external_feature_enabled=True,
        provider_state="MISSING_API_KEY",
    )
    assert result.provider_state == "MISSING_API_KEY"
    assert result.model_lane == "LOCAL_DETERMINISTIC"
    assert "PROVIDER_UNAVAILABLE" in result.warnings


def test_confirmed_conflicting_evidence_is_not_arbitrarily_selected():
    evidence = (
        {
            "claim": "policy",
            "value": "A",
            "truth_state": "CONFIRMED",
            "source": "source-a",
            "source_tier": "PRIMARY",
            "time_sensitive": False,
        },
        {
            "claim": "policy",
            "value": "B",
            "truth_state": "CONFIRMED",
            "source": "source-b",
            "source_tier": "PRIMARY",
            "time_sensitive": False,
        },
    )
    result = process_aion_request(req(evidence=evidence))
    assert result.truth_state == "UNKNOWN"
    assert "EVIDENCE_CONFLICT" in result.warnings


def test_receipt_is_bound_to_trusted_request_scope():
    result = process_aion_request(req())
    receipt = result.execution_receipts[0]["receipt"]
    assert receipt["requester_id"] == "owner-a"
    assert receipt["tenant_id"] == "tenant-a"
    assert receipt["workspace_id"] == "workspace-a"
    assert receipt["correlation_id"] == "REQ-1"
    assert receipt["fingerprint"]
    assert result.execution_receipts[0]["digest_is_signature"] is False


class FakeCheckpointAdapter:
    def __init__(self):
        self.prepared = []
        self.saved = []

    def prepare_export(self, scope, checkpoint):
        self.prepared.append((scope, checkpoint))
        return {"candidate": checkpoint, "scope": [scope.owner_id, scope.tenant_id, scope.workspace_id]}

    def save_approved(self, scope, export, approval_receipt):
        self.saved.append((scope, export, approval_receipt))
        return {"state": "SAVED", "approval_receipt": approval_receipt}


def test_checkpoint_bridge_prepares_but_does_not_save_automatically():
    adapter = FakeCheckpointAdapter()
    prepared = prepare_checkpoint_export(req(), {"id": "CHAT-CP-1"}, adapter)
    assert prepared["state"] == "PREPARED_NOT_SAVED"
    assert prepared["automatic_checkpoint_write"] is False
    assert prepared["requires_explicit_human_confirmation"] is True
    assert len(adapter.prepared) == 1
    assert adapter.saved == []


def test_checkpoint_bridge_rejects_save_without_explicit_approval():
    adapter = FakeCheckpointAdapter()
    with pytest.raises(PermissionError):
        save_approved_checkpoint(
            req(), {"candidate": 1}, adapter,
            approval_receipt="", explicit_approval=False,
        )
    assert adapter.saved == []


def test_checkpoint_bridge_saves_only_with_explicit_approval_receipt():
    adapter = FakeCheckpointAdapter()
    saved = save_approved_checkpoint(
        req(), {"candidate": 1}, adapter,
        approval_receipt="APPROVAL-1", explicit_approval=True,
    )
    assert saved["state"] == "SAVED"
    assert len(adapter.saved) == 1


def test_request_validation_requires_scoped_identity():
    with pytest.raises(ValueError):
        replace(req(), tenant_id="")
