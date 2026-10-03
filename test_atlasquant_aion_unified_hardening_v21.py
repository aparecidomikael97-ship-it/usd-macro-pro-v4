from copy import deepcopy

import pytest

from aion_chat.models import Scope
from atlasquant_aion_chat_library_adapter import AionChatLibraryAdapter
from atlasquant_aion_role_authority import (
    CRITICAL_ACTIONS,
    evaluate_role_authority,
    official_role_authority_matrix,
)
from atlasquant_aion_truth_mapping import map_truth_knowledge_state
from atlasquant_aion_unified_durable_bridge import (
    prepare_durable_handoff,
    prepare_durable_recovery,
)
from atlasquant_aion_unified_journal import (
    append_request_event,
    journal_runtime_exchange,
    verify_request_journal,
)
from atlasquant_aion_unified_runtime import (
    AionRequest,
    official_roles_snapshot,
    process_aion_request,
)


def scope(name="a"):
    return Scope(f"owner-{name}", f"tenant-{name}", f"workspace-{name}")


def req(**overrides):
    data = {
        "conversation_id": "conv-1",
        "owner_id": "owner-a",
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "user_message": "Explique o estado atual com evidência.",
        "request_id": "REQ-1",
        "requested_action": "query",
        "sector": "central",
    }
    data.update(overrides)
    return AionRequest(**data)


def reviewed_index(s, *, document_state="VALIDATED", truth_state="SUPPORTED"):
    return {
        "schema": "ATLASQUANT_AION_LIBRARY_INDEX_V1",
        "documents": [{
            "document_id": "LIB-1",
            "tenant_id": s.tenant_id,
            "workspace_id": s.workspace_id,
            "title": "Guia Macro",
            "state": document_state,
            "truth_state": truth_state,
            "source_reference": "internal://macro",
            "checksum": "sha256:x",
            "provenance_id": "PROV-1",
            "evidence_refs": ["E-1"],
            "terms": ["inflacao", "juros"],
        }],
        "passages": [{
            "passage_id": "PASS-1",
            "document_id": "LIB-1",
            "tenant_id": s.tenant_id,
            "workspace_id": s.workspace_id,
            "ordinal": 1,
            "text": "Inflação e juros exigem análise conjunta.",
            "terms": ["inflacao", "juros", "analise"],
            "state": "INDEXED",
            "provenance_id": "PROV-1",
            "evidence_refs": ["E-1"],
            "truth_state": truth_state,
        }],
        "external_persisted": False,
        "memory_promoted": False,
        "execution_authorized": False,
        "external_action_executed": False,
    }


def test_unified_journal_is_hash_chained_scoped_and_non_executing():
    request = req()
    response = process_aion_request(request)
    journal = journal_runtime_exchange(request, response, observed_at="2026-10-03T18:00:00+00:00")
    checked = verify_request_journal(journal, scope=request.scope, request_id=request.request_id)
    assert checked["valid"] is True
    assert journal["revision"] == 3
    assert [x["event_type"] for x in journal["events"]] == [
        "REQUEST_ACCEPTED", "ROLE_ROUTED", "PREFLIGHT_COMPLETED",
    ]
    assert all(x["external_action_executed"] is False for x in journal["events"])
    assert journal["memory_promoted"] is False
    assert journal["automatic_checkpoint_write"] is False


def test_unified_journal_tampering_and_cross_tenant_replay_fail_closed():
    request = req()
    journal = journal_runtime_exchange(request, process_aion_request(request))
    tampered = deepcopy(journal)
    tampered["events"][1]["selected_role"] = "prime"
    checked = verify_request_journal(tampered, scope=request.scope, request_id=request.request_id)
    assert checked["valid"] is False
    assert any("DIGEST_MISMATCH" in x for x in checked["reasons"])

    other = verify_request_journal(journal, scope=scope("b"), request_id=request.request_id)
    assert other["valid"] is False
    assert "SCOPE_MISMATCH" in other["reasons"]


