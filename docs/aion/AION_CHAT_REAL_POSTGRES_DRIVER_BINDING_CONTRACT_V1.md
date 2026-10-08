# AION Chat — Real PostgreSQL Driver Binding Contract V1

Status: DESIGN ONLY  
Date: 2026-10-07  
Dependency: PR #986 / `PostgresChatStoreAdapterSkeleton`  
Runtime effect: NONE

## 1. Purpose

Define the exact safety, transaction, scope, idempotency, health and configuration contract that a future real PostgreSQL-backed AION Chat store MUST satisfy before any production database connection is permitted.

This document does **not** authorize or implement:
- a Postgres driver import;
- `DATABASE_URL` or any credential lookup;
- a real database connection;
- SQL execution;
- schema migration;
- Render/provider configuration;
- deploy;
- Global Worker;
- external actions;
- Core checkpoint writes.

The next implementation stage must remain isolated to an ephemeral test database until separately reviewed.

## 2. Compatibility target

The future implementation MUST preserve the existing `AionChatStore` method surface and model semantics from:
- `Scope`
- `Conversation`
- `Message`
- `Attachment`
- `ConversationCheckpoint`
- `ContextSummary`
- `Page`
- `StorageUnavailableError`

No UI/product bridge may depend on PostgreSQL-specific objects.

## 3. Trusted scope boundary

Every operation MUST require an already-trusted:

```text
Scope(owner_id, tenant_id, workspace_id)
```

Rules:
1. Scope MUST never be inferred from request payload metadata.
2. Scope MUST never be optional.
3. Every read and write MUST include owner + tenant + workspace predicates.
4. Cross-scope lookup MUST resolve as unavailable, never as a partial match.
5. Conversation identifiers alone MUST NOT be treated as authorization.
6. Attachments, messages, checkpoints, summaries and idempotency records MUST be scope-bound.
7. A malformed or absent trusted scope MUST fail closed before SQL execution.

## 4. Configuration boundary

The store MUST receive a connection factory / data-source object from trusted application composition.

The store MUST NOT:
- read `DATABASE_URL` directly;
- read process environment variables directly;
- read Streamlit secrets directly;
- discover credentials dynamically;
- accept a DSN from an end-user request;
- log DSNs, passwords, tokens or connection secrets.

Configuration resolution and secret injection are a separate owner-authorized concern.

## 5. Driver boundary

The first permitted real-driver implementation SHOULD use Psycopg 3 with explicit transactions and `autocommit=False`.

Until the implementation stage is explicitly opened:
- no `psycopg`, `asyncpg` or SQLAlchemy import may be added by this design step;
- no socket/network connection may be opened.

The driver wrapper MUST translate connectivity / transaction failures into storage-layer errors without leaking secrets or raw connection strings.

## 6. Schema invariants

A real schema MUST encode enough information to prove scope isolation without trusting application memory alone.

Minimum logical entities:
- conversations;
- messages;
- attachments / records;
- checkpoints;
- context summaries;
- message idempotency ledger;
- schema metadata / version.

Required invariants:
1. Conversation scope tuple is immutable after creation.
2. Message sequence is unique within a conversation.
3. Message id is unique.
4. Idempotency key is unique for:
   `(owner_id, tenant_id, workspace_id, conversation_id, idempotency_key)`.
5. Child records cannot outlive their conversation.
6. Checkpoint coverage cannot advance past the conversation message count.
7. Summary sources must belong to the same scoped conversation and be within coverage.
8. Schema version mismatch fails closed.

No automatic migration is permitted inside application startup.

## 7. Transaction contract — append_message

Appending a message MUST be atomic with conversation count advancement.

Required semantic sequence:
1. Require healthy store.
2. Validate trusted scope.
3. Validate role and attachment references.
4. Begin transaction.
5. Locate the scoped conversation and acquire a write-safe serialization boundary.
6. Check idempotency ledger.
7. If the idempotency key already exists, return the original stored message.
8. Otherwise assign the next sequence exactly once.
9. Insert the message.
10. Persist the idempotency key → message id mapping.
11. Advance conversation `message_count` and `updated_at`.
12. Commit.
13. Return only after commit acknowledgement is known.

The implementation MUST prevent two concurrent appends from receiving the same sequence.

## 8. Unknown commit outcome

