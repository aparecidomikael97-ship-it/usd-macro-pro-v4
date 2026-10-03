"""Concrete Chat -> Checkpoint Mestre bridge.

This adapter implements the aion_chat CheckpointMasterAdapter contract over the
existing CheckpointCoreStore. It deliberately stores only an approved export
anchor in Core memory; chat payloads are never promoted automatically to
official decisions or facts.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
import json

from aion_chat.models import Scope
from atlasquant_aion_core_checkpoint_bridge import CheckpointCoreStore
from atlasquant_aion_core_intelligence.context import Context, Domain
from atlasquant_aion_core_intelligence.evidence import Origin

SCHEMA = "ATLASQUANT_AION_CHAT_CHECKPOINT_ADAPTER_V1"
MAX_EXPORT_BYTES = 512_000
MAX_RECEIPT = 512


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _scope_fingerprint(scope: Scope) -> str:
    return _digest({
        "owner_id": scope.owner_id,
        "tenant_id": scope.tenant_id,
        "workspace_id": scope.workspace_id,
    })


def _context(scope: Scope) -> Context:
    if not isinstance(scope, Scope):
        raise TypeError("Scope required")
    def token(prefix: str, value: str) -> str:
        return prefix + ":" + sha256(value.encode("utf-8")).hexdigest()[:32]
    return Context(
        tenant_id=token("tenant", scope.tenant_id),
        workspace_id=token("workspace", scope.workspace_id),
        actor_id=token("owner", scope.owner_id),
        task_id=token("chat-checkpoint", _scope_fingerprint(scope)),
        domain=Domain.ADMIN,
        role="USER",
    )


def _bounded_checkpoint(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(checkpoint, Mapping):
        raise TypeError("checkpoint mapping required")
    try:
        normalized = json.loads(_canonical(dict(checkpoint)))
    except Exception as exc:
        raise ValueError("checkpoint must be JSON-serializable") from exc
    raw = _canonical(normalized).encode("utf-8")
    if not raw or len(raw) > MAX_EXPORT_BYTES:
        raise ValueError("checkpoint export exceeds byte budget")
    conversation_id = str(normalized.get("conversation_id") or "").strip()
    sequence = normalized.get("through_sequence")
    if not conversation_id:
        raise ValueError("conversation_id required")
    if type(sequence) is not int or sequence < 0:
        raise ValueError("non-negative through_sequence required")
    return normalized


class AionChatCheckpointAdapter:
    """Scoped, idempotent, staged bridge to the existing Core checkpoint store."""

    def __init__(self):
        self._stores: dict[str, CheckpointCoreStore] = {}
        self._receipt_bindings: dict[tuple[str, str], str] = {}
        self._saved: dict[tuple[str, str], dict[str, Any]] = {}

    def _store(self, scope: Scope) -> tuple[Context, CheckpointCoreStore]:
        context = _context(scope)
        key = context.key
        if key not in self._stores:
            self._stores[key] = CheckpointCoreStore(context)
        return context, self._stores[key]

    def prepare_export(self, scope: Scope, checkpoint: dict) -> dict:
        if not isinstance(scope, Scope):
            raise TypeError("Scope required")
        payload = _bounded_checkpoint(checkpoint)
        supplied = {
            "owner_id": payload.get("owner_id"),
            "tenant_id": payload.get("tenant_id"),
            "workspace_id": payload.get("workspace_id"),
        }
        expected = {
            "owner_id": scope.owner_id,
            "tenant_id": scope.tenant_id,
            "workspace_id": scope.workspace_id,
        }
        for key, value in supplied.items():
            if value not in (None, "") and str(value) != expected[key]:
                raise ValueError(f"checkpoint {key} crosses scope")

        export_body = {
            "conversation_id": str(payload["conversation_id"]),
            "through_sequence": int(payload["through_sequence"]),
            "checkpoint": payload,
            "scope_fingerprint": _scope_fingerprint(scope),
            "automatic_memory_promotion": False,
            "automatic_checkpoint_write": False,
        }
        return {
            "schema": SCHEMA,
            "state": "PREPARED_NOT_SAVED",
            "export_digest": _digest(export_body),
            **export_body,
        }

    def save_approved(self, scope: Scope, export: dict, approval_receipt: str) -> dict:
        if not isinstance(scope, Scope):
            raise TypeError("Scope required")
        if not isinstance(export, Mapping) or export.get("schema") != SCHEMA:
            raise ValueError("invalid checkpoint export")
        receipt = str(approval_receipt or "").strip()
        if not receipt or len(receipt) > MAX_RECEIPT:
            raise PermissionError("bounded approval receipt required")
        if export.get("state") != "PREPARED_NOT_SAVED":
            raise ValueError("checkpoint export is not in prepared state")
        if export.get("scope_fingerprint") != _scope_fingerprint(scope):
            raise ValueError("checkpoint export crosses scope")

        body = {
            "conversation_id": export.get("conversation_id"),
            "through_sequence": export.get("through_sequence"),
            "checkpoint": export.get("checkpoint"),
            "scope_fingerprint": export.get("scope_fingerprint"),
            "automatic_memory_promotion": False,
            "automatic_checkpoint_write": False,
        }
        expected_digest = _digest(body)
        supplied_digest = str(export.get("export_digest") or "")
        if supplied_digest != expected_digest:
            raise ValueError("checkpoint export digest mismatch")

        scope_key = _scope_fingerprint(scope)
        receipt_key = (scope_key, receipt)
        prior_digest = self._receipt_bindings.get(receipt_key)
        if prior_digest is not None and prior_digest != supplied_digest:
            raise PermissionError("approval receipt replayed for different payload")
        if receipt_key in self._saved:
            return dict(self._saved[receipt_key])

        context, store = self._store(scope)
        current = store.revision(context)
        receipt_digest = _digest({"scope": scope_key, "receipt": receipt})
        anchor = {
            "schema": SCHEMA,
            "conversation_id": str(export.get("conversation_id") or ""),
            "through_sequence": int(export.get("through_sequence") or 0),
            "export_digest": supplied_digest,
            "approval_receipt_digest": receipt_digest,
            "contents_promoted": False,
        }
        row = store.append(
            context,
            kind="CURRENT_STATE",
            text=_canonical(anchor),
            origin=Origin.UNKNOWN,
            source="AION_CHAT_APPROVED_EXPORT",
            now=datetime.now(timezone.utc),
            expected_revision=current,
            evidence_refs=(),
        )
        bundle = store.checkpoint(context, datetime.now(timezone.utc))
        result = {
            "schema": SCHEMA,
            "state": "SAVED_AS_APPROVED_EXPORT_ANCHOR",
            "export_digest": supplied_digest,
            "approval_receipt_digest": receipt_digest,
            "checkpoint_revision": store.revision(context),
            "record_id": row["record_id"],
            "checkpoint_bundle": bundle,
            "chat_contents_promoted": False,
            "automatic_memory_promotion": False,
            "external_action_executed": False,
        }
        self._receipt_bindings[receipt_key] = supplied_digest
        self._saved[receipt_key] = dict(result)
        return result


__all__ = [
    "SCHEMA",
    "AionChatCheckpointAdapter",
]
