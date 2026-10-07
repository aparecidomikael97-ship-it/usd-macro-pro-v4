"""Ephemeral PostgreSQL binding for AION Chat contract validation.

This module is intentionally restricted to disposable CI/test databases. It does
not read environment variables, resolve production secrets, deploy, invoke a
provider, arm the Global Worker, execute external actions, or write Core state.

The store receives a trusted connection factory from composition and reuses the
already-reviewed AION Chat adapter surface from the fake-backend stage.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
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
    Page,
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


class BoundCursorCodecV1:
    """Opaque HMAC-authenticated cursor bound to scope, resource and query."""

    VERSION = 1
    MIN_KEY_BYTES = 32

    def __init__(self, signing_key: bytes):
        if not isinstance(signing_key, bytes) or len(signing_key) < self.MIN_KEY_BYTES:
            raise ValueError("cursor signing key must be at least 32 bytes")
        self._key = bytes(signing_key)

    @staticmethod
    def _b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        if not isinstance(value, str) or not value:
            raise ValueError("cursor invalid or not bound to this query")
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))

    @staticmethod
    def _canonical(value: Any) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def _digest(self, label: bytes, value: Any) -> str:
        return hmac.new(
            self._key,
            label + b"\x00" + self._canonical(value),
            hashlib.sha256,
        ).hexdigest()

    def encode(
        self,
        *,
        kind: str,
        scope: Scope,
        spec: dict[str, Any],
        position: Any,
    ) -> str:
        owner, tenant, workspace = _scope_tuple(scope)
        payload = {
            "v": self.VERSION,
            "k": str(kind),
            "s": self._digest(b"scope", [owner, tenant, workspace]),
            "q": self._digest(b"spec", spec),
            "p": position,
        }
        body = self._canonical(payload)
        signature = hmac.new(self._key, body, hashlib.sha256).digest()
        return self._b64encode(body) + "." + self._b64encode(signature)

    def decode(
        self,
        token: str,
        *,
        kind: str,
        scope: Scope,
        spec: dict[str, Any],
    ) -> Any:
        try:
            body_part, signature_part = str(token).split(".", 1)
            body = self._b64decode(body_part)
            signature = self._b64decode(signature_part)
            expected_signature = hmac.new(self._key, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected_signature):
                raise ValueError
            payload = json.loads(body.decode("utf-8"))
            owner, tenant, workspace = _scope_tuple(scope)
            if payload.get("v") != self.VERSION:
                raise ValueError
            if payload.get("k") != str(kind):
                raise ValueError
            if not hmac.compare_digest(
                str(payload.get("s") or ""),
                self._digest(b"scope", [owner, tenant, workspace]),
            ):
                raise ValueError
            if not hmac.compare_digest(
                str(payload.get("q") or ""),
                self._digest(b"spec", spec),
            ):
                raise ValueError
            if "p" not in payload:
                raise ValueError
            return payload["p"]
        except Exception as exc:
            raise ValueError("cursor invalid or not bound to this query") from exc


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
        created_at TEXT NOT NULL,
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

    def __init__(
        self,
        connection_factory: ConnectionFactory,
        *,
        environment: str = "CI",
        schema: str = self.schema,
    ):
        if not callable(connection_factory):
            raise TypeError("connection factory required")
        normalized = str(environment or "").strip().upper()
        if normalized not in {"CI", "TEST"}:
            raise ValueError("ephemeral CI/TEST environment required")
        schema_name = str(schema or "").strip()
        if (
            not schema_name
            or not schema_name.replace("_", "").isalnum()
            or not (schema_name[0].isalpha() or schema_name[0] == "_")
        ):
            raise ValueError("trusted PostgreSQL schema identifier required")
        self._connect = connection_factory
        self.environment = normalized
        self.schema = schema_name
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

    def _bind_scope(self, conn: psycopg.Connection, scope: Scope) -> None:
        """Hook for stronger CI bindings; base ephemeral schema has no RLS."""
        _scope_tuple(scope)

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
                    f"SELECT version FROM {self.schema}.schema_meta WHERE name=%s",
                    ("aion_chat",),
                )
                row = cur.fetchone()
                version = int(row[0]) if row else None
                cur.execute(
                    "SELECT to_regclass(%s), to_regclass(%s), to_regclass(%s), "
                    "to_regclass(%s), to_regclass(%s), to_regclass(%s)",
                    tuple(
                        f"{self.schema}.{name}"
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
                    (self.schema, list(REQUIRED_CONSTRAINTS)),
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {self.schema}.conversations"
                    "(owner_id,tenant_id,workspace_id,id,created_at,updated_at,archived,title,data) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        owner,
                        tenant,
                        workspace,
                        conversation.id,
                        conversation.created_at,
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.conversations "
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "ORDER BY updated_at DESC,id DESC LIMIT 201",
                    (owner, tenant, workspace),
                )
                rows = cur.fetchall()
            conn.rollback()
            return [_load(Conversation, row[0]) for row in rows]
        finally:
            conn.close()

    def list_conversations_page(
        self,
        scope: Scope,
        *,
        after: tuple[str, str] | None,
        limit: int,
        query: str,
        tag: str | None,
        since: str | None,
        until: str | None,
        archived: bool,
    ) -> list[Conversation]:
        self.require_healthy()
        owner, tenant, workspace = _scope_tuple(scope)
        clauses = [
            "c.owner_id=%s",
            "c.tenant_id=%s",
            "c.workspace_id=%s",
            "c.archived=%s",
        ]
        params: list[Any] = [owner, tenant, workspace, bool(archived)]
        if query:
            clauses.append(
                "(STRPOS(LOWER(c.title), LOWER(%s)) > 0 OR EXISTS ("
                f"SELECT 1 FROM {self.schema}.messages m "
                "WHERE m.owner_id=c.owner_id AND m.tenant_id=c.tenant_id "
                "AND m.workspace_id=c.workspace_id AND m.conversation_id=c.id "
                "AND STRPOS(LOWER(m.content), LOWER(%s)) > 0))"
            )
            params.extend([query, query])
        if tag is not None:
            clauses.append(
                "COALESCE(c.data->'metadata'->'tags','[]'::jsonb) ? %s"
            )
            params.append(tag)
        if since:
            clauses.append("c.updated_at >= %s")
            params.append(since)
        if until:
            clauses.append("c.updated_at <= %s")
            params.append(until)
        if after is not None:
            clauses.append("(c.updated_at,c.id) < (%s,%s)")
            params.extend([after[0], after[1]])
        params.append(int(limit))
        conn = self._connection()
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT c.data FROM {self.schema}.conversations c WHERE "
                    + " AND ".join(clauses)
                    + " ORDER BY c.updated_at DESC,c.id DESC LIMIT %s",
                    tuple(params),
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {self.schema}.conversations "
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
                    f"SELECT data FROM {self.schema}.conversations "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND id=%s FOR UPDATE",
                    (owner, tenant, workspace, message.conversation_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise LookupError("conversation unavailable")
                conversation = _load(Conversation, row[0])

                cur.execute(
                    f"SELECT message_id FROM {self.schema}.message_idempotency "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND conversation_id=%s AND idempotency_key=%s",
                    (owner, tenant, workspace, message.conversation_id, key),
                )
                prior = cur.fetchone()
                if prior is not None:
                    cur.execute(
                        f"SELECT data FROM {self.schema}.messages "
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
                        f"INSERT INTO {self.schema}.messages"
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
                        f"INSERT INTO {self.schema}.message_idempotency"
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
                        f"UPDATE {self.schema}.conversations SET updated_at=%s,data=%s::jsonb "
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT m.data FROM {self.schema}.message_idempotency i "
                    f"JOIN {self.schema}.messages m ON "
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.messages "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s AND conversation_id=%s "
                    "ORDER BY sequence ASC LIMIT 201",
                    (owner, tenant, workspace, str(conversation_id)),
                )
                rows = cur.fetchall()
            conn.rollback()
            return [_load(Message, row[0]) for row in rows]
        finally:
            conn.close()

    def list_messages_page(
        self,
        scope: Scope,
        conversation_id: str,
        *,
        after_sequence: int | None,
        limit: int,
        newest_first: bool,
    ) -> list[Message]:
        self.get_conversation(scope, conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        clauses = [
            "owner_id=%s",
            "tenant_id=%s",
            "workspace_id=%s",
            "conversation_id=%s",
        ]
        params: list[Any] = [owner, tenant, workspace, str(conversation_id)]
        if after_sequence is not None:
            clauses.append("sequence < %s" if newest_first else "sequence > %s")
            params.append(int(after_sequence))
        params.append(int(limit))
        direction = "DESC" if newest_first else "ASC"
        conn = self._connection()
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.messages WHERE "
                    + " AND ".join(clauses)
                    + f" ORDER BY sequence {direction} LIMIT %s",
                    tuple(params),
                )
                rows = cur.fetchall()
            conn.rollback()
            return [_load(Message, row[0]) for row in rows]
        finally:
            conn.close()

    def retrieve_messages_page(
        self,
        scope: Scope,
        conversation_id: str,
        query: str,
        *,
        before_sequence: int,
        limit: int,
    ) -> list[Message]:
        self.get_conversation(scope, conversation_id)
        owner, tenant, workspace = _scope_tuple(scope)
        conn = self._connection()
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.messages "
                    "WHERE owner_id=%s AND tenant_id=%s AND workspace_id=%s "
                    "AND conversation_id=%s AND sequence < %s "
                    "AND STRPOS(LOWER(content), LOWER(%s)) > 0 "
                    "ORDER BY sequence DESC LIMIT %s",
                    (
                        owner,
                        tenant,
                        workspace,
                        str(conversation_id),
                        int(before_sequence),
                        query,
                        int(limit),
                    ),
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.messages WHERE owner_id=%s AND tenant_id=%s "
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {self.schema}.attachments"
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.attachments WHERE owner_id=%s AND tenant_id=%s "
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.conversations WHERE owner_id=%s AND tenant_id=%s "
                    "AND workspace_id=%s AND id=%s FOR UPDATE",
                    (owner, tenant, workspace, checkpoint.conversation_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise LookupError("conversation unavailable")
                conversation = _load(Conversation, row[0])
                cur.execute(
                    f"SELECT through_sequence FROM {self.schema}.checkpoints "
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
                    f"INSERT INTO {self.schema}.checkpoints"
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
                    f"UPDATE {self.schema}.conversations SET updated_at=%s,data=%s::jsonb "
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.checkpoints WHERE owner_id=%s AND tenant_id=%s "
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.conversations WHERE owner_id=%s AND tenant_id=%s "
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
                        f"SELECT sequence FROM {self.schema}.messages WHERE owner_id=%s AND tenant_id=%s "
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
                    f"INSERT INTO {self.schema}.summaries"
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
        self._bind_scope(conn, scope)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT data FROM {self.schema}.summaries WHERE owner_id=%s AND tenant_id=%s "
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

    def __init__(
        self,
        backend: EphemeralPostgresBackendV1,
        *,
        cursor_signing_key: bytes,
    ):
        if not isinstance(backend, EphemeralPostgresBackendV1):
            raise TypeError("EphemeralPostgresBackendV1 required")
        self.backend = backend
        self._cursor = BoundCursorCodecV1(cursor_signing_key)

    @staticmethod
    def _conversation_spec(
        *,
        query: str,
        tag: str | None,
        since: str | None,
        until: str | None,
        archived: bool,
    ) -> dict[str, Any]:
        return {
            "query": str(query or "").strip(),
            "tag": None if tag is None else str(tag),
            "since": None if since in (None, "") else str(since),
            "until": None if until in (None, "") else str(until),
            "archived": bool(archived),
        }

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
        scope = self._scope(scope)
        size = self._size(page_size)
        spec = self._conversation_spec(
            query=query,
            tag=tag,
            since=since,
            until=until,
            archived=archived,
        )
        after = None
        if cursor not in (None, ""):
            position = self._cursor.decode(
                str(cursor),
                kind="conversations",
                scope=scope,
                spec=spec,
            )
            if (
                not isinstance(position, list)
                or len(position) != 2
                or not all(isinstance(value, str) and value for value in position)
            ):
                raise ValueError("cursor invalid or not bound to this query")
            after = (position[0], position[1])

        rows = self.backend.list_conversations_page(
            scope,
            after=after,
            limit=size + 1,
            query=spec["query"],
            tag=spec["tag"],
            since=spec["since"],
            until=spec["until"],
            archived=spec["archived"],
        )
        has_more = len(rows) > size
        items = rows[:size]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = self._cursor.encode(
                kind="conversations",
                scope=scope,
                spec=spec,
                position=[last.updated_at, last.id],
            )
        return Page(items, next_cursor)

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
        scope = self._scope(scope)
        size = self._size(page_size)
        conversation_id = str(conversation_id)
        spec = {
            "conversation_id": conversation_id,
            "newest_first": bool(newest_first),
        }
        after_sequence = None
        if cursor not in (None, ""):
            position = self._cursor.decode(
                str(cursor),
                kind="messages",
                scope=scope,
                spec=spec,
            )
            if not isinstance(position, int) or position < 1:
                raise ValueError("cursor invalid or not bound to this query")
            after_sequence = position

        rows = self.backend.list_messages_page(
            scope,
            conversation_id,
            after_sequence=after_sequence,
            limit=size + 1,
            newest_first=bool(newest_first),
        )
        has_more = len(rows) > size
        items = rows[:size]
        next_cursor = None
        if has_more and items:
            next_cursor = self._cursor.encode(
                kind="messages",
                scope=scope,
                spec=spec,
                position=items[-1].sequence,
            )
        return Page(items, next_cursor)

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
        scope = self._scope(scope)
        size = self._size(limit)
        query = str(query or "").strip()
        if not query:
            return []
        return self.backend.retrieve_messages_page(
            scope,
            str(conversation_id),
            query,
            before_sequence=int(before_sequence),
            limit=size,
        )


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
        "cursor_pagination_bound": True,
        "cursor_scope_binding": True,
        "cursor_query_binding": True,
        "cursor_hmac_authenticated": True,
        "cursor_key_read_by_store": False,
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
    "BoundCursorCodecV1",
    "install_ephemeral_schema",
    "reset_ephemeral_schema",
    "EphemeralPostgresBackendV1",
    "EphemeralPostgresChatStoreV1",
    "ephemeral_policy",
]
