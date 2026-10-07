# AION Chat — PostgreSQL Migration + RLS + Restore Drill CI V1

Status: IMPLEMENTATION SAFE / CI-ONLY  
Date: 2026-10-07  
Depends on: PR #991 real PostgreSQL CI binding + PR #993 production PostgreSQL preflight  
Runtime target: disposable PostgreSQL 17 in GitHub Actions only

## Purpose

Validate the next production-like database controls without touching Render or any production infrastructure.

This stage proves, in disposable CI only:

- explicit versioned migration V1;
- SHA-256 checksum binding;
- PostgreSQL advisory-lock serialization;
- no application-startup auto-migration;
- additive production-like schema;
- owner/tenant/workspace composite scope;
- scoped foreign keys and idempotency;
- PostgreSQL RLS enabled and forced as defense in depth;
- least-privilege non-superuser application role;
- default-deny behavior when trusted scope context is absent;
- cross-scope read/write denial;
- deterministic backup/restore drill using PostgreSQL 17 `pg_dump` / `pg_restore`;
- post-restore schema/migration/RLS/fixture attestation.

## Migration artifact

Migration:

`migrations/aion_chat_postgres_v1/0001_initial.sql`

Version:

`1`

Pinned SHA-256:

`d57d5c225c86306afb79cb1d5dba2a6cd8e2838730ac27171243b4ec82664ab2`

The migration runner computes the repository artifact SHA-256 before opening the database. A mismatch fails closed.

Applied migration history stores the same checksum. A database that reports version 1 with another checksum also fails closed.

## Serialization

Migration application uses a PostgreSQL transaction-scoped advisory lock.

Two concurrent migration attempts must result in exactly:

- one `APPLIED`;
- one `ALREADY_APPLIED`.

No second schema application is permitted.

The CI suite also proves that an ambiguous migration-history state fails closed and that a migration error after partial DDL execution rolls the transaction back without writing a false migration-history success record.

## Schema candidate

The production-like schema candidate is:

`aion_chat_v1`

It contains:

- `schema_migrations`;
- `schema_meta`;
- `conversations`;
- `messages`;
- `message_idempotency`;
- `attachments`;
- `checkpoints`;
- `summaries`;
- `access_audit`.

The access audit table is operational and does not require message body copies.

## RLS defense in depth

RLS is enabled and forced on all scope-bearing durable tables.

Policy predicates bind:

- `owner_id`;
- `tenant_id`;
- `workspace_id`.

The disposable CI application role has:

- no SUPERUSER;
- no CREATEDB;
- no CREATEROLE;
- no REPLICATION;
- no BYPASSRLS;
- no CREATE privilege on the AION Chat schema;
- no DELETE privilege on application data tables by default;
- no UPDATE privilege on messages, idempotency, attachments, checkpoints, summaries or audit rows.

The least-privilege profile grants:

- conversations: SELECT + INSERT + UPDATE;
- messages/idempotency/attachments/checkpoints/summaries: SELECT + INSERT;
- access audit: SELECT + INSERT only;
- schema metadata: SELECT only;
- migration history: no application-role access.

Retention/deletion remains a separate controlled capability rather than an ordinary application-role privilege. Audit rows are append-only under the application role.

RLS is defense in depth only. Trusted application scope validation remains mandatory; RLS does not replace authentication or the existing application-level scope predicates.

## Default deny

The CI evidence must show:

- no scope context -> zero scoped rows visible;
- wrong owner/tenant/workspace -> foreign rows invisible;
- an insert that conflicts with the bound scope is rejected;
- a correctly bound scope sees only its own rows;
- scope context is transaction-local and clears after commit, preventing pooled-connection scope bleed;
- append-only audit data cannot be updated or deleted by the application role.

The CI binding uses transaction-local PostgreSQL settings for owner, tenant and workspace scope. Production composition must preserve this property for every pooled connection/transaction; session-persistent scope values are not acceptable.

## Backup / restore drill

The dedicated workflow must:

1. apply the checksum-bound migration to disposable PostgreSQL 17;
2. run migration/RLS/least-privilege tests;
3. seed a deterministic non-secret restore fixture;
4. create a PostgreSQL custom-format logical backup using the matching PostgreSQL 17 client image;
5. create a fresh restore database;
6. restore with `pg_restore`;
7. attest migration checksum, schema version, RLS/forced-RLS, policies, constraints, transaction health and restore fixture digest.

This is a CI restore drill only. It is not evidence that Render PITR, provider backup retention or a real production restore has been tested.

## Security boundary

The store/runner does not read:

- `DATABASE_URL`;
- Render credentials;
- Streamlit secrets;
- provider tokens;
- production passwords.

The workflow uses test-only loopback credentials in a disposable GitHub Actions PostgreSQL service.

No production credential is committed.

## Explicitly not performed

- Render login or provisioning;
- paid resource creation;
- production DSN/hostname/user/password configuration;
- production migration;
- production backup or PITR;
- production restore;
- application deployment;
- Global Worker activation;
- model/provider execution;
- WhatsApp/e-mail/payment/trading actions;
- Core V1 mutation.

## Maximum truthful state

After all dedicated CI evidence is green, this branch may claim only:

`POSTGRES_MIGRATION_RLS_RESTORE_VALIDATED_IN_CI`

It must not claim production storage readiness or production restore readiness.

Core V1 remains frozen.

## Next boundary

After green CI, remaining production-only evidence still requires authenticated provider access:

1. current provider plan/price verification;
2. same-region provisioning;
3. private network + TLS;
4. least-privilege production role/secret injection;
5. provider backup/recovery-point evidence;
6. protected migration against the provisioned instance;
7. real restore drill / recovery evidence;
8. production connection attestation;
9. separate deployment decision.