def test_journal_redacts_secret_metadata_and_refuses_append_after_corruption():
    request = req()
    journal = journal_runtime_exchange(request, process_aion_request(request))
    journal = append_request_event(
        journal,
        event_type="RECOVERY_PREPARED",
        authorization_class="LOW_RISK",
        metadata={"api_key": "super-secret", "nested": {"password": "abc"}},
    )
    metadata = journal["events"][-1]["metadata"]
    assert metadata["api_key"] == "[REDACTED]"
    assert metadata["nested"]["password"] == "[REDACTED]"

    corrupt = deepcopy(journal)
    corrupt["head_digest"] = "sha256:deadbeef"
    with pytest.raises(ValueError, match="integrity"):
        append_request_event(
            corrupt,
            event_type="RECOVERY_PREPARED",
            authorization_class="LOW_RISK",
        )


def test_durable_handoff_and_recovery_restore_state_only():
    request = req()
    response = process_aion_request(request)
    journal = journal_runtime_exchange(request, response)
    handoff = prepare_durable_handoff(
        request, response, journal, checkpoint_digest="cp-1"
    )
    assert handoff["status"] == "PREPARED"
    task = handoff["durable_task"]
    assert task["state"] == "PAUSED"
    assert task["cursor"] == 1
    assert handoff["external_action_executed"] is False

    recovery = prepare_durable_recovery(
        task,
        handoff["journal"],
        scope=request.scope,
        request_id=request.request_id,
        checkpoint_digest="cp-1",
        expected_revision=task["revision"],
    )
    assert recovery["status"] == "RESUME_PREPARED"
    assert recovery["resume"]["restores_state_only"] is True
    assert recovery["resume"]["executes_action"] is False
    assert recovery["automatic_resume_executes"] is False


