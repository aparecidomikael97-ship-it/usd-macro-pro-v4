# AION Chat — Production Schema Binding CI V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: #991, #993, #994  
Runtime target: disposable PostgreSQL 17 only

## Purpose

Prove that the real Psycopg-backed AION Chat store can operate against the
production-like `aion_chat_v1` schema under forced PostgreSQL RLS and a
least-privilege application-role profile.

This closes the gap between two previously separate facts:

1. the real adapter worked against the disposable ephemeral schema; and
2. the production-like migration/RLS/restore schema worked independently.

This stage binds those two paths together in CI.

## Adapter refactor

The real PostgreSQL backend now receives an explicit trusted schema identifier
at construction time. The default remains the existing disposable schema, so
the earlier ephemeral path is preserved.

Scope-bearing operations also expose an internal scope-binding hook.

The base ephemeral backend keeps that hook as a no-op beyond trusted Scope
validation. The production-schema CI binding overrides the hook to establish
transaction-local PostgreSQL settings for:

- `app.owner_id`;
- `app.tenant_id`;
- `app.workspace_id`.

Application-level scope predicates remain present in every SQL statement.
RLS is defense in depth, not the sole authorization boundary.

## Transaction-local scope

Production-like scope context is installed with PostgreSQL transaction-local
settings.

The binding proves that the values exist during the transaction and clear after
COMMIT. This prevents a future pooled connection from accidentally carrying one
owner/tenant/workspace scope into the next request.

Session-persistent scope context is not accepted by this design.

## Least-privilege role

The CI binding uses the fixed disposable role:

`aion_chat_app_ci`

The role is created with:

- NOSUPERUSER;
- NOCREATEDB;
- NOCREATEROLE;
- NOREPLICATION;
- NOBYPASSRLS;
- no CREATE privilege on `aion_chat_v1`;
- no access to `schema_migrations`.

Its DML profile is:

- conversations: SELECT + INSERT + UPDATE;
- messages: SELECT + INSERT;
- message idempotency: SELECT + INSERT;
- attachments: SELECT + INSERT;
- checkpoints: SELECT + INSERT;
- summaries: SELECT + INSERT;
- access audit: SELECT + INSERT.

Ordinary application DELETE is absent. Append-only tables do not receive
UPDATE.

The health gate fails closed if that privilege profile drifts.

## Real schema compatibility

The production-like conversations table contains both `created_at` and
`updated_at`.

The shared real PostgreSQL backend now persists `Conversation.created_at`
explicitly. The disposable ephemeral schema was updated to preserve structural
compatibility, and the original ephemeral adapter regression suite remains
mandatory.

## Health gate

The production-schema CI health report requires all of the following:

- base schema version health;
- required composite constraints;
- transaction health;
- all expected RLS tables present;
- RLS enabled and forced;
- all expected scope policies present;
- current DB role is the fixed least-privilege CI role;
- no superuser / createdb / createrole / replication / bypass-RLS authority;
- no schema CREATE;
- no migration-history SELECT;
- append-only privilege profile intact.

Any drift produces `failed` and `require_healthy()` rejects use.

## Behavior proved through the real adapter

The dedicated tests cover:

- AionChatStore protocol surface;
- real Conversation create/load on `aion_chat_v1`;
- owner/tenant/workspace denial through both predicates and RLS;
- atomic append;
- concurrent contiguous message sequences;
- duplicate idempotency;
- unknown-commit reconciliation;
- HMAC-bound cursor pagination;
- query/tag search and bounded retrieval;
- attachment metadata;
- checkpoint coverage;
- context summaries;
- transaction-local scope clearing;
- forced-RLS health drift;
- privilege drift;
- connection failure fail-closed.

## Configuration boundary

The store still does not read:

- `DATABASE_URL`;
- process environment configuration;
- Streamlit secrets;
- Render credentials;
- production passwords or DSNs.

The connection factory and cursor signing key remain injected from a separate
composition boundary.

The CI use of `SET ROLE aion_chat_app_ci` exists only to simulate connecting
as the future least-privilege application identity while GitHub Actions owns the
disposable PostgreSQL service. Production composition is expected to connect
directly with the least-privilege application identity rather than rely on a
superuser plus SET ROLE.

## Explicitly absent

This stage does not:

- authenticate to Render;
- provision a production database;
- configure a production credential;
- apply a production migration;
- test provider PITR;
- deploy AtlasQuant;
- activate Global Worker;
- call an external model/provider;
- send WhatsApp/e-mail/payment/trading actions;
- mutate Core V1.

## Maximum truthful state

After green dedicated CI and green main-target validation, the maximum claim is:

`PRODUCTION_SCHEMA_ADAPTER_BINDING_VALIDATED_IN_CI`

This is not production persistence readiness.

## Remaining production-only boundary

When the HUMAN_OWNER is back at the computer, the next external sequence remains:

1. authenticate to Render;
2. verify current plan, exact price and application region;
3. pass the #993 preflight;
4. provision only if within the approved ceiling;
5. configure private networking + TLS;
6. create/inject least-privilege production identity;
7. verify provider backup/recovery point;
8. apply the protected migration;
9. run production connection and restore attestations;
10. keep deployment as a separate decision.
