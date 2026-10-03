from copy import deepcopy
import pytest

from aion_chat.models import Scope
from atlasquant_aion_chat_checkpoint_adapter import AionChatCheckpointAdapter


def scope(name="a"):
    return Scope(f"owner-{name}", f"tenant-{name}", f"workspace-{name}")


def checkpoint(**overrides):
    data = {
        "conversation_id": "conv-1",
        "through_sequence": 42,
        "confirmed_facts": {"x": "y"},
        "pending": {"todo": "review"},
    }
    data.update(overrides)
    return data


def test_prepare_export_is_scoped_and_never_saved_automatically():
    adapter = AionChatCheckpointAdapter()
    out = adapter.prepare_export(scope(), checkpoint())
    assert out["state"] == "PREPARED_NOT_SAVED"
    assert out["automatic_checkpoint_write"] is False
    assert out["automatic_memory_promotion"] is False
    assert out["export_digest"].startswith("sha256:")


def test_prepare_export_rejects_cross_tenant_payload():
    adapter = AionChatCheckpointAdapter()
    with pytest.raises(ValueError, match="crosses scope"):
        adapter.prepare_export(scope("a"), checkpoint(tenant_id="tenant-b"))


def test_save_requires_receipt():
    adapter = AionChatCheckpointAdapter()
    export = adapter.prepare_export(scope(), checkpoint())
    with pytest.raises(PermissionError):
        adapter.save_approved(scope(), export, "")


def test_save_rejects_tampered_export():
    adapter = AionChatCheckpointAdapter()
    export = adapter.prepare_export(scope(), checkpoint())
    tampered = deepcopy(export)
    tampered["checkpoint"]["confirmed_facts"]["x"] = "tampered"
    with pytest.raises(ValueError, match="digest mismatch"):
        adapter.save_approved(scope(), tampered, "approval-1")


def test_save_rejects_scope_switch():
    adapter = AionChatCheckpointAdapter()
    export = adapter.prepare_export(scope("a"), checkpoint())
    with pytest.raises(ValueError, match="crosses scope"):
        adapter.save_approved(scope("b"), export, "approval-1")


def test_approved_save_is_anchor_only_and_versioned():
    adapter = AionChatCheckpointAdapter()
    export = adapter.prepare_export(scope(), checkpoint())
    saved = adapter.save_approved(scope(), export, "approval-1")
    assert saved["state"] == "SAVED_AS_APPROVED_EXPORT_ANCHOR"
    assert saved["checkpoint_revision"] == 1
    assert saved["chat_contents_promoted"] is False
    assert saved["automatic_memory_promotion"] is False
    records = saved["checkpoint_bundle"]["records"]
    assert len(records) == 1
    assert records[0]["kind"] == "CURRENT_STATE"
    assert records[0]["origin"] == "UNKNOWN"
    assert records[0]["is_approved_decision"] is False


def test_duplicate_save_same_receipt_and_payload_is_idempotent():
    adapter = AionChatCheckpointAdapter()
    export = adapter.prepare_export(scope(), checkpoint())
    first = adapter.save_approved(scope(), export, "approval-1")
    second = adapter.save_approved(scope(), export, "approval-1")
    assert second == first
    assert second["checkpoint_revision"] == 1


def test_receipt_cannot_be_replayed_for_different_payload():
    adapter = AionChatCheckpointAdapter()
    first = adapter.prepare_export(scope(), checkpoint(through_sequence=42))
    second = adapter.prepare_export(scope(), checkpoint(through_sequence=43))
    adapter.save_approved(scope(), first, "approval-1")
    with pytest.raises(PermissionError, match="different payload"):
        adapter.save_approved(scope(), second, "approval-1")


def test_same_receipt_text_is_isolated_by_scope():
    adapter = AionChatCheckpointAdapter()
    a = adapter.prepare_export(scope("a"), checkpoint(conversation_id="a"))
    b = adapter.prepare_export(scope("b"), checkpoint(conversation_id="b"))
    ra = adapter.save_approved(scope("a"), a, "approval-1")
    rb = adapter.save_approved(scope("b"), b, "approval-1")
    assert ra["checkpoint_revision"] == 1
    assert rb["checkpoint_revision"] == 1
    assert ra["export_digest"] != rb["export_digest"]


def test_invalid_checkpoint_contract_is_rejected():
    adapter = AionChatCheckpointAdapter()
    with pytest.raises(ValueError, match="conversation_id"):
        adapter.prepare_export(scope(), {"through_sequence": 1})
    with pytest.raises(ValueError, match="through_sequence"):
        adapter.prepare_export(scope(), {"conversation_id": "x", "through_sequence": -1})