def test_durable_recovery_blocks_checkpoint_drift_and_tampered_journal():
    request = req()
    response = process_aion_request(request)
    journal = journal_runtime_exchange(request, response)
    handoff = prepare_durable_handoff(
        request, response, journal, checkpoint_digest="cp-1"
    )
    task = handoff["durable_task"]

    drift = prepare_durable_recovery(
        task,
        handoff["journal"],
        scope=request.scope,
        request_id=request.request_id,
        checkpoint_digest="cp-2",
        expected_revision=task["revision"],
    )
    assert drift["status"] == "BLOCKED"
    assert "CHECKPOINT_CHANGED" in drift["blockers"]

    bad = deepcopy(handoff["journal"])
    bad["events"][0]["state"] = "TAMPERED"
    blocked = prepare_durable_recovery(
        task,
        bad,
        scope=request.scope,
        request_id=request.request_id,
        checkpoint_digest="cp-1",
        expected_revision=task["revision"],
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["reason"] == "JOURNAL_INTEGRITY_MISMATCH"


def test_waiting_approval_survives_durable_handoff_and_recovery():
    request = req(
        user_message="Prepare publicação, sem executar.",
        requested_action="publish",
    )
    response = process_aion_request(request, approved=False)
    assert response.authorization_class == "REQUIRES_APPROVAL"
    assert response.pending_approvals

    journal = journal_runtime_exchange(request, response)
    handoff = prepare_durable_handoff(
        request, response, journal, checkpoint_digest="cp-approval"
    )
    task = handoff["durable_task"]
    assert task["state"] == "WAITING_APPROVAL"
    assert handoff["requires_explicit_approval"] is True

    recovery = prepare_durable_recovery(
        task,
        handoff["journal"],
        scope=request.scope,
        request_id=request.request_id,
        checkpoint_digest="cp-approval",
        expected_revision=task["revision"],
    )
    assert recovery["status"] == "RESUME_PREPARED"
    assert recovery["resume"]["approval_pending"] is True
    assert recovery["resume"]["executes_action"] is False


@pytest.mark.parametrize("fake_approval", ["yes", "true", 1])
def test_truthy_non_boolean_approval_never_releases_runtime_gate(fake_approval):
    request = req(
        user_message="Prepare publicação.",
        requested_action="publish",
    )
    response = process_aion_request(request, approved=fake_approval)
    assert response.authorization_class == "REQUIRES_APPROVAL"
    assert response.pending_approvals
    receipt = response.execution_receipts[0]["receipt"]
    assert receipt["approval_refs"] == []


def test_official_eight_role_matrix_keeps_critical_authority_with_human_owner():
    matrix = official_role_authority_matrix()
    assert matrix["count"] == 8
    assert matrix["critical_approval_owner"] == "HUMAN_OWNER"
    assert matrix["role_cannot_self_approve"] is True
    assert set(row["role_id"] for row in matrix["roles"]) == {
        "orchestrator", "architect", "guardian", "prime",
        "shadow", "sentinel", "commercial", "educator",
    }
    for row in matrix["roles"]:
        assert row["may_approve_critical"] is False
        assert row["may_execute_external_without_explicit_approval"] is False
        assert row["may_promote_memory_automatically"] is False
        assert row["may_write_checkpoint_automatically"] is False
        assert row["may_merge_main"] is False
        assert row["may_deploy_production"] is False
        assert row["may_spend_money"] is False
        assert row["may_read_credentials"] is False
        assert row["may_enable_real_trade"] is False
    assert "real_trade" in CRITICAL_ACTIONS

    snapshot = official_roles_snapshot()
    by_id = {row["role_id"]: row for row in snapshot["roles"]}
    assert snapshot["human_owner_retains_critical_approval"] is True
    assert by_id["prime"]["authority"]["may_prepare_guarded_execution"] is True
    assert by_id["guardian"]["authority"]["may_block_for_safety"] is True


def test_role_approval_is_not_execution_authority_even_when_exactly_true():
    result = evaluate_role_authority(
        "prime", "REQUIRES_APPROVAL", explicit_human_approval=True
    )
    assert result["status"] == "APPROVAL_PRESENT_EXECUTION_GATE_STILL_REQUIRED"
    assert result["explicit_human_approval"] is True
    assert result["role_may_approve_critical"] is False
    assert result["execution_allowed"] is False
    assert result["external_action_executed"] is False


@pytest.mark.parametrize(
    "library_state",
    ["CONFLICTING", "STALE", "QUARANTINED", "REVIEW_REQUIRED", "REJECTED"],
)
def test_truth_mapping_fails_closed_for_non_confirmed_library_states(library_state):
    mapped = map_truth_knowledge_state(
        evidence_truth_state="CONFIRMED",
        library_state=library_state,
        library_truth_state="SUPPORTED",
        freshness="FRESH",
    )
    assert mapped["operational_truth_state"] == "UNKNOWN"
    assert mapped["usable_as_confirmed_fact"] is False
    assert mapped["automatic_memory_promotion"] is False
    assert mapped["official_decision_authority"] is False


def test_truth_mapping_validated_supported_is_confirmed_but_not_promoted():
    mapped = map_truth_knowledge_state(
        evidence_truth_state="UNKNOWN",
        library_state="VALIDATED",
        library_truth_state="SUPPORTED",
        freshness="FRESH",
        provenance_review_status="VALIDATED",
    )
    assert mapped["operational_truth_state"] == "CONFIRMED"
    assert mapped["usable_as_confirmed_fact"] is True
    assert mapped["automatic_memory_promotion"] is False
    assert mapped["official_decision_authority"] is False


def test_library_adapter_rejects_forged_unreviewed_index():
    s = scope()
    adapter = AionChatLibraryAdapter()
    forged = reviewed_index(s, document_state="QUARANTINED", truth_state="UNKNOWN")
    with pytest.raises(ValueError, match="unreviewed document"):
        adapter.install_reviewed_index(s, forged)


def test_conflicting_library_hit_is_retrievable_but_not_runtime_confirmed():
    s = scope()
    adapter = AionChatLibraryAdapter()
    index = reviewed_index(s, document_state="CONFLICTING", truth_state="CONFIRMED")
    adapter.install_reviewed_index(s, index)
    hits = adapter.retrieve(s, "inflação")
    assert len(hits) == 1
    assert hits[0]["truth_state"] == "CONFIRMED"
    assert hits[0]["runtime_truth_state"] == "UNKNOWN"
    assert hits[0]["usable_as_confirmed_fact"] is False
    assert "LIBRARY_CONFLICT" in hits[0]["truth_mapping"]["reason_codes"]
