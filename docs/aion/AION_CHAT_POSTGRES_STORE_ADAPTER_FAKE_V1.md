# AION Chat — Non-Network Postgres Store Adapter Skeleton V1

## Purpose

Implement the future production store shape against an in-memory fake backend
before introducing a Postgres driver or real connection.

This is executable test scaffolding, but it has **zero network/DB-provider
execution**.

## What is implemented

- `PostgresChatStoreAdapterSkeleton` with the existing `AionChatStore`
  method surface;
- trusted `Scope(owner_id, tenant_id, workspace_id)` on every operation;
- in-memory fake backend with explicit health/schema-policy state;
- conversation/message/attachment/checkpoint/summary behavior;
- append idempotency;
- atomic sequence + message-count behavior under one fake transaction lock;
- explicit `CommitOutcomeUnknownError`;
- separate idempotency reconciliation after unknown commit;
- health/schema mismatch fail-closed.

## What is intentionally not implemented

- Postgres driver import;
- connection string;
- credentials/secrets;
- SQL;
- migrations;
- Render DB integration;
- provider/model logic;
- billing;
- deploy;
- Worker;
- external actions;
- Core writes.

## Unknown commit semantics

The fake backend can simulate: commit happened, acknowledgement certainty was
lost.

The adapter surfaces `CommitOutcomeUnknownError` and does not claim failure or
success. The caller must reconcile by idempotency key.

The test proves the underlying message exists exactly once after reconciliation.

## Compatibility

The skeleton reuses the existing:

- `Scope`
- `Conversation`
- `Message`
- `Attachment`
- `ConversationCheckpoint`
- `ContextSummary`
- `Page`
- `StorageUnavailableError`

This minimizes future UI/product bridge changes.

## Next allowed step

`DESIGN_REAL_POSTGRES_DRIVER_BINDING_CONTRACT`

A real driver must remain separately reviewed, with no production connection
until HUMAN_OWNER explicitly authorizes provisioning/configuration/deploy.
