-- AtlasQuant/AION Chat PostgreSQL schema migration V1.
-- Production-like candidate validated only against disposable CI PostgreSQL.
-- Application startup MUST NOT execute this migration implicitly.

CREATE SCHEMA IF NOT EXISTS aion_chat_v1;

CREATE TABLE aion_chat_v1.schema_migrations(
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE aion_chat_v1.schema_meta(
    name TEXT PRIMARY KEY,
    version INTEGER NOT NULL
);

INSERT INTO aion_chat_v1.schema_meta(name, version)
VALUES ('aion_chat', 1)
ON CONFLICT(name) DO UPDATE SET version=EXCLUDED.version;

CREATE TABLE aion_chat_v1.conversations(
    owner_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    title TEXT NOT NULL,
    data JSONB NOT NULL,
    PRIMARY KEY(owner_id, tenant_id, workspace_id, id)
);

CREATE INDEX conversations_scope_recency_v1
ON aion_chat_v1.conversations(
    owner_id, tenant_id, workspace_id, archived, updated_at DESC, id DESC
);

CREATE TABLE aion_chat_v1.messages(
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
      REFERENCES aion_chat_v1.conversations(owner_id, tenant_id, workspace_id, id)
      ON DELETE CASCADE
);

CREATE INDEX messages_scope_history_v1
ON aion_chat_v1.messages(
    owner_id, tenant_id, workspace_id, conversation_id, sequence
);

CREATE TABLE aion_chat_v1.message_idempotency(
    owner_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    message_id TEXT NOT NULL,
    PRIMARY KEY(
        owner_id, tenant_id, workspace_id, conversation_id, idempotency_key
    ),
    CONSTRAINT idempotency_scope_conversation_fk_v1
      FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id)
      REFERENCES aion_chat_v1.conversations(owner_id, tenant_id, workspace_id, id)
      ON DELETE CASCADE,
    CONSTRAINT idempotency_scope_message_conversation_fk_v1
      FOREIGN KEY(
          owner_id, tenant_id, workspace_id, conversation_id, message_id
      )
      REFERENCES aion_chat_v1.messages(
          owner_id, tenant_id, workspace_id, conversation_id, id
      )
      ON DELETE CASCADE
);

CREATE TABLE aion_chat_v1.attachments(
    owner_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    id TEXT NOT NULL,
    data JSONB NOT NULL,
    PRIMARY KEY(owner_id, tenant_id, workspace_id, id),
    CONSTRAINT attachments_scope_conversation_fk_v1
      FOREIGN KEY(owner_id, tenant_id, workspace_id, conversation_id)
      REFERENCES aion_chat_v1.conversations(owner_id, tenant_id, workspace_id, id)
      ON DELETE CASCADE
);

CREATE TABLE aion_chat_v1.checkpoints(
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
      REFERENCES aion_chat_v1.conversations(owner_id, tenant_id, workspace_id, id)
      ON DELETE CASCADE
);

CREATE INDEX checkpoints_scope_latest_v1
ON aion_chat_v1.checkpoints(
    owner_id, tenant_id, workspace_id, conversation_id,
    through_sequence DESC, id DESC
);

CREATE TABLE aion_chat_v1.summaries(
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
      REFERENCES aion_chat_v1.conversations(owner_id, tenant_id, workspace_id, id)
      ON DELETE CASCADE
);

CREATE INDEX summaries_scope_latest_v1
ON aion_chat_v1.summaries(
    owner_id, tenant_id, workspace_id, conversation_id,
    through_sequence DESC, id DESC
);

CREATE TABLE aion_chat_v1.access_audit(
    owner_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    id TEXT NOT NULL,
    operation TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    result TEXT NOT NULL,
    evidence_digest TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(owner_id, tenant_id, workspace_id, id)
);

CREATE INDEX access_audit_scope_time_v1
ON aion_chat_v1.access_audit(
    owner_id, tenant_id, workspace_id, created_at DESC, id DESC
);

ALTER TABLE aion_chat_v1.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.messages FORCE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.message_idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.message_idempotency FORCE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.attachments FORCE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.checkpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.summaries FORCE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.access_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE aion_chat_v1.access_audit FORCE ROW LEVEL SECURITY;

CREATE POLICY conversations_scope_policy_v1
ON aion_chat_v1.conversations
USING (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
)
WITH CHECK (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
);

CREATE POLICY messages_scope_policy_v1
ON aion_chat_v1.messages
USING (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
)
WITH CHECK (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
);

CREATE POLICY idempotency_scope_policy_v1
ON aion_chat_v1.message_idempotency
USING (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
)
WITH CHECK (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
);

CREATE POLICY attachments_scope_policy_v1
ON aion_chat_v1.attachments
USING (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
)
WITH CHECK (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
);

CREATE POLICY checkpoints_scope_policy_v1
ON aion_chat_v1.checkpoints
USING (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
)
WITH CHECK (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
);

CREATE POLICY summaries_scope_policy_v1
ON aion_chat_v1.summaries
USING (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
)
WITH CHECK (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
);

CREATE POLICY access_audit_scope_policy_v1
ON aion_chat_v1.access_audit
USING (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
)
WITH CHECK (
    owner_id = current_setting('app.owner_id', true)
    AND tenant_id = current_setting('app.tenant_id', true)
    AND workspace_id = current_setting('app.workspace_id', true)
);