A lost acknowledgement after COMMIT is not equivalent to a confirmed rollback.

If commit success cannot be proven, the store MUST raise a dedicated unknown-outcome error carrying only the safe reconciliation key.

The caller MUST NOT blindly retry the append.

The only allowed recovery path is:
1. query the idempotency ledger using the trusted scope + conversation + idempotency key;
2. if a stored message is found, return that original message;
3. if no record is found and transaction state is known to be absent, a new attempt may be considered by higher-level policy;
4. if certainty is still unavailable, remain fail closed.

Exactly-once user-visible behavior is the target; duplicate writes are not acceptable.

## 9. Idempotency semantics

An idempotency key is mandatory for message append.

For a duplicate key in the same scope and conversation:
- return the originally committed message;
- do not create a second message;
- do not increment `message_count`;
- do not mutate the original payload.

A key from another owner / tenant / workspace MUST never match.

## 10. Health gate

`storage_health()` and `require_healthy()` MUST prove at least:
- connectivity to the selected database;
- expected schema version;
- transaction capability;
- scope-policy/schema invariants required by this contract.

The store MUST fail closed when:
- database is unreachable;
- schema version differs;
- transaction initialization fails;
- required constraint / policy metadata is absent;
- connection state is ambiguous.

A shallow TCP success is not sufficient evidence of a healthy store.

## 11. Pagination and query behavior

Cursor semantics MUST remain scope-bound.

A cursor created for one:
- owner;
- tenant;
- workspace;
- conversation/query specification

MUST NOT be reusable against another scope or query.

Page-size limits remain bounded at 1..200 unless separately changed and reviewed.

## 12. Attachments, checkpoints and summaries

Attachment storage in this stage remains metadata-only.

The Postgres adapter MUST preserve:
- attachment metadata validation;
- scoped lookup;
- checkpoint monotonic coverage;
- summary source validation;
- no implicit binary/object-store upload;
- no external provider invocation.

## 13. Error model

Required externally meaningful states:
- healthy success;
- lookup unavailable;
- validation error;
- storage unavailable;
- commit outcome unknown.

Raw database exceptions MUST not cross the adapter boundary when they contain implementation or credential details.

Integrity errors that indicate contract violations MUST be translated deterministically.

## 14. Logging and evidence

Permitted evidence:
- operation class;
- safe scope hash / non-secret identifiers where already policy-approved;
- transaction outcome class;
- schema version;
- health state;
- reconciliation outcome.

Forbidden evidence:
- DSN;
- password;
- secret/token values;
- full credential-bearing exception strings.

No log entry may claim a commit succeeded unless acknowledgement or idempotency reconciliation proves it.

## 15. Test obligations before any production connection

The first real-driver implementation MUST run only against an ephemeral PostgreSQL service in CI and prove at least:

1. protocol surface parity with `AionChatStore`;
2. trusted-scope fail-closed behavior;
3. cross-owner / cross-tenant / cross-workspace denial;
4. atomic append;
5. concurrent append sequence uniqueness;
6. duplicate idempotency returns original message exactly once;
7. simulated unknown-commit reconciliation;
8. connection failure fail-closed;
9. schema mismatch fail-closed;
10. attachment scoping;
11. checkpoint monotonicity;
12. summary source coverage;
13. bounded scoped retrieval;
14. cursor scope binding;
15. no provider / billing / deploy / Worker / Core execution.

The CI database MUST be disposable and contain no production credentials or production data.

## 16. Authorization boundaries

This design contract authorizes no environment mutation.

Separately authorized steps are required for:
- adding the actual Postgres driver dependency;
- adding executable SQL/schema;
- configuring a DSN/secret;
- provisioning a database;
- applying migrations;
- connecting to Render or any production provider;
- deployment;
- enabling Worker execution.

Core V1 remains frozen and MUST NOT be modified by this workstream.

## 17. Next allowed step

After this contract is reviewed and green as a design-only change:

`IMPLEMENT_EPHEMERAL_POSTGRES_DRIVER_BINDING_V1`

That step must:
- bind the adapter to an ephemeral PostgreSQL instance only;
- add explicit tests before any production credentials exist;
- keep deploy disabled;
- keep Worker disarmed;
- keep provider/model execution disabled;
- preserve the frozen Core.
