# AION Chat — Ephemeral PostgreSQL Binding V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: PR #986 + PR #989  
Runtime target: disposable PostgreSQL service in GitHub Actions only

## Purpose

Implement the first real Psycopg/PostgreSQL persistence path for AION Chat without creating or connecting to any production database.

This stage exists to prove the storage contract against a real PostgreSQL transaction engine before production credentials, Render configuration, migration authority, deploy authority, provider execution, billing, Global Worker activation, external actions or Core writes are allowed.

## What is implemented

- psycopg[binary]==3.3.6 pinned in requirements.txt.
- Real PostgreSQL connection factory boundary.
- Store code does not read environment variables, DATABASE_URL, Streamlit secrets or provider credentials.
- Explicit disposable schema installer for CI/tests only; it is never called by store startup.
- Scope tuple persisted on all durable entities: owner, tenant and workspace.
- Composite scoped foreign keys.
- Scoped conversations, messages, attachment metadata, checkpoints and summaries.
- Dedicated message idempotency ledger.
- Explicit transactions with autocommit=False.
- SELECT ... FOR UPDATE serialization for message sequence allocation.
- Atomic message insert + idempotency mapping + conversation count advance.
- Dedicated CommitOutcomeUnknownError path plus idempotency reconciliation.
- Schema-version/required-table health gate.
- Fail-closed connection/schema behavior.
- Real concurrent-append test against PostgreSQL.
- Cross-owner, cross-tenant and cross-workspace denial tests.
- HMAC-authenticated keyset cursors with caller-injected signing key.
- Cursor binding covers owner/tenant/workspace scope plus resource/query specification.
- Conversation pagination is keyset-bound by updated_at + id.
- Message pagination is keyset-bound by sequence and direction.
- Conversation search/filter pagination is executed in PostgreSQL, including title/message query, tag, date bounds and archived state.
- Retrieval query is executed directly in PostgreSQL and is no longer capped by the legacy 201-row adapter fetch.
- No binary attachment storage; metadata only.

## CI database

The workflow creates a disposable PostgreSQL service container with test-only credentials and test-only data.

The test composition layer receives AION_CHAT_EPHEMERAL_PG_DSN. The store implementation itself never reads that variable. Tests build the connection factory and inject it into the store.

The service is loopback-only from the CI job and is destroyed after the workflow. No production secret is referenced.

## Evidence required by the workflow

The dedicated workflow must prove:

1. Psycopg dependency is pinned and importable.
2. The prior fake-adapter regression remains green.
3. The real adapter preserves the AionChatStore callable surface.
4. Owner/tenant/workspace scope is default-deny.
5. Atomic append increments sequence/count once.
6. Eight concurrent appends receive unique contiguous sequences.
7. Duplicate idempotency key returns the original committed message.
8. Simulated unknown commit is reconciled explicitly through the idempotency ledger.
9. Connection failure fails closed.
10. Schema version mismatch fails closed.
11. Attachment metadata remains scope-bound.
12. Checkpoint coverage is monotonic and cannot exceed message count.
13. Summary source coverage is validated.
14. Retrieval limits remain bounded and scope-bound.
15. Non-empty cursors are HMAC-authenticated and fail closed if tampered, cross-scope, cross-conversation, cross-direction or reused under a different query/filter specification.
16. Ascending and newest-first message keyset pagination returns complete non-duplicated sequences across pages.
17. Conversation keyset pagination preserves query/tag filters across pages.
18. Cursor signing material is injected by composition; the store does not resolve it from environment or provider secrets.
19. Provider, billing, deploy, Worker, external-action and Core execution remain absent.

## Bound cursor pagination

This stage now implements keyset cursor pagination for the real PostgreSQL path.

Cursor tokens are opaque, HMAC-authenticated and bound to:

- owner + tenant + workspace scope;
- resource kind;
- conversation id and newest-first direction for message history;
- query, tag, since, until and archived filters for conversation history.

The cursor signing key is caller-injected and must contain at least 32 bytes. The store does not read it from environment variables or provider configuration.

A cursor is rejected fail-closed when its signature is invalid, its scope changes, its conversation/direction changes, or its query/filter specification changes. This prevents a cursor issued for one authority/query from becoming evidence for another.

This CI implementation does not authorize or define the future production secret source. Production composition must provide a stable, least-privilege secret through a separately reviewed configuration boundary.

## Explicitly not authorized or implemented

- Render PostgreSQL provisioning;
- production hostname/DSN;
- production username/password;
- secret manager lookup;
- application startup migration;
- production schema migration;
- production data copy/import;
- external model/provider calls;
- billing/spend;
- deploy;
- Global Worker arming or activation;
- WhatsApp/e-mail/payment actions;
- trading execution;
- Core checkpoint mutation.

Core V1 remains frozen.

## Maximum positive state

If the dedicated workflow is green, this branch may claim only EPHEMERAL_POSTGRES_BINDING_VALIDATED_IN_CI.

It must not claim production persistence readiness.

## Next allowed decision

After green CI and review: REVIEW_EPHEMERAL_POSTGRES_EVIDENCE_BEFORE_ANY_PRODUCTION_BINDING.

Any production database connection remains a separate HUMAN_OWNER-authorized step.
