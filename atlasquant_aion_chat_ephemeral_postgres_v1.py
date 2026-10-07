"""Ephemeral PostgreSQL binding for AION Chat contract validation.

This module is intentionally restricted to disposable CI/test databases. It does
not read environment variables, resolve production secrets, deploy, invoke a
provider, arm the Global Worker, execute external actions, or write Core state.

The store receives a trusted connection factory from composition and reuses the
already-reviewed AION Chat adapter surface from the fake-backend stage.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable

import psycopg

from aion_chat.models import (
    Attachment,
    ContextSummary,
    Conversation,
    ConversationCheckpoint,
    Message,
    Scope,
    now,
)
from aion_chat.privacy import redact
from aion_chat.store import StorageUnavailableError
from atlasquant_aion_chat_postgres_store_adapter_fake_v1 import (
    CommitOutcomeUnknownError,
    PostgresChatStoreAdapterSkeleton,
)

SCHEMA_VERSION = 1
DB_SCHEMA = "aion_chat_ephemeral_v1"
REQUIRED_CONSTRAINTS = frozenset({
    "messages_scope_sequence_uq_v1",
    "messages_scope_conversation_message_uq_v1",
    "messages_scope_conversation_fk_v1",
    "idempotency_scope_conversation_fk_v1",
    "idempotency_scope_message_conversation_fk_v1",
    "attachments_scope_conversation_fk_v1",
    "checkpoints_scope_conversation_fk_v1",
    "summaries_scope_conversation_fk_v1",
})
HEALTHY = "healthy"
FAILED = "failed"
NEXT_ALLOWED_STEP = "REVIEW_EPHEMERAL_POSTGRES_EVIDENCE_BEFORE_ANY_PRODUCTION_BINDING"

ConnectionFactory = Callable[[], psycopg.Connection]


def _scope_tuple(scope: Scope) -> tuple[str, str, str]:
    if not isinstance(scope, Scope):
        raise TypeError("trusted Scope required")
    return scope.owner_id, scope.tenant_id, scope.workspace_id


def _dump(model: Any) -> str:
    return json.dumps(redact(asdict(model)), ensure_ascii=False, separators=(",", ":"))


def _load(model_type, value):
    if isinstance(value, str):
        payload = json.loads(value)
    else:
        payload = dict(value)
    return model_type(**payload)


def install_ephemeral_schema(connection_factory: ConnectionFactory) -> None:
    """Install the disposable CI schema explicitly; never called by store startup."""
    if not callable(connection_factory):
        raise TypeError("connection factory required")
    ddl = f"""
    CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA};

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.schema_meta(
        name TEXT PRIMARY KEY,
        version INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.conversations(
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        archived BOOLEAN NOT NULL,
        title TEXT NOT NULL,
        data JSONB NOT NULL,
        PRIMARY KEY(owner_id, tenant_id, workspace_id, id)
    );
    CREATE INDEX IF NOT EXISTS conversations_scope_recency_v1
      ON {DB_SCHEMA}.conversations(owner_id, tenant_id, workspace_id, archived, updated_at DESC, id DESC);

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.messages(
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        id TEXT NOT NULL,
        sequence INTEGER NOT NULL CHECK(sequence > 0),
        content TEXT NOT NULL,
        data JSONB NOT NULL,
        PRIMARY KEY(owner_id, tenant_id, workspace_id, id),
        CONSTRAINT messages_scope_sequence_uq_v1
          UNIQUE(owner_id, tenant_id, workspace_id, conversation_id, sequence),
        CONSTRAINT messages_scope_conversation_message_uq_v1
          UNIQUE(owner_id, tenant_id, workspace_id, conversation_id, id),
        CONSTRAINT messages_scope_conversation_fk_v1
          FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id)
          REFERENCES {DB_SCHEMA}.conversations(owner_id, tenant_id, workspace_id, id)
          ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS messages_scope_history_v1
      ON {DB_SCHEMA}.messages(owner_id, tenant_id, workspace_id, conversation_id, sequence);

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.message_idempotency(
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        message_id TEXT NOT NULL,
        PRIMARY KEY(owner_id, tenant_id, workspace_id, conversation_id, idempotency_key),
        CONSTRAINT idempotency_scope_conversation_fk_v1
          FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id)
          REFERENCES {DB_SCHEMA}.conversations(owner_id, tenant_id, workspace_id, id)
          ON DELETE CASCADE,
        CONSTRAINT idempotency_scope_message_conversation_fk_v1
          FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id, message_id)
          REFERENCES {DB_SCHEMA}.messages(owner_id, tenant_id, workspace_id, conversation_id, id)
          ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.attachments(
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        id TEXT NOT NULL,
        data JSONB NOT NULL,
        PRIMARY KEY(owner_id, tenant_id, workspace_id, id),
        CONSTRAINT attachments_scope_conversation_fk_v1
          FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id)
          REFERENCES {DB_SCHEMA}.conversations(owner_id, tenant_id, workspace_id, id)
          ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.checkpoints(
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        id TEXT NOT NULL,
        through_sequence INTEGER NOT NULL CHECK(through_sequence >= 0),
        data JSONB NOT NULL,
        PRIMARY KEY(owner_id, tenant_id, workspace_id, id),
        CONSTRAINT checkpoints_scope_conversation_fk_v1
          FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id)
          REFERENCES {DB_SCHEMA}.conversations(owner_id, tenant_id, workspace_id, id)
          ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS checkpoints_scope_latest_v1
      ON {DB_SCHEMA}.checkpoints(owner_id, tenant_id, workspace_id, conversation_id, through_sequence DESC, id DESC);

    CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.summaries(
        owner_id TEXT NOT NULL,
        tenant_id TEXT NOT NULL,
        workspace_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL,
        id TEXT NOT NULL,
        through_sequence INTEGER NOT NULL CHECK(through_sequence >= 0),
        data JSONB NOT NULL,
        PRIMARY KEY(owner_id, tenant_id, workspace_id, id),
        CONSTRAINT summaries_scope_conversation_fk_v1
          FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id)
          REFERENCES {DB_SCHEMA}.conversations(owner_id, tenant_id, workspace_id, id)
          ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS summaries_scope_latest_v1
      ON {DB_SCHEMA}.summaries(owner_id, tenant_id, workspace_id, conversation_id, through_sequence DESC, id DESC);
    """
    conn = connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
            cur.execute(
                f"INSERT INTO {DB_SCHEMA}.schema_meta(name, version) VALUES (%s, %s) "
                "ON CONFLICT(name) DO UPDATE SET version=EXCLUDED.version",
                ("aion_chat", SCHEMA_VERSION),
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def reset_ephemeral_schema(connection_factory: ConnectionFactory) -> None:
    """Reset only the named disposable schema used by this CI contract."""
    conn = connection_factory()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {DB_SCHEMA} CASCADE")
        conn.commit()
    finally:
        conn.close()


class EphemeralPostgresBackendV1:
    """Real psycopg backend permitted only for disposable CI/test PostgreSQL."""

    def __init__(self, connection_factory: ConnectionFactory, *, environment: str = "CI"):
        if not callable(connection_factory):
            raise TypeError("connection factory required")
        normalized = str(environment or "").strip().upper()
        if normalized not in {"CI", "TEST"}:
            raise ValueError("ephemeral CI/TEST environment required")
        self._connect = connection_factory
        self.environment = normalized
        self.commit_outcome_unknown_once = False

    def _connection(self) -> psycopg.Connection:
        try:
            conn = self._connect()
        except Exception as exc:
            raise StorageUnavailableError("ephemeral postgres connection unavailable") from exc
        try:
            conn.autocommit = False
        except Exception as exc:
            try:
                conn.close()
            except Exception:
                pass
            raise StorageUnavailableError("ephemeral postgres transaction mode unavailable") from exc
        return conn

    def health_report(self) -> dict[str, Any]:
        report = {
            "state": FAILED,
            "schema_version": None,
            "expected_schema_version": SCHEMA_VERSION,
            "scope_policy_healthy": False,
            "transaction_healthy": False,
            "required_constraints_present": 0,
            "required_constraints_expected": len(REQUIRED_CONSTRAINTS),
            "backend": "ephemeral_postgres_ci",
            "environment": self.environment,
            "production_allowed": False,
            "provider_called": False,
            "billing_executed": False,
            "deploy_executed": False,
            "worker_armed": False,
            "external_action_executed": False,
            "core_checkpoint_write": False,
        }
        conn = None
        try:
            conn = self._connection()
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT version FROM {DB_SCHEMA}.schema_meta WHERE name=%s",
                    ("aion_chat",),
                )
                row = cur.fetchone()
                version = int(row[0]) if row else None
                cur.execute(
                    "SELECT to_regclass(%s), to_regclass(%s), to_regclass(%s), "
                    "to_regclass(%s), to_regclass(%s), to_regclass(%s)",
                    tuple(
                        f"{DB_SCHEMA}.{name}"
                        for name in (
                            "conversations",
                            "messages",
                            "message_idempotency",
                            "attachments",
                            "checkpoints",
                            "summaries",
                        )
                    ),
                )
                required = cur.fetchone()
                tables_ok = bool(required) and all(value is not None for value in required)
                cur.execute(
                    "SELECT conname FROM pg_constraint c "
                    "JOIN pg_namespace n ON n.oid=c.connamespace "
                    "WHERE n.nspname=%s AND conname = ANY(%s)",
                    (DB_SCHEMA, list(REQUIRED_CONSTRAINTS)),
                )
                present_constraints = {row[0] for row in cur.fetchall()}
                constraints_ok = present_constraints == REQUIRED_CONSTRAINTS
                cur.execute("SAVEPOINT aion_health_probe")
                cur.execute("SELECT 1")
                transaction_ok = cur.fetchone() == (1,)
                cur.execute("ROLLBACK TO SAVEPOINT aion_health_probe")
                cur.execute("RELEASE SAVEPOINT aion_health_probe")
            conn.rollback()
            scope_policy_ok = tables_ok and constraints_ok
            healthy = version == SCHEMA_VERSION and scope_policy_ok and transaction_ok
            report.update(
                state=HEALTHY if healthy else FAILED,
                schema_version=version,
                scope_policy_healthy=scope_policy_ok,
                transaction_healthy=transaction_ok,
                required_constraints_present=len(present_constraints),
                required_constraints_expected=len(REQUIRED_CONSTRAINTS),
            )
            return report
        except Exception:
            return report
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def require_healthy(self) -> dict[str, Any]:
        report = self.health_report()
        if report["state"] != HEALTHY:
            raise StorageUnavailableError("ephemeral postgres store health is not proven")
        return report

    def create_conversation(self, scope: Scope, conversation: Conversation) -> Conversation:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {DB_SCHEMA}.conversations"
                    "(owner_id,tenant_id,workspace_id,id,updated_at,archived,title,data) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        owner,
                        tenant,
                        workspace,
                        conversation.id,
                        conversation.updated_at,
                        conversation.archived,
                        conversation.title,
                        _dump(conversation),
                    ),
                )
            conn.commit()
            return Conversation(**asdict(conversation))
        except psycopg.errors.UniqueViolation as exc:
            conn.rollback()
            raise ValueError("conversation already exists") from exc
        except Exception as exc:
            conn.rollback()
            if isinstance(exc, (ValueError, LookupError, TypeError)):
                raise
            raise StorageUnavailableError("ephemeral postgres create failed") from exc
        finally:
            conn.close()

    def get_conversation(self, scope: Scope, conversation_id: str) -> Conversation:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s",
                    (owner, tenant, workspace, str(conversation_id)),
                )
                row = cur.fetchone()
            conn.rollback()
            if row is None:
                raise LookupError("conversation unavailable")
            return _load(Conversation, row[0])
        finally:
            conn.close()

    def list_conversations(self, scope: Scope) -> list[Conversation]:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "ORDER BY updated_at DESC,id DESC LIMIT 201",
                    (owner, tenant, workspace),
                )
                rows = cur.fetchall()
            conn.rollback()
            return [_load(Conversation, row[0]) for row in rows]
        finally:
            conn.close()

    def update_conversation(self, scope: Scope, conversation: Conversation) -> Conversation:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {DB_SCHEMA}.conversations "
                    "SET updated_at=%s, archived=%s, title=%s, data=%s::jsonb "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s",
                    (
                        conversation.updated_at,
                        conversation.archived,
                        conversation.title,
                        _dump(conversation),
                        owner,
                        tenant,
                        workspace,
                        conversation.id,
                    ),
                )
                changed = cur.rowcount
            conn.commit()
            if changed != 1:
                raise LookupError("conversation unavailable")
            return Conversation(**asdict(conversation))
        finally:
            conn.close()

    def append_message_atomic(
        self,
        scope: Scope,
        message: Message,
        *,
        idempotency_key: str,
    ) -> Message:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        key = str(idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency_key required")
        conn = self._connection()
        stored = None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s FOR UPDATE",
                    (owner, tenant, workspace, message.conversation_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise LookupError("conversation unavailable")
                conversation = _load(Conversation, row[0])

                cur.execute(
                    f"SELECT message_id FROM {DB_SCHEMA}.message_idempotency "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND conversation_id=%s AND idempotency_key=%s",
                    (owner, tenant, workspace, message.conversation_id, key),
                )
                prior = cur.fetchone()
                if prior is not None:
                    cur.execute(
                        f"SELECT data FROM {DB_SCHEMA}.messages "
                        "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                        "AND conversation_id=%s AND id=%s",
                        (owner, tenant, workspace, message.conversation_id, prior[0]),
                    )
                    existing = cur.fetchone()
                    if existing is None:
                        raise StorageUnavailableError("idempotency index is inconsistent")
                    stored = _load(Message, existing[0])
                else:
                    stored = Message(**redact(asdict(message)))
                    stored.sequence = conversation.message_count + 1
                    cur.execute(
                        f"INSERT INTO {DB_SCHEMA}.messages"
                        "(owner_id,tenant_id,workspace_id,conversation_id,id,sequence,content,data) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                        (
                            owner,
                            tenant,
                            workspace,
                            stored.conversation_id,
                            stored.id,
                            stored.sequence,
                            stored.content,
                            _dump(stored),
                        ),
                    )
                    cur.execute(
                        f"INSERT INTO {DB_SCHEMA}.message_idempotency"
                        "(owner_id,tenant_id,workspace_id,conversation_id,idempotency_key,message_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        (
                            owner,
                            tenant,
                            workspace,
                            stored.conversation_id,
                            key,
                            stored.id,
                        ),
                    )
                    conversation.message_count = stored.sequence
                    conversation.updated_at = now()
                    cur.execute(
                        f"UPDATE {DB_SCHEMA}.conversations SET updated_at=%s,data=%s::jsonb "
                        "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s",
                        (
                            conversation.updated_at,
                            _dump(conversation),
                            owner,
                            tenant,
                            workspace,
                            conversation.id,
                        ),
                    )
            try:
                conn.commit()
            except Exception as exc:
                raise CommitOutcomeUnknownError(key) from exc
            if self.commit_outcome_unknown_once:
                self.commit_outcome_unknown_once = False
                raise CommitOutcomeUnknownError(key)
            return stored
        except CommitOutcomeUnknownError:
            raise
        except psycopg.errors.UniqueViolation as exc:
            conn.rollback()
            raise ValueError("storage uniqueness constraint rejected write") from exc
        except (LookupError, ValueError, TypeError, StorageUnavailableError):
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise StorageUnavailableError("ephemeral postgres append failed") from exc
        finally:
            conn.close()

    def find_by_idempotency(
        self,
        scope: Scope,
        conversation_id: str,
        idempotency_key: str,
    ) -> Message | None:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT m.data FROM {DB_SCHEMA}.message_idempotency i "
                    f"JOIN {DB_SCHEMA}.messages m ON "
                    "m.owner_id=i.owner_id AND m.tenant_id=i.tenant_id AND "
                    "m.workspace_id=i.workspace_id AND m.id=i.message_id "
                    "WHERE i.owner_id=%s AND i.tenant_id=%s AND i.workspace_id=%s "
                    "AND i.conversation_id=%s AND i.idempotency_key=%s",
                    (
                        owner,
                        tenant,
                        workspace,
                        str(conversation_id),
                        str(idempotency_key),
                    ),
                )
                row = cur.fetchone()
            conn.rollback()
            return _load(Message, row[0]) if row else None
        finally:
            conn.close()

    def list_messages(self, scope: Scope, conversation_id: str) -> list[Message]:
        self.get_conversation(scope, conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.messages "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND conversation_id=%s "
                    "ORDER BY sequence ASC LIMIT 201",
                    (owner, tenant, workspace, str(conversation_id)),
                )
                rows = cur.fetchall()
            conn.rollback()
            return [_load(Message, row[0]) for row in rows]
        finally:
            conn.close()

    def get_message(self, scope: Scope, conversation_id: str, message_id: str) -> Message:
        self.get_conversation(scope, conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.messages WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND conversation_id=%s AND id=%s",
                    (
                        owner,
                        tenant,
                        workspace,
                        str(conversation_id),
                        str(message_id),
                    ),
                )
                row = cur.fetchone()
            conn.rollback()
            if row is None:
                raise LookupError("message unavailable")
            return _load(Message, row[0])
        finally:
            conn.close()

    def save_attachment(self, scope: Scope, attachment: Attachment) -> Attachment:
        self.get_conversation(scope, attachment.conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {DB_SCHEMA}.attachments"
                    "(owner_id,tenant_id,workspace_id,conversation_id,id,data) "
                    "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        owner,
                        tenant,
                        workspace,
                        attachment.conversation_id,
                        attachment.id,
                        _dump(attachment),
                    ),
                )
            conn.commit()
            return Attachment(**asdict(attachment))
        except psycopg.errors.UniqueViolation as exc:
            conn.rollback()
            raise ValueError("attachment already exists") from exc
        finally:
            conn.close()

    def get_attachment(
        self,
        scope: Scope,
        conversation_id: str,
        attachment_id: str,
    ) -> Attachment:
        self.get_conversation(scope, conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.attachments WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND conversation_id=%s AND id=%s",
                    (
                        owner,
                        tenant,
                        workspace,
                        str(conversation_id),
                        str(attachment_id),
                    ),
                )
                row = cur.fetchone()
            conn.rollback()
            if row is None:
                raise LookupError("attachment unavailable")
            return _load(Attachment, row[0])
        finally:
            conn.close()

    def save_checkpoint(
        self,
        scope: Scope,
        checkpoint: ConversationCheckpoint,
    ) -> ConversationCheckpoint:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.conversations WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND id=%s FOR UPDATE",
                    (owner, tenant, workspace, checkpoint.conversation_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise LookupError("conversation unavailable")
                conversation = _load(Conversation, row[0])
                cur.execute(
                    f"SELECT through_sequence FROM {DB_SCHEMA}.checkpoints "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND conversation_id=%s "
                    "ORDER BY through_sequence DESC,id DESC LIMIT 1",
                    (owner, tenant, workspace, checkpoint.conversation_id),
                )
                prior = cur.fetchone()
                if prior and checkpoint.through_sequence <= int(prior[0]):
                    raise ValueError("coverage must advance")
                if checkpoint.through_sequence > conversation.message_count:
                    raise ValueError("coverage beyond conversation")
                cur.execute(
                    f"INSERT INTO {DB_SCHEMA}.checkpoints"
                    "(owner_id,tenant_id,workspace_id,conversation_id,id,through_sequence,data) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        owner,
                        tenant,
                        workspace,
                        checkpoint.conversation_id,
                        checkpoint.id,
                        checkpoint.through_sequence,
                        _dump(checkpoint),
                    ),
                )
                conversation.latest_checkpoint = checkpoint.id
                conversation.updated_at = now()
                cur.execute(
                    f"UPDATE {DB_SCHEMA}.conversations SET updated_at=%s,data=%s::jsonb "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s",
                    (
                        conversation.updated_at,
                        _dump(conversation),
                        owner,
                        tenant,
                        workspace,
                        conversation.id,
                    ),
                )
            conn.commit()
            return ConversationCheckpoint(**asdict(checkpoint))
        except (LookupError, ValueError):
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_latest_checkpoint(
        self,
        scope: Scope,
        conversation_id: str,
    ) -> ConversationCheckpoint | None:
        self.get_conversation(scope, conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.checkpoints WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND conversation_id=%s "
                    "ORDER BY through_sequence DESC,id DESC LIMIT 1",
                    (owner, tenant, workspace, str(conversation_id)),
                )
                row = cur.fetchone()
            conn.rollback()
            return _load(ConversationCheckpoint, row[0]) if row else None
        finally:
            conn.close()

    def save_summary(self, scope: Scope, summary: ContextSummary) -> ContextSummary:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.conversations WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND id=%s FOR UPDATE",
                    (owner, tenant, workspace, summary.conversation_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise LookupError("conversation unavailable")
                conversation = _load(Conversation, row[0])
                if summary.through_sequence > conversation.message_count:
                    raise ValueError("coverage beyond conversation")
                for message_id in summary.source_message_ids:
                    cur.execute(
                        f"SELECT sequence FROM {DB_SCHEMA}.messages WHERE owner_id=%s AND tenant_id=%s "
                        "AND workspace_id=%s AND conversation_id=%s AND id=%s",
                        (
                            owner,
                            tenant,
                            workspace,
                            summary.conversation_id,
                            message_id,
                        ),
                    )
                    source = cur.fetchone()
                    if source is None:
                        raise LookupError("summary source message unavailable")
                    if int(source[0]) > summary.through_sequence:
                        raise ValueError("source beyond coverage")
                cur.execute(
                    f"INSERT INTO {DB_SCHEMA}.summaries"
                    "(owner_id,tenant_id,workspace_id,conversation_id,id,through_sequence,data) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        owner,
                        tenant,
                        workspace,
                        summary.conversation_id,
                        summary.id,
                        summary.through_sequence,
                        _dump(summary),
                    ),
                )
            conn.commit()
            return ContextSummary(**asdict(summary))
        except (LookupError, ValueError):
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_latest_summary(
        self,
        scope: Scope,
        conversation_id: str,
    ) -> ContextSummary | None:
        self.get_conversation(scope, conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {DB_SCHEMA}.summaries WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND conversation_id=%s "
                    "ORDER BY through_sequence DESC,id DESC LIMIT 1",
                    (owner, tenant, workspace, str(conversation_id)),
                )
                row = cur.fetchone()
            conn.rollback()
            return _load(ContextSummary, row[0]) if row else None
        finally:
            conn.close()


class EphemeralPostgresChatStoreV1(PostgresChatStoreAdapterSkeleton):
    """AionChatStore-compatible adapter over the real disposable PostgreSQL backend."""

    def __init__(self, backend: EphemeralPostgresBackendV1):
        if not isinstance(backend, EphemeralPostgresBackendV1):
            raise TypeError("EphemeralPostgresBackendV1 required")
        self.backend = backend


def ephemeral_policy() -> dict[str, Any]:
    return {
        "schema": "ATLASQUANT_AION_CHAT_EPHEMERAL_POSTGRES_V1",
        "driver": "psycopg",
        "driver_version": str(psycopg.__version__),
        "environment_allowed": ["CI", "TEST"],
        "production_allowed": False,
        "environment_read_by_store": False,
        "secret_lookup_by_store": False,
        "database_url_read_by_store": False,
        "explicit_schema_install_only": True,
        "provider_called": False,
        "billing_executed": False,
        "deploy_executed": False,
        "worker_armed": False,
        "external_action_executed": False,
        "core_checkpoint_write": False,
        "next_allowed_step": NEXT_ALLOWED_STEP,
    }


__all__ = [
    "SCHEMA_VERSION",
    "DB_SCHEMA",
    "REQUIRED_CONSTRAINTS",
    "HEALTHY",
    "FAILED",
    "NEXT_ALLOWED_STEP",
    "install_ephemeral_schema",
    "reset_ephemeral_schema",
    "EphemeralPostgresBackendV1",
    "EphemeralPostgresChatStoreV1",
    "ephemeral_policy",
]
