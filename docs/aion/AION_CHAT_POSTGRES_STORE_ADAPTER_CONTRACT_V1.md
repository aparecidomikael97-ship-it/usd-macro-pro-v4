# AION Chat — Postgres Store Adapter Implementation Contract V1

## Purpose

Define the implementation boundary for a future production Postgres-backed
`AionChatStore` without importing a database driver or opening a connection.

## Compatibility

The future adapter must preserve the existing `AionChatStore` protocol and
reuse existing AION chat model types. UI/product bridges should not need a
second storage API.

Required capabilities include:

- conversation create/get/list/search/archive;
- message append/get/list;
- attachment metadata add/get;
- checkpoint save/get;
- context summary save/get;
- scoped retrieval.

## Scope safety

Every storage operation requires a trusted `Scope(owner_id, tenant_id,
workspace_id)`.

Application scope checks remain mandatory even if PostgreSQL RLS is enabled.

There is no unscoped admin query mode.

## Transaction safety

`append_message` must atomically:

1. lock/serialize the conversation sequence;
2. verify scoped conversation and attachments;
3. enforce idempotency;
4. append exactly one message;
5. update conversation message count/timestamp in the same transaction.

If commit outcome becomes uncertain, state is
`COMMIT_OUTCOME_UNKNOWN`. Blind retry is forbidden.

## Health safety

Before production storage operations, the adapter must verify:

- DB connectivity/health;
- compatible schema version;
- required scope/RLS policy health.

Unknown or failed health is fail-closed.

## Separation of concerns

The Postgres store adapter never:

- selects or calls an AI provider;
- grants approval;
- evaluates model budget;
- sends external actions;
- writes Core checkpoint state.

Those remain separate layers.

## Maximum state

`READY_FOR_POSTGRES_STORE_ADAPTER_IMPLEMENTATION`

## Next allowed step

`IMPLEMENT_NON_NETWORK_POSTGRES_ADAPTER_SKELETON_WITH_FAKE_BACKEND`

That next step must use a fake/in-memory DB boundary for tests only and must not
connect to production.
