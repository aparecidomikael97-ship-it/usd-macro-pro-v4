"""Non-network Postgres store adapter skeleton with an in-memory fake backend.

This is implementation scaffolding only. It intentionally imports no Postgres
driver, opens no network connection, reads no secrets, executes no SQL and
performs no deploy/provider/external action.

The goal is to prove the future production adapter's interface, scope,
transaction, idempotency and unknown-commit behavior before a real DB driver is
introduced.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from threading import RLock
from typing import Any
from uuid import uuid4

from aion_chat.attachments import validate_metadata
from aion_chat.models import (
    Attachment,
    ContextSummary,
    Conversation,
    ConversationCheckpoint,
    Message,
    Page,
    Scope,
    now,
)
from aion_chat.privacy import redact
from aion_chat.store import StorageUnavailableError


HEALTHY = "healthy"
FAILED = "failed"
SCHEMA_VERSION = 1


class CommitOutcomeUnknownError(StorageUnavailableError):
    """The fake backend committed but intentionally withholds commit certainty."""

    def __init__(self, idempotency_key: str):
        super().__init__("commit outcome unknown")
        self.idempotency_key = str(idempotency_key or "")


def _clone(model):
    return type(model)(**deepcopy(asdict(model)))


class FakePostgresBackend:
    """In-memory transaction boundary used only to test adapter semantics."""

    def __init__(self):
        self._lock = RLock()
        self.healthy = True
        self.schema_version = SCHEMA_VERSION
        self.scope_policy_healthy = True
        self._conversations: dict[tuple[str, str, str, str], Conversation] = {}
        self._messages: dict[tuple[str, str, str, str], list[Message]] = {}
        self._attachments: dict[tuple[str, str, str, str, str], Attachment] = {}
        self._checkpoints: dict[tuple[str, str, str, str], list[ConversationCheckpoint]] = {}
        self._summaries: dict[tuple[str, str, str, str], list[ContextSummary]] = {}
        self._idempotency: dict[tuple[str, str, str, str, str], str] = {}
        self.commit_outcome_unknown_once = False

    @staticmethod
    def _scope_key(scope: Scope) -> tuple[str, str, str]:
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        return (scope.owner_id, scope.tenant_id, scope.workspace_id)

    def health_report(self) -> dict[str, Any]:
        state = HEALTHY if (
            self.healthy
            and self.schema_version == SCHEMA_VERSION
            and self.scope_policy_healthy
        ) else FAILED
        return {
            "state": state,
            "schema_version": self.schema_version,
            "expected_schema_version": SCHEMA_VERSION,
            "scope_policy_healthy": self.scope_policy_healthy,
            "backend": "fake_in_memory",
            "network": False,
        }

    def require_healthy(self) -> dict[str, Any]:
        report = self.health_report()
        if report["state"] != HEALTHY:
            raise StorageUnavailableError("production store health is not proven")
        return report

    def create_conversation(self, scope: Scope, conversation: Conversation) -> Conversation:
        self.require_healthy()
        key = (*self._scope_key(scope), conversation.id)
        with self._lock:
            if key in self._conversations:
                raise ValueError("conversation already exists")
            self._conversations[key] = _clone(conversation)
            self._messages[key] = []
            self._checkpoints[key] = []
            self._summaries[key] = []
            return _clone(conversation)

    def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation:
        self.require_healthy()
        key = (*self._scope_key(scope), str(conversation_id))
        with self._lock:
            value = self._conversations.get(key)
            if value is None:
                raise LookupError("conversation unavailable")
            return _clone(value)

    def list_conversations(self, scope: Scope) -> list[Conversation]:
        self.require_healthy()
        prefix = self._scope_key(scope)
        with self._lock:
            items = [
                _clone(value)
                for key, value in self._conversations.items()
                if key[:3] == prefix
            ]
        return sorted(items, key=lambda c: (c.updated_at, c.id), reverse=True)

    def update_conversation(self, scope: Scope, conversation: Conversation) -> Conversation:
        self.require_healthy()
        key = (*self._scope_key(scope), conversation.id)
        with self._lock:
            if key not in self._conversations:
                raise LookupError("conversation unavailable")
            self._conversations[key] = _clone(conversation)
            return _clone(conversation)

    def append_message_atomic(
        self,
        scope: Scope,
        message: Message,
        *,
        idempotency_key: str,
    ) -> Message:
        self.require_healthy()
        key = (*self._scope_key(scope), message.conversation_id)
        idem_key = (*self._scope_key(scope), message.conversation_id, idempotency_key)
        with self._lock:
            conversation = self._conversations.get(key)
            if conversation is None:
                raise LookupError("conversation unavailable")

            prior_id = self._idempotency.get(idem_key)
            if prior_id:
                for existing in self._messages[key]:
                    if existing.id == prior_id:
                        return _clone(existing)
                raise StorageUnavailableError("idempotency index is inconsistent")

            existing_ids = {item.id for item in self._messages[key]}
            if message.id in existing_ids:
                raise ValueError("message id already exists")

            stored = _clone(message)
            stored.sequence = conversation.message_count + 1
            self._messages[key].append(_clone(stored))
            self._idempotency[idem_key] = stored.id

            conversation = _clone(conversation)
            conversation.message_count = stored.sequence
            conversation.updated_at = now()
            self._conversations[key] = conversation

            if self.commit_outcome_unknown_once:
                self.commit_outcome_unknown_once = False
                raise CommitOutcomeUnknownError(idempotency_key)
            return _clone(stored)

    def find_by_idempotency(
        self,
        scope: Scope,
        conversation_id: str,
        idempotency_key: str,
    ) -> Message | None:
        self.require_healthy()
        idem_key = (*self._scope_key(scope), conversation_id, idempotency_key)
        key = (*self._scope_key(scope), conversation_id)
        with self._lock:
            prior_id = self._idempotency.get(idem_key)
            if not prior_id:
                return None
            for item in self._messages.get(key, []):
                if item.id == prior_id:
                    return _clone(item)
            raise StorageUnavailableError("idempotency index is inconsistent")

    def list_messages(self, scope: Scope, conversation_id: str) -> list[Message]:
        self.get_conversation(scope, conversation_id)
        key = (*self._scope_key(scope), conversation_id)
        with self._lock:
            return [_clone(item) for item in self._messages.get(key, [])]

    def get_message(self, scope: Scope, conversation_id: str, message_id: str) -> Message:
        for item in self.list_messages(scope, conversation_id):
            if item.id == message_id:
                return item
        raise LookupError("message unavailable")

    def save_attachment(self, scope: Scope, attachment: Attachment) -> Attachment:
        self.get_conversation(scope, attachment.conversation_id)
        key = (*self._scope_key(scope), attachment.conversation_id, attachment.id)
        with self._lock:
            if key in self._attachments:
                raise ValueError("attachment already exists")
            self._attachments[key] = _clone(attachment)
            return _clone(attachment)

    def get_attachment(
        self,
        scope: Scope,
        conversation_id: str,
        attachment_id: str,
    ) -> Attachment:
        self.get_conversation(scope, conversation_id)
        key = (*self._scope_key(scope), conversation_id, attachment_id)
        with self._lock:
            value = self._attachments.get(key)
            if value is None:
                raise LookupError("attachment unavailable")
            return _clone(value)

    def save_checkpoint(
        self,
        scope: Scope,
        checkpoint: ConversationCheckpoint,
    ) -> ConversationCheckpoint:
        conversation = self.get_conversation(scope, checkpoint.conversation_id)
        key = (*self._scope_key(scope), checkpoint.conversation_id)
        with self._lock:
            history = self._checkpoints[key]
            if history and checkpoint.through_sequence <= history[-1].through_sequence:
                raise ValueError("coverage must advance")
            if checkpoint.through_sequence > conversation.message_count:
                raise ValueError("coverage beyond conversation")
            history.append(_clone(checkpoint))
            conversation.latest_checkpoint = checkpoint.id
            conversation.updated_at = now()
            self._conversations[key] = conversation
            return _clone(checkpoint)

    def get_latest_checkpoint(
        self,
        scope: Scope,
        conversation_id: str,
    ) -> ConversationCheckpoint | None:
        self.get_conversation(scope, conversation_id)
        key = (*self._scope_key(scope), conversation_id)
        with self._lock:
            history = self._checkpoints[key]
            return _clone(history[-1]) if history else None

    def save_summary(self, scope: Scope, summary: ContextSummary) -> ContextSummary:
        conversation = self.get_conversation(scope, summary.conversation_id)
        if summary.through_sequence > conversation.message_count:
            raise ValueError("coverage beyond conversation")
        messages = {
            item.id: item
            for item in self.list_messages(scope, summary.conversation_id)
        }
        for message_id in summary.source_message_ids:
            item = messages.get(message_id)
            if item is None:
                raise LookupError("summary source message unavailable")
            if item.sequence > summary.through_sequence:
                raise ValueError("source beyond coverage")
        key = (*self._scope_key(scope), summary.conversation_id)
        with self._lock:
            self._summaries[key].append(_clone(summary))
            return _clone(summary)

    def get_latest_summary(
        self,
        scope: Scope,
        conversation_id: str,
    ) -> ContextSummary | None:
        self.get_conversation(scope, conversation_id)
        key = (*self._scope_key(scope), conversation_id)
        with self._lock:
            history = self._summaries[key]
            return _clone(history[-1]) if history else None


class PostgresChatStoreAdapterSkeleton:
    """AionChatStore-compatible non-network skeleton backed by FakePostgresBackend."""

    def __init__(self, backend: FakePostgresBackend):
        if not isinstance(backend, FakePostgresBackend):
            raise TypeError("fake backend required in V1 skeleton")
        self.backend = backend

    @staticmethod
    def _scope(scope: Scope) -> Scope:
        if not isinstance(scope, Scope):
            raise TypeError("trusted Scope required")
        return scope

    @staticmethod
    def _size(size: int) -> int:
        if not isinstance(size, int) or not 1 <= size <= 200:
            raise ValueError("page_size must be 1..200")
        return size

    def storage_health(self) -> dict[str, Any]:
        return self.backend.health_report()

    def require_healthy(self) -> dict[str, Any]:
        return self.backend.require_healthy()

    def create_conversation(self, scope: Scope, title="Nova conversa", metadata=None) -> Conversation:
        scope = self._scope(scope)
        self.require_healthy()
        conversation = Conversation(
            **asdict(scope),
            title=redact(title),
            metadata=redact(metadata or {}),
        )
        return self.backend.create_conversation(scope, conversation)

    def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation:
        return self.backend.get_conversation(self._scope(scope), conversation_id)

    def list_conversations(
        self,
        scope: Scope,
        cursor=None,
        page_size=30,
        *,
        query="",
        tag=None,
        since=None,
        until=None,
        archived=False,
        **_filters,
    ) -> Page:
        if cursor not in (None, ""):
            raise ValueError("fake skeleton cursor pagination is not implemented")
        size = self._size(page_size)
        items = self.backend.list_conversations(self._scope(scope))
        filtered = []
        for conversation in items:
            if conversation.archived != bool(archived):
                continue
            if query:
                haystack = [conversation.title]
                haystack.extend(
                    item.content
                    for item in self.backend.list_messages(scope, conversation.id)
                )
                if query.casefold() not in "\n".join(haystack).casefold():
                    continue
            tags = list((conversation.metadata or {}).get("tags") or [])
            if tag is not None and tag not in tags:
                continue
            if since and conversation.updated_at < since:
                continue
            if until and conversation.updated_at > until:
                continue
            filtered.append(conversation)
        return Page(filtered[:size], None)

    def search_conversations(self, scope: Scope, query: str, **filters) -> Page:
        return self.list_conversations(scope, query=query, **filters)

    def archive_conversation(self, scope: Scope, conversation_id: str) -> Conversation:
        scope = self._scope(scope)
        conversation = self.backend.get_conversation(scope, conversation_id)
        conversation.archived = True
        conversation.updated_at = now()
        return self.backend.update_conversation(scope, conversation)

    def append_message(self, scope: Scope, message: Message) -> Message:
        scope = self._scope(scope)
        if message.role not in {"user", "assistant", "system", "task"}:
            raise ValueError("invalid role")
        if message.conversation_id != self.get_conversation(scope, message.conversation_id).id:
            raise LookupError("conversation unavailable")
        for attachment_id in message.attachments:
            self.get_attachment(scope, message.conversation_id, attachment_id)
        clean = Message(**redact(asdict(message)))
        idempotency_key = str((clean.metadata or {}).get("idempotency_key") or "").strip()
        if not idempotency_key:
            raise ValueError("idempotency_key required")
        return self.backend.append_message_atomic(
            scope,
            clean,
            idempotency_key=idempotency_key,
        )

    def reconcile_message_idempotency(
        self,
        scope: Scope,
        conversation_id: str,
        idempotency_key: str,
    ) -> Message | None:
        if not str(idempotency_key or "").strip():
            raise ValueError("idempotency_key required")
        return self.backend.find_by_idempotency(
            self._scope(scope),
            conversation_id,
            str(idempotency_key),
        )

    def list_messages(
        self,
        scope: Scope,
        conversation_id: str,
        cursor=None,
        page_size=50,
        *,
        newest_first=False,
        **_options,
    ) -> Page:
        if cursor not in (None, ""):
            raise ValueError("fake skeleton cursor pagination is not implemented")
        size = self._size(page_size)
        items = self.backend.list_messages(self._scope(scope), conversation_id)
        if newest_first:
            items = list(reversed(items))
        return Page(items[:size], None)

    def get_message(self, scope: Scope, conversation_id: str, message_id: str) -> Message:
        return self.backend.get_message(self._scope(scope), conversation_id, message_id)

    def add_attachment_metadata(self, scope: Scope, attachment: Attachment) -> Attachment:
        scope = self._scope(scope)
        validate_metadata(attachment)
        return self.backend.save_attachment(scope, Attachment(**redact(asdict(attachment))))

    def get_attachment(
        self,
        scope: Scope,
        conversation_id: str,
        attachment_id: str,
    ) -> Attachment:
        return self.backend.get_attachment(
            self._scope(scope),
            conversation_id,
            attachment_id,
        )

    def save_checkpoint(
        self,
        scope: Scope,
        checkpoint: ConversationCheckpoint,
    ) -> ConversationCheckpoint:
        return self.backend.save_checkpoint(self._scope(scope), checkpoint)

    def get_latest_checkpoint(
        self,
        scope: Scope,
        conversation_id: str,
    ) -> ConversationCheckpoint | None:
        return self.backend.get_latest_checkpoint(
            self._scope(scope),
            conversation_id,
        )

    def save_context_summary(
        self,
        scope: Scope,
        summary: ContextSummary,
    ) -> ContextSummary:
        return self.backend.save_summary(self._scope(scope), summary)

    def get_latest_summary(
        self,
        scope: Scope,
        conversation_id: str,
    ) -> ContextSummary | None:
        return self.backend.get_latest_summary(
            self._scope(scope),
            conversation_id,
        )

    def retrieve_messages(
        self,
        scope: Scope,
        conversation_id: str,
        query: str,
        *,
        before_sequence: int,
        limit=10,
        **_options,
    ) -> list[Message]:
        size = self._size(limit)
        items = self.backend.list_messages(self._scope(scope), conversation_id)
        if not query.strip():
            return []
        result = [
            item
            for item in reversed(items)
            if item.sequence < before_sequence
            and query.casefold() in item.content.casefold()
        ]
        return result[:size]


def skeleton_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_POSTGRES_STORE_ADAPTER_FAKE_V1",
        "implementation_skeleton": True,
        "fake_backend_only": True,
        "postgres_client_imported": False,
        "connection_opened": False,
        "sql_executed": False,
        "credentials_loaded": False,
        "secrets_loaded": False,
        "network_called": False,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "next_allowed_step": "DESIGN_REAL_POSTGRES_DRIVER_BINDING_CONTRACT",
    }


__all__ = [
    "HEALTHY",
    "FAILED",
    "SCHEMA_VERSION",
    "CommitOutcomeUnknownError",
    "FakePostgresBackend",
    "PostgresChatStoreAdapterSkeleton",
    "skeleton_policy",
]
